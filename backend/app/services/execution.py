import logging
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.models import Action, Invoice, Obligation
from backend.app.paypal.client import paypal_client, PayPalError
from backend.app.guardrail.state_machine import GuardrailStateMachine, ActionState, InvalidStateTransitionError
from backend.app.guardrail.policy import validate_action_against_policy, PolicyViolationError
from backend.app.guardrail.audit import append_audit_log

logger = logging.getLogger("action_executor")


class ActionExecutionService:
    """
    Executes approved actions through the PayPal Sandbox:
    - Invoicing v2: Reminders, Discount updates
    - Payouts: Batch payouts with idempotency key
    Zero fake batch IDs, zero swallowed errors, atomic concurrency locking,
    and strict recipient & policy validation.
    """

    @staticmethod
    async def execute_action(db: Session, action: Action, actor: str = "owner") -> Action:
        # 1. State check: must be in APPROVED state
        if action.state != ActionState.APPROVED:
            raise InvalidStateTransitionError(
                f"Action {action.id} cannot be executed. Current state is '{action.state}'. Must be '{ActionState.APPROVED}'."
            )

        # 2. Concurrency lock: atomically transition from approved -> executing
        affected = db.query(Action).filter(
            Action.id == action.id,
            Action.state == ActionState.APPROVED
        ).update({"state": ActionState.EXECUTING})
        db.commit()

        if affected == 0:
            raise InvalidStateTransitionError(
                f"Concurrent execution blocked: Action {action.id} is already executing or state has changed."
            )
        db.refresh(action)

        # 3. Safety Policy & Exact Canonical Payload Integrity Verification
        try:
            from backend.app.guardrail.approval import compute_action_payload, generate_payload_hash
            approval_ver = getattr(action, "approval_version", 2)
            if approval_ver is None:
                raise PolicyViolationError("Action missing explicit approval_version. Execution blocked.")
            if not action.approved_payload_hash:
                raise PolicyViolationError("Missing approved payload hash. Action must be re-approved by owner.")

            current_payload = compute_action_payload(action)
            current_hash = generate_payload_hash(current_payload)
            if current_hash != action.approved_payload_hash:
                action.state = ActionState.PROPOSED  # Require fresh owner approval
                action.approved_payload_hash = None
                db.commit()
                append_audit_log(
                    db=db,
                    actor="guardrail",
                    event="EXECUTION_REJECTED_PAYLOAD_TAMPERED",
                    payload={"action_id": action.id, "expected_hash": action.approved_payload_hash, "current_hash": current_hash},
                    owner_id=action.owner_id
                )
                raise PolicyViolationError(
                    "TAMPERING DETECTED: Action execution parameters were modified after approval! Fresh owner approval is required."
                )
            validate_action_against_policy(action, db)
        except Exception:
            # Revert back to APPROVED on pre-execution policy failure (if not already reverted to proposed)
            if action.state == ActionState.EXECUTING:
                action.state = ActionState.APPROVED
                db.commit()
            raise

        # 4. Execution routing
        try:
            if action.action_type == "SEND_REMINDER":
                inv_id = action.paypal_ref
                if not inv_id:
                    raise ValueError(f"Action {action.id} has no associated invoice reference.")

                # Verify invoice exists and belongs to this owner
                inv_query = db.query(Invoice).filter(Invoice.paypal_invoice_id == inv_id)
                if action.owner_id:
                    inv_query = inv_query.join(Invoice.client).filter(Invoice.client.has(owner_id=action.owner_id))
                invoice = inv_query.first()
                if not invoice:
                    raise ValueError(f"Associated invoice {inv_id} not found or does not belong to owner.")

                msg = action.messages[0].body if action.messages else "Please find payment link attached."

                if action.is_simulated:
                    logger.info(f"[LOCAL DEMO SIMULATION] Simulated invoice reminder for action {action.id} ({inv_id}). External PayPal API not called.")
                    append_audit_log(
                        db=db,
                        actor=actor,
                        event="ACTION_SIMULATED_REMINDER_EXECUTED_LOCALLY",
                        payload={"action_id": action.id, "invoice_id": inv_id, "note": "Local demo simulation only. PayPal API not called."},
                        owner_id=action.owner_id
                    )
                    GuardrailStateMachine.transition(
                        db=db,
                        action=action,
                        target_state=ActionState.EXECUTED,
                        actor=actor,
                        paypal_ref=inv_id
                    )
                    action.is_simulated = True
                    db.commit()
                else:
                    # Dispatches real request to PayPal Sandbox API; raises PayPalError on failure
                    await paypal_client.send_invoice_reminder(
                        invoice_id=inv_id,
                        subject="Payment Reminder: Upcoming Invoice Settlement",
                        note=msg
                    )

                    GuardrailStateMachine.transition(
                        db=db,
                        action=action,
                        target_state=ActionState.EXECUTED,
                        actor=actor,
                        paypal_ref=inv_id
                    )

            elif action.action_type == "APPLY_DISCOUNT":
                inv_id = action.paypal_ref
                if not inv_id:
                    raise ValueError(f"Action {action.id} has no associated invoice reference.")

                inv_query = db.query(Invoice).filter(Invoice.paypal_invoice_id == inv_id)
                if action.owner_id:
                    inv_query = inv_query.join(Invoice.client).filter(Invoice.client.has(owner_id=action.owner_id))
                invoice = inv_query.first()
                if not invoice:
                    raise ValueError(f"Associated invoice {inv_id} not found or does not belong to owner.")

                disc_pct = float(action.plan.details.get("discount_pct", 3.0)) if action.plan and action.plan.details else 3.0

                if action.is_simulated:
                    logger.info(f"[LOCAL DEMO SIMULATION] Simulated discount for action {action.id} ({inv_id}). External PayPal API not called.")
                    invoice.discount_applied = disc_pct
                    db.commit()
                    append_audit_log(
                        db=db,
                        actor=actor,
                        event="ACTION_SIMULATED_DISCOUNT_EXECUTED_LOCALLY",
                        payload={"action_id": action.id, "invoice_id": inv_id, "discount_pct": disc_pct, "note": "Local demo simulation only. PayPal API not called."},
                        owner_id=action.owner_id
                    )
                    GuardrailStateMachine.transition(
                        db=db,
                        action=action,
                        target_state=ActionState.EXECUTED,
                        actor=actor,
                        paypal_ref=inv_id
                    )
                    action.is_simulated = True
                    db.commit()
                else:
                    # Dispatches real request to PayPal Sandbox API; raises PayPalError on failure
                    await paypal_client.apply_invoice_discount(
                        invoice_id=inv_id,
                        discount_percent=disc_pct,
                        note="Early payment discount applied."
                    )

                    # Only update local database upon verified PayPal API success
                    invoice.discount_applied = disc_pct
                    db.commit()

                    GuardrailStateMachine.transition(
                        db=db,
                        action=action,
                        target_state=ActionState.EXECUTED,
                        actor=actor,
                        paypal_ref=inv_id
                    )

            elif action.action_type in ("SCHEDULE_PAYOUT_SPLIT", "PAYOUT"):
                # Determine and validate recipient contractor email
                recipient_email = None
                recip_clean = action.recipient.strip()

                # Enforce contractor split permission and consent check immediately before execution (FAIL CLOSED)
                if action.action_type in ("SCHEDULE_PAYOUT_SPLIT", "PAYOUT"):
                    obl = None
                    if getattr(action, "obligation_id", None):
                        obl = db.query(Obligation).filter(Obligation.id == action.obligation_id).first()
                        if not obl:
                            raise PolicyViolationError(
                                f"FAIL-CLOSED: Obligation ID {action.obligation_id} not found. Execution blocked."
                            )
                        if not action.owner_id or obl.owner_id != action.owner_id:
                            append_audit_log(
                                db=db,
                                actor=actor,
                                event="EXECUTION_OWNERSHIP_MISMATCH_BLOCKED",
                                payload={
                                    "action_id": action.id,
                                    "action_owner_id": action.owner_id,
                                    "obligation_id": obl.id,
                                    "obligation_owner_id": obl.owner_id
                                },
                                owner_id=action.owner_id
                            )
                            raise PolicyViolationError(
                                f"OWNERSHIP MISMATCH: Obligation {obl.id} belongs to owner {obl.owner_id}, not action owner {action.owner_id}. Execution blocked."
                            )

                    if not obl:
                        if not action.owner_id:
                            raise PolicyViolationError("OWNERSHIP MISMATCH: Action has no owner_id. Execution blocked.")
                        obl_query = db.query(Obligation).filter(
                            (Obligation.payee_name.ilike(recip_clean)) | (Obligation.payee_email.ilike(recip_clean)),
                            Obligation.owner_id == action.owner_id
                        )
                        matching_obls = obl_query.all()

                        if len(matching_obls) == 0:
                            raise PolicyViolationError(
                                f"FAIL-CLOSED: No matching obligation found for contractor '{action.recipient}'. Execution blocked."
                            )
                        if len(matching_obls) > 1:
                            raise PolicyViolationError(
                                f"FAIL-CLOSED: Ambiguous contractor obligation: multiple matching obligations found for '{action.recipient}'. Execution blocked."
                            )
                        obl = matching_obls[0]

                    # Recheck contractor identity
                    if (obl.payee_name.strip().lower() != action.recipient.strip().lower() and
                        obl.payee_email.strip().lower() != action.recipient.strip().lower()):
                        raise PolicyViolationError(
                            f"FAIL-CLOSED: Consent contractor '{obl.payee_name}' does not match action recipient '{action.recipient}'. Execution blocked."
                        )

                    # Recheck split permission
                    if obl.split_allowed is not True:
                        raise PolicyViolationError(
                            f"FAIL-CLOSED: Split permission is not granted for contractor '{obl.payee_name}'. Execution blocked."
                        )

                    # Recheck consent status
                    if getattr(obl, "split_consent_recorded", False) is not True:
                        raise PolicyViolationError(
                            f"FAIL-CLOSED: Verified contractor split consent is not recorded for '{obl.payee_name}'. Execution blocked."
                        )

                    # FIX 1: Reject simulated consent for real payout execution
                    if not action.is_simulated and getattr(obl, "split_consent_is_simulated", False) is True:
                        append_audit_log(
                            db=db,
                            actor="guardrail",
                            event="EXECUTION_REJECTED_SIMULATED_CONSENT",
                            payload={"action_id": action.id, "contractor": obl.payee_name, "reason": "Simulated consent cannot be used for genuine payout execution."},
                            owner_id=action.owner_id
                        )
                        raise PolicyViolationError(
                            f"SIMULATED CONSENT REJECTED: Contractor consent for '{obl.payee_name}' is simulated. Genuine payout execution blocked."
                        )

                    # FIX 2: Recheck actual PayPal payout destination
                    current_email = obl.payee_email.strip().lower() if obl.payee_email else None
                    if action.payout_recipient_email and current_email != action.payout_recipient_email.strip().lower():
                        append_audit_log(
                            db=db,
                            actor="guardrail",
                            event="EXECUTION_REJECTED_DESTINATION_TAMPERED",
                            payload={"action_id": action.id, "approved_destination": action.payout_recipient_email, "current_destination": current_email},
                            owner_id=action.owner_id
                        )
                        raise PolicyViolationError(
                            f"DESTINATION TAMPERED: Approved destination '{action.payout_recipient_email}' does not match current obligation PayPal email '{current_email}'. Fresh owner approval required."
                        )

                    recipient_email = action.payout_recipient_email or current_email
                else:
                    if "@" in recip_clean:
                        recipient_email = recip_clean
                    else:
                        obl = db.query(Obligation).filter(
                            Obligation.owner_id == action.owner_id,
                            (Obligation.payee_name.ilike(recip_clean)) | (Obligation.payee_email.ilike(recip_clean))
                        ).first()
                        if obl and obl.payee_email:
                            recipient_email = obl.payee_email.strip()

                if not recipient_email or "@" not in recipient_email:
                    raise ValueError(
                        f"Cannot resolve verified recipient email for payout recipient '{action.recipient}'. Execution aborted."
                    )

                # STRICT CENTRAL CHECK: Treat every action marked is_simulated=True as strictly local/demo-only.
                # Under NO circumstances can a simulated action call paypal_client.create_payout()
                if action.is_simulated:
                    sim_batch_id = f"SIM-PAYOUT-{action.idempotency_key[:24]}"
                    logger.info(
                        f"[LOCAL DEMO SIMULATION] Executed simulated payout action {action.id} "
                        f"locally for {action.recipient} ({action.amount} {action.currency}). "
                        f"External PayPal payout API was NOT contacted."
                    )
                    append_audit_log(
                        db=db,
                        actor=actor,
                        event="ACTION_SIMULATED_PAYOUT_EXECUTED_LOCALLY",
                        payload={
                            "action_id": action.id,
                            "recipient": action.recipient,
                            "recipient_email": recipient_email,
                            "amount": float(action.amount),
                            "currency": action.currency,
                            "simulated_batch_id": sim_batch_id,
                            "note": "Local demo simulation only. PayPal API not called."
                        },
                        owner_id=action.owner_id
                    )
                    GuardrailStateMachine.transition(
                        db=db,
                        action=action,
                        target_state=ActionState.EXECUTED,
                        actor=actor,
                        paypal_ref=sim_batch_id
                    )
                    action.is_simulated = True
                    db.commit()
                else:
                    # Dispatches real request to PayPal Sandbox API; raises PayPalError on failure
                    res = await paypal_client.create_payout(
                        recipient_email=recipient_email,
                        amount=float(action.amount),
                        currency=action.currency,
                        sender_batch_id=action.idempotency_key,
                        note=f"Contractor Payout - Ref {action.idempotency_key[:8]}"
                    )

                    # Extract and validate real PayPal payout batch ID
                    batch_id = res.get("batch_header", {}).get("payout_batch_id")
                    if not batch_id:
                        raise PayPalError(f"PayPal create_payout response missing valid payout_batch_id: {res}")

                    batch_status = res.get("batch_header", {}).get("batch_status", "PENDING")
                    logger.info(f"PayPal Payout batch created: {batch_id} with status {batch_status}")

                    GuardrailStateMachine.transition(
                        db=db,
                        action=action,
                        target_state=ActionState.EXECUTED,
                        actor=actor,
                        paypal_ref=batch_id
                    )
                    action.is_simulated = False
                    db.commit()
            else:
                raise ValueError(f"Unknown action type: {action.action_type}")

        except Exception as e:
            logger.error(f"Execution failed for action {action.id}: {e}")
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.FAILED,
                actor=actor,
                error_message=str(e)
            )
            append_audit_log(
                db=db,
                actor="system",
                event="ACTION_EXECUTION_FAILED",
                payload={"action_id": action.id, "error": str(e)},
                owner_id=action.owner_id
            )
            raise e

        return action

