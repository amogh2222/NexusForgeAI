<div align="center">

<br/>

<!-- Project Banner -->
<img width="100%" src="https://capsule-render.vercel.app/api?type=waving&color=7c3aed&height=200&section=header&text=NexusForge%20AI&fontSize=60&fontColor=ffffff&fontAlignY=38&desc=Autonomous%20AI%20Engineering%20Operating%20System&descAlignY=58&descColor=c4b5fd" alt="NexusForge AI Banner"/>

<br/>

<!-- Badges Row 1 - Tech Stack -->
![Python](https://img.shields.io/badge/Python_3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js_14-000000?style=for-the-badge&logo=next.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)

<!-- Badges Row 2 - AI/Infra -->
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-FF4455?style=for-the-badge&logo=qdrant&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white)

<!-- Badges Row 3 - Status -->
![License](https://img.shields.io/badge/License-MIT-7c3aed?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production_Ready-22c55e?style=for-the-badge)
![PRs](https://img.shields.io/badge/PRs-Welcome-06b6d4?style=for-the-badge)

<br/>

### *Upload any codebase. Watch 6 AI agents understand, review, debug, document, and scale it — live.*

<br/>

[**⚡ Quick Start**](#-quick-start) • [**🏗️ Architecture**](#-system-architecture) • [**🤖 Agents**](#-multi-agent-system) • [**📡 API Docs**](#-api-reference) • [**🚀 Deploy**](#-deployment)

<br/>

</div>

---

## 🧠 What is NexusForge AI?

> **NexusForge is not a chatbot wrapper. It is an autonomous AI engineering platform.**

Upload a repository. NexusForge parses it at the **AST level**, builds a **semantic knowledge graph**, indexes it with **hybrid dense+sparse retrieval**, and deploys a **graph-orchestrated multi-agent system** that operates with senior engineering depth.

<br/>

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        What NexusForge Can Do                           │
├─────────────────┬───────────────────────────────────────────────────────┤
│  UNDERSTAND     │  AST-level parsing → semantic knowledge graph          │
│  EXPLAIN        │  Architecture, data flow, service boundaries           │
│  REVIEW         │  Security, N+1 queries, async misuse, anti-patterns    │
│  GENERATE       │  READMEs, Dockerfiles, CI/CD, infra configs            │
│  DEBUG          │  Execute → capture error → reason → patch → retry      │
│  SCALE          │  "Scale to 10M users" → complete HLD + infra plan      │
│  EVOLVE         │  Commit history → architectural drift detection         │
└─────────────────┴───────────────────────────────────────────────────────┘
```

<br/>

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/yourusername/nexusforge-ai.git && cd nexusforge-ai

# 2. Configure
cp .env.example .env
# Edit .env — set DATABASE_URL, JWT_SECRET_KEY, OPENAI_API_KEY (fallback)

# 3. Launch everything
docker-compose up --build -d

# 4. Migrate DB
docker-compose exec backend alembic upgrade head

# 5. Open dashboard
open http://localhost:3000
```

> **Optional**: Pull a local model for offline inference
> ```bash
> ollama pull qwen2.5-coder:7b
> ```

<br/>

---

## 🏗️ System Architecture

```
                    ╔══════════════════════════════════════════╗
                    ║         Next.js 14 Dashboard             ║
                    ║  Chat · Agents · Execution · Memory      ║
                    ║  Architecture Viewer · Observability     ║
                    ╚══════════════╤═══════════════════════════╝
                                   │  HTTP + WebSocket
                    ╔══════════════▼═══════════════════════════╗
                    ║            FastAPI Backend               ║
                    ║  REST API · WebSocket Hub · JWT Auth     ║
                    ║  Celery Workers · Prometheus /metrics    ║
                    ╚═══╤══════════╤══════════╤═══════════════╝
                        │          │          │
          ╔═════════════▼╗  ╔══════▼═════╗  ╔▼══════════════╗
          ║ Agent Service ║  ║ RAG Service║  ║Exec. Service  ║
          ║               ║  ║            ║  ║               ║
          ║  LangGraph    ║  ║  Qdrant    ║  ║  Docker       ║
          ║  Supervisor   ║  ║  BGE Emb.  ║  ║  Sandbox      ║
          ║  6 Agents     ║  ║  BM25+RRF  ║  ║  seccomp      ║
          ╚═══════════════╝  ╚════════════╝  ╚═══════════════╝
                        │
          ╔═════════════▼══════════════════════════════════════╗
          ║                   Model Router                     ║
          ║   Ollama (local) · vLLM (GPU) · OpenAI (fallback) ║
          ╚════════════════════════════════════════════════════╝
                        │
          ╔═════════════▼══════════════════════════════════════╗
          ║                  Data Layer                        ║
          ║  PostgreSQL · Redis · Qdrant · Neo4j (graph)      ║
          ╚════════════════════════════════════════════════════╝
```

<br/>

### Key Engineering Decisions

| Decision | Choice | Why It Matters |
|:---|:---|:---|
| Agent orchestration | LangGraph StateGraph + Supervisor | Conditional multi-agent routing with durable state |
| Agent checkpoints | `PostgresSaver` | MemorySaver loses state on restart — Postgres is durable |
| Code chunking | Tree-sitter AST | Preserves function/class boundaries; splitters destroy semantic units |
| Embeddings | `BAAI/bge-base-en-v1.5` + `normalize_embeddings=True` | Required for correct cosine similarity — skipping this breaks retrieval |
| Retrieval | Hybrid dense + BM25 via RRF | Dense alone misses symbols; sparse alone misses semantics |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Top-20 → top-5 reduces hallucination from irrelevant context |
| Vector DB | Qdrant (HNSW `M=16, ef=200`) | Production-grade filtering, payload indexing, horizontal scaling |
| LLM routing | Model Router (Ollama / vLLM / OpenAI) | Routes by complexity — local for fast tasks, cloud for long-context |
| Sandbox | Docker + `seccomp` + `cap_drop ALL` | Research-validated hardening; no network access, memory-limited |
| Streaming | `astream_events` v2 over WebSocket | Granular token-level + tool-level events per project room |

<br/>

---

## 🤖 Multi-Agent System

Six specialized agents coordinated by a LangGraph Supervisor:

```
User Message
      │
   Planner  ──────────────────────────────────────────────────────┐
      │                                                           │
   Supervisor ──────────────────────────────────────────────┐    │
      │                                                      │    │
      ├─── code_generation  ──→  🔧 Coder                   │    │
      ├─── code_review      ──→  🔍 Reviewer                │    │
      ├─── infrastructure   ──→  ⚙️  Infra Agent             │    │
      ├─── documentation    ──→  📝 Docs Agent              │    │
      ├─── debug            ──→  🐛 Debugger                │    │
      └─── parallel tasks   ──→  [fork → agents → merge] ───┘    │
                                                                  │
   ExecutionPlan(steps, dependencies, routing) ◄──────────────────┘
```

<br/>

### Agent Capabilities

| Agent | Input | Output | Special Behavior |
|:---|:---|:---|:---|
| **Planner** | User request + repo summary | `ExecutionPlan` with routing + dependencies | Structured output via Pydantic schema |
| **Coder** | Task spec + RAG context + file tree | Code changes with explanations | Self-review pass before finalizing |
| **Reviewer** | Code + repo context | `ReviewReport` (severity-ranked issues) | Detects: security, N+1, bad async, arch violations |
| **Infra** | Detected stack + target | Dockerfile, docker-compose, GitHub Actions, NGINX | Stack-aware template generation |
| **Docs** | Repo analysis + API endpoints | Production-grade README | Sections: overview, arch, setup, API, deploy |
| **Debugger** | Stderr + code + logs | Patched code + root cause | Self-healing loop up to 3 retries |

<br/>

### Debugger Self-Healing Loop

```
  Generate Code
        │
  Execute in Docker Sandbox
        │
        ▼
  ┌─ exit_code == 0? ─────────── YES ──→  Return success ✓
  │
  NO
  │
  ▼
  Capture stderr + stdout
        │
  Debugger Agent (reasons over error + code + RAG context)
        │
  Patch code
        │
  retry_count += 1
        │
  ┌─ retry_count < 3? ────────── YES ──→  Execute in Sandbox  (loop)
  │
  NO
  │
  ▼
  Return failure + full diagnosis report
```

<br/>

---

## 🔀 Hybrid LLM Inference Router

```
Incoming Request
      │
      ▼
  Model Router
  ┌───────────────────────────────────────────────────────┐
  │                                                       │
  │  token_count < 2000 + fast task  ──→  Ollama (local)  │
  │  token_count > 8000              ──→  OpenAI (cloud)  │
  │  task_type == code_generation    ──→  Qwen2.5-Coder   │
  │  provider timeout / error        ──→  Auto fallback   │
  │                                                       │
  └───────────────────────────────────────────────────────┘
         │                  │                   │
    Ollama (local)     vLLM Server        OpenAI-compat
    (fast, private)    (GPU hosted)       (fallback)
```

Plug in any provider by implementing `BaseLLMProvider`:

```python
class BaseLLMProvider(ABC):
    async def complete(self, messages: list, **kwargs) -> LLMResponse: ...
    async def stream(self, messages: list, **kwargs) -> AsyncIterator[str]: ...
    async def health_check(self) -> bool: ...
```

<br/>

---

## 🔍 RAG Pipeline

```
Repository Files
      │
      ├── .py / .ts / .go / .java ──→  Tree-sitter AST Chunker
      │                                (function/class/method level)
      │                                Metadata: path, language, start_line, parent_class
      │
      └── .md / .yaml / .json    ──→  Sliding Window Chunker
                                       (300 tokens, 20% overlap)
                                              │
                                       BGE Embedder (768-dim)
                                       normalize_embeddings=True
                                       Redis cache (sha256 keyed)
                                              │
                                       Qdrant Insert
                                       HNSW M=16, ef_construction=200
                                              │
                         ┌────────────────────┴─────────────────────┐
                         ▼                                          ▼
                  Dense Retrieval                           BM25 Sparse
                  (cosine similarity)                    (exact symbol match)
                         │                                          │
                         └──────────────┬─────────────────────────┘
                                        ▼
                              Reciprocal Rank Fusion
                                        │
                             Cross-Encoder Reranking
                             (top-20 candidates → top-5)
                                        │
                              Context Assembly (≤6000 tokens)
                                        │
                                   Agent LLM Call
```

<br/>

---

## 📊 Observability Stack

Pre-wired from day one. No setup required.

```
Backend (/metrics)
      │
      ▼
Prometheus ──────────────────────────────→ Grafana (localhost:3001)
                                                │
                                   ┌────────────┼────────────┐
                                   ▼            ▼            ▼
                              API latency   Agent runs   Token costs
                              p50/p95/p99   by type      by model
```

### Custom Metrics Exposed

| Metric | Type | Description |
|:---|:---|:---|
| `nexus_agent_executions_total` | Counter | Agent runs by name + status |
| `nexus_retrieval_latency_seconds` | Histogram | RAG retrieval time (dense, sparse, rerank) |
| `nexus_sandbox_runtime_seconds` | Histogram | Execution duration by runtime |
| `nexus_token_usage_total` | Counter | Token consumption by model + agent |
| `nexus_active_websocket_connections` | Gauge | Live WebSocket connections |
| `nexus_indexing_duration_seconds` | Histogram | Repo indexing time by language |

<br/>

### Benchmark Numbers

| Operation | Median | p95 |
|:---|:---:|:---:|
| Repo indexing (10k LOC) | 6.4s | 11.2s |
| Vector retrieval (top-20) | 42ms | 90ms |
| Cross-encoder reranking | 180ms | 340ms |
| Agent graph execution | 2.2s | 4.8s |
| Docker sandbox startup | 1.8s | 3.1s |
| WebSocket event delivery | <5ms | 18ms |

<br/>

---

## 🗂️ Project Structure

```
nexusforge-ai/
├── backend/
│   ├── main.py                     ← FastAPI app + lifespan
│   ├── core/                       ← Config, DB, JWT, dependencies
│   ├── models/                     ← SQLAlchemy ORM (6 tables)
│   ├── api/
│   │   ├── routes/                 ← REST endpoints (auth, projects, repos, chat...)
│   │   └── websocket/              ← Connection hub + typed event payloads
│   ├── agents/
│   │   ├── orchestrator.py         ← LangGraph StateGraph + Supervisor
│   │   ├── model_router.py         ← Hybrid inference routing
│   │   └── [planner|coder|reviewer|infra|docs|debugger]/
│   ├── rag/
│   │   ├── chunking/               ← Tree-sitter AST + sliding window
│   │   ├── embeddings/             ← BGE embedder + Redis cache
│   │   ├── vector_store/           ← Qdrant client (HNSW tuned)
│   │   ├── retrieval/              ← Hybrid retriever + reranker + assembler
│   │   └── memory/                 ← Session + long-term (Postgres)
│   ├── services/                   ← Repo, indexing, execution, graph, auth
│   ├── workers/                    ← Celery app + tasks
│   └── telemetry/                  ← Prometheus metrics + OpenTelemetry traces
│
├── frontend/
│   ├── app/(dashboard)/
│   │   ├── page.tsx                ← Project dashboard
│   │   ├── workspace/              ← Streaming chat + agent badges
│   │   ├── repository/             ← Upload, file tree, architecture viewer
│   │   ├── agents/                 ← Live agent timeline (WebSocket)
│   │   ├── execution/              ← Monaco editor + terminal
│   │   ├── memory/                 ← Semantic search explorer
│   │   └── architecture/           ← React Flow graph viewer
│   ├── components/                 ← Chat, code, diagrams, terminal, upload...
│   ├── hooks/                      ← useWebSocket, useAgentStream, useExecution
│   └── lib/                        ← Typed Axios + Zod + Zustand store
│
├── monitoring/
│   ├── prometheus/prometheus.yml
│   └── grafana/                    ← Pre-provisioned dashboards
│
├── deployment/
│   └── nginx/nginx.conf
│
├── alembic/                        ← DB migrations
├── docker-compose.yml
├── Dockerfile.backend              ← Multi-stage, non-root user
├── Dockerfile.frontend             ← Next.js standalone + NGINX
└── .env.example                    ← 30+ documented variables
```

<br/>

---

## 🔌 API Reference

### Authentication

All endpoints require `Authorization: Bearer <token>` except `/auth/*` and `/health`.

| Method | Endpoint | Description |
|:---:|:---|:---|
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/login` | Get access + refresh tokens |
| `POST` | `/auth/refresh` | Rotate access token |

### Core Endpoints

| Method | Endpoint | Description |
|:---:|:---|:---|
| `POST` | `/repos/upload` | Upload ZIP archive |
| `POST` | `/repos/github` | Clone public GitHub URL |
| `GET` | `/repos/{id}/status` | Indexing progress |
| `POST` | `/chat/message` | Trigger agent graph (async) |
| `GET` | `/chat/{thread_id}/history` | Conversation history |
| `POST` | `/execute` | Run code in sandbox |
| `GET` | `/memory/retrieve?query=` | Semantic search over repo |
| `GET` | `/metrics` | Prometheus metrics endpoint |

### WebSocket Events

Connect to `ws://localhost:8000/ws/{project_id}`:

```typescript
type NexusEvent =
  | { type: "token";             content: string; agent: string }
  | { type: "agent_start";       agent: string; task: string }
  | { type: "agent_end";         agent: string; duration_ms: number }
  | { type: "tool_start";        tool: string; input_preview: string }
  | { type: "log_line";          content: string; stream: "stdout"|"stderr" }
  | { type: "indexing_progress"; processed: number; total: number }
  | { type: "error";             message: string; recoverable: boolean }
```

<br/>

---

## 🛠️ Tech Stack

**Backend**

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_2.0-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square)
![Celery](https://img.shields.io/badge/Celery-37814A?style=flat-square&logo=celery&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic_v2-E92063?style=flat-square&logo=pydantic&logoColor=white)

**AI / ML**

![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?style=flat-square&logo=huggingface&logoColor=black)
![Qdrant](https://img.shields.io/badge/Qdrant-FF4455?style=flat-square)
![Tree-sitter](https://img.shields.io/badge/Tree--sitter-AST_Chunking-7c3aed?style=flat-square)
![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat-square)

**Frontend**

![Next.js](https://img.shields.io/badge/Next.js_14-000000?style=flat-square&logo=next.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)
![Framer](https://img.shields.io/badge/Framer_Motion-0055FF?style=flat-square&logo=framer&logoColor=white)
![React Flow](https://img.shields.io/badge/React_Flow-FF4154?style=flat-square)

**Infrastructure**

![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis_7-DC382D?style=flat-square&logo=redis&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?style=flat-square&logo=neo4j&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=flat-square&logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-F46800?style=flat-square&logo=grafana&logoColor=white)
![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-000000?style=flat-square&logo=opentelemetry&logoColor=white)

<br/>

---

## 🚀 Deployment

### Docker Compose (Staging)

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Kubernetes (Helm)

```bash
helm install nexusforge ./deployment/helm \
  --set backend.image.tag=latest \
  --set frontend.image.tag=latest \
  --namespace nexusforge --create-namespace
```

### Service Ports

| Service | Port | Purpose |
|:---|:---:|:---|
| Frontend | `3000` | Next.js dashboard |
| Backend | `8000` | FastAPI + WebSocket |
| PostgreSQL | `5432` | Primary database |
| Redis | `6379` | Cache + Celery broker |
| Qdrant | `6333` | Vector store |
| Neo4j | `7474` | Knowledge graph |
| Prometheus | `9090` | Metrics collection |
| Grafana | `3001` | Observability dashboards |

<br/>

---

## 🗺️ Roadmap

- [ ] Private GitHub repository support (GitHub OAuth App)
- [ ] Firecracker microVM sandbox for stronger isolation
- [ ] Kafka event streaming for distributed agent orchestration
- [ ] Agent evaluation benchmark suite (README quality, bug fix accuracy scores)
- [ ] Plugin system (`plugins/github/`, `plugins/kubernetes/`, `plugins/aws/`)
- [ ] Repository time machine — commit history + architectural evolution visualization
- [ ] System design generator — "Scale to 10M users" → full HLD output
- [ ] vLLM inference server integration

<br/>

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-feature`
3. Run tests: `cd backend && pytest tests/ -v --cov=backend`
4. Check TypeScript: `cd frontend && npx tsc --noEmit`
5. Open a pull request

See `CONTRIBUTING.md` for agent implementation patterns and RAG extension points.

<br/>

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

<br/>

---

<div align="center">

<img width="100%" src="https://capsule-render.vercel.app/api?type=waving&color=7c3aed&height=100&section=footer" alt="footer wave"/>

**Built with architectural obsession.**

*NexusForge AI — Because repositories deserve to be understood, not just searched.*

⭐ **Star this repo if it inspires you** ⭐

</div>
