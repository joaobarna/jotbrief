# Gera o app instalável em dist\JotBrief\ (PyInstaller, pasta única). Uso: powershell -File packaging\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
uv run pyinstaller --noconfirm --clean --windowed --name JotBrief `
  --icon src\jotbrief\assets\jotbrief.ico `
  --paths src `
  --add-data "src\jotbrief\assets;jotbrief\assets" `
  --collect-data faster_whisper `
  --collect-all sherpa_onnx `
  --collect-all ctranslate2 `
  --exclude-module nvidia `
  --exclude-module torch `
  --exclude-module tkinter `
  --exclude-module matplotlib `
  --exclude-module pytest `
  packaging\jb_entry.py
