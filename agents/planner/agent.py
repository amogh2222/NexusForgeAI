"""NexusForge AI — Planner Agent"""
import time

import structlog
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel

from agents.base_agent import BaseAgent

log = structlog.get_logger()


class ExecutionStep(BaseModel):
    step_number: int
    agent: str
    task: str
    description: str
    dependencies: list[int] = []


class ExecutionPlan(BaseModel):
    title: str
    summary: str
    steps: list[ExecutionStep]
    estimated_complexity: str  # "simple" | "moderate" | "complex"
    first_agent: str


class PlannerAgent(BaseAgent):
    """
    Breaks user requests into structured execution plans.
    Determines which agents to invoke and in what order.
    """

    AGENT_NAME = "planner"
    AGENT_ICON = "📋"
    SYSTEM_PROMPT = """You are the Planner Agent for NexusForge AI, an enterprise AI engineering platform.

Your role is to analyze user requests and create structured execution plans that coordinate specialized agents:
- **coder**: Code generation, modification, feature implementation
- **reviewer**: Code review, security audit, performance analysis
- **infra**: Dockerfile, docker-compose, CI/CD, Kubernetes configs
- **docs**: README generation, architecture documentation, onboarding guides
- **debugger**: Bug fixing, error analysis, stack trace investigation

When planning, consider:
1. Task dependencies (some agents need output from others)
2. The repository context provided
3. The complexity of the request
4. Which specialized agents are most appropriate

Always output a structured plan with clear, actionable steps."""

    async def run(self, state: dict) -> dict:
        start_time = time.time()
        task = state.get("current_task", "")
        context_prompt = self._build_context_prompt(state)

        log.info("planner.running", task=task[:100])

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""
{context_prompt}

## User Request
{task}

## Repository Info
{state.get('repository_id', 'No repository attached')}

Please create a structured execution plan for this request.
"""),
        ]

        try:
            plan = await self._invoke_llm(messages, structured_output_schema=ExecutionPlan)
            duration_ms = int((time.time() - start_time) * 1000)

            log.info("planner.complete",
                     steps=len(plan.steps),
                     complexity=plan.estimated_complexity,
                     duration_ms=duration_ms)

            return {
                "plan": plan.model_dump(),
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
                "messages": [{"role": "agent", "agent": self.AGENT_NAME, "content": f"Created execution plan: {plan.title}"}],
            }

        except Exception as e:
            log.error("planner.error", error=str(e))
            return {
                "plan": {"steps": [], "first_agent": "coder", "summary": task},
                "error": str(e),
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
            }
