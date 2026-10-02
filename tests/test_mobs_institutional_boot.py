import copy
import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from src.mobs_institutional_boot import (
    InstitutionalBootError, authority_digest, capture_repository, institutional_boot,
)

CONTRACT = 'project/automation/future/AGENT_RUNTIME_INTEGRATION.md'
_TEST_TRUST = None


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True).stdout.decode().strip()


@pytest.fixture
def mandate(tmp_path, monkeypatch):
    root = tmp_path / 'institution'
    root.mkdir()
    git(root, 'init', '-b', 'dev')
    docs = {
        'PROJECT_INDEX.md': '# PROJECT INDEX\n[Agent Runtime Integration](project/automation/future/AGENT_RUNTIME_INTEGRATION.md)\n# Decision Tree\n```\n├─ Código\n│ → AI_CONTEXT.md\n│ → PROJECT_RULES.md\n└─ Branding\n│ → BRAND.md\n```\n',
        'AI_CONTEXT.md': '# Context\nInstitution governs; runtime executes.\n',
        'PROJECT_RULES.md': '# Rules\nReview before promotion.\n',
        CONTRACT: '# Integration\nFail closed on drift.\n',
    }
    for name, content in docs.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
    baseline = capture_repository(str(root))
    result = dict(source=baseline, target=copy.deepcopy(baseline), mandate='Inspect code',
                exclusions='No writes or publication', category='Código',
                authority_review='consistent',
                authorities={n: authority_digest(c) for n, c in docs.items()},
                objective='Inspect code', scope='Read the authorized repository only',
                allowed_paths=['**'],
                allowed_tools=['read_file', 'ls', 'grep', 'glob', 'get_workspace'],
                allowed_operations=['read'],
                approval_required_operations=[], approvals={},
                limits={'max_steps': 10, 'time_limit_seconds': 60, 'command_timeout_seconds': None},
                allowed_commands=[])
    from tests.mobs_reviewer_support import install_trust, attach_review
    import sys
    trust = install_trust(monkeypatch, tmp_path, root)
    monkeypatch.setattr(sys.modules[__name__], '_TEST_TRUST', trust)
    return attach_review(result, trust)


def boot(request):
    return institutional_boot(request, request['target']['path'])


def writable_mandate(mandate, tmp_path):
    target = tmp_path / 'executor'
    target.mkdir()
    git(target, 'init', '-b', 'dev')
    (target / 'allowed').mkdir()
    (target / 'allowed' / 'existing.txt').write_text('before\n', encoding='utf-8')
    git(target, 'add', '.')
    git(target, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
    mandate['target'] = capture_repository(str(target))
    mandate.update(
        objective='Create the authorized text artifact',
        scope='Only the declared target paths',
        exclusions='No deletion, publication, deployment, credentials, or Git operations',
        allowed_paths=['allowed/**'],
        allowed_tools=['write_file', 'edit_file', 'apply_patch', 'read_file'],
        allowed_operations=['read', 'write', 'create'],
        approval_required_operations=[], approvals={},
        limits={'max_steps': 8, 'time_limit_seconds': 60, 'command_timeout_seconds': None},
        allowed_commands=[],
    )
    return mandate


def test_success_reads_index_first_and_only_selected_sources(mandate, monkeypatch):
    import src.mobs_institutional_boot as module
    reads = []
    original = module._document
    def read(root, name):
        reads.append(name)
        return original(root, name)
    monkeypatch.setattr(module, '_document', read)
    ctx = boot(mandate)
    assert reads[0] == 'PROJECT_INDEX.md'
    assert set(ctx.documents) == set(mandate['authorities'])
    assert 'BRAND.md' not in reads
    assert ctx.message()['_protected'] is True
    assert mandate['source']['head'] in ctx.message()['content']
    ctx.verify()


@pytest.mark.parametrize('field', ['source', 'target', 'mandate', 'exclusions', 'category', 'authorities', 'authority_review'])
def test_missing_mandate_field_blocks(mandate, field):
    del mandate[field]
    with pytest.raises(InstitutionalBootError):
        institutional_boot(mandate, 'unused')


def test_authority_missing(mandate):
    (Path(mandate['source']['path']) / CONTRACT).unlink()
    # Explicitly authorize the changed tree; absent authority still fails.
    mandate['source'] = capture_repository(mandate['source']['path'])
    mandate['target'] = dict(mandate['source'])
    with pytest.raises(InstitutionalBootError, match='Missing or unreadable'):
        boot(mandate)


@pytest.mark.parametrize('content', ['', '\x00', '<<<<<<< ours\nconflict\n=======\nother\n>>>>>>> theirs'])
def test_invalid_authority(mandate, content):
    path = Path(mandate['source']['path']) / CONTRACT
    path.write_text(content, encoding='utf-8')
    mandate['source'] = capture_repository(mandate['source']['path'])
    mandate['target'] = dict(mandate['source'])
    mandate['authorities'][CONTRACT] = authority_digest(content)
    with pytest.raises(InstitutionalBootError, match='Invalid or conflicted'):
        boot(mandate)


@pytest.mark.parametrize('review', ['contradictory', 'ambiguous', None, True])
def test_unresolved_authority_review_blocks(mandate, review):
    mandate['authority_review'] = review
    with pytest.raises(InstitutionalBootError, match='review'):
        boot(mandate)


def test_reviewed_content_mismatch(mandate):
    mandate['authorities'][CONTRACT] = '0' * 64
    with pytest.raises(InstitutionalBootError, match='reviewed content'):
        boot(mandate)


def test_selected_route_cannot_omit_required_authority(mandate):
    del mandate['authorities']['PROJECT_RULES.md']
    with pytest.raises(InstitutionalBootError, match='omits required'):
        boot(mandate)


@pytest.mark.parametrize('field,value', [('branch', 'wrong'), ('head', '0' * 40), ('head', 'dev'), ('working_tree_sha256', '0' * 64)])
def test_baseline_mismatch(mandate, field, value):
    mandate['source'][field] = value
    with pytest.raises(InstitutionalBootError):
        boot(mandate)


def test_invalid_workspace(mandate, tmp_path):
    with pytest.raises(InstitutionalBootError, match='workspace'):
        institutional_boot(mandate, str(tmp_path))


def test_drift_during_execution(mandate):
    ctx = boot(mandate)
    (Path(ctx.source['path']) / 'PROJECT_RULES.md').write_text('# Changed', encoding='utf-8')
    with pytest.raises(InstitutionalBootError, match='drift'):
        ctx.verify()


def test_untracked_bytes_are_part_of_baseline(mandate):
    path = Path(mandate['source']['path']) / 'untracked.txt'
    path.write_text('first')
    mandate['source'] = capture_repository(str(path.parent))
    mandate['target'] = dict(mandate['source'])
    # The newly authorized baseline needs its own explicit human receipt.
    from tests.mobs_reviewer_support import attach_review
    attach_review(mandate, _TEST_TRUST)
    ctx = boot(mandate)
    path.write_text('second')
    with pytest.raises(InstitutionalBootError, match='drift'):
        ctx.verify()


def test_path_escape_rejected(mandate):
    mandate['authorities']['../secret.md'] = '0' * 64
    with pytest.raises(InstitutionalBootError, match='path'):
        boot(mandate)


def test_unsupported_category_fails_closed(mandate):
    mandate['category'] = 'Unknown'
    with pytest.raises(InstitutionalBootError, match='category'):
        boot(mandate)


def test_context_survives_real_compaction(mandate):
    from src.context_compactor import trim_for_context
    context = boot(mandate).message()
    messages = [context, {'role': 'user', 'content': 'x' * 30000}, {'role': 'user', 'content': 'Inspect'}]
    trimmed = trim_for_context(messages, 2000, reserve_tokens=200)
    assert any(m.get('content') == context['content'] for m in trimmed)


def collect(gen):
    import asyncio
    async def run():
        return [chunk async for chunk in gen]
    return asyncio.run(run())


def loop_setup(monkeypatch):
    import src.agent_loop as loop
    monkeypatch.setattr('src.tool_security.owner_is_admin_or_single_user', lambda owner: True)
    monkeypatch.setattr('src.tool_execution.owner_is_admin_or_single_user', lambda owner: True)
    monkeypatch.setattr(loop, 'get_setting', lambda key, default=None: default)
    monkeypatch.setattr(loop, 'get_mcp_manager', lambda: None)
    # Keep the real loop, reducers and dispatcher; only the external model is fake.
    return loop


def run_governed(loop, mandate, **kwargs):
    max_rounds = kwargs.pop('max_rounds', 1)
    kwargs.setdefault('owner', mandate['review_record']['reviewer'])
    return collect(loop.stream_agent_loop(
        'http://localhost:11434/api/chat', 'test-model',
        [{'role': 'user', 'content': 'Inspect the code and explain it'}],
        mobs_execution=mandate, workspace=mandate['target']['path'],
        max_rounds=max_rounds, context_length=100000, **kwargs,
    ))


def shell_mandate(mandate, tmp_path, commands, timeout=2):
    mandate = writable_mandate(mandate, tmp_path)
    mandate['limits']['command_timeout_seconds'] = 30
    mandate.update(
        exclusions='No shell composition, Git writes, installation, deployment, publication, or credentials',
        allowed_tools=['bash', 'write_file', 'edit_file', 'apply_patch', 'read_file'],
        allowed_operations=['read', 'write', 'create', 'test', 'lint', 'typecheck', 'build', 'git_read'],
        allowed_commands=commands,
        limits={'max_steps': 8, 'time_limit_seconds': 60, 'command_timeout_seconds': timeout},
    )
    return mandate


def contained_result(**fields):
    """A mocked dispatcher result must carry trusted boundary evidence."""
    return {"output": "", "exit_code": 0,
            "trusted_execution": {"adapter": "windows_appcontainer_job_v1", "effects": []},
            **fields}


def test_real_loop_sends_reviewed_context_and_preserves_single_done(mandate, monkeypatch):
    loop = loop_setup(monkeypatch)
    seen = []
    async def stream(candidates, messages, **kwargs):
        seen.extend(messages)
        yield 'data: {"delta":"Inspection complete."}\n\n'
        yield 'data: [DONE]\n\n'
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    chunks = run_governed(loop, mandate)
    assert any('MOBS INSTITUTIONAL CONTEXT' in str(m.get('content')) for m in seen)
    assert any('institutional_verified' in c for c in chunks)
    assert chunks.count('data: [DONE]\n\n') == 1
    assert all('_protected' not in m for m in seen)


def test_failed_boot_never_calls_model_or_tools(mandate, monkeypatch):
    loop = loop_setup(monkeypatch)
    mandate['authority_review'] = 'contradictory'
    def forbidden(*args, **kwargs):
        pytest.fail('execution ran after failed boot')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', forbidden)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('institutional_blocked' in c for c in chunks)


def test_non_mobs_delegates_without_boot(monkeypatch):
    loop = loop_setup(monkeypatch)
    def forbidden(*args, **kwargs):
        pytest.fail('ordinary task triggered institutional boot')
    monkeypatch.setattr('src.mobs_institutional_boot.institutional_boot', forbidden)
    seen = []
    async def stream(candidates, messages, **kwargs):
        seen.extend(messages)
        yield 'data: {"delta":"Hello."}\n\n'
        yield 'data: [DONE]\n\n'
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    chunks = collect(loop.stream_agent_loop('http://localhost/api/chat', 'm', [{'role':'user','content':'hello'}]))
    assert seen
    assert not any('MOBS INSTITUTIONAL CONTEXT' in str(m) for m in seen)
    assert not any('institutional_' in c for c in chunks)


def test_loop_blocks_drift_before_tool_dispatch(mandate, monkeypatch):
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        (Path(mandate['source']['path']) / 'PROJECT_RULES.md').write_text('# Changed', encoding='utf-8')
        yield 'data: ' + json.dumps({'delta': '```read_file\nPROJECT_RULES.md\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    def forbidden(*args, **kwargs):
        pytest.fail('tool ran after drift')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('institutional_blocked' in c for c in chunks)
    assert not any('institutional_verified' in c for c in chunks)


def test_lost_context_fails_before_model(mandate, monkeypatch):
    loop = loop_setup(monkeypatch)
    import src.context_compactor as compactor
    monkeypatch.setattr(compactor, 'trim_for_context', lambda messages, *a, **k: [m for m in messages if not m.get('_protected')])
    def forbidden(*args, **kwargs):
        pytest.fail('model ran without institutional context')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('Institutional context lost' in c for c in chunks)


def test_owner_denied_before_any_repository_read(mandate, monkeypatch):
    loop = loop_setup(monkeypatch)
    monkeypatch.setattr('src.tool_security.owner_is_admin_or_single_user', lambda owner: False)
    def forbidden(*args, **kwargs):
        pytest.fail('repository read before permission check')
    monkeypatch.setattr('src.mobs_institutional_boot.capture_repository', forbidden)
    assert any('not authorized' in c for c in run_governed(loop, mandate))


def test_repository_removed_after_boot_is_closed(mandate):
    ctx = boot(mandate)
    moved = Path(ctx.source['path']).with_name('moved')
    Path(ctx.source['path']).rename(moved)
    with pytest.raises(InstitutionalBootError):
        ctx.verify()


def test_staged_content_part_of_baseline(mandate):
    root = Path(mandate['source']['path'])
    file = root / 'AI_CONTEXT.md'
    original = file.read_bytes()
    file.write_text('# staged one')
    git(root, 'add', 'AI_CONTEXT.md')
    file.write_bytes(original)
    first = capture_repository(str(root))
    file.write_text('# staged two')
    git(root, 'add', 'AI_CONTEXT.md')
    file.write_bytes(original)
    second = capture_repository(str(root))
    assert first['working_tree_sha256'] != second['working_tree_sha256']


def test_existing_read_tool_is_reused(mandate, monkeypatch):
    loop = loop_setup(monkeypatch)
    calls = []
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```read_file\nPROJECT_RULES.md\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    async def execute(block, **kwargs):
        calls.append((block.tool_type, kwargs['workspace']))
        return ('read_file', {'output': 'Rules', 'exit_code': 0})
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', execute)
    chunks = run_governed(loop, mandate)
    assert calls == [('read_file', mandate['target']['path'])]
    assert any('institutional_verified' in c for c in chunks)


def test_context_capacity_fails_closed(mandate, monkeypatch):
    loop = loop_setup(monkeypatch)
    monkeypatch.setattr(loop, 'estimate_tokens', lambda *a, **k: 200000)
    def forbidden(*args, **kwargs):
        pytest.fail('model called with context above capacity')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('capacity' in c for c in chunks)


def test_runtime_cannot_write_in_boot_slice(mandate, monkeypatch):
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```bash\necho forbidden\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    def forbidden(*args, **kwargs):
        pytest.fail('mutating tool dispatched in boot slice')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('institutional_blocked' in c for c in chunks)


def test_branch_drift_during_execution(mandate):
    ctx = boot(mandate)
    git(Path(ctx.source['path']), 'switch', '-c', 'other')
    with pytest.raises(InstitutionalBootError, match='drift'):
        ctx.verify()


def test_separate_authority_and_execution_repositories(mandate, tmp_path):
    target = tmp_path / 'executor'
    target.mkdir()
    git(target, 'init', '-b', 'dev')
    (target / 'code.py').write_text('pass\n')
    git(target, 'add', '.')
    git(target, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
    mandate['target'] = capture_repository(str(target))
    ctx = boot(mandate)
    assert ctx.source['path'] != ctx.target['path']
    (target / 'code.py').write_text('changed\n')
    with pytest.raises(InstitutionalBootError, match='drift'):
        ctx.verify()


def test_explicit_null_mandate_is_not_a_non_mobs_fallback(monkeypatch):
    loop = loop_setup(monkeypatch)
    def forbidden(*args, **kwargs):
        pytest.fail('invalid explicit mandate fell back to ordinary execution')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', forbidden)
    chunks = collect(loop.stream_agent_loop('http://localhost/api/chat', 'm', [], mobs_execution=None))
    assert any('institutional_blocked' in c for c in chunks)


def test_authorized_write_uses_existing_dispatcher_and_records_provenance(mandate, tmp_path, monkeypatch):
    mandate = writable_mandate(mandate, tmp_path)
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```write_file\n{"path":"allowed/result.txt","content":"approved\\n"}\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    chunks = run_governed(loop, mandate)
    assert (Path(mandate['target']['path']) / 'allowed' / 'result.txt').read_text(encoding='utf-8') == 'approved\n'
    mutation = next(json.loads(chunk[6:]) for chunk in chunks if 'institutional_mutation' in chunk)
    assert mutation['data']['paths'] == ['allowed/result.txt']
    verified = next(json.loads(chunk[6:]) for chunk in chunks if 'institutional_verified' in chunk)
    assert verified['data']['mutations'][0]['paths'] == ['allowed/result.txt']
    assert verified['data']['final_target']['working_tree_sha256'] != mandate['target']['working_tree_sha256']


@pytest.mark.skipif(__import__('os').name != 'nt', reason='Windows Native adapter')
def test_real_agent_loop_private_write_reaches_sealed_artifact_without_target_write(mandate, tmp_path, monkeypatch):
    from tests.mobs_reviewer_support import install_junior_operational_profile
    from src.mobs_mandate_builder import _proposal_digest
    install_junior_operational_profile(monkeypatch, tmp_path)
    mandate = writable_mandate(mandate, tmp_path)
    mandate['limits']['command_timeout_seconds'] = 30
    mandate.update(promotion_eligible=True, proposal_id='promotion-loop-fixture',
                   authority_snapshot=mandate['review_record']['snapshot_id'], _promotion_session_id='fixture')
    mandate['project_profile'] = 'generic'
    from src.mobs_mandate_builder import CAPABILITY_PROFILE_VERSION
    mandate['capability_profile_version'] = CAPABILITY_PROFILE_VERSION
    mandate['capabilities'] = {'version': CAPABILITY_PROFILE_VERSION, 'project_profile': 'generic'}
    from src.mobs_controlled_promotion import operational_profile_identity
    mandate['operational_authority_profile'] = operational_profile_identity()
    mandate['proposal_digest'] = _proposal_digest(mandate)
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```write_file\n{"path":"allowed/existing.txt","content":"private only"}\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    recorded = []
    monkeypatch.setattr('src.mobs_controlled_promotion.record_pending', lambda session, artifact: recorded.append(artifact) or {'id': artifact['id'], 'status': 'human_approval_required'})
    chunks = run_governed(loop, mandate)
    assert recorded and recorded[0]['effect'] == 'write'
    assert (Path(mandate['target']['path']) / 'allowed' / 'existing.txt').read_text() == 'before\n'
    assert any('institutional_command' in chunk for chunk in chunks)


def test_write_outside_allowed_scope_is_blocked_before_dispatch(mandate, tmp_path, monkeypatch):
    mandate = writable_mandate(mandate, tmp_path)
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```write_file\n{"path":"outside.txt","content":"no"}\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    def forbidden(*args, **kwargs):
        pytest.fail('out-of-scope write reached the dispatcher')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('Path is outside mandate' in chunk for chunk in chunks)


def test_read_scope_and_create_scope_are_distinct(mandate, tmp_path):
    mandate = writable_mandate(mandate, tmp_path)
    mandate['allowed_read_paths'] = ['allowed/existing.txt']
    mandate['allowed_write_paths'] = ['allowed/existing.txt']
    mandate['allowed_create_paths'] = []
    mandate['allowed_tools'].append('grep')
    ctx = boot(mandate)
    assert ctx.authorize_tool('read_file', 'allowed/existing.txt') is None
    with pytest.raises(InstitutionalBootError, match='outside mandate'):
        ctx.authorize_tool('read_file', 'allowed/missing.txt')
    with pytest.raises(InstitutionalBootError, match='Read search root'):
        ctx.authorize_tool('grep', '{"pattern":"x","path":"allowed"}')
    with pytest.raises(InstitutionalBootError, match='outside mandate'):
        ctx.authorize_tool('write_file', 'allowed/new.txt\ncontent')
    assert ctx.authorize_tool('write_file', 'allowed/existing.txt\ncontent').operations == ('write',)
    mandate['allowed_read_paths'] = []
    blind = boot(mandate)
    with pytest.raises(InstitutionalBootError, match='outside mandate'):
        blind.authorize_tool('edit_file', '{"path":"allowed/existing.txt","old_string":"before","new_string":"after"}')


@pytest.mark.parametrize('path', ['allowed/NUL', 'allowed/CON.txt', 'allowed/file.txt:stream', 'allowed/file.'])
def test_windows_device_and_stream_paths_are_not_authorizable(mandate, tmp_path, path):
    mandate = writable_mandate(mandate, tmp_path)
    ctx = boot(mandate)
    with pytest.raises(InstitutionalBootError, match='Invalid'):
        ctx.authorize_tool('read_file', path)


def test_unapproved_tool_is_blocked_before_dispatch(mandate, tmp_path, monkeypatch):
    mandate = writable_mandate(mandate, tmp_path)
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```bash\necho forbidden\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    def forbidden(*args, **kwargs):
        pytest.fail('unapproved tool reached the dispatcher')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('Tool is outside mandate' in chunk for chunk in chunks)


def test_delete_requires_explicit_approval(mandate, tmp_path, monkeypatch):
    mandate = writable_mandate(mandate, tmp_path)
    mandate['allowed_operations'].append('delete')
    loop = loop_setup(monkeypatch)
    patch_text = '*** Begin Patch\n*** Delete File: allowed/existing.txt\n*** End Patch'
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': f'```apply_patch\n{patch_text}\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    def forbidden(*args, **kwargs):
        pytest.fail('unapproved delete reached the dispatcher')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('Explicit approval required for operation: delete' in chunk for chunk in chunks)


def test_explicitly_approved_delete_is_allowed(mandate, tmp_path, monkeypatch):
    mandate = writable_mandate(mandate, tmp_path)
    mandate['allowed_operations'].append('delete')
    mandate['approvals'] = {'delete': 'review-2026-09-28'}
    loop = loop_setup(monkeypatch)
    patch_text = '*** Begin Patch\n*** Delete File: allowed/existing.txt\n*** End Patch'
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': f'```apply_patch\n{patch_text}\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    chunks = run_governed(loop, mandate)
    assert not (Path(mandate['target']['path']) / 'allowed' / 'existing.txt').exists()
    assert any('institutional_mutation' in chunk for chunk in chunks)
    assert any('institutional_verified' in chunk for chunk in chunks)


def test_secret_like_path_requires_credentials_approval(mandate, tmp_path, monkeypatch):
    mandate = writable_mandate(mandate, tmp_path)
    mandate['allowed_paths'] = ['allowed/**', 'secrets/**']
    mandate['allowed_operations'].append('credentials')
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```write_file\n{"path":"secrets/app.txt","content":"blocked"}\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    def forbidden(*args, **kwargs):
        pytest.fail('credential write reached the dispatcher without approval')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('Explicit approval required for operation: credentials' in chunk for chunk in chunks)


def test_drift_during_mutation_is_detected_and_not_verified(mandate, tmp_path, monkeypatch):
    mandate = writable_mandate(mandate, tmp_path)
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```write_file\n{"path":"allowed/result.txt","content":"approved"}\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    async def mutate_and_drift(block, **kwargs):
        root = Path(kwargs['workspace'])
        (root / 'allowed' / 'result.txt').write_text('approved', encoding='utf-8')
        (root / 'intruder.txt').write_text('drift', encoding='utf-8')
        return ('write_file', {'output': 'written', 'exit_code': 0})
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', mutate_and_drift)
    chunks = run_governed(loop, mandate)
    assert any('Unexpected drift during mutation' in chunk for chunk in chunks)
    assert not any('institutional_verified' in chunk for chunk in chunks)


def test_authorized_shell_command_uses_existing_dispatcher_and_records_ledger(mandate, tmp_path, monkeypatch):
    mandate = shell_mandate(mandate, tmp_path, ['git status'])
    loop = loop_setup(monkeypatch)
    calls = []
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```bash\ngit status --short\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    async def execute(block, **kwargs):
        calls.append((block.tool_type, kwargs['workspace'], kwargs['shell_timeout']))
        return ('bash', contained_result())
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', execute)
    chunks = run_governed(loop, mandate)
    assert calls == [('bash', mandate['target']['path'], 2)]
    command = next(json.loads(chunk[6:]) for chunk in chunks if 'institutional_command' in chunk)
    assert command['data']['operation'] == 'git_read'
    assert command['data']['exit_code'] == 0
    assert any('institutional_verified' in chunk for chunk in chunks)


def test_shell_command_outside_mandate_is_blocked_before_dispatch(mandate, tmp_path, monkeypatch):
    mandate = shell_mandate(mandate, tmp_path, ['git status'])
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```bash\ngit log -1\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    def forbidden(*args, **kwargs):
        pytest.fail('unapproved shell command reached dispatcher')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('Shell command is outside mandate' in chunk for chunk in chunks)


def test_shell_cwd_escape_is_blocked_before_dispatch(mandate, tmp_path, monkeypatch):
    mandate = shell_mandate(mandate, tmp_path, ['git status'])
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```bash\ngit -C .. status\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    def forbidden(*args, **kwargs):
        pytest.fail('cwd escape reached dispatcher')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('Invalid shell command' in chunk for chunk in chunks)


def test_shell_windows_path_escape_is_blocked_before_dispatch(mandate, tmp_path, monkeypatch):
    mandate = shell_mandate(mandate, tmp_path, ['git status'])
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```bash\ngit -C C:\\outside status\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    def forbidden(*args, **kwargs):
        pytest.fail('Windows cwd escape reached dispatcher')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('Invalid shell command' in chunk for chunk in chunks)


def test_shell_timeout_is_propagated_to_existing_bash_tool(mandate, tmp_path, monkeypatch):
    mandate = shell_mandate(mandate, tmp_path, ['python -m pytest'], timeout=1)
    loop = loop_setup(monkeypatch)
    received = []
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```bash\npython -m pytest\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    async def execute(block, **kwargs):
        received.append(kwargs['shell_timeout'])
        return ('bash', contained_result(error='bash: timed out after 1s — process killed', exit_code=124))
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', execute)
    chunks = run_governed(loop, mandate)
    assert received == [1]
    command = next(json.loads(chunk[6:]) for chunk in chunks if 'institutional_command' in chunk)
    assert command['data']['exit_code'] == 124


def test_existing_bash_tool_enforces_context_timeout():
    from src.agent_tools.subprocess_tools import BashTool
    result = asyncio.run(BashTool().execute(
        'python -c "import time; time.sleep(2)"',
        {'shell_timeout': 0.1, 'subproc_env': None},
    ))
    assert result['exit_code'] == 124
    assert 'timed out after 0.1s' in result['error']


def test_git_mutation_is_blocked_before_dispatch(mandate, tmp_path, monkeypatch):
    mandate = shell_mandate(mandate, tmp_path, ['git status'])
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```bash\ngit reset --hard\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    def forbidden(*args, **kwargs):
        pytest.fail('mutating Git command reached dispatcher')
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', forbidden)
    chunks = run_governed(loop, mandate)
    assert any('Git command is not read-only' in chunk for chunk in chunks)


def test_failed_test_can_be_observed_and_retried_in_next_loop_round(mandate, tmp_path, monkeypatch):
    mandate = shell_mandate(mandate, tmp_path, ['python -m pytest'])
    loop = loop_setup(monkeypatch)
    model_calls = 0
    results = [
        contained_result(output='1 failed', exit_code=1),
        contained_result(output='1 passed', exit_code=0),
    ]
    async def stream(candidates, messages, **kwargs):
        nonlocal model_calls
        model_calls += 1
        yield 'data: ' + json.dumps({'delta': '```bash\npython -m pytest\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    async def execute(block, **kwargs):
        return ('bash', results.pop(0))
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', execute)
    chunks = run_governed(loop, mandate, max_rounds=2)
    assert model_calls == 2
    assert sum('institutional_command' in chunk for chunk in chunks) == 2
    assert any('institutional_verified' in chunk for chunk in chunks)


def test_external_drift_during_command_is_detected(mandate, tmp_path, monkeypatch):
    mandate = shell_mandate(mandate, tmp_path, ['git status'])
    loop = loop_setup(monkeypatch)
    async def stream(candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({'delta': '```bash\ngit status --short\n```'}) + '\n\n'
        yield 'data: [DONE]\n\n'
    async def drift(block, **kwargs):
        (Path(kwargs['workspace']) / 'intruder.txt').write_text('external drift', encoding='utf-8')
        return ('bash', contained_result())
    monkeypatch.setattr(loop, 'stream_llm_with_fallback', stream)
    monkeypatch.setattr(loop, 'execute_tool_block', drift)
    chunks = run_governed(loop, mandate)
    assert any('Target workspace drift during private command' in chunk for chunk in chunks)
    assert not any('institutional_verified' in chunk for chunk in chunks)


@pytest.mark.parametrize('tool,content', [
    ('edit_file', '{"path":"allowed/existing.txt","old_string":"old","new_string":"new"}'),
    ('apply_patch', '*** Begin Patch\n*** Update File: allowed/existing.txt\n@@\n-old\n+new\n*** End Patch'),
])
def test_promotion_eligible_execution_blocks_direct_write_tools(mandate, tmp_path, tool, content):
    mandate = writable_mandate(mandate, tmp_path)
    mandate['promotion_eligible'] = True
    mandate['_promotion_session_id'] = 'fixture'
    from src.mobs_mandate_builder import _proposal_digest
    mandate['proposal_digest'] = _proposal_digest(mandate)
    with pytest.raises(InstitutionalBootError, match='Direct writes'):
        boot(mandate).authorize_tool(tool, content)
