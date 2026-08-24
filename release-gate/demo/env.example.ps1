# Copy to env.ps1, replace the placeholders, and dot-source it in PowerShell.
# Keep env.ps1 untracked. Do not commit proxy credentials.

$username = [uri]::EscapeDataString("DOMAIN\user")
$password = [uri]::EscapeDataString("replace-with-password")
$proxy = "http://${username}:${password}@proxy.example.corp:8080/"

$env:HTTP_PROXY = $proxy
$env:HTTPS_PROXY = $proxy
$env:ALL_PROXY = $proxy
$env:NO_PROXY = "localhost,127.0.0.1"
$env:UV_SYSTEM_CERTS = "true"
$env:UV_LINK_MODE = "copy"
