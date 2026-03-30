# SafeSend Webhook Receiver Launcher
# Run from anywhere - sets location relative to this script's directory

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
& python -m Webhook.run
