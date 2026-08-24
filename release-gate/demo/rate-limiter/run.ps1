[CmdletBinding()]
param(
    [ValidateSet("verify", "verify-repair")]
    [string]$Command = "verify"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$environmentScript = Join-Path $PSScriptRoot "..\env.ps1"
if (-not (Test-Path -LiteralPath $environmentScript -PathType Leaf)) {
    throw "Missing $environmentScript. Copy ..\env.example.ps1 to ..\env.ps1 and fill in approved local values."
}

. $environmentScript
$python = (uv python find 3.12 | Select-Object -Last 1).Trim()
if (-not $python -or -not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "uv did not resolve a Python 3.12 executable"
}

$version = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
if ($version -notmatch '^3\.12\.') {
    throw "Resolved interpreter is Python $version, expected Python 3.12.x"
}

& $python (Join-Path $PSScriptRoot "demo.py") $Command
exit $LASTEXITCODE
