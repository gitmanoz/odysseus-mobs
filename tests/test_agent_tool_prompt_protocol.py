"""The advertised tool protocol must match the channel actually sent to a provider."""
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
