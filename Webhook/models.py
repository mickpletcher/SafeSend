"""
SafeSend Webhook Event Models

Normalized representations of every SafeSend webhook payload.
All event types are mapped to a common WebhookEvent wrapper so the
processor can route them with a simple match/switch pattern.

Event Type Reference:
    Returns (no eventType field):
        - Download Esign Document  -> detected by 'documentStatus' key
        - Return Status Changed    -> detected by 'status' key at root

    SafeSend Signatures:
        3000 - Document Signed
        3001 - Signature Status Changed

    SafeSend Organizers:
        2000 - Engagement Letter Signed
        2001 - Organizer Completed
        2002 - Source Document Uploaded
        2003 - Accessed Organizer Notification
        2004 - Questionnaire Completed

    SafeSend Exchange:
        4000 - Download DRL Document
        4001 - Download Drop-Off Link

    Client Management:
        5001 - Client Information Change

    SafeSend Gather:
        6000 - Download Esign Documents
        6001 - Download Fillable Organizer
        6002 - Download Source Documents
        6003 - Download Custom Questionnaire
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------
class EventType:
    # SafeSend Returns (no eventType in payload - detected by key presence)
    RETURNS_ESIGN = "RETURNS_ESIGN"
    RETURNS_STATUS_CHANGED = "RETURNS_STATUS_CHANGED"

    # SafeSend Signatures
    SIG_DOCUMENT_SIGNED = 3000
    SIG_STATUS_CHANGED = 3001

    # SafeSend Organizers
    ORG_ENGAGEMENT_LETTER_SIGNED = 2000
    ORG_ORGANIZER_COMPLETED = 2001
    ORG_SOURCE_DOC_UPLOADED = 2002
    ORG_ACCESSED = 2003
    ORG_QUESTIONNAIRE_COMPLETED = 2004

    # SafeSend Exchange
    EXC_DRL_DOCUMENT = 4000
    EXC_DROPOFF_LINK = 4001

    # Client Management
    CM_CLIENT_CHANGED = 5001

    # SafeSend Gather
    GTR_ESIGN_DOCUMENTS = 6000
    GTR_FILLABLE_ORGANIZER = 6001
    GTR_SOURCE_DOCUMENTS = 6002
    GTR_CUSTOM_QUESTIONNAIRE = 6003


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------
class DocumentFile(BaseModel):
    file_name: str = Field(default="")
    sas_url: str = Field(default="")

    @classmethod
    def from_raw(cls, raw: dict) -> "DocumentFile":
        return cls(
            file_name=raw.get("fileName", raw.get("name", "")),
            sas_url=raw.get("sasUrl", ""),
        )


class DocumentClient(BaseModel):
    client_type: str = ""
    name: str = ""
    email: str = ""
    document_files: list[DocumentFile] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Main normalized event wrapper
# ---------------------------------------------------------------------------
class WebhookEvent(BaseModel):
    """
    Normalized wrapper around any SafeSend webhook payload.
    The raw payload is always preserved in `raw_payload` for full fidelity.
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    received_at: datetime = Field(default_factory=datetime.utcnow)

    # Normalized event type (int for typed events, str for Returns events)
    event_type: Any = None

    # Common fields (present in most event types)
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    tax_year: Optional[int] = None

    # Document download info (when payload contains a document)
    document_file: Optional[DocumentFile] = None
    has_document: bool = False

    # Raw payload preserved for full access in handlers
    raw_payload: dict = Field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict) -> "WebhookEvent":
        """
        Parse a raw SafeSend JSON payload into a normalized WebhookEvent.
        Handles the special case where Returns webhooks have no eventType field.
        """
        raw_event_type = payload.get("eventType")
        event_data = payload.get("eventData", payload)  # some Returns events have no wrapper

        # Determine event type
        if raw_event_type is not None:
            try:
                event_type = int(raw_event_type)
            except (TypeError, ValueError):
                event_type = None
        elif "documentStatus" in payload:
            event_type = EventType.RETURNS_ESIGN
        elif "status" in payload and "taxReturnId" in payload:
            event_type = EventType.RETURNS_STATUS_CHANGED
        else:
            event_type = None

        # Extract common fields
        client_id = (
            event_data.get("clientId")
            or payload.get("clientId")
        )
        client_name = (
            event_data.get("clientName")
            or event_data.get("taxPayerName")
            or event_data.get("taxpayerName")
            or payload.get("clientId")
        )
        tax_year = event_data.get("taxYear") or payload.get("taxYear")

        # Extract document file if present
        doc_file = None
        has_document = False
        raw_doc = event_data.get("documentFile") or event_data.get("document")
        if raw_doc:
            doc_file = DocumentFile.from_raw(raw_doc)
            has_document = bool(doc_file.sas_url)

        return cls(
            event_type=event_type,
            client_id=client_id,
            client_name=client_name,
            tax_year=tax_year,
            document_file=doc_file,
            has_document=has_document,
            raw_payload=payload,
        )

    @property
    def event_data(self) -> dict:
        """Convenience accessor for the eventData block."""
        return self.raw_payload.get("eventData", self.raw_payload)

    def describe(self) -> str:
        return (
            f"EventType={self.event_type} | "
            f"ClientId={self.client_id} | "
            f"TaxYear={self.tax_year} | "
            f"HasDocument={self.has_document}"
        )
