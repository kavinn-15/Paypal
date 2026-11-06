from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from backend.app.db import get_db
from backend.app.models import AuditLog
from backend.app.schemas import AuditLogOut, AuditVerifyResponse
from backend.app.guardrail.audit import verify_audit_chain

router = APIRouter(prefix="/audit", tags=["Audit Log & Integrity"])


@router.get("", response_model=List[AuditLogOut])
def list_audit_logs(db: Session = Depends(get_db)):
    """Returns chronological audit log entries."""
    return db.query(AuditLog).order_by(AuditLog.id.desc()).all()


@router.get("/verify", response_model=AuditVerifyResponse)
def verify_audit_log_chain(db: Session = Depends(get_db)):
    """
    Verifies the cryptographic SHA-256 hash chain of the entire audit log from Genesis to Tip.
    Detects any database tampering, alteration, or deletion of historical records.
    """
    is_valid, total_blocks, msg, corrupted_id = verify_audit_chain(db)
    return AuditVerifyResponse(
        chain_valid=is_valid,
        total_blocks=total_blocks,
        genesis_valid=is_valid,
        message=msg,
        corrupted_block_id=corrupted_id
    )

