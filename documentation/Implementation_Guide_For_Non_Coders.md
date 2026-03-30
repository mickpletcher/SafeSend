# Implementation Guide For Non Coders

## 1. What this system does

This system receives webhook notifications from SafeSend.

When SafeSend sends a notification, this system can:

1. Validate the request
2. Identify what event happened
3. Download document files from temporary SafeSend SAS links
4. Save files to your storage path
5. Queue events for safe processing
6. Prevent duplicate processing of the same payload

## 2. Plain language architecture

1. SafeSend sends an HTTPS POST request to your webhook endpoint.
2. Your server responds quickly with HTTP 200.
3. The payload is checked for duplicates.
4. If unique, it is pushed to a queue.
5. A background worker processes the event.
6. For document events, it downloads files to your configured folder.

## 3. What you need before setup

1. A Windows machine or server that can run Python.
2. Python 3.9 or later.
3. Access to SafeSend Developer configuration.
4. A storage location for downloaded documents.
5. Public HTTPS endpoint if SafeSend needs to call your server from outside your network.

## 4. Folder structure you should know

1. Webhook runtime code is in the Webhook folder.
2. Main entrypoint module is Webhook.run.
3. Main API endpoint logic is in Webhook.main.
4. Event handlers are in Webhook.processor.
5. Download logic is in Webhook.downloader.
6. Queue backend selection is in Webhook.event_queue.

## 5. Quick setup on Windows

### Step 1. Open PowerShell in the repository root

Expected path should end in SafeSend.

### Step 2. Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3. Install dependencies

```powershell
pip install -r .\Webhook\requirements.txt
```

### Step 4. Create your environment file

```powershell
Copy-Item .\Webhook\.env.example .\Webhook\.env
```

### Step 5. Edit the environment file

Set at least these values:

1. WEBHOOK_SECRET
2. DOWNLOAD_BASE_PATH
3. HOST
4. PORT

### Step 6. Start the service

Option A script launcher:

```powershell
.\Webhook\Start-Webhook.ps1
```

Option B Python module:

```powershell
python -m Webhook.run
```

## 6. SafeSend portal configuration

Use your SafeSend Developer settings page.

1. Set webhook URL to your public endpoint plus /webhook/safesend
2. Set API key value to match WEBHOOK_SECRET
3. Subscribe to desired event categories
4. Save changes

Example endpoint format:

```text
https://yourdomain.example.com/webhook/safesend
```

## 7. How to verify it is running

Use this health endpoint:

```text
GET /health
```

Expected response includes:

1. status
2. queue_depth
3. metrics

Metrics include:

1. received_total
2. enqueued_total
3. invalid_api_key_total
4. duplicate_total

## 8. Security behavior in plain terms

1. The endpoint always returns HTTP 200 so SafeSend does not disable delivery.
2. Bad API keys are not processed.
3. Duplicate payloads are detected and ignored.
4. File path handling is sanitized to reduce path traversal risk.

## 9. Durability behavior in plain terms

1. If Azure Service Bus values are empty, queue is in memory.
2. If Azure Service Bus values are set, queue uses Service Bus.
3. Dedupe fingerprints are persisted in a local SQLite database.

## 10. Common deployment choices

### Choice A. Local or small office deployment

1. In memory queue
2. Local storage path
3. Good for testing and pilot use

### Choice B. Production deployment

1. Azure Service Bus enabled
2. Durable network storage path
3. HTTPS endpoint behind reverse proxy
4. Backup and monitoring enabled

## 11. Event categories supported

1. SafeSend Returns
2. SafeSend Signatures
3. SafeSend Organizers
4. SafeSend Exchange
5. SafeSend Gather
6. Client Management

Returns events are special because some do not include eventType and are inferred from payload fields.

## 12. Testing for non coders

Run all tests:

```powershell
python -m pytest -q Webhook/tests
```

If tests pass, you should see a pass count and no failures.

## 13. First day go live checklist

1. Webhook URL responds over HTTPS.
2. Secret value matches in both places.
3. Health endpoint returns status ok.
4. Test payload reaches endpoint.
5. Document download path is writable.
6. Metrics increment as expected.
7. Duplicate replay does not create duplicate work.

## 14. If something fails

1. Check the health endpoint first.
2. Check logs folder.
3. Validate .env values.
4. Verify SafeSend webhook subscription is still active.
5. Confirm your server can be reached from SafeSend.

See Operations Runbook for detailed troubleshooting steps.
