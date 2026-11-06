import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.db import Base
from backend.app.models import AuditLog
from backend.app.guardrail.audit import append_audit_log, verify_audit_chain, compute_hash, GENESIS_HASH


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()
    yield db
    db.close()


def test_audit_log_append_and_verify(test_db):
    # Verify empty chain
    is_valid, count, msg, corrupted_id = verify_audit_chain(test_db)
    assert is_valid is True
    assert count == 0

    # Append 3 events
    e1 = append_audit_log(test_db, "owner", "ACTION_PROPOSED", {"action_id": 1, "amount": 100.0})
    assert e1.prev_hash == GENESIS_HASH
    assert len(e1.hash) == 64

    e2 = append_audit_log(test_db, "owner", "ACTION_APPROVED", {"action_id": 1, "hash": "abc"})
    assert e2.prev_hash == e1.hash

    e3 = append_audit_log(test_db, "system", "ACTION_EXECUTED", {"action_id": 1, "ref": "PAY-123"})
    assert e3.prev_hash == e2.hash

    # Verify chain intact
    is_valid, count, msg, corrupted_id = verify_audit_chain(test_db)
    assert is_valid is True
    assert count == 3
    assert corrupted_id is None


def test_audit_log_detects_payload_tampering(test_db):
    e1 = append_audit_log(test_db, "owner", "ACTION_PROPOSED", {"action_id": 1, "amount": 100.0})
    e2 = append_audit_log(test_db, "owner", "ACTION_APPROVED", {"action_id": 1, "hash": "abc"})

    # Tamper with e1 payload directly in database
    e1.payload = {"action_id": 1, "amount": 99999.0}  # Alter amount
    test_db.commit()

    is_valid, count, msg, corrupted_id = verify_audit_chain(test_db)
    assert is_valid is False
    assert corrupted_id == e1.id
    assert "tampered" in msg.lower()


def test_audit_log_detects_hash_tampering(test_db):
    e1 = append_audit_log(test_db, "owner", "ACTION_PROPOSED", {"action_id": 1, "amount": 100.0})
    e2 = append_audit_log(test_db, "owner", "ACTION_APPROVED", {"action_id": 1, "hash": "abc"})

    # Tamper with e2 prev_hash
    e2.prev_hash = "deadbeef" * 8
    test_db.commit()

    is_valid, count, msg, corrupted_id = verify_audit_chain(test_db)
    assert is_valid is False
    assert corrupted_id == e2.id
    assert "broken" in msg.lower() or "mismatch" in msg.lower()

