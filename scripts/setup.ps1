# NexusForge AI — Windows PowerShell Setup Script
# Usage: .\scripts\setup.ps1
# Requires: Docker Desktop, Python 3.11+, Node.js 20+

$ErrorActionPreference = "Stop"

$CYAN   = [ConsoleColor]::Cyan
$GREEN  = [ConsoleColor]::Green
$YELLOW = [ConsoleColor]::Yellow
$RED    = [ConsoleColor]::Red

function Write-Info   { param($msg) Write-Host "[NexusForge] $msg" -ForegroundColor Cyan }
function Write-Ok     { param($msg) Write-Host "[✓] $msg" -ForegroundColor Green }
function Write-Warn   { param($msg) Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Fail   { param($msg) Write-Host "[✗] $msg" -ForegroundColor Red; exit 1 }

Write-Host @"
  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
              AI Engineering Platform
"@ -ForegroundColor Blue

# ─── Prerequisite checks ──────────────────────────────────────
Write-Info "Checking prerequisites..."

$checks = @("docker", "python", "node", "npm")
foreach ($cmd in $checks) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Fail "$cmd is required but not found. Install it and retry."
    }
    Write-Ok "$cmd found"
}

# ─── .env setup ───────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Write-Info "Creating .env from template..."
    Copy-Item ".env.example" ".env"
    
    # Generate JWT secret
    $jwtSecret = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 64 | ForEach-Object { [char]$_ })
    (Get-Content ".env") -replace "your-super-secret-jwt-key-change-this-in-production-minimum-32-chars", $jwtSecret | Set-Content ".env"
    Write-Ok ".env created with auto-generated JWT secret"
} else {
    Write-Warn ".env already exists, skipping"
}

# ─── Start Docker services ────────────────────────────────────
Write-Info "Pulling Docker images..."
docker compose pull

Write-Info "Starting infrastructure services..."
docker compose up -d postgres redis chromadb

# Wait for PostgreSQL
Write-Info "Waiting for PostgreSQL..."
$retries = 0
do {
    Start-Sleep -Seconds 2
    $retries++
    $pgReady = docker compose exec -T postgres pg_isready -U nexus -d nexusforge 2>$null
} while ($LASTEXITCODE -ne 0 -and $retries -lt 20)
Write-Ok "PostgreSQL ready"

# ─── Python deps ──────────────────────────────────────────────
Write-Info "Installing Python dependencies..."
pip install -e ".[all]" --quiet
Write-Ok "Python dependencies installed"

# ─── Migrations ───────────────────────────────────────────────
Write-Info "Running database migrations..."
python -m alembic upgrade head
if ($LASTEXITCODE -eq 0) { Write-Ok "Migrations complete" } else { Write-Warn "Migrations failed — check DATABASE_URL in .env" }

# ─── Frontend deps ────────────────────────────────────────────
Write-Info "Installing frontend dependencies..."
Set-Location frontend
npm ci --silent
Set-Location ..
Write-Ok "Frontend dependencies installed"

# ─── Done ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host " NexusForge AI setup complete!" -ForegroundColor Green
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Start everything:    docker compose up"
Write-Host "  Start frontend:      cd frontend; npm run dev"
Write-Host "  Start backend:       uvicorn backend.main:app --reload"
Write-Host ""
Write-Host "  Frontend:            http://localhost:3000"
Write-Host "  API Docs (Swagger):  http://localhost:8000/docs"
Write-Host "  ChromaDB:            http://localhost:8001"
Write-Host ""
