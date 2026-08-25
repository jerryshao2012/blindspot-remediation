#!/usr/bin/env bash
# ==============================================================================
# Serve HTML Presentations on localhost (macOS / Linux)
# ==============================================================================
set -e

# Resolve repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default configuration
DEFAULT_PORT=8080
PORT="${1:-$DEFAULT_PORT}"
OPEN_BROWSER=true

# Parse flags
for arg in "$@"; do
  case $arg in
    --no-open)
      OPEN_BROWSER=false
      ;;
    --deck1)
      DECK_TARGET="docs/code-assistant-skill-plugin-development.html"
      ;;
    --deck2)
      DECK_TARGET="release-gate/demo/release-gate-demo.html"
      ;;
    [0-9]*)
      PORT="$arg"
      ;;
  esac
done

# Function to check if a port is in use
is_port_in_use() {
  local p="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -i ":$p" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$p" >/dev/null 2>&1
  else
    return 1
  fi
}

# Auto-increment port if busy
MAX_PORT_ATTEMPTS=20
CURRENT_PORT="$PORT"
attempt=0
while is_port_in_use "$CURRENT_PORT"; do
  echo "⚠️  Port $CURRENT_PORT is already in use. Checking next port..."
  CURRENT_PORT=$((CURRENT_PORT + 1))
  attempt=$((attempt + 1))
  if [ "$attempt" -ge "$MAX_PORT_ATTEMPTS" ]; then
    echo "❌ Error: Could not find an available port after $MAX_PORT_ATTEMPTS attempts."
    exit 1
  fi
done
PORT="$CURRENT_PORT"

BASE_URL="http://localhost:${PORT}"
DECK1_URL="${BASE_URL}/docs/code-assistant-skill-plugin-development.html"
DECK2_URL="${BASE_URL}/release-gate/demo/release-gate-demo.html"
PORTAL_URL="${BASE_URL}/docs/presentations.html"

# Determine target URL to open
if [ -n "$DECK_TARGET" ]; then
  OPEN_URL="${BASE_URL}/${DECK_TARGET}"
elif [ -f "docs/presentations.html" ]; then
  OPEN_URL="$PORTAL_URL"
else
  OPEN_URL="$DECK1_URL"
fi

# Print banner
echo ""
echo "================================================================================"
echo "  🎬 PRESENTATION LOCALHOST SERVER (macOS / Linux)"
echo "================================================================================"
echo "  Root Directory : $SCRIPT_DIR"
echo "  Server Address : $BASE_URL"
echo ""
echo "  📖 Available Presentation Decks:"
echo "    [1] Code Assistant Skill & Plugin Dev:"
echo "        $DECK1_URL"
echo ""
echo "    [2] Release Gate Live Demonstration:"
echo "        $DECK2_URL"
echo ""
echo "    [★] Presentation Hub:"
echo "        $PORTAL_URL"
echo ""
echo "  💡 Speaker Mode Tip:"
echo "     Press 'N' or click the Speaker Notes icon on any slide."
echo "     Multi-screen placement works automatically on http://localhost!"
echo "================================================================================"
echo "  Press [Ctrl + C] to stop the server."
echo "================================================================================"
echo ""

# Helper to open browser
open_browser_url() {
  local url="$1"
  if [ "$OPEN_BROWSER" = true ]; then
    (
      sleep 0.8
      if command -v open >/dev/null 2>&1; then
        open "$url"
      elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 || true
      elif command -v sensible-browser >/dev/null 2>&1; then
        sensible-browser "$url" >/dev/null 2>&1 || true
      fi
    ) &
  fi
}

open_browser_url "$OPEN_URL"

# Detect and run server
if command -v python3 >/dev/null 2>&1; then
  echo "🚀 Starting server with Python 3..."
  exec python3 -m http.server "$PORT" --bind 127.0.0.1
elif command -v python >/dev/null 2>&1; then
  echo "🚀 Starting server with Python..."
  exec python -m http.server "$PORT" --bind 127.0.0.1
elif command -v node >/dev/null 2>&1; then
  echo "🚀 Starting server with Node.js built-in HTTP server..."
  exec node -e "
    const http = require('http');
    const fs = require('fs');
    const path = require('path');
    const root = process.cwd();
    const mimeTypes = {
      '.html': 'text/html; charset=utf-8',
      '.js': 'text/javascript; charset=utf-8',
      '.mjs': 'text/javascript; charset=utf-8',
      '.css': 'text/css; charset=utf-8',
      '.json': 'application/json',
      '.png': 'image/png',
      '.jpg': 'image/jpeg',
      '.svg': 'image/svg+xml',
      '.ico': 'image/x-icon'
    };
    const server = http.createServer((req, res) => {
      let reqPath = decodeURI(req.url.split('?')[0]);
      if (reqPath === '/' || reqPath === '') reqPath = '/docs/presentations.html';
      const filePath = path.join(root, reqPath);
      if (!filePath.startsWith(root)) {
        res.writeHead(403);
        return res.end('403 Forbidden');
      }
      fs.stat(filePath, (err, stats) => {
        if (err || !stats.isFile()) {
          res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
          return res.end('404 Not Found: ' + reqPath);
        }
        const ext = path.extname(filePath).toLowerCase();
        res.writeHead(200, {
          'Content-Type': mimeTypes[ext] || 'application/octet-stream',
          'Access-Control-Allow-Origin': '*'
        });
        fs.createReadStream(filePath).pipe(res);
      });
    });
    server.listen($PORT, '127.0.0.1', () => {
      console.log('Serving HTTP on 127.0.0.1 port $PORT ...');
    });
  "
else
  echo "❌ Error: Neither Python 3 nor Node.js was found on your system."
  echo "Please install Python 3 (https://www.python.org) or Node.js (https://nodejs.org)."
  exit 1
fi
