"""Actual HTTP chat cleanup with synthetic generation and failed persistence."""
import asyncio
import pytest

from tests.test_mobs_chat_identity import chat
from tests.test_mobs_mandate_builder import projects


@pytest.mark.parametrize('mode', ['agent', 'chat'])
def test_interrupted_agent_save_failure_is_reported_and_registry_cleared(chat, monkeypatch, mode):
    from routes import chat_routes as routes
    from src import agent_runs
    state = {'interrupted': False, 'save_attempts': 0}
    monkeypatch.setattr(agent_runs, '_RUNS', {})
    monkeypatch.setattr(routes, 'get_session_mode', lambda *a: 'agent')
    async def interrupted(*a, **k):
        yield 'data: {"delta":"partial answer"}\n\n'
        state['interrupted'] = True
        raise asyncio.CancelledError
    def save():
        if state['interrupted']:
            state['save_attempts'] += 1
            raise OSError('private path and disk details must not reach client')
    monkeypatch.setattr(routes, 'stream_agent_loop', interrupted)
    monkeypatch.setattr(routes, 'stream_llm_with_fallback', interrupted)
    monkeypatch.setattr(chat.manager, 'save_sessions', save)
    response = chat.post(message='Explique uma função Python.', workspace='', mode=mode)
    assert response.status_code == 200
    assert state['save_attempts'] == 1, response.text
    assert 'partial answer' in response.text
    assert 'event: error' in response.text
    assert 'private path' not in response.text
    assert agent_runs.get_status('s') == 'error'
    assert 's' not in routes._active_streams
