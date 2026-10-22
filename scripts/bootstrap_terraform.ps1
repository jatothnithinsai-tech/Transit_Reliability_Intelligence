$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolDir = Join-Path $projectRoot '.tools/terraform-1.13.5'
New-Item -ItemType Directory -Path $toolDir -Force | Out-Null
$zipPath = Join-Path $toolDir 'terraform_1.13.5_windows_amd64.zip'
$checksPath = Join-Path $toolDir 'SHA256SUMS'
Invoke-WebRequest -UseBasicParsing -Uri 'https://releases.hashicorp.com/terraform/1.13.5/terraform_1.13.5_windows_amd64.zip' -OutFile $zipPath -TimeoutSec 60
Invoke-WebRequest -UseBasicParsing -Uri 'https://releases.hashicorp.com/terraform/1.13.5/terraform_1.13.5_SHA256SUMS' -OutFile $checksPath -TimeoutSec 30
$match = Get-Content -LiteralPath $checksPath | Where-Object { $_ -match ' terraform_1.13.5_windows_amd64.zip$' }
if (-not $match) { throw 'Official Terraform checksum not found.' }
$expectedHash = ($match -split '\s+')[0]
$actualHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
if ($actualHash -ne $expectedHash) { throw 'Terraform archive checksum mismatch.' }
Expand-Archive -LiteralPath $zipPath -DestinationPath $toolDir -Force
& (Join-Path $toolDir 'terraform.exe') version
