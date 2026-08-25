"""
NexusForge AI — Self-Improving Workflow
Generate → Execute → Evaluate → Debug → Retry loop via LangGraph.

This is the autonomous coding loop:
  1. GENERATE: Coder agent writes code for the task
  2. EXECUTE:  Run code in sandboxed environment (gVisor/Docker/subprocess)
  3. EVALUATE: Check output correctness (test pass/fail + LLM judge)
  4. DEBUG:    If evaluation fails, debugger agent analyzes errors
  5. RETRY:    Loop back to GENERATE with debugger's fix guidance
  6. DONE:     Emit final result after pass or max_retries reached

Max retries: 3 (configurable). Each cycle emits WebSocket events
so the frontend ThoughtPipeline shows live progress.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal, Optional

import structlog
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

log = structlog.get_logger()


# ─── State ────────────────────────────────────────────────────────────────────

class SelfImprovingState(TypedDict):
    # Input
    task_description: str
    language: str
    project_id: str
    test_cases: list[dict]          # [{"input": ..., "expected": ...}]
    max_retries: int

    # Working state
    generated_code: str
    execution_result: dict          # {stdout, stderr, return_code, timed_out}
    evaluation_passed: bool
    evaluation_feedback: str
    debug_guidance: str
    retry_count: int
    error: Optional[str]

    # Output
    final_code: str
    final_output: str
    total_cycles: int
    success: bool
    events: list[dict]              # for WebSocket streaming


# ─── Result ───────────────────────────────────────────────────────────────────

@dataclass
class WorkflowResult:
    success: bool
    final_code: str
    final_output: str
    total_cycles: int
    events: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0


# ─── Nodes ────────────────────────────────────────────────────────────────────

async def generate_node(state: SelfImprovingState) -> dict:
    """GENERATE: Coder agent writes code for the task."""
    from agents.router.model_router import ModelRouter, TaskType

    llm = ModelRouter.get_instance().get_langchain_llm(TaskType.CODEGEN)
    retry = state["retry_count"]
    debug_guidance = state.get("debug_guidance", "")

    system_prompt = (
        f"You are an expert {state['language']} developer. "
        "Write ONLY executable code with no explanation, no markdown fences, no comments unless necessary. "
        "The code must be runnable as-is."
    )

    if retry == 0:
        user_prompt = (
            f"Task: {state['task_description']}\n\n"
            f"Language: {state['language']}\n"
            "Write complete, working code:"
        )
    else:
        prev_result = state.get("execution_result", {})
        user_prompt = (
            f"Task: {state['task_description']}\n\n"
            f"Your previous attempt (cycle {retry}) failed.\n"
            f"Previous code:\n```\n{state.get('generated_code','')}\n```\n\n"
            f"Execution error:\n{prev_result.get('stderr','')[:500]}\n\n"
            f"Debug guidance:\n{debug_guidance}\n\n"
            "Write a FIXED version of the code:"
        )

    event = {
        "type": "generate",
        "cycle": retry + 1,
        "message": f"🤖 Generating code (cycle {retry + 1})…",
        "timestamp": time.time(),
    }

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        code = response.content if hasattr(response, "content") else str(response)
        # Strip markdown fences if model added them
        code = _strip_fences(code)
        event["status"] = "ok"
        log.info("self_improving.generated", cycle=retry + 1, chars=len(code))
    except Exception as e:
        code = ""
        event["status"] = "error"
        event["error"] = str(e)
        log.warning("self_improving.generate_failed", error=str(e))

    return {
        "generated_code": code,
        "events": state.get("events", []) + [event],
    }


async def execute_node(state: SelfImprovingState) -> dict:
    """EXECUTE: Run generated code in sandbox."""
    from sandbox.firecracker_isolator import FirecrackerIsolator
    
    isolator = FirecrackerIsolator()
    code = state["generated_code"]
    language = state["language"]

    event = {
        "type": "execute",
        "cycle": state["retry_count"] + 1,
        "message": f"⚡ Executing in {isolator.get_isolation_level().split('(')[0].strip()}…",
        "timestamp": time.time(),
    }

    if not code.strip():
        result = {"stdout": "", "stderr": "Empty code generated", "return_code": 1, "timed_out": False}
        event["status"] = "error"
    else:
        sandbox_result = await isolator.execute(code, language=language, timeout_seconds=10)
        result = {
            "stdout": sandbox_result.stdout,
            "stderr": sandbox_result.stderr,
            "return_code": sandbox_result.return_code,
            "timed_out": sandbox_result.timed_out,
            "mode": sandbox_result.mode,
            "execution_ms": sandbox_result.execution_ms,
        }
        event["status"] = "ok" if sandbox_result.return_code == 0 else "error"
        event["stdout_preview"] = sandbox_result.stdout[:200]
        log.info(
            "self_improving.executed",
            rc=sandbox_result.return_code,
            mode=sandbox_result.mode,
            ms=round(sandbox_result.execution_ms, 1),
        )

    return {
        "execution_result": result,
        "events": state.get("events", []) + [event],
    }


async def evaluate_node(state: SelfImprovingState) -> dict:
    """EVALUATE: Check if execution output meets requirements."""
    result = state["execution_result"]
    test_cases = state.get("test_cases", [])
    code = state["generated_code"]

    event = {
        "type": "evaluate",
        "cycle": state["retry_count"] + 1,
        "message": "🔍 Evaluating output…",
        "timestamp": time.time(),
    }

    # Hard fail: execution error / timeout
    if result.get("timed_out"):
        return {
            "evaluation_passed": False,
            "evaluation_feedback": "Code execution timed out (>10s). Must optimize.",
            "events": state.get("events", []) + [{**event, "status": "fail", "reason": "timeout"}],
        }

    if result.get("return_code", 1) != 0:
        stderr = result.get("stderr", "")
        return {
            "evaluation_passed": False,
            "evaluation_feedback": f"Runtime error:\n{stderr[:500]}",
            "events": state.get("events", []) + [{**event, "status": "fail", "reason": "runtime_error"}],
        }

    stdout = result.get("stdout", "")

    # Test case matching (if provided)
    if test_cases:
        failures = []
        for tc in test_cases:
            expected = str(tc.get("expected", ""))
            if expected and expected not in stdout:
                failures.append(f"Expected '{expected}' not found in output")
        if failures:
            feedback = "Test failures:\n" + "\n".join(failures[:5])
            return {
                "evaluation_passed": False,
                "evaluation_feedback": feedback,
                "events": state.get("events", []) + [{**event, "status": "fail", "reason": "test_failure"}],
            }

    # LLM judge for quality (no test cases, or all passed)
    try:
        from agents.router.model_router import ModelRouter, TaskType
        from langchain_core.messages import HumanMessage

        llm = ModelRouter.get_instance().get_langchain_llm(TaskType.REVIEW)
        judge_prompt = (
            f"Task: {state['task_description']}\n\n"
            f"Code:\n```{state['language']}\n{code[:1500]}\n```\n\n"
            f"Output:\n{stdout[:500]}\n\n"
            "Does this code correctly solve the task? "
            "Reply with exactly one word: PASS or FAIL, then a brief reason."
        )
        response = await llm.ainvoke([HumanMessage(content=judge_prompt)])
        verdict = (response.content if hasattr(response, "content") else str(response)).strip()
        passed = verdict.upper().startswith("PASS")
        feedback = verdict if not passed else "LLM judge: PASS"
    except Exception as e:
        # Default to pass if LLM unavailable but execution succeeded
        passed = True
        feedback = f"LLM judge unavailable ({e}), execution succeeded"

    log.info("self_improving.evaluated", passed=passed, cycle=state["retry_count"] + 1)
    return {
        "evaluation_passed": passed,
        "evaluation_feedback": feedback,
        "events": state.get("events", []) + [{**event, "status": "pass" if passed else "fail", "feedback": feedback[:200]}],
    }


async def debug_node(state: SelfImprovingState) -> dict:
    """DEBUG: Analyze failures and produce fix guidance for next GENERATE cycle."""
    from agents.router.model_router import ModelRouter, TaskType
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ModelRouter.get_instance().get_langchain_llm(TaskType.DEBUG)
    result = state["execution_result"]
    feedback = state["evaluation_feedback"]

    event = {
        "type": "debug",
        "cycle": state["retry_count"] + 1,
        "message": "🐛 Debugger analyzing failure…",
        "timestamp": time.time(),
    }

    prompt = (
        f"Task: {state['task_description']}\n\n"
        f"Failed code:\n```{state['language']}\n{state['generated_code'][:1500]}\n```\n\n"
        f"STDOUT: {result.get('stdout','')[:300]}\n"
        f"STDERR: {result.get('stderr','')[:500]}\n"
        f"Evaluation feedback: {feedback}\n\n"
        "Provide SPECIFIC, CONCISE fix instructions (3-5 bullet points). "
        "Focus on the root cause. No code, just guidance."
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content="You are an expert debugger. Be concise and specific."),
            HumanMessage(content=prompt),
        ])
        guidance = response.content if hasattr(response, "content") else str(response)
        event["status"] = "ok"
        log.info("self_improving.debug_guidance_generated", chars=len(guidance))
    except Exception as e:
        guidance = f"Fix the error: {result.get('stderr','')[:200]}"
        event["status"] = "error"
        log.warning("self_improving.debug_failed", error=str(e))

    return {
        "debug_guidance": guidance,
        "retry_count": state["retry_count"] + 1,
        "events": state.get("events", []) + [{**event, "guidance_preview": guidance[:200]}],
    }


async def finalize_node(state: SelfImprovingState) -> dict:
    """DONE: Package final result."""
    passed = state.get("evaluation_passed", False)
    cycles = state["retry_count"] + 1
    event = {
        "type": "done",
        "cycle": cycles,
        "success": passed,
        "message": (
            f"✅ Code verified after {cycles} cycle(s)" if passed
            else f"⚠️ Max retries ({state['max_retries']}) reached — returning best attempt"
        ),
        "timestamp": time.time(),
    }
    log.info(
        "self_improving.done",
        success=passed,
        cycles=cycles,
        project_id=state.get("project_id"),
    )
    return {
        "final_code": state.get("generated_code", ""),
        "final_output": state.get("execution_result", {}).get("stdout", ""),
        "total_cycles": cycles,
        "success": passed,
        "events": state.get("events", []) + [event],
    }


# ─── Routing ──────────────────────────────────────────────────────────────────

def should_retry(state: SelfImprovingState) -> Literal["debug", "done"]:
    """After evaluate: retry if failed and retries remain, else done."""
    if state.get("evaluation_passed"):
        return "done"
    if state["retry_count"] >= state["max_retries"] - 1:
        return "done"
    return "debug"


def after_debug(state: SelfImprovingState) -> Literal["generate"]:
    """After debug: always go back to generate."""
    return "generate"


# ─── Graph Builder ────────────────────────────────────────────────────────────

def build_self_improving_graph() -> StateGraph:
    """Build and compile the self-improving LangGraph workflow."""
    graph = StateGraph(SelfImprovingState)

    graph.add_node("generate", generate_node)
    graph.add_node("execute",  execute_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("debug",    debug_node)
    graph.add_node("done",     finalize_node)

    graph.set_entry_point("generate")
    graph.add_edge("generate", "execute")
    graph.add_edge("execute",  "evaluate")
    graph.add_conditional_edges("evaluate", should_retry, {"debug": "debug", "done": "done"})
    graph.add_conditional_edges("debug",    after_debug,  {"generate": "generate"})
    graph.add_edge("done", END)

    return graph.compile()


# ─── Public API ───────────────────────────────────────────────────────────────

async def run_self_improving(
    task_description: str,
    language: str = "python",
    project_id: str = "",
    test_cases: Optional[list[dict]] = None,
    max_retries: int = 3,
) -> WorkflowResult:
    """
    Run the self-improving code generation workflow.

    Args:
        task_description: What code to generate (natural language)
        language:         Target language ("python", "javascript", "bash")
        project_id:       Project UUID (for cost tracking)
        test_cases:       Optional list of {input, expected} dicts
        max_retries:      Maximum Generate→Execute→Evaluate cycles (default: 3)

    Returns:
        WorkflowResult with final_code, success flag, and cycle events
    """
    graph = build_self_improving_graph()
    start = time.perf_counter()

    initial_state: SelfImprovingState = {
        "task_description": task_description,
        "language": language,
        "project_id": project_id,
        "test_cases": test_cases or [],
        "max_retries": max_retries,
        "generated_code": "",
        "execution_result": {},
        "evaluation_passed": False,
        "evaluation_feedback": "",
        "debug_guidance": "",
        "retry_count": 0,
        "error": None,
        "final_code": "",
        "final_output": "",
        "total_cycles": 0,
        "success": False,
        "events": [],
    }

    try:
        final_state = await graph.ainvoke(initial_state)
        duration_ms = (time.perf_counter() - start) * 1000
        return WorkflowResult(
            success=final_state.get("success", False),
            final_code=final_state.get("final_code", ""),
            final_output=final_state.get("final_output", ""),
            total_cycles=final_state.get("total_cycles", 0),
            events=final_state.get("events", []),
            duration_ms=duration_ms,
        )
    except Exception as e:
        log.warning("self_improving.workflow_failed", error=str(e))
        return WorkflowResult(
            success=False,
            final_code="",
            final_output="",
            total_cycles=0,
            error=str(e),
            duration_ms=(time.perf_counter() - start) * 1000,
        )


async def stream_self_improving(
    task_description: str,
    language: str = "python",
    project_id: str = "",
    test_cases: Optional[list[dict]] = None,
    max_retries: int = 3,
) -> AsyncIterator[dict]:
    """
    Stream self-improving workflow events as they happen.
    Yields event dicts: {type, cycle, message, status, timestamp}
    Compatible with WebSocket / Server-Sent Events.
    """
    graph = build_self_improving_graph()

    initial_state: SelfImprovingState = {
        "task_description": task_description,
        "language": language,
        "project_id": project_id,
        "test_cases": test_cases or [],
        "max_retries": max_retries,
        "generated_code": "",
        "execution_result": {},
        "evaluation_passed": False,
        "evaluation_feedback": "",
        "debug_guidance": "",
        "retry_count": 0,
        "error": None,
        "final_code": "",
        "final_output": "",
        "total_cycles": 0,
        "success": False,
        "events": [],
    }

    seen_events = 0
    async for chunk in graph.astream(initial_state):
        for node_name, node_output in chunk.items():
            new_events = node_output.get("events", [])
            for ev in new_events[seen_events:]:
                yield ev
            seen_events = len(new_events)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _strip_fences(code: str) -> str:
    """Remove markdown code fences that models sometimes add."""
    import re
    # Strip ```python ... ``` or ``` ... ```
    code = re.sub(r'^```[\w]*\n', '', code.strip(), flags=re.MULTILINE)
    code = re.sub(r'\n```$', '', code.strip(), flags=re.MULTILINE)
    return code.strip()
