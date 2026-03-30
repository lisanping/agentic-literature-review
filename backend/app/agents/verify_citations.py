"""verify_citations node — validate every citation against data sources."""

import structlog

from app.agents.registry import agent_registry
from app.agents.state import ReviewState
from app.sources.registry import SourceRegistry

logger = structlog.stdlib.get_logger()


async def verify_citations_node(
    state: ReviewState,
    source_registry: SourceRegistry | None = None,
) -> dict:
    """Verify each reference in the draft by checking against data sources.

    For each reference, attempt to confirm its existence via Semantic Scholar
    (DOI or S2 ID lookup). Papers that cannot be verified are flagged.

    Returns:
        Partial state with ``citation_verification`` list.
    """
    references = state.get("references", [])
    if not references:
        return {"citation_verification": [], "current_phase": "draft_review"}

    if source_registry is None:
        from app.config import settings
        from app.sources import create_source_registry
        source_registry = create_source_registry(settings)

    s2_source = source_registry.get_source("semantic_scholar")

    verification_results: list[dict] = []

    for ref in references:
        paper_id = ref.get("paper_id", "")
        title = ref.get("title", "")
        doi = ref.get("doi")
        status = "pending"
        verified_source = None

        # Try to verify via S2
        if s2_source and paper_id:
            try:
                result = await s2_source.get_paper(paper_id)
                if result:
                    status = "verified"
                    verified_source = "semantic_scholar"
            except Exception:
                pass

        # Try DOI if not yet verified
        if status != "verified" and s2_source and doi:
            try:
                result = await s2_source.get_paper(f"DOI:{doi}")
                if result:
                    status = "verified"
                    verified_source = "semantic_scholar"
            except Exception:
                pass

        if status == "pending":
            status = "unverified"

        verification_results.append({
            "paper_id": paper_id,
            "title": title,
            "status": status,
            "source": verified_source,
        })

    verified = sum(1 for v in verification_results if v["status"] == "verified")
    logger.info(
        "agent.verify_citations",
        total=len(verification_results),
        verified=verified,
        unverified=len(verification_results) - verified,
    )

    return {
        "citation_verification": verification_results,
        "current_phase": "draft_review",
    }


agent_registry.register("verify_citations", verify_citations_node)
