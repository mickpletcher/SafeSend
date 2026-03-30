# SafeSend Webhook Receiver — Quick Start Checklist

Print this page. Work top to bottom. Check each box before moving on.

---

## Part 1 — Before You Begin

- [ ] You have a Windows machine (Windows 10 or 11) and can open PowerShell
- [ ] You have access to the SafeSend portal at https://secure.safesend.com
- [ ] You know the network address or hostname of the machine that will run this service
- [ ] Your IT team has confirmed the machine can receive inbound traffic on port 8000 (or a port of your choosing)
- [ ] You have a folder path ready for downloaded documents (example: `C:\SafeSendDocuments`)

---

## Part 2 — Install Prerequisites

- [ ] Install **Python 3.11 or newer**
  - Download from https://www.python.org/downloads/
  - During setup: check **"Add Python to PATH"**
  - Verify: open PowerShell, run `python --version` — should print a version number

- [ ] Install **Git**
  - Download from https://git-scm.com/download/win
  - Verify: open PowerShell, run `git --version` — should print a version number

---

## Part 3 — Get the Code

Open PowerShell and run these commands one at a time:

```powershell
# Clone the repository (adjust the path to wherever you want it)
git clone https://github.com/mickpletcher/SafeSend.git "C:\SafeSend"

# Move into the project folder
Set-Location "C:\SafeSend"

# Create a virtual Python environment
python -m venv .venv

# Activate it
.venv\Scripts\Activate.ps1

# Install all required packages
pip install -r Webhook\requirements.txt
```

- [ ] All commands ran without red error text

---

## Part 4 — Create Your Configuration File

```powershell
# Copy the example config
Copy-Item Webhook\.env.example Webhook\.env
```

Open `Webhook\.env` in Notepad and fill in **at minimum** these three lines:

| Setting | What to put here |
|---|---|
| `WEBHOOK_SECRET` | Any long random string — you will paste this into SafeSend |
| `DOWNLOAD_BASE_PATH` | Full path to the folder where documents should be saved |
| `PORT` | 8000 (or whatever port your IT team opened) |

- [ ] `WEBHOOK_SECRET` is set to a unique secret (not the placeholder text)
- [ ] `DOWNLOAD_BASE_PATH` points to a real folder that exists on disk
- [ ] The download folder is on a drive with enough free space for your document volume

---

## Part 5 — Start the Service (Test Run)

```powershell
# From the project root with the virtual environment active
python -m Webhook.run
```

You should see output like:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

- [ ] Service started without errors
- [ ] Open a browser on the same machine and go to `http://localhost:8000/health`
- [ ] The page shows `{"status": "ok", ...}` — not an error

Press `Ctrl+C` to stop the service after confirming this.

---

## Part 6 — Configure SafeSend

Log in to the SafeSend portal.

1. Navigate to **Admin Settings** then **Integrations** (or **Developer Settings** depending on your portal version)
2. Find the **Webhook** or **Outbound Notifications** section
3. Set the **Endpoint URL** to:

   ```
   http://YOUR-SERVER-ADDRESS:8000/webhook
   ```

   Replace `YOUR-SERVER-ADDRESS` with the actual hostname or IP of your machine.

4. Set the **API Key** (or **Shared Secret**) to the exact value you put in `WEBHOOK_SECRET`
5. Save

- [ ] Endpoint URL saved in SafeSend portal
- [ ] API Key in portal matches `WEBHOOK_SECRET` in your `.env` file exactly (case-sensitive)

---

## Part 7 — Fire a Test Event

In the SafeSend portal, use the **Test Webhook** or **Send Test Event** button if available. If not, complete a real transaction (such as sending a test document).

Back on your server, check the logs:

```powershell
Get-Content -Path Webhook\logs\webhook.log -Wait
```

- [ ] A log entry appeared showing a received event
- [ ] No error messages printed
- [ ] If a document was attached, verify the file appeared in your `DOWNLOAD_BASE_PATH` folder

---

## Part 8 — Run as a Background Service (Optional but Recommended)

For the service to survive reboots, schedule it as a Windows Task or run the provided launcher:

```powershell
# The launcher script handles activation and startup
.\Webhook\Start-Webhook.ps1
```

To auto-start on login or reboot, create a Scheduled Task in Windows Task Scheduler pointing to:

```
Program:   powershell.exe
Arguments: -ExecutionPolicy Bypass -File "C:\SafeSend\Webhook\Start-Webhook.ps1"
```

Set **Run whether user is logged on or not** and **Run with highest privileges**.

- [ ] Service starts automatically after a test reboot (if running in production)

---

## Part 9 — Ongoing Health Checks

Check these regularly (daily for the first week, then weekly):

| Check | How |
|---|---|
| Service is running | `http://YOUR-SERVER:8000/health` returns `"status": "ok"` |
| Queue depth is low | `queue_depth` in the health response stays near 0 |
| No error spikes | Review `Webhook\logs\webhook.log` for `ERROR` lines |
| Disk space | Confirm `DOWNLOAD_BASE_PATH` drive has free space |
| Dedupe DB size | Check file size of `Webhook\dedupe_store.db` (should stay small) |

---

## Quick Reference — Common Problems

| Symptom | Likely Cause | Fix |
|---|---|---|
| Health endpoint shows error | Service not running | Re-run start command |
| Documents not appearing | Wrong `DOWNLOAD_BASE_PATH` | Check `.env`, verify folder exists |
| SafeSend shows webhook failures | URL wrong or firewall blocked | Verify URL and port are reachable externally |
| API key errors in log | Secret mismatch | Copy-paste secret from `.env` exactly into SafeSend portal |
| Service crashes on start | Missing `.env` or bad Python path | Re-activate venv, verify `.env` exists |

---

## Emergency Stop

```powershell
# Find and stop the process
Get-Process -Name python | Stop-Process -Force
```

---

*Full documentation is in the `documentation/` folder of this repository.*
