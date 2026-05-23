"""
NexusForge AI — Repository Evolution Intelligence
Analyzes git history for architectural patterns, bug introduction,
contributor behavior, and complexity evolution.

Uses PyDriller (built on gitpython) for efficient commit mining.
PyDriller's mod.complexity gives cyclomatic complexity per file.

THIS is a signature feature — no other AI coding tool answers:
  "Which commit introduced the auth complexity?"
  "Why did latency increase after last Thursday?"
"""
from __future__ import annotations

import hashlib
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class CommitMetric:
    hash: str
    short_hash: str
    author: str
    email: str
    date: datetime
    message: str
    files_changed: int
    lines_added: int
    lines_deleted: int
    churn_score: float      # lines_added + lines_deleted
    avg_complexity: float   # mean cyclomatic complexity of changed files
    is_bug_fix: bool
    is_refactor: bool
    is_feature: bool
    is_security: bool


@dataclass
class ContributorStats:
    name: str
    email: str
    total_commits: int
    lines_added: int
    lines_deleted: int
    files_owned: list[str]      # files with >50% commits by this author
    busiest_hours: list[int]    # most active hours of day
    avg_commit_size: float
    bug_fix_rate: float         # fraction of commits that are bug fixes


@dataclass
class SuspectCommit:
    hash: str
    author: str
    date: datetime
    message: str
    diff_snippet: str
    risk_score: float           # 0-1 (higher = more likely bug introducer)
    files_affected: list[str]


@dataclass
class ComplexityPoint:
    """A single data point on the complexity timeline."""
    date: datetime
    commit_hash: str
    commit_message: str
    file_count: int
    avg_complexity: float
    total_lines: int
    churn: int


# ─── Classifier ──────────────────────────────────────────────────────────────

_BUG_PATTERN     = re.compile(r'\b(fix|bug|patch|hotfix|issue|error|crash|broken|defect)\b', re.I)
_REFACTOR_PATTERN = re.compile(r'\b(refactor|cleanup|clean.up|reorganize|restructure|rename|move)\b', re.I)
_FEATURE_PATTERN  = re.compile(r'\b(feat|feature|add|implement|new|introduce|support)\b', re.I)
_SECURITY_PATTERN = re.compile(r'\b(security|vuln|cve|auth|token|jwt|secret|injection|xss|csrf)\b', re.I)


def _classify_commit(message: str) -> dict[str, bool]:
    msg = message.lower()
    return {
        "is_bug_fix":  bool(_BUG_PATTERN.search(msg)),
        "is_refactor": bool(_REFACTOR_PATTERN.search(msg)),
        "is_feature":  bool(_FEATURE_PATTERN.search(msg)),
        "is_security": bool(_SECURITY_PATTERN.search(msg)),
    }


def _risk_score(lines_added: int, lines_deleted: int, files: int, message: str) -> float:
    """Heuristic risk score for bug-introduction likelihood."""
    churn = lines_added + lines_deleted
    score = 0.0
    # Large commits = higher risk (harder to review)
    if churn > 500: score += 0.3
    elif churn > 200: score += 0.15
    # Many files = higher risk
    if files > 10: score += 0.2
    elif files > 5: score += 0.1
    # No commit message = higher risk
    if len(message.strip()) < 10: score += 0.2
    # Security-related = higher risk (may introduce security bugs)
    if _SECURITY_PATTERN.search(message): score += 0.2
    return min(score, 1.0)


# ─── Analyzer ────────────────────────────────────────────────────────────────

class GitAnalyzer:
    """Analyzes git repository history for architectural intelligence."""

    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path)
        self._pydriller_available = False
        self._gitpython_available = False
        self._check_deps()

    def _check_deps(self) -> None:
        try:
            import pydriller  # noqa
            self._pydriller_available = True
        except ImportError:
            log.warning("git_analyzer.pydriller_missing", hint="pip install pydriller")
        try:
            import git  # noqa
            self._gitpython_available = True
        except ImportError:
            log.warning("git_analyzer.gitpython_missing", hint="pip install gitpython")

    # ── Commit History ────────────────────────────────────────────────────────

    def analyze_commit_history(
        self, max_commits: int = 500
    ) -> list[CommitMetric]:
        """Return per-commit metrics for the last max_commits commits."""
        if not self._pydriller_available:
            return []

        from pydriller import Repository

        metrics: list[CommitMetric] = []
        start = time.perf_counter()

        try:
            repo = Repository(str(self.repo_path))
            count = 0
            for commit in repo.traverse_commits():
                if count >= max_commits:
                    break
                count += 1

                lines_added = sum(
                    m.added_lines for m in commit.modified_files
                    if m.source_code is not None
                )
                lines_deleted = sum(
                    m.deleted_lines for m in commit.modified_files
                    if m.source_code is not None
                )
                # Cyclomatic complexity (None for non-Python/Java/C files)
                complexities = [
                    m.complexity for m in commit.modified_files
                    if m.complexity is not None
                ]
                avg_complexity = (
                    sum(complexities) / len(complexities) if complexities else 0.0
                )
                cls = _classify_commit(commit.msg or "")
                metrics.append(CommitMetric(
                    hash=commit.hash,
                    short_hash=commit.hash[:8],
                    author=commit.author.name or "Unknown",
                    email=commit.author.email or "",
                    date=commit.author_date,
                    message=(commit.msg or "").strip()[:200],
                    files_changed=len(commit.modified_files),
                    lines_added=lines_added,
                    lines_deleted=lines_deleted,
                    churn_score=float(lines_added + lines_deleted),
                    avg_complexity=avg_complexity,
                    **cls,
                ))

            elapsed = (time.perf_counter() - start) * 1000
            log.info(
                "git_analyzer.history_complete",
                commits=len(metrics),
                duration_ms=round(elapsed, 1),
            )
        except Exception as e:
            log.warning("git_analyzer.history_failed", error=str(e))

        return metrics

    # ── Bug Introduction ──────────────────────────────────────────────────────

    def find_bug_introduction_commits(
        self, pattern: str, max_results: int = 10
    ) -> list[SuspectCommit]:
        """
        Find commits that touched code matching a pattern.
        Uses git log -S (pickaxe) to find commits where pattern was added/removed.
        """
        if not self._gitpython_available:
            return []

        import git

        suspects: list[SuspectCommit] = []
        try:
            repo = git.Repo(str(self.repo_path))
            # git log -S "pattern" — finds commits where pattern appears/disappears
            commits_with_pattern = list(
                repo.iter_commits(all=True, S=pattern, max_count=50)
            )
            for commit in commits_with_pattern:
                files = list(commit.stats.files.keys())
                total_lines = commit.stats.total["lines"]
                total_files = commit.stats.total["files"]

                # Get a small diff snippet
                diff_snippet = ""
                try:
                    if commit.parents:
                        diffs = commit.parents[0].diff(commit, unified=3)
                        for d in diffs[:1]:  # first changed file only
                            if d.diff:
                                diff_snippet = d.diff.decode("utf-8", errors="replace")[:500]
                except Exception:
                    pass

                risk = _risk_score(
                    commit.stats.total.get("insertions", 0),
                    commit.stats.total.get("deletions", 0),
                    total_files,
                    commit.message or "",
                )

                suspects.append(SuspectCommit(
                    hash=commit.hexsha[:8],
                    author=commit.author.name or "Unknown",
                    date=commit.committed_datetime,
                    message=(commit.message or "").strip()[:200],
                    diff_snippet=diff_snippet,
                    risk_score=risk,
                    files_affected=files[:20],
                ))

            suspects.sort(key=lambda s: s.risk_score, reverse=True)
            return suspects[:max_results]

        except Exception as e:
            log.warning("git_analyzer.blame_failed", pattern=pattern, error=str(e))
            return []

    # ── Contributor Patterns ──────────────────────────────────────────────────

    def get_contributor_patterns(self) -> list[ContributorStats]:
        """Aggregate per-author statistics from commit history."""
        if not self._pydriller_available:
            return []

        from pydriller import Repository

        author_data: dict[str, dict] = defaultdict(lambda: {
            "email": "",
            "commits": 0,
            "lines_added": 0,
            "lines_deleted": 0,
            "bug_fixes": 0,
            "file_commits": defaultdict(int),
            "hours": defaultdict(int),
        })

        try:
            for commit in Repository(str(self.repo_path)).traverse_commits():
                name = commit.author.name or "Unknown"
                d = author_data[name]
                d["email"] = commit.author.email or ""
                d["commits"] += 1
                d["lines_added"] += sum(
                    m.added_lines for m in commit.modified_files
                    if m.source_code is not None
                )
                d["lines_deleted"] += sum(
                    m.deleted_lines for m in commit.modified_files
                    if m.source_code is not None
                )
                if _classify_commit(commit.msg or "")["is_bug_fix"]:
                    d["bug_fixes"] += 1
                for mod in commit.modified_files:
                    d["file_commits"][mod.filename] += 1
                d["hours"][commit.author_date.hour] += 1

        except Exception as e:
            log.warning("git_analyzer.contributors_failed", error=str(e))
            return []

        results: list[ContributorStats] = []
        for name, d in author_data.items():
            total = d["commits"]
            if total == 0:
                continue

            # Files where this author made >50% of commits
            owned = [
                f for f, cnt in d["file_commits"].items()
                if cnt / total > 0.5
            ][:20]

            # Top 3 busiest hours
            busiest = sorted(d["hours"].keys(), key=lambda h: d["hours"][h], reverse=True)[:3]

            results.append(ContributorStats(
                name=name,
                email=d["email"],
                total_commits=total,
                lines_added=d["lines_added"],
                lines_deleted=d["lines_deleted"],
                files_owned=owned,
                busiest_hours=busiest,
                avg_commit_size=(d["lines_added"] + d["lines_deleted"]) / max(total, 1),
                bug_fix_rate=d["bug_fixes"] / max(total, 1),
            ))

        results.sort(key=lambda c: c.total_commits, reverse=True)
        return results

    # ── Complexity Timeline ───────────────────────────────────────────────────

    def get_complexity_timeline(self, n_samples: int = 20) -> list[ComplexityPoint]:
        """
        Sample commits evenly across history for a complexity timeline chart.
        Returns n_samples data points ordered by date (oldest first).
        """
        if not self._pydriller_available:
            return []

        from pydriller import Repository

        all_commits = []
        try:
            for commit in Repository(str(self.repo_path)).traverse_commits():
                complexities = [
                    m.complexity for m in commit.modified_files
                    if m.complexity is not None
                ]
                all_commits.append({
                    "date": commit.author_date,
                    "hash": commit.hash[:8],
                    "message": (commit.msg or "")[:80],
                    "complexity": sum(complexities) / len(complexities) if complexities else 0.0,
                    "file_count": len(commit.modified_files),
                    "churn": sum(
                        m.added_lines + m.deleted_lines
                        for m in commit.modified_files
                        if m.source_code is not None
                    ),
                })
        except Exception as e:
            log.warning("git_analyzer.timeline_failed", error=str(e))
            return []

        if not all_commits:
            return []

        # Sample evenly
        total = len(all_commits)
        step = max(1, total // n_samples)
        sampled = all_commits[::step][:n_samples]

        return [
            ComplexityPoint(
                date=c["date"],
                commit_hash=c["hash"],
                commit_message=c["message"],
                file_count=c["file_count"],
                avg_complexity=c["complexity"],
                total_lines=0,  # expensive to compute; omitted
                churn=c["churn"],
            )
            for c in sampled
        ]
