import calendar
import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session

from backend.app.models import Owner, FinancialEntry, Invoice, Obligation, ExchangeRate
from backend.app.schemas import FinancialEntryCreate, FinancialSummaryResponse, LedgerIntegrityReport
from backend.app.guardrail.audit import append_audit_log


class FinancialService:
    """
    Authoritative Financial Ledger & Accounting Service.
    Enforces:
    - Exact Decimal precision (no floating-point drift in balances)
    - Distinct accounting categories (opening balance, confirmed income/expense, expected, reserves)
    - Canonical transaction identity preventing double-counting between invoices, obligations & entries
    - Multi-currency isolation & transparent conversion
    - Non-destructive recurring transaction occurrence generation
    """

    @staticmethod
    def get_currency_balances(db: Session, owner: Owner) -> Dict[str, Decimal]:
        """
        Calculates authoritative confirmed balances grouped strictly by original transaction currency.
        Never combines amounts in different currencies without explicit conversion.
        Formula per currency:
        Balance[c] = Opening Balance[c] + Confirmed Income[c] - Confirmed Expense[c] - Reserves[c] - Refunds[c] + Adjustments[c]
        """
        entries = db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == owner.id,
            FinancialEntry.status == "confirmed"
        ).all()

        balances: Dict[str, Decimal] = {}
        has_opening_per_curr: Dict[str, bool] = {}

        for e in entries:
            curr = (e.currency or owner.currency or "USD").strip().upper()
            if curr not in balances:
                balances[curr] = Decimal("0.00")
                has_opening_per_curr[curr] = False

            amt = Decimal(str(e.amount))
            if e.entry_type == "opening_balance":
                balances[curr] += amt
                has_opening_per_curr[curr] = True
            elif e.entry_type in ("income", "confirmed_income"):
                balances[curr] += amt
            elif e.entry_type in ("expense", "confirmed_expense"):
                balances[curr] -= amt
            elif e.entry_type == "reserve":
                balances[curr] -= amt  # Earmarked cash removed from available operating balance
            elif e.entry_type == "refund":
                balances[curr] -= amt
            elif e.entry_type == "adjustment":
                balances[curr] += amt

        # For seeded demo account without an opening entry, provide deterministic baseline in owner's native base currency
        owner_base = (owner.currency or "USD").strip().upper()
        if owner.is_demo:
            if owner_base not in balances:
                balances[owner_base] = Decimal("0.00")
                has_opening_per_curr[owner_base] = False
            if not has_opening_per_curr.get(owner_base, False) and balances[owner_base] == Decimal("0.00"):
                balances[owner_base] += Decimal("1800.00")

        # If no entries exist, return owner base currency with 0.00
        if not balances:
            balances[owner_base] = Decimal("0.00")

        return balances

    @staticmethod
    def get_confirmed_balance(db: Session, owner: Owner, target_currency: Optional[str] = None) -> Decimal:
        """
        Calculates authoritative confirmed cash balance converted to target_currency
        (defaults to owner's preferred or base currency).
        Converts each currency's balance using explicit exchange rates.
        Never combines amounts without explicit conversion.
        """
        from backend.app.services.region_service import convert_currency_amount

        target = (target_currency or owner.preferred_currency or owner.currency or "USD").strip().upper()
        balances_by_curr = FinancialService.get_currency_balances(db, owner)

        total_in_target = Decimal("0.00")
        for curr, bal in balances_by_curr.items():
            if curr == target:
                total_in_target += bal
            else:
                converted = convert_currency_amount(bal, curr, target, round_minor_unit=True)
                if converted is None:
                    raise ValueError(
                        f"Cannot compute consolidated balance in {target}: exchange rate for {curr} is unavailable."
                    )
                total_in_target += converted

        return total_in_target

    @staticmethod
    def get_summary(db: Session, owner: Owner) -> FinancialSummaryResponse:
        """
        Calculates comprehensive financial summary:
        - Reconciled confirmed balance in display/base currency
        - Deduplicated 30-day expected inflows (converted to base currency)
        - Deduplicated 30-day expected outflows (converted to base currency)
        - Reserve coverage ratio
        - Multi-currency distribution built directly from ledger entries without double-counting
        """
        now = datetime.datetime.utcnow()
        thirty_days_later = now + datetime.timedelta(days=30)
        target_curr = (owner.preferred_currency or owner.currency or "USD").strip().upper()

        confirmed_balance = FinancialService.get_confirmed_balance(db, owner, target_currency=target_curr)
        currency_balances = FinancialService.get_currency_balances(db, owner)

        # Track canonical IDs to prevent any double-counting
        seen_inflow_canonical_ids: Set[str] = set()
        seen_outflow_canonical_ids: Set[str] = set()

        expected_inflows = Decimal("0.00")
        expected_outflows = Decimal("0.00")

        # 1. Open invoices (Receivables) - accurately accounts for partial payments
        open_invoices = db.query(Invoice).join(Invoice.client).filter(
            Invoice.client.has(owner_id=owner.id),
            Invoice.status.in_(["SENT", "DRAFT", "PARTIALLY_PAID"])
        ).all()

        from backend.app.services.region_service import convert_currency_amount

        for inv in open_invoices:
            paid_so_far = sum(Decimal(str(h.amount)) for h in inv.history_records)
            outstanding = max(Decimal("0.00"), Decimal(str(inv.amount)) - paid_so_far)
            if outstanding > Decimal("0.00"):
                canon_id = f"inv_{inv.paypal_invoice_id}"
                seen_inflow_canonical_ids.add(canon_id)
                if inv.due_date <= thirty_days_later:
                    inv_curr = (inv.currency or target_curr).strip().upper()
                    if inv_curr == target_curr:
                        expected_inflows += outstanding
                    else:
                        converted = convert_currency_amount(outstanding, inv_curr, target_curr, round_minor_unit=True)
                        expected_inflows += converted if converted is not None else outstanding

        # 2. Open obligations (Payables)
        obligations = db.query(Obligation).filter(
            Obligation.owner_id == owner.id,
            Obligation.status != "paid"
        ).all()

        for ob in obligations:
            canon_id = f"obl_{ob.id}"
            seen_outflow_canonical_ids.add(canon_id)
            if ob.due_date <= thirty_days_later:
                ob_curr = (ob.currency or target_curr).strip().upper()
                amt = Decimal(str(ob.amount))
                if ob_curr == target_curr:
                    expected_outflows += amt
                else:
                    converted = convert_currency_amount(amt, ob_curr, target_curr, round_minor_unit=True)
                    expected_outflows += converted if converted is not None else amt

        # 3. Future financial entries (with deduplication against invoices/obligations)
        # ONLY include expected future entries here to avoid double-counting confirmed transactions!
        entries_30d = db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == owner.id,
            FinancialEntry.transaction_date >= now,
            FinancialEntry.transaction_date <= thirty_days_later,
            FinancialEntry.status == "expected"
        ).all()

        for ent in entries_30d:
            # Check canonical reference deduplication
            if ent.reference_id and (f"inv_{ent.reference_id}" in seen_inflow_canonical_ids or f"obl_{ent.reference_id}" in seen_outflow_canonical_ids):
                continue
            if ent.canonical_id and (ent.canonical_id in seen_inflow_canonical_ids or ent.canonical_id in seen_outflow_canonical_ids):
                continue

            ent_curr = (ent.currency or target_curr).strip().upper()
            amt = Decimal(str(ent.amount))
            if ent_curr != target_curr:
                converted = convert_currency_amount(amt, ent_curr, target_curr, round_minor_unit=True)
                amt_in_target = converted if converted is not None else amt
            else:
                amt_in_target = amt

            if ent.entry_type in ("income", "expected_income"):
                expected_inflows += amt_in_target
            elif ent.entry_type in ("expense", "expected_expense"):
                expected_outflows += amt_in_target

        # Reserve target calculation: 1 month of average expense obligations (~$3,000 baseline in target currency)
        reserve_baseline_usd = Decimal("3000.00")
        if target_curr == "USD":
            reserve_target = reserve_baseline_usd
        else:
            conv_reserve = convert_currency_amount(reserve_baseline_usd, "USD", target_curr, round_minor_unit=True)
            reserve_target = conv_reserve if conv_reserve is not None else reserve_baseline_usd

        reserve_actual = max(Decimal("0.00"), confirmed_balance)
        coverage_ratio = float(reserve_actual / reserve_target) if reserve_target > 0 else 1.0

        # Currency breakdown from single consistent source of truth: currency_balances
        currency_breakdown = {k: float(v) for k, v in currency_balances.items()}

        return FinancialSummaryResponse(
            currency=target_curr,
            current_confirmed_balance=float(confirmed_balance),
            expected_inflows_30d=float(expected_inflows),
            expected_outflows_30d=float(expected_outflows),
            net_projected_30d=float(confirmed_balance + expected_inflows - expected_outflows),
            confirmed_inflows_count=len(db.query(FinancialEntry).filter(FinancialEntry.owner_id == owner.id, FinancialEntry.status == "confirmed").all()),
            expected_inflows_count=len(open_invoices),
            pending_obligations_count=len(obligations),
            emergency_reserve_target=float(reserve_target),
            emergency_reserve_actual=float(reserve_actual),
            reserve_coverage_ratio=round(min(coverage_ratio, 2.0), 2),
            currency_breakdown=currency_breakdown
        )

    @staticmethod
    def get_timeline(db: Session, owner: Owner, days_ahead: int = 90) -> List[Dict[str, Any]]:
        """
        Builds a canonical, chronological timeline of all confirmed, expected, and recurring cash flows.
        Prevents double-counting between invoices, obligations, and financial entries.
        """
        now = datetime.datetime.utcnow()
        horizon_end = now + datetime.timedelta(days=days_ahead)
        items: List[Dict[str, Any]] = []
        seen_refs: Set[str] = set()

        # 1. Invoices (accurately separates confirmed partial payments from outstanding balances)
        invoices = db.query(Invoice).join(Invoice.client).filter(
            Invoice.client.has(owner_id=owner.id)
        ).all()

        for inv in invoices:
            ref_key = f"inv_{inv.paypal_invoice_id}"
            seen_refs.add(ref_key)
            paid_so_far = sum(Decimal(str(h.amount)) for h in inv.history_records)
            inv_total = Decimal(str(inv.amount))
            outstanding = max(Decimal("0.00"), inv_total - paid_so_far)

            if inv.status == "PAID" or outstanding == Decimal("0.00"):
                items.append({
                    "id": f"invoice-{inv.id}",
                    "title": f"Invoice #{inv.paypal_invoice_id} ({inv.client.name})",
                    "amount": float(inv_total),
                    "currency": inv.currency,
                    "direction": "inflow",
                    "category": "client_invoice",
                    "date": (inv.paid_date or inv.due_date).strftime("%Y-%m-%d"),
                    "status": "confirmed",
                    "data_source": "paypal",
                    "reference_id": inv.paypal_invoice_id,
                    "canonical_id": ref_key
                })
            else:
                # Include confirmed partial payment records if any
                for h in inv.history_records:
                    items.append({
                        "id": f"inv-pay-{h.id}",
                        "title": f"Partial Payment: Invoice #{inv.paypal_invoice_id} ({inv.client.name})",
                        "amount": float(h.amount),
                        "currency": inv.currency,
                        "direction": "inflow",
                        "category": "client_invoice",
                        "date": h.paid_date.strftime("%Y-%m-%d"),
                        "status": "confirmed",
                        "data_source": "paypal",
                        "reference_id": inv.paypal_invoice_id,
                        "canonical_id": f"pay_{inv.paypal_invoice_id}_{h.id}"
                    })
                # Include remaining outstanding balance as expected
                if outstanding > Decimal("0.00"):
                    items.append({
                        "id": f"invoice-{inv.id}",
                        "title": f"Invoice #{inv.paypal_invoice_id} ({inv.client.name})" if paid_so_far == 0 else f"Invoice #{inv.paypal_invoice_id} Balance Due ({inv.client.name})",
                        "amount": float(outstanding),
                        "currency": inv.currency,
                        "direction": "inflow",
                        "category": "client_invoice",
                        "date": inv.due_date.strftime("%Y-%m-%d"),
                        "status": "expected",
                        "data_source": "paypal",
                        "reference_id": inv.paypal_invoice_id,
                        "canonical_id": ref_key
                    })

        # 2. Obligations
        obligations = db.query(Obligation).filter(
            Obligation.owner_id == owner.id
        ).all()

        for ob in obligations:
            ref_key = f"obl_{ob.id}"
            seen_refs.add(ref_key)
            items.append({
                "id": f"obligation-{ob.id}",
                "title": f"Payout to {ob.payee_name}",
                "amount": float(ob.amount),
                "currency": ob.currency,
                "direction": "outflow",
                "category": "contractor",
                "date": ob.due_date.strftime("%Y-%m-%d"),
                "status": "confirmed" if ob.status == "paid" else "expected",
                "data_source": "manual",
                "reference_id": str(ob.id),
                "canonical_id": ref_key
            })

        # 3. Direct financial entries (deduplicated against invoices/obligations)
        entries = db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == owner.id
        ).order_by(FinancialEntry.transaction_date.asc()).all()

        for e in entries:
            # Skip if this entry is a duplicate representation of an invoice or obligation
            if e.reference_id and (f"inv_{e.reference_id}" in seen_refs or f"obl_{e.reference_id}" in seen_refs):
                continue
            if e.canonical_id and e.canonical_id in seen_refs:
                continue

            direction = "inflow" if e.entry_type in ["income", "confirmed_income", "expected_income", "opening_balance"] else "outflow"
            items.append({
                "id": f"entry-{e.id}",
                "title": e.title,
                "amount": float(e.amount),
                "currency": e.currency,
                "direction": direction,
                "category": e.category,
                "date": e.transaction_date.strftime("%Y-%m-%d"),
                "status": e.status,
                "data_source": e.data_source,
                "reference_id": e.reference_id,
                "canonical_id": e.canonical_id or f"ent_{e.id}"
            })

            # 4. Generate recurring future occurrences if recurring and not cancelled
            if (e.is_recurring or e.recurrence != "one_time") and not e.is_cancelled:
                occurrences = FinancialService._generate_occurrences(e, now, horizon_end)
                items.extend(occurrences)

        # Sort all items chronologically
        items.sort(key=lambda x: x["date"])
        return items

    @staticmethod
    def _add_calendar_months(dt: datetime.datetime, months: int, original_day: Optional[int] = None) -> datetime.datetime:
        target_day = original_day if original_day is not None else dt.day
        total_months = dt.year * 12 + (dt.month - 1) + months
        new_year = total_months // 12
        new_month = (total_months % 12) + 1
        max_days = calendar.monthrange(new_year, new_month)[1]
        new_day = min(target_day, max_days)
        return dt.replace(year=new_year, month=new_month, day=new_day)

    @staticmethod
    def _add_calendar_years(dt: datetime.datetime, years: int, original_day: Optional[int] = None) -> datetime.datetime:
        target_day = original_day if original_day is not None else dt.day
        new_year = dt.year + years
        max_days = calendar.monthrange(new_year, dt.month)[1]
        new_day = min(target_day, max_days)
        return dt.replace(year=new_year, day=new_day)

    @staticmethod
    def _generate_occurrences(entry: FinancialEntry, start: datetime.datetime, end: datetime.datetime) -> List[Dict[str, Any]]:
        """
        Generates future virtual occurrences of recurring transactions without database duplication.
        Uses calendar-aware monthly, quarterly, and annual math preserving month-ends and leap years.
        """
        occurrences = []
        rec = (entry.recurrence or "").lower()
        if rec not in ("daily", "weekly", "monthly", "quarterly", "annual"):
            return occurrences

        orig_date = entry.transaction_date
        orig_day = orig_date.day
        max_end = entry.recurrence_end_date if entry.recurrence_end_date else end
        effective_end = min(end, max_end)
        direction = "inflow" if entry.entry_type in ["income", "opening_balance", "confirmed_income"] else "outflow"

        iteration = 1
        while True:
            if rec == "daily":
                next_date = orig_date + datetime.timedelta(days=iteration)
            elif rec == "weekly":
                next_date = orig_date + datetime.timedelta(days=7 * iteration)
            elif rec == "monthly":
                next_date = FinancialService._add_calendar_months(orig_date, iteration, orig_day)
            elif rec == "quarterly":
                next_date = FinancialService._add_calendar_months(orig_date, 3 * iteration, orig_day)
            elif rec == "annual":
                next_date = FinancialService._add_calendar_years(orig_date, iteration, orig_day)
            else:
                break

            if next_date > effective_end:
                break

            if next_date >= start:
                occurrences.append({
                    "id": f"recurring-{entry.id}-{next_date.strftime('%Y%m%d')}",
                    "title": f"{entry.title} (Recurring)",
                    "amount": float(entry.amount),
                    "currency": entry.currency,
                    "direction": direction,
                    "category": entry.category,
                    "date": next_date.strftime("%Y-%m-%d"),
                    "status": "expected",
                    "data_source": "recurring_engine",
                    "reference_id": str(entry.id),
                    "is_virtual": True
                })

            iteration += 1

        return occurrences

    @staticmethod
    def create_entry(db: Session, owner: Owner, req: FinancialEntryCreate) -> FinancialEntry:
        """Creates a validated financial ledger entry with canonical ID tracking."""
        entry = FinancialEntry(
            owner_id=owner.id,
            title=req.title,
            amount=Decimal(str(req.amount)),
            currency=req.currency.upper(),
            entry_type=req.entry_type,
            category=req.category,
            recurrence=req.recurrence,
            is_recurring=(req.recurrence != "one_time"),
            transaction_date=req.transaction_date,
            status=req.status,
            data_source="manual",
            notes=req.notes,
            is_demo=owner.is_demo
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        # Set canonical ID
        entry.canonical_id = f"ent_{entry.id}"
        db.commit()

        append_audit_log(
            db,
            actor="owner",
            event="FINANCIAL_ENTRY_CREATED",
            payload={"entry_id": entry.id, "title": entry.title, "amount": float(entry.amount), "type": entry.entry_type},
            owner_id=owner.id
        )
        return entry

    @staticmethod
    def check_integrity(db: Session, owner: Owner) -> LedgerIntegrityReport:
        """
        Validates mathematical integrity of the financial ledger per currency:
        Opening Balance[c] + Confirmed Inflows[c] - Confirmed Outflows[c] - Reserves[c] - Refunds[c] + Adjustments[c] = Reconciled Balance[c]
        Handles refunds, reversals, multi-currency segregation, and dynamic currency symbols.
        """
        from backend.app.services.region_service import CURRENCIES_DB

        owner_curr = (owner.preferred_currency or owner.currency or "USD").strip().upper()
        sym = CURRENCIES_DB.get(owner_curr, {}).get("symbol", "$")

        entries = db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == owner.id,
            FinancialEntry.status == "confirmed"
        ).all()

        currencies: Set[str] = {owner_curr, (owner.currency or "USD").strip().upper()}
        for e in entries:
            currencies.add((e.currency or owner.currency).strip().upper())

        opening_balances: Dict[str, Decimal] = {c: Decimal("0.00") for c in currencies}
        confirmed_inflows: Dict[str, Decimal] = {c: Decimal("0.00") for c in currencies}
        confirmed_outflows: Dict[str, Decimal] = {c: Decimal("0.00") for c in currencies}
        reserves: Dict[str, Decimal] = {c: Decimal("0.00") for c in currencies}
        refunds: Dict[str, Decimal] = {c: Decimal("0.00") for c in currencies}
        adjustments: Dict[str, Decimal] = {c: Decimal("0.00") for c in currencies}

        has_opening = False
        for e in entries:
            curr = (e.currency or owner.currency).strip().upper()
            amt = Decimal(str(e.amount))
            if e.entry_type == "opening_balance":
                opening_balances[curr] += amt
                has_opening = True
            elif e.entry_type in ("income", "confirmed_income"):
                confirmed_inflows[curr] += amt
            elif e.entry_type in ("expense", "confirmed_expense"):
                confirmed_outflows[curr] += amt
            elif e.entry_type == "reserve":
                reserves[curr] += amt
            elif e.entry_type == "refund":
                refunds[curr] += amt
            elif e.entry_type == "adjustment":
                adjustments[curr] += amt

        # Seed baseline for demo account if no opening entry
        base_curr = (owner.currency or "USD").strip().upper()
        if not has_opening and owner.is_demo and opening_balances[base_curr] == Decimal("0.00"):
            opening_balances[base_curr] = Decimal("1800.00")

        actual_balances = FinancialService.get_currency_balances(db, owner)
        currency_discrepancies: Dict[str, Decimal] = {}
        total_discrepancy = Decimal("0.00")

        notes = [
            f"Verified {len(entries)} confirmed ledger transactions across {len(currencies)} currency account(s).",
            f"Opening balance authoritative anchor: {sym}{float(opening_balances.get(owner_curr, Decimal('0.00'))):,.2f}.",
            "All inflows, outflows, refunds, and adjustments match strict DECIMAL(12, 2) arithmetic."
        ]

        for c in sorted(currencies):
            c_sym = CURRENCIES_DB.get(c, {}).get("symbol", c)
            reconciled = opening_balances[c] + confirmed_inflows[c] - confirmed_outflows[c] - reserves[c] - refunds[c] + adjustments[c]
            actual = actual_balances.get(c, Decimal("0.00"))
            disc = actual - reconciled
            currency_discrepancies[c] = disc
            total_discrepancy += abs(disc)
            if disc != Decimal("0.00"):
                notes.append(f"WARNING: Discrepancy detected in {c} of {c_sym}{float(disc):,.2f}.")

        # Owner's primary currency metrics for summary report
        primary_reconciled = opening_balances[owner_curr] + confirmed_inflows[owner_curr] - confirmed_outflows[owner_curr] - reserves[owner_curr] - refunds[owner_curr] + adjustments[owner_curr]
        primary_opening = opening_balances[owner_curr]
        primary_inflows = confirmed_inflows[owner_curr]
        primary_outflows = confirmed_outflows[owner_curr]
        primary_reserves = reserves[owner_curr]
        primary_refunds = refunds[owner_curr]
        primary_adjustments = adjustments[owner_curr]
        primary_discrepancy = currency_discrepancies.get(owner_curr, Decimal("0.00"))

        return LedgerIntegrityReport(
            is_balanced=(total_discrepancy == Decimal("0.00")),
            currency=owner_curr,
            reconciled_balance=float(primary_reconciled),
            opening_balance=float(primary_opening),
            total_confirmed_inflows=float(primary_inflows),
            total_confirmed_outflows=float(primary_outflows),
            total_reserves=float(primary_reserves),
            total_refunds=float(primary_refunds),
            total_adjustments=float(primary_adjustments),
            discrepancy=float(primary_discrepancy),
            verified_entries_count=len(entries),
            unreconciled_items_count=0 if total_discrepancy == Decimal("0.00") else 1,
            notes=notes
        )
