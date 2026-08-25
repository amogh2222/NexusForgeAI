"""
NexusForge AI — GitHub Plugin
Integrates GitHub API for PR management, issue tracking, and CI status.
"""
from __future__ import annotations

from typing import Any

import structlog

from plugins.base import NexusPlugin, PluginMetadata

log = structlog.get_logger()


class GitHubPlugin(NexusPlugin):
    """GitHub integration: PRs, issues, checks, webhooks."""

    ACTIONS = [
        "list_prs", "get_pr", "create_pr_comment",
        "list_issues", "create_issue",
        "get_check_runs", "trigger_workflow",
        "get_file_content", "create_commit",
    ]

    def __init__(self) -> None:
        self._client = None
        self._org: str = ""
        self._repo: str = ""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="github",
            version="1.0.0",
            description="GitHub API integration for PR management and CI/CD",
            author="NexusForge AI",
            capabilities=["git", "ci", "review", "issues"],
            config_schema={
                "token": {"type": "string", "required": True, "secret": True},
                "org": {"type": "string", "required": True},
                "repo": {"type": "string", "required": True},
            },
        )

    async def initialize(self, config: dict) -> bool:
        try:
            from github import Github
            
            # Use provided token or fallback to OAuth user token if available in config
            token = config.get("token") or config.get("oauth_token")
            if not token:
                log.warning("github_plugin.no_token")
                return False
                
            self._client = Github(token)
            self._org = config.get("org", "")
            self._repo = config.get("repo", "")
            log.info("github_plugin.initialized", org=self._org, repo=self._repo)
            return True
        except ImportError:
            log.warning("github_plugin.pygithub_missing", hint="pip install PyGithub")
            return False
        except Exception as e:
            log.warning("github_plugin.init_failed", error=str(e))
            return False

    async def health_check(self) -> dict:
        if not self._client:
            return {"status": "error", "reason": "not initialized"}
        try:
            rate = self._client.get_rate_limit()
            return {
                "status": "ok",
                "api_calls_remaining": rate.core.remaining,
                "org": self._org,
                "repo": self._repo,
            }
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def execute(self, action: str, params: dict) -> Any:
        if not self._client:
            return {"error": "Plugin not initialized"}

        repo = self._client.get_repo(f"{self._org}/{params.get('repo', self._repo)}")

        match action:
            case "list_prs":
                prs = repo.get_pulls(state=params.get("state", "open"))
                return [
                    {
                        "number": pr.number,
                        "title": pr.title,
                        "author": pr.user.login,
                        "state": pr.state,
                        "url": pr.html_url,
                        "created_at": pr.created_at.isoformat(),
                    }
                    for pr in list(prs)[:params.get("limit", 20)]
                ]

            case "get_pr":
                pr = repo.get_pull(params["number"])
                files = [f.filename for f in pr.get_files()]
                return {
                    "number": pr.number,
                    "title": pr.title,
                    "body": pr.body or "",
                    "author": pr.user.login,
                    "files_changed": files,
                    "additions": pr.additions,
                    "deletions": pr.deletions,
                    "diff_url": pr.diff_url,
                }

            case "create_pr_comment":
                pr = repo.get_pull(params["number"])
                comment = pr.create_issue_comment(params["body"])
                return {"comment_id": comment.id, "url": comment.html_url}

            case "list_issues":
                issues = repo.get_issues(state=params.get("state", "open"))
                return [
                    {
                        "number": issue.number,
                        "title": issue.title,
                        "labels": [l.name for l in issue.labels],
                        "url": issue.html_url,
                    }
                    for issue in list(issues)[:params.get("limit", 20)]
                ]

            case "get_check_runs":
                sha = params.get("sha") or repo.get_branch(
                    params.get("branch", "main")
                ).commit.sha
                commit = repo.get_commit(sha)
                runs = commit.get_check_runs()
                return [
                    {"name": r.name, "status": r.status, "conclusion": r.conclusion}
                    for r in runs
                ]

            case "get_file_content":
                content = repo.get_contents(params["path"])
                return {
                    "path": content.path,
                    "content": content.decoded_content.decode("utf-8", errors="replace"),
                    "sha": content.sha,
                }

            case _:
                return {"error": f"Unknown action: {action}"}

    def get_actions(self) -> list[str]:
        return self.ACTIONS
