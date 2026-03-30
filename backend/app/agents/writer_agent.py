"""Writer Agent — outline generation, section writing, citation formatting, coherence review.

Components (aligned with §5.5, enhanced in v0.3 §4):
  - Outline Generator: create structured outline from analyses + topic_clusters
  - Section Writer: write each section with proper citations + analyst/critic context
  - Citation Formatter: insert citation marks and build reference list
  - Coherence Reviewer: LLM full-draft coherence check
  - Specialized Output Writers: methodology_review, gap_report, trend_report, research_roadmap
  - Citation Weight Strategy: quality_score ≥ 0.7 prioritized, < 0.3 downgraded

Node functions:
  - generate_outline_node: analyses + clusters → outline
  - write_review_node: outline + analyses + analyst/critic data → full_draft + references
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

# Citation weight thresholds
QUALITY_HIGH_THRESHOLD = 0.7
QUALITY_LOW_THRESHOLD = 0.3

# Output types that use specialized writers (not outline → section flow)
SPECIALIZED_OUTPUT_TYPES = {
    "methodology_review",
    "gap_report",
    "trend_report",
    "research_roadmap",
}


# ── Outline Generator ──


async def generate_outline(
    analyses: list[dict],
    user_query: str,
    output_type: str,
    output_language: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
    topic_clusters: list[dict] | None = None,
) -> tuple[dict, dict]:
    """Generate a structured outline from paper analyses + topic clusters.

    When topic_clusters are available, they are passed to the prompt so the
    LLM can organize sections around thematic clusters.

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
        topic_clusters=topic_clusters or [],
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
    comparison_matrix: dict | None = None,
    contradictions: list[dict] | None = None,
    research_trends: dict | None = None,
) -> tuple[str, dict]:
    """Write a single section of the review.

    Analyst/Critic context (comparison_matrix, contradictions, research_trends)
    is passed to the prompt when available so the LLM can integrate structured
    analysis data into the narrative.

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
        comparison_matrix=comparison_matrix or {},
        contradictions=contradictions or [],
        research_trends=research_trends or {},
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


# ── Citation Weight Strategy ──


def apply_citation_weights(
    analyses: list[dict],
    quality_assessments: list[dict],
) -> list[dict]:
    """Reorder analyses by quality score: high-quality papers first.

    Papers with quality_score ≥ QUALITY_HIGH_THRESHOLD are prioritized.
    Papers with quality_score < QUALITY_LOW_THRESHOLD are moved to the end.
    Papers without a quality assessment keep their original position.

    Returns:
        A new list of analyses sorted by citation priority.
    """
    if not quality_assessments:
        return analyses

    # Build quality lookup
    quality_map: dict[str, float] = {}
    for qa in quality_assessments:
        pid = qa.get("paper_id", "")
        quality_map[pid] = qa.get("quality_score", 0.5)

    def _sort_key(analysis: dict) -> tuple[int, float]:
        pid = analysis.get("paper_id", "")
        score = quality_map.get(pid, 0.5)
        if score >= QUALITY_HIGH_THRESHOLD:
            tier = 0  # first
        elif score < QUALITY_LOW_THRESHOLD:
            tier = 2  # last
        else:
            tier = 1  # middle
        return (tier, -score)

    return sorted(analyses, key=_sort_key)


# ── Specialized Output Writers ──


async def write_specialized_output(
    output_type: str,
    analyses: list[dict],
    user_query: str,
    output_language: str,
    state: ReviewState,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[str, dict]:
    """Write a specialized output type using its dedicated prompt template.

    Supported types: methodology_review, gap_report, trend_report, research_roadmap.

    Returns:
        (full_text_markdown, updated_token_usage)
    """
    template_vars: dict = {
        "user_query": user_query,
        "analyses": analyses,
        "output_language": output_language,
    }

    if output_type == "methodology_review":
        template_vars["comparison_matrix"] = state.get("comparison_matrix", {})

    elif output_type == "gap_report":
        template_vars["research_gaps"] = state.get("research_gaps", [])
        template_vars["contradictions"] = state.get("contradictions", [])
        template_vars["limitation_summary"] = state.get("limitation_summary", "")
        template_vars["topic_clusters"] = state.get("topic_clusters", [])

    elif output_type == "trend_report":
        template_vars["research_trends"] = state.get("research_trends", {})
        template_vars["timeline"] = state.get("timeline", [])

    elif output_type == "research_roadmap":
        template_vars["topic_clusters"] = state.get("topic_clusters", [])
        template_vars["research_gaps"] = state.get("research_gaps", [])
        template_vars["research_trends"] = state.get("research_trends", {})
        template_vars["timeline"] = state.get("timeline", [])

    prompt = prompt_manager.render("writer", output_type, **template_vars)

    content, token_usage = await llm.call(
        prompt=prompt,
        agent_name="writer",
        task_type="section_writing",
        token_usage=token_usage,
    )

    logger.info(
        "writer.specialized_output",
        output_type=output_type,
        chars=len(content),
    )
    return content.strip(), token_usage


# ── Node Functions ──


async def generate_outline_node(
    state: ReviewState,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict:
    """Generate outline node: analyses + clusters → structured outline.

    When topic_clusters are available (from Analyst), they are passed to the
    LLM so it can organize the outline around thematic clusters.
    """
    llm = llm or LLMRouter()
    prompt_manager = prompt_manager or PromptManager()

    analyses = state.get("paper_analyses", [])
    output_types = state.get("output_types", ["full_review"])
    output_type = output_types[0] if output_types else "full_review"
    topic_clusters = state.get("topic_clusters", [])

    outline, token_usage = await generate_outline(
        analyses=analyses,
        user_query=state.get("user_query", ""),
        output_type=output_type,
        output_language=state.get("output_language", "zh"),
        llm=llm,
        prompt_manager=prompt_manager,
        token_usage=state.get("token_usage"),
        topic_clusters=topic_clusters,
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
    """Write full review node: outline + analyses + analyst/critic data → draft.

    v0.3 enhancements:
    - Citation weight strategy: reorders analyses by quality_score
    - Passes comparison_matrix, contradictions, research_trends to section writer
    - Specialized output types (methodology_review, gap_report, etc.) use dedicated prompts
    - Auto-appends "Research Gaps & Future Directions" section for full_review
    """
    llm = llm or LLMRouter()
    prompt_manager = prompt_manager or PromptManager()

    outline = state.get("outline", {})
    analyses = state.get("paper_analyses", [])
    user_query = state.get("user_query", "")
    citation_style = state.get("citation_style", "apa")
    output_language = state.get("output_language", "zh")
    output_types = state.get("output_types", ["full_review"])
    output_type = output_types[0] if output_types else "full_review"

    # Analyst/Critic context
    comparison_matrix = state.get("comparison_matrix")
    contradictions = state.get("contradictions", [])
    research_trends = state.get("research_trends")
    research_gaps = state.get("research_gaps", [])
    limitation_summary = state.get("limitation_summary", "")
    quality_assessments = state.get("quality_assessments", [])

    # Apply citation weights
    weighted_analyses = apply_citation_weights(analyses, quality_assessments)

    token_usage = state.get("token_usage")

    # Specialized output types use a single dedicated prompt
    if output_type in SPECIALIZED_OUTPUT_TYPES:
        full_draft, token_usage = await write_specialized_output(
            output_type=output_type,
            analyses=weighted_analyses,
            user_query=user_query,
            output_language=output_language,
            state=state,
            llm=llm,
            prompt_manager=prompt_manager,
            token_usage=token_usage,
        )

        references = build_references_list(weighted_analyses, citation_style)

        # Add references section
        if references:
            ref_lines = ["\n\n---\n\n## References\n"]
            for ref in references:
                ref_lines.append(f"[{ref['index']}] {ref['formatted']}")
            full_draft += "\n".join(ref_lines)

        logger.info(
            "agent.write_complete",
            output_type=output_type,
            chars=len(full_draft),
            references=len(references),
        )

        return {
            "draft_sections": [{"heading": output_type, "content": full_draft}],
            "full_draft": full_draft,
            "references": references,
            "token_usage": token_usage,
            "current_phase": "draft_review",
        }

    # Standard outline → section flow for full_review etc.
    sections_content: list[dict] = []

    for section in outline.get("sections", []):
        section_text, token_usage = await write_section(
            section=section,
            analyses=weighted_analyses,
            user_query=user_query,
            citation_style=citation_style,
            output_language=output_language,
            llm=llm,
            prompt_manager=prompt_manager,
            token_usage=token_usage,
            comparison_matrix=comparison_matrix,
            contradictions=contradictions,
            research_trends=research_trends,
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

    # Auto-generate Research Gaps section if gaps are available
    if research_gaps and output_type == "full_review":
        gaps_section = _build_gaps_section(research_gaps, limitation_summary)
        sections_content.append({
            "heading": "Research Gaps & Future Directions",
            "content": gaps_section,
        })

    # Assemble full draft
    title = outline.get("title", f"Literature Review: {user_query}")
    draft_parts = [f"# {title}\n"]
    for sec in sections_content:
        draft_parts.append(f"\n## {sec['heading']}\n\n{sec['content']}")
    full_draft = "\n".join(draft_parts)

    # Build references
    references = build_references_list(weighted_analyses, citation_style)

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


def _build_gaps_section(
    research_gaps: list[dict],
    limitation_summary: str,
) -> str:
    """Build a Research Gaps & Future Directions section from Critic output.

    This is an algorithmic assembly (no LLM call) that formats the
    structured gap data into readable markdown.
    """
    parts: list[str] = []

    if research_gaps:
        for i, gap in enumerate(research_gaps, 1):
            priority = gap.get("priority", "medium")
            priority_label = {"high": "🔴 高", "medium": "🟡 中", "low": "🟢 低"}.get(
                priority, priority
            )
            parts.append(f"### {i}. {gap.get('description', '')}")
            parts.append(f"- **优先级**: {priority_label}")
            evidence = gap.get("evidence", [])
            if evidence:
                parts.append(f"- **证据**: {'; '.join(evidence)}")
            direction = gap.get("suggested_direction", "")
            if direction:
                parts.append(f"- **建议方向**: {direction}")
            parts.append("")

    if limitation_summary:
        parts.append("### 共性局限总结\n")
        parts.append(limitation_summary)
        parts.append("")

    return "\n".join(parts) if parts else "暂无研究空白数据。"


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
