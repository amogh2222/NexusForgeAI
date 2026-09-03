"""NexusForge AI — Coder Agent"""
import time
from typing import List

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from agents.base_agent import BaseAgent

log = structlog.get_logger()


class FileChange(BaseModel):
    path: str
    content: str
    action: str = "create"  # "create" | "modify" | "delete"
    explanation: str = ""
    language: str = ""


class GeneratedCode(BaseModel):
    task_description: str
    files: List[FileChange]
    setup_instructions: str = ""
    dependencies: List[str] = []
    notes: str = ""


class CoderAgent(BaseAgent):
    """
    Generates and modifies production-quality code.
    Uses RAG context for accurate understanding of existing codebase.
    """

    AGENT_NAME = "coder"
    AGENT_ICON = "💻"
    SYSTEM_PROMPT = """You are the Coder Agent for NexusForge AI. You are a senior software engineer who writes clean, production-grade code.

Coding standards you follow:
1. **Type hints**: Always include Python type hints or TypeScript types
2. **Error handling**: Wrap risky operations in try/except with meaningful messages
3. **Documentation**: Add docstrings for public functions/classes
4. **Security**: Never hardcode secrets, validate inputs, handle auth properly
5. **Performance**: Use async where appropriate, avoid N+1 queries, batch operations
6. **Testing**: Write testable code (dependency injection, pure functions where possible)
7. **Compatibility**: Match the existing codebase style from context

When generating code:
- Use the repository context to understand existing patterns, naming conventions, and imports
- Generate complete, working files — not snippets with "..." placeholders
- Include all necessary imports
- Follow the project's existing code style

Output a structured response with complete file contents."""

    async def run(self, state: dict) -> dict:
        start_time = time.time()
        task = state.get("current_task", "")
        plan = state.get("plan", {})
        context_prompt = self._build_context_prompt(state)

        log.info("coder.running", task=task[:100])

        # Extract specific coding task from plan if available
        coding_task = task
        if plan and plan.get("steps"):
            coder_steps = [s for s in plan["steps"] if s.get("agent") == "coder"]
            if coder_steps:
                coding_task = coder_steps[0].get("task", task)

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""
{context_prompt}

## Coding Task
{coding_task}

## Plan Context
{plan.get('summary', 'No plan context available')}

Generate complete, production-quality code for this task.
Follow the patterns and conventions shown in the repository context above.
"""),
        ]

        try:
            result = await self._invoke_llm(messages, structured_output_schema=GeneratedCode)
            duration_ms = int((time.time() - start_time) * 1000)

            log.info("coder.complete",
                     files=len(result.files),
                     duration_ms=duration_ms)

            from langchain_core.messages import AIMessage
            files_summary = "\n".join(f"- `{f.path}` ({f.action}): {f.explanation[:80]}" for f in result.files)

            code_blocks = []
            for f in result.files:
                f_lang = f.language or ("python" if f.path.endswith(".py") else "text")
                code_blocks.append(f"### `{f.path}`\n```{f_lang}\n{f.content}\n```\n{f.explanation}")
            full_code_section = "\n\n".join(code_blocks)

            summary_msg = f"""## Code Generated

**Task**: {result.task_description}

**Files Modified/Created**:
{files_summary}

{full_code_section}

{result.notes}
"""
            if result.dependencies:
                summary_msg += f"\n**Dependencies to install**: `{', '.join(result.dependencies)}`"

            return {
                "generated_code": result.model_dump(),
                "messages": [AIMessage(content=summary_msg)],
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
            }

        except Exception as e:
            log.error("coder.error", error=str(e))
            return {
                "generated_code": {"files": [], "task_description": task},
                "error": str(e),
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
            }
