"""
In memory async event queue.

Decouples the webhook endpoint from background event processing.
"""

import asyncio
from .models import WebhookEvent

event_queue: asyncio.Queue[WebhookEvent] = asyncio.Queue()
