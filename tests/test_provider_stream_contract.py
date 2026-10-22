"""Synthetic wire responses; never contact a model or dispatch a command."""
import asyncio
import json

import httpx
import pytest
from src import llm_core
from src.agent_tools import function_call_to_tool_block


def drive(monkeypatch, lines, *, native=False, failure=None, complete=True):
    state = {'closed': False}
    class Response:
        status_code = 200
        async def aiter_lines(self):
            for line in lines:
                yield json.dumps(line) if native else 'data: ' + json.dumps(line)
            if failure: raise failure
            if not native and complete:
                yield 'data: [DONE]'
    class Context:
        async def __aenter__(self): return Response()
        async def __aexit__(self, *args): state['closed'] = True
    class Client:
        def stream(self, *args, **kwargs): return Context()
    monkeypatch.setattr(llm_core, '_get_http_client', lambda: Client())
    monkeypatch.setattr(llm_core, '_is_host_dead', lambda *a: False)
    monkeypatch.setattr(llm_core, '_clear_host_dead', lambda *a: None)
    monkeypatch.setattr(llm_core, 'note_model_activity', lambda *a, **k: None)
    async def collect():
        return [e async for e in llm_core.stream_llm(
            'http://127.0.0.1:11434' if native else 'https://fixture.invalid/v1',
            'fixture', [{'role': 'user', 'content': 'fixture'}],
            tools=[{'type': 'function', 'function': {'name': 'ls', 'parameters': {}}}])]
    chunks = asyncio.run(collect())
    events = [json.loads(line[6:]) for chunk in chunks for line in chunk.splitlines()
              if line.startswith('data: ') and line != 'data: [DONE]']
    assert state['closed']
    return events


def delta(calls): return {'choices': [{'delta': {'tool_calls': calls}}]}
def call(index, name, args):
    return {'index': index, 'id': f'c{index}', 'function': {'name': name, 'arguments': args}}


@pytest.mark.parametrize('bad', [4, [], 'bad', {'function': 7},
    call(0, 'ls', {'path': '.'}), call('bad', 'ls', '{}')])
def test_bad_delta_does_not_drop_valid_sibling(monkeypatch, bad):
    events = drive(monkeypatch, [delta([bad, call(1, 'ls', '{}')])])
    calls = [c for e in events if e.get('type') == 'tool_calls' for c in e['calls']]
    assert [c['id'] for c in calls] == ['c1']


@pytest.mark.parametrize('native', [False, True])
def test_incomplete_json_never_converts(monkeypatch, native):
    lines = [{'message': {'tool_calls': [call(0, 'bash', '{"command":')]}, 'done': True}] if native else [delta([call(0, 'bash', '{"command":')])]
    events = drive(monkeypatch, lines, native=native)
    for e in events:
        for c in e.get('calls', []):
            assert function_call_to_tool_block(c['name'], c['arguments']) is None


@pytest.mark.parametrize('native', [False, True])
@pytest.mark.parametrize('failure', [httpx.ReadTimeout('fixture'), httpx.ReadError('fixture')])
def test_interruption_preserves_text_but_never_releases_calls(monkeypatch, native, failure):
    lines = [{'message': {'content': 'partial', 'tool_calls': [call(0, 'ls', {})]}}] if native else [delta([call(0, 'ls', '{}')]), {'choices': [{'delta': {'content': 'partial'}}]}]
    events = drive(monkeypatch, lines, native=native, failure=failure)
    assert any(e.get('delta') == 'partial' for e in events)
    assert any(e.get('status') in (502, 504) for e in events)
    assert not any(e.get('type') == 'tool_calls' for e in events)


@pytest.mark.parametrize('args', [False, 0, [], 'bad'])
def test_native_invalid_arguments_do_not_become_empty_object(monkeypatch, args):
    events = drive(monkeypatch, [{'message': {'tool_calls': [call(0, 'ls', args)]}, 'done': True}], native=True)
    for e in events:
        for c in e.get('calls', []):
            assert function_call_to_tool_block(c['name'], c['arguments']) is None


def test_fragmented_parallel_arguments_stay_in_their_slots(monkeypatch):
    events = drive(monkeypatch, [delta([call(0, 'read_file', '{"path":"'), call(2, 'ls', '{}')]),
        delta([{'index': 0, 'function': {'arguments': 'src/a.py"}'}}])])
    calls = next(e['calls'] for e in events if e.get('type') == 'tool_calls')
    assert [(c['name'], json.loads(c['arguments'])) for c in calls] == [('read_file', {'path': 'src/a.py'}), ('ls', {})]


@pytest.mark.parametrize('function', [{'arguments': []}, 7, {'name': []}])
def test_invalid_continuation_invalidates_previously_valid_slot(monkeypatch, function):
    events = drive(monkeypatch, [delta([call(0, 'ls', '{}')]),
        delta([{'index': 0, 'function': function}, call(1, 'ls', '{}')])])
    calls = next(e['calls'] for e in events if e.get('type') == 'tool_calls')
    assert [c['id'] for c in calls] == ['c1']


def test_native_eof_without_done_is_error_not_success(monkeypatch):
    events = drive(monkeypatch, [{'message': {'content': 'partial', 'tool_calls': [call(0, 'ls', {})]}}], native=True)
    assert any(e.get('status') == 502 and 'before done' in e.get('error', '') for e in events)
    assert not any(e.get('type') == 'tool_calls' for e in events)


def test_native_complete_calls_and_usage_keep_order(monkeypatch):
    events = drive(monkeypatch, [{'message': {'tool_calls': [7, call(0, 'ls', {}), call(1, 'read_file', {'path': 'src/a.py'})]}},
        {'done': True, 'prompt_eval_count': 30, 'eval_count': 7}], native=True)
    assert [(c['name'], json.loads(c['arguments'])) for c in events[0]['calls']] == [('ls', {}), ('read_file', {'path': 'src/a.py'})]
    assert events[1] == {'type': 'usage', 'data': {'input_tokens': 30, 'output_tokens': 7}}


@pytest.mark.parametrize('native', [False, True])
def test_repeated_id_on_two_calls_is_not_executable(monkeypatch, native):
    first, second = call(0, 'ls', {} if native else '{}'), call(1, 'ls', {} if native else '{}')
    second['id'] = first['id']
    lines = [{'message': {'tool_calls': [first, second]}, 'done': True}] if native else [delta([first, second])]
    events = drive(monkeypatch, lines, native=native)
    assert not any(e.get('calls') for e in events)


@pytest.mark.parametrize('conflict', ['id', 'name'])
def test_conflicting_identity_cannot_overwrite_an_accumulated_call(monkeypatch, conflict):
    first = call(0, 'ls', '{}')
    second = {'index': 0, 'function': {}}
    if conflict == 'id': second['id'] = 'different'
    else: second['function']['name'] = 'get_workspace'
    events = drive(monkeypatch, [delta([first]), delta([second])])
    assert not any(e.get('calls') for e in events)


def test_null_index_continuation_uses_id_instead_of_last_parallel_slot(monkeypatch):
    events = drive(monkeypatch, [delta([call(None, 'read_file', '{"path":"')]),
        delta([{'id': 'other', 'function': {'name': 'ls', 'arguments': '{}'}}]),
        delta([{'id': 'cNone', 'function': {'arguments': 'src/a.py"}'}}])])
    calls = next(e['calls'] for e in events if e.get('type') == 'tool_calls')
    assert [json.loads(c['arguments']) for c in calls] == [{'path': 'src/a.py'}, {}]


def test_rejected_duplicate_does_not_poison_unrelated_call(monkeypatch):
    first, conflict, sibling = call(0, 'ls', '{}'), call(1, 'ls', '{}'), call(2, 'get_workspace', '{}')
    conflict['id'] = first['id']
    events = drive(monkeypatch, [delta([first, conflict, sibling])])
    assert [c['id'] for e in events for c in e.get('calls', [])] == ['c2']


def test_native_identical_calls_without_ids_are_not_content_deduplicated(monkeypatch):
    events = drive(monkeypatch, [{'message': {'tool_calls': [
        {'function': {'name': 'ls', 'arguments': {}}},
        {'function': {'name': 'ls', 'arguments': {}}}]}, 'done': True}], native=True)
    calls = next(e['calls'] for e in events if e.get('type') == 'tool_calls')
    assert len(calls) == 2 and calls[0]['id'] != calls[1]['id']


@pytest.mark.parametrize('native', [False, True])
@pytest.mark.parametrize('bad_id', [False, 0, ['bad']])
def test_non_string_id_is_rejected_without_dropping_sibling(monkeypatch, native, bad_id):
    first, sibling = call(0, 'ls', {} if native else '{}'), call(1, 'ls', {} if native else '{}')
    first['id'] = bad_id
    lines = [{'message': {'tool_calls': [first, sibling]}, 'done': True}] if native else [delta([first, sibling])]
    events = drive(monkeypatch, lines, native=native)
    assert [c['id'] for e in events for c in e.get('calls', [])] == ['c1']


def test_openai_eof_without_completion_never_releases_pending_calls(monkeypatch):
    events = drive(monkeypatch, [delta([call(0, 'ls', '{}')])], complete=False)
    assert not any(e.get('calls') for e in events)
    assert any(e.get('status') == 502 for e in events)


def test_openai_finish_reason_can_confirm_completion_without_done(monkeypatch):
    events = drive(monkeypatch, [delta([call(0, 'ls', '{}')]),
        {'choices': [{'delta': {}, 'finish_reason': 'tool_calls'}]}], complete=False)
    assert len(next(e['calls'] for e in events if e.get('type') == 'tool_calls')) == 1


@pytest.mark.parametrize('reason', ['length', 'content_filter'])
def test_truncated_calls_never_execute_even_with_done_marker(monkeypatch, reason):
    events = drive(monkeypatch, [delta([call(0, 'ls', '{}')]),
        {'choices': [{'delta': {}, 'finish_reason': reason}]}])
    assert not any(e.get('calls') for e in events)
    assert any(e.get('status') == 502 for e in events)
