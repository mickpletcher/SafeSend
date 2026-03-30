"""
Queue adapter for webhook events.

Uses in-memory queue by default. If Azure Service Bus settings are provided,
the adapter will publish/consume from Service Bus for durability.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from .config import settings
from .models import WebhookEvent

logger = logging.getLogger("safesend.queue")


class InMemoryEventQueue:
	def __init__(self, max_size: int = 0):
		self._queue: asyncio.Queue[WebhookEvent] = asyncio.Queue(maxsize=max_size)

	async def start(self) -> None:
		return None

	async def close(self) -> None:
		return None

	async def put(self, event: WebhookEvent) -> None:
		await self._queue.put(event)

	async def get(self) -> WebhookEvent:
		return await self._queue.get()

	def task_done(self) -> None:
		self._queue.task_done()

	def qsize(self) -> int:
		return self._queue.qsize()


class ServiceBusEventQueue:
	def __init__(self, connection_string: str, queue_name: str):
		self._connection_string = connection_string
		self._queue_name = queue_name
		self._client: Any = None
		self._sender: Any = None
		self._receiver: Any = None
		self._current_message: Any = None
		self._started = False

	async def start(self) -> None:
		if self._started:
			return

		try:
			from azure.servicebus import ServiceBusMessage
			from azure.servicebus.aio import ServiceBusClient
		except ImportError as exc:
			raise RuntimeError(
				"Azure Service Bus backend requested but package is missing. "
				"Install azure-servicebus."
			) from exc

		self._servicebus_message_cls = ServiceBusMessage
		self._client = ServiceBusClient.from_connection_string(self._connection_string)
		self._sender = self._client.get_queue_sender(queue_name=self._queue_name)
		self._receiver = self._client.get_queue_receiver(queue_name=self._queue_name)
		await self._sender.__aenter__()
		await self._receiver.__aenter__()
		self._started = True
		logger.info(f"Using Azure Service Bus queue backend | queue={self._queue_name}")

	async def close(self) -> None:
		if not self._started:
			return

		await self._receiver.__aexit__(None, None, None)
		await self._sender.__aexit__(None, None, None)
		await self._client.close()
		self._started = False

	async def put(self, event: WebhookEvent) -> None:
		if not self._started:
			await self.start()

		payload = event.model_dump_json()
		msg = self._servicebus_message_cls(payload)
		await self._sender.send_messages(msg)

	async def get(self) -> WebhookEvent:
		if not self._started:
			await self.start()

		while True:
			messages = await self._receiver.receive_messages(max_message_count=1, max_wait_time=5)
			if not messages:
				await asyncio.sleep(0.1)
				continue

			msg = messages[0]
			self._current_message = msg
			raw = b"".join(bytes(part) for part in msg.body).decode("utf-8", errors="replace")
			data = json.loads(raw)
			return WebhookEvent.model_validate(data)

	def task_done(self) -> None:
		# Service Bus settlement confirms successful processing.
		if self._current_message is None:
			return

		msg = self._current_message
		self._current_message = None
		asyncio.create_task(self._receiver.complete_message(msg))

	def qsize(self) -> int:
		# Service Bus does not expose queue depth through the receiver.
		return 0


def _build_queue_backend() -> InMemoryEventQueue | ServiceBusEventQueue:
	if settings.AZURE_SERVICE_BUS_CONNECTION_STRING and settings.AZURE_SERVICE_BUS_QUEUE_NAME:
		return ServiceBusEventQueue(
			connection_string=settings.AZURE_SERVICE_BUS_CONNECTION_STRING,
			queue_name=settings.AZURE_SERVICE_BUS_QUEUE_NAME,
		)

	return InMemoryEventQueue(max_size=settings.EVENT_QUEUE_MAX_SIZE)


event_queue = _build_queue_backend()
