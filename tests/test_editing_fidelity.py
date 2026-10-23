import json
from pathlib import Path

import pytest
from src.agent_tools.filesystem_tools import EditFileTool, WriteFileTool, _unified_diff


@pytest.fixture
def confined(tmp_path, monkeypatch):
    from src import tool_execution
    def resolve(raw):
        path=(tmp_path/raw).resolve()
        if not path.is_relative_to(tmp_path.resolve()): raise ValueError('outside fixture')
        return str(path)
    monkeypatch.setattr(tool_execution,'_resolve_tool_path',resolve)
    return tmp_path


@pytest.mark.asyncio
@pytest.mark.parametrize('payload',[
    {'path':'a.txt','old_string':'keep'},
    {'path':'a.txt','old_string':'keep','new_string':'x','replace_all':'false'},
    {'path':'a.txt','old_string':'keep','new_string':None},
    {'path':123,'old_string':'keep','new_string':'x'},
    {'path':'a.txt','old_string':True,'new_string':'x'},
])
async def test_invalid_edit_arguments_never_modify_file(confined,payload):
    original=b'keep\r\n' if 'new_string' not in payload else b'keep keep\r\n'
    path=confined/'a.txt';path.write_bytes(original)
    result=await EditFileTool().execute(json.dumps(payload),{})
    assert result['exit_code']==1
    assert path.read_bytes()==original


@pytest.mark.asyncio
@pytest.mark.parametrize('raw',[
    b'prefix\nold\ntail\n',b'prefix\r\nold\r\ntail\r\n',
    b'\xef\xbb\xbfprefix\r\nold\ntail\r',
])
async def test_edit_preserves_bytes_outside_the_replaced_region(confined,raw):
    path=confined/'a.txt';path.write_bytes(raw)
    result=await EditFileTool().execute(json.dumps({'path':'a.txt','old_string':'old','new_string':'new'}),{})
    assert result['exit_code']==0
    assert path.read_bytes()==raw.replace(b'old',b'new')


@pytest.mark.asyncio
async def test_write_counts_utf8_bytes_and_preserves_literal_line_endings(confined):
    value='ação\nnext\r\nlast\r'
    result=await WriteFileTool().execute(json.dumps({'path':'a.txt','content':value}),{})
    assert result['exit_code']==0
    assert (confined/'a.txt').read_bytes()==value.encode('utf-8')
    assert f'Wrote {len(value.encode("utf-8"))} bytes' in result['output']


@pytest.mark.asyncio
@pytest.mark.parametrize('value',[{'path':'a.txt'},{'path':'a.txt','content':None},{'path':3,'content':'x'}])
async def test_incomplete_json_write_does_not_create_a_file(confined,value):
    result=await WriteFileTool().execute(json.dumps(value),{})
    assert result['exit_code']==1
    assert list(confined.iterdir())==[]


def test_diff_counts_content_with_header_like_prefixes():
    diff=_unified_diff('--old\n','++new\n','a.txt')
    assert diff['added']==1 and diff['removed']==1


def test_diff_explains_final_newline_only_change():
    diff=_unified_diff('same\n','same','a.txt')
    assert diff and diff['text']
    assert diff['added']==0 and diff['removed']==0


@pytest.mark.asyncio
async def test_multiline_matching_preserves_legacy_newline_equivalence(confined):
    path=confined/'a.txt';path.write_bytes(b'head\r\none\r\ntwo\r\ntail\r\n')
    result=await EditFileTool().execute(json.dumps({'path':'a.txt','old_string':'one\ntwo','new_string':'new\ntext'}),{})
    assert result['exit_code']==0
    assert path.read_bytes()==b'head\r\nnew\ntext\r\ntail\r\n'
    assert '(1 replacement)' in result['output']


@pytest.mark.asyncio
async def test_multiline_ambiguity_does_not_choose_a_newline_variant(confined):
    path=confined/'a.txt';original=b'one\r\ntwo\r\none\ntwo\n';path.write_bytes(original)
    args={'path':'a.txt','old_string':'one\ntwo','new_string':'x'}
    result=await EditFileTool().execute(json.dumps(args),{})
    assert result['exit_code']==1 and 'not unique' in result['error']
    assert path.read_bytes()==original
    result=await EditFileTool().execute(json.dumps({**args,'replace_all':True}),{})
    assert result['exit_code']==0 and '(2 replacements)' in result['output']
    assert path.read_bytes()==b'x\r\nx\n'


@pytest.mark.asyncio
async def test_replacement_is_literal_and_explicit_empty_is_supported(confined):
    path=confined/'a.txt';path.write_bytes(b'a[0].*\r\nkeep\r\n')
    result=await EditFileTool().execute(json.dumps({'path':'a.txt','old_string':'a[0].*','new_string':r'\1\literal'}),{})
    assert result['exit_code']==0 and path.read_bytes()==b'\\1\\literal\r\nkeep\r\n'
    result=await EditFileTool().execute(json.dumps({'path':'a.txt','old_string':r'\1\literal','new_string':''}),{})
    assert result['exit_code']==0 and path.read_bytes()==b'\r\nkeep\r\n'
    result=await WriteFileTool().execute(json.dumps({'path':'a.txt','content':''}),{})
    assert result['exit_code']==0 and path.read_bytes()==b''


@pytest.mark.asyncio
@pytest.mark.parametrize('value',['{broken','[]','null','123',None])
async def test_malformed_edit_input_is_a_controlled_failure(confined,value):
    result=await EditFileTool().execute(value,{})
    assert result['exit_code']==1 and 'JSON object required' in result['error']
    assert list(confined.iterdir())==[]


@pytest.mark.asyncio
async def test_unencodable_replacement_and_binary_read_do_not_destroy_content(confined):
    path=confined/'a.txt';original=b'keep\r\n';path.write_bytes(original)
    for tool,args in [(EditFileTool(),{'path':'a.txt','old_string':'keep','new_string':'\ud800'}),
                      (WriteFileTool(),{'path':'a.txt','content':'\ud800'})]:
        result=await tool.execute(json.dumps(args),{})
        assert result['exit_code']==1 and path.read_bytes()==original
    path.write_bytes(b'keep\xff')
    result=await EditFileTool().execute(json.dumps({'path':'a.txt','old_string':'keep','new_string':'changed'}),{})
    assert result['exit_code']==1 and path.read_bytes()==b'keep\xff'


@pytest.mark.asyncio
@pytest.mark.parametrize('old,new',[('absent','new'),('keep','keep'),('','new')])
async def test_failed_or_identical_edit_does_not_touch_original_bytes(confined,old,new):
    path=confined/'a.txt';original=b'keep\r\n';path.write_bytes(original)
    result=await EditFileTool().execute(json.dumps({'path':'a.txt','old_string':old,'new_string':new}),{})
    assert result['exit_code']==1 and path.read_bytes()==original


def test_truncated_diff_is_explicit_without_losing_full_line_counts(monkeypatch):
    from src.agent_tools import filesystem_tools as fs
    monkeypatch.setattr(fs,'MAX_DIFF_LINES',4)
    diff=fs._unified_diff('a\nb\nc\n','x\ny\nz\n','a.txt')
    assert diff['truncated'] is True and 'truncated at 4 lines' in diff['text']
    assert diff['added']==3 and diff['removed']==3


@pytest.mark.asyncio
async def test_crlf_is_one_newline_and_never_two_backtracked_matches(confined):
    path=confined/'a.txt';path.write_bytes(b'head\r\ntail')
    result=await EditFileTool().execute(json.dumps({'path':'a.txt','old_string':'\n\n','new_string':'x'}),{})
    assert result['exit_code']==1 and path.read_bytes()==b'head\r\ntail'
    result=await EditFileTool().execute(json.dumps({'path':'a.txt','old_string':'\n','new_string':'|','replace_all':True}),{})
    assert result['exit_code']==0 and path.read_bytes()==b'head|tail'
    assert '(1 replacement)' in result['output']
