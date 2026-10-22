"""Response reuse investigation, using the actual stream with a fake transport."""
import asyncio
import copy
import json

from src import llm_core


def test_full_history_and_latest_request_change_cache_identity():
    messages = [{'role': 'system', 'content': 'protected'}, {'role': 'user', 'content': 'oi'}]
    key = lambda ms: llm_core._get_cache_key('fixture', 'model', ms, 0.2, 300)
    before = copy.deepcopy(messages)
    assert key(messages) != key(messages + [{'role': 'assistant', 'content': 'Olá'}, {'role': 'user', 'content': 'Você está mandando bem'}])
    assert key(messages) != key([{'role': 'system', 'content': 'other'}, *messages[1:]])
    assert messages == before


def test_stream_does_not_reuse_response_cache_and_passes_each_latest_request(monkeypatch):
    requests = []
    class Response:
        status_code = 200
        def __init__(self, text): self.text = text
        async def aiter_lines(self):
            yield json.dumps({'message': {'content': self.text}, 'done': True})
    class Context:
        def __init__(self, text): self.text = text
        async def __aenter__(self): return Response(self.text)
        async def __aexit__(self, *a): pass
    class Client:
        def stream(self, *args, **kwargs):
            requests.append(copy.deepcopy(kwargs['json']['messages']))
            return Context(requests[-1][-1]['content'])
    monkeypatch.setattr(llm_core, '_get_http_client', lambda: Client())
    monkeypatch.setattr(llm_core, '_is_host_dead', lambda *a: False)
    monkeypatch.setattr(llm_core, '_clear_host_dead', lambda *a: None)
    monkeypatch.setattr(llm_core, 'note_model_activity', lambda *a, **k: None)
    def forbidden(*a): raise AssertionError('stream must not reuse plain response cache')
    monkeypatch.setattr(llm_core, '_get_cached_response', forbidden)
    monkeypatch.setattr(llm_core, '_set_cached_response', forbidden)
    history = [{'role': 'user', 'content': 'oi'}, {'role': 'assistant', 'content': 'Olá'}]
    original = copy.deepcopy(history)
    async def run():
        outputs = []
        for latest in ('oi', 'Você está mandando bem', 'Agora cite meu pedido'):
            messages = history + [{'role': 'user', 'content': latest}]
            chunks = [e async for e in llm_core.stream_llm('http://127.0.0.1:11434', 'fixture', messages)]
            events = [json.loads(line[6:]) for chunk in chunks for line in chunk.splitlines()
                      if line.startswith('data: ') and line != 'data: [DONE]']
            assert ''.join(e.get('delta', '') for e in events) == latest, events
            outputs.append(chunks)
        assert outputs[0] != outputs[1] != outputs[2]
    asyncio.run(run())
    assert history == original
    assert [ms[-1]['content'] for ms in requests] == ['oi', 'Você está mandando bem', 'Agora cite meu pedido']
