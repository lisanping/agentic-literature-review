"""CLI client for the agentic literature review system — §9.1."""

import asyncio
import json
import sys

import click
import structlog

logger = structlog.stdlib.get_logger()


@click.group()
def cli():
    """Agentic Literature Review — CLI interface."""
    pass


@cli.command()
@click.argument("query")
@click.option("--language", "-l", default="zh", type=click.Choice(["zh", "en", "bilingual"]))
@click.option("--style", "-s", default="apa", type=click.Choice(["apa", "ieee", "gbt7714"]))
@click.option("--output-type", "-t", default="full_review")
@click.option("--budget", "-b", type=int, default=None, help="Token budget limit")
def review(query: str, language: str, style: str, output_type: str, budget: int | None):
    """Run a complete literature review for QUERY."""
    click.echo(f"Starting literature review: {query}")
    click.echo(f"  Language: {language}, Style: {style}, Type: {output_type}")
    if budget:
        click.echo(f"  Token budget: {budget:,}")

    asyncio.run(_run_review(query, language, style, output_type, budget))


async def _run_review(
    query: str, language: str, style: str, output_type: str, budget: int | None
):
    """Execute the review workflow with interactive HITL prompts."""
    from app.agents.orchestrator import compile_review_graph
    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()
    graph = compile_review_graph(checkpointer=checkpointer)
    thread_config = {"configurable": {"thread_id": "cli-session"}}

    initial_state = {
        "user_query": query,
        "output_types": [output_type],
        "output_language": language,
        "citation_style": style,
        "token_budget": budget,
        "uploaded_papers": [],
        "feedback_iteration_count": 0,
        "feedback_search_queries": [],
        "error_log": [],
    }

    click.echo("\n--- Phase 1: Intent Parsing + Search ---")
    result = await graph.ainvoke(initial_state, config=thread_config)

    # HITL 1: Search review
    candidates = result.get("candidate_papers", [])
    click.echo(f"\nFound {len(candidates)} candidate papers:")
    for i, p in enumerate(candidates[:20], 1):
        title = p.get("title", "?")[:70]
        year = p.get("year", "?")
        cits = p.get("citation_count", 0)
        click.echo(f"  [{i}] ({year}) {title}  [cited: {cits}]")
    if len(candidates) > 20:
        click.echo(f"  ... and {len(candidates) - 20} more")

    # Interactive selection
    action = click.prompt(
        "\nSelect papers (all / exclude 3,7 / add \"query\")",
        default="all",
    )
    selected = candidates
    state_update = {}
    if action.startswith("exclude"):
        try:
            indices = [int(x.strip()) - 1 for x in action.replace("exclude", "").split(",")]
            selected = [p for i, p in enumerate(candidates) if i not in indices]
        except ValueError:
            pass
        state_update = {"selected_papers": selected, "needs_more_search": False}
    elif action.startswith("add"):
        extra_query = action.replace("add", "").strip().strip('"').strip("'")
        state_update = {
            "selected_papers": candidates,
            "needs_more_search": True,
            "feedback_search_queries": [extra_query],
        }
    else:
        state_update = {"selected_papers": candidates, "needs_more_search": False}

    await graph.aupdate_state(
        thread_config, state_update, as_node="human_review_search"
    )

    click.echo(f"\n--- Phase 2: Reading {len(selected)} papers ---")
    result = await graph.ainvoke(None, config=thread_config)

    # HITL 2: Outline review
    outline = result.get("outline", {})
    click.echo("\nGenerated outline:")
    for i, sec in enumerate(outline.get("sections", []), 1):
        click.echo(f"  {i}. {sec.get('heading', '?')} — {sec.get('description', '')}")

    outline_action = click.prompt("\nApprove outline? (yes / retry \"instruction\")", default="yes")
    if outline_action.startswith("retry"):
        instruction = outline_action.replace("retry", "").strip().strip('"')
        click.echo(f"  Re-generating outline with: {instruction}")

    await graph.aupdate_state(thread_config, {}, as_node="human_review_outline")

    click.echo("\n--- Phase 3: Writing + Citation Verification ---")
    result = await graph.ainvoke(None, config=thread_config)

    # HITL 3: Draft review
    draft = result.get("full_draft", "")
    click.echo(f"\nGenerated draft ({len(draft)} chars)")

    # Citation verification summary
    verifications = result.get("citation_verification", [])
    verified = sum(1 for v in verifications if v.get("status") == "verified")
    total = len(verifications)
    if total:
        click.echo(f"  Citations: {verified}/{total} verified ✅, {total - verified} unconfirmed ⚠️")

    # Coverage
    coverage = result.get("fulltext_coverage", {})
    if coverage:
        click.echo(
            f"  Coverage: fulltext {coverage.get('fulltext_count', 0)} / "
            f"abstract-only {coverage.get('abstract_only_count', 0)}"
        )

    draft_action = click.prompt("\nApprove draft? (yes / revise \"instruction\")", default="yes")
    if draft_action.startswith("revise"):
        instruction = draft_action.replace("revise", "").strip().strip('"')
        await graph.aupdate_state(
            thread_config,
            {"revision_instructions": instruction},
            as_node="human_review_draft",
        )
    else:
        await graph.aupdate_state(
            thread_config, {"revision_instructions": ""}, as_node="human_review_draft"
        )

    click.echo("\n--- Phase 4: Export ---")
    result = await graph.ainvoke(None, config=thread_config)

    final = result.get("final_output", "")

    # Token usage
    usage = result.get("token_usage", {})
    if usage:
        total_in = usage.get("total_input", 0)
        total_out = usage.get("total_output", 0)
        click.echo(f"\nToken usage: input={total_in:,} output={total_out:,} total={total_in + total_out:,}")

    # Save output
    output_file = "review_output.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final)
    click.echo(f"\n✅ Review saved to {output_file}")

    # Save references as BibTeX
    refs = result.get("references", [])
    if refs:
        from app.services.export import export_bibtex

        bib = export_bibtex(refs)
        bib_file = "references.bib"
        with open(bib_file, "w", encoding="utf-8") as f:
            f.write(bib)
        click.echo(f"✅ References saved to {bib_file}")


@cli.command()
@click.argument("project_id")
def status(project_id: str):
    """Show project workflow status."""
    click.echo(f"Querying status for project: {project_id}")
    # In full implementation, would query the API
    click.echo("(Requires running API server)")


if __name__ == "__main__":
    cli()
