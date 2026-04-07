"""GitHub App webhooks: PRs and PR comments."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import get_settings
from app.services.github_app import verify_webhook_signature
from app.services.webhook_queue import enqueue
import redis.asyncio as redis

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _get_redis(request: Request) -> redis.Redis:
    r = getattr(request.app.state, "redis", None)
    if not r:
        raise HTTPException(503, "Redis unavailable")
    return r


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, str]:
    settings = get_settings()
    body = await request.body()
    if settings.github_webhook_secret:
        if not verify_webhook_signature(body, x_hub_signature_256, settings.github_webhook_secret):
            raise HTTPException(401, "invalid signature")

    if not x_github_event:
        raise HTTPException(400, "missing event")

    payload: dict[str, Any] = json.loads(body.decode("utf-8") or "{}")

    if x_github_event == "ping":
        return {"status": "pong"}

    redis_client = _get_redis(request)

    if x_github_event == "pull_request":
        action = payload.get("action")
        if action not in ("opened", "synchronize", "reopened", "ready_for_review"):
            return {"status": "ignored", "reason": action or "unknown"}
        pr = payload.get("pull_request") or {}
        repo = (payload.get("repository") or {}).get("full_name")
        num = pr.get("number")
        inst = (payload.get("installation") or {}).get("id")
        if not repo or not num or not inst:
            return {"status": "ignored", "reason": "missing fields"}
        try:
            pr_no = int(num)
            inst_id = int(inst)
        except (TypeError, ValueError):
            log.warning("ignored webhook: non-numeric pr or installation id")
            return {"status": "ignored", "reason": "invalid ids"}
        await enqueue(
            redis_client,
            {
                "installation_id": inst_id,
                "repo_full_name": str(repo),
                "pr_number": pr_no,
            },
        )
        log.info("queued pr %s#%s", repo, num)
        return {"status": "queued"}

    if x_github_event == "issue_comment":
        issue = payload.get("issue") or {}
        if "pull_request" not in issue:
            return {"status": "ignored", "reason": "not a PR comment"}
        action = payload.get("action")
        if action != "created":
            return {"status": "ignored", "reason": action or "unknown"}
        body_text = (payload.get("comment") or {}).get("body") or ""
        lower = body_text.lower()
        if "patchwork" not in lower:
            return {"status": "ignored", "reason": "no keyword"}
        repo = (payload.get("repository") or {}).get("full_name")
        num = issue.get("number")
        inst = (payload.get("installation") or {}).get("id")
        if not repo or not num or not inst:
            return {"status": "ignored"}
        try:
            pr_no = int(num)
            inst_id = int(inst)
        except (TypeError, ValueError):
            log.warning("ignored issue_comment webhook: invalid ids")
            return {"status": "ignored", "reason": "invalid ids"}
        await enqueue(
            redis_client,
            {
                "installation_id": inst_id,
                "repo_full_name": str(repo),
                "pr_number": pr_no,
            },
        )
        log.info("queued from comment %s#%s", repo, num)
        return {"status": "queued"}

    return {"status": "ignored", "event": x_github_event}
