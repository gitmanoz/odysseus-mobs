"""Real HTTP/persistence regressions for read-only session reconstruction."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from core.database import MobsExecution, MobsAuthorityReview, MobsPromotion, Session
from tests.test_mobs_chat_identity import chat, event, propose
from tests.test_mobs_mandate_builder import projects
from src.mobs_presentation import complete_textless_action


def state(chat):
    response = chat.client.get('/api/chat/institutional_state/s')
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    return response.json()


def facts(chat):
    with chat.factory() as db:
        return [(type(row).__name__, {c.name: getattr(row, c.name) for c in row.__table__.columns})
                for model in (MobsExecution, MobsAuthorityReview, MobsPromotion)
                for row in db.query(model).all()]


def test_reopening_recovers_exact_pending_proposal_without_decision(chat):
    proposal = propose(chat)
    before = facts(chat)
    first = state(chat)
    second = state(chat)
    assert first == second
    assert first['proposal']['proposal_digest'] == proposal['proposal_digest']
    assert first['actions'] == ['review', 'cancel']
    assert first['reviewed'] is False and not first['active']
    assert facts(chat) == before
    assert not chat.model_calls


def test_fresh_backend_process_reads_persisted_pending_without_resuming(chat):
    proposal = propose(chat)
    before = facts(chat)
    with chat.factory() as db:
        url = str(db.bind.url)
    environment = {**os.environ, 'DATABASE_URL': url, 'PYTHONDONTWRITEBYTECODE': '1'}
    script = (
        "import json; from src.mobs_presentation import session_presentation; "
        "print(json.dumps(session_presentation('s', None)))"
    )
    result = subprocess.run([sys.executable, '-B', '-c', script],
                            cwd=Path(__file__).resolve().parents[1], env=environment,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    recovered = json.loads(result.stdout.strip().splitlines()[-1])
    assert recovered['proposal']['proposal_digest'] == proposal['proposal_digest']
    assert recovered['proposal']['status'] == 'pending'
    assert recovered['active'] is False and recovered['reviewed'] is False
    assert 'approve' not in recovered['actions']
    assert facts(chat) == before and not chat.model_calls


def test_textless_review_is_separate_from_approval_and_recovered(chat):
    proposal = propose(chat)
    event(chat.post('review', proposal, message=''), 'mobs_authority_reviewed')
    before = facts(chat)
    view = state(chat)
    assert view['reviewed'] and view['actions'] == ['approve', 'cancel']
    assert view['proposal']['status'] == 'pending'
    assert facts(chat) == before and not chat.model_calls


def test_textless_cancel_requires_exact_reference_and_cannot_repeat(chat):
    proposal = propose(chat)
    response = chat.post('cancel', proposal, message='', mobs_proposal_digest='wrong')
    assert response.status_code == 400
    event(chat.post('cancel', proposal, message=''), 'mobs_mandate_cancelled')
    assert chat.post('cancel', proposal, message='').status_code == 400
    assert state(chat)['actions'] == []


def test_approval_can_start_existing_loop_but_restart_does_not_resume(chat, monkeypatch):
    proposal = propose(chat)
    event(chat.post('review', proposal, message=''), 'mobs_authority_reviewed')
    response = chat.post('approve', proposal, message='')
    assert response.status_code == 200, response.text
    assert chat.model_calls
    # A persisted approved record alone is not evidence of a live run.
    with chat.factory() as db:
        row = db.get(MobsExecution, 's')
        row.status = 'approved'
        db.commit()
    monkeypatch.setattr('src.agent_runs.is_active', lambda sid: False)
    before, calls = facts(chat), len(chat.model_calls)
    view = state(chat)
    assert view['continuity'] == 'unconfirmed' and not view['active']
    assert view['actions'] == []
    assert facts(chat) == before and len(chat.model_calls) == calls


@pytest.mark.parametrize('change', ['source', 'target', 'identity'])
def test_drift_or_invalid_identity_blocks_without_path_disclosure_or_mutation(chat, change):
    propose(chat)
    if change == 'source':
        (chat.source / 'PROJECT_RULES.md').write_text('changed')
    elif change == 'target':
        (chat.target / 'hidden-unauthorized.txt').write_text('external')
    else:
        with chat.factory() as db:
            row = db.get(MobsExecution, 's')
            raw = json.loads(row.proposal_json)
            raw['proposal_digest'] = 'invalid'
            row.proposal_json = json.dumps(raw)
            db.commit()
    before = facts(chat)
    view = state(chat)
    assert view['validity'] == 'unavailable' and view['actions'] == []
    assert 'hidden-unauthorized' not in json.dumps(view)
    assert facts(chat) == before


def test_missing_binding_preserves_pending_but_cannot_review_or_approve(chat, monkeypatch):
    propose(chat)
    monkeypatch.setattr('src.mobs_presentation.human_reviewer', lambda request: (_ for _ in ()).throw(ValueError('missing')))
    before = facts(chat)
    view = state(chat)
    assert view['proposal'] and view['actions'] == ['cancel']
    assert not view['reviewed'] and facts(chat) == before


def test_run_starting_during_read_disables_decisions_without_mutating_records(chat, monkeypatch):
    propose(chat)
    samples = iter([False, True])
    monkeypatch.setattr('src.agent_runs.is_active', lambda sid: next(samples))
    before = facts(chat)
    view = state(chat)
    assert view['active'] and view['actions'] == [] and view['continuity'] == 'active'
    assert facts(chat) == before


def test_get_does_not_invoke_promotion_gate_or_transition_uncertain_record(chat, monkeypatch):
    propose(chat)
    with chat.factory() as db:
        db.add(MobsPromotion(id='interrupted', session_id='s', proposal_id='x', proposal_digest='x',
               artifact_digest='broken', status='promotion_applying', artifact_json='{}'))
        db.commit()
    def forbidden(*args, **kwargs):
        pytest.fail('GET must not call transition-capable promotion functions')
    monkeypatch.setattr('src.mobs_controlled_promotion.promotion_requires_human', forbidden)
    monkeypatch.setattr('src.mobs_controlled_promotion._record_outcome', forbidden)
    before = facts(chat)
    view = state(chat)
    assert view['promotions'][0]['actions'] == []
    assert facts(chat) == before


def test_read_route_enforces_real_session_ownership(chat, monkeypatch):
    from routes import chat_routes, session_routes
    monkeypatch.setattr(chat_routes, '_verify_session_owner', session_routes._verify_session_owner)
    monkeypatch.setattr(session_routes, 'SessionLocal', chat.factory)
    with chat.factory() as db:
        db.get(Session, 's').owner = 'founder'
        db.add(Session(id='other', owner='another', name='Private', model='fixture', endpoint_url='http://localhost/api/chat'))
        db.commit()
    assert chat.client.get('/api/chat/institutional_state/s').status_code == 200
    assert chat.client.get('/api/chat/institutional_state/other').status_code == 404
    assert chat.client.get('/api/chat/institutional_state/unknown').status_code == 404


def test_sealed_promotion_is_recovered_and_missing_store_is_not_created(chat, tmp_path, monkeypatch):
    from tests.test_mobs_controlled_promotion import _approved_development, _artifact
    from src.mobs_controlled_promotion import record_pending
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal)
    record_pending('s', artifact)
    before = facts(chat)
    view = state(chat)
    assert view['promotions'][0]['validity'] == 'valid'
    assert view['promotions'][0]['actions'] == ['promote']
    assert facts(chat) == before
    absent = tmp_path / 'missing-store'
    original_store = os.environ['MOBS_PROMOTION_STORE']
    monkeypatch.setenv('MOBS_PROMOTION_STORE', str(absent))
    view = state(chat)
    assert view['promotions'][0]['actions'] == []
    assert not absent.exists() and facts(chat) == before
    monkeypatch.setenv('MOBS_PROMOTION_STORE', original_store)
    applied = event(chat.post('promote', message='', mobs_promotion_id=artifact['id'],
                             mobs_promotion_digest=artifact['artifact_digest']), 'mobs_promotion_applied')
    assert applied['status'] == 'promotion_applied_verified'
    assert (chat.target / 'src/promoted.txt').read_bytes() == b'sealed\n'
    assert state(chat)['promotions'][0]['status'] == 'promotion_applied_verified'


def test_preautorizable_single_file_keeps_policy_gate_without_client_grant(chat, tmp_path, monkeypatch):
    from tests.mobs_reviewer_support import install_junior_operational_profile
    from tests.test_mobs_controlled_promotion import _approved_development, _artifact
    from src.mobs_controlled_promotion import record_pending
    install_junior_operational_profile(monkeypatch, tmp_path, self_development_preauthorized=True)
    monkeypatch.setenv('MOBS_SELF_DEVELOPMENT_ROOT', str(chat.target))
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py', content=b'pass\n# candidate\n')
    record_pending('s', artifact)
    before = facts(chat)
    view = state(chat)
    item = view['promotions'][0]
    assert item['status'] == 'promotion_preauthorized'
    assert item['actions'] == ['validate_promotion'] and item['validity'] == 'valid'
    assert facts(chat) == before


def test_multifile_receipt_is_exact_and_no_get_approves_or_applies(chat, tmp_path):
    from tests.test_mobs_multifile_promotion import _context, _sealed_two, _validate_receipt
    from src.mobs_controlled_promotion import record_pending
    proposal, _ = _context(chat)
    artifact = _sealed_two(chat, tmp_path, proposal)
    record_pending('s', artifact)
    assert state(chat)['promotions'][0]['actions'] == ['validate_promotion']
    _validate_receipt(chat, artifact)  # Software-test receipt fixture, no human decision.
    before = facts(chat)
    assert state(chat)['promotions'][0]['actions'] == ['validate_promotion', 'promote']
    assert facts(chat) == before
    with chat.factory() as db:
        row = db.get(MobsPromotion, artifact['id'])
        receipt = json.loads(row.outcome_json)
        receipt['validation']['artifact_digest'] = 'another-candidate'
        row.outcome_json = json.dumps(receipt)
        db.commit()
    before = facts(chat)
    assert state(chat)['promotions'][0]['actions'] == ['validate_promotion']
    assert facts(chat) == before


@pytest.mark.parametrize('action', ['propose', 'validate_promotion', 'other', 'approve'])
def test_empty_or_incomplete_requests_do_not_bypass_text_guard(chat, action):
    assert not complete_textless_action(action, {'session': 's'})
    response = chat.post(action, message='')
    assert response.status_code >= 400 or 'error' in response.text

def test_slow_institutional_observation_keeps_event_loop_responsive(chat, monkeypatch):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from src import mobs_presentation
    entered = threading.Event()
    release = threading.Event()
    def slow_observation(*args):
        entered.set()
        release.wait(3)
        return {'session_id': 's', 'active': False, 'actions': []}
    monkeypatch.setattr(mobs_presentation, 'session_presentation', slow_observation)
    @chat.client.app.get('/_test_event_loop_tick')
    async def tick():
        return {'tick': True}
    with chat.client, ThreadPoolExecutor(max_workers=2) as pool:
        query = pool.submit(chat.client.get, '/api/chat/institutional_state/s')
        assert entered.wait(2)
        started = time.monotonic()
        try:
            response = chat.client.get('/_test_event_loop_tick')
            elapsed = time.monotonic() - started
        finally:
            release.set()
        assert query.result(timeout=5).status_code == 200
    assert response.status_code == 200
    assert elapsed < 1, f'Observational query blocked the event loop for {elapsed:.2f}s'
