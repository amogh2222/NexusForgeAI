"""NexusForge AI — Docs Agent (README + Architecture Docs)"""
import time

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent

log = structlog.get_logger()


class DocsAgent(BaseAgent):
    """
    Generates production-grade README files and architecture documentation.
    Produces senior-engineer quality output, not tutorials.
    """

    AGENT_NAME = "docs"
    AGENT_ICON = "📄"
    SYSTEM_PROMPT = """You are the Documentation Agent for NexusForge AI. You are a senior staff engineer who writes production-grade technical documentation.

Your output must:
- Be immediately usable in a real open-source or enterprise project
- Include concrete code examples, not placeholders
- Cover all standard README sections comprehensively
- Use proper Markdown formatting with badges, code blocks, and tables
- Sound like it was written by a senior engineer, not a tutorial

README Structure (follow this exactly):

# Project Name

[![License](badge)] [![Version](badge)] [![CI Status](badge)]

> One-line tagline describing what this project does and why it's interesting.

## Overview
[2-3 paragraphs: what it is, why it exists, who it's for]

## ✨ Features
[Bullet points with specific, concrete features]

## 🏗️ Architecture
[ASCII diagram or description of system components]

## 🚀 Quick Start
[Minimal steps to get running in 5 minutes]

## 📋 Prerequisites
[Specific version requirements]

## ⚙️ Installation
[Detailed step-by-step with code blocks]

## 🐳 Docker Setup
[Complete docker-compose instructions]

## 🔧 Configuration
[All environment variables in a table with defaults and descriptions]

## 📡 API Documentation
[Key endpoints with request/response examples]

## 🚢 Deployment
[Production deployment guide]

## 📈 Scaling
[Horizontal scaling notes]

## 🔍 Troubleshooting
[Common issues and solutions]

## 📁 Project Structure
[Annotated directory tree]

## 🤝 Contributing
[Contributing guidelines]

## 📝 License

CRITICAL: Do NOT use placeholders like [Your Name] or [Description]. Use the actual repository context to generate real content."""

    async def run(self, state: dict) -> dict:
        start_time = time.time()
        task = state.get("current_task", "")
        context_prompt = self._build_context_prompt(state)

        log.info("docs.running", task=task[:100])

        # Determine if this is a README request or general Q&A
        is_readme_request = any(kw in task.lower() for kw in ["readme", "documentation", "generate docs"])

        if is_readme_request:
            prompt = f"""
{context_prompt}

## Task
Generate a production-grade README.md for this repository.

Use all available context to write real, specific content — not generic placeholders.
Include actual API endpoints, actual environment variables, actual architecture details.

Repository context is above. Generate the complete README.md now:
"""
        else:
            prompt = f"""
{context_prompt}

## User Question
{task}

Answer as a senior software engineer with deep knowledge of this codebase.
Be specific, reference actual files and code when relevant.
"""

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        try:
            response = await self._invoke_llm(messages)
            content = response.content if hasattr(response, "content") else str(response)
            duration_ms = int((time.time() - start_time) * 1000)

            log.info("docs.complete", chars=len(content), duration_ms=duration_ms)

            from langchain_core.messages import AIMessage
            result = {
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
                "messages": [AIMessage(content=content)],
            }

            if is_readme_request:
                result["readme_content"] = content

            return result

        except Exception as e:
            log.error("docs.error", error=str(e))
            from langchain_core.messages import AIMessage
            return {
                "messages": [AIMessage(content=f"Documentation generation failed: {str(e)}")],
                "error": str(e),
                "agent_history": state.get("agent_history", []) + [self.AGENT_NAME],
            }
