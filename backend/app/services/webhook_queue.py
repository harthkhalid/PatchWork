"""Redis-backed queue for PR analysis jobs."""

import json
import uuid

import redis.asyncio as redis

QUEUE_KEY = "patchwork:pr_jobs"


async def enqueue(redis_client: redis.Redis, payload: dict) -> str:
    job_id = str(uuid.uuid4())
    body = json.dumps({"job_id": job_id, **payload})
    await redis_client.lpush(QUEUE_KEY, body)
    return job_id


async def dequeue_blocking(redis_client: redis.Redis, timeout_sec: int = 5) -> dict | None:
    result = await redis_client.brpop(QUEUE_KEY, timeout=timeout_sec)
    if not result:
        return None
    _, raw = result
    return json.loads(raw)
