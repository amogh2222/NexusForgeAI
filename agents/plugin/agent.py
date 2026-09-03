"""NexusForge AI — Plugin Agent"""
import time
import structlog
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from agents.base_agent import BaseAgent

log = structlog.get_logger()


class PluginAgent(BaseAgent):
    """
    Executes actions on external systems using the PluginRegistry tools.
    """

    AGENT_NAME = "plugin"
    AGENT_ICON = "🔌"
    SYSTEM_PROMPT = """You are the Plugin Agent for NexusForge AI.
You have access to several external systems via plugins (e.g., GitHub, Kubernetes).
Use the provided tools to interact with these systems and accomplish the user's task.
If you need to list pull requests, create issues, check kubernetes pods, etc., use the tools.
Once you have the information, summarize it clearly for the user.
"""

    async def run(self, state: dict) -> dict:
        start_time = time.time()
        task = state.get("current_task", "")
        log.info("plugin.running", task=task[:100])

        self._emit_agent_start(state, "Executing plugin tools")

        from plugins.registry import PluginRegistry
        registry = PluginRegistry.get_instance()
        tools = registry.get_langchain_tools()

        if not tools:
            summary = "No plugins are currently loaded or configured."
            self._emit_agent_end(state, "Plugin Execution Failed", summary, int((time.time() - start_time) * 1000))
            return {"messages": [HumanMessage(content=summary)]}

        llm = self._get_llm()

        # create_react_agent manages the tool calling loop
        agent_executor = create_react_agent(llm, tools, prompt=self.SYSTEM_PROMPT)

        # We don't want to pass ALL messages to the tool agent, just the task, to save context
        messages = [HumanMessage(content=task)]

        try:
            result = await agent_executor.ainvoke({"messages": messages})
            final_message = result["messages"][-1].content
        except Exception as e:
            log.error("plugin.execution_failed", error=str(e))
            final_message = f"Error executing plugin tools: {e}"

        duration_ms = int((time.time() - start_time) * 1000)
        log.info("plugin.complete", duration_ms=duration_ms)

        self._emit_agent_end(state, "Plugin Execution Complete", final_message[:100], duration_ms)

        # Log to DB
        from backend.core.database import AsyncSessionLocal
        from backend.models import AgentLog
        try:
            async with AsyncSessionLocal() as db:
                db.add(AgentLog(**self._log_to_db_payload(
                    state, "execute_plugins", task, final_message, duration_ms
                )))
                await db.commit()
        except Exception as e:
            log.warning("plugin.db_log_failed", error=str(e))

        return {
            "messages": [HumanMessage(content=final_message)],
            "agent_history": state.get("agent_history", []) + [self.AGENT_NAME]
        }
