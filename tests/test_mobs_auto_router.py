from types import SimpleNamespace

import pytest

from src.mobs_auto_router import (
    MOBS_AUTO_DISPLAY_NAME,
    MOBS_AUTO_MODEL_ID,
    MOBS_CODER_MODEL,
    ResolvedMobsRoute,
    _ollama_native_chat_url,
    choose_mobs_model,
    is_mobs_auto,
    resolve_mobs_auto_route,
)


def test_general_conversation_uses_general_model():
    model, reason = choose_mobs_model("oi")
    assert model == MOBS_CODER_MODEL
    assert reason == "general_prompt"


def test_code_prompt_uses_coder_model():
    model, reason = choose_mobs_model("Implemente e teste este endpoint Python")
    assert model == MOBS_CODER_MODEL
    assert reason == "engineering_prompt"


def test_workspace_forces_coder_model():
    model, reason = choose_mobs_model("Analise isso", workspace="C:/AI/projects/odysseus-mobs")
    assert model == MOBS_CODER_MODEL
    assert reason == "workspace"


def test_shell_tool_intent_uses_coder_model():
    intent = SimpleNamespace(category="shell", needs_tools=True)
    model, reason = choose_mobs_model("Faça isso", chat_mode="agent", tool_intent=intent)
    assert model == MOBS_CODER_MODEL
    assert reason == "tool_intent:shell"


def test_auto_sentinel_detection():
    assert is_mobs_auto(MOBS_AUTO_MODEL_ID)
    assert not is_mobs_auto(MOBS_CODER_MODEL)


def test_resolved_route_preserves_symbolic_identity():
    route = ResolvedMobsRoute(
        endpoint_id="local",
        endpoint_url="http://host.docker.internal:11434/v1/chat/completions",
        model=MOBS_CODER_MODEL,
        headers={},
        reason="general_prompt",
    )
    assert route.requested_model == MOBS_AUTO_MODEL_ID
    assert route.display_name == MOBS_AUTO_DISPLAY_NAME
    assert route.disable_thinking is True


def test_mobs_auto_uses_ollama_native_endpoint():
    assert _ollama_native_chat_url("http://host.docker.internal:11434") == (
        "http://host.docker.internal:11434/api/chat"
    )
    assert _ollama_native_chat_url("http://localhost:11434/v1") == (
        "http://localhost:11434/api/chat"
    )
    assert _ollama_native_chat_url("http://localhost:11434/v1/chat/completions") == (
        "http://localhost:11434/api/chat"
    )


def test_general_and_engineering_routes_use_coder_even_when_qwen3_is_visible(monkeypatch):
    import src.mobs_auto_router as router

    endpoint = SimpleNamespace(
        id="local", base_url="http://127.0.0.1:11434/v1", api_key="",
        cached_models='["qwen3:8b", "qwen2.5-coder:7b"]',
        pinned_models="[]", hidden_models="[]",
    )
    monkeypatch.setattr(router, "_iter_enabled_endpoints", lambda owner: [endpoint])
    for message in ("Olá", "Corrija este bug Python"):
        route = resolve_mobs_auto_route(message)
        assert route.model == MOBS_CODER_MODEL
        assert route.requested_model == MOBS_AUTO_MODEL_ID
        assert route.used_fallback is False


def test_qwen3_alone_cannot_satisfy_mobs_auto(monkeypatch):
    import src.mobs_auto_router as router

    endpoint = SimpleNamespace(
        id="local", base_url="http://127.0.0.1:11434/v1", api_key="",
        cached_models='["qwen3:8b"]', pinned_models="[]", hidden_models="[]",
    )
    monkeypatch.setattr(router, "_iter_enabled_endpoints", lambda owner: [endpoint])
    with pytest.raises(RuntimeError, match="requires qwen2.5-coder:7b"):
        resolve_mobs_auto_route("Olá")
