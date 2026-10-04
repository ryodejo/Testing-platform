$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$localDir = Join-Path $projectRoot '.local'
$keyPath = Join-Path $localDir 'secret-key.txt'
if (!(Test-Path -LiteralPath $keyPath)) {
    New-Item -ItemType Directory -Force -Path $localDir | Out-Null
    $keyBytes = New-Object byte[] 64
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($keyBytes) } finally { $rng.Dispose() }
    [IO.File]::WriteAllText($keyPath, [Convert]::ToBase64String($keyBytes))
}
if (!$env:SECRET_KEY) { $env:SECRET_KEY = [IO.File]::ReadAllText($keyPath) }
if (!$env:DEBUG) { $env:DEBUG = '1' }
if (!$env:ALLOWED_HOSTS) { $env:ALLOWED_HOSTS = 'localhost,127.0.0.1' }
