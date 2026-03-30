"""
SafeSend Webhook Receiver
FastAPI application that accepts push events from SafeSend and routes them
to the appropriate handler based on eventType.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
import hashlib
import json
from fastapi import FastAPI, Request, Header
from fastapi.responses import JSONResponse

from .config import settings
from .event_queue import event_queue
from .processor import process_event
from .models import WebhookEvent
from .dedupe_store import SQLiteDedupeStore
import asyncio

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
Path("logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/receiver.log"),
    ],
)
logger = logging.getLogger("safesend.receiver")
dedupe_store = SQLiteDedupeStore(
    db_path=settings.DEDUPE_DB_PATH,
    ttl_seconds=settings.DEDUPE_TTL_SECONDS,
)
webhook_metrics = {
    "received_total": 0,
    "enqueued_total": 0,
    "invalid_api_key_total": 0,
    "duplicate_total": 0,
}


# ---------------------------------------------------------------------------
# Lifespan: start background processor on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SafeSend Webhook Receiver starting up")
    await dedupe_store.start()
    await event_queue.start()
    task = asyncio.create_task(background_processor())
    yield
    task.cancel()
    await event_queue.close()
    await dedupe_store.close()
    logger.info("SafeSend Webhook Receiver shutting down")


app = FastAPI(
    title="SafeSend Webhook Receiver",
    description="Receives and processes SafeSend webhook events",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Background queue processor
# ---------------------------------------------------------------------------
async def background_processor():
    """Continuously drain the in-memory queue and process events."""
    logger.info("Background processor started")
    while True:
        event = None
        try:
            event = await event_queue.get()
            logger.info(
                f"Processing event | type={event.event_type} | id={event.event_id}"
            )
            await process_event(event)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception(f"Unhandled error in background processor: {exc}")
        finally:
            if event is not None:
                event_queue.task_done()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "queue_depth": event_queue.qsize(),
        "metrics": webhook_metrics,
    }


# ---------------------------------------------------------------------------
# Main webhook endpoint
# ---------------------------------------------------------------------------
@app.post("/webhook/safesend")
async def receive_webhook(
    request: Request,
    x_api_key: str = Header(default=None),
):
    """
    Primary inbound endpoint for all SafeSend webhook events.

    SafeSend POSTs JSON payloads here when events occur. This endpoint:
    1. Optionally validates a shared API key header
    2. Parses the payload
    3. Enqueues it for async processing
    4. Returns HTTP 200 immediately

    CRITICAL: Always return 200. If SafeSend does not receive a 2xx response
    it will disable the webhook subscription and queue all future events.
    """
    webhook_metrics["received_total"] += 1

    # Optional API key validation (configure in .env)
    if settings.WEBHOOK_SECRET and x_api_key != settings.WEBHOOK_SECRET:
        logger.warning("Rejected webhook - invalid API key")
        webhook_metrics["invalid_api_key_total"] += 1
        return JSONResponse(status_code=200, content={"received": False, "reason": "invalid api key"})

    try:
        payload = await request.json()
    except Exception:
        logger.error("Failed to parse webhook payload as JSON")
        # Still return 200 to prevent SafeSend from disabling the subscription.
        # Log the raw body for debugging.
        raw = await request.body()
        logger.error(f"Raw body: {raw[:500]}")
        return JSONResponse(status_code=200, content={"received": False, "reason": "invalid json"})

    # Build a normalized event object
    try:
        event = WebhookEvent.from_payload(payload)
    except Exception as exc:
        logger.error(f"Failed to normalize webhook payload: {exc}")
        return JSONResponse(status_code=200, content={"received": False, "reason": "invalid payload"})

    if event.event_type is None:
        logger.warning("Unable to determine event type from payload")
        return JSONResponse(status_code=200, content={"received": False, "reason": "unknown event type"})

    logger.info(
        f"Received event | type={event.event_type} | id={event.event_id}"
    )

    payload_key = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    try:
        duplicate = await dedupe_store.was_seen(payload_key)
    except Exception as exc:
        logger.exception(f"Failed dedupe check, continuing without dedupe: {exc}")
        duplicate = False

    if duplicate:
        logger.info("Duplicate webhook payload detected, skipping enqueue")
        webhook_metrics["duplicate_total"] += 1
        return JSONResponse(status_code=200, content={"received": True, "duplicate": True})

    # Push onto the async queue - do NOT process inline
    await event_queue.put(event)
    webhook_metrics["enqueued_total"] += 1

    # Always return 200 to SafeSend
    return JSONResponse(status_code=200, content={"received": True, "event_id": event.event_id})
