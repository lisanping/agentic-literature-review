"""Conditional routing functions for the workflow DAG — aligned with §4.3."""

from app.agents.state import ReviewState

MAX_FEEDBACK_ITERATIONS = 2
MAX_REVISION_ITERATIONS = 2
AUTO_REVISE_THRESHOLD = 6.0
MAX_CONTRACT_DIMENSIONS = 2


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
    - Otherwise → proceed to ``analyze``
    """
    feedback_queries = state.get("feedback_search_queries", [])
    iteration_count = state.get("feedback_iteration_count", 0)
    if feedback_queries and iteration_count < MAX_FEEDBACK_ITERATIONS:
        return "search"
    return "analyze"


def route_after_critique(state: ReviewState) -> str:
    """Route after critique phase.

    - If Critic generated supplementary search queries AND
      iterations < MAX → back to ``search``
    - Otherwise → proceed to ``generate_outline``
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


def route_after_review_assessment(state: ReviewState) -> str:
    """Route after Critic's review-level assessment.

    Decision logic:
      1. weighted_score >= threshold → human_review_draft (quality OK)
      2. revision_iteration_count >= max → human_review_draft (iteration cap)
      3. score did not improve vs previous round → human_review_draft (stalled)
      4. Otherwise → auto_revise (revise per iteration contract)
    """
    scores = state.get("review_scores", {})
    weighted = scores.get("weighted", 10.0)
    iteration = state.get("revision_iteration_count", 0)
    history = state.get("revision_score_history", [])

    if weighted >= AUTO_REVISE_THRESHOLD:
        return "human_review_draft"

    if iteration >= MAX_REVISION_ITERATIONS:
        return "human_review_draft"

    # Monotonic convergence check: stop if no improvement
    if len(history) >= 2:
        prev_weighted = history[-2].get("scores", {}).get("weighted", 0)
        if weighted <= prev_weighted:
            return "human_review_draft"

    return "auto_revise"


def generate_revision_contract(
    review_scores: dict,
    review_feedback: list[dict],
) -> dict:
    """Generate an iteration contract from the latest review assessment.

    Selects the lowest-scoring dimensions (up to MAX_CONTRACT_DIMENSIONS),
    sets incremental targets, and extracts actionable instructions from feedback.
    """
    dimensions = ["coherence", "depth", "rigor", "utility"]
    scored = [(d, review_scores.get(d, 5)) for d in dimensions]
    scored.sort(key=lambda x: x[1])

    focus = scored[:MAX_CONTRACT_DIMENSIONS]
    targets = {d: min(s + 2, 10) for d, s in focus}
    focus_dims = [d for d, _ in focus]

    relevant_feedback = [
        fb for fb in review_feedback
        if fb.get("dimension") in focus_dims
    ]
    instructions = "\n".join(
        f"- [{fb['dimension']}] {fb.get('location', '')}: "
        f"{fb.get('suggestion', fb.get('description', ''))}"
        for fb in relevant_feedback[:6]
    )

    return {
        "focus_dimensions": focus_dims,
        "targets": targets,
        "instructions": instructions or "请改进上述低分维度的整体质量",
        "previous_scores": review_scores,
    }


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
    "route_after_review_assessment": route_after_review_assessment,
    "check_token_budget": check_token_budget,
}
