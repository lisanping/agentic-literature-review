"""Visualization data API — graph / timeline / trends — v0.4."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import check_project_access, get_current_user_optional, get_db
from app.models.paper import Paper
from app.models.project import Project
from app.models.project_paper import ProjectPaper
from app.models.user import User

logger = structlog.stdlib.get_logger()

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/visualizations",
    tags=["visualizations"],
)

# Default cluster color palette (matches frontend)
CLUSTER_COLORS = [
    "#1677ff", "#52c41a", "#fa8c16", "#722ed1", "#eb2f96",
    "#13c2c2", "#faad14", "#f5222d", "#2f54eb", "#a0d911",
    "#597ef7", "#9254de", "#ff7a45", "#36cfc9", "#ff85c0",
]


@router.get("/graph")
async def get_graph_data(
    project_id: str,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Build knowledge graph data from project papers and their analysis.

    Nodes = papers, edges = citation relationships,
    clusters from analyst topic_clusters if available.
    """
    project = await check_project_access(project_id, db, user, min_permission="viewer")

    # Fetch papers with analysis
    result = await db.execute(
        select(ProjectPaper)
        .options(selectinload(ProjectPaper.paper))
        .where(
            ProjectPaper.project_id == project_id,
            ProjectPaper.deleted_at.is_(None),
        )
    )
    project_papers = result.scalars().all()

    # Build paper lookup
    papers = [pp.paper for pp in project_papers if pp.paper is not None]
    paper_ids = {p.id for p in papers}

    # Try to get cluster assignments from review outputs
    cluster_assignments: dict[str, tuple[str, str]] = {}  # paper_id -> (cluster_id, cluster_name)
    clusters_info: list[dict] = []

    # Check if project has analysis result with clusters in review output
    from app.models.review_output import ReviewOutput
    output_result = await db.execute(
        select(ReviewOutput).where(
            ReviewOutput.project_id == project_id,
            ReviewOutput.deleted_at.is_(None),
        ).order_by(ReviewOutput.created_at.desc()).limit(1)
    )
    output = output_result.scalar_one_or_none()

    if output and output.structured_data:
        sd = output.structured_data
        # Look for topic_clusters in structured data
        topic_clusters = sd.get("topic_clusters") or sd.get("analyst", {}).get("topic_clusters", [])
        for idx, cluster in enumerate(topic_clusters):
            cid = cluster.get("id", f"cluster-{idx}")
            cname = cluster.get("name", f"主题 {idx + 1}")
            color = CLUSTER_COLORS[idx % len(CLUSTER_COLORS)]
            paper_ids_in_cluster = cluster.get("paper_ids", [])
            clusters_info.append({
                "id": cid,
                "name": cname,
                "color": color,
                "paper_count": len(paper_ids_in_cluster),
            })
            for pid in paper_ids_in_cluster:
                cluster_assignments[pid] = (cid, cname)

    # Build nodes
    nodes = []
    for p in papers:
        cluster_id, cluster_name = cluster_assignments.get(p.id, (None, None))
        nodes.append({
            "id": p.id,
            "title": p.title,
            "authors": p.authors[:5] if p.authors else [],
            "year": p.year,
            "citations_count": p.citation_count or 0,
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
        })

    # Build edges from citation network in structured data
    edges: list[dict] = []
    if output and output.structured_data:
        citation_network = output.structured_data.get("citation_network", [])
        for edge in citation_network:
            src = edge.get("source")
            tgt = edge.get("target")
            if src in paper_ids and tgt in paper_ids:
                edges.append({
                    "source": src,
                    "target": tgt,
                    "relation_type": edge.get("relation_type", "cites"),
                    "weight": edge.get("weight", 1),
                })

    return {"nodes": nodes, "edges": edges, "clusters": clusters_info}


@router.get("/timeline")
async def get_timeline_data(
    project_id: str,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Build timeline data grouped by year."""
    await check_project_access(project_id, db, user, min_permission="viewer")

    result = await db.execute(
        select(ProjectPaper)
        .options(selectinload(ProjectPaper.paper))
        .where(
            ProjectPaper.project_id == project_id,
            ProjectPaper.deleted_at.is_(None),
        )
    )
    project_papers = result.scalars().all()
    papers = [pp.paper for pp in project_papers if pp.paper is not None]

    # Group by year
    year_groups: dict[int, list] = {}
    for p in papers:
        year = p.year or 0
        if year not in year_groups:
            year_groups[year] = []
        year_groups[year].append({
            "id": p.id,
            "title": p.title,
            "authors": p.authors[:3] if p.authors else [],
            "citations_count": p.citation_count or 0,
        })

    events = []
    for year in sorted(year_groups.keys()):
        if year == 0:
            continue
        ps = year_groups[year]
        events.append({
            "year": year,
            "paper_count": len(ps),
            "paper_ids": [p["id"] for p in ps],
            "papers": ps,
            "milestone": None,
        })

    return {"events": events}


@router.get("/trends")
async def get_trends_data(
    project_id: str,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return trends data for the project."""
    await check_project_access(project_id, db, user, min_permission="viewer")

    # Try to get from review output structured_data
    from app.models.review_output import ReviewOutput
    output_result = await db.execute(
        select(ReviewOutput).where(
            ReviewOutput.project_id == project_id,
            ReviewOutput.deleted_at.is_(None),
        ).order_by(ReviewOutput.created_at.desc()).limit(1)
    )
    output = output_result.scalar_one_or_none()

    if output and output.structured_data:
        sd = output.structured_data
        trends = sd.get("research_trends") or sd.get("analyst", {}).get("research_trends", {})
        if trends:
            return trends

    return {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""}
