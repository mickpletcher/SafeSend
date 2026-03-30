"""
SafeSend Webhook Receiver
FastAPI application that accepts push events from SafeSend and routes them
to the appropriate handler based on eventType.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse

from config import settings
from event_queue import event_queue
from processor import process_event
from models import WebhookEvent
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


# ---------------------------------------------------------------------------
# Lifespan: start background processor on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SafeSend Webhook Receiver starting up")
    task = asyncio.create_task(background_processor())
    yield
    task.cancel()
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
    return {"status": "ok", "queue_depth": event_queue.qsize()}


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

    # Optional API key validation (configure in .env)
    if settings.WEBHOOK_SECRET and x_api_key != settings.WEBHOOK_SECRET:
        logger.warning("Rejected webhook - invalid API key")
        raise HTTPException(status_code=401, detail="Invalid API key")

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

    # Push onto the async queue - do NOT process inline
    await event_queue.put(event)

    # Always return 200 to SafeSend
    return JSONResponse(status_code=200, content={"received": True, "event_id": event.event_id})
