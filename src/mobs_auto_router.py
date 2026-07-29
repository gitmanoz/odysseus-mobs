"""Deterministic MOBS Auto model routing for local Ollama models."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

from core.database import ModelEndpoint, SessionLocal
from src.auth_helpers import owner_filter
from src.endpoint_resolver import build_headers, normalize_base

MOBS_AUTO_MODEL_ID = "__mobs_auto__"
MOBS_AUTO_DISPLAY_NAME = "MOBS Auto"
MOBS_GENERAL_MODEL = "qwen3:8b"
MOBS_CODER_MODEL = "qwen2.5-coder:7b"

_ENGINEERING_RE = re.compile(
    r"\b(?:code|coding|program|programming|implement|implementation|refactor|"
    r"debug|bug|fix|test|tests|build|compile|terminal|shell|bash|powershell|"
    r"git|commit|branch|repository|repo|workspace|file|folder|directory|path|"
    r"python|javascript|typescript|java|c\+\+|sql|api|endpoint|docker|npm|pip)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResolvedMobsRoute:
    endpoint_id: str
    endpoint_url: str
    model: str
    headers: dict[str, str]
    reason: str
    requested_model: str = MOBS_AUTO_MODEL_ID
    display_name: str = MOBS_AUTO_DISPLAY_NAME
    disable_thinking: bool = True
    used_fallback: bool = False


def is_mobs_auto(model: Any) -> bool:
    return str(model or "").strip() == MOBS_AUTO_MODEL_ID


def choose_mobs_model(
    message: str,
    *,
    chat_mode: str = "chat",
    tool_intent: Any = None,
    workspace: str = "",
    plan_mode: bool = False,
) -> tuple[str, str]:
    """Choose one of the two MOBS local models without calling another LLM."""
    category = str(getattr(tool_intent, "category", "") or "").lower()
    needs_tools = bool(getattr(tool_intent, "needs_tools", False))

    if workspace:
        return MOBS_CODER_MODEL, "workspace"
    if category in {"shell", "workspace", "code", "files", "git"}:
        return MOBS_CODER_MODEL, f"tool_intent:{category}"
    if needs_tools and str(chat_mode or "").lower() == "agent":
        return MOBS_CODER_MODEL, "agent_tools"
    if _ENGINEERING_RE.search(str(message or "")):
        return MOBS_CODER_MODEL, "engineering_prompt"
    if plan_mode and _ENGINEERING_RE.search(str(message or "")):
        return MOBS_CODER_MODEL, "engineering_plan"
    return MOBS_GENERAL_MODEL, "general_prompt"


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    return []


def _visible_models(endpoint: ModelEndpoint) -> list[str]:
    cached = _json_list(getattr(endpoint, "cached_models", None))
    pinned = _json_list(getattr(endpoint, "pinned_models", None))
    hidden = set(_json_list(getattr(endpoint, "hidden_models", None)))
    out: list[str] = []
    for model in [*cached, *pinned]:
        if model not in hidden and model not in out:
            out.append(model)
    return out


def _iter_enabled_endpoints(owner: str | None = None) -> Iterable[ModelEndpoint]:
    db = SessionLocal()
    try:
        query = db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True)  # noqa: E712
        if owner:
            query = owner_filter(query, ModelEndpoint, owner)
        rows = query.all()
        for row in rows:
            db.expunge(row)
        return rows
    finally:
        db.close()


def _openai_compatible_chat_url(base: str) -> str:
    """Use Ollama's OpenAI-compatible chat endpoint for MOBS Auto.

    Odysseus already sends ``think: false`` for thinking-capable models on this
    endpoint. Keeping this decision inside the MOBS route avoids changing the
    behavior of manually selected Ollama models.
    """
    parsed = urlparse(normalize_base(base))
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/v1"):
        target_path = f"{path}/chat/completions"
    elif path:
        target_path = f"{path}/v1/chat/completions"
    else:
        target_path = "/v1/chat/completions"
    return urlunparse(parsed._replace(path=target_path, query="", fragment=""))


def resolve_mobs_auto_route(
    message: str,
    *,
    owner: str | None = None,
    chat_mode: str = "chat",
    tool_intent: Any = None,
    workspace: str = "",
    plan_mode: bool = False,
) -> ResolvedMobsRoute:
    requested, reason = choose_mobs_model(
        message,
        chat_mode=chat_mode,
        tool_intent=tool_intent,
        workspace=workspace,
        plan_mode=plan_mode,
    )
    alternate = MOBS_GENERAL_MODEL if requested == MOBS_CODER_MODEL else MOBS_CODER_MODEL

    endpoints = list(_iter_enabled_endpoints(owner))
    for candidate, used_fallback in ((requested, False), (alternate, True)):
        for endpoint in endpoints:
            if candidate not in _visible_models(endpoint):
                continue
            base = normalize_base(endpoint.base_url or "")
            return ResolvedMobsRoute(
                endpoint_id=str(endpoint.id or ""),
                endpoint_url=_openai_compatible_chat_url(base),
                model=candidate,
                headers=build_headers(endpoint.api_key or "", endpoint.base_url or "") if endpoint.api_key else {},
                reason=reason if not used_fallback else f"{reason}:fallback",
                used_fallback=used_fallback,
            )

    raise RuntimeError(
        "MOBS Auto requires qwen3:8b or qwen2.5-coder:7b on an enabled model endpoint"
    )
