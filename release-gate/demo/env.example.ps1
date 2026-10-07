$username = [uri]::EscapeDataString("DOMAIN\username")
$password = [uri]::EscapeDataString("password")
$proxy  = "http://${username}:${password}@proxy.example.com:8080/"
$email = "user@example.com"
$token = "your_token_here"
$env:HTTP_PROXY = $proxy
$env:HTTPS_PROXY = $proxy
$env:ALL_PROXY = $proxy
$env:http_proxy = $proxy
$env:https_proxy = $proxy
$env:all_proxy = $proxy
$env:NO_PROXY = "localhost,127.0.0.1"
$env:UV_SYSTEM_CERTS = "true"
$env:UV_LINK_MODE="copy"

# Configure Git proxy
# git config --global http.proxy $proxy
# git config --global https.proxy $proxy

# Config pip proxy and indexes
# pip config --user set global.proxy $proxy
# pip config --user set global.index https://${email}:${token}@example.jfrog.io/artifactory/api/pypi/pypi-virtual/simple
# pip config --user set global.index-url https://${email}:${token}@example.jfrog.io/artifactory/api/pypi/pypi-virtual/simple
# pip config --user set global.trusted-host example.jfrog.io
# pip config --user set global.extra-index-url https://${email}:${token}@example.jfrog.io/artifactory/api/pypi/mlops-PyPI-Releases-85777/simple