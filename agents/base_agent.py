"""
NexusForge AI — Base Agent
Abstract base class for all 6 specialized agents.
Provides: LLM binding (Ollama + OpenAI fallback), RAG injection,
WebSocket event emission, retry logic, and token tracking.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from backend.core.config import settings

log = structlog.get_logger()

def _is_retryable_llm_error(e: Exception) -> bool:
    """Return False if the exception is a 429/quota error, bypassing tenacity retries."""
    err_msg = str(e).lower()
    if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg or "prepayment" in err_msg:
        return False
    return True

class BaseAgent(ABC):
    """
    Abstract base for all NexusForge agents.
    Subclasses implement `run(state) -> dict`.
    """

    AGENT_NAME: str = "base"
    AGENT_ICON: str = "🤖"
    SYSTEM_PROMPT: str = "You are a helpful AI assistant."

    def __init__(self):
        self._llm: Optional[BaseChatModel] = None

    def _get_llm(self) -> BaseChatModel:
        """Get LLM — Ollama primary, OpenAI fallback."""
        if self._llm is not None:
            return self._llm

        # Try Ollama first
        try:
            from langchain_ollama import ChatOllama
            llm = ChatOllama(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                temperature=0.1,
                num_ctx=8192,
                timeout=settings.OLLAMA_TIMEOUT,
                streaming=True,  # REQUIRED for token streaming
            )
            # Verify connection
            llm.invoke("ping")
            self._llm = llm
            log.info("agent.llm_connected", agent=self.AGENT_NAME, provider="ollama", model=settings.OLLAMA_MODEL)
            return self._llm
        except Exception as e:
            log.warning("agent.ollama_unavailable", agent=self.AGENT_NAME, error=str(e))

        # Fallback to OpenAI-compatible API
        if settings.OPENAI_API_KEY and "gemini" in settings.OPENAI_MODEL.lower():
            from langchain_google_genai import ChatGoogleGenerativeAI

            self._llm = ChatGoogleGenerativeAI(
                model=settings.OPENAI_MODEL,
                google_api_key=settings.OPENAI_API_KEY,
                temperature=0.1,
            )
            log.info("agent.llm_connected", agent=self.AGENT_NAME, provider="gemini", model=settings.OPENAI_MODEL)
            return self._llm

        if settings.OPENAI_API_KEY and settings.USE_OPENAI_FALLBACK:
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                model=settings.OPENAI_MODEL,
                temperature=0.1,
                streaming=True,
            )
            log.info("agent.llm_connected", agent=self.AGENT_NAME, provider="openai", model=settings.OPENAI_MODEL)
            return self._llm

        raise RuntimeError(
            f"No LLM available for agent {self.AGENT_NAME}. "
            "Configure OLLAMA_BASE_URL or OPENAI_API_KEY."
        )

    def _build_context_prompt(self, state: dict) -> str:
        """Build the context section of the prompt from RAG results."""
        context = state.get("retrieved_context", "")
        sources = state.get("context_sources", [])

        if not context:
            return ""

        sources_str = "\n".join(f"  - {s}" for s in sources[:10]) if sources else "  - (no source info)"
        return f"""
## Retrieved Code Context

The following code was retrieved from the repository as relevant context:

```
{context[:4000]}
```

Sources:
{sources_str}

---
"""

    def _clean_llm_output(self, text: str) -> str:
        """Clean conversational filler while preserving all code blocks and markdown."""
        if not text:
            return ""
        lines = text.splitlines()
        cleaned_lines = []
        for line in lines:
            # Strip trivial conversational filler only if at the very start
            if not cleaned_lines and line.lower().startswith("here is the"):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_is_retryable_llm_error),
        reraise=True,
    )
    async def _do_invoke_llm(self, messages: list, structured_output_schema=None) -> Any:
        """Core LLM invocation with tenacity retry logic (bypassed on 429)."""
        llm = self._get_llm()

        if structured_output_schema:
            llm_with_schema = llm.with_structured_output(structured_output_schema)
            return await llm_with_schema.ainvoke(messages)

        resp = await llm.ainvoke(messages)
        content = resp.content if hasattr(resp, "content") else str(resp)
        if isinstance(content, list):
             text_blocks = [b.get("text", "") for b in content if isinstance(b, dict) and "text" in b]
             content = "".join(text_blocks) if text_blocks else str(content)
        cleaned_content = self._clean_llm_output(content)
        if hasattr(resp, "content"):
            resp.content = cleaned_content
        return resp

    async def _invoke_llm(self, messages: list, structured_output_schema=None) -> Any:
        """Wrapper to invoke LLM with structured or unstructured output, propagating real errors."""
        try:
            return await self._do_invoke_llm(messages, structured_output_schema)
        except Exception as e:
            log.error("llm.invocation_failed", agent=self.name, error=str(e))
            raise RuntimeError(f"LLM invocation failed for agent '{self.name}': {e}") from e

    def _emit_agent_start(self, state: dict, action: str) -> dict:
        """Return agent start event payload for WebSocket broadcast."""
        return {
            "type": "agent_start",
            "agent_name": self.AGENT_NAME,
            "icon": self.AGENT_ICON,
            "action": action,
            "thread_id": state.get("thread_id"),
        }

    def _emit_agent_end(self, state: dict, action: str, summary: str, duration_ms: int) -> dict:
        """Return agent end event payload."""
        return {
            "type": "agent_end",
            "agent_name": self.AGENT_NAME,
            "action": action,
            "output_summary": summary,
            "duration_ms": duration_ms,
            "thread_id": state.get("thread_id"),
        }

    def _log_to_db_payload(self, state: dict, action: str, input_summary: str, output_summary: str, duration_ms: int) -> dict:
        """Build the payload for AgentLog database entry."""
        return {
            "project_id": state.get("project_id"),
            "thread_id": state.get("thread_id"),
            "agent_name": self.AGENT_NAME,
            "action": action,
            "input_summary": input_summary[:500] if input_summary else None,
            "output_summary": output_summary[:500] if output_summary else None,
            "duration_ms": duration_ms,
        }

    @abstractmethod
    async def run(self, state: dict) -> dict:
        """
        Execute agent logic. Returns a dict of state updates.
        Must update `agent_history` with self.AGENT_NAME.
        """
        ...
