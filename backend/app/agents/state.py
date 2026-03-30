"""ReviewState — shared state for the LangGraph workflow — aligned with §4.2."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class ReviewState(TypedDict, total=False):
    """Shared state passed between all Agent nodes in the workflow.

    Every Agent node receives the full state and returns a dict containing
    only the fields it wants to update. LangGraph merges the updates
    automatically.

    NOTE: For large fields (candidate_papers, paper_analyses, full_draft),
    the state stores IDs or summaries only. Full data lives in the
    business database to avoid bloating checkpoint serialization.
    """

    # ── User input ──
    user_query: str
    uploaded_papers: list[str]
    output_types: list[str]
    output_language: str  # "zh" | "en" | "bilingual"
    citation_style: str   # "apa" | "ieee" | "gbt7714"

    # ── Search phase ──
    search_strategy: dict
    candidate_papers: list[dict]   # lightweight paper dicts
    selected_papers: list[dict]    # user-confirmed papers

    # ── Reading phase ──
    paper_analyses: list[dict]     # analysis result dicts
    reading_progress: dict         # {total, completed, current}

    # ── Analysis phase (v0.3) ──
    topic_clusters: list[dict]
    comparison_matrix: dict
    timeline: list[dict]
    citation_network: dict
    research_trends: dict

    # ── Critique phase (v0.3) ──
    quality_assessments: list[dict]
    contradictions: list[dict]
    research_gaps: list[dict]
    limitation_summary: str

    # ── Writing phase ──
    outline: dict
    draft_sections: list[dict]
    full_draft: str
    references: list[dict]
    final_output: str

    # ── Citation verification ──
    citation_verification: list[dict]

    # ── Cost tracking ──
    token_usage: dict
    token_budget: int | None

    # ── Fulltext coverage ──
    fulltext_coverage: dict  # {total, fulltext_count, abstract_only_count}

    # ── Feedback loop control ──
    feedback_search_queries: list[str]
    feedback_iteration_count: int

    # ── Flow control ──
    current_phase: str
    messages: Annotated[list, add_messages]
    error_log: list[dict]

    # ── HITL signals ──
    needs_more_search: bool
    revision_instructions: str

    # ── Project reference ──
    project_id: str
