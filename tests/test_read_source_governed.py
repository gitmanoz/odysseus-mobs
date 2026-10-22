"""Real governed read/dispatcher, synthetic model, temporary institutional fixture."""
import json
from tests.test_mobs_institutional_boot import mandate, loop_setup, run_governed


def test_governed_read_reference_binds_existing_mandate_baseline(mandate, monkeypatch):
    loop=loop_setup(monkeypatch)
    async def model(*a,**k):
        yield 'data: '+json.dumps({'type':'tool_calls','calls':[{'id':'read','name':'read_file','arguments':'{"path":"AI_CONTEXT.md"}'}]})+'\n\n'
        yield 'data: [DONE]\n\n'
    monkeypatch.setattr(loop,'stream_llm_with_fallback',model)
    chunks=run_governed(loop,mandate)
    events=[json.loads(line[6:]) for chunk in chunks for line in chunk.splitlines() if line.startswith('data: {')]
    output=next(e for e in events if e.get('type')=='tool_output')
    assert output['exit_code']==0
    reference=output['source_reference']
    assert reference['path']=='AI_CONTEXT.md'
    assert reference['baseline_head']==mandate['target']['head']
    assert reference['baseline_working_tree_sha256']==mandate['target']['working_tree_sha256']
    assert reference['workspace']==mandate['target']['path']
    assert any(e.get('type')=='institutional_verified' for e in events)
