import asyncio
import json
from src.agent_tools.filesystem_tools import ReadFileTool


def test_read_range_reference_matches_actual_returned_lines_without_extra_read(tmp_path, monkeypatch):
    import src.tool_execution as execution
    source=tmp_path/'unicode.py'; source.write_text('um\ndois\ntrês\n',encoding='utf-8')
    monkeypatch.setattr(execution,'_resolve_tool_path',lambda path:str(source))
    result=asyncio.run(ReadFileTool().execute(json.dumps({'path':'src/unicode.py','offset':2,'limit':1}),{}))
    assert result['output']=='dois\n'
    assert result['source_reference']=={'path':'src/unicode.py','start_line':2,'kind':'read_file_snapshot'}
    source.unlink()
    missing=asyncio.run(ReadFileTool().execute('src/unicode.py',{}))
    assert missing['exit_code']==1 and 'source_reference' not in missing


def test_actual_loop_sends_and_persists_same_source_reference(monkeypatch):
    from tests.test_fenced_example_not_executed_for_native_models import _patch_common, _run_loop
    import src.agent_loop as loop
    calls=[]; _patch_common(monkeypatch,calls)
    async def read(*a,**k):
        return 'read_file',{'output':'two\n','exit_code':0,'source_reference':{'path':'src/a.py','start_line':2}}
    monkeypatch.setattr(loop,'execute_tool_block',read)
    events=_run_loop(monkeypatch,'gpt-4o',[],native_calls=[{'id':'read','name':'read_file','arguments':'{"path":"src/a.py","offset":2,"limit":1}'}])
    output=next(e for e in events if e.get('type')=='tool_output')
    metrics=next(e['data'] for e in events if e.get('type')=='metrics')
    assert output['source_reference']['path']=='src/a.py'
    assert metrics['tool_events'][0]['source_reference']==output['source_reference']
