#!/usr/bin/env sh
# Copy to env.sh, replace the placeholders, and source it in a POSIX shell.
# Keep env.sh untracked. Do not commit proxy credentials.

proxy_username='DOMAIN\user'
proxy_password='replace-with-password'
username=$(PROXY_USERNAME="$proxy_username" python3 -c 'import os, urllib.parse; print(urllib.parse.quote(os.environ["PROXY_USERNAME"], safe=""))')
password=$(PROXY_PASSWORD="$proxy_password" python3 -c 'import os, urllib.parse; print(urllib.parse.quote(os.environ["PROXY_PASSWORD"], safe=""))')
proxy="http://${username}:${password}@proxy.example.corp:8080/"

export HTTP_PROXY="$proxy"
export HTTPS_PROXY="$proxy"
export ALL_PROXY="$proxy"
export NO_PROXY="localhost,127.0.0.1"
export UV_SYSTEM_CERTS="true"
export UV_LINK_MODE="copy"
