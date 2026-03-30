"""LLM multi-model router with token tracking and fallback — aligned with §10.5."""

from dataclasses import dataclass, field
from typing import Any

import structlog
from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

logger = structlog.stdlib.get_logger()

# ── Model configuration ──


@dataclass
class ModelConfig:
    """Configuration for a single LLM model."""

    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.3
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0


# ── Default model configs ──

DEFAULT_MODEL_CONFIGS: dict[str, ModelConfig] = {
    "gpt-4o": ModelConfig(
        model_name="gpt-4o",
        max_tokens=4096,
        temperature=0.3,
        cost_per_1k_input=2.50,
        cost_per_1k_output=10.00,
    ),
    "gpt-4o-mini": ModelConfig(
        model_name="gpt-4o-mini",
        max_tokens=4096,
        temperature=0.3,
        cost_per_1k_input=0.15,
        cost_per_1k_output=0.60,
    ),
}

# ── Default routing table: agent → task_type → model_name ──

DEFAULT_MODEL_ROUTING: dict[str, dict[str, str]] = {
    "search": {
        "query_planning": "gpt-4o-mini",
        "relevance_ranking": "gpt-4o-mini",
    },
    "reader": {
        "info_extraction": "gpt-4o",
        "relation_detection": "gpt-4o-mini",
    },
    "analyst": {
        "topic_clustering": "gpt-4o",
        "comparison": "gpt-4o",
    },
    "critic": {
        "quality_assessment": "gpt-4o",
        "gap_identification": "gpt-4o",
    },
    "writer": {
        "outline": "gpt-4o",
        "section_writing": "gpt-4o",
        "coherence_review": "gpt-4o",
    },
}

# ── Fallback table ──

FALLBACK_MODELS: dict[str, str | None] = {
    "gpt-4o": "gpt-4o-mini",
    "gpt-4o-mini": None,
}


def update_token_usage(
    current: dict | None,
    agent: str,
    input_tokens: int,
    output_tokens: int,
) -> dict:
    """Accumulate token usage, both total and per-agent."""
    usage = dict(current) if current else {
        "total_input": 0,
        "total_output": 0,
        "by_agent": {},
    }
    usage["total_input"] = usage.get("total_input", 0) + input_tokens
    usage["total_output"] = usage.get("total_output", 0) + output_tokens

    by_agent = usage.get("by_agent", {})
    agent_usage = by_agent.get(agent, {"input": 0, "output": 0})
    agent_usage["input"] = agent_usage.get("input", 0) + input_tokens
    agent_usage["output"] = agent_usage.get("output", 0) + output_tokens
    by_agent[agent] = agent_usage
    usage["by_agent"] = by_agent
    return usage


class LLMRouter:
    """Route LLM calls to the optimal model based on agent and task type.

    Features:
    - Multi-model routing via configurable routing table
    - Automatic token usage tracking
    - Fallback to smaller model on failure
    """

    def __init__(
        self,
        model_configs: dict[str, ModelConfig] | None = None,
        routing_table: dict[str, dict[str, str]] | None = None,
        default_model: str = "gpt-4o",
        api_key: str | None = None,
    ):
        self.model_configs = model_configs or DEFAULT_MODEL_CONFIGS
        self.routing_table = routing_table or DEFAULT_MODEL_ROUTING
        self.default_model = default_model
        self._client = AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)

    def resolve_model(self, agent_name: str, task_type: str) -> ModelConfig:
        """Resolve the model config for a given agent and task type."""
        model_name = (
            self.routing_table.get(agent_name, {}).get(
                task_type, self.default_model
            )
        )
        return self.model_configs.get(
            model_name, self.model_configs[self.default_model]
        )

    async def call(
        self,
        prompt: str,
        agent_name: str,
        task_type: str,
        token_usage: dict | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, dict]:
        """Unified LLM call entry: auto-routes model + tracks tokens.

        Returns:
            (response_text, updated_token_usage)
        """
        config = self.resolve_model(agent_name, task_type)
        return await self._call_with_fallback(
            config=config,
            prompt=prompt,
            agent_name=agent_name,
            token_usage=token_usage,
            system_prompt=system_prompt,
            **kwargs,
        )

    async def _call_with_fallback(
        self,
        config: ModelConfig,
        prompt: str,
        agent_name: str,
        token_usage: dict | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, dict]:
        """Call LLM with automatic fallback on failure."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._do_call(config, messages, **kwargs)
        except Exception as exc:
            fallback_name = FALLBACK_MODELS.get(config.model_name)
            if fallback_name and fallback_name in self.model_configs:
                logger.warning(
                    "llm.fallback",
                    primary=config.model_name,
                    fallback=fallback_name,
                    error=str(exc),
                )
                fallback_config = self.model_configs[fallback_name]
                response = await self._do_call(
                    fallback_config, messages, **kwargs
                )
            else:
                raise

        usage = response.usage
        token_update = update_token_usage(
            current=token_usage,
            agent=agent_name,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

        logger.info(
            "llm.call",
            agent=agent_name,
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

        return response.choices[0].message.content or "", token_update

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    )
    async def _do_call(
        self, config: ModelConfig, messages: list[dict], **kwargs: Any
    ):
        """Execute the actual OpenAI API call with retry."""
        return await self._client.chat.completions.create(
            model=config.model_name,
            messages=messages,
            max_tokens=kwargs.pop("max_tokens", config.max_tokens),
            temperature=kwargs.pop("temperature", config.temperature),
            **kwargs,
        )
