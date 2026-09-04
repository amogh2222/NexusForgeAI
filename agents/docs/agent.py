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

    README_SYSTEM_PROMPT = """You are the Documentation Agent for NexusForge AI. You are a senior staff engineer who writes production-grade technical documentation.

Your output must:
- Be immediately usable in a real open-source or enterprise project
- Include concrete code examples, not placeholders
- Use proper Markdown formatting with badges, code blocks, and tables
- Be concise, high-density, and senior-engineer grade (under 800 words)

README Structure:

# Project Name

[![License](badge)] [![Version](badge)] [![CI Status](badge)]

> One-line tagline describing what this project does.

## Overview
[Key purpose, architecture, and technology stack]

## ✨ Features
[Bullet points with specific, concrete features]

## 🏗️ Architecture & Tech Stack
[System components, database layer, services, and APIs]

## 🚀 Quick Start
[Minimal steps to run via Docker or locally]

## 🔧 Configuration
[Key environment variables]

## 📡 API Endpoints
[Key endpoints with request/response examples]

CRITICAL: Do NOT use placeholders like [Your Name] or [Description]. Use actual technical details from the prompt and repository context."""

    QA_SYSTEM_PROMPT = """You are the Principal Codebase & Architecture Specialist at NexusForge AI.
Your role is to provide senior-engineer level explanations, architecture breakdowns, exact symbol citations, and function analyses strictly grounded in the indexed repository.

GROUNDING & CITATION REQUIREMENTS:
1. Cite exact file paths, class names, function names, and line numbers from the retrieved code context.
2. When explaining architecture, identify:
   - Main entry point (e.g. backend/main.py, app entry file)
   - Major services, routers, and processing layers
   - Database layer (models, ORM sessions, migrations, vector stores)
   - How requests flow from entry to services to storage
3. When searching for symbols or references (e.g. FastAPI references, indexing function):
   - Cite the exact file paths and line references where the symbol appears.
4. When explaining a specific function:
   - Detail its exact purpose, parameters, return types, error handling, and callers based directly on the source code.
5. ANTI-HALLUCINATION CONTRACT (MANDATORY):
   - If the user asks to locate, explain, or inspect a class, function, file, or symbol (such as 'QuantumRepositoryOptimizer' or any nonexistent entity) and it is NOT in the retrieved code context or codebase:
     YOU MUST STATE: "Not found in indexed repository."
   - Under no circumstances should you invent, assume, or hallucinate file paths, classes, or explanations for nonexistent entities."""

    SYSTEM_PROMPT = QA_SYSTEM_PROMPT

    async def run(self, state: dict) -> dict:
        start_time = time.time()
        task = state.get("current_task", "")
        context_prompt = self._build_context_prompt(state)

        log.info("docs.running", task=task[:100])

        # Determine if this is a README request or general Q&A
        is_readme_request = "readme" in task.lower()

        if is_readme_request:
            prompt = f"""
{context_prompt}

## User Task
{task}

Generate a production-grade README.md following the user's specification and all repository context.
Use all available context to write real, specific content — not generic placeholders.
Include actual API endpoints, actual environment variables, actual architecture details.

Generate the complete README.md now:
"""
            system_prompt = self.README_SYSTEM_PROMPT
        else:
            prompt = f"""
{context_prompt}

## User Question
{task}

Provide a direct, senior-engineer answer grounded in the indexed repository context.
Remember: If a requested class, symbol, or function is not found in the indexed repository, state: "Not found in indexed repository."
"""
            system_prompt = self.QA_SYSTEM_PROMPT

        messages = [
            SystemMessage(content=system_prompt),
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
