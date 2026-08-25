<#
.SYNOPSIS
  Serves HTML presentations on http://localhost for Windows PowerShell.

.DESCRIPTION
  Launches a local HTTP server from the repository root, allowing presentations
  to run on http://localhost where the Window Management API and multi-monitor
  Speaker View work seamlessly.

.PARAMETER Port
  The TCP port to listen on (default: 8080). If busy, automatically finds the next open port.

.PARAMETER NoOpen
  Do not automatically launch the web browser.

.PARAMETER Deck1
  Open presentation deck 1 directly (Code Assistant Skill & Plugin Development).

.PARAMETER Deck2
  Open presentation deck 2 directly (Release Gate Live Demonstration).

.EXAMPLE
  .\serve-presentations.ps1
  .\serve-presentations.ps1 -Port 3000
  .\serve-presentations.ps1 -Deck2
#>

[CmdletBinding()]
param(
  [int]$Port = 8080,
  [switch]$NoOpen,
  [switch]$Deck1,
  [switch]$Deck2
)

$ErrorActionPreference = "Stop"

# Resolve repository root directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Helper to test if a port is open
function Test-PortInUse([int]$p) {
  try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $p)
    $listener.Start()
    $listener.Stop()
    return $false
  } catch {
    return $true
  }
}

# Find available port
$CurrentPort = $Port
$MaxAttempts = 20
$Attempts = 0

while (Test-PortInUse -p $CurrentPort) {
  Write-Host "⚠️  Port $CurrentPort is in use. Checking next port..." -ForegroundColor Yellow
  $CurrentPort++
  $Attempts++
  if ($Attempts -ge $MaxAttempts) {
    Write-Error "Could not find an available port after $MaxAttempts attempts."
    exit 1
  }
}

$Port = $CurrentPort
$BaseUrl = "http://localhost:$Port"
$Deck1Url = "$BaseUrl/docs/code-assistant-skill-plugin-development.html"
$Deck2Url = "$BaseUrl/release-gate/demo/release-gate-demo.html"
$PortalUrl = "$BaseUrl/docs/presentations.html"

# Determine target URL
if ($Deck1) {
  $TargetUrl = $Deck1Url
} elseif ($Deck2) {
  $TargetUrl = $Deck2Url
} elseif (Test-Path "$ScriptDir/docs/presentations.html") {
  $TargetUrl = $PortalUrl
} else {
  $TargetUrl = $Deck1Url
}

# Print visual banner
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  🎬 PRESENTATION LOCALHOST SERVER (Windows)" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Root Directory : $ScriptDir" -ForegroundColor Gray
Write-Host "  Server Address : $BaseUrl" -ForegroundColor Green
Write-Host ""
Write-Host "  📖 Available Presentation Decks:" -ForegroundColor White
Write-Host "    [1] Code Assistant Skill & Plugin Dev:" -ForegroundColor Cyan
Write-Host "        $Deck1Url" -ForegroundColor Yellow
Write-Host ""
Write-Host "    [2] Release Gate Live Demonstration:" -ForegroundColor Cyan
Write-Host "        $Deck2Url" -ForegroundColor Yellow
Write-Host ""
Write-Host "    [★] Presentation Hub:" -ForegroundColor Cyan
Write-Host "        $PortalUrl" -ForegroundColor Yellow
Write-Host ""
Write-Host "  💡 Speaker Mode Tip:" -ForegroundColor Green
Write-Host "     Press 'N' or click the Speaker Notes icon on any slide." -ForegroundColor White
Write-Host "     Multi-screen placement works automatically on http://localhost!" -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Press [Ctrl + C] to stop the server." -ForegroundColor Gray
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Open browser if requested
if (-not $NoOpen) {
  Start-Job -ScriptBlock {
    param($url)
    Start-Sleep -Milliseconds 800
    Start-Process $url
  } -ArgumentList $TargetUrl | Out-Null
}

# Check for Python
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
  $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $pythonCmd = "py"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
  $pythonCmd = "python3"
}

if ($pythonCmd) {
  Write-Host "🚀 Starting server with Python ($pythonCmd)..." -ForegroundColor Green
  & $pythonCmd -m http.server $Port --bind 127.0.0.1
  exit $LASTEXITCODE
}

# Check for Node.js
if (Get-Command node -ErrorAction SilentlyContinue) {
  Write-Host "🚀 Starting server with Node.js..." -ForegroundColor Green
  $nodeScript = @"
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
server.listen($Port, '127.0.0.1', () => {
  console.log('Serving HTTP on 127.0.0.1 port $Port ...');
});
"@
  node -e $nodeScript
  exit $LASTEXITCODE
}

# Fallback: Native .NET HttpListener in PowerShell
Write-Host "🚀 Starting built-in PowerShell .NET HTTP server on port $Port..." -ForegroundColor Green
$listener = New-Object System.Net.HttpListener
$prefix = "http://localhost:$Port/"
$listener.Prefixes.Add($prefix)
$listener.Start()

$mimeTypes = @{
  ".html" = "text/html; charset=utf-8"
  ".js"   = "text/javascript; charset=utf-8"
  ".mjs"  = "text/javascript; charset=utf-8"
  ".css"  = "text/css; charset=utf-8"
  ".json" = "application/json"
  ".svg"  = "image/svg+xml"
  ".png"  = "image/png"
  ".jpg"  = "image/jpeg"
  ".ico"  = "image/x-icon"
}

try {
  while ($listener.IsListening) {
    $context = $listener.GetContext()
    $request = $context.Request
    $response = $context.Response

    $rawPath = [System.Uri]::UnescapeDataString($request.Url.AbsolutePath)
    if ($rawPath -eq "/" -or [string]::IsNullOrWhiteSpace($rawPath)) {
      $rawPath = "/docs/presentations.html"
    }

    $relativePath = $rawPath.TrimStart("/").Replace("/", [System.IO.Path]::DirectorySeparatorChar)
    $localFile = [System.IO.Path]::Combine($ScriptDir, $relativePath)

    if (Test-Path -Path $localFile -PathType Leaf) {
      $ext = [System.IO.Path]::GetExtension($localFile).ToLower()
      $contentType = if ($mimeTypes.ContainsKey($ext)) { $mimeTypes[$ext] } else { "application/octet-stream" }
      $response.ContentType = $contentType
      $response.Headers.Add("Access-Control-Allow-Origin", "*")

      $bytes = [System.IO.File]::ReadAllBytes($localFile)
      $response.ContentLength64 = $bytes.Length
      $response.OutputStream.Write($bytes, 0, $bytes.Length)
      $response.StatusCode = 200
    } else {
      $response.StatusCode = 404
      $msg = [System.Text.Encoding]::UTF8.GetBytes("404 Not Found: $rawPath")
      $response.ContentLength64 = $msg.Length
      $response.OutputStream.Write($msg, 0, $msg.Length)
    }
    $response.OutputStream.Close()
  }
} finally {
  $listener.Stop()
  $listener.Close()
}
