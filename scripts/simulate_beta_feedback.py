#!/usr/bin/env python3
"""
Simulate 300+ developer feedback events against a running Patchwork API.

Usage (from repo root, with API up on port 8000):
  pip install httpx
  python scripts/simulate_beta_feedback.py --base-url http://localhost:8000 --count 320
"""

from __future__ import annotations

import argparse
import asyncio
import random
import string
from typing import Any

import httpx

REPOS = [
    "acme/payments-api",
    "acme/web-app",
    "acme/ml-pipeline",
    "contoso/auth-service",
    "contoso/data-plane",
    "patchwork/demo-repo",
]


def _rand_suffix(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


async def send_one(client: httpx.AsyncClient, base: str, i: int) -> None:
    repo = random.choice(REPOS)
    pr_number = random.randint(1, 400)
    verdict = random.choices(["correct", "false_positive"], weights=[0.78, 0.22], k=1)[0]
    prompt_version = random.choices(["v1", "v2"], weights=[0.15, 0.85], k=1)[0]
    payload: dict[str, Any] = {
        "repo_full_name": repo,
        "pr_number": pr_number,
        "installation_id": random.randint(100_000, 999_999),
        "finding_key": f"{repo}:pr{pr_number}:finding:{i}:{_rand_suffix()}",
        "verdict": verdict,
        "prompt_version": prompt_version,
        "category": random.choice(["security", "performance", "anti_pattern", "maintainability"]),
        "notes": "simulated beta feedback",
    }
    r = await client.post(f"{base.rstrip('/')}/api/feedback", json=payload, timeout=30.0)
    r.raise_for_status()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=320)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()

    sem = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient() as client:

        async def wrapped(i: int) -> None:
            async with sem:
                await send_one(client, args.base_url, i)

        await asyncio.gather(*(wrapped(i) for i in range(args.count)))
    print(f"Posted {args.count} feedback rows to {args.base_url}")


if __name__ == "__main__":
    asyncio.run(main())
