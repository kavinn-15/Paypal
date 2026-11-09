import pytest
from backend.app.db import SessionLocal
from backend.app.models import Action
from backend.app.guardrail.state_machine import GuardrailStateMachine, InvalidStateTransitionError, ActionState
from backend.app.guardrail.approval import (
    generate_approval_hash, compute_action_payload, generate_payload_hash, generate_canonical_approval_signature
)
from backend.scripts.seed import seed_database


@pytest.fixture(scope="module")
def setup_db():
    seed_database(clean=True, demo_mode=True)


def test_guardrail_state_machine_happy_path(setup_db):
    db = SessionLocal()
    try:
        # Create a proposed simulated action for demo contractor Marcus Sterling
        idemp = "act_test_state_123"

        action = Action(
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="Marcus Sterling",
            amount=1600.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp,
            is_simulated=True,
            approval_version=2,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        valid_hash = generate_canonical_approval_signature(generate_payload_hash(cp))
        action.approval_hash = valid_hash
        db.commit()

        # 1. Transition proposed -> approved
        action = GuardrailStateMachine.transition(
            db=db,
            action=action,
            target_state=ActionState.APPROVED,
            actor="owner",
            approval_hash=valid_hash
        )
        assert action.state == ActionState.APPROVED
        assert action.approved_at is not None

        # 2. Transition approved -> executed
        action = GuardrailStateMachine.transition(
            db=db,
            action=action,
            target_state=ActionState.EXECUTED,
            actor="system",
            paypal_ref="PAYPAL-BATCH-999"
        )
        assert action.state == ActionState.EXECUTED
        assert action.executed_at is not None
        assert action.paypal_ref == "PAYPAL-BATCH-999"

        # 3. Transition executed -> confirmed
        action = GuardrailStateMachine.transition(
            db=db,
            action=action,
            target_state=ActionState.CONFIRMED,
            actor="webhook"
        )
        assert action.state == ActionState.CONFIRMED
        assert action.confirmed_at is not None

    finally:
        db.close()


def test_guardrail_rejects_illegal_transition(setup_db):
    db = SessionLocal()
    try:
        idemp = "act_test_illegal_456"
        valid_hash = generate_approval_hash(
            recipient="Marcus Sterling",
            amount=1600.0,
            currency="USD",
            action_type="SCHEDULE_PAYOUT_SPLIT",
            idempotency_key=idemp
        )
        action = Action(
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="Marcus Sterling",
            amount=1600.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp,
            approval_hash=valid_hash
        )
        db.add(action)
        db.commit()
        db.refresh(action)

        # Attempt illegal jump: proposed -> executed (skipping approval!)
        with pytest.raises(InvalidStateTransitionError) as exc:
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.EXECUTED,
                actor="malicious_agent"
            )
        assert "Illegal state transition attempted" in str(exc.value)

        # Attempt illegal jump: proposed -> confirmed
        with pytest.raises(InvalidStateTransitionError):
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.CONFIRMED,
                actor="malicious_agent"
            )

    finally:
        db.close()


def test_guardrail_rejects_tampered_approval_hash(setup_db):
    db = SessionLocal()
    try:
        idemp = "act_test_tamper_789"
        action = Action(
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="Marcus Sterling",
            amount=1600.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp,
            is_simulated=True,
            approval_version=2,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        valid_hash = generate_canonical_approval_signature(generate_payload_hash(cp))
        action.approval_hash = valid_hash
        db.commit()

        # Tampered hash (someone changed amount or random signature)
        tampered_hash = "deadbeef" * 8
        with pytest.raises(InvalidStateTransitionError) as exc:
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.APPROVED,
                actor="owner",
                approval_hash=tampered_hash
            )
        assert "TAMPERING DETECTED" in str(exc.value)

        # Altering amount after hash was generated
        action.amount = 9999.0  # Attempt to steal 9999
        with pytest.raises(InvalidStateTransitionError) as exc:
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.APPROVED,
                actor="owner",
                approval_hash=valid_hash
            )
        assert "TAMPERING DETECTED" in str(exc.value)

    finally:
        db.close()

