"""Preserve observed tool results when an existing governance gate blocks later."""
import json
from types import SimpleNamespace

import pytest
import src.agent_loop as loop
import src.mobs_institutional_boot as boot
from tests.test_mobs_chat_identity import chat, propose, event
from tests.test_mobs_mandate_builder import projects


@pytest.mark.asyncio
async def test_block_after_command_keeps_receipt_and_partial_history_metrics(monkeypatch):
    receipt = {'command':'python -m pytest -q tests/test_probe.py','exit_code':0}
    context = SimpleNamespace(review_record={'reviewer':'tester'}, source={},target={},documents={},
                              execution=SimpleNamespace(allowed_tools={'bash'}),mutation_ledger=[receipt])
    monkeypatch.setattr(boot,'institutional_boot',lambda *a: context)
    monkeypatch.setattr('src.tool_security.owner_is_admin_or_single_user',lambda owner: True)
    async def failing(*args,**kwargs):
        for event in [
            {'type':'agent_prep','data':{'prompt_build':0.1},'context_profile':{'message_tokens_estimated':30000}},
            {'type':'tool_start','tool':'bash','command':receipt['command'],'round':1},
            {'type':'institutional_command','data':receipt},
            {'type':'tool_output','tool':'bash','command':receipt['command'],'output':'1 passed','exit_code':0},
            {'type':'agent_step','round':2},
        ]:
            yield 'data: '+json.dumps(event)+'\n\n'
        raise boot.InstitutionalBootError('Institutional context exceeds model capacity')
    monkeypatch.setattr(loop,'_stream_agent_loop',failing)
    chunks=[c async for c in loop.stream_agent_loop('local','fixture',[],mobs_execution={},owner='tester',workspace='fixture')]
    events=[json.loads(c[6:]) for c in chunks if c.startswith('data: {')]
    blocked=next(e for e in events if e.get('type')=='institutional_blocked')
    metrics=next(e['data'] for e in events if e.get('type')=='metrics')
    assert blocked['ledger']==[receipt]
    assert metrics['incomplete'] is True
    assert metrics['tool_events'][0]['output']=='1 passed'
    assert metrics['tool_events'][0]['exit_code']==0
    assert metrics['agent_rounds']==2
    assert metrics['agent_prep_breakdown']=={'prompt_build':0.1}
    assert metrics['initial_context_profile']['message_tokens_estimated']==30000
    assert not any(e.get('type')=='institutional_verified' for e in events)
    assert chunks[-1]=='data: [DONE]\n\n'


def test_http_block_passes_observed_result_to_existing_history_save(chat, monkeypatch):
    from src.mobs_mandate_builder import load_proposal
    from routes.chat_helpers import save_assistant_response
    from routes import chat_routes
    monkeypatch.setattr(chat_routes, 'save_assistant_response', save_assistant_response)
    saved = []
    monkeypatch.setattr(chat.sess, 'add_message', saved.append)

    async def failing(*args, **kwargs):
        # Synthetic execution events test persistence only, not Python/TEB.
        yield 'data: '+json.dumps({'type':'agent_prep','data':{'prompt_build':0.1},
                                  'context_profile':{'message_tokens_estimated':30000}})+'\n\n'
        yield 'data: '+json.dumps({'type':'tool_start','tool':'bash','command':'fixture pytest','round':1})+'\n\n'
        yield 'data: '+json.dumps({'type':'tool_output','tool':'bash','command':'fixture pytest',
                                  'output':'synthetic result retained','exit_code':1})+'\n\n'
        raise boot.InstitutionalBootError('synthetic followup capacity block')

    proposal = propose(chat)
    event(chat.post('review', proposal, message=''), 'mobs_authority_reviewed')
    monkeypatch.setattr(loop, '_stream_agent_loop', failing)
    response = chat.post('approve', proposal, message='')
    assert response.status_code == 200
    assert 'synthetic followup capacity block' in response.text
    assert '"type": "agent_prep"' in response.text
    assert load_proposal('s')['status'] == 'blocked'
    metadata = [message.metadata for message in saved if message.role == 'assistant'][-1]
    assert metadata['incomplete'] is True
    assert metadata['tool_events'][0]['output'] == 'synthetic result retained'
    assert metadata['tool_events'][0]['exit_code'] == 1
