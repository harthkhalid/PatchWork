"""Dashboard API: analytics, feedback, stars, prompts."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.models import PRAnalysisRun, StarCounter
from app.services.false_positive_tracker import (
    false_positive_rate_for_repo,
    false_positive_rate_global,
    list_repo_stats,
    record_feedback,
)
from app.services.prompt_eval import compare_versions, evaluate_prompt_version
from app.services.prompts import list_prompt_versions

router = APIRouter(prefix="/api", tags=["api"])


class FeedbackIn(BaseModel):
    repo_full_name: str = Field(..., min_length=3)
    pr_number: int = Field(..., ge=1)
    installation_id: int = 0
    finding_key: str = Field(..., min_length=4)
    verdict: str = Field(..., pattern="^(correct|false_positive)$")
    prompt_version: str = "v2"
    category: str = "general"
    comment_id: str | None = None
    notes: str | None = None


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "patchwork"}


@router.get("/badge/install.svg")
async def install_badge() -> Response:
    """Shields-style SVG for README / marketing pages."""
    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="132" height="20" role="img">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <mask id="a">
    <rect width="132" height="20" rx="3" fill="#fff"/>
  </mask>
  <g mask="url(#a)">
    <rect width="72" height="20" fill="#555"/>
    <rect x="72" width="60" height="20" fill="#22c55e"/>
    <rect width="132" height="20" fill="url(#b)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" font-size="11">
    <text x="37" y="14" fill="#010101" fill-opacity=".3">patchwork</text>
    <text x="37" y="13">patchwork</text>
    <text x="101" y="14" fill="#010101" fill-opacity=".3">install</text>
    <text x="101" y="13">install</text>
  </g>
  <a href="{base}/install"><rect width="132" height="20" fill="transparent"/></a>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/stars")
async def stars(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    row = await session.scalar(select(StarCounter).where(StarCounter.id == 1))
    if not row:
        row = StarCounter(id=1, stars=512)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return {
        "stars": row.stars,
        "display": f"{row.stars}+",
        "message": "Community momentum metric (demo counter — wire to GitHub stars if desired).",
    }


@router.post("/stars/increment")
async def stars_increment(session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    row = await session.scalar(select(StarCounter).where(StarCounter.id == 1))
    if not row:
        row = StarCounter(id=1, stars=512)
        session.add(row)
    else:
        row.stars += 1
    await session.commit()
    await session.refresh(row)
    return {"stars": row.stars}


@router.get("/analytics/fp-rate")
async def fp_rate(
    repo: str | None = None,
    version: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if repo:
        return await false_positive_rate_for_repo(session, repo, version)
    return await false_positive_rate_global(session, version)


@router.get("/analytics/repos")
async def repos(session: AsyncSession = Depends(get_session)) -> list[dict[str, object]]:
    return await list_repo_stats(session)


@router.get("/analytics/prompt-eval")
async def prompt_eval(version: str | None = None, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    v = version or get_settings().active_prompt_version
    return await evaluate_prompt_version(session, v)


@router.get("/prompts/versions")
async def prompts_versions() -> list[dict[str, str]]:
    return list_prompt_versions()


@router.get("/prompts/compare")
async def prompts_compare(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    versions = [p["version"] for p in list_prompt_versions()]
    return await compare_versions(session, versions)


@router.post("/feedback")
async def feedback(body: FeedbackIn, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    row = await record_feedback(
        session,
        repo_full_name=body.repo_full_name,
        pr_number=body.pr_number,
        installation_id=body.installation_id,
        finding_key=body.finding_key,
        verdict=body.verdict,
        prompt_version=body.prompt_version,
        category=body.category,
        comment_id=body.comment_id,
        notes=body.notes,
    )
    return {"id": row.id, "status": "recorded"}


@router.get("/prs/recent")
async def recent_prs(
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(PRAnalysisRun).order_by(desc(PRAnalysisRun.created_at)).limit(min(limit, 100))
    rows = (await session.scalars(stmt)).all()
    return [
        {
            "repo": r.repo_full_name,
            "pr": r.pr_number,
            "health_score": r.health_score,
            "findings": r.findings_count,
            "prompt_version": r.prompt_version,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
