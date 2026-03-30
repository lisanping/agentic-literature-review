"""Tests for PromptManager — template loading and rendering."""

import os
import tempfile
from pathlib import Path

from app.services.prompt_manager import PromptManager


def _create_test_prompts_dir():
    """Create a temp directory with test prompt templates."""
    tmpdir = tempfile.mkdtemp()
    agent_dir = Path(tmpdir) / "test_agent"
    agent_dir.mkdir()
    (agent_dir / "greet.md").write_text(
        "Hello {{ name }}, welcome to {{ project }}!"
    )
    (agent_dir / "list.md").write_text(
        "Items:\n{% for item in items %}- {{ item }}\n{% endfor %}"
    )
    return tmpdir


def test_render_simple_template():
    tmpdir = _create_test_prompts_dir()
    pm = PromptManager(prompts_dir=tmpdir)
    result = pm.render("test_agent", "greet", name="Alice", project="ALR")
    assert "Hello Alice" in result
    assert "welcome to ALR" in result


def test_render_loop_template():
    tmpdir = _create_test_prompts_dir()
    pm = PromptManager(prompts_dir=tmpdir)
    result = pm.render("test_agent", "list", items=["A", "B", "C"])
    assert "- A" in result
    assert "- B" in result
    assert "- C" in result


def test_has_template():
    tmpdir = _create_test_prompts_dir()
    pm = PromptManager(prompts_dir=tmpdir)
    assert pm.has_template("test_agent", "greet") is True
    assert pm.has_template("test_agent", "nonexistent") is False
    assert pm.has_template("nonexistent_agent", "greet") is False


def test_render_real_prompts():
    """Verify the actual MVP prompt templates can be loaded and rendered."""
    prompts_dir = Path(__file__).parent.parent / "prompts"
    if not prompts_dir.exists():
        return  # Skip if running from different CWD
    pm = PromptManager(prompts_dir=str(prompts_dir))

    # search/query_planning
    result = pm.render(
        "search", "query_planning",
        user_query="LLM in code generation",
        output_language="zh",
    )
    assert "LLM in code generation" in result
    assert "JSON" in result

    # reader/info_extraction
    result = pm.render(
        "reader", "info_extraction",
        title="Test Paper",
        authors="Author A, Author B",
        year=2024,
        content="This paper studies...",
        user_query="deep learning",
    )
    assert "Test Paper" in result

    # writer/outline
    result = pm.render(
        "writer", "outline",
        user_query="test query",
        output_type="full_review",
        analyses=[{"title": "Paper 1", "objective": "Test", "methodology": "DL", "findings": "Good", "key_concepts": ["A"]}],
        output_language="zh",
    )
    assert "Paper 1" in result
