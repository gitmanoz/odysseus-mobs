import pytest

from src import model_context
from src.mobs_institutional_boot import InstitutionalBootError

URL = 'http://127.0.0.1:11434/v1/chat/completions'
MESSAGES = [{'role': 'system', 'content': 'Reviewed authority remains intact.'}]


def test_compat_reload_to_4k_blocks_response_before_it_can_be_used(monkeypatch):
    readings = iter([(32768, True), (4096, True)])
    monkeypatch.setattr(model_context, 'get_context_length_known', lambda *a: next(readings))
    model_context.verify_governed_ollama_window(URL, 'model', MESSAGES, 32768, 2048)
    with pytest.raises(InstitutionalBootError, match='window changed'):
        model_context.verify_governed_ollama_window(URL, 'model', MESSAGES, 32768, 2048)


@pytest.mark.parametrize('reading', [(4096, False), (32768, False)])
def test_unverified_runner_fails_closed(monkeypatch, reading):
    monkeypatch.setattr(model_context, 'get_context_length_known', lambda *a: reading)
    with pytest.raises(InstitutionalBootError, match='unverified'):
        model_context.verify_governed_ollama_window(URL, 'model', MESSAGES, 32768, 2048)


def test_stable_window_preserves_protected_message(monkeypatch):
    monkeypatch.setattr(model_context, 'get_context_length_known', lambda *a: (32768, True))
    before = [dict(m) for m in MESSAGES]
    model_context.verify_governed_ollama_window(URL, 'model', MESSAGES, 32768, 2048)
    assert MESSAGES == before


@pytest.mark.parametrize('output', [0, 1000])
def test_output_reserve_is_not_omitted(monkeypatch, output):
    monkeypatch.setattr(model_context, 'get_context_length_known', lambda *a: (4096, True))
    large = [{'role': 'system', 'content': 'x' * 11000}]
    with pytest.raises(InstitutionalBootError, match='output reserve'):
        model_context.verify_governed_ollama_window(URL, 'model', large, 4096, output)


def test_unrelated_provider_does_not_gain_ollama_probe(monkeypatch):
    def unexpected(*args):
        raise AssertionError('Must not query local Ollama for another provider')
    monkeypatch.setattr(model_context, 'get_context_length_known', unexpected)
    model_context.verify_governed_ollama_window('https://api.example.org/v1/chat/completions',
                                               'model', MESSAGES, 32768, 2048)
