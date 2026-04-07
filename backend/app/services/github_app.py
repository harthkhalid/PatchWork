"""GitHub App JWT and installation access tokens."""

import time
from typing import Any

import httpx
import jwt

from app.config import Settings, get_settings, resolve_private_key


def _build_jwt(settings: Settings) -> str:
    pem = resolve_private_key(settings)
    if not pem or not settings.github_app_id:
        raise RuntimeError("GitHub App credentials not configured")
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 9 * 60,
        "iss": int(settings.github_app_id),
    }
    return jwt.encode(payload, pem, algorithm="RS256")


async def get_installation_token(installation_id: int, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    token = _build_jwt(settings)
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        return str(data["token"])


async def verify_webhook_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    if not secret or not signature_header:
        return False
    import hmac
    import hashlib

    if not signature_header.startswith("sha256="):
        return False
    sig = signature_header[7:]
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, sig)
