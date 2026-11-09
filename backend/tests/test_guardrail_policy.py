import pytest
from backend.app.db import SessionLocal
from backend.app.models import Action
from backend.app.guardrail.policy import validate_action_against_policy, PolicyViolationError
from backend.scripts.seed import seed_database


@pytest.fixture(scope="module")
def setup_db():
    seed_database(clean=True, demo_mode=True)


def test_policy_currency_validation(setup_db):
    db = SessionLocal()
    try:
        # Valid currency USD
        act_valid = Action(
            action_type="SEND_REMINDER",
            recipient="Apex Design Studio",
            amount=100.0,
            currency="USD",
            idempotency_key="k1",
            approval_hash="h1"
        )
        validate_action_against_policy(act_valid, db)

        # Invalid currency XYZ
        act_invalid = Action(
            action_type="SEND_REMINDER",
            recipient="Apex Design Studio",
            amount=100.0,
            currency="XYZ",
            idempotency_key="k2",
            approval_hash="h2"
        )
        with pytest.raises(PolicyViolationError) as exc:
            validate_action_against_policy(act_invalid, db)
        assert "Currency 'XYZ' is not in allowed" in str(exc.value)

    finally:
        db.close()


def test_policy_max_payout_limit(setup_db):
    db = SessionLocal()
    try:
        # Payout exceeds max payout limit of $10,000
        act_excessive = Action(
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="Marcus Sterling",
            amount=50000.0,
            currency="USD",
            idempotency_key="k3",
            approval_hash="h3"
        )
        with pytest.raises(PolicyViolationError) as exc:
            validate_action_against_policy(act_excessive, db)
        assert "exceeds configured maximum limit" in str(exc.value)

    finally:
        db.close()


def test_policy_unrecognized_recipient(setup_db):
    db = SessionLocal()
    try:
        # Hacker attempts to divert funds to unknown email
        act_rogue = Action(
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="attacker@evil-domain.example.com",
            amount=500.0,
            currency="USD",
            idempotency_key="k4",
            approval_hash="h4"
        )
        with pytest.raises(PolicyViolationError) as exc:
            validate_action_against_policy(act_rogue, db)
        assert "not a recognized contractor or client" in str(exc.value)

    finally:
        db.close()

