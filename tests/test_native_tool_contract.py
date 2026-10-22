"""Malformed provider envelopes cannot crash or turn examples into actions."""
import pytest

import src.agent_loop as loop
from src.tool_schemas import function_call_to_tool_block


@pytest.mark.parametrize('call', [None, 42, {'name': []}, {'name': 'unknown', 'arguments': {}}])
def test_invalid_native_envelope_does_not_execute_text_fallback(call):
    blocks, native, converted = loop._resolve_tool_blocks(
        'Example only:\n```bash\necho example\n```', [call], 1, is_api_model=False)
    assert blocks == []
    assert converted == []


@pytest.mark.parametrize('tool,args', [
    ('write_file', {'path': 'src/a.py'}),
    ('write_file', {'path': 'src/a.py', 'content': []}),
    ('write_file', {'path': 7, 'content': 'x'}),
    ('edit_file', {'path': 'src/a.py', 'old_string': 'old'}),
    ('bash', {'command': ['echo', 'example']}),
    ('read_file', {'path': 'src/a.py', 'limit': True}),
])
def test_invalid_code_tool_arguments_are_rejected_before_dispatch(tool, args):
    assert function_call_to_tool_block(tool, args) is None


def test_valid_native_calls_stay_aligned_when_an_invalid_call_is_between_them():
    first = {'id': 'a', 'name': 'read_file', 'arguments': '{"path":"src/a.py"}'}
    last = {'id': 'b', 'name': 'bash', 'arguments': '{"command":"python -m pytest -q"}'}
    blocks, native, converted = loop._resolve_tool_blocks('', [first, None, last], 1)
    assert [b.tool_type for b in blocks] == ['read_file', 'bash']
    assert converted == [first, last]
    assert native


def test_empty_file_and_empty_replacement_are_valid_explicit_values():
    assert function_call_to_tool_block('write_file', {'path': 'src/a.py', 'content': ''}).content == 'src/a.py\n'
    assert function_call_to_tool_block('edit_file', {'path': 'src/a.py', 'old_string': 'old', 'new_string': ''})


@pytest.mark.parametrize('tool', ['ls', 'get_workspace'])
@pytest.mark.parametrize('args', ['[]', 'false', '0', 'null', '"bad"', [], False, 0])
def test_optional_code_args_cannot_coerce_non_object_into_default_read(tool, args):
    assert function_call_to_tool_block(tool, args) is None


@pytest.mark.parametrize('envelope', [{}, 42, False, 'malformed'])
def test_malformed_top_level_native_container_never_falls_back_to_examples(envelope):
    assert loop._resolve_tool_blocks('```bash\necho example\n```', envelope, 1)[0] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('gate', ['disabled', 'policy'])
async def test_dispatcher_denial_precedes_bound_execution_and_restores_context(tmp_path, gate):
    from types import SimpleNamespace
    from src.agent_tools import ToolBlock
    import src.tool_execution as execution
    called = []
    async def forbidden():
        called.append(True)
        raise AssertionError('denied tool must not execute')
    previous = execution._active_workspace.get()
    _, result = await execution.execute_tool_block(ToolBlock('bash','echo example'),
        workspace=str(tmp_path), trusted_execution=SimpleNamespace(execute=forbidden),
        disabled_tools={'bash'} if gate=='disabled' else None,
        tool_policy=SimpleNamespace(blocks=lambda name: name=='bash') if gate=='policy' else None)
    assert result['exit_code'] == 1
    assert called == []
    assert execution._active_workspace.get() == previous
