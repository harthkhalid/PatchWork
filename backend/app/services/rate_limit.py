"""Sliding-window rate limits using Redis."""

import time
import uuid

import redis.asyncio as redis


async def allow(redis_client: redis.Redis, key: str, limit: int, window_sec: int = 60) -> bool:
    now = time.time()
    window_start = now - window_sec
    member = f"{now}:{uuid.uuid4().hex}"
    pipe = redis_client.pipeline(transaction=True)
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window_sec + 1)
    results = await pipe.execute()
    count = int(results[2])
    if count > limit:
        await redis_client.zrem(key, member)
        return False
    return True
