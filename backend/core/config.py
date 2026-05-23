"""
NexusForge AI — Application Configuration
Pydantic BaseSettings with full env var loading.
"""
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── App ──────────────────────────────────────────────────
    APP_NAME: str = "NexusForge AI"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "info"
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://nexusforge.ai",
    ]

    # ─── Security ─────────────────────────────────────────────
    SECRET_KEY: str = "change-this-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ─── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://nexusforge:nexusforge_secret@localhost:5432/nexusforge"
    DATABASE_SYNC_URL: str = "postgresql://nexusforge:nexusforge_secret@localhost:5432/nexusforge"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ─── Redis ────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600

    # ─── Qdrant Vector Store (production-grade) ────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_PREFIX: str = "nexusforge"
    QDRANT_USE_GRPC: bool = False

    # ─── Neo4j Knowledge Graph ────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "nexusforge_graph"
    NEO4J_DATABASE: str = "neo4j"

    # ─── Ollama ───────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT: int = 120

    # ─── Intelligent Model Router ──────────────────────────────
    MODEL_ROUTER_ENABLED: bool = True
    VLLM_BASE_URL: Optional[str] = None
    DEFAULT_PLANNER_MODEL: str = "qwen2.5-coder:7b"
    DEFAULT_CODER_MODEL: str = "qwen2.5-coder:7b"
    DEFAULT_REVIEWER_MODEL: str = "qwen2.5-coder:7b"
    DEFAULT_LONG_CONTEXT_MODEL: str = "gpt-4o-mini"
    LOCAL_CONTEXT_WINDOW_TOKENS: int = 8192

    # ─── OpenAI Fallback ──────────────────────────────────────
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    USE_OPENAI_FALLBACK: bool = True

    # ─── Embeddings ───────────────────────────────────────────
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_MAX_SEQ_LENGTH: int = 512
    EMBEDDING_QUERY_PREFIX: str = "Represent this sentence for searching relevant passages: "

    # ─── GitHub Integration ───────────────────────────────────
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_PRIVATE_KEY_PATH: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: Optional[str] = None
    GITHUB_REDIRECT_URI: str = "http://localhost:3000/auth/github/callback"

    # ─── File Storage ─────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: List[str] = [".zip", ".tar.gz"]

    # ─── Celery ───────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_MAX_RETRIES: int = 3
    CELERY_TASK_TIMEOUT: int = 300

    # ─── Sandbox ──────────────────────────────────────────────
    SANDBOX_TIMEOUT_SECONDS: int = 30
    SANDBOX_MAX_MEMORY_MB: int = 256
    SANDBOX_DOCKER_ENABLED: bool = False

    # ─── Cost + Token Tracking ────────────────────────────────
    TRACK_TOKEN_COSTS: bool = True
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "nexusforge-ai"

    # ─── Rate Limiting ────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # ─── Chunking ─────────────────────────────────────────────
    CHUNK_MAX_TOKENS: int = 1024
    CHUNK_MIN_TOKENS: int = 50
    CHUNK_OVERLAP_TOKENS: int = 50

    # ─── Retrieval ────────────────────────────────────────────
    RETRIEVAL_TOP_K: int = 10
    RETRIEVAL_RERANK_TOP_K: int = 5
    CONTEXT_MAX_TOKENS: int = 6000

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def ollama_api_url(self) -> str:
        return f"{self.OLLAMA_BASE_URL}/api"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
