"""
NexusForge AI — System Design Agent
Translates high-level scaling requirements into detailed system architectures (HLD).
"""
import time
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent

log = structlog.get_logger()

class SysDesignAgent(BaseAgent):
    AGENT_NAME = "sysdesign"
    AGENT_ICON = "🏗️"

    def __init__(self):
        super().__init__()
        self._system_prompt = (
            "You are an expert Staff/Principal Infrastructure Architect. "
            "Your task is to take architecture or scaling requirements and produce a concise, "
            "high-impact Technical Design / Architecture document. "
            "Include:\n"
            "1. Architectural Concept & Core Components\n"
            "2. Mermaid diagram illustrating the topology / flow\n"
            "3. Concrete implementation code or schema example\n"
            "4. Key trade-offs and recommendations\n"
            "Be direct, highly technical, and concise. Format in GitHub-flavored Markdown."
        )

    async def run(self, state: dict) -> dict:
        start_time = time.perf_counter()
        query = state.get("current_task") or state.get("task_description", "")

        log.info("sysdesign_agent.started", task=query[:50])

        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=f"Requirement: {query}\n\nProvide the complete System Design HLD:")
        ]

        try:
            response = await self._invoke_llm(messages)
            content = response.content if hasattr(response, "content") else str(response)

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit logs (conceptual for now, to integrate with existing telemetry)
            log.info("sysdesign_agent.completed", duration_ms=duration_ms)

            history = state.get("agent_history", [])
            history.append(self.AGENT_NAME)

            return {
                "agent_history": history,
                "sysdesign_result": content,
                "messages": state.get("messages", []) + [response]
            }
        except Exception as e:
            log.error("sysdesign_agent.failed", error=str(e))
            return {"error": f"SysDesign agent failed: {e}"}

