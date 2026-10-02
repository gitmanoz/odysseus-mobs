"""Governed Git identity reads use reviewed metadata, never agent Git argv."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.mobs_institutional_boot import InstitutionalBootError, capture_repository, institutional_boot
from src.mobs_mandate_builder import CAPABILITY_PROFILE_VERSION, derive_capabilities
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
])
def test_model_cannot_supply_git_executable_or_arguments(mandate, tmp_path, command):
    request = shell_mandate(mandate, tmp_path, ['git_branch_current', 'git_head_current'])
    context = institutional_boot(request, request['target']['path'])
    with pytest.raises(InstitutionalBootError):
        context.authorize_tool('bash', command)


def test_old_profile_is_not_accepted(mandate, tmp_path):
    request = shell_mandate(mandate, tmp_path, ['git_branch_current'])
    request['capability_profile_version'] = '4'
    request['project_profile'] = 'generic'
    request['capabilities'] = {'version': '4', 'project_profile': 'generic'}
    request['proposal_id'] = 'obsolete'
    with pytest.raises(InstitutionalBootError):
        institutional_boot(request, request['target']['path'])


def test_git_identity_recipes_are_python_profile_only(tmp_path):
    project = tmp_path / 'profiles'
    (project / 'src').mkdir(parents=True)
    (project / 'project.godot').write_text('[application]\n', encoding='utf-8')
    common = ['pytest', 'python -m pytest']
    assert CAPABILITY_PROFILE_VERSION == '5'
    assert derive_capabilities(project, 'generic')['allowed_commands'] == common
    assert derive_capabilities(project, 'godot')['allowed_commands'] == common
    assert derive_capabilities(project, 'python')['allowed_commands'] == [
        *common, 'git_branch_current', 'git_head_current',
        'python -m py_compile', 'ruff check --no-fix',
    ]


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
