"""Bounded sealed previews, including authenticated HTTP non-mutation coverage."""
import hashlib
import json
from pathlib import Path

import pytest

from src.mobs_presentation import _sealed_text_preview, PREVIEW_FILE_BYTES


@pytest.fixture
def sealed(tmp_path, monkeypatch):
    store, target = tmp_path / 'store', tmp_path / 'target'
    target.mkdir()
    directory = store / ('a' * 32)
    directory.mkdir(parents=True)
    monkeypatch.setenv('MOBS_PROMOTION_STORE', str(store))
    monkeypatch.delenv('MOBS_SELF_DEVELOPMENT_ROOT', raising=False)
    values = {'content-0.bin': b'new\n', 'preimage-0.bin': b'old\n', 'content-1.bin': b'<script>not executed</script>\n'}
    for name, content in values.items():
        (directory / name).write_bytes(content)
    digest = lambda name: hashlib.sha256(values[name]).hexdigest()
    artifact = {'id': 'a' * 32, 'format_version': 2, 'self_development': False, 'effects': [
        {'path': 'src/app.py', 'effect': 'write', 'content_sha256': digest('content-0.bin'), 'preimage_sha256': digest('preimage-0.bin')},
        {'path': 'tests/test_app.py', 'effect': 'create', 'content_sha256': digest('content-1.bin')}]}
    return artifact, target, directory


def test_preview_returns_exact_before_after_and_diff_without_writes(sealed):
    artifact, target, directory = sealed
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    files = _sealed_text_preview(artifact, target)
    assert files[0]['before'] == 'old\n' and files[0]['after'] == 'new\n'
    assert '-old' in files[0]['diff'] and '+new' in files[0]['diff']
    assert files[1]['before'] == '' and files[1]['after'] == '<script>not executed</script>\n'
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before
    assert list(target.iterdir()) == []


@pytest.mark.parametrize('filename', ['content-0.bin', 'preimage-0.bin', 'content-1.bin'])
def test_altered_sealed_bytes_never_return_a_preview(sealed, filename):
    artifact, target, directory = sealed
    (directory / filename).write_bytes(b'private data that must not be returned')
    with pytest.raises(ValueError):
        _sealed_text_preview(artifact, target)


@pytest.mark.parametrize('content', [b'\xff', b'zero\x00byte', b'x' * (PREVIEW_FILE_BYTES + 1), b'x\n' * 2001],
                         ids=['invalid-utf8', 'binary', 'oversized', 'excessive-lines'])
def test_binary_oversize_and_excessive_lines_are_not_partially_disclosed(sealed, content):
    artifact, target, directory = sealed
    (directory / 'content-1.bin').write_bytes(content)
    artifact['effects'][1]['content_sha256'] = hashlib.sha256(content).hexdigest()
    with pytest.raises((ValueError, UnicodeError)):
        _sealed_text_preview(artifact, target)


def test_missing_store_is_not_created(sealed, monkeypatch, tmp_path):
    artifact, target, _ = sealed
    missing = tmp_path / 'missing'
    monkeypatch.setenv('MOBS_PROMOTION_STORE', str(missing))
    with pytest.raises(ValueError):
        _sealed_text_preview(artifact, target)
    assert not missing.exists()


# The real route, persistence and authorization checks; no model output or TEB
# execution is used to prepare the sealed test candidate.
from tests.test_mobs_chat_identity import chat
from tests.test_mobs_mandate_builder import projects


def test_authenticated_preview_is_exact_observational_and_session_bound(chat, tmp_path, monkeypatch):
    from tests.test_mobs_multifile_promotion import _context, _sealed_two
    from tests.test_mobs_presentation import facts
    from src.mobs_controlled_promotion import record_pending
    from core.database import Session, MobsExecution
    from routes import chat_routes, session_routes
    proposal, _ = _context(chat)
    artifact = _sealed_two(chat, tmp_path, proposal)
    record_pending('s', artifact)
    assert len(_sealed_text_preview(artifact, chat.target)) == 2
    # This HTTP test examines a persisted, completed mandate with a pending
    # artifact. The shared model stub emits no tool and is correctly blocked by
    # the fail-closed runtime guard. Seed the presentation state explicitly in
    # the isolated DB; this is not evidence of real execution or promotion.
    with chat.factory() as db:
        db.get(MobsExecution, 's').status = 'completed'
        db.commit()
    before = facts(chat)
    calls_before = list(chat.model_calls)
    url = '/api/chat/institutional_state/s'
    reference = {'promotion_id': artifact['id'], 'promotion_digest': artifact['artifact_digest']}
    response = chat.client.get(url, params=reference)
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    data = response.json()
    assert data['validity'] == 'valid', data
    assert data['promotions'][0]['validity'] == 'valid', json.dumps({
        'reviewed': data['reviewed'], 'reviewer_available': data['reviewer_available'],
        'status': data['proposal']['status'], 'promotion': data['promotions'][0]})
    assert data['preview']['validity'] == 'valid', data
    assert data['preview']['artifact_digest'] == artifact['artifact_digest']
    assert len(data['preview']['files']) == 2
    assert facts(chat) == before and chat.model_calls == calls_before
    # A run starting while bytes are read invalidates the response; never
    # return an apparently current comparison alongside a new active run.
    with monkeypatch.context() as scoped:
        samples = iter([False, True])
        scoped.setattr('src.agent_runs.is_active', lambda sid: next(samples))
        raced = chat.client.get(url, params=reference).json()
    assert raced['active'] is True and raced['preview'] == {'validity': 'unavailable'}
    stale = chat.client.get(url, params={**reference, 'promotion_digest': '0' * 64}).json()
    assert stale['preview'] == {'validity': 'unavailable'}
    assert chat.client.get(url, params={'promotion_id': '../secret', 'promotion_digest': '0' * 64}).status_code == 400
    source = chat.target / 'src/app.py'
    original = source.read_bytes()
    source.write_bytes(b'external drift\n')
    assert chat.client.get(url, params=reference).json()['preview'] == {'validity': 'unavailable'}
    source.write_bytes(original)
    monkeypatch.setattr(chat_routes, '_verify_session_owner', session_routes._verify_session_owner)
    monkeypatch.setattr(session_routes, 'SessionLocal', chat.factory)
    with chat.factory() as db:
        db.get(Session, 's').owner = 'another'
        db.commit()
    assert chat.client.get(url, params=reference).status_code == 404
    assert facts(chat) == before and chat.model_calls == calls_before
    chat.client.cookies.clear()
    assert chat.client.get(url, params=reference).status_code == 401
