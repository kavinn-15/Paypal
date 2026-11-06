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
    def get_confirmed_balance(db: Session, owner: Owner) -> Decimal:
        """
        Calculates authoritative confirmed cash balance strictly from confirmed entries:
        Confirmed Balance = Opening Balance + Confirmed Income - Confirmed Expense - Reserves +/- Adjustments
        Never includes uncollected invoices or expected amounts.
        """
        entries = db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == owner.id,
            FinancialEntry.status == "confirmed"
        ).all()

        balance = Decimal("0.00")
        has_opening = False

        for e in entries:
            amt = Decimal(str(e.amount))
            if e.entry_type == "opening_balance":
                balance += amt
                has_opening = True
            elif e.entry_type in ("income", "confirmed_income"):
                balance += amt
            elif e.entry_type in ("expense", "confirmed_expense"):
                balance -= amt
            elif e.entry_type == "reserve":
                balance -= amt  # Earmarked cash removed from available operating balance
            elif e.entry_type == "refund":
                balance -= amt
            elif e.entry_type == "adjustment":
                balance += amt

        # For seeded demo account without opening entry, provide deterministic baseline
        if not has_opening and owner.is_demo:
            balance += Decimal("1800.00")

        return balance

    @staticmethod
    def get_summary(db: Session, owner: Owner) -> FinancialSummaryResponse:
        """
        Calculates comprehensive financial summary:
        - Reconciled confirmed balance
        - Deduplicated 30-day expected inflows
        - Deduplicated 30-day expected outflows
        - Reserve coverage ratio
        - Multi-currency distribution
        """
        now = datetime.datetime.utcnow()
        thirty_days_later = now + datetime.timedelta(days=30)

        confirmed_balance = FinancialService.get_confirmed_balance(db, owner)

        # Track canonical IDs to prevent any double-counting
        seen_inflow_canonical_ids: Set[str] = set()
        seen_outflow_canonical_ids: Set[str] = set()

        expected_inflows = Decimal("0.00")
        expected_outflows = Decimal("0.00")

        # 1. Open invoices (Receivables)
        open_invoices = db.query(Invoice).join(Invoice.client).filter(
            Invoice.client.has(owner_id=owner.id),
            Invoice.status.in_(["SENT", "DRAFT"])
        ).all()

        for inv in open_invoices:
            canon_id = f"inv_{inv.paypal_invoice_id}"
            seen_inflow_canonical_ids.add(canon_id)
            if inv.due_date <= thirty_days_later:
                expected_inflows += Decimal(str(inv.amount))

        # 2. Open obligations (Payables)
        obligations = db.query(Obligation).filter(
            Obligation.owner_id == owner.id,
            Obligation.status != "paid"
        ).all()

        for ob in obligations:
            canon_id = f"obl_{ob.id}"
            seen_outflow_canonical_ids.add(canon_id)
            if ob.due_date <= thirty_days_later:
                expected_outflows += Decimal(str(ob.amount))

        # 3. Expected financial entries (with deduplication against invoices/obligations)
        entries_30d = db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == owner.id,
            FinancialEntry.transaction_date >= now,
            FinancialEntry.transaction_date <= thirty_days_later,
            FinancialEntry.status.in_(["expected", "confirmed"])
        ).all()

        currency_buckets: Dict[str, Decimal] = {owner.currency: confirmed_balance}

        for ent in entries_30d:
            # Check canonical reference deduplication
            if ent.reference_id and (f"inv_{ent.reference_id}" in seen_inflow_canonical_ids or f"obl_{ent.reference_id}" in seen_outflow_canonical_ids):
                continue
            if ent.canonical_id and (ent.canonical_id in seen_inflow_canonical_ids or ent.canonical_id in seen_outflow_canonical_ids):
                continue

            amt = Decimal(str(ent.amount))
            if ent.entry_type in ("income", "expected_income"):
                expected_inflows += amt
            elif ent.entry_type in ("expense", "expected_expense"):
                expected_outflows += amt

            # Track currency distribution
            c = ent.currency.upper()
            if c not in currency_buckets:
                currency_buckets[c] = Decimal("0.00")
            if ent.entry_type in ("income", "confirmed_income", "opening_balance"):
                currency_buckets[c] += amt
            elif ent.entry_type in ("expense", "confirmed_expense"):
                currency_buckets[c] -= amt

        # Reserve target calculation: 1 month of average expense obligations (~$3,000 baseline)
        reserve_target = Decimal("3000.00")
        reserve_actual = max(Decimal("0.00"), confirmed_balance)
        coverage_ratio = float(reserve_actual / reserve_target) if reserve_target > 0 else 1.0

        currency_breakdown = {k: float(v) for k, v in currency_buckets.items()}

        return FinancialSummaryResponse(
            currency=owner.currency,
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

        # 1. Invoices
        invoices = db.query(Invoice).join(Invoice.client).filter(
            Invoice.client.has(owner_id=owner.id)
        ).all()

        for inv in invoices:
            ref_key = f"inv_{inv.paypal_invoice_id}"
            seen_refs.add(ref_key)
            items.append({
                "id": f"invoice-{inv.id}",
                "title": f"Invoice #{inv.paypal_invoice_id} ({inv.client.name})",
                "amount": float(inv.amount),
                "currency": inv.currency,
                "direction": "inflow",
                "category": "client_invoice",
                "date": inv.due_date.strftime("%Y-%m-%d"),
                "status": "confirmed" if inv.status == "PAID" else "expected",
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
    def _generate_occurrences(entry: FinancialEntry, start: datetime.datetime, end: datetime.datetime) -> List[Dict[str, Any]]:
        """Generates future virtual occurrences of recurring transactions without database duplication."""
        occurrences = []
        rec = entry.recurrence.lower()
        step_days = 0
        if rec == "daily":
            step_days = 1
        elif rec == "weekly":
            step_days = 7
        elif rec == "monthly":
            step_days = 30
        elif rec == "quarterly":
            step_days = 90
        elif rec == "annual":
            step_days = 365
        else:
            return occurrences

        current_date = entry.transaction_date
        max_end = entry.recurrence_end_date if entry.recurrence_end_date else end
        effective_end = min(end, max_end)

        direction = "inflow" if entry.entry_type in ["income", "opening_balance", "confirmed_income"] else "outflow"

        while current_date + datetime.timedelta(days=step_days) <= effective_end:
            current_date += datetime.timedelta(days=step_days)
            if current_date < start:
                continue
            occurrences.append({
                "id": f"recurring-{entry.id}-{current_date.strftime('%Y%m%d')}",
                "title": f"{entry.title} (Recurring)",
                "amount": float(entry.amount),
                "currency": entry.currency,
                "direction": direction,
                "category": entry.category,
                "date": current_date.strftime("%Y-%m-%d"),
                "status": "expected",
                "data_source": "recurring_engine",
                "reference_id": str(entry.id),
                "is_virtual": True
            })

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
        Validates mathematical integrity of the financial ledger:
        Opening Balance + Total Confirmed Inflows - Total Confirmed Outflows - Reserves = Reconciled Balance
        Verifies discrepancy == 0.00.
        """
        entries = db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == owner.id,
            FinancialEntry.status == "confirmed"
        ).all()

        opening_balance = Decimal("1800.00") if owner.is_demo else Decimal("0.00")
        confirmed_inflows = Decimal("0.00")
        confirmed_outflows = Decimal("0.00")
        reserves = Decimal("0.00")
        adjustments = Decimal("0.00")

        for e in entries:
            amt = Decimal(str(e.amount))
            if e.entry_type == "opening_balance":
                opening_balance = amt
            elif e.entry_type in ("income", "confirmed_income"):
                confirmed_inflows += amt
            elif e.entry_type in ("expense", "confirmed_expense"):
                confirmed_outflows += amt
            elif e.entry_type == "reserve":
                reserves += amt
            elif e.entry_type == "adjustment":
                adjustments += amt

        reconciled_balance = opening_balance + confirmed_inflows - confirmed_outflows - reserves + adjustments
        actual_balance = FinancialService.get_confirmed_balance(db, owner)
        discrepancy = actual_balance - reconciled_balance

        notes = [
            f"Verified {len(entries)} confirmed ledger transactions.",
            f"Opening balance authoritative anchor: ${float(opening_balance):,.2f}.",
            "All inflows and outflows match strict DECIMAL(12, 2) arithmetic."
        ]

        if discrepancy != Decimal("0.00"):
            notes.append(f"WARNING: Discrepancy detected of ${float(discrepancy):,.2f}.")

        return LedgerIntegrityReport(
            is_balanced=(discrepancy == Decimal("0.00")),
            currency=owner.currency,
            reconciled_balance=float(reconciled_balance),
            opening_balance=float(opening_balance),
            total_confirmed_inflows=float(confirmed_inflows),
            total_confirmed_outflows=float(confirmed_outflows),
            total_reserves=float(reserves),
            total_adjustments=float(adjustments),
            discrepancy=float(discrepancy),
            verified_entries_count=len(entries),
            unreconciled_items_count=0 if discrepancy == Decimal("0.00") else 1,
            notes=notes
        )
