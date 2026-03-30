# Operations Runbook

## 1. Daily health check

1. Call GET /health.
2. Confirm status is ok.
3. Review queue_depth.
4. Review metrics trend.

Expected metric behavior:

1. received_total increases as webhooks arrive.
2. enqueued_total increases for valid unique payloads.
3. invalid_api_key_total should remain low.
4. duplicate_total may increase during retries or replay events.

## 2. Startup procedure

1. Open PowerShell in repository root.
2. Activate virtual environment.
3. Start with python module command or launcher script.
4. Confirm service is listening.
5. Confirm health endpoint response.

## 3. SafeSend delivery issue triage

### Symptom: No payloads arriving

1. Confirm webhook subscription is active in SafeSend.
2. Confirm endpoint URL is correct and publicly reachable.
3. Confirm TLS certificate is valid.
4. Confirm firewall allows inbound traffic.
5. Confirm application process is running.

### Symptom: Payloads arrive but no files download

1. Check logs for download errors.
2. Confirm DOWNLOAD_BASE_PATH is writable.
3. Check SAS URL expiry timing.
4. Verify event includes document link fields.

### Symptom: Too many duplicate entries

1. Inspect duplicate_total metric trend.
2. Validate DEDUPE_DB_PATH is persistent and writable.
3. Confirm DEDUPE_TTL_SECONDS is not too short.

### Symptom: Invalid API key count rising

1. Confirm SafeSend API key setting matches WEBHOOK_SECRET.
2. Rotate secret if exposure is suspected.
3. Monitor source IP patterns at reverse proxy.

## 4. Queue mode operations

### In memory mode

1. Simple mode for local use.
2. Queue data is lost on restart.

### Service Bus mode

1. Set AZURE_SERVICE_BUS_CONNECTION_STRING.
2. Set AZURE_SERVICE_BUS_QUEUE_NAME.
3. Verify queue exists and identity has rights.

## 5. Backup and retention

1. Back up downloaded documents based on policy.
2. Back up dedupe database if continuity required.
3. Rotate logs and retain for audit windows.

## 6. Change management

Before making changes:

1. Run tests.
2. Record current .env values securely.
3. Plan rollback command and timing.

After changes:

1. Run tests again.
2. Restart service.
3. Validate health endpoint.
4. Send one controlled test webhook.

## 7. Disaster recovery basics

1. Rebuild environment from repository and requirements.
2. Restore .env from secure secret store.
3. Restore document storage access.
4. Restore dedupe database if needed.
5. Start service and verify health.

## 8. Support handoff checklist

1. Current endpoint URL
2. SafeSend subscription state
3. Last known health response
4. Recent error log sample
5. Queue mode in use
6. Storage path in use
7. Owner contact and escalation path
