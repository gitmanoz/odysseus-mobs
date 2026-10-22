"""Cancellation before startup and while awaiting a previous partial save."""
import asyncio

import pytest
from src import agent_runs as runs


@pytest.mark.asyncio
async def test_stop_before_first_tick_is_terminal_and_closes_generator(monkeypatch):
    monkeypatch.setattr(runs, '_RUNS', {})
    closed = []
    class Source:
        def __aiter__(self): return self
        async def __anext__(self):
            raise AssertionError('stopped source must not begin')
        async def aclose(self): closed.append(True)
    run = runs.start('one', Source())
    assert runs.stop('one')
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert run.status == 'stopped'
    assert not runs.is_active('one')
    assert closed == [True]
    assert [e async for e in runs.subscribe('one')] == []


@pytest.mark.asyncio
async def test_cancel_replacement_during_previous_save_is_terminal(monkeypatch):
    monkeypatch.setattr(runs, '_RUNS', {})
    started, saving, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def original():
        try:
            yield 'partial'
            started.set()
            await asyncio.Event().wait()
        finally:
            saving.set()
            await release.wait()
    old = runs.start('one', original())
    await started.wait()
    closed = []
    class Replacement:
        def __aiter__(self): return self
        async def __anext__(self): raise AssertionError('must wait for save')
        async def aclose(self): closed.append(True)
    new = runs.start('one', Replacement())
    await saving.wait()
    assert runs.stop('one')
    await asyncio.sleep(0)
    assert new.status == 'stopped'
    assert closed == [True]
    assert not old.task.done()  # partial save is still being awaited
    release.set()
    await old.task
    await new.task
    assert [e async for e in runs.subscribe('one')] == []


@pytest.mark.asyncio
async def test_repeated_stop_and_third_send_preserve_original_save_barrier(monkeypatch):
    monkeypatch.setattr(runs, '_RUNS', {})
    started, saving, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    saved = []
    async def original():
        try:
            yield 'partial'
            started.set()
            await asyncio.Event().wait()
        finally:
            saving.set()
            await release.wait()
            saved.append('partial saved')
    old = runs.start('one', original()); await started.wait()
    async def unused():
        yield 'must not start'
    middle = runs.start('one', unused()); await saving.wait()
    assert runs.stop('one')
    await asyncio.sleep(0)
    assert runs.stop('one')
    async def newest():
        assert saved == ['partial saved']
        yield 'new answer'
    new = runs.start('one', newest())
    await asyncio.sleep(0)
    assert new.buffer == []
    assert not middle.task.done()
    release.set()
    await new.task; await old.task; await middle.task
    assert new.status == 'done'
    assert new.buffer == ['new answer']
    assert middle.status == 'stopped'


@pytest.mark.asyncio
async def test_failed_source_keeps_partial_replay_and_error_status(monkeypatch):
    monkeypatch.setattr(runs, '_RUNS', {})
    async def failed():
        yield 'data: partial\n\n'
        raise TimeoutError('synthetic timeout')
    run = runs.start('one', failed())
    await run.task
    replay = [e async for e in runs.subscribe('one')]
    assert replay[0] == 'data: partial\n\n'
    assert 'event: error' in replay[1]
    assert replay[-1] == 'data: [DONE]\n\n'
    assert run.status == 'error'
    assert not runs.is_active('one')


@pytest.mark.asyncio
async def test_cleanup_failure_is_visible_and_other_session_is_independent(monkeypatch):
    monkeypatch.setattr(runs, '_RUNS', {})
    class Source:
        def __aiter__(self): return self
        async def __anext__(self): raise AssertionError('must not start')
        async def aclose(self): raise OSError('private storage details')
    failed = runs.start('one', Source())
    assert runs.stop('one')
    async def unrelated(): yield 'other answer'
    other = runs.start('two', unrelated())
    await failed.task; await other.task
    replay = ''.join([e async for e in runs.subscribe('one')])
    assert failed.status == 'error'
    assert 'event: error' in replay and 'private storage' not in replay
    assert other.status == 'done'
    assert [e async for e in runs.subscribe('two')] == ['other answer']
