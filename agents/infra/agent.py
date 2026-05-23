"""NexusForge AI — Infra Agent"""
import time

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from agents.base_agent import BaseAgent

log = structlog.get_logger()


class InfraBundle(BaseModel):
    dockerfile: str = ""
    docker_compose: str = ""
    github_actions_ci: str = ""
    nginx_conf: str = ""
    kubernetes_manifests: str = ""
    env_example: str = ""
    setup_instructions: str = ""
    notes: str = ""


class InfraAgent(BaseAgent):
    """
    Generates production-grade infrastructure configurations.
    Tailored to the detected technology stack.
    """

    AGENT_NAME = "infra"
    AGENT_ICON = "🐳"
    SYSTEM_PROMPT = """You are the Infrastructure Agent for NexusForge AI. You are a DevOps/Platform engineer specializing in containerization, CI/CD, and cloud-native deployments.

You generate production-grade infrastructure configurations that:
1. **Follow security best practices**: Non-root users, minimal base images, no hardcoded secrets
2. **Are optimized**: Multi-stage Docker builds, layer caching, slim images
3. **Include health checks**: Proper healthcheck commands with realistic intervals
4. **Support scaling**: Stateless services, environment-based configuration
5. **Work out of the box**: Complete, not requiring manual edits to run

Technologies you master:
- Docker + Docker Compose (multi-service orchestration)
- GitHub Actions (CI/CD with caching, matrix builds, deployment)
- NGINX (reverse proxy, SSL termination, rate limiting)
- Kubernetes (Deployments, Services, Ingress, ConfigMaps, Secrets)
- Popular cloud providers (AWS, GCP, Azure configurations)

Always use the detected framework/language stack from repository context to generate appropriate configurations."""

    async def run(self, state: dict) -> dict:
        start_time = time.time()
        task = state.get("current_task", "")
        context_prompt = self._build_context_prompt(state)

        log.info("infra.running", task=task[:100])

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""
{context_prompt}

## Infrastructure Request
{task}

Generate complete, production-ready infrastructure configurations based on:
1. The technology stack detected in the repository context
2. The specific infrastructure request above
3. Security and performance best practices

Include Dockerfile, docker-compose.yml, and GitHub Actions CI/CD at minimum.
"""),
        ]

        try:
            bundle = await self._invoke_llm(messages, structured_output_schema=InfraBundle)
            duration_ms = int((time.time() - start_time) * 1000)

            log.info("infra.complete", duration_ms=duration_ms)

            from langchain_core.messages import AIMessage
            components = [k for k, v in bundle.model_dump().items() if v and k != "notes"]
            summary_msg = f"""## Infrastructure Generated

**Components**: {', '.join(components)}

{bundle.notes}

{bundle.setup_instructions}
"""

            return {
                "infra_bundle": bundle.model_dump(),
                "messages": [AIMessage(content=summary_msg)],
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
            }

        except Exception as e:
            log.error("infra.error", error=str(e))
            return {
                "infra_bundle": {},
                "error": str(e),
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
            }
