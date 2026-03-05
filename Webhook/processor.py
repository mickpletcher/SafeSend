"""
SafeSend Event Processor

Routes normalized WebhookEvents to the correct handler function based on
event_type. Each handler is responsible for:
  - Extracting relevant fields from event.raw_payload / event.event_data
  - Downloading documents from SAS URLs (if applicable)
  - Triggering downstream actions (archive, notify, update records, etc.)

IMPORTANT: SAS URLs are time-limited. Download documents immediately inside
the handler - do not store the URL for later retrieval.
"""

import logging
from .models import WebhookEvent, EventType, DocumentFile
from .downloader import download_document
from .config import settings

logger = logging.getLogger("safesend.processor")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
async def process_event(event: WebhookEvent) -> None:
    """Route a WebhookEvent to the correct handler."""

    handlers = {
        # SafeSend Returns
        EventType.RETURNS_ESIGN:           handle_returns_esign,
        EventType.RETURNS_STATUS_CHANGED:  handle_returns_status_changed,

        # SafeSend Signatures
        EventType.SIG_DOCUMENT_SIGNED:     handle_sig_document_signed,
        EventType.SIG_STATUS_CHANGED:      handle_sig_status_changed,

        # SafeSend Organizers
        EventType.ORG_ENGAGEMENT_LETTER_SIGNED:   handle_org_engagement_letter,
        EventType.ORG_ORGANIZER_COMPLETED:         handle_org_organizer_completed,
        EventType.ORG_SOURCE_DOC_UPLOADED:         handle_org_source_doc_uploaded,
        EventType.ORG_ACCESSED:                    handle_org_accessed,
        EventType.ORG_QUESTIONNAIRE_COMPLETED:     handle_org_questionnaire_completed,

        # SafeSend Exchange
        EventType.EXC_DRL_DOCUMENT:        handle_exc_drl_document,
        EventType.EXC_DROPOFF_LINK:        handle_exc_dropoff_link,

        # Client Management
        EventType.CM_CLIENT_CHANGED:       handle_cm_client_changed,

        # SafeSend Gather
        EventType.GTR_ESIGN_DOCUMENTS:     handle_gtr_esign_documents,
        EventType.GTR_FILLABLE_ORGANIZER:  handle_gtr_fillable_organizer,
        EventType.GTR_SOURCE_DOCUMENTS:    handle_gtr_source_documents,
        EventType.GTR_CUSTOM_QUESTIONNAIRE: handle_gtr_custom_questionnaire,
    }

    handler = handlers.get(event.event_type)
    if handler:
        await handler(event)
    else:
        logger.warning(
            f"No handler registered for event_type={event.event_type} | "
            f"event_id={event.event_id}"
        )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
async def maybe_download(event: WebhookEvent, label: str) -> str | None:
    """
    Download the document from the event's SAS URL if one is present.
    Returns the local file path, or None if no document was in the payload.
    """
    if not event.has_document or not event.document_file:
        return None

    doc: DocumentFile = event.document_file
    file_name = doc.file_name or f"{event.event_id}.bin"

    logger.info(f"Downloading {label} document: {file_name}")
    local_path = await download_document(
        sas_url=doc.sas_url,
        file_name=file_name,
        sub_dir=label,
    )
    logger.info(f"Saved {label} document to: {local_path}")
    return local_path


def log_event(event: WebhookEvent, label: str) -> None:
    logger.info(f"[{label}] {event.describe()}")


# ---------------------------------------------------------------------------
# SafeSend Returns Handlers
# ---------------------------------------------------------------------------
async def handle_returns_esign(event: WebhookEvent) -> None:
    """
    Fires when a tax return is e-signed or manually signed.
    Payload contains SAS links inside documentClients array.
    """
    log_event(event, "RETURNS_ESIGN")
    p = event.raw_payload

    signature_status = p.get("signatureStatus", "")
    tax_year = p.get("taxYear")
    engagement_type = p.get("engagementType", "")
    signed_on = p.get("signedOn", "")

    logger.info(
        f"Return signed | status={signature_status} | "
        f"type={engagement_type} | year={tax_year} | signed={signed_on}"
    )

    # documentClients is an array - each client may have their own documents
    clients = p.get("documentClients", [])
    for client in clients:
        client_name = client.get("name", "unknown")
        client_email = client.get("email", "")

        # Each client can have multiple document SAS links
        for doc in client.get("signerDocuments", []):
            file_name = doc.get("fileName", f"return_{tax_year}.pdf")
            sas_url = doc.get("sasUrl", "")
            if sas_url:
                logger.info(f"Downloading signed return for {client_name}: {file_name}")
                await download_document(
                    sas_url=sas_url,
                    file_name=file_name,
                    sub_dir=f"returns/{event.client_id or 'unknown'}",
                )

    # TODO: Trigger downstream workflow
    # Examples:
    #   - Move return to DMS / SharePoint
    #   - Update practice management system status
    #   - Send Teams notification to ERO
    #   - Trigger PowerShell automation via queue


async def handle_returns_status_changed(event: WebhookEvent) -> None:
    """
    Fires whenever a return status changes (any stage in the lifecycle).
    Use this to drive workflow state tracking.
    """
    log_event(event, "RETURNS_STATUS_CHANGED")
    p = event.raw_payload

    status = p.get("status", "")
    status_date = p.get("statusDate", "")
    ero_email = p.get("eroEmail", "")
    assigned_email = p.get("assignedEmail", "")
    form_type = p.get("formType", "")
    document_id = p.get("documentId")
    tax_return_id = p.get("taxReturnId", "")

    logger.info(
        f"Return status changed | status={status} | "
        f"form={form_type} | client={event.client_id} | "
        f"year={event.tax_year} | returnId={tax_return_id}"
    )

    # TODO: Update your internal status tracking table/system
    # Possible statuses: PROCESSING, DELIVERED, ESIGNED, MANUALSIGN,
    #                    RECALLED, UPLOADFORMS


# ---------------------------------------------------------------------------
# SafeSend Signatures Handlers
# ---------------------------------------------------------------------------
async def handle_sig_document_signed(event: WebhookEvent) -> None:
    """
    eventType 3000 - Fires when any recipient signs a signature request.
    For multi-signer requests, status will be 'partially signed' until all sign.
    """
    log_event(event, "SIG_DOCUMENT_SIGNED")
    data = event.event_data

    total = data.get("totalRecipients", 0)
    recipients = data.get("recipientList", [])
    sent_by = data.get("sentBy", "")

    logger.info(
        f"Signature received | client={event.client_id} | "
        f"signers={len(recipients)}/{total} | sentBy={sent_by}"
    )

    local_path = await maybe_download(event, "signatures")

    # TODO: Check if all signers complete, then route document


async def handle_sig_status_changed(event: WebhookEvent) -> None:
    """
    eventType 3001 - Fires on any signature status change.
    Statuses: Processing, Out for Signature, Delivery Failed, E-Signed,
              Partially Signed, Signature Stamping Failed, Declined, Canceled
    """
    log_event(event, "SIG_STATUS_CHANGED")
    data = event.event_data

    status = data.get("status", "")
    doc_info = data.get("documentInfo", [])

    logger.info(
        f"Signature status changed | client={event.client_id} | "
        f"status={status} | documents={len(doc_info)}"
    )

    # TODO: Handle terminal states (Declined, Canceled) with appropriate alerts


# ---------------------------------------------------------------------------
# SafeSend Organizers Handlers
# ---------------------------------------------------------------------------
async def handle_org_engagement_letter(event: WebhookEvent) -> None:
    """
    eventType 2000 - All e-sign documents in the organizer have been signed.
    Document may be a ZIP file if multiple signatures.
    """
    log_event(event, "ORG_ENGAGEMENT_LETTER")
    data = event.event_data

    ero_signer = data.get("eroSigner", "")
    assigned_to = data.get("assignedTo", "")
    document_guid = data.get("documentGuid", "")

    logger.info(
        f"Engagement letter signed | client={event.client_id} | "
        f"taxpayer={event.client_name} | year={event.tax_year} | "
        f"ero={ero_signer} | guid={document_guid}"
    )

    local_path = await maybe_download(event, "organizers/engagement_letters")

    # TODO: Archive engagement letter, update CRM/practice management


async def handle_org_organizer_completed(event: WebhookEvent) -> None:
    """
    eventType 2001 - Taxpayer has marked their organizer complete.
    Custom question responses are included in the payload when present.
    """
    log_event(event, "ORG_ORGANIZER_COMPLETED")
    data = event.event_data

    logger.info(
        f"Organizer completed | client={event.client_id} | "
        f"taxpayer={event.client_name} | year={event.tax_year}"
    )

    local_path = await maybe_download(event, "organizers/completed")

    # TODO: Notify preparer that organizer is ready for review
    # TODO: Trigger intake workflow in practice management system


async def handle_org_source_doc_uploaded(event: WebhookEvent) -> None:
    """
    eventType 2002 - A source document was uploaded to the organizer.
    Fires once per document - expect multiple events per client.
    """
    log_event(event, "ORG_SOURCE_DOC_UPLOADED")
    data = event.event_data

    file_name = event.document_file.file_name if event.document_file else "unknown"
    logger.info(
        f"Source document uploaded | client={event.client_id} | "
        f"taxpayer={event.client_name} | year={event.tax_year} | file={file_name}"
    )

    local_path = await maybe_download(event, f"organizers/source_docs/{event.client_id}")

    # TODO: Index document in DMS, update document checklist


async def handle_org_accessed(event: WebhookEvent) -> None:
    """
    eventType 2003 - Organizer recipient accessed the taxpayer experience.
    No document in this payload - purely a tracking/notification event.
    """
    log_event(event, "ORG_ACCESSED")
    data = event.event_data

    accessed_on = data.get("accessedOn", "")
    batch_name = data.get("batchName", "")
    organizer_id = data.get("organizerId", "")

    logger.info(
        f"Organizer accessed | client={event.client_id} | "
        f"taxpayer={event.client_name} | batch={batch_name} | "
        f"accessed={accessed_on}"
    )

    # TODO: Update engagement tracking, remove from "not yet opened" follow-up list


async def handle_org_questionnaire_completed(event: WebhookEvent) -> None:
    """
    eventType 2004 - Questionnaire completed within an organizer workflow.
    Document may be a ZIP if multiple signature files.
    """
    log_event(event, "ORG_QUESTIONNAIRE_COMPLETED")
    data = event.event_data

    logger.info(
        f"Questionnaire completed | client={event.client_id} | "
        f"taxpayer={event.client_name} | year={event.tax_year}"
    )

    local_path = await maybe_download(event, "organizers/questionnaires")


# ---------------------------------------------------------------------------
# SafeSend Exchange Handlers
# ---------------------------------------------------------------------------
async def handle_exc_drl_document(event: WebhookEvent) -> None:
    """
    eventType 4000 - Client uploaded a document to a Document Request List.
    Each document upload is its own event. Webhooks are the ONLY way to
    retrieve DRL documents via API.
    """
    log_event(event, "EXC_DRL_DOCUMENT")
    data = event.event_data

    drl_id = data.get("documentRequestListId", "")
    client_email = data.get("clientEmailId", "")
    field_name = data.get("documentFieldName", "")
    uploaded_date = data.get("uploadedDate", "")

    logger.info(
        f"DRL document uploaded | drlId={drl_id} | "
        f"client={client_email} | field={field_name} | date={uploaded_date}"
    )

    local_path = await maybe_download(event, f"exchange/drl/{event.client_id or drl_id}")

    # TODO: Route to correct folder/DMS location based on documentFieldName
    # TODO: Update document checklist completion tracking


async def handle_exc_dropoff_link(event: WebhookEvent) -> None:
    """
    eventType 4001 - File submitted via a drop-off link.
    Fires for all link types (company, personal, folder) including blacklisted senders.
    """
    log_event(event, "EXC_DROPOFF_LINK")
    data = event.event_data

    sender_email = data.get("senderEmail", "")
    sender_name = f"{data.get('senderFirstName', '')} {data.get('senderLastName', '')}".strip()
    dropoff_type = data.get("dropoffType", "")
    is_blacklisted = data.get("isBlacklisted", False)
    subject = data.get("dropoffSubject", "")
    recipients = data.get("dropoffRecipient", [])

    logger.info(
        f"Drop-off received | sender={sender_email} | "
        f"type={dropoff_type} | blacklisted={is_blacklisted} | "
        f"subject={subject} | recipients={recipients}"
    )

    if is_blacklisted:
        logger.warning(f"Drop-off from blacklisted sender: {sender_email}")
        # TODO: Alert security / do not process document
        return

    local_path = await maybe_download(event, f"exchange/dropoffs/{sender_email}")

    # TODO: Route to recipient's inbox or designated folder


# ---------------------------------------------------------------------------
# Client Management Handler
# ---------------------------------------------------------------------------
async def handle_cm_client_changed(event: WebhookEvent) -> None:
    """
    eventType 5001 - Client added, updated, or deleted in Client Management.
    Use uid as the permanent cross-reference key (clientId may change).
    """
    log_event(event, "CM_CLIENT_CHANGED")
    data = event.event_data

    uid = data.get("uId", "")
    action_type = data.get("actionType", "")  # ADD, UPDATE, DELETE
    ero = data.get("ero", "")
    location = data.get("location", "")
    client_type = data.get("type", "")
    mfj = data.get("mfj", False)

    logger.info(
        f"Client changed | action={action_type} | uid={uid} | "
        f"clientId={event.client_id} | ero={ero} | location={location}"
    )

    # TODO: Sync to external CRM or practice management system
    # TODO: Use uid as stable foreign key - clientId can be reassigned
    # Possible actions: ADD, UPDATE, DELETE


# ---------------------------------------------------------------------------
# SafeSend Gather Handlers
# ---------------------------------------------------------------------------
async def handle_gtr_esign_documents(event: WebhookEvent) -> None:
    """
    eventType 6000 - All e-sign documents signed OR declined by Gather recipient.
    """
    log_event(event, "GTR_ESIGN_DOCUMENTS")
    data = event.event_data

    gather_id = data.get("gatherId")
    spouse_name = data.get("spouseName", "")
    ero_signer = data.get("eroSigner", "")

    logger.info(
        f"Gather esign complete | gatherId={gather_id} | "
        f"client={event.client_id} | taxpayer={event.client_name} | "
        f"spouse={spouse_name} | ero={ero_signer}"
    )

    local_path = await maybe_download(event, f"gather/{event.client_id}/esign")

    # TODO: Archive engagement letter to DMS
    # TODO: Update Gather status in tracking system


async def handle_gtr_fillable_organizer(event: WebhookEvent) -> None:
    """
    eventType 6001 - Fillable organizer within Gather request marked complete.
    Only fires if an organizer was included in the Gather request.
    """
    log_event(event, "GTR_FILLABLE_ORGANIZER")
    data = event.event_data

    gather_id = data.get("gatherId")

    logger.info(
        f"Gather organizer complete | gatherId={gather_id} | "
        f"client={event.client_id} | year={event.tax_year}"
    )

    local_path = await maybe_download(event, f"gather/{event.client_id}/organizer")

    # TODO: Notify preparer organizer portion is ready


async def handle_gtr_source_documents(event: WebhookEvent) -> None:
    """
    eventType 6002 - Source document uploaded to Gather request.
    Fires once per document - expect many events per client during tax season.
    """
    log_event(event, "GTR_SOURCE_DOCUMENTS")
    data = event.event_data

    gather_id = data.get("gatherId")
    engagement_type = data.get("engagementType", "")
    batch_name = data.get("batchName", "")
    file_name = event.document_file.file_name if event.document_file else "unknown"

    logger.info(
        f"Gather source doc uploaded | gatherId={gather_id} | "
        f"client={event.client_id} | file={file_name} | "
        f"engagement={engagement_type} | batch={batch_name}"
    )

    local_path = await maybe_download(event, f"gather/{event.client_id}/source_docs")

    # TODO: Index document, update completeness tracking


async def handle_gtr_custom_questionnaire(event: WebhookEvent) -> None:
    """
    eventType 6003 - Custom questionnaire within Gather request completed.
    Only fires if a questionnaire was included in the Gather request.
    """
    log_event(event, "GTR_CUSTOM_QUESTIONNAIRE")
    data = event.event_data

    gather_id = data.get("gatherId")

    logger.info(
        f"Gather questionnaire complete | gatherId={gather_id} | "
        f"client={event.client_id} | year={event.tax_year}"
    )

    local_path = await maybe_download(event, f"gather/{event.client_id}/questionnaire")
