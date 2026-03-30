"""Prompt template loading and rendering — aligned with §10.6."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from app.config import settings


class PromptManager:
    """Load and render Jinja2 prompt templates from the prompts directory.

    Templates are organized as ``{agent_name}/{task_type}.md`` under the
    configured ``PROMPTS_DIR``.
    """

    def __init__(self, prompts_dir: str | None = None):
        self.prompts_dir = Path(prompts_dir or settings.PROMPTS_DIR)
        self.env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            autoescape=False,  # Prompts don't need HTML escaping
            keep_trailing_newline=True,
        )

    def render(self, agent_name: str, task_type: str, **kwargs) -> str:
        """Load and render a prompt template.

        Args:
            agent_name: Agent name (subdirectory, e.g. "search").
            task_type: Task type (filename without extension, e.g. "query_planning").
            **kwargs: Template variables.

        Returns:
            Rendered prompt text.

        Raises:
            TemplateNotFound: If the template file does not exist.
        """
        template_path = f"{agent_name}/{task_type}.md"
        template = self.env.get_template(template_path)
        return template.render(**kwargs)

    def has_template(self, agent_name: str, task_type: str) -> bool:
        """Check whether a template file exists."""
        template_path = self.prompts_dir / agent_name / f"{task_type}.md"
        return template_path.is_file()
