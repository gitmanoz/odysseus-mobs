import json
import pytest
from src.agent_tools.filesystem_tools import ApplyPatchTool


@pytest.fixture
def confined(tmp_path,monkeypatch):
    from src import tool_execution
    def resolve(raw):
        path=(tmp_path/raw).resolve()
        if not path.is_relative_to(tmp_path.resolve()):raise ValueError('outside fixture')
        return str(path)
    monkeypatch.setattr(tool_execution,'_resolve_tool_path',resolve)
    return tmp_path


def patch(*ops):
    return '*** Begin Patch\n'+'\n'.join(ops)+'\n*** End Patch'


@pytest.mark.asyncio
async def test_update_requires_whole_line_context(confined):
    p=confined/'a.txt';p.write_bytes(b'prefix_old_suffix\n')
    result=await ApplyPatchTool().execute(patch('*** Update File: a.txt\n@@\n-old\n+new'),{})
    assert result['exit_code']==1 and p.read_bytes()==b'prefix_old_suffix\n'


@pytest.mark.asyncio
async def test_duplicate_resolved_targets_are_rejected_before_writing(confined):
    p=confined/'a.txt';p.write_bytes(b'one\ntwo\n')
    result=await ApplyPatchTool().execute(patch('*** Update File: a.txt\n@@\n-one\n+ONE','*** Update File: ./a.txt\n@@\n-two\n+TWO'),{})
    assert result['exit_code']==1 and p.read_bytes()==b'one\ntwo\n'


@pytest.mark.asyncio
async def test_ancestor_file_targets_are_rejected_before_creation(confined):
    result=await ApplyPatchTool().execute(patch('*** Add File: parent\n+file','*** Add File: parent/child\n+child'),{})
    assert result['exit_code']==1 and list(confined.iterdir())==[]


@pytest.mark.asyncio
async def test_invalid_utf8_in_later_operation_does_not_write_earlier_file(confined):
    args={'patch_text':patch('*** Add File: a.txt\n+good','*** Add File: b.txt\n+\ud800')}
    result=await ApplyPatchTool().execute(json.dumps(args),{})
    assert result['exit_code']==1 and list(confined.iterdir())==[]


@pytest.mark.asyncio
@pytest.mark.parametrize('original',[b'head\nold\ntail\n',b'\xef\xbb\xbfhead\r\nold\ntail\r',b'old'])
async def test_patch_preserves_unmodified_bytes_and_final_newline(confined,original):
    p=confined/'a.txt';p.write_bytes(original)
    result=await ApplyPatchTool().execute(patch('*** Update File: a.txt\n@@\n-old\n+new'),{})
    assert result['exit_code']==0 and p.read_bytes()==original.replace(b'old',b'new')


@pytest.mark.asyncio
async def test_invalid_second_context_leaves_both_files_untouched(confined):
    for name in ('a.txt','b.txt'):(confined/name).write_bytes(b'old\n')
    result=await ApplyPatchTool().execute(patch('*** Update File: a.txt\n@@\n-old\n+new','*** Update File: b.txt\n@@\n-absent\n+new'),{})
    assert result['exit_code']==1
    assert all((confined/name).read_bytes()==b'old\n' for name in ('a.txt','b.txt'))


@pytest.mark.asyncio
@pytest.mark.parametrize('value',[None,123,{'patch':True},{'patch_text':'x','patch':'y'},{'patch_text':None},{}])
async def test_malformed_patch_arguments_are_controlled_failures(confined,value):
    result=await ApplyPatchTool().execute(json.dumps(value) if isinstance(value,dict) else value,{})
    assert result['exit_code']==1 and list(confined.iterdir())==[]


@pytest.mark.asyncio
@pytest.mark.parametrize('alias',['patch_text','patchText','patch'])
async def test_valid_json_alias_and_add_are_literal_utf8(confined,alias):
    result=await ApplyPatchTool().execute(json.dumps({alias:patch('*** Add File: src/a.txt\n+ação\n+next')}),{})
    assert result['exit_code']==0 and (confined/'src/a.txt').read_bytes()=='ação\nnext\n'.encode()


@pytest.mark.asyncio
async def test_valid_patch_updates_two_files_preserving_local_endings(confined):
    (confined/'a.txt').write_bytes(b'head\r\nold\r\ntail\r\n')
    (confined/'b.txt').write_bytes(b'old')
    result=await ApplyPatchTool().execute(patch('*** Update File: a.txt\n@@\n head\n-old\n+new\n tail','*** Update File: b.txt\n@@\n-old\n+new'),{})
    assert result['exit_code']==0 and '(2 files' in result['output']
    assert (confined/'a.txt').read_bytes()==b'head\r\nnew\r\ntail\r\n'
    assert (confined/'b.txt').read_bytes()==b'new'
    assert result['diff']['added']==2 and result['diff']['removed']==2


@pytest.mark.asyncio
@pytest.mark.parametrize('hunks',[
    '@@\n+unanchored',
    '@@\n-two\n+TWO\n@@\n-one\n+ONE',
    '@@\n-one\n+ONE\n@@\n-ONE\n+OTHER',
])
async def test_unanchored_reverse_and_overlapping_hunks_are_rejected(confined,hunks):
    p=confined/'a.txt';original=b'one\ntwo\n';p.write_bytes(original)
    result=await ApplyPatchTool().execute(patch('*** Update File: a.txt\n'+hunks),{})
    assert result['exit_code']==1 and p.read_bytes()==original


@pytest.mark.asyncio
async def test_ambiguous_whole_line_context_is_rejected(confined):
    p=confined/'a.txt';original=b'old\nold\n';p.write_bytes(original)
    result=await ApplyPatchTool().execute(patch('*** Update File: a.txt\n@@\n-old\n+new'),{})
    assert result['exit_code']==1 and 'matched 2 times' in result['error']
    assert p.read_bytes()==original


@pytest.mark.asyncio
async def test_blank_row_and_eof_append_have_real_line_boundaries(confined):
    p=confined/'a.txt';p.write_bytes(b'head\r\n\r\ntail')
    result=await ApplyPatchTool().execute(patch('*** Update File: a.txt\n@@\n-\n+middle'),{})
    assert result['exit_code']==0 and p.read_bytes()==b'head\r\nmiddle\r\ntail'
    result=await ApplyPatchTool().execute(patch('*** Update File: a.txt\n@@\n tail\n+end'),{})
    assert result['exit_code']==0 and p.read_bytes()==b'head\r\nmiddle\r\ntail\r\nend'


@pytest.mark.asyncio
async def test_delete_and_add_are_prepared_together(confined):
    (confined/'a.txt').write_bytes(b'old\r\n')
    result=await ApplyPatchTool().execute(patch('*** Delete File: a.txt','*** Add File: b.txt\n+new'),{})
    assert result['exit_code']==0 and not (confined/'a.txt').exists()
    assert (confined/'b.txt').read_bytes()==b'new\n'


@pytest.mark.asyncio
async def test_combined_diff_reports_truncation_and_full_counts(confined,monkeypatch):
    from src.agent_tools import filesystem_tools
    monkeypatch.setattr(filesystem_tools,'MAX_DIFF_LINES',4)
    for name in ('a.txt','b.txt'):(confined/name).write_bytes(b'old\n')
    result=await ApplyPatchTool().execute(patch('*** Update File: a.txt\n@@\n-old\n+new','*** Update File: b.txt\n@@\n-old\n+new'),{})
    assert result['exit_code']==0 and result['diff']['truncated'] is True
    assert result['diff']['added']==2 and result['diff']['removed']==2


@pytest.mark.parametrize('bad_file',['a.txt','b.txt'])
def test_private_two_file_adapter_rejects_partial_line_context_before_writes(tmp_path,bad_file):
    from src.windows_native_execution import _apply_private_patch, TrustedExecutionUnavailable
    before={name:b'prefix_old_suffix\n' if name==bad_file else b'old\n' for name in ('a.txt','b.txt')}
    for name,content in before.items():(tmp_path/name).write_bytes(content)
    payload=patch('*** Update File: a.txt\n@@\n-old\n+new','*** Update File: b.txt\n@@\n-old\n+new')
    with pytest.raises(TrustedExecutionUnavailable,match='cannot apply'):
        _apply_private_patch(tmp_path,payload,('a.txt','b.txt'),('a.txt','b.txt'),())
    assert all((tmp_path/name).read_bytes()==content for name,content in before.items())
