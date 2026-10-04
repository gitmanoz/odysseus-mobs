"""Governed Git identity reads use reviewed metadata, never agent Git argv."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from src.mobs_institutional_boot import (
    InstitutionalBootError, _baseline_inventory, capture_repository, institutional_boot,
)
from src.mobs_mandate_builder import CAPABILITY_PROFILE_VERSION, derive_capabilities
from src.windows_native_execution import MAX_FILE_BYTES, TrustedExecutionUnavailable, inventory
from tests.test_mobs_institutional_boot import mandate, shell_mandate, git


def test_capture_preserves_index_and_uses_observational_git(mandate, monkeypatch):
    import src.mobs_institutional_boot as boot

    root = Path(mandate['source']['path'])
    index = root / '.git' / 'index'
    before = (index.read_bytes(), index.stat().st_mtime_ns)
    original = boot.subprocess.run
    invocations = []

    def observed(argv, **kwargs):
        invocations.append((argv, kwargs['env']))
        return original(argv, **kwargs)

    monkeypatch.setenv('GIT_CONFIG_COUNT', '1')
    monkeypatch.setenv('GIT_ALTERNATE_OBJECT_DIRECTORIES', str(root / 'outside'))
    monkeypatch.setattr(boot.subprocess, 'run', observed)
    assert capture_repository(str(root)) == mandate['source']
    assert (index.read_bytes(), index.stat().st_mtime_ns) == before
    assert invocations
    for argv, env in invocations:
        assert '--no-optional-locks' in argv and '--no-pager' in argv
        assert env['GIT_OPTIONAL_LOCKS'] == '0'
        assert env['GIT_TERMINAL_PROMPT'] == '0'
        assert env['GIT_NO_LAZY_FETCH'] == '1'
        assert env['GIT_CONFIG_GLOBAL'] == boot.os.devnull
        assert 'GIT_CONFIG_COUNT' not in env
        assert 'GIT_ALTERNATE_OBJECT_DIRECTORIES' not in env
    assert any('--no-ext-diff' in argv and '--no-textconv' in argv for argv, _ in invocations)


def test_capture_inventory_includes_ignored_content_and_excludes_git_metadata(mandate):
    root = Path(mandate['target']['path'])
    (root / '.gitignore').write_text('ignored.txt\n', encoding='utf-8')
    git(root, 'add', '.gitignore')
    git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'ignore fixture')
    ignored = root / 'ignored.txt'
    ignored.write_text('one\n', encoding='utf-8')
    first = capture_repository(str(root))
    assert 'working_tree_status' not in first
    assert '.git/index' not in inventory(root, include_git=False)
    ignored.write_text('two\n', encoding='utf-8')
    second = capture_repository(str(root))
    assert first['working_tree_inventory_sha256'] != second['working_tree_inventory_sha256']
    assert first['working_tree_sha256'] != second['working_tree_sha256']


def test_inventory_excludes_git_metadata_at_every_depth_and_preserves_include_git(tmp_path):
    directory_root = tmp_path / 'directory-root'
    (directory_root / '.git').mkdir(parents=True)
    (directory_root / '.git' / 'config').write_text('metadata\n', encoding='utf-8')
    nested_directory = directory_root / 'vendor' / 'fixture' / '.git'
    nested_directory.mkdir(parents=True)
    (nested_directory / 'HEAD').write_text('nested metadata\n', encoding='utf-8')
    (directory_root / 'project.txt').write_text('project\n', encoding='utf-8')

    linked_root = tmp_path / 'linked-root'
    linked_root.mkdir()
    (linked_root / '.git').write_text('gitdir: elsewhere\n', encoding='utf-8')
    nested_file = linked_root / 'nested' / '.git'
    nested_file.parent.mkdir()
    nested_file.write_text('gitdir: elsewhere\n', encoding='utf-8')
    (linked_root / 'project.txt').write_text('project\n', encoding='utf-8')

    assert inventory(directory_root, include_git=False) == {
        'project.txt': inventory(directory_root, include_git=True)['project.txt'],
    }
    assert inventory(linked_root, include_git=False) == {
        'project.txt': inventory(linked_root, include_git=True)['project.txt'],
    }
    included_directory = inventory(directory_root, include_git=True)
    included_linked = inventory(linked_root, include_git=True)
    assert '.git/config' in included_directory
    assert 'vendor/fixture/.git/HEAD' in included_directory
    assert '.git' in included_linked
    assert 'nested/.git' in included_linked


def _ignored_large_file(root: Path) -> Path:
    (root / '.gitignore').write_text('ignored-large.bin\ncreated.bin\n', encoding='utf-8')
    git(root, 'add', '.gitignore')
    git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
        'commit', '-m', 'large ignored fixture')
    large = root / 'ignored-large.bin'
    with large.open('wb') as stream:
        stream.truncate(MAX_FILE_BYTES + 3 * 64 * 1024)
    return large


def test_baseline_inventory_bounds_large_ignored_without_weakening_teb(mandate):
    root = Path(mandate['target']['path'])
    _ignored_large_file(root)
    first = capture_repository(str(root))
    second = capture_repository(str(root))
    assert first == second
    with pytest.raises(TrustedExecutionUnavailable, match='exceeds inventory limit'):
        inventory(root, include_git=False)


@pytest.mark.parametrize('change', ['size', 'metadata', 'sample', 'create_remove'])
def test_large_ignored_baseline_detects_operational_drift(mandate, change):
    root = Path(mandate['target']['path'])
    large = _ignored_large_file(root)
    baseline = capture_repository(str(root))
    if change == 'size':
        with large.open('r+b') as stream:
            stream.truncate(large.stat().st_size + 1)
    elif change == 'metadata':
        stamp = large.stat().st_mtime_ns + 2_000_000_000
        os.utime(large, ns=(stamp, stamp))
    elif change == 'sample':
        with large.open('r+b') as stream:
            stream.seek(0)
            stream.write(b'changed sampled content')
    else:
        created = root / 'created.bin'
        created.write_bytes(b'ignored creation\n')
        assert capture_repository(str(root)) != baseline
        created.unlink()
        large.unlink()
    assert capture_repository(str(root)) != baseline


def test_baseline_inventory_excludes_git_metadata_at_any_depth(mandate):
    root = Path(mandate['target']['path'])
    nested = root / 'vendor' / 'fixture' / '.git'
    nested.mkdir(parents=True)
    (nested / 'config').write_text('metadata\n', encoding='utf-8')
    entries = _baseline_inventory(root)
    assert '.git' not in entries
    assert '.git/config' not in entries
    assert 'vendor/fixture/.git/config' not in entries


@pytest.mark.parametrize('recipe,field', [
    ('git_branch_current', 'branch'), ('git_head_current', 'head'),
])
def test_identity_recipe_returns_exact_approved_baseline(mandate, tmp_path, recipe, field):
    request = shell_mandate(mandate, tmp_path, [recipe], timeout=20)
    context = institutional_boot(request, request['target']['path'])
    pending = context.authorize_tool('bash', recipe)
    result = asyncio.run(pending.boundary_policy.execute())
    assert result['output'] == request['target'][field]
    assert result['command_capability'] == {
        'recipe': recipe, 'permitted': True, 'executable_available': True,
        'boundary_executable': True,
    }
    event = context.complete_command(pending, result)
    assert event['value'] == request['target'][field]
    assert event['boundary']['baseline'] == request['target']
    assert event['changed_paths'] == []


def test_drift_between_authorization_and_identity_read_is_blocked(mandate, tmp_path):
    request = shell_mandate(mandate, tmp_path, ['git_head_current'], timeout=20)
    context = institutional_boot(request, request['target']['path'])
    pending = context.authorize_tool('bash', 'git_head_current')
    (Path(request['target']['path']) / 'allowed' / 'existing.txt').write_text('external drift\n')
    result = asyncio.run(pending.boundary_policy.execute())
    assert result['exit_code'] == 1
    with pytest.raises(InstitutionalBootError, match='execution boundary'):
        context.complete_command(pending, result)
    assert context.mutation_ledger[-1]['status'] == 'blocked'


def test_drift_during_identity_read_is_blocked(mandate, tmp_path, monkeypatch):
    import src.mobs_institutional_boot as boot

    request = shell_mandate(mandate, tmp_path, ['git_branch_current'], timeout=20)
    context = institutional_boot(request, request['target']['path'])
    pending = context.authorize_tool('bash', 'git_branch_current')
    original = boot.capture_repository

    def concurrent_change(path):
        result = original(path)
        (Path(path) / 'allowed' / 'existing.txt').write_text('concurrent\n')
        return result

    monkeypatch.setattr(boot, 'capture_repository', concurrent_change)
    result = asyncio.run(pending.boundary_policy.execute())
    assert result['exit_code'] == 1
    assert 'drift' in result['error'].lower()


@pytest.mark.parametrize('command', [
    'git status', 'git rev-parse HEAD', 'git_branch_current --help',
    'git_head_current HEAD', 'git_head_current --output=elsewhere',
    'git_status_current --short', 'git_status_current src/app.py',
])
def test_model_cannot_supply_git_executable_or_arguments(mandate, tmp_path, command):
    request = shell_mandate(mandate, tmp_path, [
        'git_branch_current', 'git_head_current', 'git_status_current',
    ])
    context = institutional_boot(request, request['target']['path'])
    with pytest.raises(InstitutionalBootError):
        context.authorize_tool('bash', command)


def test_old_profile_is_not_accepted(mandate, tmp_path):
    request = shell_mandate(mandate, tmp_path, ['git_branch_current'])
    request['capability_profile_version'] = '5'
    request['project_profile'] = 'generic'
    request['capabilities'] = {'version': '5', 'project_profile': 'generic'}
    request['proposal_id'] = 'obsolete'
    with pytest.raises(InstitutionalBootError):
        institutional_boot(request, request['target']['path'])


def test_git_read_recipes_are_python_profile_only(tmp_path):
    project = tmp_path / 'profiles'
    (project / 'src').mkdir(parents=True)
    (project / 'project.godot').write_text('[application]\n', encoding='utf-8')
    common = ['pytest', 'python -m pytest']
    assert CAPABILITY_PROFILE_VERSION == '6'
    assert derive_capabilities(project, 'generic')['allowed_commands'] == common
    assert derive_capabilities(project, 'godot')['allowed_commands'] == common
    assert derive_capabilities(project, 'python')['allowed_commands'] == [
        *common, 'git_branch_current', 'git_head_current', 'git_status_current',
        'python -m py_compile', 'ruff check --no-fix',
    ]


def _status_request(mandate, tmp_path):
    request = shell_mandate(mandate, tmp_path, ['git_status_current'], timeout=20)
    return request, Path(request['target']['path'])


def test_status_returns_only_authorized_git_states(mandate, tmp_path):
    request, root = _status_request(mandate, tmp_path)
    (root / '.gitignore').write_text('allowed/ignored.txt\nelsewhere-ignored.txt\n', encoding='utf-8')
    git(root, 'add', '.gitignore')
    git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'ignore fixture')
    (root / 'allowed' / 'existing.txt').write_text('modified\n', encoding='utf-8')
    (root / 'allowed' / 'untracked.txt').write_text('untracked\n', encoding='utf-8')
    (root / 'allowed' / 'ignored.txt').write_text('ignored\n', encoding='utf-8')
    (root / 'elsewhere-ignored.txt').write_text('hidden\n', encoding='utf-8')
    request['target'] = capture_repository(str(root))
    context = institutional_boot(request, str(root))
    pending = context.authorize_tool('bash', 'git_status_current')
    result = asyncio.run(pending.boundary_policy.execute())
    assert result['exit_code'] == 0
    payload = json.loads(result['output'])
    assert payload == {'entries': [
        {'path': 'allowed/existing.txt', 'status': ' M'},
        {'path': 'allowed/ignored.txt', 'status': '!!'},
        {'path': 'allowed/untracked.txt', 'status': '??'},
    ]}
    assert 'elsewhere-ignored.txt' not in result['output']
    event = context.complete_command(pending, result)
    assert event['value'] == payload


@pytest.mark.parametrize('relative,content', [
    ('allowed/existing.txt', 'tracked drift\n'),
    ('allowed/untracked.txt', 'untracked drift\n'),
    ('allowed/ignored.txt', 'ignored drift\n'),
])
def test_status_blocks_tracked_untracked_and_ignored_drift(mandate, tmp_path, relative, content):
    request, root = _status_request(mandate, tmp_path)
    if relative.endswith('ignored.txt'):
        (root / '.gitignore').write_text('allowed/ignored.txt\n', encoding='utf-8')
        git(root, 'add', '.gitignore')
        git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'ignore fixture')
        request['target'] = capture_repository(str(root))
    context = institutional_boot(request, str(root))
    pending = context.authorize_tool('bash', 'git_status_current')
    path = root / relative
    path.write_text(content, encoding='utf-8')
    result = asyncio.run(pending.boundary_policy.execute())
    assert result['exit_code'] == 1
    assert 'drift' in result['error'].lower()


def test_unauthorized_ignored_drift_blocks_without_path_leakage(mandate, tmp_path):
    request, root = _status_request(mandate, tmp_path)
    (root / '.gitignore').write_text('private/hidden.txt\n', encoding='utf-8')
    git(root, 'add', '.gitignore')
    git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'ignore private fixture')
    request['target'] = capture_repository(str(root))
    context = institutional_boot(request, str(root))
    pending = context.authorize_tool('bash', 'git_status_current')
    hidden = 'private/hidden.txt'
    target = root / hidden
    target.parent.mkdir()
    target.write_text('outside approved read scope\n', encoding='utf-8')

    result = asyncio.run(pending.boundary_policy.execute())
    assert result['exit_code'] == 1
    assert 'drift' in result['error'].lower()
    assert 'output' not in result and 'trusted_execution' not in result
    assert hidden not in json.dumps(result, sort_keys=True)
    with pytest.raises(InstitutionalBootError, match='execution boundary'):
        context.complete_command(pending, result)
    ledger = context.mutation_ledger[-1]
    assert ledger['status'] == 'blocked'
    assert hidden not in json.dumps(ledger, sort_keys=True)


@pytest.mark.parametrize('alternate_file', ['alternates', 'http-alternates'])
def test_object_alternates_are_rejected_before_governed_baseline(
        mandate, tmp_path, monkeypatch, alternate_file):
    import src.mobs_institutional_boot as boot

    root = Path(mandate['target']['path'])
    outside = tmp_path / 'external-object-store'
    outside.mkdir()
    git(outside, 'init', '-b', 'dev')
    alternates = root / '.git' / 'objects' / 'info' / alternate_file
    alternates.write_text(str(outside / '.git' / 'objects') + '\n', encoding='utf-8')
    original = boot._git

    def no_object_reads(path, *args):
        if args[:2] in {('rev-parse', 'HEAD'), ('ls-files', '--stage')} or args[0] in {'status', 'diff'}:
            pytest.fail('Object-consuming Git command ran before alternates rejection')
        return original(path, *args)

    monkeypatch.setattr(boot, '_git', no_object_reads)
    with pytest.raises(InstitutionalBootError, match='alternates are unsupported'):
        capture_repository(str(root))


def test_alternates_appearing_during_capture_do_not_produce_baseline(mandate, tmp_path, monkeypatch):
    import src.mobs_institutional_boot as boot

    root = Path(mandate['target']['path'])
    outside = tmp_path / 'external-objects'
    outside.mkdir()
    alternates = root / '.git' / 'objects' / 'info' / 'alternates'
    original = boot._git

    def concurrent_alternate(path, *args):
        result = original(path, *args)
        if args == ('ls-files', '--others', '--exclude-standard', '-z'):
            alternates.write_text(str(outside) + '\n', encoding='utf-8')
        return result

    monkeypatch.setattr(boot, '_git', concurrent_alternate)
    with pytest.raises(InstitutionalBootError, match='alternates are unsupported'):
        capture_repository(str(root))


def test_missing_git_and_unsupported_configuration_fail_closed(mandate, tmp_path, monkeypatch):
    import src.mobs_institutional_boot as boot

    request = shell_mandate(mandate, tmp_path, ['git_head_current'], timeout=20)
    context = institutional_boot(request, request['target']['path'])
    pending = context.authorize_tool('bash', 'git_head_current')
    with monkeypatch.context() as patch:
        patch.setattr(boot.shutil, 'which', lambda _: None)
        result = asyncio.run(pending.boundary_policy.execute())
        assert result['exit_code'] == 1
        assert result['command_capability']['executable_available'] is False

    root = Path(request['target']['path'])
    git(root, 'config', 'filter.unsafe.clean', 'echo unsafe')
    with pytest.raises(InstitutionalBootError, match='configuration is unsupported'):
        capture_repository(str(root))


def test_inconsistent_git_identity_is_blocked(mandate, monkeypatch):
    import src.mobs_institutional_boot as boot

    original = boot._git
    head_reads = 0

    def inconsistent(root, *args):
        nonlocal head_reads
        if args == ('rev-parse', 'HEAD'):
            head_reads += 1
            if head_reads == 2:
                return b'0' * 40 + b'\n'
        return original(root, *args)

    monkeypatch.setattr(boot, '_git', inconsistent)
    with pytest.raises(InstitutionalBootError, match='changed during capture'):
        capture_repository(mandate['target']['path'])
