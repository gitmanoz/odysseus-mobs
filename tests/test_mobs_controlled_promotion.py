"""Focused integration coverage for the v0 sealed single-file promotion path."""
import json
import hashlib
from pathlib import Path

import pytest

from src.mobs_controlled_promotion import PromotionError, _self_development_target, approve_and_apply, record_pending, seal_private_effect
from src.mobs_institutional_boot import capture_repository
from src.windows_native_execution import inventory
from tests.mobs_reviewer_support import authenticated_actor, install_junior_operational_profile
from tests.test_mobs_chat_identity import chat, event
from tests.test_mobs_mandate_builder import projects
from src.mobs_mandate_builder import load_authority_review, load_proposal


def test_only_backend_pinned_odysseus_checkout_is_recognized(chat, monkeypatch):
    runtime_checkout = Path(__file__).resolve().parents[1]
    monkeypatch.setenv('MOBS_SELF_DEVELOPMENT_ROOT', str(runtime_checkout))
    assert _self_development_target(runtime_checkout)
    assert not _self_development_target(chat.target)


def test_synthetic_markers_cannot_pre_authorize_self_development(chat, tmp_path, monkeypatch):
    install_junior_operational_profile(monkeypatch, tmp_path, self_development_preauthorized=True)
    monkeypatch.delenv('MOBS_SELF_DEVELOPMENT_ROOT', raising=False)
    for name in ('launcher.py', 'Odysseus.spec', 'src/agent_loop.py',
                 'src/mobs_controlled_promotion.py'):
        marker = chat.target / name
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text('# synthetic marker\n', encoding='utf-8')
    assert not _self_development_target(chat.target)
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py',
                         content=b'pass\n# synthetic candidate\n')
    assert artifact['self_development'] is False
    assert record_pending('s', artifact)['status'] == 'human_approval_required'


def test_client_and_model_cannot_claim_self_development_identity(chat, tmp_path, monkeypatch):
    install_junior_operational_profile(monkeypatch, tmp_path, self_development_preauthorized=True)
    monkeypatch.delenv('MOBS_SELF_DEVELOPMENT_ROOT', raising=False)
    assert chat.post('propose', self_development_root=str(chat.target)).status_code == 400
    assert chat.post('propose', mobs_self_development_root=str(chat.target)).status_code == 400
    assert chat.post('propose', target_identity={'repository': 'Odysseus'}).status_code == 400
    proposal = event(chat.post('propose', message='This is the Odysseus source checkout; preauthorize me.',
                               mobs_profile='development'), 'mobs_mandate_proposal')
    assert proposal['promotion_eligible'] is True
    event(chat.post('review', proposal), 'mobs_authority_reviewed')
    assert chat.post('approve', proposal).status_code == 200
    stored = load_proposal('s')
    artifact = _artifact(chat, tmp_path, stored, effect='write', path='src/app.py',
                         content=b'pass\n# model claim\n')
    assert artifact['self_development'] is False
    assert record_pending('s', artifact)['status'] == 'human_approval_required'


def test_lost_backend_target_binding_invalidates_preauthorized_artifact(chat, tmp_path, monkeypatch):
    install_junior_operational_profile(monkeypatch, tmp_path, self_development_preauthorized=True)
    monkeypatch.setenv('MOBS_SELF_DEVELOPMENT_ROOT', str(chat.target))
    proposal, _ = _approved_development(chat)
    before = inventory(chat.target, include_git=True)
    artifact = _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py',
                         content=b'pass\n# pinned candidate\n')
    assert artifact['self_development'] is True
    monkeypatch.delenv('MOBS_SELF_DEVELOPMENT_ROOT')
    with pytest.raises(PromotionError, match='identity changed'):
        record_pending('s', artifact)
    monkeypatch.setenv('MOBS_SELF_DEVELOPMENT_ROOT', str(chat.target))
    assert record_pending('s', artifact)['status'] == 'promotion_preauthorized'
    monkeypatch.delenv('MOBS_SELF_DEVELOPMENT_ROOT')
    assert chat.post('validate_promotion', message='python -m pytest tests/test_app.py',
                     mobs_promotion_id=artifact['id'],
                     mobs_promotion_digest=artifact['artifact_digest']).status_code == 400
    assert inventory(chat.target, include_git=True) == before


def test_self_development_requires_exact_private_validation_before_human_promotion(chat, tmp_path, monkeypatch):
    """The route cannot turn Junior approval into an unvalidated self-change."""
    from core.database import MobsPromotion
    from src.windows_native_execution import WindowsExecutionPolicy
    monkeypatch.setattr('src.mobs_controlled_promotion._self_development_target', lambda target: True)
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    before = inventory(chat.target, include_git=True)
    artifact = _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py', content=b'pass\n# candidate\n')
    record_pending('s', artifact)
    store = Path(__import__('os').environ['MOBS_PROMOTION_STORE']) / artifact['id']
    assert hashlib.sha256((store / 'preimage.bin').read_bytes()).hexdigest() == artifact['preimage_sha256']
    assert inventory(chat.target, include_git=True) == before
    without_validation = chat.post('promote', mobs_promotion_id=artifact['id'],
                                   mobs_promotion_digest=artifact['artifact_digest'])
    assert without_validation.status_code == 400
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact['id']).status == 'promotion_blocked'

    # A fresh exact artifact is needed after any blocked attempt.
    artifact = _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py', content=b'pass\n# candidate\n')
    record_pending('s', artifact)
    injected = chat.post('validate_promotion', message='python -m pytest tests/test_app.py',
                         mobs_promotion_id=artifact['id'], mobs_promotion_digest=artifact['artifact_digest'],
                         content_sha256='0' * 64)
    assert injected.status_code == 400
    assert 'cannot replace trusted MOBS' in injected.text
    observed = []
    async def contained_validation(policy):
        observed.append(policy.validation_artifact['artifact_digest'])
        assert policy.promotion_binding is None
        assert (store.parent / artifact['id'] / 'content.bin').read_bytes() == b'pass\n# candidate\n'
        return {'exit_code': 0, 'output': '1 passed', 'trusted_execution': {
            'adapter': 'windows_appcontainer_job_v1', 'effects': [],
            'validated_artifact_digest': artifact['artifact_digest'],
            'target_before_sha256': artifact['target_inventory_sha256'],
            'target_after_sha256': artifact['target_inventory_sha256'], 'timed_out': False}}
    monkeypatch.setattr(WindowsExecutionPolicy, 'execute', contained_validation)
    response = chat.post('validate_promotion', message='python -m pytest tests/test_app.py',
                         mobs_promotion_id=artifact['id'], mobs_promotion_digest=artifact['artifact_digest'])
    receipt = event(response, 'mobs_promotion_validated')
    assert receipt['validation']['artifact_digest'] == artifact['artifact_digest']
    assert receipt['validation']['exit_code'] == 0
    assert observed == [artifact['artifact_digest']]
    assert inventory(chat.target, include_git=True) == before
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact['id']).status == 'human_approval_required'
    applied = event(chat.post('promote', mobs_promotion_id=artifact['id'],
                              mobs_promotion_digest=artifact['artifact_digest']), 'mobs_promotion_applied')
    assert applied['status'] == 'promotion_applied_verified'
    assert hashlib.sha256((chat.target / 'src/app.py').read_bytes()).hexdigest() == artifact['content_sha256']


def test_self_development_preauthorization_validates_then_promotes_without_human_gate(chat, tmp_path, monkeypatch):
    from core.database import MobsPromotion
    from src.windows_native_execution import WindowsExecutionPolicy

    monkeypatch.setattr('src.mobs_controlled_promotion._self_development_target', lambda target: True)
    install_junior_operational_profile(monkeypatch, tmp_path, self_development_preauthorized=True)
    proposal, _ = _approved_development(chat)
    baseline = inventory(chat.target, include_git=True)
    artifact = _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py',
                         content=b'pass\n# preauthorized candidate\n')
    pending = record_pending('s', artifact)
    assert pending['status'] == 'promotion_preauthorized'
    assert inventory(chat.target, include_git=True) == baseline

    # A model/client cannot skip the private validation or supply approval evidence.
    assert chat.post('promote', mobs_promotion_id=artifact['id'],
                     mobs_promotion_digest=artifact['artifact_digest']).status_code == 400
    assert chat.post('validate_promotion', message='python -m pytest tests/test_app.py',
                     mobs_promotion_id=artifact['id'], mobs_promotion_digest=artifact['artifact_digest'],
                     approval={'reviewer': 'founder'}).status_code == 400
    assert chat.post('validate_promotion', message='python -m pytest tests/test_app.py',
                     mobs_promotion_id=artifact['id'], mobs_promotion_digest=artifact['artifact_digest'],
                     self_development=True, operational_policy={'result': 'preauthorized'}).status_code == 400
    monkeypatch.setattr('src.mobs_reviewer_authorization.human_reviewer',
                        lambda request: (_ for _ in ()).throw(AssertionError('human gate was used')))

    async def validated(policy):
        return {'exit_code': 0, 'output': '1 passed', 'trusted_execution': {
            'adapter': 'windows_appcontainer_job_v1', 'effects': [],
            'validated_artifact_digest': artifact['artifact_digest'],
            'target_before_sha256': artifact['target_inventory_sha256'],
            'target_after_sha256': artifact['target_inventory_sha256'], 'timed_out': False}}
    monkeypatch.setattr(WindowsExecutionPolicy, 'execute', validated)
    response = chat.post('validate_promotion', message='python -m pytest tests/test_app.py',
                         mobs_promotion_id=artifact['id'], mobs_promotion_digest=artifact['artifact_digest'])
    applied = event(response, 'mobs_promotion_applied')
    assert applied['status'] == 'promotion_applied_verified'
    assert (chat.target / 'src/app.py').read_bytes() == b'pass\n# preauthorized candidate\n'
    with chat.factory() as db:
        row = db.get(MobsPromotion, artifact['id'])
        assert json.loads(row.approval_json)['type'] == 'operational_preauthorization'
        assert json.loads(row.outcome_json)['validation']['artifact_digest'] == artifact['artifact_digest']


def test_preauthorization_policy_change_invalidates_old_mandate(chat, tmp_path, monkeypatch):
    monkeypatch.setattr('src.mobs_controlled_promotion._self_development_target', lambda target: True)
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py', content=b'pass\n# old\n')
    record_pending('s', artifact)
    install_junior_operational_profile(monkeypatch, tmp_path, self_development_preauthorized=True)
    with pytest.raises(Exception, match='Operational Authority Profile changed'):
        load_proposal('s')
    blocked = chat.post('validate_promotion', message='python -m pytest tests/test_app.py',
                        mobs_promotion_id=artifact['id'], mobs_promotion_digest=artifact['artifact_digest'])
    assert blocked.status_code == 400
    assert (chat.target / 'src/app.py').read_bytes() != b'pass\n# old\n'


def test_preauthorized_self_development_failed_validation_never_promotes(chat, tmp_path, monkeypatch):
    from core.database import MobsPromotion
    from src.windows_native_execution import WindowsExecutionPolicy

    monkeypatch.setattr('src.mobs_controlled_promotion._self_development_target', lambda target: True)
    install_junior_operational_profile(monkeypatch, tmp_path, self_development_preauthorized=True)
    proposal, _ = _approved_development(chat)
    before = inventory(chat.target, include_git=True)
    artifact = _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py', content=b'pass\n# failed\n')
    record_pending('s', artifact)

    async def failed(policy):
        return {'exit_code': 1, 'output': 'test failed', 'trusted_execution': {}}
    monkeypatch.setattr(WindowsExecutionPolicy, 'execute', failed)
    response = chat.post('validate_promotion', message='python -m pytest tests/test_app.py',
                         mobs_promotion_id=artifact['id'], mobs_promotion_digest=artifact['artifact_digest'])
    assert response.status_code == 400
    assert inventory(chat.target, include_git=True) == before
    with chat.factory() as db:
        row = db.get(MobsPromotion, artifact['id'])
        assert row.status == 'promotion_preauthorized'
        assert row.approval_json is None
        assert json.loads(row.outcome_json)['validation_error'] == 'InstitutionalBootError'


def test_junior_non_self_development_still_requires_human_session(chat, tmp_path, monkeypatch):
    install_junior_operational_profile(monkeypatch, tmp_path, self_development_preauthorized=True)
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal)
    assert record_pending('s', artifact)['status'] == 'human_approval_required'
    chat.client.cookies.clear()
    response = chat.post('promote', mobs_promotion_id=artifact['id'],
                         mobs_promotion_digest=artifact['artifact_digest'])
    assert response.status_code == 400
    assert not (chat.target / 'src/promoted.txt').exists()


def test_windows_policy_overlays_exact_sealed_bytes_into_private_baseline(chat, tmp_path, monkeypatch):
    """Exercise adapter assembly while replacing only the native process launch."""
    import threading
    from src.windows_native_execution import WindowsExecutionPolicy
    monkeypatch.setattr('src.mobs_controlled_promotion._self_development_target', lambda target: True)
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    baseline = inventory(chat.target, include_git=True)
    artifact = _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py', content=b'pass\n# sealed\n')
    def stage(_executable, private, _include_pytest=False):
        toolchain = private / '.odysseus-toolchain'
        toolchain.mkdir()
        executable = toolchain / 'python.exe'
        executable.write_bytes(b'synthetic toolchain')
        return executable
    def observe(_executable, _arguments, private, _environment, _timeout, _stop, _write, _create):
        assert (private / 'src/app.py').read_bytes() == b'pass\n# sealed\n'
        assert inventory(chat.target, include_git=True) == baseline
        return {'stdout': '1 passed', 'stderr': '', 'exit_code': 0, 'timed_out': False,
                'profile_effects': [], 'native_configuration': {'synthetic_observer': True}}
    monkeypatch.setattr('src.windows_native_execution._stage_python_toolchain', stage)
    monkeypatch.setattr('src.windows_native_execution._run_appcontainer', observe)
    policy = WindowsExecutionPolicy(str(chat.target), ('python', '-m', 'pytest', 'tests/test_app.py'),
                                    ('src/**', 'tests/**'), ('src/**',), (), 30,
                                    validation_artifact=artifact)
    result = policy._execute_sync(threading.Event())
    assert result['exit_code'] == 0
    assert result['trusted_execution']['validated_artifact_digest'] == artifact['artifact_digest']
    assert inventory(chat.target, include_git=True) == baseline


def test_promotion_cannot_target_active_runtime_checkout(chat, tmp_path, monkeypatch):
    import src.runtime_paths
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    before = inventory(chat.target, include_git=True)
    monkeypatch.setattr(src.runtime_paths, 'get_app_root', lambda: str(chat.target))
    with pytest.raises(PromotionError, match='overlaps the active runtime'):
        _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py', content=b'candidate\n')
    assert inventory(chat.target, include_git=True) == before
    assert not list(Path(__import__('os').environ['MOBS_PROMOTION_STORE']).glob('*/artifact.json'))


def _digest(entries):
    import hashlib
    h = hashlib.sha256()
    for path, value in sorted(entries.items()):
        h.update(path.encode()); h.update(b"\0"); h.update(value.encode()); h.update(b"\0")
    return h.hexdigest()


def _approved_development(chat):
    p = event(chat.post("propose", mobs_profile="development"), "mobs_mandate_proposal")
    event(chat.post("review", p), "mobs_authority_reviewed")
    assert chat.post("approve", p).status_code == 200
    return load_proposal("s"), p


def _artifact(chat, tmp_path, proposal, *, effect="create", path="src/promoted.txt", content=b"sealed\n"):
    private = tmp_path / "private"; private.mkdir(parents=True, exist_ok=True)
    target = Path(proposal["target"]["path"])
    file = private / path; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(content)
    review = load_authority_review(proposal["authority_snapshot"], "founder")
    before = {} if effect == "create" else {path: (target / path).read_bytes() and __import__('hashlib').sha256((target / path).read_bytes()).hexdigest()}
    return seal_private_effect(private, {"effect": effect, "path": path}, binding={
        "proposal_id": proposal["proposal_id"], "proposal_digest": proposal["proposal_digest"],
        "authority_snapshot": proposal["authority_snapshot"], "source_baseline": proposal["source"],
        "target_baseline": proposal["target"], "review_authorization": review["authorization"],
        "private_before": before, "target_inventory_sha256": _digest(inventory(target, include_git=True)),
    })


def test_junior_artifact_requires_exact_human_approval_and_applies_create(chat, tmp_path, monkeypatch):
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal)
    pending = record_pending("s", artifact)
    assert pending["status"] == "human_approval_required"
    response = chat.post("promote", mobs_promotion_id=artifact["id"], mobs_promotion_digest=artifact["artifact_digest"])
    result = event(response, "mobs_promotion_applied")
    assert result["status"] == "promotion_applied_verified"
    assert (chat.target / "src" / "promoted.txt").read_text() == "sealed\n"


def test_tampered_reference_persists_blocked_state(chat, tmp_path, monkeypatch):
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal)
    record_pending("s", artifact)
    actor = authenticated_actor(chat.trust)
    with pytest.raises(PromotionError, match="Stale"):
        approve_and_apply("s", {"promotion_id": artifact["id"], "promotion_digest": "0" * 64}, actor)
    from core.database import MobsPromotion
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact['id']).status == 'promotion_blocked'


def test_target_drift_persists_blocked_state(chat, tmp_path, monkeypatch):
    from core.database import MobsPromotion
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal)
    record_pending("s", artifact)
    actor = authenticated_actor(chat.trust)
    (chat.target / "src" / "app.py").write_text("concurrent\n")
    with pytest.raises(PromotionError, match="drift"):
        approve_and_apply("s", {"promotion_id": artifact["id"], "promotion_digest": artifact["artifact_digest"]}, actor)
    assert not (chat.target / "src" / "promoted.txt").exists()
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact['id']).status == 'promotion_blocked'


def test_unprovisioned_or_non_junior_policy_fails_closed(chat, tmp_path, monkeypatch):
    for name in ('MOBS_OPERATIONAL_AUTHORITY_FILE', 'MOBS_OPERATIONAL_AUTHORITY_SHA256', 'MOBS_PROMOTION_STORE'):
        monkeypatch.delenv(name, raising=False)
    response = chat.post('propose', mobs_profile='development')
    assert response.status_code == 400
    assert 'Operational Authority Profile is unavailable' in response.text


def test_changed_operational_policy_blocks_pending_promotion(chat, tmp_path, monkeypatch):
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal)
    record_pending("s", artifact)
    policy_path = Path(monkeypatch.getenv("MOBS_OPERATIONAL_AUTHORITY_FILE")) if hasattr(monkeypatch, 'getenv') else Path(__import__('os').environ['MOBS_OPERATIONAL_AUTHORITY_FILE'])
    policy = json.loads(policy_path.read_text()); policy['version'] = 2
    raw = (json.dumps(policy, sort_keys=True) + "\n").encode(); policy_path.write_bytes(raw)
    monkeypatch.setenv("MOBS_OPERATIONAL_AUTHORITY_SHA256", __import__('hashlib').sha256(raw).hexdigest())
    with pytest.raises(PromotionError, match="Operational Authority Profile changed"):
        approve_and_apply("s", {"promotion_id": artifact["id"], "promotion_digest": artifact["artifact_digest"]}, authenticated_actor(chat.trust))
    from core.database import MobsPromotion
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact['id']).status == 'promotion_blocked'


def test_create_failure_after_applying_state_leaves_no_partial_destination(chat, tmp_path, monkeypatch):
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal)
    record_pending("s", artifact)
    monkeypatch.setattr('src.mobs_controlled_promotion.os.link', lambda *_: (_ for _ in ()).throw(OSError('publish failed')))
    with pytest.raises(OSError, match='publish failed'):
        approve_and_apply("s", {"promotion_id": artifact["id"], "promotion_digest": artifact["artifact_digest"]}, authenticated_actor(chat.trust))
    assert not (chat.target / 'src' / 'promoted.txt').exists()
    from core.database import MobsPromotion
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact['id']).status == 'promotion_interrupted_or_uncertain'


def test_staging_fsync_failure_is_persisted_as_uncertain_after_applying(chat, tmp_path, monkeypatch):
    """The target-local staging file exists only after the durable applying state."""
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal)
    record_pending("s", artifact)
    monkeypatch.setattr(
        'src.mobs_controlled_promotion.os.fsync',
        lambda *_: (_ for _ in ()).throw(OSError('staging fsync failed')),
    )
    with pytest.raises(OSError, match='staging fsync failed'):
        approve_and_apply("s", {"promotion_id": artifact["id"], "promotion_digest": artifact["artifact_digest"]}, authenticated_actor(chat.trust))
    assert not (chat.target / 'src' / 'promoted.txt').exists()
    from core.database import MobsPromotion
    with chat.factory() as db:
        row = db.get(MobsPromotion, artifact['id'])
        assert row.status == 'promotion_interrupted_or_uncertain'
        assert json.loads(row.outcome_json)['reason'] == 'application_exception'


def test_store_inside_target_is_rejected_before_artifact_or_target_mutation(chat, tmp_path, monkeypatch):
    """A configured artifact store can never become a hidden target mutation."""
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    before = inventory(chat.target, include_git=True)
    invalid_store = chat.target / 'promotion-store'
    monkeypatch.setenv('MOBS_PROMOTION_STORE', str(invalid_store))
    with pytest.raises(PromotionError, match='cannot reside in the target'):
        _artifact(chat, tmp_path, proposal)
    assert inventory(chat.target, include_git=True) == before
    assert not invalid_store.exists()


def test_concurrent_post_apply_drift_is_never_verified(chat, tmp_path, monkeypatch):
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal, _ = _approved_development(chat)
    artifact = _artifact(chat, tmp_path, proposal, effect='write', path='src/app.py', content=b'promoted\n')
    record_pending('s', artifact)
    original = __import__('os').replace
    def replace_then_drift(source, destination):
        original(source, destination)
        Path(destination).write_text('concurrent\n')
    monkeypatch.setattr('src.mobs_controlled_promotion.os.replace', replace_then_drift)
    with pytest.raises(PromotionError, match='uncertain'):
        approve_and_apply('s', {'promotion_id': artifact['id'], 'promotion_digest': artifact['artifact_digest']}, authenticated_actor(chat.trust))
    from core.database import MobsPromotion
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact['id']).status == 'promotion_interrupted_or_uncertain'
