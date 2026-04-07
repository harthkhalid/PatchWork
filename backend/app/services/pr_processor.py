"""End-to-end PR analysis: fetch diff, run GPT, post comments, persist analytics."""

import asyncio
import logging

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import PRAnalysisRun
from app.services.github_app import get_installation_token
from app.services.github_client import GitHubClient, split_owner_repo
from app.services.openai_pipeline import analyze_diff, compute_health_score
from app.services.rate_limit import allow
from app.services import webhook_queue as wq

_log = logging.getLogger(__name__)


async def process_pr_job(
    redis_client: redis.Redis,
    session: AsyncSession,
    *,
    installation_id: int,
    repo_full_name: str,
    pr_number: int,
) -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        _log.warning("OPENAI_API_KEY missing; skip PR analysis")
        return
    if not await allow(redis_client, f"gh:install:{installation_id}", settings.github_api_rpm):
        await wq.enqueue(
            redis_client,
            {
                "installation_id": installation_id,
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
            },
        )
        await asyncio.sleep(2)
        return
    if not await allow(redis_client, "oa:global", settings.openai_rpm):
        await wq.enqueue(
            redis_client,
            {
                "installation_id": installation_id,
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
            },
        )
        await asyncio.sleep(2)
        return

    token = await get_installation_token(installation_id)
    gh = GitHubClient(token)
    owner, repo = split_owner_repo(repo_full_name)
    pr = await gh.get_pull_request(owner, repo, pr_number)
    diff_text = await gh.get_pull_diff(owner, repo, pr_number)
    head_sha = str(pr["head"]["sha"])

    findings, _raw, bundle = await analyze_diff(
        diff_text=diff_text,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        prompt_version=settings.active_prompt_version,
    )
    health = compute_health_score(findings)

    run = PRAnalysisRun(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        installation_id=installation_id,
        health_score=health,
        findings_count=len(findings),
        prompt_version=bundle.version,
    )
    session.add(run)
    await session.commit()

    for f in findings:
        tag = f"[{f.severity.upper()}] **{f.title}** ({f.category})\n\n{f.body}"
        if f.evidence:
            tag += f"\n\n_Evidence:_ {f.evidence}"
        tag += f"\n\n<!-- patchwork:finding:{f.key()}|pv:{bundle.version} -->"
        footer = (
            "\n\n---\n_Submit feedback in the [Patchwork dashboard]("
            + settings.public_base_url
            + "/) or reply with `patchwork correct` / `patchwork false positive`._"
        )
        body = tag + footer
        line = max(1, f.line)
        await gh.create_review_comment(
            owner,
            repo,
            pr_number,
            body,
            head_sha,
            f.file,
            line,
        )
