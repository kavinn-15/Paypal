import asyncio
import logging
from typing import Dict, Any, Optional
from backend.app.db import SessionLocal
from backend.app.models import WebhookEvent
from backend.app.events.processor import process_webhook_event

logger = logging.getLogger("event_queue")


class EventQueue:
    """
    In-process asynchronous event queue backed by persisted webhook_events table.
    Guarantees that events are processed in order and never lost across server restarts.
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    async def enqueue(self, event_id: int, payload: Dict[str, Any], is_simulated: bool = False):
        await self._queue.put((event_id, payload, is_simulated))
        logger.info(f"Enqueued webhook event ID: {event_id} (simulated={is_simulated})")

    async def start(self):
        if self._running:
            return
        self._running = True

        # Recovery on startup: pull any uncompleted verified events from database
        db = SessionLocal()
        try:
            pending_events = db.query(WebhookEvent).filter(
                WebhookEvent.processed == False,
                WebhookEvent.verified == True
            ).order_by(WebhookEvent.id.asc()).all()

            for evt in pending_events:
                await self._queue.put((evt.id, evt.payload, evt.is_simulated))
            logger.info(f"EventQueue initialized: recovered {len(pending_events)} pending event(s).")
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
        logger.info("EventQueue worker loop started.")
        while self._running:
            try:
                event_id, payload, is_simulated = await self._queue.get()
                db = SessionLocal()
                try:
                    process_webhook_event(db, payload, is_simulated=is_simulated)
                    # Mark processed in database
                    record = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
                    if record:
                        record.processed = True
                        db.commit()
                except Exception as e:
                    logger.error(f"Error processing queued event {event_id}: {e}")
                finally:
                    db.close()
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in event queue worker: {e}")
                await asyncio.sleep(1.0)


event_queue = EventQueue()

