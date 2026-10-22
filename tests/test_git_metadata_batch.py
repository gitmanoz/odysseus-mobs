"""Batch path discovery preserves the exact metadata fingerprint and checks."""
import subprocess

import pytest
import src.mobs_institutional_boot as boot


@pytest.mark.parametrize('linked', [False, True])
def test_batched_paths_match_previous_fingerprint_in_normal_and_linked_worktrees(tmp_path, monkeypatch, linked):
    root = tmp_path / 'repo'; root.mkdir()
    def git(*args):
        subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
    git('init', '-b', 'test')
    (root / 'a').write_text('content')
    git('add', 'a'); git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture')
    if linked:
        target = tmp_path / 'linked'
        git('worktree','add','--detach',str(target))
    else:
        target = root
    original = boot._git; calls = []
    def counted(path,*args):
        calls.append(args); return original(path,*args)
    monkeypatch.setattr(boot, '_git', counted)
    batched = boot._git_metadata(target)
    assert len(calls) == 1
    def prior(path,*args):
        return b'\n'.join(original(path,'rev-parse','--path-format=absolute',*tail).strip() for tail in (
            ('--git-path','index'),('--git-common-dir',),('--git-path','HEAD'),('--git-path','config.worktree'))) + b'\n'
    monkeypatch.setattr(boot, '_git', prior)
    assert boot._git_metadata(target) == batched
    # A real metadata mutation still changes the fingerprint.
    config = root / '.git/config'
    config.write_bytes(config.read_bytes() + b'\n# changed\n')
    assert boot._git_metadata(target) != batched


@pytest.mark.parametrize('output', [b'', b'one\ntwo\nthree\n', b'one\n\nthree\nfour\n', b'a\nb\nc\nd\ne\n'])
def test_incomplete_or_ambiguous_path_batch_fails_closed(monkeypatch, tmp_path, output):
    monkeypatch.setattr(boot, '_git', lambda *a: output)
    with pytest.raises(boot.InstitutionalBootError, match='incomplete or ambiguous'):
        boot._git_metadata(tmp_path)
