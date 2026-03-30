"""export node — generate final output files from the review draft."""

import structlog

from app.agents.registry import agent_registry
from app.agents.state import ReviewState
from app.services.export import export_markdown

logger = structlog.stdlib.get_logger()


async def export_node(state: ReviewState) -> dict:
    """Export node: format the final review into requested output formats.

    Produces the final Markdown output from the draft and references.
    Additional formats (Word, BibTeX, RIS) are handled by the export API
    endpoint on-demand.

    Returns:
        Partial state with ``final_output`` and ``current_phase``.
    """
    full_draft = state.get("full_draft", "")
    references = state.get("references", [])
    outline = state.get("outline", {})
    title = outline.get("title")

    # Generate final Markdown output
    # (The full_draft already contains references section from the writer,
    #  but we also produce a clean version via export_markdown)
    final_output = export_markdown(
        content=full_draft,
        references=references,
        title=title,
    )

    logger.info(
        "agent.export_complete",
        chars=len(final_output),
        references=len(references),
    )

    return {
        "final_output": final_output,
        "current_phase": "completed",
    }


agent_registry.register("export", export_node)
