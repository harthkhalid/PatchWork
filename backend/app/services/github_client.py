"""GitHub REST helpers for PR diffs and review comments."""

from typing import Any

import httpx


class GitHubClient:
    def __init__(self, token: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_pull_request(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(url, headers=self._headers)
            r.raise_for_status()
            return r.json()

    async def get_pull_diff(self, owner: str, repo: str, number: int) -> str:
        h = {**self._headers, "Accept": "application/vnd.github.diff"}
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.get(url, headers=h)
            r.raise_for_status()
            return r.text

    async def create_review_comment(
        self,
        owner: str,
        repo: str,
        number: int,
        body: str,
        commit_id: str,
        path: str,
        line: int,
        side: str = "RIGHT",
    ) -> dict[str, Any]:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/comments"
        payload = {
            "body": body,
            "commit_id": commit_id,
            "path": path,
            "line": line,
            "side": side,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=self._headers, json=payload)
            if r.status_code >= 400:
                return await self._fallback_issue_comment(owner, repo, number, body, r.text[:400])
            return r.json()

    async def _fallback_issue_comment(
        self, owner: str, repo: str, number: int, body: str, err: str
    ) -> dict[str, Any]:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments"
        wrapped = f"<!-- patchwork-line-fallback -->\n**Patchwork** (could not anchor to line: {err[:200]})\n\n{body}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=self._headers, json={"body": wrapped})
            r.raise_for_status()
            return r.json()


def split_owner_repo(full_name: str) -> tuple[str, str]:
    parts = full_name.split("/", 1)
    if len(parts) != 2:
        raise ValueError("expected owner/repo")
    return parts[0], parts[1]
