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

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

$Output = Join-Path $Root "dist\$Name.exe"
if (-not (Test-Path -LiteralPath $Output)) {
  Write-Error "sidecar build did not produce expected output: $Output"
  exit 1
}

Write-Host "sidecar built: dist\$Name.exe"
