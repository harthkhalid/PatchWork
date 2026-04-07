"""OpenAI review pipeline with structured JSON output and confidence filtering."""

import json
import re
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from app.config import Settings, get_settings
from app.services.prompts import PromptBundle, load_prompt, render_user


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    category: str
    title: str
    body: str
    confidence: float
    evidence: str = ""

    def key(self) -> str:
        h = f"{self.file}:{self.line}:{self.title}"
        return re.sub(r"\s+", " ", h)[:250]


def _truncate_diff(diff_text: str, max_chars: int = 95000) -> str:
    if len(diff_text) <= max_chars:
        return diff_text
    return diff_text[: max_chars - 80] + "\n\n... [truncated for token limits] ..."


def _parse_findings(raw: str) -> list[dict[str, Any]]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict) and "findings" in data:
        return list(data["findings"])
    if isinstance(data, list):
        return list(data)
    return []


def _filter_by_confidence(rows: list[dict[str, Any]], min_confidence: float = 0.55) -> list[Finding]:
    out: list[Finding] = []
    for row in rows:
        try:
            conf = float(row.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        if conf < min_confidence:
            continue
        sev = str(row.get("severity", "info")).lower()
        if sev == "info" and conf < 0.72:
            continue
        f = Finding(
            file=str(row.get("file", "unknown")),
            line=int(row.get("line", 0)),
            severity=sev,
            category=str(row.get("category", "maintainability")).lower(),
            title=str(row.get("title", "Finding"))[:200],
            body=str(row.get("body", ""))[:8000],
            confidence=min(1.0, max(0.0, conf)),
            evidence=str(row.get("evidence", ""))[:500],
        )
        out.append(f)
    return out[:20]


async def analyze_diff(
    *,
    diff_text: str,
    repo_full_name: str,
    pr_number: int,
    settings: Settings | None = None,
    prompt_version: str | None = None,
) -> tuple[list[Finding], str, PromptBundle]:
    settings = settings or get_settings()
    version = prompt_version or settings.active_prompt_version
    bundle = load_prompt(version)
    client = AsyncOpenAI(api_key=settings.openai_api_key or None)
    user = render_user(
        bundle,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        diff_text=_truncate_diff(diff_text),
    )
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": bundle.system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    rows = _parse_findings(content)
    findings = _filter_by_confidence(rows)
    return findings, content, bundle


def compute_health_score(findings: list[Finding]) -> float:
    """0-100, higher is healthier (fewer severe issues)."""
    if not findings:
        return 100.0
    weights = {"critical": 25, "high": 18, "medium": 10, "low": 4, "info": 1}
    penalty = 0.0
    for f in findings:
        penalty += weights.get(f.severity, 3)
    score = max(0.0, 100.0 - min(100.0, penalty))
    return round(score, 1)
