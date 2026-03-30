# Configuration Reference

All configuration is controlled by environment variables in Webhook .env.

## Core settings

1. WEBHOOK_SECRET
Purpose: Shared secret used to authenticate incoming webhook calls.
Required: Strongly recommended.
If blank: Request auth check is effectively bypassed.

2. DOWNLOAD_BASE_PATH
Purpose: Root folder for downloaded documents.
Examples:
1. C:\SafeSendDocuments
2. \\FileServer\SafeSend\Docs
3. /mnt/safesend/docs

3. HOST
Purpose: Bind address for the web server.
Default: 0.0.0.0

4. PORT
Purpose: Listening port for the web server.
Default: 8000

5. LOG_LEVEL
Purpose: Logging verbosity.
Common values: info, warning, error, debug.

## Optional integrations

1. TEAMS_WEBHOOK_URL
Purpose: Future notification integration.
Current status: Placeholder setting.

## Queue settings

1. AZURE_SERVICE_BUS_CONNECTION_STRING
Purpose: Enables durable queue backend when set.

2. AZURE_SERVICE_BUS_QUEUE_NAME
Purpose: Queue name used with Service Bus backend.
Default: safesend-events

3. EVENT_QUEUE_MAX_SIZE
Purpose: Max queue size for in memory mode.
Default: 0
Meaning of 0: Unbounded queue.

## Dedupe settings

1. DEDUPE_DB_PATH
Purpose: SQLite file path for payload dedupe fingerprints.
Default: Webhook/dedupe_store.db

2. DEDUPE_TTL_SECONDS
Purpose: How long payload fingerprints are retained.
Default: 604800
Meaning: 7 days.

## Recommended baseline by environment

### Development

1. WEBHOOK_SECRET set
2. In memory queue
3. EVENT_QUEUE_MAX_SIZE left at 0
4. Local DOWNLOAD_BASE_PATH

### Production

1. WEBHOOK_SECRET set
2. Service Bus values set
3. DOWNLOAD_BASE_PATH on resilient storage
4. DEDUPE_DB_PATH on persistent disk
5. LOG_LEVEL info or warning

## Validation checklist for configuration

1. .env file exists in Webhook folder.
2. Secret in SafeSend matches WEBHOOK_SECRET exactly.
3. DOWNLOAD_BASE_PATH exists and is writable.
4. If Service Bus is enabled, both Service Bus values are present.
5. Service starts without config exceptions.
