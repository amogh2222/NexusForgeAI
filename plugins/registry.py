"""
NexusForge AI — Plugin Registry
Discovers, initializes, and provides access to plugins.
"""
import importlib
import inspect
import json
import os
import pkgutil
from typing import Dict, List, Any

import structlog

from plugins.base import NexusPlugin

log = structlog.get_logger()


class PluginRegistry:
    """Manages the lifecycle and routing of NexusPlugins."""

    _instance = None

    def __init__(self):
        self._plugins: Dict[str, NexusPlugin] = {}

    @classmethod
    def get_instance(cls) -> "PluginRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize_plugins(self, configs: Dict[str, Dict[str, Any]]) -> None:
        """
        Dynamically load plugins from the plugins/ directory and initialize them.
        configs is a dictionary mapping plugin_name -> config_dict.
        """
        plugins_dir = os.path.dirname(__file__)
        
        # Iterate over all modules in the plugins package
        for _, module_name, is_pkg in pkgutil.iter_modules([plugins_dir]):
            if is_pkg and module_name not in ("__pycache__",):
                try:
                    module = importlib.import_module(f"plugins.{module_name}.plugin")
                    
                    # Find all classes that subclass NexusPlugin
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, NexusPlugin) and obj is not NexusPlugin:
                            plugin_instance = obj()
                            meta = plugin_instance.metadata
                            
                            # Only initialize if we have config for it
                            plugin_config = configs.get(meta.name, {})
                            
                            success = await plugin_instance.initialize(plugin_config)
                            if success:
                                self._plugins[meta.name] = plugin_instance
                                log.info("plugin_registry.loaded", plugin=meta.name)
                            else:
                                log.warning("plugin_registry.init_failed", plugin=meta.name)
                except ImportError as e:
                    log.warning("plugin_registry.import_error", module=module_name, error=str(e))
                except Exception as e:
                    log.error("plugin_registry.unexpected_error", module=module_name, error=str(e))

    def get_plugin(self, name: str) -> NexusPlugin | None:
        return self._plugins.get(name)

    def list_plugins(self) -> List[NexusPlugin]:
        return list(self._plugins.values())

    def get_langchain_tools(self) -> List[Any]:
        """
        Convert loaded plugins into LangChain tools so agents can use them.
        Returns a list of structured tools.
        """
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, Field

        class PluginToolInput(BaseModel):
            action: str = Field(..., description="The action to execute")
            params: str = Field(default="{}", description="JSON string of parameters for the action")

        tools = []
        for name, plugin in self._plugins.items():
            meta = plugin.metadata
            actions_list = plugin.ACTIONS if hasattr(plugin, "ACTIONS") else []
            
            description = (
                f"Interact with {meta.name}. "
                f"Description: {meta.description}. "
                f"Available actions: {', '.join(actions_list)}. "
                "Pass the action name and a JSON string of parameters."
            )
            
            # Create a synchronous wrapper for Langchain if async isn't supported, 
            # but LangGraph supports async tools natively via coroutine.
            async def _run_plugin(action: str, params: str = "{}", _plugin=plugin) -> str:
                try:
                    parsed_params = json.loads(params) if params else {}
                    result = await _plugin.execute(action, parsed_params)
                    return json.dumps(result, indent=2)
                except Exception as e:
                    return f"Error executing plugin {meta.name}: {e}"

            tool = StructuredTool.from_function(
                coroutine=_run_plugin,
                name=f"{name}_plugin",
                description=description,
                args_schema=PluginToolInput,
            )
            tools.append(tool)

        return tools
