"""Conditional routing functions for the workflow DAG — aligned with §4.3."""

from app.agents.state import ReviewState

MAX_FEEDBACK_ITERATIONS = 2


def route_after_search_review(state: ReviewState) -> str:
    """Route after user reviews search results.

    - If user requests more search → back to ``search``
    - If no papers selected → back to ``search``
    - Otherwise → proceed to ``read``
    """
    if state.get("needs_more_search"):
        return "search"
    if not state.get("selected_papers"):
        return "search"
    return "read"


def route_after_read(state: ReviewState) -> str:
    """Route after reading phase.

    - If Reader found papers needing supplementary search AND
      iterations < MAX → back to ``search``
    - Otherwise → proceed to ``generate_outline``
      (``analyze`` is MVP-disabled; the orchestrator maps the
       ``analyze`` target to ``generate_outline`` when analyze is off)
    """
    feedback_queries = state.get("feedback_search_queries", [])
    iteration_count = state.get("feedback_iteration_count", 0)
    if feedback_queries and iteration_count < MAX_FEEDBACK_ITERATIONS:
        return "search"
    return "generate_outline"


def route_after_critique(state: ReviewState) -> str:
    """Route after critique phase (MVP disabled).

    Same logic as ``route_after_read`` but from the Critic node.
    """
    feedback_queries = state.get("feedback_search_queries", [])
    iteration_count = state.get("feedback_iteration_count", 0)
    if feedback_queries and iteration_count < MAX_FEEDBACK_ITERATIONS:
        return "search"
    return "generate_outline"


def route_after_draft_review(state: ReviewState) -> str:
    """Route after user reviews the draft.

    - If user provided revision instructions → ``revise_review``
    - Otherwise → ``export``
    """
    if state.get("revision_instructions"):
        return "revise_review"
    return "export"


def check_token_budget(state: ReviewState) -> str:
    """Check whether the token budget has been exceeded.

    Returns ``"budget_exceeded"`` or ``"continue"``.
    """
    budget = state.get("token_budget")
    if not budget:
        return "continue"
    usage = state.get("token_usage", {})
    total = usage.get("total_input", 0) + usage.get("total_output", 0)
    if total >= budget:
        return "budget_exceeded"
    return "continue"


# ── Router lookup table (used by the orchestrator) ──

ROUTER_REGISTRY: dict[str, callable] = {
    "route_after_search_review": route_after_search_review,
    "route_after_read": route_after_read,
    "route_after_critique": route_after_critique,
    "route_after_draft_review": route_after_draft_review,
    "check_token_budget": check_token_budget,
}
