#!/usr/bin/env sh
# macOS/POSIX proxy environment. Source this file from your shell.
# . demo/env.sh

proxy='http://DOMAIN%5Cusername:password@proxy.example.com:8080/'

export HTTP_PROXY="$proxy"
export HTTPS_PROXY="$proxy"
export ALL_PROXY="$proxy"
export http_proxy="$proxy"
export https_proxy="$proxy"
export all_proxy="$proxy"
export NO_PROXY="localhost,127.0.0.1,example.jfrog.io"
export no_proxy="$NO_PROXY"
export UV_SYSTEM_CERTS="true"
export UV_LINK_MODE="copy"

# Configure Git proxy
# git config --global http.proxy "$proxy"
# git config --global https.proxy "$proxy"

# Config pip proxy and indexes
email='user@example.com'
token='your_token_here'
artifactory_index_url="https://${email}:${token}@example.jfrog.io/artifactory/api/pypi/pypi-virtual/simple"
artifactory_extra_index_url="https://${email}:${token}@example.jfrog.io/artifactory/api/pypi/mlops-PyPI-Releases-85777/simple"

export UV_INDEX_URL="$artifactory_index_url"
# The extra index currently returns 403 for this project; opt in explicitly
# after access is granted.
unset UV_EXTRA_INDEX_URL

pip config --user set global.proxy "$proxy"
pip config --user set global.index "$artifactory_index_url"
pip config --user set global.index-url "$artifactory_index_url"
pip config --user set global.trusted-host "example.jfrog.io"
pip config --user set global.extra-index-url "$artifactory_extra_index_url"

# uv sync --system-certs