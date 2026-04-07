"""Versioned prompt templates loaded from YAML files."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@dataclass
class PromptBundle:
    version: str
    description: str
    system: str
    user_template: str


def load_prompt(version: str) -> PromptBundle:
    path = _PROMPTS_DIR / f"{version}.yaml"
    if not path.exists():
        path = _PROMPTS_DIR / "v2.yaml"
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PromptBundle(
        version=str(data.get("version", path.stem)),
        description=str(data.get("description", "")),
        system=str(data.get("system", "")),
        user_template=str(data.get("user_template", "")),
    )


def list_prompt_versions() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for p in sorted(_PROMPTS_DIR.glob("v*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        out.append(
            {
                "version": str(data.get("version", p.stem)),
                "description": str(data.get("description", "")),
                "path": str(p.relative_to(_PROMPTS_DIR.parent)),
            }
        )
    return out


def render_user(bundle: PromptBundle, **kwargs: Any) -> str:
    return bundle.user_template.format(**kwargs)
