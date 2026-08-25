#!/usr/bin/env python3
"""
NexusForge AI — Benchmark Runner
Executes the Agent Evaluation Benchmark Suite and outputs a markdown report.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime

import structlog

# Add parent directory to path so we can import backend/evaluation
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from evaluation.benchmark_suite import BenchmarkSuite, EvaluationReport

log = structlog.get_logger()

async def dummy_agent_fn(prompt: str) -> str:
    """A dummy agent function for testing the runner."""
    from backend.core.config import settings
    
    if settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY, temperature=0)
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        return resp.content if hasattr(resp, "content") else str(resp)
    
    return "Dummy response containing some keywords: installation, docker, injection, sequential, gather, query, cache"


def generate_markdown_report(report: EvaluationReport, output_file: str):
    """Generate a GitHub-flavored Markdown report."""
    
    lines = [
        f"# NexusForge AI — Agent Benchmark Report",
        f"**Run ID:** `{report.suite_id}`",
        f"**Date:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Summary",
        f"- **Total Cases:** {report.total_cases}",
        f"- **Passed:** {report.passed_cases}",
        f"- **Pass Rate:** {report.pass_rate * 100:.1f}%",
        f"- **Mean Score:** {report.mean_score:.2f} / 100",
        f"- **p95 Latency:** {report.p95_latency_ms / 1000:.2f}s",
        "",
        "## Detailed Results",
        "| ID | Name | Passed | Score | Latency | Error |",
        "|---|---|:---:|---:|---:|---|",
    ]
    
    for run in report.runs:
        passed_icon = "✅" if run.passed else "❌"
        error = run.error if run.error else "-"
        score = f"{run.overall_score:.1f}"
        latency = f"{run.latency_ms / 1000:.2f}s"
        lines.append(f"| `{run.case_id}` | {run.case_name} | {passed_icon} | {score} | {latency} | {error} |")
        
    lines.append("")
    lines.append("## Failure Analysis")
    failures = [r for r in report.runs if not r.passed]
    if failures:
        for f in failures:
            lines.append(f"### {f.case_name} (`{f.case_id}`)")
            lines.append(f"- **Keyword Recall:** {f.keyword_recall * 100:.1f}%")
            lines.append(f"- **Rubric Score:** {f.rubric_score:.1f}")
            lines.append(f"#### Agent Output Snippet:")
            lines.append("```text")
            lines.append(f.agent_output[:500] + ("..." if len(f.agent_output) > 500 else ""))
            lines.append("```")
    else:
        lines.append("No failures! 🎉")
        
    with open(output_file, "w") as f:
        f.write("\n".join(lines))
    log.info("benchmark.report_generated", path=output_file)


async def main():
    parser = argparse.ArgumentParser(description="Run NexusForge Benchmark Suite")
    parser.add_argument("--output", default="benchmark_report.md", help="Output markdown file")
    parser.add_argument("--cases", nargs="+", help="Specific case IDs to run")
    args = parser.parse_args()
    
    suite = BenchmarkSuite()
    suite_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    log.info("benchmark.start", suite_id=suite_id, cases=args.cases)
    
    report = await suite.run(
        suite_id=suite_id,
        agent_fn=dummy_agent_fn,
        case_ids=args.cases
    )
    
    generate_markdown_report(report, args.output)
    
    if report.pass_rate < 1.0:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
