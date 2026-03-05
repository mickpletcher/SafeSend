"""
In-memory async event queue.

Decouples the webhook endpoint (must return 200 immediately) from the
event processor (may take time to download documents and run logic).

For production at scale, replace this with Azure Service Bus, Redis Streams,
or another durable queue so events survive process restarts.
"""

import asyncio
from .models import WebhookEvent

# Simple in-memory async queue
# Replace with a durable queue adapter for production
event_queue: asyncio.Queue[WebhookEvent] = asyncio.Queue()
