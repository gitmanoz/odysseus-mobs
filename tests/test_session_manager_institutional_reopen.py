"""Real persistence regressions: empty chats can own presentable MOBS records."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.session_manager as manager_module
from core.database import Base, Session, MobsExecution, MobsPromotion
from core.session_manager import SessionManager


@pytest.mark.parametrize('status', ['pending', 'approved'])
def test_empty_governed_session_reopens_without_mutation_or_execution(tmp_path, monkeypatch, status):
    engine = create_engine('sqlite:///' + (tmp_path / 'sessions.sqlite').as_posix())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(manager_module, 'SessionLocal', factory)
    with factory() as db:
        for sid, owner, archived in [('pending', 'alice', False), ('other', 'bob', False),
                                      ('empty', 'alice', False), ('archived', 'alice', True)]:
            db.add(Session(id=sid, name=sid, model='fixture', endpoint_url='http://localhost/v1',
                           owner=owner, archived=archived, message_count=0))
        db.flush()
        for sid in ('pending', 'other', 'archived'):
            db.add(MobsExecution(session_id=sid, target_path='/synthetic', status=status,
                                 proposal_json='{}', ledger_json='[]'))
        db.commit()
    manager = SessionManager.__new__(SessionManager)
    manager.sessions = {}
    manager.load_sessions()
    assert set(manager.sessions) == {'pending', 'other'}
    assert set(manager.get_sessions_for_user('alice')) == {'pending'}
    assert manager.sessions['pending'].message_count == 0
    assert not manager.sessions['pending'].history
    with factory() as db:
        assert [(r.status, r.proposal_json, r.ledger_json) for r in db.query(MobsExecution).all()] == [(status, '{}', '[]')] * 3
        assert all(r.message_count == 0 for r in db.query(Session).all())
    engine.dispose()


@pytest.mark.parametrize('status', ['human_approval_required', 'promotion_preauthorized',
    'promotion_applying', 'promotion_interrupted_or_uncertain'])
def test_empty_session_with_unresolved_promotion_is_discoverable(tmp_path, monkeypatch, status):
    engine = create_engine('sqlite:///' + (tmp_path / 'sessions.sqlite').as_posix())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(manager_module, 'SessionLocal', factory)
    with factory() as db:
        db.add(Session(id='promotion', name='promotion', model='fixture', endpoint_url='http://localhost/v1', owner='alice', message_count=0))
        db.flush()
        db.add(MobsPromotion(id='artifact', session_id='promotion', proposal_id='p', proposal_digest='pd',
                            artifact_digest='ad', status=status, artifact_json='{}'))
        db.commit()
    manager = SessionManager.__new__(SessionManager)
    manager.sessions = {}
    manager.load_sessions()
    assert set(manager.get_sessions_for_user('alice')) == {'promotion'}
    with factory() as db:
        row = db.query(MobsPromotion).one()
        assert (row.status, row.artifact_json, row.approval_json, row.outcome_json) == (status, '{}', None, None)
    engine.dispose()
