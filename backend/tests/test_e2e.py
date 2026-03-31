"""End-to-end integration test — mock LLM, full workflow via API.

Tests the complete lifecycle:
  Create project → Start workflow → HITL search review → HITL outline review →
  HITL draft review → Export → Verify final output

All LLM calls are mocked. Uses an in-memory SQLite database.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models.database import Base


# ═══════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════


@pytest.fixture
async def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(test_db):
    """Create a test client with the in-memory DB injected."""
    from app.api.deps import get_db

    async def override_get_db():
        async with test_db() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════
#  Project CRUD e2e
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_project_crud_lifecycle(client):
    """Create → Get → Update → List → Delete lifecycle."""
    # Create
    resp = await client.post(
        "/api/v1/projects",
        json={"user_query": "LLM in code generation"},
    )
    assert resp.status_code == 201
    project = resp.json()
    project_id = project["id"]
    assert project["user_query"] == "LLM in code generation"
    assert project["status"] == "created"
    assert project["output_language"] == "zh"
    assert project["citation_style"] == "apa"

    # Get
    resp = await client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == project_id

    # Update
    resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"token_budget": 10000},
    )
    assert resp.status_code == 200
    assert resp.json()["token_budget"] == 10000

    # List
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1

    # List with pagination
    resp = await client.get("/api/v1/projects?page=1&size=5")
    assert resp.status_code == 200
    assert resp.json()["size"] == 5

    # Delete
    resp = await client.delete(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 204

    # Get after delete → 404
    resp = await client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_project_not_found(client):
    resp = await client.get("/api/v1/projects/nonexistent-id")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_project_validation(client):
    # Query too short (min_length=2)
    resp = await client.post(
        "/api/v1/projects",
        json={"user_query": "X"},
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════
#  Workflow status + cancel
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_workflow_status_and_cancel(client):
    """Create project → check status → cancel."""
    resp = await client.post(
        "/api/v1/projects",
        json={"user_query": "Test workflow control"},
    )
    project_id = resp.json()["id"]

    # Status
    resp = await client.get(f"/api/v1/projects/{project_id}/workflow/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"

    # Cancel
    resp = await client.post(f"/api/v1/projects/{project_id}/workflow/cancel")
    assert resp.status_code == 204

    # Status after cancel
    resp = await client.get(f"/api/v1/projects/{project_id}/workflow/status")
    assert resp.json()["status"] == "cancelled"


# ═══════════════════════════════════════════════
#  Workflow start (mock Celery)
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_workflow_start_dispatches_celery(client):
    """Starting a workflow should dispatch a Celery task."""
    resp = await client.post(
        "/api/v1/projects",
        json={"user_query": "Test dispatch"},
    )
    project_id = resp.json()["id"]

    with patch("app.tasks.run_review_segment") as mock_task:
        mock_result = MagicMock()
        mock_result.id = "celery-task-123"
        mock_task.delay.return_value = mock_result

        resp = await client.post(
            f"/api/v1/projects/{project_id}/workflow/start"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "celery-task-123"
        assert data["status"] == "started"

        # Verify Celery was called with correct args
        mock_task.delay.assert_called_once()
        call_kwargs = mock_task.delay.call_args
        assert call_kwargs.kwargs["project_id"] == project_id
        assert call_kwargs.kwargs["resume"] is False


@pytest.mark.asyncio
async def test_workflow_start_conflict(client):
    """Starting a workflow twice should return 409."""
    resp = await client.post(
        "/api/v1/projects",
        json={"user_query": "Test conflict"},
    )
    project_id = resp.json()["id"]

    with patch("app.tasks.run_review_segment") as mock_task:
        mock_result = MagicMock()
        mock_result.id = "task-1"
        mock_task.delay.return_value = mock_result

        # First start
        await client.post(f"/api/v1/projects/{project_id}/workflow/start")

        # Second start → conflict
        resp = await client.post(
            f"/api/v1/projects/{project_id}/workflow/start"
        )
        assert resp.status_code == 409


# ═══════════════════════════════════════════════
#  Workflow resume (mock Celery)
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_workflow_resume_search_review(client):
    """Resume after search review should dispatch Celery with HITL state."""
    resp = await client.post(
        "/api/v1/projects",
        json={"user_query": "Test resume"},
    )
    project_id = resp.json()["id"]

    with patch("app.tasks.run_review_segment") as mock_task:
        mock_result = MagicMock()
        mock_result.id = "task-resume-1"
        mock_task.delay.return_value = mock_result

        resp = await client.post(
            f"/api/v1/projects/{project_id}/workflow/resume",
            json={
                "hitl_type": "search_review",
                "selected_paper_ids": ["p1", "p2"],
                "approved": True,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resumed"

        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs["resume"] is True
        assert call_kwargs["config"]["hitl_type"] == "search_review"


@pytest.mark.asyncio
async def test_workflow_resume_draft_review_with_revision(client):
    """Resume with revision instructions should pass them through."""
    resp = await client.post(
        "/api/v1/projects",
        json={"user_query": "Test revision"},
    )
    project_id = resp.json()["id"]

    with patch("app.tasks.run_review_segment") as mock_task:
        mock_result = MagicMock()
        mock_result.id = "task-2"
        mock_task.delay.return_value = mock_result

        resp = await client.post(
            f"/api/v1/projects/{project_id}/workflow/resume",
            json={
                "hitl_type": "draft_review",
                "revision_instructions": "Fix the introduction",
                "approved": False,
            },
        )
        assert resp.status_code == 200
        config = mock_task.delay.call_args.kwargs["config"]
        assert config["revision_instructions"] == "Fix the introduction"


# ═══════════════════════════════════════════════
#  Output & export
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_output_list_empty(client):
    resp = await client.post(
        "/api/v1/projects",
        json={"user_query": "Test outputs"},
    )
    project_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}/outputs")
    assert resp.status_code == 200
    assert resp.json() == []


# ═══════════════════════════════════════════════
#  Full workflow e2e (mock agents, no Celery)
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_full_workflow_e2e_mock_agents():
    """Run the complete LangGraph workflow with mock agents end-to-end.

    This tests the actual graph execution (not API), verifying the DAG
    flows correctly through all nodes including HITL pause/resume.
    """
    from langgraph.checkpoint.memory import MemorySaver

    from app.agents.orchestrator import build_review_graph
    from app.agents.registry import AgentRegistry

    # Build mock registry
    reg = AgentRegistry()

    async def _parse_intent(state):
        return {
            "search_strategy": {"queries": [{"query": state["user_query"]}], "key_concepts": ["LLM"]},
            "current_phase": "searching",
        }

    async def _search(state):
        return {
            "candidate_papers": [
                {"title": "Paper A", "s2_id": "s2-1", "authors": ["Author A"], "year": 2024, "citation_count": 100},
                {"title": "Paper B", "s2_id": "s2-2", "authors": ["Author B"], "year": 2023, "citation_count": 50},
                {"title": "Paper C", "s2_id": "s2-3", "authors": ["Author C"], "year": 2025, "citation_count": 200},
            ],
            "current_phase": "search_review",
            "feedback_search_queries": [],
        }

    async def _human_review_search(state):
        return {"current_phase": "search_review"}

    async def _read(state):
        papers = state.get("selected_papers", [])
        return {
            "paper_analyses": [
                {
                    "paper_id": p.get("s2_id", str(i)),
                    "title": p.get("title", ""),
                    "objective": f"Study on {p.get('title', '')}",
                    "methodology": "Experimental",
                    "findings": "Significant results",
                    "limitations": "Small sample",
                    "key_concepts": ["LLM"],
                    "method_category": "ml",
                    "datasets": ["dataset-1"],
                    "authors": p.get("authors", []),
                    "year": p.get("year"),
                }
                for i, p in enumerate(papers)
            ],
            "feedback_search_queries": [],
            "current_phase": "outlining",
            "fulltext_coverage": {"total": len(papers), "fulltext_count": 0, "abstract_only_count": len(papers)},
            "reading_progress": {"total": len(papers), "completed": len(papers)},
        }

    async def _check_read_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        if feedback:
            count = state.get("feedback_iteration_count", 0)
            return {"feedback_iteration_count": count + 1}
        return {}

    async def _analyze(state):
        return {
            "topic_clusters": [{"id": "c0", "name": "Cluster", "paper_ids": [], "paper_count": 0}],
            "comparison_matrix": {"title": "M", "dimensions": [], "methods": [], "narrative": ""},
            "citation_network": {"nodes": [], "edges": [], "key_papers": [], "bridge_papers": []},
            "timeline": [],
            "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
            "current_phase": "critiquing",
        }

    async def _critique(state):
        return {
            "quality_assessments": [],
            "contradictions": [],
            "research_gaps": [],
            "limitation_summary": "",
            "feedback_search_queries": [],
            "current_phase": "outlining",
        }

    async def _check_critic_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        if feedback:
            count = state.get("feedback_iteration_count", 0)
            return {"feedback_iteration_count": count + 1}
        return {}

    async def _generate_outline(state):
        analyses = state.get("paper_analyses", [])
        return {
            "outline": {
                "title": "Literature Review: LLM in Code Generation",
                "sections": [
                    {"heading": "Introduction", "description": "Background", "relevant_paper_indices": []},
                    {"heading": "Methods", "description": "Approaches", "relevant_paper_indices": list(range(1, len(analyses) + 1))},
                    {"heading": "Results", "description": "Key findings", "relevant_paper_indices": list(range(1, len(analyses) + 1))},
                    {"heading": "Conclusion", "description": "Summary", "relevant_paper_indices": []},
                ],
            },
            "current_phase": "outline_review",
        }

    async def _human_review_outline(state):
        return {"current_phase": "writing"}

    async def _write_review(state):
        outline = state.get("outline", {})
        title = outline.get("title", "Review")
        sections = outline.get("sections", [])
        draft = f"# {title}\n\n"
        for sec in sections:
            draft += f"## {sec['heading']}\n\n{sec['description']} content...\n\n"
        return {
            "full_draft": draft,
            "draft_sections": [{"heading": s["heading"], "content": f"{s['description']} content..."} for s in sections],
            "references": [
                {"paper_id": a["paper_id"], "title": a["title"], "formatted": f"{', '.join(a.get('authors', ['?']))} ({a.get('year', '?')}). {a['title']}."}
                for a in state.get("paper_analyses", [])
            ],
            "current_phase": "verifying",
        }

    async def _verify_citations(state):
        refs = state.get("references", [])
        return {
            "citation_verification": [{"paper_id": r["paper_id"], "status": "verified"} for r in refs],
            "current_phase": "review_assessment",
        }

    async def _review_assessment(state):
        return {
            "review_scores": {"coherence": 7, "depth": 7, "rigor": 8, "utility": 7, "weighted": 7.2},
            "review_feedback": [],
            "current_phase": "draft_review",
        }

    async def _auto_revise(state):
        iteration = state.get("revision_iteration_count", 0)
        return {
            "full_draft": "# Auto-revised\n\nImproved.",
            "revision_iteration_count": iteration + 1,
            "current_phase": "review_assessment",
        }

    async def _human_review_draft(state):
        return {"current_phase": "draft_review"}

    async def _export(state):
        return {"final_output": state.get("full_draft", ""), "current_phase": "completed"}

    async def _revise_review(state):
        return {"full_draft": "# Revised\n\nImproved.", "revision_instructions": ""}

    reg.register("parse_intent", _parse_intent)
    reg.register("search", _search)
    reg.register("human_review_search", _human_review_search)
    reg.register("read", _read)
    reg.register("check_read_feedback", _check_read_feedback)
    reg.register("analyze", _analyze)
    reg.register("critique", _critique)
    reg.register("check_critic_feedback", _check_critic_feedback)
    reg.register("generate_outline", _generate_outline)
    reg.register("human_review_outline", _human_review_outline)
    reg.register("write_review", _write_review)
    reg.register("verify_citations", _verify_citations)
    reg.register("review_assessment", _review_assessment)
    reg.register("auto_revise", _auto_revise)
    reg.register("human_review_draft", _human_review_draft)
    reg.register("export", _export)
    reg.register("revise_review", _revise_review)

    graph = build_review_graph(registry=reg)
    checkpointer = MemorySaver()
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review_search", "human_review_outline", "human_review_draft"],
    )

    cfg = {"configurable": {"thread_id": "e2e-test"}}
    initial_state = {
        "user_query": "LLM in code generation",
        "output_language": "zh",
        "citation_style": "apa",
        "output_types": ["full_review"],
        "feedback_iteration_count": 0,
        "feedback_search_queries": [],
        "error_log": [],
    }

    # Step 1: parse_intent + search → pause at human_review_search
    result = await compiled.ainvoke(initial_state, config=cfg)
    assert len(result.get("candidate_papers", [])) == 3

    # Step 2: User selects all papers → resume
    await compiled.aupdate_state(
        cfg,
        {"selected_papers": result["candidate_papers"], "needs_more_search": False},
        as_node="human_review_search",
    )
    result = await compiled.ainvoke(None, config=cfg)
    assert result.get("outline") is not None
    assert len(result["outline"]["sections"]) == 4

    # Step 3: Approve outline → resume
    await compiled.aupdate_state(cfg, {}, as_node="human_review_outline")
    result = await compiled.ainvoke(None, config=cfg)
    assert "full_draft" in result
    assert len(result.get("references", [])) == 3
    assert len(result.get("citation_verification", [])) == 3
    assert all(v["status"] == "verified" for v in result["citation_verification"])

    # Step 4: Approve draft → export
    await compiled.aupdate_state(cfg, {"revision_instructions": ""}, as_node="human_review_draft")
    result = await compiled.ainvoke(None, config=cfg)
    assert result["current_phase"] == "completed"
    assert "final_output" in result
    assert "# Literature Review" in result["final_output"]

    # Verify the full pipeline produced expected artifacts
    assert result.get("reading_progress", {}).get("completed") == 3
    assert result.get("fulltext_coverage", {}).get("abstract_only_count") == 3


@pytest.mark.asyncio
async def test_full_workflow_e2e_with_revision():
    """E2E workflow where user requests a draft revision before export."""
    from langgraph.checkpoint.memory import MemorySaver
    from app.agents.orchestrator import build_review_graph
    from app.agents.registry import AgentRegistry

    reg = AgentRegistry()

    async def _parse_intent(state):
        return {"search_strategy": {"queries": [{"query": state["user_query"]}]}, "current_phase": "searching"}

    async def _search(state):
        return {"candidate_papers": [{"title": "P", "s2_id": "1", "authors": ["A"]}], "current_phase": "search_review", "feedback_search_queries": []}

    async def _human_review_search(state):
        return {"current_phase": "search_review"}

    async def _read(state):
        return {"paper_analyses": [{"paper_id": "1", "title": "P", "objective": "O"}], "feedback_search_queries": [], "current_phase": "outlining"}

    async def _check_read_feedback(state):
        return {}

    async def _analyze_stub(state):
        return {
            "topic_clusters": [], "comparison_matrix": {"title": "", "dimensions": [], "methods": [], "narrative": ""},
            "citation_network": {"nodes": [], "edges": [], "key_papers": [], "bridge_papers": []},
            "timeline": [], "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
            "current_phase": "critiquing",
        }

    async def _critique_stub(state):
        return {
            "quality_assessments": [], "contradictions": [], "research_gaps": [],
            "limitation_summary": "", "feedback_search_queries": [], "current_phase": "outlining",
        }

    async def _check_critic_feedback_stub(state):
        return {}

    async def _generate_outline(state):
        return {"outline": {"title": "Review", "sections": [{"heading": "Intro", "description": "Bg"}]}, "current_phase": "outline_review"}

    async def _human_review_outline(state):
        return {"current_phase": "writing"}

    async def _write_review(state):
        return {"full_draft": "# Original Draft", "references": [], "current_phase": "verifying"}

    async def _verify_citations(state):
        return {"citation_verification": [], "current_phase": "review_assessment"}

    async def _review_assessment(state):
        return {
            "review_scores": {"coherence": 7, "depth": 7, "rigor": 8, "utility": 7, "weighted": 7.2},
            "review_feedback": [],
            "current_phase": "draft_review",
        }

    async def _auto_revise(state):
        iteration = state.get("revision_iteration_count", 0)
        return {
            "full_draft": "# Auto-revised Draft",
            "revision_iteration_count": iteration + 1,
            "current_phase": "review_assessment",
        }

    async def _human_review_draft(state):
        return {"current_phase": "draft_review"}

    async def _revise_review(state):
        return {"full_draft": "# Revised Draft with improvements", "revision_instructions": "", "current_phase": "draft_review"}

    async def _export(state):
        return {"final_output": state.get("full_draft", ""), "current_phase": "completed"}

    for name, fn in [
        ("parse_intent", _parse_intent), ("search", _search),
        ("human_review_search", _human_review_search), ("read", _read),
        ("check_read_feedback", _check_read_feedback),
        ("analyze", _analyze_stub), ("critique", _critique_stub),
        ("check_critic_feedback", _check_critic_feedback_stub),
        ("generate_outline", _generate_outline),
        ("human_review_outline", _human_review_outline),
        ("write_review", _write_review), ("verify_citations", _verify_citations),
        ("review_assessment", _review_assessment), ("auto_revise", _auto_revise),
        ("human_review_draft", _human_review_draft),
        ("revise_review", _revise_review), ("export", _export),
    ]:
        reg.register(name, fn)

    graph = build_review_graph(registry=reg)
    checkpointer = MemorySaver()
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review_search", "human_review_outline", "human_review_draft"],
    )
    cfg = {"configurable": {"thread_id": "e2e-revision"}}

    # Run to search review
    await compiled.ainvoke({"user_query": "test", "output_language": "zh", "citation_style": "apa", "output_types": ["full_review"]}, config=cfg)
    await compiled.aupdate_state(cfg, {"selected_papers": [{"title": "P", "s2_id": "1", "authors": ["A"]}]}, as_node="human_review_search")
    # Run to outline review
    await compiled.ainvoke(None, config=cfg)
    await compiled.aupdate_state(cfg, {}, as_node="human_review_outline")
    # Run to draft review
    result = await compiled.ainvoke(None, config=cfg)
    assert "Original Draft" in result.get("full_draft", "")

    # Request revision
    await compiled.aupdate_state(cfg, {"revision_instructions": "Improve intro"}, as_node="human_review_draft")
    result = await compiled.ainvoke(None, config=cfg)
    assert "Revised Draft" in result.get("full_draft", "")

    # Approve revised draft → export
    await compiled.aupdate_state(cfg, {"revision_instructions": ""}, as_node="human_review_draft")
    result = await compiled.ainvoke(None, config=cfg)
    assert result["current_phase"] == "completed"
    assert "Revised Draft" in result["final_output"]


@pytest.mark.asyncio
async def test_full_workflow_e2e_feedback_loop():
    """E2E workflow where reader triggers a supplemental search via feedback loop."""
    from langgraph.checkpoint.memory import MemorySaver
    from app.agents.orchestrator import build_review_graph
    from app.agents.registry import AgentRegistry

    reg = AgentRegistry()
    search_count = {"n": 0}

    async def _parse_intent(state):
        return {"search_strategy": {"queries": [{"query": state["user_query"]}]}, "current_phase": "searching"}

    async def _search(state):
        search_count["n"] += 1
        return {"candidate_papers": [{"title": f"P{search_count['n']}", "s2_id": f"s{search_count['n']}", "authors": ["A"]}], "current_phase": "search_review", "feedback_search_queries": []}

    async def _human_review_search(state):
        return {"selected_papers": state.get("candidate_papers", []), "current_phase": "reading"}

    async def _read(state):
        iteration = state.get("feedback_iteration_count", 0)
        feedback = ["supplemental query"] if iteration < 1 else []
        return {"paper_analyses": [{"paper_id": "p1", "title": "P", "objective": "O"}], "feedback_search_queries": feedback, "current_phase": "outlining"}

    async def _check_read_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        if feedback:
            return {"feedback_iteration_count": state.get("feedback_iteration_count", 0) + 1}
        return {}

    async def _analyze_stub2(state):
        return {
            "topic_clusters": [], "comparison_matrix": {"title": "", "dimensions": [], "methods": [], "narrative": ""},
            "citation_network": {"nodes": [], "edges": [], "key_papers": [], "bridge_papers": []},
            "timeline": [], "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
            "current_phase": "critiquing",
        }

    async def _critique_stub2(state):
        return {
            "quality_assessments": [], "contradictions": [], "research_gaps": [],
            "limitation_summary": "", "feedback_search_queries": [], "current_phase": "outlining",
        }

    async def _check_critic_feedback_stub2(state):
        return {}

    async def _generate_outline(state):
        return {"outline": {"title": "Rev", "sections": [{"heading": "I", "description": "D"}]}, "current_phase": "outline_review"}

    async def _human_review_outline(state):
        return {"current_phase": "writing"}

    async def _write_review(state):
        return {"full_draft": "# Draft", "references": [], "current_phase": "verifying"}

    async def _verify_citations(state):
        return {"citation_verification": [], "current_phase": "review_assessment"}

    async def _review_assessment(state):
        return {
            "review_scores": {"coherence": 7, "depth": 7, "rigor": 8, "utility": 7, "weighted": 7.2},
            "review_feedback": [],
            "current_phase": "draft_review",
        }

    async def _auto_revise(state):
        iteration = state.get("revision_iteration_count", 0)
        return {
            "full_draft": "# Auto-revised",
            "revision_iteration_count": iteration + 1,
            "current_phase": "review_assessment",
        }

    async def _human_review_draft(state):
        return {"current_phase": "draft_review"}

    async def _revise_review(state):
        return {"full_draft": "# Revised", "revision_instructions": ""}

    async def _export(state):
        return {"final_output": state.get("full_draft", ""), "current_phase": "completed"}

    for name, fn in [
        ("parse_intent", _parse_intent), ("search", _search),
        ("human_review_search", _human_review_search), ("read", _read),
        ("check_read_feedback", _check_read_feedback),
        ("analyze", _analyze_stub2), ("critique", _critique_stub2),
        ("check_critic_feedback", _check_critic_feedback_stub2),
        ("generate_outline", _generate_outline),
        ("human_review_outline", _human_review_outline),
        ("write_review", _write_review), ("verify_citations", _verify_citations),
        ("review_assessment", _review_assessment), ("auto_revise", _auto_revise),
        ("human_review_draft", _human_review_draft),
        ("revise_review", _revise_review), ("export", _export),
    ]:
        reg.register(name, fn)

    # Compile WITHOUT interrupt_before to let it run fully automated
    graph = build_review_graph(registry=reg)
    compiled = graph.compile()

    result = await compiled.ainvoke({
        "user_query": "test", "output_language": "zh", "citation_style": "apa",
        "output_types": ["full_review"],
    })

    # Search should be called twice (initial + 1 feedback loop)
    assert search_count["n"] == 2
    assert result["current_phase"] == "completed"


# ═══════════════════════════════════════════════
#  API error handling e2e
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_error_response_format(client):
    """Verify unified error response matches §8.3.7 format."""
    resp = await client.get("/api/v1/projects/nonexistent")
    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert "code" in body["detail"]
    assert "message" in body["detail"]


@pytest.mark.asyncio
async def test_openapi_schema_available(client):
    """Verify OpenAPI schema is generated and accessible."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "Agentic Literature Review"
    assert "/api/v1/projects" in schema["paths"]
    assert "/healthz" in schema["paths"]
