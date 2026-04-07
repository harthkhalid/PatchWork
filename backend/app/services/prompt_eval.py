"""Evaluation logic: compare prompt versions using labeled feedback (false positive rate)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.false_positive_tracker import false_positive_rate_global


async def evaluate_prompt_version(session: AsyncSession, version: str) -> dict[str, float | int]:
    """Primary metric: FP rate on human-labeled subset. Target < 8%."""
    stats = await false_positive_rate_global(session, prompt_version=version)
    target = 0.08
    meets_target = stats["false_positive_rate"] <= target if stats["total_labeled"] else True
    return {
        **stats,
        "target_false_positive_rate": target,
        "meets_target": bool(meets_target),
    }


async def compare_versions(session: AsyncSession, versions: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for v in versions:
        ev = await evaluate_prompt_version(session, v)
        rows.append({"version": v, **ev})
    return rows
