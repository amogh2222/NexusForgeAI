"""
NexusForge AI — Repository Time Machine Agent
Analyzes git commit history to detect architectural drift and visualize evolution.
"""
import time
import subprocess
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent

log = structlog.get_logger()

class TimeMachineAgent(BaseAgent):
    AGENT_NAME = "time_machine"
    AGENT_ICON = "⏳"

    def __init__(self):
        super().__init__()
        self._system_prompt = (
            "You are an expert Software Archaeologist. "
            "You are given a summary of the repository's git commit history. "
            "Analyze the timeline and describe the architectural evolution, identifying major shifts, "
            "tech debt accumulation, and significant refactors. "
            "Output your analysis in a structured Markdown report with a Mermaid timeline."
        )

    def _get_git_history(self, limit: int = 50) -> str:
        """Extracts the git log from the current directory."""
        try:
            result = subprocess.run(
                ["git", "log", "-n", str(limit), "--oneline", "--stat"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout if result.returncode == 0 else "Git history unavailable."
        except Exception as e:
            log.warning("time_machine.git_failed", error=str(e))
            return f"Git error: {e}"

    async def run(self, state: dict) -> dict:
        start_time = time.perf_counter()

        log.info("time_machine_agent.started")

        history_text = self._get_git_history(limit=state.get("history_limit", 50))

        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=f"Git History Summary:\n```text\n{history_text[:8000]}\n```")
        ]

        try:
            response = await self._invoke_llm(messages)
            content = response.content if hasattr(response, "content") else str(response)

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            log.info("time_machine_agent.completed", duration_ms=duration_ms)

            history = state.get("agent_history", [])
            history.append(self.AGENT_NAME)

            return {
                "agent_history": history,
                "time_machine_result": content,
                "messages": [response]
            }
        except Exception as e:
            log.error("time_machine_agent.failed", error=str(e))
            return {"error": f"Time Machine agent failed: {e}"}

