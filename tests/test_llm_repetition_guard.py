"""Stop native Ollama repetition while preserving ordinary text and code."""
import asyncio
import json

import pytest

from src import llm_core


@pytest.mark.parametrize('unit', ['k', 'ha', 'he', 'rs'])
def test_fragmented_laughter_stops_with_bounded_detection(unit):
    guard = llm_core._DegenerateStreamGuard('qwen2.5-coder:7b')
    assert guard.check('Claro! ') is None
    error = None
    for _ in range(256):
        error = guard.check(unit)
        if error:
            break
    assert error and 'event: error' in error
    assert len(guard.recent_text) <= 1024


def test_normal_laughter_and_long_code_are_not_treated_as_a_loop():
    guard = llm_core._DegenerateStreamGuard('qwen')
    assert guard.check('Kkkkk, boa! Vamos continuar com o projeto.') is None
    for char in '\n```python\nvalue = "' + 'k' * 700 + '"\n```\n':
        assert guard.check(char) is None
    for i in range(150):
        assert guard.check(f'\nvariavel_{i} = {i} + outra_{i}\n') is None


@pytest.mark.parametrize('channel', ['content', 'thinking'])
def test_native_ollama_closes_stream_on_repetition(monkeypatch, channel):
    state = {'reads': 0, 'closed': False}

    class Response:
        status_code = 200

        async def aiter_lines(self):
            for _ in range(600):
                state['reads'] += 1
                yield json.dumps({'message': {channel: 'k'}, 'done': False})
            yield json.dumps({'message': {}, 'done': True})

    class Context:
        async def __aenter__(self):
            return Response()

        async def __aexit__(self, *args):
            state['closed'] = True

    class Client:
        def stream(self, *args, **kwargs):
            return Context()

    monkeypatch.setattr(llm_core, '_get_http_client', lambda: Client())
    monkeypatch.setattr(llm_core, '_is_host_dead', lambda *a: False)
    monkeypatch.setattr(llm_core, '_clear_host_dead', lambda *a: None)
    monkeypatch.setattr(llm_core, 'note_model_activity', lambda *a, **k: None)
    monkeypatch.setattr(llm_core, 'get_context_length', lambda *a: 32768)

    async def collect():
        return [event async for event in llm_core.stream_llm(
            'http://localhost:11434', 'qwen2.5-coder:7b',
            [{'role': 'user', 'content': 'Oi'}], max_tokens=2048)]

    events = asyncio.run(collect())
    assert state['closed']
    assert state['reads'] == 256
    assert sum(event.startswith('event: error') for event in events) == 1
    assert not any('[DONE]' in event for event in events)
