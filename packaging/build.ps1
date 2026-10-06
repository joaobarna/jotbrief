# Gera o app instalável em dist\SaidKeep\ (PyInstaller, pasta única). Uso: powershell -File packaging\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
uv run python scripts\gerar_changelog.py   # versão = data/hora do último commit (YYYY.MM.DD.HH.mm), embutida no app
uv run pyinstaller --noconfirm --clean --windowed --name SaidKeep `
  --icon src\saidkeep\assets\saidkeep.ico `
  --paths src `
  --add-data "src\saidkeep\assets;saidkeep\assets" `
  --add-data "src\saidkeep\data;saidkeep\data" `
  --collect-data faster_whisper `
  --collect-all sherpa_onnx `
  --collect-all ctranslate2 `
  --exclude-module nvidia `
  --exclude-module torch `
  --exclude-module tkinter `
  --exclude-module matplotlib `
  --exclude-module pytest `
  packaging\entry.py
