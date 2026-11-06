import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models import Owner, FinancialEntry, Invoice, Obligation
from backend.app.schemas import FinancialEntryCreate, FinancialSummaryResponse
from backend.app.guardrail.audit import append_audit_log


class FinancialService:

    @staticmethod
    def get_summary(db: Session, owner: Owner) -> FinancialSummaryResponse:
        """
        Calculate authoritative cash position:
        - Confirmed cash (never conflated with expected income)
        - Expected inflows (next 30d)
        - Expected outflows (next 30d)
        - Emergency reserve target vs actual
        """
        now = datetime.datetime.utcnow()
        thirty_days_later = now + datetime.timedelta(days=30)

        # 1. Base opening balance from confirmed entries or owner baseline
        confirmed_balance_entries = db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == owner.id,
            FinancialEntry.status == "confirmed"
        ).all()

        confirmed_balance = Decimal("1800.00") if owner.is_demo else Decimal("0.00")
        for e in confirmed_balance_entries:
            if e.entry_type in ["income", "opening_balance"]:
                confirmed_balance += Decimal(str(e.amount))
            elif e.entry_type == "expense":
                confirmed_balance -= Decimal(str(e.amount))

        # 2. Invoices (expected inflows)
        open_invoices = db.query(Invoice).join(Invoice.client).filter(
            Invoice.client.has(owner_id=owner.id),
            Invoice.status.in_(["SENT", "DRAFT"])
        ).all()

        expected_inflows = Decimal("0.00")
        for inv in open_invoices:
            if inv.due_date <= thirty_days_later:
                expected_inflows += Decimal(str(inv.amount))

        # 3. Obligations and expenses (expected outflows)
        obligations = db.query(Obligation).filter(
            Obligation.owner_id == owner.id,
            Obligation.status != "paid"
        ).all()

        expected_outflows = Decimal("0.00")
        for ob in obligations:
            if ob.due_date <= thirty_days_later:
                expected_outflows += Decimal(str(ob.amount))

        # Additional financial entries next 30 days
        entries_30d = db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == owner.id,
            FinancialEntry.transaction_date >= now,
            FinancialEntry.transaction_date <= thirty_days_later,
            FinancialEntry.status.in_(["expected", "confirmed"])
        ).all()

        for ent in entries_30d:
            amt = Decimal(str(ent.amount))
            if ent.entry_type == "income":
                expected_inflows += amt
            elif ent.entry_type == "expense":
                expected_outflows += amt

        # Emergency reserve target: 1 month of average monthly expenses (~$3,000 for standard freelancer)
        reserve_target = Decimal("3000.00")
        reserve_actual = max(Decimal("0.00"), confirmed_balance)
        coverage_ratio = float(reserve_actual / reserve_target) if reserve_target > 0 else 1.0

        return FinancialSummaryResponse(
            currency=owner.currency,
            current_confirmed_balance=float(confirmed_balance),
            expected_inflows_30d=float(expected_inflows),
            expected_outflows_30d=float(expected_outflows),
            net_projected_30d=float(confirmed_balance + expected_inflows - expected_outflows),
            confirmed_inflows_count=len([e for e in confirmed_balance_entries if e.entry_type == "income"]),
            expected_inflows_count=len(open_invoices),
            pending_obligations_count=len(obligations),
            emergency_reserve_target=float(reserve_target),
            emergency_reserve_actual=float(reserve_actual),
            reserve_coverage_ratio=round(min(coverage_ratio, 2.0), 2)
        )

    @staticmethod
    def get_timeline(db: Session, owner: Owner) -> List[Dict[str, Any]]:
        """
        Build an intelligent chronological timeline of cash flows.
        Distinguishes:
        - Confirmed money (already in balance)
        - Expected money (due soon via invoice or contract)
        - Estimated money (statistical model forecast)
        - Simulated money (what-if trial)
        """
        items = []

        # 1. Financial entries
        entries = db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == owner.id
        ).order_by(FinancialEntry.transaction_date.asc()).all()

        for e in entries:
            items.append({
                "id": f"entry-{e.id}",
                "title": e.title,
                "amount": float(e.amount),
                "currency": e.currency,
                "direction": "inflow" if e.entry_type in ["income", "opening_balance"] else "outflow",
                "category": e.category,
                "date": e.transaction_date.strftime("%Y-%m-%d"),
                "status": e.status,  # confirmed | expected | estimated | simulated
                "data_source": e.data_source,
                "reference_id": e.reference_id
            })

        # 2. Invoices (Receivables)
        invoices = db.query(Invoice).join(Invoice.client).filter(
            Invoice.client.has(owner_id=owner.id)
        ).all()

        for inv in invoices:
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
                "reference_id": inv.paypal_invoice_id
            })

        # 3. Obligations (Payables)
        obligations = db.query(Obligation).filter(
            Obligation.owner_id == owner.id
        ).all()

        for ob in obligations:
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
                "reference_id": str(ob.id)
            })

        # Sort all items chronologically
        items.sort(key=lambda x: x["date"])
        return items

    @staticmethod
    def create_entry(db: Session, owner: Owner, req: FinancialEntryCreate) -> FinancialEntry:
        entry = FinancialEntry(
            owner_id=owner.id,
            title=req.title,
            amount=Decimal(str(req.amount)),
            currency=req.currency.upper(),
            entry_type=req.entry_type,
            category=req.category,
            recurrence=req.recurrence,
            transaction_date=req.transaction_date,
            status=req.status,
            data_source="manual",
            notes=req.notes,
            is_demo=owner.is_demo
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        append_audit_log(
            db,
            actor="owner",
            event="FINANCIAL_ENTRY_CREATED",
            payload={"entry_id": entry.id, "title": entry.title, "amount": float(entry.amount), "type": entry.entry_type}
        )
        return entry
