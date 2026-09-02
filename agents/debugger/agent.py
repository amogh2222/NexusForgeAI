"""NexusForge AI — Debugger Agent"""
import time
from typing import Optional

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from agents.base_agent import BaseAgent

log = structlog.get_logger()


class DebugReport(BaseModel):
    root_cause: str
    error_type: str
    explanation: str
    fixed_code: Optional[str] = None
    fixed_file_path: Optional[str] = None
    additional_fixes: list[str] = []
    confidence: str = "high"  # "high" | "medium" | "low"
    should_retry_execution: bool = False


class DebuggerAgent(BaseAgent):
    """
    Analyzes failures, identifies root causes, and generates fixes.
    Can trigger re-execution after applying fixes.
    """

    AGENT_NAME = "debugger"
    AGENT_ICON = "🐛"
    SYSTEM_PROMPT = """You are the Debugger Agent for NexusForge AI. You are an expert software engineer specializing in debugging complex distributed systems.

Your debugging methodology:
1. **Read the full stack trace** — identify the exact error type and location
2. **Trace the execution path** — understand what led to the failure
3. **Identify the root cause** — not just the symptom, but why it happened
4. **Generate a targeted fix** — minimal change that resolves the root cause
5. **Consider side effects** — will the fix break anything else?

Common patterns you recognize:
- **ImportError/ModuleNotFoundError**: Missing dependencies or incorrect import paths
- **AttributeError**: Wrong attribute access, None values, API changes
- **TypeError**: Wrong argument types, missing args, incompatible versions
- **KeyError/IndexError**: Missing dict keys, list out of bounds, data schema mismatch
- **ConnectionRefusedError**: Service not running, wrong port, firewall issues
- **PermissionError**: File system permissions, insufficient Docker capabilities
- **Async issues**: Missing await, running sync code in async context, event loop conflicts
- **Database errors**: Migration not run, connection pool exhausted, deadlocks

When you output fixed code:
- Provide the complete corrected file, not just the diff
- Explain what was wrong and why the fix works
- Note if related fixes might be needed elsewhere"""

    async def run(self, state: dict) -> dict:
        start_time = time.time()
        task = state.get("current_task", "")
        execution_result = state.get("execution_result", {})
        context_prompt = self._build_context_prompt(state)

        log.info("debugger.running")

        # Gather all error information
        stderr = execution_result.get("stderr", "") if execution_result else ""
        exit_code = execution_result.get("exit_code", -1) if execution_result else -1
        generated_code = state.get("generated_code", {})

        code_context = ""
        if generated_code and generated_code.get("files"):
            for f in generated_code["files"][:3]:
                code_context += f"\n\n### {f.get('path')}\n```{f.get('language', '')}\n{f.get('content', '')}\n```"

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""
{context_prompt}

## Error Information

**Exit Code**: {exit_code}

**Error Output (stderr)**:
```
{stderr[:3000] if stderr else 'No stderr output'}
```

## Failing Code
{code_context or 'Code not available — analyze from stack trace and context.'}

## Task Context
{task}

Analyze this failure, identify the root cause, and provide a complete fix.
"""),
        ]

        try:
            report = await self._invoke_llm(messages, structured_output_schema=DebugReport)
            duration_ms = int((time.time() - start_time) * 1000)

            log.info("debugger.complete",
                     root_cause=report.root_cause[:100],
                     confidence=report.confidence,
                     duration_ms=duration_ms)

            code_section = f"\n### Fixed Code\n```python\n{report.fixed_code}\n```\n" if report.fixed_code else ""
            summary_msg = f"""## Debug Analysis

**Root Cause**: {report.root_cause}

**Error Type**: {report.error_type}

**Explanation**: {report.explanation}

**Confidence**: {report.confidence}
{code_section}
{f"**Fixed File**: `{report.fixed_file_path}`" if report.fixed_file_path else ""}

{chr(10).join(f"- {fix}" for fix in report.additional_fixes) if report.additional_fixes else ""}
"""

            return {
                "debug_report": report.model_dump(),
                "messages": [AIMessage(content=summary_msg)],
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
            }

        except Exception as e:
            log.error("debugger.error", error=str(e))
            return {
                "debug_report": {"root_cause": "Analysis failed", "error_type": "unknown"},
                "error": str(e),
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
            }
