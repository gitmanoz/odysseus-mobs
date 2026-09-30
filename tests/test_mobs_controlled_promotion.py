"""Focused integration coverage for the v0 sealed single-file promotion path."""
import json
from pathlib import Path

import pytest

from src.mobs_controlled_promotion import PromotionError, approve_and_apply, record_pending, seal_private_effect
from src.mobs_institutional_boot import capture_repository
from src.windows_native_execution import inventory
from tests.mobs_reviewer_support import authenticated_actor, install_junior_operational_profile
from tests.test_mobs_chat_identity import chat, event
from tests.test_mobs_mandate_builder import projects
from src.mobs_mandate_builder import load_authority_review, load_proposal


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
    private = tmp_path / "private"; private.mkdir(parents=True)
    target = Path(proposal["target"]["path"])
    file = private / path; file.parent.mkdir(parents=True); file.write_bytes(content)
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
