# NexusForge AI

[![License: MIT](https://img.shields.io/badge/License-MIT-violet.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-purple.svg)](https://langchain-ai.github.io/langgraph/)

> **Enterprise-grade autonomous AI software engineering platform.** Upload a repository, ask anything — 6 specialized AI agents will understand, generate, review, document, and deploy your code.

---

## Overview

NexusForge AI is a full-stack, production-ready AI engineering operating system that combines:

- **Multi-Agent Orchestration** — 6 specialized LangGraph agents (Planner, Coder, Reviewer, Infra, Docs, Debugger) coordinated by a Supervisor StateGraph
- **RAG Pipeline** — Tree-sitter AST chunking + BGE embeddings + BM25 hybrid retrieval via Reciprocal Rank Fusion for precise code search
- **Real-time Streaming** — Agent outputs stream token-by-token via WebSocket using LangGraph's `astream_events v2` API
- **Isolated Code Execution** — Run Python, Node.js, Go, and Bash in sandboxed subprocesses with live terminal output
- **Full GitHub Integration** — OAuth, private repos, branch exploration, PR analysis, clone + index pipeline
- **Long-term Memory** — ChromaDB vector store with HNSW indexing, per-project semantic search that persists across sessions

This is not a chatbot. It is a deployable SaaS platform with a production-grade distributed backend.

---

## ✨ Features

- **🤖 6 Specialized AI Agents** — Each expert in a specific engineering domain
- **📊 Semantic Code Search** — BGE + BM25 hybrid retrieval with sub-second response
- **💻 Live Code Execution** — Python, Node.js, Go, Bash in real-time sandboxes
- **🏗️ Architecture Diagrams** — React Flow interactive system diagrams auto-generated from repos
- **📄 README Generation** — Production-grade docs generated from actual codebase analysis
- **🔍 Security Review** — Automated vulnerability and anti-pattern detection
- **🐳 Infra Generation** — Dockerfile, docker-compose, GitHub Actions CI/CD on demand
- **🐛 Auto Debugging** — Root cause analysis with targeted code fixes
- **🔐 Full Auth** — JWT access/refresh tokens + GitHub OAuth (public + private repos)
- **📡 WebSocket Streaming** — Real-time agent output with per-agent color coding

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js 16 Frontend                       │
│  Dashboard · Workspace · Repository · Agents · Execution    │
│  Memory · Architecture Viewer                               │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP + WebSocket
┌────────────────────▼────────────────────────────────────────┐
│                  FastAPI Backend                             │
│  Auth · Projects · Repositories · GitHub · Chat · Exec     │
│  WebSocket Hub (Redis pub/sub → WS broadcast)               │
└──┬──────────────────┬──────────────────┬────────────────────┘
   │                  │                  │
   ▼                  ▼                  ▼
PostgreSQL          Redis             ChromaDB
(Users, Projects,  (Broker +        (BGE Vectors
 Chat, Executions,  Pub/Sub +         HNSW Index
 Agent Logs)        Cache)            Per-project)
                     │
┌────────────────────▼────────────────────────────────────────┐
│               Celery Workers                                 │
│  indexing_task  ·  agent_task  ·  execution_task            │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│            LangGraph Orchestrator                            │
│  StateGraph with PostgresSaver checkpoints                  │
│                                                             │
│   ┌──────────┐  ┌────────┐  ┌──────────┐  ┌─────────┐     │
│   │ Planner  │  │ Coder  │  │ Reviewer │  │  Infra  │     │
│   └──────────┘  └────────┘  └──────────┘  └─────────┘     │
│   ┌──────────┐  ┌──────────┐                               │
│   │  Docs   │  │ Debugger │                               │
│   └──────────┘  └──────────┘                               │
│                     │                                       │
│              Ollama (Qwen2.5-Coder)                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

**Prerequisites:** Docker Desktop, Python 3.11+, Node.js 20+

```bash
# 1. Clone the repository
git clone https://github.com/your-org/nexusforge-ai.git
cd nexusforge-ai

# 2. Run setup (Linux/macOS)
bash scripts/setup.sh

# OR on Windows PowerShell
.\scripts\setup.ps1

# 3. Start all services
docker compose up

# 4. Open the platform
open http://localhost:3000
```

The setup script will:
- Copy `.env.example` → `.env` with auto-generated JWT secret
- Pull all Docker images
- Start PostgreSQL, Redis, ChromaDB
- Run database migrations
- Install Python and Node.js dependencies
- Pull the Ollama Qwen2.5-Coder model

---

## 📋 Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Docker Desktop | 25.0+ | All infrastructure services |
| Python | 3.11+ | Backend + Celery workers |
| Node.js | 20+ | Next.js frontend |
| npm | 10+ | Frontend package management |
| Ollama | Latest | Local LLM inference (optional — OpenAI fallback available) |

---

## ⚙️ Installation

### Option A: Full Docker (recommended)

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env: set JWT_SECRET_KEY, optionally add OPENAI_API_KEY

# Start everything
docker compose up -d

# Pull LLM model (first time, ~4GB download)
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

### Option B: Hybrid (Docker infra + local dev)

```bash
# Start only infra services
docker compose up -d postgres redis chromadb ollama

# Install backend
pip install -e ".[all]"
python -m alembic upgrade head
uvicorn backend.main:app --reload --port 8000

# Start Celery workers (separate terminal)
celery -A backend.workers.celery_app worker \
  -Q indexing,agents,execution \
  -c 4 --loglevel=info

# Install and start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

---

## 🐳 Docker Setup

The `docker-compose.yml` defines 8 services:

| Service | Port | Description |
|---------|------|-------------|
| `backend` | 8000 | FastAPI + Uvicorn (2 workers) |
| `frontend` | 3000 | Next.js production build |
| `postgres` | 5432 | Primary database (pgvector ready) |
| `redis` | 6379 | Celery broker + pub/sub |
| `chromadb` | 8001 | Vector store (persistent volume) |
| `celery-worker` | — | 3 queues: indexing, agents, execution |
| `ollama` | 11434 | Local LLM inference |
| `nginx` | 80/443 | Reverse proxy + SSL termination |

---

## 🔧 Configuration

All configuration is via environment variables. Copy `.env.example` → `.env` and set:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | ✅ | — | Must be 32+ chars random string |
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://...` | Async PostgreSQL connection |
| `REDIS_URL` | ✅ | `redis://redis:6379/0` | Redis connection |
| `OLLAMA_BASE_URL` | — | `http://ollama:11434` | Local Ollama endpoint |
| `OLLAMA_MODEL` | — | `qwen2.5-coder:7b` | Default LLM model |
| `OPENAI_API_KEY` | — | — | OpenAI fallback (if Ollama unavailable) |
| `GITHUB_CLIENT_ID` | — | — | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | — | — | GitHub OAuth app client secret |
| `EMBEDDING_MODEL` | — | `BAAI/bge-base-en-v1.5` | BGE embedding model |
| `CHROMA_HOST` | — | `chromadb` | ChromaDB server host |
| `UPLOAD_DIR` | — | `/app/data/uploads` | Repository upload path |

---

## 📡 API Documentation

Interactive Swagger UI: `http://localhost:8000/docs`

### Key Endpoints

```
POST   /api/v1/auth/register          Register new user
POST   /api/v1/auth/login             Login → JWT tokens
GET    /api/v1/github/oauth/url       Get GitHub OAuth URL
POST   /api/v1/github/oauth/callback  Exchange OAuth code → tokens
GET    /api/v1/github/repos           List user's GitHub repos

POST   /api/v1/projects               Create project
GET    /api/v1/projects               List projects

POST   /api/v1/repositories/upload    Upload ZIP for indexing
POST   /api/v1/repositories/github    Clone GitHub repo
GET    /api/v1/repositories/{id}/tree File tree

POST   /api/v1/chat/message           Queue AI message (streams via WS)
GET    /api/v1/chat/{thread_id}/history Chat history

GET    /api/v1/memory/retrieve?query= Semantic search
GET    /api/v1/memory/stats           ChromaDB collection stats

POST   /api/v1/executions             Run code in sandbox
GET    /api/v1/executions/{id}        Get execution result

WS     /api/v1/ws/{project_id}/{thread_id}  Real-time agent streaming
```

---

## 🚢 Deployment

### Production with Docker Compose

```bash
# Set production env vars
echo "ENVIRONMENT=production" >> .env
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" >> .env

# Build images
docker compose build

# Start with nginx
docker compose --profile production up -d

# Set up SSL (Let's Encrypt)
docker compose exec nginx certbot --nginx -d your-domain.com
```

### Environment-Specific Tips

- **JWT_SECRET_KEY**: Generate with `openssl rand -hex 32`. Never reuse dev key in prod.
- **Database**: Use managed PostgreSQL (AWS RDS, Supabase, Neon) for production. Update `DATABASE_URL`.
- **Redis**: Use managed Redis (Upstash, AWS ElastiCache) for production scaling.
- **ChromaDB**: Mount a persistent volume — data survives restarts.
- **Ollama**: For cloud deployment, use OpenAI API by setting `USE_OPENAI_FALLBACK=true` and `OPENAI_API_KEY`.

---

## 📈 Scaling

NexusForge is designed to scale horizontally:

```bash
# Scale Celery workers
docker compose up -d --scale celery-worker=4

# Scale FastAPI backend
docker compose up -d --scale backend=3
```

**Worker queues** are separated for independent scaling:
- `indexing` — Heavy I/O (repo cloning, embedding generation)
- `agents` — CPU/GPU (LLM inference)  
- `execution` — Sandboxed code runs (isolated resources)

---

## 🔍 Troubleshooting

| Problem | Solution |
|---------|----------|
| `Ollama connection refused` | Run `docker compose up ollama` and wait 30s for model load |
| `ChromaDB heartbeat failed` | Check `docker compose ps chromadb` — it needs 20-30s to start |
| `Embedding model slow` | First run downloads ~430MB BGE model — subsequent runs use cache |
| `WebSocket disconnects` | Check `NEXT_PUBLIC_WS_URL` matches your backend hostname |
| `GitHub OAuth fails` | Verify `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and redirect URI in GitHub App settings |
| `Celery tasks queued but not running` | Start worker: `docker compose up celery-worker` |

---

## 📁 Project Structure

```
nexusforge-ai/
├── backend/                    # FastAPI application
│   ├── main.py                 # App entry point + lifespan
│   ├── core/                   # Config, database, security, dependencies
│   ├── models/                 # SQLAlchemy ORM models
│   ├── api/
│   │   ├── routes/             # auth, github, projects, repositories, health
│   │   └── websocket/          # hub.py (ConnectionManager) + events.py
│   ├── services/               # auth_service, repository_service
│   └── workers/
│       ├── celery_app.py       # Celery configuration
│       └── tasks/              # indexing_task, agent_task, execution_task
├── agents/                     # LangGraph agent system
│   ├── orchestrator.py         # StateGraph + PostgresSaver + Supervisor
│   ├── base_agent.py           # Abstract base + Ollama/OpenAI LLM
│   ├── planner/                # ExecutionPlan structured output
│   ├── coder/                  # GeneratedCode structured output
│   ├── reviewer/               # ReviewReport structured output
│   ├── infra/                  # Dockerfile + docker-compose + CI/CD
│   ├── docs/                   # README generation + Q&A
│   └── debugger/               # Root cause analysis + DebugReport
├── rag/                        # RAG pipeline
│   ├── chunking/               # ast_chunker.py + text_chunker.py
│   ├── embeddings/             # embedder.py (BGE singleton)
│   ├── vector_store/           # chroma_store.py (HNSW + batch upsert)
│   └── retrieval/              # retriever.py (Hybrid BGE+BM25+RRF)
├── frontend/                   # Next.js 16 application
│   ├── app/
│   │   ├── (dashboard)/        # Dashboard, Workspace, Repository, Agents,
│   │   │                       # Execution, Memory, Architecture pages
│   │   └── (auth)/             # Login, Register pages
│   ├── components/
│   │   ├── layout/Sidebar.tsx  # Animated collapsible sidebar
│   │   └── providers/          # QueryProvider, StoreProvider
│   └── globals.css             # Design system (glassmorphism, animations)
├── deployment/
│   └── nginx/nginx.conf        # SSL + WebSocket + rate limiting
├── scripts/
│   ├── setup.sh                # Linux/macOS quick setup
│   └── setup.ps1               # Windows PowerShell setup
├── .github/workflows/ci.yml    # CI: test → build → push → scan
├── Dockerfile.backend          # Multi-stage backend image
├── Dockerfile.frontend         # Standalone Next.js image
├── docker-compose.yml          # Full stack orchestration
└── .env.example                # Environment template
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'feat: add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

Please follow the existing code style:
- Python: type hints everywhere, async where appropriate, structured logging with `structlog`
- TypeScript: strict mode, functional components, Framer Motion for animations
- Commits: [Conventional Commits](https://conventionalcommits.org/) format

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ⚡ by the NexusForge team · Powered by LangGraph, FastAPI, Next.js, ChromaDB, and Ollama
</p>
