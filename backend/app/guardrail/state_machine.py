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
    EXECUTING = "executing"
    EXECUTED = "executed"
    SIMULATED = "simulated"
    CONFIRMED = "confirmed"
    FAILED = "failed"


# Strict Directed State Machine Graph
ALLOWED_TRANSITIONS = {
    ActionState.PROPOSED: [ActionState.APPROVED],
    ActionState.APPROVED: [ActionState.EXECUTING, ActionState.EXECUTED],
    ActionState.EXECUTING: [ActionState.EXECUTED, ActionState.FAILED],
    ActionState.EXECUTED: [ActionState.CONFIRMED, ActionState.SIMULATED, ActionState.FAILED],
    ActionState.SIMULATED: [ActionState.CONFIRMED, ActionState.FAILED],
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

        # Idempotent state transition (already in target state)
        if current_state == target_state:
            return action

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

            # Enforce contractor split consent check prior to approval (FAIL CLOSED)
            if action.action_type == "SCHEDULE_PAYOUT_SPLIT":
                from backend.app.models import Obligation
                recip_clean = action.recipient.strip()
                obl_query = db.query(Obligation).filter(
                    (Obligation.payee_name.ilike(recip_clean)) | (Obligation.payee_email.ilike(recip_clean))
                )
                if action.owner_id is not None:
                    obl_query = obl_query.filter(Obligation.owner_id == action.owner_id)
                matching_obls = obl_query.all()

                if len(matching_obls) == 0:
                    raise InvalidStateTransitionError(
                        f"FAIL-CLOSED: No matching obligation found for contractor '{action.recipient}'. Approval rejected."
                    )
                if len(matching_obls) > 1:
                    raise InvalidStateTransitionError(
                        f"FAIL-CLOSED: Ambiguous contractor obligation: multiple matching obligations found for '{action.recipient}'. Approval rejected."
                    )

                obl = matching_obls[0]

                if obl.split_allowed is not True:
                    raise InvalidStateTransitionError(
                        f"FAIL-CLOSED: Split permission is not granted (split_allowed={obl.split_allowed}) for contractor '{obl.payee_name}'."
                    )

                if getattr(obl, "split_consent_recorded", False) is not True:
                    raise InvalidStateTransitionError(
                        f"FAIL-CLOSED: Verified contractor split consent is not recorded for '{obl.payee_name}'."
                    )

                if (obl.payee_name.strip().lower() != action.recipient.strip().lower() and
                    obl.payee_email.strip().lower() != action.recipient.strip().lower()):
                    raise InvalidStateTransitionError(
                        f"FAIL-CLOSED: Consent contractor '{obl.payee_name}' does not match action recipient '{action.recipient}'."
                    )

            # Strict cryptographic verification with complete canonical payload binding
            from backend.app.guardrail.approval import (
                compute_action_payload, generate_payload_hash,
                generate_canonical_approval_signature, verify_approval_hash
            )
            import hmac

            canonical_payload = compute_action_payload(action)
            payload_hash = generate_payload_hash(canonical_payload)
            expected_canonical_sig = generate_canonical_approval_signature(payload_hash)

            if hmac.compare_digest(approval_hash, expected_canonical_sig):
                action.approved_payload_hash = payload_hash
                action.approved_at = now
                action.approval_hash = expected_canonical_sig
            else:
                # Check legacy compact signature ONLY for isolated old records without plans/messages
                is_compact_valid = verify_approval_hash(
                    provided_hash=approval_hash,
                    recipient=action.recipient,
                    amount=action.amount,
                    currency=action.currency,
                    action_type=action.action_type,
                    idempotency_key=action.idempotency_key
                )
                is_new_action = bool(action.plan_id or (hasattr(action, "messages") and action.messages))
                if is_compact_valid and not is_new_action:
                    action.approved_payload_hash = payload_hash
                    action.approved_at = now
                    action.approval_hash = approval_hash
                else:
                    raise InvalidStateTransitionError(
                        "TAMPERING DETECTED: Invalid approval signature! Parameters do not match cryptographically signed canonical payload."
                    )

        elif target_state == ActionState.EXECUTED:
            action.executed_at = now
            if paypal_ref:
                action.paypal_ref = paypal_ref

        elif target_state == ActionState.CONFIRMED:
            # Genuine verified PayPal confirmation only
            action.confirmed_at = now
            action.is_simulated = False

        elif target_state == ActionState.SIMULATED:
            # Development simulation state: never represented as genuine confirmed PayPal webhook
            action.is_simulated = True

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
                "amount": float(action.amount),
                "currency": action.currency,
                "paypal_ref": action.paypal_ref,
                "idempotency_key": action.idempotency_key
            }
        )

        return action

