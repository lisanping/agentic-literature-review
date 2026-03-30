"""Orchestrator — config-driven LangGraph workflow builder — aligned with §4.4.

Constructs the literature review DAG from ``config/workflow.yaml``,
registers all agent nodes, wires conditional routing edges and
sequential edges, and configures HITL interrupt points.
"""

from pathlib import Path
from typing import Any

import yaml
import structlog
from langgraph.graph import END, START, StateGraph

from app.agents.registry import agent_registry
from app.agents.routing import ROUTER_REGISTRY
from app.agents.state import ReviewState

logger = structlog.stdlib.get_logger()

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "workflow.yaml"


# ── HITL passthrough nodes ──
# These nodes do nothing during automated execution.
# The workflow *pauses* at them via ``interrupt_before`` so the
# user can inspect state and submit feedback before the graph
# resumes.


async def human_review_search(state: ReviewState) -> dict:
    """HITL: user reviews candidate papers after search."""
    return {"current_phase": "search_review"}


async def human_review_outline(state: ReviewState) -> dict:
    """HITL: user reviews the generated outline."""
    return {"current_phase": "outline_review"}


async def human_review_draft(state: ReviewState) -> dict:
    """HITL: user reviews the full review draft."""
    return {"current_phase": "draft_review"}


async def check_read_feedback(state: ReviewState) -> dict:
    """Check whether Reader discovered papers needing supplemental search.

    Increments ``feedback_iteration_count`` when feedback queries exist,
    so the routing function can enforce the max-iteration cap.
    """
    feedback = state.get("feedback_search_queries", [])
    iteration = state.get("feedback_iteration_count", 0)
    if feedback:
        return {"feedback_iteration_count": iteration + 1}
    return {}


async def check_critic_feedback(state: ReviewState) -> dict:
    """Check whether Critic generated supplementary search queries.

    Increments ``feedback_iteration_count`` when feedback queries exist,
    so the routing function can enforce the max-iteration cap.
    """
    feedback = state.get("feedback_search_queries", [])
    iteration = state.get("feedback_iteration_count", 0)
    if feedback:
        return {"feedback_iteration_count": iteration + 1}
    return {}


# Register the lightweight / HITL nodes that aren't full agents
agent_registry.register("human_review_search", human_review_search)
agent_registry.register("human_review_outline", human_review_outline)
agent_registry.register("human_review_draft", human_review_draft)
agent_registry.register("check_read_feedback", check_read_feedback)
agent_registry.register("check_critic_feedback", check_critic_feedback)


# ── Config loading ──


def load_workflow_config(config_path: str | Path | None = None) -> dict:
    """Load and return the workflow YAML configuration."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Graph builder ──


def _get_enabled_nodes(config: dict) -> list[dict]:
    """Return only the enabled node configs (preserving order)."""
    return [
        n for n in config["workflow"]["nodes"]
        if n.get("enabled", True)
    ]


def _get_sequential_nodes(enabled_nodes: list[dict]) -> list[str]:
    """Return names of nodes that participate in the sequential chain.

    Nodes with ``sequential: false`` are excluded — they are only
    reachable via conditional routing edges (e.g. ``revise_review``).
    """
    return [
        n["name"] for n in enabled_nodes
        if n.get("sequential", True)
    ]


def _get_enabled_edges(config: dict) -> list[dict]:
    """Return only the enabled edge configs."""
    return [
        e for e in config["workflow"].get("edges", [])
        if e.get("enabled", True)
    ]


def _nodes_with_conditional_out(edges: list[dict]) -> set[str]:
    """Set of node names that have a conditional outgoing edge."""
    return {e["from"] for e in edges}


def build_review_graph(
    config_path: str | Path | None = None,
    registry=None,
) -> StateGraph:
    """Build the LangGraph StateGraph from workflow.yaml.

    1. Adds all enabled nodes from the registry.
    2. Wires conditional routing edges.
    3. Fills sequential edges between adjacent enabled nodes that
       lack a conditional outgoing edge.
    4. Connects START and END.

    Returns:
        An **uncompiled** StateGraph (call ``.compile()`` to get a
        runnable graph).
    """
    registry = registry or agent_registry
    config = load_workflow_config(config_path)
    enabled_nodes = _get_enabled_nodes(config)
    enabled_edges = _get_enabled_edges(config)
    conditional_sources = _nodes_with_conditional_out(enabled_edges)

    # Ensure all agent modules are imported so they self-register
    _ensure_agents_imported()

    graph = StateGraph(ReviewState)

    # 1. Add nodes
    enabled_names: list[str] = []
    for node_cfg in enabled_nodes:
        name = node_cfg["name"]
        node_fn = registry.get(name)
        graph.add_node(name, node_fn)
        enabled_names.append(name)

    if not enabled_names:
        raise ValueError("No enabled nodes in workflow config")

    # 2. Add conditional routing edges
    for edge_cfg in enabled_edges:
        from_node = edge_cfg["from"]
        if from_node not in enabled_names:
            continue  # source disabled → skip

        router_name = edge_cfg["router"]
        router_fn = ROUTER_REGISTRY.get(router_name)
        if router_fn is None:
            raise ValueError(
                f"Router '{router_name}' not found in ROUTER_REGISTRY"
            )

        # Only include targets that are actually enabled
        targets = [t for t in edge_cfg["targets"] if t in enabled_names]
        if not targets:
            continue

        path_map = {t: t for t in targets}
        graph.add_conditional_edges(from_node, router_fn, path_map)

    # 3. Add sequential edges between adjacent *sequential* nodes
    seq_names = _get_sequential_nodes(enabled_nodes)
    for i in range(len(seq_names) - 1):
        src = seq_names[i]
        dst = seq_names[i + 1]
        if src not in conditional_sources:
            graph.add_edge(src, dst)

    # 4. Connect START → first node, last sequential node → END
    graph.set_entry_point(seq_names[0])
    last = seq_names[-1]
    if last not in conditional_sources:
        graph.add_edge(last, END)

    # 5. Loop-back edges for non-sequential nodes
    if "revise_review" in enabled_names and "human_review_draft" in enabled_names:
        graph.add_edge("revise_review", "human_review_draft")

    logger.info(
        "orchestrator.graph_built",
        nodes=len(enabled_names),
        conditional_edges=len(enabled_edges),
    )

    return graph


def compile_review_graph(
    config_path: str | Path | None = None,
    checkpointer=None,
) -> Any:
    """Build and compile the workflow graph with checkpointer + HITL interrupts.

    Returns a compiled LangGraph that can be ``.invoke()``-ed or
    ``.astream()``-ed.
    """
    config = load_workflow_config(config_path)
    graph = build_review_graph(config_path)

    # Determine HITL interrupt nodes
    interrupt_nodes = [
        n["name"]
        for n in _get_enabled_nodes(config)
        if n.get("interrupt")
    ]

    if checkpointer is None:
        from app.agents.checkpointer import create_checkpointer
        checkpointer = create_checkpointer()

    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes,
    )

    logger.info(
        "orchestrator.compiled",
        interrupt_nodes=interrupt_nodes,
        has_checkpointer=checkpointer is not None,
    )

    return compiled


# ── Ensure agents are imported ──


def _ensure_agents_imported():
    """Import all agent modules so they self-register into the global registry."""
    import app.agents.intent_parser   # noqa: F401
    import app.agents.search_agent    # noqa: F401
    import app.agents.reader_agent    # noqa: F401
    import app.agents.analyst_agent   # noqa: F401
    import app.agents.critic_agent    # noqa: F401
    import app.agents.writer_agent    # noqa: F401
    import app.agents.verify_citations  # noqa: F401
    import app.agents.export_node     # noqa: F401
