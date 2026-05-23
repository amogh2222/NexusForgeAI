#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════
# NexusForge AI — Linux/macOS Setup Script
# Usage: bash scripts/setup.sh
# ════════════════════════════════════════════════════════════════
set -euo pipefail

BLUE='\033[0;34m'; CYAN='\033[0;36m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

info()    { echo -e "${CYAN}[NexusForge]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo -e "${BLUE}"
echo "  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗"
echo "  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝"
echo "  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗"
echo "  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║"
echo "  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║"
echo "  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝"
echo "                  AI Engineering Platform"
echo -e "${NC}"

# ─── Check prerequisites ──────────────────────────────────────
info "Checking prerequisites..."

check_command() {
    command -v "$1" &>/dev/null || error "$1 is required but not installed. Please install it first."
    success "$1 found: $(command -v "$1")"
}

check_command docker
check_command "docker compose" || check_command docker-compose
check_command python3
check_command node
check_command npm

# Check Docker is running
docker info &>/dev/null || error "Docker daemon is not running. Please start Docker first."
success "Docker daemon is running"

# ─── Copy .env ────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    info "Creating .env from template..."
    cp .env.example .env
    
    # Generate secure random keys
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/your-super-secret-jwt-key-change-this-in-production-minimum-32-chars/$JWT_SECRET/" .env
    success ".env created with auto-generated JWT secret"
else
    warn ".env already exists, skipping"
fi

# ─── Pull & start infrastructure services ─────────────────────
info "Pulling Docker images..."
docker compose pull --quiet

info "Starting infrastructure services..."
docker compose up -d postgres redis chromadb

# Wait for PostgreSQL
info "Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
    docker compose exec -T postgres pg_isready -U nexus -d nexusforge &>/dev/null && break
    sleep 2
done
success "PostgreSQL is ready"

# Wait for Redis
info "Waiting for Redis..."
for i in $(seq 1 15); do
    docker compose exec -T redis redis-cli ping &>/dev/null && break
    sleep 1
done
success "Redis is ready"

# ─── Install Python backend dependencies ──────────────────────
info "Installing Python backend dependencies..."
if command -v uv &>/dev/null; then
    uv pip install -e ".[all]" --quiet
elif command -v pip3 &>/dev/null; then
    pip3 install -e ".[all]" --quiet
fi
success "Python dependencies installed"

# ─── Run database migrations ──────────────────────────────────
info "Running database migrations..."
python3 -m alembic upgrade head || warn "Migrations failed (may need to configure DATABASE_URL)"

# ─── Install frontend dependencies ────────────────────────────
info "Installing frontend dependencies..."
cd frontend && npm ci --silent && cd ..
success "Frontend dependencies installed"

# ─── Pull Ollama model ────────────────────────────────────────
if docker compose ps ollama 2>/dev/null | grep -q "running"; then
    info "Pulling Ollama model (qwen2.5-coder:7b) — this may take a few minutes..."
    docker compose exec ollama ollama pull qwen2.5-coder:7b && \
        success "Ollama model downloaded" || \
        warn "Ollama model download failed (you can pull manually with: docker compose exec ollama ollama pull qwen2.5-coder:7b)"
fi

# ─── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN} NexusForge AI setup complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "  Start everything:       docker compose up"
echo "  Start frontend only:    cd frontend && npm run dev"
echo "  Start backend only:     uvicorn backend.main:app --reload"
echo "  Start Celery workers:   celery -A backend.workers.celery_app worker -l info"
echo ""
echo "  Frontend:               http://localhost:3000"
echo "  Backend API:            http://localhost:8000"
echo "  API Docs (Swagger):     http://localhost:8000/docs"
echo "  ChromaDB:               http://localhost:8001"
echo ""
