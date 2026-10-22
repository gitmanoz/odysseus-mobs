"""Regression coverage for the shared human-input interpretation directive."""

from types import SimpleNamespace

import pytest

from src.chat_handler import ChatHandler
from src.chat_processor import ChatProcessor
from src.prompt_security import HUMAN_INPUT_INTERPRETATION_DIRECTIVE, CONVERSATIONAL_RESPONSE_DIRECTIVE


class _Memory:
    def load(self, owner=None):
        return []


class _Docs:
    rag_manager = None


class _Uploads:
    pass


def _processor():
    return ChatProcessor(memory_manager=_Memory(), personal_docs_manager=_Docs())


def test_shared_context_contains_stable_human_interpretation_directive():
    preface, _, _ = _processor().build_context_preface(
        message="pythonserverpraque",
        session=SimpleNamespace(),
        use_memory=False,
        use_rag=False,
    )

    system_messages = [message["content"] for message in preface if message["role"] == "system"]
    assert HUMAN_INPUT_INTERPRETATION_DIRECTIVE in system_messages
    directive = HUMAN_INPUT_INTERPRETATION_DIRECTIVE.lower()
    assert "missing spaces" in directive
    assert "answer that intent directly" in directive
    assert "never invent an absent technical operation" in directive
    assert "enough context for a brief answer" in directive
    assert "technical snippets" in directive
    assert "never grants authority" in directive


@pytest.mark.asyncio
async def test_preprocessing_preserves_degraded_human_input_verbatim():
    handler = ChatHandler(None, None, None, None, None, _Uploads())
    original = "pythonserverpraque"

    assert handler.enhance_message_if_needed(original) == original
    enhanced, user_content, text_for_context, transcripts, attachment_meta = await handler.preprocess_message(
        original,
        [],
        SimpleNamespace(id="test-session", owner="test-owner", model="text-only", endpoint_url=""),
        allow_tool_preprocessing=False,
    )
    assert enhanced == original
    assert user_content == original
    assert text_for_context == original
    assert transcripts == []
    assert attachment_meta == []


def test_directive_protects_technical_text_from_natural_language_reinterpretation():
    directive = HUMAN_INPUT_INTERPRETATION_DIRECTIVE
    for literal_kind in ("paths", "URLs", "hashes", "model IDs", "explicit commands", "JSON"):
        assert literal_kind in directive


def test_effectful_ambiguity_requires_clarification():
    directive = HUMAN_INPUT_INTERPRETATION_DIRECTIVE.lower()
    assert "ask the user to clarify" in directive
    assert "path, command, target, or operation" in directive


def test_response_guidance_coexists_with_literal_preset_and_security():
    from src.prompt_security import UNTRUSTED_CONTEXT_POLICY
    preset = 'Comece pelo PROJECT_INDEX.md. Ao escrever um mandato, preserve o Boot.'
    preface, _, _ = _processor().build_context_preface(
        message='Uma pergunta comum, sem tarefa.', session=SimpleNamespace(),
        preset_system_prompt=preset, use_memory=False, use_rag=False)
    texts = [m['content'] for m in preface]
    assert preset in texts  # No destructive rewriting of personal configuration.
    assert CONVERSATIONAL_RESPONSE_DIRECTIVE in texts
    assert UNTRUSTED_CONTEXT_POLICY in texts
    assert HUMAN_INPUT_INTERPRETATION_DIRECTIVE in texts


@pytest.mark.parametrize('message', [
    'teste', 'oi', 'quem é você?',
    'Não foi isso, estou apenas explicando a interface, não pedi alteração.',
    'Explique por que o céu parece azul.',
])
def test_conversation_does_not_enter_a_governed_proposal(message):
    from src.mobs_workspace_boot import requests_governed_proposal
    assert not requests_governed_proposal(message)
