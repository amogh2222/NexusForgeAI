"""
NexusForge AI — RAGAS RAG Quality Evaluator
Measures retrieval + generation quality using LLM-as-judge.

Metrics (RAGAS v0.2+):
  - faithfulness:        Is the answer grounded in the retrieved context?
  - answer_relevancy:    Does the answer address the question?
  - context_precision:  Are top retrieved chunks relevant?
  - context_recall:     Did we retrieve all needed info?

Note: RAGAS uses an LLM internally for judging — budget OpenAI API calls.
      Use gpt-4o-mini for cost efficiency (~$0.15/1M tokens).
      The `contexts` field MUST be List[List[str]] (one list per question).
      The `ground_truth` column is SINGULAR in v0.2 (not `ground_truths`).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import structlog

log = structlog.get_logger()


@dataclass
class RAGASResult:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: Optional[float]    # requires ground_truth
    mean_score: float
    questions_evaluated: int
    error: Optional[str] = None


async def evaluate_rag(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],    # List[List[str]] — one list per question
    ground_truths: Optional[list[str]] = None,
) -> RAGASResult:
    """
    Evaluate RAG pipeline quality using RAGAS metrics.

    Args:
        questions:     Input questions
        answers:       Generated answers
        contexts:      Retrieved contexts per question (List[List[str]])
        ground_truths: Optional expected answers for recall calculation

    Returns:
        RAGASResult with all 4 metrics (context_recall=None if no ground_truths)
    """
    n = len(questions)
    if not (len(answers) == len(contexts) == n):
        return RAGASResult(
            faithfulness=0.0,
            answer_relevancy=0.0,
            context_precision=0.0,
            context_recall=None,
            mean_score=0.0,
            questions_evaluated=0,
            error="Mismatched input lengths",
        )

    # Set LangSmith tracing if configured
    from backend.core.config import settings
    if settings.LANGSMITH_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT

    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            faithfulness,
        )

        data: dict = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,    # must be List[List[str]]
        }

        metrics = [faithfulness, answer_relevancy, context_precision]

        # context_recall requires ground_truth (singular in v0.2)
        if ground_truths and len(ground_truths) == n:
            from ragas.metrics import context_recall
            data["ground_truth"] = ground_truths  # SINGULAR — v0.2 change
            metrics.append(context_recall)

        dataset = Dataset.from_dict(data)

        # Use gpt-4o-mini as judge (cost-effective)
        judge_llm = None
        if settings.OPENAI_API_KEY:
            try:
                from langchain_openai import ChatOpenAI
                judge_llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=settings.OPENAI_API_KEY,
                )
            except Exception:
                pass

        result = evaluate(dataset, metrics=metrics, llm=judge_llm)
        df = result.to_pandas()

        faithfulness_score = float(df["faithfulness"].mean()) if "faithfulness" in df else 0.0
        relevancy_score = float(df["answer_relevancy"].mean()) if "answer_relevancy" in df else 0.0
        precision_score = float(df["context_precision"].mean()) if "context_precision" in df else 0.0
        recall_score = float(df["context_recall"].mean()) if "context_recall" in df else None

        scores = [faithfulness_score, relevancy_score, precision_score]
        if recall_score is not None:
            scores.append(recall_score)
        mean = sum(scores) / len(scores)

        log.info(
            "ragas.evaluation_complete",
            questions=n,
            faithfulness=faithfulness_score,
            relevancy=relevancy_score,
            precision=precision_score,
            recall=recall_score,
        )

        return RAGASResult(
            faithfulness=faithfulness_score,
            answer_relevancy=relevancy_score,
            context_precision=precision_score,
            context_recall=recall_score,
            mean_score=mean,
            questions_evaluated=n,
        )

    except ImportError as e:
        log.error("ragas.not_installed", error=str(e), hint="pip install ragas datasets")
        raise RuntimeError(f"Enterprise Feature not implemented: RAGAS evaluation failed. Missing dependencies: {e}")
    except Exception as e:
        log.error("ragas.evaluation_failed", error=str(e))
        raise RuntimeError(f"RAGAS evaluation failed: {e}")
