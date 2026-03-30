# Datasets and Data Flow

This project does not use machine learning datasets.

It uses operational data streams and generated records.

## 1. Data sources used by this system

1. SafeSend webhook payloads.
2. SafeSend document SAS URLs included in payloads.
3. Raw vendor documentation PDFs in Raw Data Handbooks.
4. Local configuration data from .env.

## 2. Data inputs by category

### A. Event payload data

Source: SafeSend webhook delivery.
Format: JSON.
Transport: HTTPS POST.

Common fields:

1. eventType
2. eventData
3. clientId
4. clientName
5. taxYear
5. documentFile or document

Notes:

1. Some Returns webhooks do not provide eventType.
2. Returns detection is inferred from payload keys such as documentStatus and status plus taxReturnId.

### B. Document binary data

Source: SafeSend SAS URLs from payload.
Format: Binary files, usually PDF or ZIP.
Storage: Under DOWNLOAD_BASE_PATH.

Important behavior:

1. SAS links are temporary.
2. Downloads should happen immediately.

### C. Dedupe fingerprint dataset

Source: SHA256 hash of normalized payload JSON.
Storage: SQLite at DEDUPE_DB_PATH.
Purpose: Prevent duplicate processing.

Schema:

1. key as unique payload fingerprint.
2. seen_at as Unix timestamp.

Retention:

1. Controlled by DEDUPE_TTL_SECONDS.
2. Older rows are purged during lookups.

### D. Runtime metrics dataset

Source: In process counters.
Exposed by: GET /health.
Fields:

1. received_total
2. enqueued_total
3. invalid_api_key_total
4. duplicate_total

### E. Test datasets

Source: Synthetic payload fixtures in test file.
Location: Webhook/tests/test_receiver.py.
Purpose: Validate parser, routing, auth behavior, duplicate handling, and health output.

## 3. Data sinks

1. Queue backend
Mode A: In memory queue.
Mode B: Azure Service Bus queue.

2. File storage
Downloaded documents saved to DOWNLOAD_BASE_PATH.

3. Logs
Runtime logs written to logs/receiver.log.

4. SQLite dedupe store
Fingerprint records stored at DEDUPE_DB_PATH.

## 4. Data flow from receipt to completion

1. Payload received at /webhook/safesend.
2. API key checked if WEBHOOK_SECRET configured.
3. Payload parsed into normalized event model.
4. Payload fingerprint checked against dedupe store.
5. Unique payload is sent to queue.
6. Worker consumes queue item.
7. Handler routes by event type.
8. If document link exists, file download executes.
9. File saved to DOWNLOAD_BASE_PATH subfolders.

## 5. Dataset quality checks you should run

1. Verify payload contains expected fields for each subscribed event.
2. Verify eventType mapping aligns with SafeSend docs.
3. Verify downloaded file names and client folders match expected routing.
4. Verify duplicate replay does not create duplicate files.
5. Verify invalid API key requests increment metric without enqueue.

## 6. Data governance recommendations

1. Store documents on controlled network storage.
2. Restrict access to webhook server logs.
3. Rotate and protect WEBHOOK_SECRET.
4. Define retention policy for downloaded documents.
5. Back up dedupe database if dedupe continuity matters.
6. If using Service Bus, apply least privilege identity and queue RBAC.

## 7. Vendor reference datasets used to design this implementation

1. Raw Data Handbooks/API_Portal_Integration_Guide_Rawdata.pdf
2. Raw Data Handbooks/Webhook_Integration_Guide_Rawdata.pdf

These sources define:

1. Event catalogs and behavior
2. Error handling expectations
3. 2xx success handling requirements
4. Product specific webhook payload semantics
