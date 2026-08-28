"""
NexusForge AI — Intelligent Model Router
Routes LLM calls by task type, context length, cost, and provider availability.

Architecture:
  TaskType → ModelConfig → Provider (Ollama / vLLM / OpenAI)

Features:
- Per-task model specialization (coding model for code, planning model for planning)
- Automatic long-context fallback to cloud when local window exceeded
- LiteLLM Router for multi-provider load balancing and failover
- Tracks usage per model for cost dashboard
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import structlog

log = structlog.get_logger()


class TaskType(str, Enum):
    PLANNING = "planning"   # lightweight reasoning → fast local model
    CODEGEN = "codegen"     # code generation → specialized coder model
    REVIEW = "review"       # code review → same as coder
    DOCS = "docs"           # documentation → general instruction-following
    DEBUG = "debug"         # debugging → coder model
    LONG_CTX = "long_ctx"   # > local context window → cloud fallback
    GENERAL = "general"     # catch-all


@dataclass
class ModelConfig:
    alias: str
    provider: str           # "ollama", "vllm", "openai"
    model_name: str
    task_type: TaskType
    context_window: int = 8192
    cost_per_1m_input: float = 0.0
    cost_per_1m_output: float = 0.0
    is_local: bool = True


class ModelRouter:
    """
    Routes each LLM request to the most appropriate model/provider.

    Routing priority:
    1. Context length overflow → long_ctx model (cloud)
    2. vLLM available + codegen/debug task → vLLM (fast local GPU)
    3. Task type → task-specific Ollama model
    4. Fallback → general Ollama model
    """

    # Task type → LiteLLM model alias mapping
    TASK_ALIAS: dict[TaskType, str] = {
        TaskType.PLANNING: "planning",
        TaskType.CODEGEN: "codegen",
        TaskType.REVIEW: "review",
        TaskType.DOCS: "docs",
        TaskType.DEBUG: "codegen",   # reuse coder
        TaskType.GENERAL: "general",
        TaskType.LONG_CTX: "long_ctx",
    }

    _instance: Optional["ModelRouter"] = None

    def __init__(self) -> None:
        from backend.core.config import settings
        self._s = settings
        self._router = self._build_router()
        log.info(
            "model_router.initialized",
            router_enabled=settings.MODEL_ROUTER_ENABLED,
            ollama=settings.OLLAMA_BASE_URL,
            vllm=settings.VLLM_BASE_URL or "disabled",
            openai=bool(settings.OPENAI_API_KEY),
        )

    # ─── LiteLLM Router ──────────────────────────────────────────────────────

    def _build_router(self) -> Any:
        """Build LiteLLM Router with all configured providers."""
        try:
            from litellm import Router

            s = self._s
            model_list: list[dict] = []

            # ── Ollama models (local) ──────────────────────────────────────
            ollama_models = {
                "codegen": s.DEFAULT_CODER_MODEL,
                "review": s.DEFAULT_REVIEWER_MODEL,
                "planning": s.DEFAULT_PLANNER_MODEL,
                "docs": s.DEFAULT_PLANNER_MODEL,
                "general": s.OLLAMA_MODEL,
            }
            for alias, model in ollama_models.items():
                model_list.append({
                    "model_name": alias,
                    "litellm_params": {
                        "model": f"ollama/{model}",
                        "api_base": s.OLLAMA_BASE_URL,
                    }
                })

            # ── vLLM pool for codegen (fast GPU) ──────────────────────────
            if s.VLLM_BASE_URL:
                model_list.append({
                    "model_name": "codegen",   # parallel pool entry
                    "litellm_params": {
                        "model": "openai/vllm-codegen",
                        "api_base": s.VLLM_BASE_URL,
                        "api_key": "placeholder",   # vLLM ignores key
                    }
                })

            # ── Long context: OpenAI if key present, else local ────────────
            if s.OPENAI_API_KEY:
                model_list.append({
                    "model_name": "long_ctx",
                    "litellm_params": {
                        "model": s.DEFAULT_LONG_CONTEXT_MODEL,
                        "api_key": s.OPENAI_API_KEY,
                    }
                })
            else:
                model_list.append({
                    "model_name": "long_ctx",
                    "litellm_params": {
                        "model": f"ollama/{s.OLLAMA_MODEL}",
                        "api_base": s.OLLAMA_BASE_URL,
                    }
                })

            return Router(
                model_list=model_list,
                routing_strategy="latency-based-routing",
                fallbacks=[
                    {"codegen": ["long_ctx"]},
                    {"planning": ["general"]},
                    {"review": ["codegen"]},
                ],
                num_retries=2,
                allowed_fails=3,
                set_verbose=False,
            )

        except ImportError:
            log.warning(
                "model_router.litellm_not_installed",
                hint="pip install litellm",
            )
            return None
        except Exception as e:
            log.warning("model_router.router_build_failed", error=str(e))
            return None

    # ─── Public API ──────────────────────────────────────────────────────────

    def route(self, task_type: TaskType, context_length: int = 0) -> str:
        """Return the LiteLLM model alias to use for this task."""
        s = self._s
        # Auto-upgrade to long_ctx if local window exceeded
        if context_length > s.LOCAL_CONTEXT_WINDOW_TOKENS:
            log.info(
                "model_router.long_ctx_upgrade",
                context_length=context_length,
                limit=s.LOCAL_CONTEXT_WINDOW_TOKENS,
            )
            return "long_ctx"
        alias = self.TASK_ALIAS.get(task_type, "general")
        log.info("model_router.routed", task_type=task_type.value, alias=alias)
        return alias

    def get_langchain_llm(self, task_type: TaskType, context_length: int = 0):
        """
        Get a LangChain-compatible chat model for direct use in agents.
        Falls back gracefully if specific providers are unavailable.
        """
        from langchain_ollama import ChatOllama

        s = self._s

        # If Gemini key is provided, prefer it for EVERYTHING to ensure it works seamlessly
        if s.OPENAI_API_KEY:
            try:
                from langchain_openai import ChatOpenAI
                log.info("model_router.using_openai", model=s.OPENAI_MODEL)
                return ChatOpenAI(
                    model=s.OPENAI_MODEL,
                    api_key=s.OPENAI_API_KEY,
                    base_url=s.OPENAI_BASE_URL if s.OPENAI_BASE_URL else None,
                    temperature=0.05 if task_type in (TaskType.CODEGEN, TaskType.DEBUG) else 0.2,
                )
            except Exception as e:
                log.warning("model_router.openai_fallback_failed", error=str(e))

        # Cloud fallback for long context (OpenAI)
        if context_length > s.LOCAL_CONTEXT_WINDOW_TOKENS and s.OPENAI_API_KEY:
            try:
                from langchain_openai import ChatOpenAI
                log.info("model_router.using_openai_long_ctx", model=s.DEFAULT_LONG_CONTEXT_MODEL)
                return ChatOpenAI(
                    model=s.DEFAULT_LONG_CONTEXT_MODEL,
                    api_key=s.OPENAI_API_KEY,
                    streaming=True,
                    temperature=0.1,
                )
            except Exception as e:
                log.warning("model_router.openai_fallback_failed", error=str(e))

        # vLLM for codegen tasks (fast GPU inference)
        if s.VLLM_BASE_URL and task_type in (TaskType.CODEGEN, TaskType.DEBUG):
            try:
                from langchain_openai import ChatOpenAI
                log.info("model_router.using_vllm", task=task_type.value)
                return ChatOpenAI(
                    model="codegen",
                    base_url=s.VLLM_BASE_URL,
                    api_key="placeholder",
                    streaming=True,
                    temperature=0.05,
                )
            except Exception as e:
                log.warning("model_router.vllm_failed", error=str(e))

        # Task-specific Ollama model
        model_map = {
            TaskType.CODEGEN:  s.DEFAULT_CODER_MODEL,
            TaskType.DEBUG:    s.DEFAULT_CODER_MODEL,
            TaskType.REVIEW:   s.DEFAULT_REVIEWER_MODEL,
            TaskType.PLANNING: s.DEFAULT_PLANNER_MODEL,
            TaskType.DOCS:     s.DEFAULT_PLANNER_MODEL,
            TaskType.GENERAL:  s.OLLAMA_MODEL,
            TaskType.LONG_CTX: s.OLLAMA_MODEL,
        }
        model = model_map.get(task_type, s.OLLAMA_MODEL)
        temperature = 0.05 if task_type in (TaskType.CODEGEN, TaskType.DEBUG) else 0.2

        log.info(
            "model_router.using_ollama",
            task=task_type.value,
            model=model,
            temperature=temperature,
        )
        return ChatOllama(
            model=model,
            base_url=s.OLLAMA_BASE_URL,
            temperature=temperature,
        )

    def get_routing_info(self, task_type: TaskType, context_length: int = 0) -> dict:
        """Return routing decision metadata for the cost widget."""
        alias = self.route(task_type, context_length)
        s = self._s
        provider_map = {
            "long_ctx": "openai" if s.OPENAI_API_KEY else "ollama",
            "codegen": "vllm" if s.VLLM_BASE_URL else "ollama",
        }
        provider = provider_map.get(alias, "ollama")
        return {
            "task_type": task_type.value,
            "alias": alias,
            "provider": provider,
            "reason": f"Task={task_type.value}, ctx={context_length} tokens",
        }

    @classmethod
    def get_instance(cls) -> "ModelRouter":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
