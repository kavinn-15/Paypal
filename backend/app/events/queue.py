import asyncio
import logging
from typing import Dict, Any, Optional
from backend.app.db import SessionLocal
from backend.app.models import WebhookEvent
from backend.app.events.processor import process_webhook_event

logger = logging.getLogger("event_queue")


import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from backend.app.db import SessionLocal
from backend.app.models import WebhookEvent
from backend.app.events.processor import process_webhook_event

logger = logging.getLogger("event_queue")

MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0


class EventQueue:
    """
    In-process asynchronous event queue backed by persisted webhook_events table.
    Guarantees durable, idempotent webhook processing with bounded retries,
    exponential backoff, dead-letter queue (DLQ) isolation, and startup crash recovery.
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    async def enqueue(self, event_id: int, payload: Dict[str, Any], is_simulated: bool = False):
        await self._queue.put((event_id, payload, is_simulated, 0))
        logger.info(f"Enqueued webhook event ID: {event_id} (simulated={is_simulated})")

    async def start(self):
        if self._running:
            return
        self._running = True

        # Recovery on startup: pull uncompleted verified events that have not exceeded MAX_RETRIES
        db = SessionLocal()
        try:
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
        logger.info("EventQueue durable worker loop started.")
        while self._running:
            try:
                event_id, payload, is_simulated, attempt = await self._queue.get()
                db = SessionLocal()
                try:
                    record = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
                    if record and record.processed:
                        # Event already processed by another worker / replay
                        self._queue.task_done()
                        continue

                    if record:
                        record.processing_state = "processing"
                        db.commit()

                    # Process the event logic
                    result = process_webhook_event(db, payload, is_simulated=is_simulated, webhook_event_id=event_id)

                    # Update record on verified success
                    if record:
                        record.processed = True
                        record.processing_state = "processed"
                        record.reconciliation_status = "reconciled"
                        record.processed_at = datetime.now(timezone.utc)
                        record.error_details = None
                        db.commit()
                    logger.info(f"Successfully processed webhook event {event_id}: {result.get('status')}")

                except Exception as e:
                    logger.error(f"Error processing queued event {event_id} (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                    if record:
                        record.retry_count = attempt + 1
                        record.error_details = str(e)

                        if record.retry_count >= MAX_RETRIES:
                            # Route permanently to Dead-Letter Queue (DLQ)
                            record.processing_state = "dead_letter"
                            record.reconciliation_status = "manual_review_required"
                            logger.error(f"Webhook event {event_id} exceeded max retries ({MAX_RETRIES}). Moved to dead-letter queue.")
                        else:
                            record.processing_state = "received"
                            # Re-enqueue with exponential backoff delay
                            backoff = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                            asyncio.create_task(self._delayed_requeue(event_id, payload, is_simulated, attempt + 1, backoff))

                        db.commit()
                finally:
                    db.close()
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

