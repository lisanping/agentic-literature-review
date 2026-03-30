"""Agent registry — central lookup for all Agent node functions — aligned with §4.4."""

from typing import Any, Callable

from app.agents.state import ReviewState

# Agent node function type: takes ReviewState, returns partial state update dict
AgentNodeFn = Callable[[ReviewState], Any]


class AgentRegistry:
    """Registry for all Agent node functions in the workflow."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentNodeFn] = {}

    def register(self, name: str, node_fn: AgentNodeFn) -> None:
        """Register an agent node function."""
        self._agents[name] = node_fn

    def get(self, name: str) -> AgentNodeFn:
        """Retrieve a registered agent node function."""
        if name not in self._agents:
            raise ValueError(f"Agent '{name}' not registered")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())


# Global singleton — agents self-register on import
agent_registry = AgentRegistry()
