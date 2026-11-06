from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from backend.app.models import Action
from backend.app.guardrail.approval import verify_approval_hash
from backend.app.guardrail.audit import append_audit_log


class InvalidStateTransitionError(Exception):
    pass


class ActionState:
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTED = "executed"
    CONFIRMED = "confirmed"
    FAILED = "failed"


# Strict Directed State Machine Graph
ALLOWED_TRANSITIONS = {
    ActionState.PROPOSED: [ActionState.APPROVED],
    ActionState.APPROVED: [ActionState.EXECUTED],
    ActionState.EXECUTED: [ActionState.CONFIRMED, ActionState.FAILED],
    ActionState.FAILED: [ActionState.APPROVED, ActionState.PROPOSED],  # Permitted retry paths
    ActionState.CONFIRMED: []  # Immutable terminal state
}


class GuardrailStateMachine:
    """
    Deterministic Guardrail State Machine:
    Strictly enforces four-state sequence:
    proposed -> approved -> executed -> confirmed (plus failed with retry).
    """

    @staticmethod
    def transition(
        db: Session,
        action: Action,
        target_state: str,
        actor: str,
        approval_hash: Optional[str] = None,
        paypal_ref: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Action:
        current_state = action.state.lower()
        target_state = target_state.lower()

        # Check if transition is allowed
        allowed = ALLOWED_TRANSITIONS.get(current_state, [])
        if target_state not in allowed:
            raise InvalidStateTransitionError(
                f"SAFETY VIOLATION: Illegal state transition attempted: '{current_state}' -> '{target_state}'. "
                f"Allowed target states from '{current_state}': {allowed}"
            )

        now = datetime.now(timezone.utc)

        # Transition Rule: proposed -> approved requires verified HMAC approval signature
        if target_state == ActionState.APPROVED:
            if not approval_hash:
                raise InvalidStateTransitionError(
                    "Approval signature missing. Owner HMAC approval hash is required."
                )

            # Strict cryptographic verification
            is_valid = verify_approval_hash(
                provided_hash=approval_hash,
                recipient=action.recipient,
                amount=action.amount,
                currency=action.currency,
                action_type=action.action_type,
                idempotency_key=action.idempotency_key
            )
            if not is_valid:
                raise InvalidStateTransitionError(
                    "TAMPERING DETECTED: Invalid approval hash! Amount, recipient, currency, or action_type "
                    "does not match the cryptographically signed parameters."
                )

            action.approved_at = now
            action.approval_hash = approval_hash

        elif target_state == ActionState.EXECUTED:
            action.executed_at = now
            if paypal_ref:
                action.paypal_ref = paypal_ref

        elif target_state == ActionState.CONFIRMED:
            action.confirmed_at = now

        elif target_state == ActionState.FAILED:
            action.error_message = error_message or "Execution failed."

        action.state = target_state
        db.commit()
        db.refresh(action)

        # Record in Hash-Chained Audit Log
        append_audit_log(
            db=db,
            actor=actor,
            event=f"ACTION_STATE_CHANGED_{target_state.upper()}",
            payload={
                "action_id": action.id,
                "plan_id": action.plan_id,
                "action_type": action.action_type,
                "previous_state": current_state,
                "new_state": target_state,
                "recipient": action.recipient,
                "amount": action.amount,
                "currency": action.currency,
                "paypal_ref": action.paypal_ref,
                "idempotency_key": action.idempotency_key
            }
        )

        return action

