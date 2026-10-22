"""Real transcript persistence and detached replay, without a model or UI."""
import asyncio

import pytest
from src import agent_runs


@pytest.mark.asyncio
async def test_disconnect_and_reopen_replay_each_event_once_without_cancelling_run(monkeypatch):
    monkeypatch.setattr(agent_runs, '_RUNS', {})
    ready, release = asyncio.Event(), asyncio.Event()
    events = ['data: first\n\n', 'data: second\n\n']
    async def provider():
        yield events[0]
        ready.set(); await release.wait()
        yield events[1]
    run = agent_runs.start('one', provider())
    await ready.wait()
    subscriber = agent_runs.subscribe('one')
    assert await anext(subscriber) == events[0]
    await subscriber.aclose()
    assert agent_runs.is_active('one')
    release.set(); await run.task
    assert [event async for event in agent_runs.subscribe('one')] == events
    assert [event async for event in agent_runs.subscribe('one')] == events
    assert [event async for event in agent_runs.subscribe('other')] == []


@pytest.mark.asyncio
async def test_replacement_waits_for_partial_save_and_does_not_mix_conversations(monkeypatch):
    monkeypatch.setattr(agent_runs, '_RUNS', {})
    started, never = asyncio.Event(), asyncio.Event()
    writes = []
    async def first():
        try:
            yield 'old partial'
            started.set(); await never.wait()
        finally:
            await asyncio.sleep(0)
            writes.append('old partial saved')
    old = agent_runs.start('one', first()); await started.wait()
    async def replacement():
        assert writes == ['old partial saved']
        yield 'new answer'
    async def other():
        yield 'other answer'
    new = agent_runs.start('one', replacement())
    unrelated = agent_runs.start('two', other())
    await new.task; await unrelated.task
    assert old.status == 'stopped'
    assert [event async for event in agent_runs.subscribe('one')] == ['new answer']
    assert [event async for event in agent_runs.subscribe('two')] == ['other answer']


def test_reopened_transcripts_keep_latest_request_and_isolate_synthetic_provider_input(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base
    import core.session_manager as sessions
    engine = create_engine('sqlite:///' + str(tmp_path / 'transcripts.sqlite'))
    Base.metadata.create_all(engine)
    monkeypatch.setattr(sessions, 'SessionLocal', sessionmaker(bind=engine))
    manager = sessions.SessionManager()
    for sid in ('one', 'two'):
        manager.create_session(sid, sid, 'http://synthetic.invalid', 'fixture', owner='fixture')
    requests = []
    for sid, prompt in [('one','oi'), ('one','Você está mandando bem.'), ('two','Outro projeto.'), ('one','Agora cite minha mensagem anterior.')]:
        manager.add_message(sid, sessions.ChatMessage(role='user',content=prompt))
        manager = sessions.SessionManager()
        context = manager.get_session(sid).get_context_messages()
        requests.append((sid, context))
        assert context[-1]['role'] == 'user'
        assert context[-1]['content'] == prompt
        manager.add_message(sid, sessions.ChatMessage(role='assistant',content='Resposta sintética: '+prompt))
    assert 'Você está mandando bem.' in [m['content'] for m in requests[-1][1]]
    assert all('Outro projeto.' != m['content'] for m in requests[-1][1])
    assert [m['content'] for m in requests[2][1]] == ['Outro projeto.']
    engine.dispose()
