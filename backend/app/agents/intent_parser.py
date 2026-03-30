"""parse_intent node — LLM-based user intent parsing and search strategy generation."""

import json

import structlog

from app.agents.registry import agent_registry
from app.agents.state import ReviewState
from app.services.llm import LLMRouter
from app.services.prompt_manager import PromptManager

logger = structlog.stdlib.get_logger()


async def parse_intent_node(
    state: ReviewState,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict:
    """Parse user query into a structured search strategy.

    Uses LLM to analyze the research question and generate:
    - Multiple complementary search queries
    - Key concepts
    - Suggested filters (year range, citation threshold, etc.)

    Returns:
        Partial state update with ``search_strategy`` and ``current_phase``.
    """
    llm = llm or LLMRouter()
    prompt_manager = prompt_manager or PromptManager()

    user_query = state["user_query"]
    output_language = state.get("output_language", "zh")

    prompt = prompt_manager.render(
        "search",
        "query_planning",
        user_query=user_query,
        output_language=output_language,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="search",
        task_type="query_planning",
        token_usage=state.get("token_usage"),
    )

    # Parse the LLM JSON response
    search_strategy = _parse_strategy_response(response_text, user_query)

    logger.info(
        "agent.parse_intent",
        query_count=len(search_strategy.get("queries", [])),
        concepts=search_strategy.get("key_concepts", []),
    )

    return {
        "search_strategy": search_strategy,
        "token_usage": token_usage,
        "current_phase": "searching",
    }


def _parse_strategy_response(response_text: str, user_query: str) -> dict:
    """Parse LLM response into a search strategy dict.

    Falls back to a simple strategy if JSON parsing fails.
    """
    try:
        # Try to extract JSON from the response
        text = response_text.strip()
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        strategy = json.loads(text)
        # Ensure required keys exist
        if "queries" not in strategy:
            strategy["queries"] = [{"query": user_query, "purpose": "direct query"}]
        return strategy
    except (json.JSONDecodeError, IndexError, KeyError):
        logger.warning("agent.parse_intent.json_parse_failed", response=response_text[:200])
        return {
            "queries": [{"query": user_query, "purpose": "direct query"}],
            "key_concepts": [],
            "suggested_filters": {},
        }


agent_registry.register("parse_intent", parse_intent_node)
