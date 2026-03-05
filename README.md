# SafeSend Webhook Integration

A Python FastAPI application that receives and processes webhook events from SafeSend. Automatically downloads documents from time-limited SAS URLs and routes events to appropriate handlers based on event type.

## Repository Contents

### Documentation
- [API_Portal_Integration_Guide.pdf](API_Portal_Integration_Guide.pdf) - SafeSend API Portal integration reference
- [Webhook_Integration_Guide.pdf](Webhook_Integration_Guide.pdf) - SafeSend webhook implementation guide
- [SafeSend_Developer_Handbook.docx](SafeSend_Developer_Handbook.docx) - Complete developer reference
- **Raw Data Handbooks/** - Source documentation files
  - API_Portal_Integration_Guide_Rawdata.pdf
  - Webhook_Integration_Guide_Rawdata.pdf

### Webhook Application
The **Webhook/** directory contains the complete webhook receiver application.

**Core Application:**
- `main.py` - FastAPI application with webhook endpoint and background processor
- `processor.py` - Event router and handlers for all SafeSend event types
- `models.py` - Pydantic models for webhook events and data structures
- `config.py` - Configuration management via environment variables
- `downloader.py` - Document downloader for time-limited SAS URLs
- `queue.py` - In-memory event queue (with optional Azure Service Bus support)

**Entry Points:**
- `run.py` - Python entry point for starting the application
- `Start-Webhook.ps1` - PowerShell launcher script

**Testing:**
- `test_receiver.py` - Test utilities for webhook endpoint

**Configuration:**
- `.env.example` - Environment variable template
- `requirements.txt` - Python dependencies

## Supported Event Types

The webhook receiver handles events from multiple SafeSend products:

**SafeSend Returns:**
- Download eSigned documents
- Return status changes

**SafeSend Signatures:**
- Document signed (3000)
- Signature status changed (3001)

**SafeSend Organizers:**
- Engagement letter signed (2000)
- Organizer completed (2001)
- Source document uploaded (2002)
- Organizer accessed (2003)
- Questionnaire completed (2004)

**SafeSend Exchange:**
- DRL document available (4000)
- Drop-off link document (4001)

**Client Management:**
- Client information changed (5001)

**SafeSend Gather:**
- eSigned documents (6000)
- Fillable organizer (6001)
- Source documents (6002)
- Custom questionnaire (6003)

## Setup

### Prerequisites
- Python 3.9 or higher
- Network access to receive webhooks from SafeSend
- (Optional) Azure Service Bus for production queue management

### Installation

1. Clone the repository:
```bash
git clone https://github.com/mickpletcher/SafeSend.git
cd SafeSend/Webhook
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your settings
```

### Configuration

Edit `.env` with your settings:

```env
# Webhook Security - set this in SafeSend Developer Portal
WEBHOOK_SECRET=your_shared_secret_here

# Document Storage - local or UNC path
DOWNLOAD_BASE_PATH=C:\SafeSendDocuments

# Server
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info

# Optional: Microsoft Teams notifications
TEAMS_WEBHOOK_URL=

# Optional: Azure Service Bus (recommended for production)
AZURE_SERVICE_BUS_CONNECTION_STRING=
AZURE_SERVICE_BUS_QUEUE_NAME=safesend-events
```

## Usage

### Starting the Webhook Receiver

**Windows (PowerShell):**
```powershell
cd Webhook
.\Start-Webhook.ps1
```

**Python:**
```bash
cd Webhook
python run.py
```

**Direct with uvicorn:**
```bash
cd Webhook
uvicorn main:app --host 0.0.0.0 --port 8000
```

The application starts on `http://0.0.0.0:8000` by default.

### Endpoints

- `POST /webhook/safesend` - Main webhook receiver endpoint
- `GET /health` - Health check with queue depth

### Configuring SafeSend

1. Log in to SafeSend Developer Portal
2. Navigate to Webhook Configuration
3. Set webhook URL to: `https://your-server.com/webhook/safesend`
4. Set API Key header to match your `WEBHOOK_SECRET` value
5. Select event types to subscribe to

## How It Works

1. **Webhook Reception** - SafeSend POSTs JSON payloads to `/webhook/safesend`
2. **Validation** - Optional API key header validation
3. **Event Queuing** - Events are queued for async processing
4. **Immediate Response** - Returns HTTP 200 immediately (critical to prevent webhook disablement)
5. **Background Processing** - Events are routed to handlers based on type
6. **Document Download** - SAS URLs are processed immediately before expiration
7. **Storage** - Documents saved to configured `DOWNLOAD_BASE_PATH`

## Important Notes

**SAS URL Expiration:**
SAS URLs in webhook payloads are time-limited and expire quickly. The application downloads documents immediately upon receipt. Never store SAS URLs for later use.

**HTTP 200 Response:**
The webhook endpoint MUST return HTTP 200. If SafeSend does not receive a 2xx response, it will disable the webhook subscription and queue all future events.

**Production Deployment:**
- Use HTTPS with valid SSL certificate
- Configure `WEBHOOK_SECRET` for security
- Use Azure Service Bus instead of in-memory queue
- Configure network firewall to allow SafeSend webhook IPs
- Use UNC path or network storage for `DOWNLOAD_BASE_PATH`

## Architecture

```
SafeSend → POST → /webhook/safesend → Validate → Queue → Background Processor
                                                              ↓
                                                         Route by Type
                                                              ↓
                                                    Event Type Handlers
                                                              ↓
                                                    Download Documents
                                                              ↓
                                                      Save to Storage
```

## License

MIT License - See [LICENSE](LICENSE) for details.

Copyright (c) 2026 Mick Pletcher
