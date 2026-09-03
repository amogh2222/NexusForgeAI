"""
NexusForge AI — Plugin System
Extensible architecture for integrating external services.

Plugin contract: subclass NexusPlugin, implement required methods,
register with PluginRegistry. No framework changes needed.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger()


@dataclass
class PluginMetadata:
    name: str
    version: str
    description: str
    author: str
    capabilities: list[str]  # e.g. ["git", "ci", "deploy", "cloud"]
    config_schema: dict = field(default_factory=dict)


class NexusPlugin(ABC):
    """Base class for all NexusForge AI plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Plugin metadata — name, version, capabilities."""
        ...

    @abstractmethod
    async def initialize(self, config: dict) -> bool:
        """Initialize the plugin with config. Return True if successful."""
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        """Return health status dict: {\"status\": \"ok\", ...}"""
        ...

    @abstractmethod
    async def execute(self, action: str, params: dict) -> Any:
        """Execute a plugin action. Actions defined per plugin."""
        ...

    def get_actions(self) -> list[str]:
        """List available actions for this plugin."""
        return []
