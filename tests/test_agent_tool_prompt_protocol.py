"""The advertised tool protocol must match the channel actually sent to a provider."""
import pytest
import src.agent_loop as loop


def test_compact_fenced_prompt_exposes_executable_argument_syntax(monkeypatch):
    monkeypatch.setattr(loop, 'get_builtin_overrides', lambda: {})
    prompt = loop._assemble_prompt({'bash', 'read_file'}, compact=True, native_tools=False)
    assert 'fenced code block' in prompt
    assert '```bash' in prompt
    assert '```read_file' in prompt
    assert 'Only the tool schemas provided by the API' not in prompt
    assert 'Prefer native' not in prompt
    assert 'web_search' not in prompt


def test_native_prompt_still_uses_api_schema_channel(monkeypatch):
    monkeypatch.setattr(loop, 'get_builtin_overrides', lambda: {})
    prompt = loop._assemble_prompt({'bash'}, compact=True, native_tools=True)
    assert 'Only the tool schemas provided by the API' in prompt
    assert '```bash' not in prompt


def test_compact_usage_preserves_parseable_multiline_fence():
    hint = loop._compact_tool_line('read_file', 'Read a file.\n```read_file\nsrc/probe.py\n```')
    blocks, native, _ = loop._resolve_tool_blocks(hint, [], 1, is_api_model=False)
    assert len(blocks) == 1
    assert blocks[0].tool_type == 'read_file'
    assert 'src/probe.py' in blocks[0].content
    assert not native


def test_compact_usage_keeps_complete_multiline_arguments():
    hint = loop._compact_tool_line('bash', 'Shell.\n```bash\nfirst\n  second\n\n```\nMore examples')
    assert '```bash\nfirst\n  second\n\n```' in hint
    assert 'More examples' not in hint


@pytest.mark.parametrize('name', ['bash', 'python', 'read_file', 'write_file', 'edit_file', 'apply_patch', 'get_workspace'])
def test_shipped_compact_example_is_recognized_without_parser_expansion(monkeypatch, name):
    monkeypatch.setattr(loop, 'get_builtin_overrides', lambda: {})
    prompt = loop._assemble_prompt({name}, compact=True, native_tools=False)
    blocks, native, _ = loop._resolve_tool_blocks(prompt, [], 1, is_api_model=False)
    assert len(blocks) == 1
    assert blocks[0].tool_type == name
    if name == 'get_workspace':
        assert blocks[0].content == '{}'
    assert not native


def test_compact_code_navigation_uses_existing_schemas_and_respects_selection(monkeypatch):
    monkeypatch.setattr(loop, 'get_builtin_overrides', lambda: {})
    prompt = loop._assemble_prompt({'grep', 'glob', 'ls'}, {'glob'}, compact=True, native_tools=False)
    blocks, _, _ = loop._resolve_tool_blocks(prompt, [], 1, is_api_model=False)
    assert {b.tool_type for b in blocks} == {'grep', 'ls'}
    assert '"pattern"' in prompt
    assert '```glob' not in prompt
    assert '```bash' not in prompt


def test_compact_native_code_navigation_still_uses_api_channel(monkeypatch):
    monkeypatch.setattr(loop, 'get_builtin_overrides', lambda: {})
    prompt = loop._assemble_prompt({'grep', 'ls'}, compact=True, native_tools=True)
    assert '- `grep`' in prompt
    assert '- `ls`' in prompt
    assert '```grep' not in prompt
    assert '```ls' not in prompt


def test_protocol_is_part_of_system_prompt_cache_identity(monkeypatch):
    seen = []
    def build(*a, **kw):
        seen.append(kw['native_tools'])
        return ('NATIVE' if kw['native_tools'] else 'FENCED', '')
    monkeypatch.setattr(loop, '_build_base_prompt', build)
    monkeypatch.setattr(loop, '_cached_base_prompt', None)
    monkeypatch.setattr(loop, '_cached_base_prompt_key', None)
    monkeypatch.setattr(loop, 'get_setting', lambda key, default=None: default)
    for native, expected in [(True, 'NATIVE'), (False, 'FENCED'), (True, 'NATIVE')]:
        messages, _ = loop._build_system_prompt(
            [{'role': 'user', 'content': 'Execute a test'}], 'm', None, None,
            relevant_tools={'bash'}, compact=True, native_tools=native,
            suppress_local_context=True, suppress_skills=True)
        assert any(expected in str(m['content']) for m in messages)
        assert not any(('FENCED' if native else 'NATIVE') in str(m['content']) for m in messages)
    assert seen == [True, False, True]


def test_governed_protocol_survives_reduction_after_long_preset(monkeypatch):
    from src.context_compactor import trim_for_context
    monkeypatch.setattr(loop, 'get_builtin_overrides', lambda: {})
    monkeypatch.setattr(loop, 'get_setting', lambda key, default=None: default)
    request = {'role': 'user', 'content': 'Execute python -m pytest -q tests/test_probe.py'}
    messages, _ = loop._build_system_prompt(
        [{'role': 'system', 'content': 'Preset guidance. ' * 800}, request],
        'm', None, None, relevant_tools={'bash'}, compact=True,
        native_tools=False, protect_tool_protocol=True,
        suppress_local_context=True, suppress_skills=True)
    authority = {'role': 'system', 'content': 'Reviewed authority. ' * 4000, '_protected': True}
    messages.insert(-1, authority)
    protocol = next(m for m in messages if m.get('_governed_tool_protocol'))
    assert loop.estimate_tokens(messages) > 30000 - 2048
    reduced = trim_for_context(messages, 30000, 2048)
    assert protocol in reduced
    assert 'fenced code block' in protocol['content']
    assert '```bash' in protocol['content']
    assert authority in reduced


def test_ordinary_prompt_does_not_gain_governed_protection(monkeypatch):
    monkeypatch.setattr(loop, 'get_builtin_overrides', lambda: {})
    monkeypatch.setattr(loop, 'get_setting', lambda key, default=None: default)
    messages, _ = loop._build_system_prompt(
        [{'role': 'user', 'content': 'Hello'}], 'm', None, None,
        relevant_tools={'bash'}, compact=True, native_tools=False,
        suppress_local_context=True, suppress_skills=True)
    assert not any(m.get('_governed_tool_protocol') for m in messages)


def test_governed_action_instruction_keeps_shell_and_workspace_tools_distinct():
    class Execution:
        allowed_commands = (('python', '-m', 'pytest'),)

    class Context:
        execution = Execution()

    message = loop._governed_action_message(Context())
    assert message['_protected'] is True
    assert 'already been bound and verified' in message['content']
    assert 'tool name' in message['content']
    assert '`python -m pytest`' in message['content']
    assert 'get_workspace' not in message['content']
    assert 'Do not restart or narrate the boot sequence' in message['content']
