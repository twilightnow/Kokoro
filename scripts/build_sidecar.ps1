param(
  [string]$Name = "kokoro-sidecar"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name $Name `
  --collect-all edge_tts `
  --collect-all pydantic `
  --hidden-import uvicorn.logging `
  --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.websockets.auto `
  --add-data "characters;characters" `
  --add-data ".env.example;." `
  "src\api\sidecar_entry.py"

Write-Host "sidecar built: dist\$Name.exe"
