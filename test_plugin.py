import asyncio
import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.core.config import settings
from agents.orchestrator import NexusOrchestrator, create_initial_state

async def main():
    print("Testing PluginAgent integration...")
    
    # Needs to initialize PluginRegistry since we are outside the FastAPI lifespan
    from plugins.registry import PluginRegistry
    plugin_registry = PluginRegistry.get_instance()
    await plugin_registry.initialize_plugins({
        "github": {
            "token": settings.GITHUB_APP_PRIVATE_KEY_PATH, # Or token
            "org": "NexusForge",
            "repo": "demo"
        }
    })
    
    orchestrator = NexusOrchestrator()
    graph = await orchestrator.get_graph()
    
    state = create_initial_state(
        project_id="test_proj",
        thread_id="test_thread",
        user_message="List open pull requests on the GitHub repository",
    )
    
    config = {"configurable": {"thread_id": "test_thread"}}
    
    print("Running graph...")
    try:
        async for s in graph.astream(state, config=config):
            print(f"Step: {list(s.keys())}")
            if "plugin" in s:
                final_state = s["plugin"]
                break
    except Exception as e:
        print(f"Graph execution failed: {e}")
        
    print(f"\nFinal Task Type: {final_state.get('task_type')}")
    print("\nFinal Messages:")
    for msg in final_state.get("messages", []):
        print(f"[{msg.type}]: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
