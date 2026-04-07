"""Aggregate false positive rates per repo and prompt version."""

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeedbackEntry, FeedbackVerdict


async def record_feedback(
    session: AsyncSession,
    *,
    repo_full_name: str,
    pr_number: int,
    installation_id: int,
    finding_key: str,
    verdict: str,
    prompt_version: str,
    category: str = "general",
    comment_id: str | None = None,
    notes: str | None = None,
) -> FeedbackEntry:
    row = FeedbackEntry(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        installation_id=installation_id,
        comment_id=comment_id,
        finding_key=finding_key,
        category=category,
        verdict=verdict,
        prompt_version=prompt_version,
        notes=notes,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def false_positive_rate_for_repo(
    session: AsyncSession,
    repo_full_name: str,
    prompt_version: str | None = None,
) -> dict[str, float | int]:
    """FP rate = false_positive / (correct + false_positive)."""
    cond = [FeedbackEntry.repo_full_name == repo_full_name]
    if prompt_version:
        cond.append(FeedbackEntry.prompt_version == prompt_version)
    stmt = select(
        func.sum(case((FeedbackEntry.verdict == FeedbackVerdict.FALSE_POSITIVE, 1), else_=0)).label("fp"),
        func.sum(case((FeedbackEntry.verdict == FeedbackVerdict.CORRECT, 1), else_=0)).label("ok"),
    ).where(and_(*cond))
    row = (await session.execute(stmt)).one()
    fp = int(row.fp or 0)
    ok = int(row.ok or 0)
    denom = fp + ok
    rate = (fp / denom) if denom else 0.0
    return {"false_positive_rate": rate, "false_positives": fp, "correct": ok, "total_labeled": denom}


async def false_positive_rate_global(
    session: AsyncSession,
    prompt_version: str | None = None,
) -> dict[str, float | int]:
    cond = []
    if prompt_version:
        cond.append(FeedbackEntry.prompt_version == prompt_version)
    stmt = select(
        func.sum(case((FeedbackEntry.verdict == FeedbackVerdict.FALSE_POSITIVE, 1), else_=0)).label("fp"),
        func.sum(case((FeedbackEntry.verdict == FeedbackVerdict.CORRECT, 1), else_=0)).label("ok"),
    )
    if cond:
        stmt = stmt.where(and_(*cond))
    row = (await session.execute(stmt)).one()
    fp = int(row.fp or 0)
    ok = int(row.ok or 0)
    denom = fp + ok
    rate = (fp / denom) if denom else 0.0
    return {"false_positive_rate": rate, "false_positives": fp, "correct": ok, "total_labeled": denom}


async def list_repo_stats(session: AsyncSession) -> list[dict[str, object]]:
    stmt = select(
        FeedbackEntry.repo_full_name,
        func.sum(case((FeedbackEntry.verdict == FeedbackVerdict.FALSE_POSITIVE, 1), else_=0)).label("fp"),
        func.sum(case((FeedbackEntry.verdict == FeedbackVerdict.CORRECT, 1), else_=0)).label("ok"),
    ).group_by(FeedbackEntry.repo_full_name)
    rows = (await session.execute(stmt)).all()
    out: list[dict[str, object]] = []
    for r in rows:
        fp, ok = int(r.fp or 0), int(r.ok or 0)
        denom = fp + ok
        out.append(
            {
                "repo": r.repo_full_name,
                "false_positive_rate": (fp / denom) if denom else 0.0,
                "false_positives": fp,
                "correct": ok,
                "total_labeled": denom,
            }
        )
    return sorted(out, key=lambda x: str(x["repo"]))
