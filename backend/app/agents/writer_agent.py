"""Writer Agent — outline generation, section writing, citation formatting, coherence review.

Components (aligned with §5.5):
  - Outline Generator: create structured outline from analyses
  - Section Writer: write each section with proper citations
  - Citation Formatter: insert citation marks and build reference list
  - Coherence Reviewer: LLM full-draft coherence check

Node functions:
  - generate_outline_node: analyses → outline
  - write_review_node: outline + analyses → full_draft + references
  - revise_review_node: full_draft + revision_instructions → revised draft
"""

import json

import structlog

from app.agents.registry import agent_registry
from app.agents.state import ReviewState
from app.parsers.citation_formatter import CitationInfo, format_citation
from app.services.llm import LLMRouter
from app.services.prompt_manager import PromptManager

logger = structlog.stdlib.get_logger()


# ── Outline Generator ──


async def generate_outline(
    analyses: list[dict],
    user_query: str,
    output_type: str,
    output_language: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[dict, dict]:
    """Generate a structured outline from paper analyses.

    Returns:
        (outline_dict, updated_token_usage)
    """
    prompt = prompt_manager.render(
        "writer",
        "outline",
        user_query=user_query,
        output_type=output_type,
        analyses=analyses,
        output_language=output_language,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="writer",
        task_type="outline",
        token_usage=token_usage,
    )

    outline = _parse_json_response(response_text, fallback={
        "title": f"Literature Review: {user_query}",
        "sections": [
            {"heading": "Introduction", "description": "Background and scope", "subsections": [], "relevant_paper_indices": []},
            {"heading": "Main Findings", "description": "Key findings from the literature", "subsections": [], "relevant_paper_indices": list(range(1, len(analyses) + 1))},
            {"heading": "Conclusion", "description": "Summary and future directions", "subsections": [], "relevant_paper_indices": []},
        ],
    })

    return outline, token_usage


# ── Section Writer ──


async def write_section(
    section: dict,
    analyses: list[dict],
    user_query: str,
    citation_style: str,
    output_language: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[str, dict]:
    """Write a single section of the review.

    Returns:
        (section_markdown, updated_token_usage)
    """
    # Gather analyses relevant to this section
    relevant_indices = section.get("relevant_paper_indices", [])
    if relevant_indices:
        section_analyses = [
            analyses[i - 1] for i in relevant_indices
            if 0 < i <= len(analyses)
        ]
    else:
        section_analyses = analyses  # use all if not specified

    prompt = prompt_manager.render(
        "writer",
        "section_writing",
        user_query=user_query,
        section_heading=section.get("heading", ""),
        section_description=section.get("description", ""),
        section_analyses=section_analyses,
        citation_style=citation_style,
        output_language=output_language,
    )

    content, token_usage = await llm.call(
        prompt=prompt,
        agent_name="writer",
        task_type="section_writing",
        token_usage=token_usage,
    )

    return content.strip(), token_usage


# ── Citation Formatter ──


def build_references_list(
    analyses: list[dict], citation_style: str = "apa"
) -> list[dict]:
    """Build a formatted reference list from paper analyses."""
    references = []
    for i, analysis in enumerate(analyses, 1):
        title = analysis.get("title", f"Paper {i}")
        authors = analysis.get("authors", ["Unknown"])
        if isinstance(authors, str):
            authors = [authors]
        year = analysis.get("year")

        info = CitationInfo(
            title=title,
            authors=authors,
            year=year,
            venue=analysis.get("venue"),
            doi=analysis.get("doi"),
        )
        formatted = format_citation(info, citation_style)

        references.append({
            "index": i,
            "paper_id": analysis.get("paper_id", ""),
            "title": title,
            "authors": authors,
            "year": year,
            "formatted": formatted,
        })

    return references


# ── Coherence Reviewer ──


async def review_coherence(
    full_draft: str,
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[dict, dict]:
    """LLM-based coherence review of the full draft.

    Returns:
        (review_result_dict, updated_token_usage)
    """
    prompt = prompt_manager.render(
        "writer",
        "coherence_review",
        user_query=user_query,
        full_draft=full_draft[:12000],  # limit to avoid token overflow
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="writer",
        task_type="coherence_review",
        token_usage=token_usage,
    )

    review = _parse_json_response(response_text, fallback={
        "overall_quality": 0.7,
        "issues": [],
        "summary": "Review completed.",
    })

    return review, token_usage


# ── Node Functions ──


async def generate_outline_node(
    state: ReviewState,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict:
    """Generate outline node: analyses → structured outline."""
    llm = llm or LLMRouter()
    prompt_manager = prompt_manager or PromptManager()

    analyses = state.get("paper_analyses", [])
    output_types = state.get("output_types", ["full_review"])
    output_type = output_types[0] if output_types else "full_review"

    outline, token_usage = await generate_outline(
        analyses=analyses,
        user_query=state.get("user_query", ""),
        output_type=output_type,
        output_language=state.get("output_language", "zh"),
        llm=llm,
        prompt_manager=prompt_manager,
        token_usage=state.get("token_usage"),
    )

    logger.info(
        "agent.outline_generated",
        sections=len(outline.get("sections", [])),
    )

    return {
        "outline": outline,
        "token_usage": token_usage,
        "current_phase": "outline_review",
    }


async def write_review_node(
    state: ReviewState,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict:
    """Write full review node: outline + analyses → full_draft + references."""
    llm = llm or LLMRouter()
    prompt_manager = prompt_manager or PromptManager()

    outline = state.get("outline", {})
    analyses = state.get("paper_analyses", [])
    user_query = state.get("user_query", "")
    citation_style = state.get("citation_style", "apa")
    output_language = state.get("output_language", "zh")

    sections_content: list[dict] = []
    token_usage = state.get("token_usage")

    # Write each section sequentially
    for section in outline.get("sections", []):
        section_text, token_usage = await write_section(
            section=section,
            analyses=analyses,
            user_query=user_query,
            citation_style=citation_style,
            output_language=output_language,
            llm=llm,
            prompt_manager=prompt_manager,
            token_usage=token_usage,
        )

        sections_content.append({
            "heading": section.get("heading", ""),
            "content": section_text,
        })

        logger.info(
            "writer.section_complete",
            heading=section.get("heading", ""),
            chars=len(section_text),
        )

    # Assemble full draft
    title = outline.get("title", f"Literature Review: {user_query}")
    draft_parts = [f"# {title}\n"]
    for sec in sections_content:
        draft_parts.append(f"\n## {sec['heading']}\n\n{sec['content']}")
    full_draft = "\n".join(draft_parts)

    # Build references
    references = build_references_list(analyses, citation_style)

    # Add references section to draft
    if references:
        ref_lines = ["\n\n---\n\n## References\n"]
        for ref in references:
            ref_lines.append(f"[{ref['index']}] {ref['formatted']}")
        full_draft += "\n".join(ref_lines)

    logger.info(
        "agent.write_complete",
        sections=len(sections_content),
        chars=len(full_draft),
        references=len(references),
    )

    return {
        "draft_sections": sections_content,
        "full_draft": full_draft,
        "references": references,
        "token_usage": token_usage,
        "current_phase": "draft_review",
    }


async def revise_review_node(
    state: ReviewState,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict:
    """Revise the review based on user feedback.

    Uses the coherence reviewer with revision instructions as context.
    """
    llm = llm or LLMRouter()
    prompt_manager = prompt_manager or PromptManager()

    full_draft = state.get("full_draft", "")
    revision_instructions = state.get("revision_instructions", "")

    # Use section_writing prompt with revision context
    revision_prompt = (
        f"请根据以下修改意见修订综述全文。\n\n"
        f"## 修改意见\n{revision_instructions}\n\n"
        f"## 当前全文\n{full_draft[:12000]}\n\n"
        f"请输出修订后的完整综述文本（Markdown 格式）。"
    )

    revised_text, token_usage = await llm.call(
        prompt=revision_prompt,
        agent_name="writer",
        task_type="section_writing",
        token_usage=state.get("token_usage"),
    )

    logger.info("agent.revise_complete", chars=len(revised_text))

    return {
        "full_draft": revised_text.strip(),
        "revision_instructions": "",  # clear after processing
        "token_usage": token_usage,
        "current_phase": "draft_review",
    }


# ── Utilities ──


def _parse_json_response(response_text: str, fallback: dict) -> dict:
    """Parse JSON from LLM response with fallback."""
    try:
        text = response_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.warning("writer.json_parse_failed")
        return fallback


# ── Register all writer nodes ──

agent_registry.register("generate_outline", generate_outline_node)
agent_registry.register("write_review", write_review_node)
agent_registry.register("revise_review", revise_review_node)
