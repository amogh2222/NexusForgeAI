"""NexusForge AI — Reviewer Agent"""
import time
from typing import List

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from agents.base_agent import BaseAgent

log = structlog.get_logger()


class ReviewIssue(BaseModel):
    severity: str          # "critical" | "high" | "medium" | "low" | "info"
    category: str          # "security" | "performance" | "architecture" | "n+1_query" | "bad_async" | "style"
    location: str          # file:line or description
    description: str
    suggestion: str
    code_snippet: str = ""


class ReviewReport(BaseModel):
    overall_score: int     # 0-100
    summary: str
    issues: List[ReviewIssue]
    critical_issues: List[ReviewIssue]
    strengths: List[str]
    recommendations: List[str]


class ReviewerAgent(BaseAgent):
    """
    Performs comprehensive code review with categorized, actionable feedback.
    Identifies security vulnerabilities, performance bottlenecks, and bad patterns.
    """

    AGENT_NAME = "reviewer"
    AGENT_ICON = "🔍"
    SYSTEM_PROMPT = """You are the Code Reviewer Agent for NexusForge AI. You are a principal engineer specializing in:

**Security**: SQL injection, XSS, auth bypass, exposed secrets, SSRF, path traversal
**Performance**: N+1 queries, missing indexes, synchronous blocking calls, memory leaks, O(n²) algorithms
**Architecture**: God objects, tight coupling, missing abstractions, violation of SOLID principles
**Async Patterns**: Blocking event loops, missing await, sync calls in async context, race conditions
**Reliability**: Missing error handling, no retries, single points of failure, missing timeouts

For each issue found:
1. Be specific with file locations and line numbers when available
2. Explain WHY it's a problem (not just that it is)
3. Provide a concrete fix suggestion or code example
4. Rate severity accurately (don't mark everything critical)

Format your response as a structured JSON review report.

Examples of high-quality feedback:
- "Database queries in a loop at users_service.py:42 — this will cause N+1 queries when loading user profiles at scale. Use select_related() or a single JOIN query instead."
- "Missing rate limiting on /api/auth/login endpoint — vulnerable to brute force. Add Redis-based rate limiting: 5 attempts per IP per minute."
- "Synchronous requests.get() call inside async function at api/github.py:89 — this blocks the event loop under load. Use httpx.AsyncClient() instead."
"""

    async def run(self, state: dict) -> dict:
        start_time = time.time()
        context_prompt = self._build_context_prompt(state)
        generated_code = state.get("generated_code", {})
        task = state.get("current_task", "")

        log.info("reviewer.running")

        code_to_review = ""
        if generated_code and generated_code.get("files"):
            for f in generated_code["files"][:5]:  # Review up to 5 files
                code_to_review += f"\n\n### {f.get('path', 'unknown')}\n```\n{f.get('content', '')}\n```"
        elif context_prompt:
            code_to_review = "Review the repository code from context above."

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""
{context_prompt}

## Code to Review
{code_to_review or 'Review based on repository context provided above.'}

## Review Request
{task}

Perform a comprehensive code review. Be specific, actionable, and accurate.
"""),
        ]

        try:
            report = await self._invoke_llm(messages, structured_output_schema=ReviewReport)
            duration_ms = int((time.time() - start_time) * 1000)

            log.info("reviewer.complete",
                     score=report.overall_score,
                     total_issues=len(report.issues),
                     critical=len(report.critical_issues),
                     duration_ms=duration_ms)

            from langchain_core.messages import AIMessage
            summary_msg = f"""## Code Review Results

**Score**: {report.overall_score}/100

{report.summary}

### Issues Found ({len(report.issues)} total)
{"".join(f"- **[{i.severity.upper()}]** {i.category}: {i.description}" + chr(10) for i in report.issues[:10])}

### Recommendations
{"".join(f"- {r}" + chr(10) for r in report.recommendations[:5])}
"""

            return {
                "review_results": report.model_dump(),
                "messages": [AIMessage(content=summary_msg)],
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
            }

        except Exception as e:
            log.error("reviewer.error", error=str(e))
            return {
                "review_results": {"critical_issues": [], "issues": [], "overall_score": 0},
                "error": str(e),
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
            }
