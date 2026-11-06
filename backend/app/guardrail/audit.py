import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from backend.app.models import AuditLog

GENESIS_HASH = "0" * 64


def serialize_payload(payload: Dict[str, Any]) -> str:
    """Deterministically serializes payload dict to JSON with sorted keys."""
    return json.dumps(payload, sort_keys=True, default=str)


def compute_hash(
    prev_hash: str,
    ts: datetime,
    actor: str,
    event: str,
    payload: Dict[str, Any]
) -> str:
    """Computes SHA-256 cryptographic hash chaining prev_hash with event metadata."""
    payload_str = serialize_payload(payload)
    # Normalize timestamp to UTC naive ISO string for consistent SQLite roundtrip
    if isinstance(ts, datetime):
        if ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S.%f")
    else:
        ts_str = str(ts).replace("+00:00", "").replace("Z", "").replace(" ", "T")

    content = f"{prev_hash}|{ts_str}|{actor}|{event}|{payload_str}".encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def append_audit_log(
    db: Session,
    actor: str,
    event: str,
    payload: Dict[str, Any],
    owner_id: Optional[int] = None
) -> AuditLog:
    """Appends an immutable, hash-chained record to the audit log."""
    last_entry = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = last_entry.hash if last_entry else GENESIS_HASH

    now = datetime.now(timezone.utc)
    new_hash = compute_hash(prev_hash, now, actor, event, payload)

    entry = AuditLog(
        owner_id=owner_id,
        ts=now,
        actor=actor,
        event=event,
        payload=payload,
        prev_hash=prev_hash,
        hash=new_hash
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def verify_audit_chain(db: Session) -> Tuple[bool, int, str, Any]:
    """
    Verifies the integrity of the entire audit hash chain from genesis to tip.
    Returns (is_valid, total_blocks, message, corrupted_block_id).
    """
    entries = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    if not entries:
        return True, 0, "Audit log is empty.", None

    expected_prev = GENESIS_HASH
    for i, entry in enumerate(entries):
        # 1. Check prev_hash linkage
        if entry.prev_hash != expected_prev:
            return (
                False,
                len(entries),
                f"Hash chain broken at block ID {entry.id}. Prev hash mismatch. "
                f"Expected: {expected_prev[:12]}..., Found: {entry.prev_hash[:12]}...",
                entry.id
            )

        # 2. Recompute block hash
        expected_hash = compute_hash(
            entry.prev_hash,
            entry.ts,
            entry.actor,
            entry.event,
            entry.payload
        )
        if entry.hash != expected_hash:
            return (
                False,
                len(entries),
                f"Hash mismatch at block ID {entry.id}. Data has been tampered with. "
                f"Recorded: {entry.hash[:12]}..., Computed: {expected_hash[:12]}...",
                entry.id
            )

        expected_prev = entry.hash

    return True, len(entries), f"Audit chain verified successfully ({len(entries)} blocks). 100% intact.", None
