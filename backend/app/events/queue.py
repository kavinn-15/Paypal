import asyncio
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from backend.app.db import SessionLocal
from backend.app.models import WebhookEvent
from backend.app.events.processor import process_webhook_event

logger = logging.getLogger("event_queue")

MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
LEASE_TIMEOUT_SECONDS = 120


class EventQueue:
    """
    In-process asynchronous event queue backed by persisted webhook_events table.
    Guarantees durable, idempotent webhook processing with:
    - Bounded retries and exponential backoff
    - Dead-letter queue (DLQ) isolation
    - Atomic database lease locking across workers
    - Correct outcome preservation (quarantined vs processed)
    - Crash recovery on startup (resetting stale locks and re-queuing pending events)
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._worker_id = f"worker_{uuid.uuid4().hex[:8]}"

    async def enqueue(self, event_id: int, payload: Dict[str, Any], is_simulated: bool = False):
        await self._queue.put((event_id, payload, is_simulated, 0))
        logger.info(f"Enqueued webhook event ID: {event_id} (simulated={is_simulated})")

    async def start(self):
        if self._running:
            return
        self._running = True

        # Recovery on startup: reset stale locks and pull uncompleted verified events
        db = SessionLocal()
        try:
            stale_cutoff = datetime.now(timezone.utc) - timedelta(seconds=LEASE_TIMEOUT_SECONDS)
            # 1. Release any stale locks left by previous crashes
            db.query(WebhookEvent).filter(
                WebhookEvent.processed == False,
                WebhookEvent.locked_at != None,
                WebhookEvent.locked_at < stale_cutoff
            ).update({
                WebhookEvent.locked_at: None,
                WebhookEvent.locked_by: None,
                WebhookEvent.processing_state: "received"
            }, synchronize_session=False)
            db.commit()

            # 2. Recover pending verified events that have not exceeded retries
            pending_events = db.query(WebhookEvent).filter(
                WebhookEvent.processed == False,
                WebhookEvent.verified == True,
                WebhookEvent.processing_state.notin_(["quarantined", "dead_letter"])
            ).order_by(WebhookEvent.id.asc()).all()

            for evt in pending_events:
                await self._queue.put((evt.id, evt.payload, evt.is_simulated, evt.retry_count))
            logger.info(f"EventQueue initialized: recovered {len(pending_events)} pending event(s) from database.")
        except Exception as e:
            logger.error(f"Error recovering pending events on startup: {e}")
        finally:
            db.close()

        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _worker_loop(self):
        logger.info(f"EventQueue worker loop started (worker_id={self._worker_id}).")
        while self._running:
            try:
                event_id, payload, is_simulated, attempt = await self._queue.get()
                db = SessionLocal()
                try:
                    now = datetime.now(timezone.utc)
                    stale_cutoff = now - timedelta(seconds=LEASE_TIMEOUT_SECONDS)

                    # 1. Atomic lease lock claim in database
                    claimed = db.query(WebhookEvent).filter(
                        WebhookEvent.id == event_id,
                        WebhookEvent.processed == False,
                        (WebhookEvent.locked_at == None) | (WebhookEvent.locked_at < stale_cutoff)
                    ).update({
                        WebhookEvent.processing_state: "processing",
                        WebhookEvent.locked_at: now,
                        WebhookEvent.locked_by: self._worker_id
                    }, synchronize_session=False)
                    db.commit()

                    if claimed == 0:
                        # Event already claimed by another active worker or already processed
                        logger.info(f"Skipping event {event_id}: already processed or locked by another worker.")
                        continue

                    # 2. Process the event logic
                    result = process_webhook_event(db, payload, is_simulated=is_simulated, webhook_event_id=event_id)
                    status = result.get("status")

                    # 3. Authoritatively record processing outcome
                    record = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
                    if record:
                        record.locked_at = None
                        record.locked_by = None

                        if status in ("success", "already_processed"):
                            record.processed = True
                            record.processing_state = "processed"
                            if record.reconciliation_status not in ("manual_review_required", "payout_failed"):
                                record.reconciliation_status = "reconciled"
                            record.processed_at = datetime.now(timezone.utc)
                            record.error_details = None
                        elif status in ("quarantined", "flagged_manual_review"):
                            # CRITICAL: Quarantined events MUST NOT be marked processed!
                            record.processed = False
                            record.processing_state = "quarantined"
                            record.reconciliation_status = "manual_review_required"
                            record.error_details = result.get("reason") or "Manual review required"
                        elif status == "unhandled_event_type":
                            record.processed = True
                            record.processing_state = "quarantined"
                            record.reconciliation_status = "unhandled_type"
                            record.error_details = f"Unhandled event type: {result.get('event_type')}"

                        db.commit()
                    logger.info(f"EventQueue handled event {event_id}: outcome={status}")

                except Exception as e:
                    logger.error(f"Error processing queued event {event_id} (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                    try:
                        record = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
                        if record:
                            record.retry_count = attempt + 1
                            record.error_details = str(e)
                            record.locked_at = None
                            record.locked_by = None
                            max_r = record.max_retries or MAX_RETRIES

                            if record.retry_count >= max_r:
                                # Route permanently to Dead-Letter Queue (DLQ)
                                record.processing_state = "dead_letter"
                                record.reconciliation_status = "manual_review_required"
                                logger.error(f"Webhook event {event_id} exceeded max retries ({max_r}). Moved to dead-letter queue.")
                            else:
                                record.processing_state = "received"
                                backoff = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                                asyncio.create_task(self._delayed_requeue(event_id, payload, is_simulated, attempt + 1, backoff))

                            db.commit()
                    except Exception as db_err:
                        logger.error(f"Failed to record error state for event {event_id}: {db_err}")
                finally:
                    db.close()
                    # CRITICAL FIX: task_done() is invoked strictly ONCE per dequeued item
                    self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in event queue worker: {e}")
                await asyncio.sleep(1.0)

    async def _delayed_requeue(self, event_id: int, payload: Dict[str, Any], is_simulated: bool, next_attempt: int, delay: float):
        await asyncio.sleep(delay)
        await self._queue.put((event_id, payload, is_simulated, next_attempt))
        logger.info(f"Re-enqueued webhook event {event_id} after {delay:.1f}s backoff (attempt {next_attempt}).")


event_queue = EventQueue()
