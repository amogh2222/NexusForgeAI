import argparse
import asyncio
import uuid
from typing import Optional

def run_benchmark(case_ids: Optional[list[str]] = None):
    from evaluation.benchmark_suite import BenchmarkSuite, GOLDEN_TEST_CASES

    suite = BenchmarkSuite()
    available_cases = case_ids or [c.id for c in GOLDEN_TEST_CASES]

    print("Starting benchmark suite execution...")
    print(f"Cases: {', '.join(available_cases)}")

    async def agent_fn(prompt: str) -> str:
        from agents.orchestrator import get_orchestrator
        orch = get_orchestrator()

        project_id = str(uuid.uuid4())
        thread_id = str(uuid.uuid4())

        result = await orch.arun(
            project_id=project_id,
            thread_id=thread_id,
            user_message=prompt
        )

        if result and "messages" in result and result["messages"]:
            return result["messages"][-1].content
        return "Agent produced no output."

    async def main():
        report = await suite.run(
            suite_id=f"cli-run-{uuid.uuid4().hex[:8]}",
            agent_fn=agent_fn,
            case_ids=case_ids
        )

        print("\n=== BENCHMARK REPORT ===")
        print(f"Total: {report.total_cases} | Passed: {report.passed_cases} | Pass Rate: {report.pass_rate:.1%}")
        print(f"Mean Score: {report.mean_score:.1f}/100 | p95 Latency: {report.p95_latency_ms:.0f}ms")
        print("------------------------")

        for r in report.runs:
            status = "✅" if r.passed else "❌"
            print(f"{status} [{r.case_id}] Score: {r.overall_score:.1f} | Latency: {r.latency_ms:.0f}ms")
            if not r.passed and r.error:
                print(f"   Error: {r.error}")

    asyncio.run(main())


def main():
    parser = argparse.ArgumentParser(description="NexusForge AI Agent Evaluation Benchmark CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the benchmark suite")
    run_parser.add_argument("--cases", type=str, help="Comma-separated case IDs", default=None)

    subparsers.add_parser("list", help="List available test cases")

    args = parser.parse_args()

    if args.command == "list":
        from evaluation.benchmark_suite import CASE_INDEX
        print("Available Test Cases:")
        for case_id, case in CASE_INDEX.items():
            print(f"- {case_id}: {case.name}")
    elif args.command == "run":
        case_ids = args.cases.split(",") if args.cases else None
        run_benchmark(case_ids)

if __name__ == "__main__":
    main()
