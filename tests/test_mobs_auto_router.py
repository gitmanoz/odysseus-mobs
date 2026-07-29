from types import SimpleNamespace

from src.mobs_auto_router import (
    MOBS_AUTO_DISPLAY_NAME,
    MOBS_AUTO_MODEL_ID,
    MOBS_CODER_MODEL,
    MOBS_GENERAL_MODEL,
    ResolvedMobsRoute,
    _openai_compatible_chat_url,
    choose_mobs_model,
    is_mobs_auto,
)


def test_general_conversation_uses_general_model():
    model, reason = choose_mobs_model("oi")
    assert model == MOBS_GENERAL_MODEL
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
    assert not is_mobs_auto(MOBS_GENERAL_MODEL)


def test_resolved_route_preserves_symbolic_identity():
    route = ResolvedMobsRoute(
        endpoint_id="local",
        endpoint_url="http://host.docker.internal:11434/v1/chat/completions",
        model=MOBS_GENERAL_MODEL,
        headers={},
        reason="general_prompt",
    )
    assert route.requested_model == MOBS_AUTO_MODEL_ID
    assert route.display_name == MOBS_AUTO_DISPLAY_NAME
    assert route.disable_thinking is True


def test_mobs_auto_uses_ollama_openai_compatible_endpoint():
    assert _openai_compatible_chat_url("http://host.docker.internal:11434") == (
        "http://host.docker.internal:11434/v1/chat/completions"
    )
    assert _openai_compatible_chat_url("http://localhost:11434/v1") == (
        "http://localhost:11434/v1/chat/completions"
    )
