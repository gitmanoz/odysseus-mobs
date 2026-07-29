from types import SimpleNamespace

from src.mobs_auto_router import (
    MOBS_CODER_MODEL,
    MOBS_GENERAL_MODEL,
    choose_mobs_model,
    is_mobs_auto,
)


def test_general_conversation_uses_general_model():
    model, reason = choose_mobs_model("Explique este conceito de forma simples")
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
    assert is_mobs_auto("__mobs_auto__")
    assert not is_mobs_auto("qwen3:8b")
