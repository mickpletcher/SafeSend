"""
Tests for the SafeSend webhook receiver.

Run with:  pytest -v
"""

import pytest
import asyncio
from pathlib import Path
from models import WebhookEvent, EventType
from downloader import _safe_output_dir


# ---------------------------------------------------------------------------
# Test payload factories
# ---------------------------------------------------------------------------
def make_returns_esign_payload():
    return {
        "documentStatus": "USERSIGNED",
        "signatureStatus": "ESigned",
        "signedOn": "2024-04-15T14:32:00.000Z",
        "taxSoftware": "ProSystems",
        "deliveredOn": "2024-04-10T09:00:00.000Z",
        "taxYear": 2023,
        "engagementType": "E1040",
        "documentClients": [
            {
                "clientType": "Individual",
                "name": "John Smith",
                "email": "john@example.com",
                "signerDocuments": [
                    {"fileName": "1040_2023.pdf", "sasUrl": "https://example.com/doc1"}
                ]
            }
        ]
    }


def make_returns_status_payload():
    return {
        "status": "ESIGNED",
        "statusDate": "2024-04-15T14:32:00.000Z",
        "eroEmail": "preparer@cbiz.com",
        "assignedEmail": "reviewer@cbiz.com",
        "formType": "E1040",
        "taxYear": 2023,
        "documentGuid": "53e12ecb-f233-429e-882d-59018a7ee8b2",
        "documentId": 147857,
        "clientId": "CLIENT_001",
        "httpStatus": 0,
        "uniqueArgs": "",
        "taxReturnId": "LCRKJF8TVXG47AT5E0YU6RYKYW"
    }


def make_typed_payload(event_type: int, extra: dict = None):
    data = {
        "eventType": event_type,
        "eventData": {
            "clientId": "TEST_CLIENT",
            "clientName": "Test Client",
            "taxYear": 2023,
            "documentFile": {
                "fileName": "test.pdf",
                "sasUrl": "https://example.com/test.pdf"
            },
            **(extra or {})
        }
    }
    return data


# ---------------------------------------------------------------------------
# Model parsing tests
# ---------------------------------------------------------------------------
class TestWebhookEventParsing:

    def test_returns_esign_detection(self):
        payload = make_returns_esign_payload()
        event = WebhookEvent.from_payload(payload)
        assert event.event_type == EventType.RETURNS_ESIGN
        assert event.tax_year == 2023

    def test_returns_status_detection(self):
        payload = make_returns_status_payload()
        event = WebhookEvent.from_payload(payload)
        assert event.event_type == EventType.RETURNS_STATUS_CHANGED
        assert event.client_id == "CLIENT_001"

    def test_typed_event_parsing(self):
        for etype in [3000, 3001, 2000, 2001, 2002, 2003, 2004,
                      4000, 4001, 5001, 6000, 6001, 6002, 6003]:
            payload = make_typed_payload(etype)
            event = WebhookEvent.from_payload(payload)
            assert event.event_type == etype, f"Failed for eventType {etype}"

    def test_document_extraction(self):
        payload = make_typed_payload(4000, {"document": {"name": "w2.pdf", "sasUrl": "https://x.com/w2.pdf"}})
        # Exchange DRL uses 'document' not 'documentFile'
        payload["eventData"]["document"] = {"name": "w2.pdf", "sasUrl": "https://x.com/w2.pdf"}
        event = WebhookEvent.from_payload(payload)
        assert event.has_document
        assert event.document_file is not None

    def test_no_document_event(self):
        payload = make_returns_status_payload()
        event = WebhookEvent.from_payload(payload)
        assert not event.has_document
        assert event.document_file is None

    def test_raw_payload_preserved(self):
        payload = make_returns_esign_payload()
        event = WebhookEvent.from_payload(payload)
        assert event.raw_payload == payload

    def test_unknown_payload_does_not_crash(self):
        event = WebhookEvent.from_payload({"someUnknownField": "value"})
        assert event.event_type is None

    def test_malformed_event_type_does_not_crash(self):
        payload = {"eventType": "not-a-number", "eventData": {}}
        event = WebhookEvent.from_payload(payload)
        assert event.event_type is None


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------
class TestEventRouter:

    @pytest.mark.asyncio
    async def test_all_typed_events_route_without_error(self):
        """Ensure all known event types route to a handler without raising."""
        from processor import process_event

        event_types = [3000, 3001, 2000, 2001, 2002, 2003, 2004,
                       4000, 4001, 5001, 6000, 6001, 6002, 6003]

        for etype in event_types:
            payload = make_typed_payload(etype)
            event = WebhookEvent.from_payload(payload)
            # Handlers will try to download but sas_url is fake - that's fine
            # We just verify routing doesn't raise unhandled exceptions
            try:
                await process_event(event)
            except Exception as exc:
                # Download failures are expected with fake URLs - not a routing error
                if "download" in str(exc).lower() or "sas" in str(exc).lower():
                    pass
                elif "connect" in str(exc).lower() or "url" in str(exc).lower():
                    pass
                else:
                    raise

    @pytest.mark.asyncio
    async def test_returns_events_route_without_error(self):
        from processor import process_event

        for payload in [make_returns_esign_payload(), make_returns_status_payload()]:
            event = WebhookEvent.from_payload(payload)
            try:
                await process_event(event)
            except Exception as exc:
                if any(k in str(exc).lower() for k in ["download", "connect", "url", "sas"]):
                    pass
                else:
                    raise

    @pytest.mark.asyncio
    async def test_unknown_event_type_does_not_raise(self):
        from processor import process_event
        event = WebhookEvent.from_payload({"eventType": 9999, "eventData": {}})
        # Should log a warning but not raise
        await process_event(event)


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------
class TestWebhookEndpoint:

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_webhook_accepts_valid_payload(self, client):
        payload = make_returns_status_payload()
        response = client.post("/webhook/safesend", json=payload)
        assert response.status_code == 200
        assert response.json()["received"] is True

    def test_webhook_returns_200_for_invalid_json_structure(self, client):
        # Even garbage payloads should return 200 to prevent SafeSend disabling the subscription
        response = client.post(
            "/webhook/safesend",
            content=b"not json at all",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200

    def test_webhook_returns_200_for_malformed_event_type(self, client):
        response = client.post(
            "/webhook/safesend",
            json={"eventType": "not-a-number", "eventData": {}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["received"] is False
        assert data["reason"] == "unknown event type"

    def test_webhook_rejects_wrong_api_key(self, client, monkeypatch):
        import config
        monkeypatch.setattr(config.settings, "WEBHOOK_SECRET", "correct_secret")
        response = client.post(
            "/webhook/safesend",
            json=make_returns_status_payload(),
            headers={"x-api-key": "wrong_secret"}
        )
        assert response.status_code == 401

    def test_webhook_accepts_correct_api_key(self, client, monkeypatch):
        import config
        monkeypatch.setattr(config.settings, "WEBHOOK_SECRET", "correct_secret")
        response = client.post(
            "/webhook/safesend",
            json=make_returns_status_payload(),
            headers={"x-api-key": "correct_secret"}
        )
        assert response.status_code == 200


class TestPathSanitization:

    def test_safe_output_dir_keeps_paths_under_base(self):
        base_path = Path("downloads")
        resolved_base = base_path.resolve()

        output_dir = _safe_output_dir(base_path, "../../outside/../safe:folder")

        assert output_dir == resolved_base or resolved_base in output_dir.parents
