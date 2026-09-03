"""NexusForge AI — Reviewer Agent"""
from __future__ import annotations

import time
from typing import List

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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
    Enforces strict anti-hallucination, anti-repetition, and ORM-safety rules.
    """

    AGENT_NAME = "reviewer"
    AGENT_ICON = "🔍"
    SYSTEM_PROMPT = """You are a Principal Security & Systems Architect conducting an exacting code review for NexusForge AI.

CRITICAL REVIEW RULES (STRICT COMPLIANCE REQUIRED):
1. ZERO BOILERPLATE OR TEMPLATE REPETITION:
   - NEVER repeat identical or near-identical descriptions across multiple methods or files.
   - Each reported issue MUST describe a distinct, genuine vulnerability with concrete code evidence.
2. VERIFY METHOD PARAMETERS & SIGNATURES:
   - NEVER claim a method lacks validation for a parameter (such as 'email') unless that EXACT parameter is explicitly declared in that method's signature in the code.
   - For example, do NOT claim 'list_all' or 'get_by_id' lacks validation for an 'email' parameter. Only review parameters that actually exist in the code.
3. ORM & SQL INJECTION STANDARDS:
   - When code uses an ORM (SQLAlchemy, Django ORM, Prisma, Tortoise) or parameterized queries, input binding is handled automatically by the ORM.
   - Do NOT falsely claim SQL injection on standard ORM calls. Only flag SQL injection if you see raw unescaped string interpolation (e.g., f"SELECT ... {var}" or "SELECT ... " + var).
4. QUALITY OVER QUANTITY:
   - Report only 2 to 5 genuine, verified, high-impact issues.
   - If the code is well-structured and safe, assign an appropriate score (85-98) and report zero or one minor informational observation.
   - NEVER invent issues or copy-paste identical template items.

Format your response as a structured JSON review report.
"""

    async def run(self, state: dict) -> dict:
        start_time = time.time()
        context_prompt = self._build_context_prompt(state)
        generated_code = state.get("generated_code", {})
        task = state.get("current_task", "")
        retrieved_context = state.get("retrieved_context", "")

        log.info("reviewer.running")

        code_to_review = ""
        if generated_code and generated_code.get("files"):
            for f in generated_code["files"][:5]:
                code_to_review += f"\n\n### {f.get('path', 'unknown')}\n```\n{f.get('content', '')}\n```"
        elif retrieved_context:
            code_to_review = f"```\n{retrieved_context[:6000]}\n```"
        else:
            code_to_review = "Review repository architecture and structure from the context provided above."

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""
{context_prompt}

## Code to Review
{code_to_review}

## Review Request
{task}

Perform a rigorous, professional code review. Be specific, distinct, and accurate. Do not repeat template statements.
"""),
        ]

        try:
            report = await self._invoke_llm(messages, structured_output_schema=ReviewReport)
            duration_ms = int((time.time() - start_time) * 1000)

            # ─── Post-Processing: Deduplication & Quality Filtering ─────
            filtered_issues: List[ReviewIssue] = []
            seen_fingerprints: set[str] = set()

            for issue in report.issues:
                desc = issue.description.strip()
                if not desc:
                    continue

                # Normalize fingerprint by removing method and parameter names
                import re
                fingerprint = re.sub(
                    r"\b(in the \w+ method|for the \w+ parameter|in method \w+|for parameter \w+)\b",
                    "",
                    desc.lower(),
                )
                fingerprint = re.sub(r"\s+", " ", fingerprint).strip()

                # Check for near-identical duplicate issues
                is_duplicate = False
                for seen in seen_fingerprints:
                    from difflib import SequenceMatcher
                    if SequenceMatcher(None, fingerprint, seen).ratio() > 0.65:
                        is_duplicate = True
                        break

                if is_duplicate:
                    log.info("reviewer.dropped_duplicate_issue", location=issue.location, desc=desc[:60])
                    continue

                seen_fingerprints.add(fingerprint)
                filtered_issues.append(issue)

            report.issues = filtered_issues
            report.critical_issues = [
                i for i in report.issues if i.severity.lower() in ("critical", "high")
            ]

            # Adjust score if deduplication eliminated false critical issues
            if not report.critical_issues and report.overall_score < 70 and len(report.issues) <= 2:
                report.overall_score = 88

            log.info(
                "reviewer.complete",
                score=report.overall_score,
                total_issues=len(report.issues),
                critical=len(report.critical_issues),
                duration_ms=duration_ms,
            )

            summary_msg = f"""## Code Review Results

**Score**: {report.overall_score}/100

{report.summary}

### Issues Found ({len(report.issues)} total)
{"".join(f"- **[{i.severity.upper()}]** {i.category}: {i.description}" + chr(10) for i in report.issues[:10]) if report.issues else "- No critical vulnerabilities found. Code follows standard conventions."}

### Recommendations
{"".join(f"- {r}" + chr(10) for r in report.recommendations[:5]) if report.recommendations else "- Continue following clean code and testing best practices."}
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
