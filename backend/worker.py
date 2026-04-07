"""Redis queue worker: processes PR analysis jobs."""

import asyncio
import logging

import redis.asyncio as redis

from app.config import get_settings
from app.database import async_session_maker, init_db
from app.services.pr_processor import process_pr_job
from app.services.webhook_queue import QUEUE_KEY, dequeue_blocking

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    await init_db()
    r = redis.from_url(settings.redis_url, decode_responses=True)
    log.info("worker listening on %s key=%s", settings.redis_url, QUEUE_KEY)
    while True:
        try:
            job = await dequeue_blocking(r, timeout_sec=10)
            if not job:
                continue
            installation_id = int(job["installation_id"])
            repo_full_name = str(job["repo_full_name"])
            pr_number = int(job["pr_number"])
            async with async_session_maker() as session:
                await process_pr_job(
                    r,
                    session,
                    installation_id=installation_id,
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                )
            log.info("processed %s#%s", repo_full_name, pr_number)
        except Exception as e:
            log.exception("job failed: %s", e)
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run_worker())
