"""Two-file private patch and sealed promotion regression coverage."""
import asyncio
import hashlib
import json
import os
import shutil
import threading
from pathlib import Path

import pytest

from core.database import MobsPromotion
from src.mobs_controlled_promotion import (
    PromotionError, approve_and_apply, promotion_requires_human, record_pending,
    seal_private_effects, validate_private_artifact,
)
from src.mobs_institutional_boot import InstitutionalBootError, capture_repository, institutional_boot
from src.mobs_mandate_builder import (
    CAPABILITY_PROFILE_VERSION, MandateProposalError, load_authority_review,
    load_proposal, validate_proposal_identity,
)
from src.windows_native_execution import TrustedExecutionUnavailable, inventory
from src.windows_native_execution import WindowsExecutionPolicy
from tests.mobs_reviewer_support import authenticated_actor, install_junior_operational_profile
from tests.test_mobs_chat_identity import chat, event
from tests.test_mobs_controlled_promotion import _approved_development, _artifact, _digest
from tests.test_mobs_mandate_builder import projects


def _patch(second="write"):
    tail = ("*** Update File: tests/test_app.py\n@@\n-pass\n+assert True\n" if second == "write"
            else "*** Add File: tests/new_test.py\n+assert True\n")
    return "*** Begin Patch\n*** Update File: src/app.py\n@@\n-pass\n+print('ok')\n" + tail + "*** End Patch"


def _context(chat):
    proposal, _ = _approved_development(chat)
    review = load_authority_review(proposal["authority_snapshot"], "founder")
    candidate = {**proposal, "authority_review": "consistent", "review_record": review,
                 "_promotion_session_id": "s"}
    return proposal, institutional_boot(candidate, str(chat.target))


def _sealed_two(chat, tmp_path, proposal, *, second="write", target=None):
    target = target or chat.target
    private = tmp_path / "multi-private"
    private.mkdir(exist_ok=True)
    (private / "src").mkdir(exist_ok=True)
    (private / "tests").mkdir(exist_ok=True)
    (private / "src/app.py").write_text("print('ok')\n")
    second_path = "tests/test_app.py" if second == "write" else "tests/new_test.py"
    (private / second_path).write_text("assert True\n")
    review = load_authority_review(proposal["authority_snapshot"], "founder")
    before = {"src/app.py": hashlib.sha256((target / "src/app.py").read_bytes()).hexdigest()}
    if second == "write":
        before[second_path] = hashlib.sha256((target / second_path).read_bytes()).hexdigest()
    artifact = seal_private_effects(private, [
        {"effect": "write", "path": "src/app.py"},
        {"effect": second, "path": second_path} if second == "write" else
        {"effect": "create", "path": second_path},
    ], binding={"proposal_id": proposal["proposal_id"], "proposal_digest": proposal["proposal_digest"],
                "authority_snapshot": proposal["authority_snapshot"], "source_baseline": proposal["source"],
                "target_baseline": capture_repository(str(target)), "review_authorization": review["authorization"],
                "private_before": before,
                "target_inventory_sha256": _digest(inventory(target, include_git=True))})
    return artifact


def _validate_receipt(chat, artifact):
    with chat.factory() as db:
        row = db.get(MobsPromotion, artifact["id"])
        row.outcome_json = json.dumps({"validation": {
            "artifact_digest": artifact["artifact_digest"],
            "proposal_digest": artifact["proposal_digest"],
            "authority_snapshot": artifact["authority_snapshot"],
            "target_baseline": artifact["target_baseline"],
            "target_inventory_sha256": artifact["target_inventory_sha256"],
            "exit_code": 0, "boundary": {
                "validated_artifact_digest": artifact["artifact_digest"],
                "target_before_sha256": artifact["target_inventory_sha256"],
                "target_after_sha256": artifact["target_inventory_sha256"]}}})
        db.commit()


@pytest.mark.parametrize("second", ["write", "create"])
def test_two_file_patch_reaches_private_artifact(chat, second):
    proposal, context = _context(chat)
    before = inventory(chat.target, include_git=True)
    pending = context.authorize_tool("apply_patch", _patch(second))
    result = asyncio.run(pending.boundary_policy.execute())
    receipt = context.complete_command(pending, result)
    artifact = result["trusted_execution"]["promotion_artifact"]
    assert len(artifact["effects"]) == 2
    assert [item["effect"] for item in artifact["effects"]] == ["write", second]
    assert receipt["promotion"]["status"] == "human_approval_required"
    assert inventory(chat.target, include_git=True) == before
    assert proposal["capability_profile_version"] == CAPABILITY_PROFILE_VERSION


@pytest.mark.parametrize("patch", [
    "*** Begin Patch\n*** Update File: src/app.py\n@@\n-pass\n+x\n*** Update File: src/app.py\n@@\n-pass\n+y\n*** End Patch",
    "*** Begin Patch\n*** Update File: src/app.py\n@@\n-pass\n+x\n*** Update File: tests/test_app.py\n@@\n-pass\n+y\n*** Add File: tests/third.py\n+z\n*** End Patch",
    "*** Begin Patch\n*** Update File: src/app.py\n@@\n-pass\n+x\n*** Delete File: tests/test_app.py\n*** End Patch",
])
def test_duplicate_third_and_delete_fail_before_private_execution(chat, patch):
    _proposal, context = _context(chat)
    with pytest.raises(InstitutionalBootError):
        context.authorize_tool("apply_patch", patch)


def test_collective_digest_and_old_profile_rejected(chat, tmp_path):
    proposal, _ = _context(chat)
    artifact = _sealed_two(chat, tmp_path, proposal)
    assert artifact["artifact_digest"]
    artifact["effects"][1]["content_sha256"] = "0" * 64
    with pytest.raises(PromotionError, match="invalid"):
        record_pending("s", artifact)
    old = dict(proposal, capability_profile_version="2")
    with pytest.raises(MandateProposalError, match="incompatible"):
        validate_proposal_identity(old)


def test_new_pair_supersedes_pending_candidate_and_preserves_its_evidence(chat, tmp_path):
    proposal, _ = _context(chat)
    old = _sealed_two(chat, tmp_path, proposal)
    record_pending("s", old)
    _validate_receipt(chat, old)
    replacement = _sealed_two(chat, tmp_path, proposal)
    assert record_pending("s", replacement)["status"] == "human_approval_required"
    with chat.factory() as db:
        prior = db.get(MobsPromotion, old["id"])
        assert prior.status == "promotion_blocked"
        outcome = json.loads(prior.outcome_json)
        assert outcome["reason"] == "superseded_by_new_candidate"
        assert outcome["superseded_by"] == replacement["id"]
        assert outcome["previous_outcome"]["validation"]["artifact_digest"] == old["artifact_digest"]
        assert db.get(MobsPromotion, replacement["id"]).status == "human_approval_required"
    reference = {"promotion_id": old["id"], "promotion_digest": old["artifact_digest"]}
    with pytest.raises(PromotionError, match="no longer pending"):
        asyncio.run(validate_private_artifact("s", reference, "python -m pytest tests/test_app.py",
                                              authenticated_actor(chat.trust)))
    with pytest.raises(PromotionError, match="no longer pending"):
        approve_and_apply("s", reference, authenticated_actor(chat.trust))
    assert chat.post("validate_promotion", message="python -m pytest tests/test_app.py",
                     mobs_promotion_id=old["id"], mobs_promotion_digest=old["artifact_digest"]).status_code == 400
    assert chat.post("promote", mobs_promotion_id=old["id"],
                     mobs_promotion_digest=old["artifact_digest"]).status_code == 400


@pytest.mark.parametrize("quarantine_status", ["promotion_applying", "promotion_interrupted_or_uncertain"])
def test_unresolved_target_blocks_other_artifacts_but_not_other_target(chat, tmp_path, quarantine_status):
    proposal, _ = _context(chat)
    unresolved = _sealed_two(chat, tmp_path, proposal)
    record_pending("s", unresolved)
    single = _artifact(chat, tmp_path, proposal, effect="write", path="src/app.py",
                       content=b"pass\n# another candidate\n")
    record_pending("s", single)
    next_pair = _sealed_two(chat, tmp_path, proposal)
    other_target = tmp_path / "other-target"
    shutil.copytree(chat.target, other_target)
    other_pair = _sealed_two(chat, tmp_path, proposal, target=other_target)
    with chat.factory() as db:
        row = db.get(MobsPromotion, unresolved["id"])
        row.status = quarantine_status
        row.outcome_json = json.dumps({"status": quarantine_status, "reason": "test_unresolved"})
        db.commit()
    with pytest.raises(PromotionError, match="quarantined"):
        record_pending("s", next_pair)
    reference = {"promotion_id": single["id"], "promotion_digest": single["artifact_digest"]}
    with pytest.raises(PromotionError, match="quarantined"):
        promotion_requires_human("s", reference)
    with pytest.raises(PromotionError, match="quarantined"):
        asyncio.run(validate_private_artifact("s", reference, "python -m pytest tests/test_app.py",
                                              authenticated_actor(chat.trust)))
    with pytest.raises(PromotionError, match="quarantined"):
        approve_and_apply("s", reference, authenticated_actor(chat.trust))
    with chat.factory() as db:
        assert db.get(MobsPromotion, unresolved["id"]).status == quarantine_status
        assert db.get(MobsPromotion, single["id"]).status == "promotion_blocked"
    assert record_pending("s", other_pair)["status"] == "human_approval_required"


@pytest.mark.parametrize("change", ["supersede", "quarantine"])
def test_private_validation_rechecks_candidate_and_target_after_command(chat, tmp_path, monkeypatch, change):
    proposal, _ = _context(chat)
    candidate = _sealed_two(chat, tmp_path, proposal)
    record_pending("s", candidate)
    if change == "supersede":
        replacement = _sealed_two(chat, tmp_path, proposal)
    else:
        blocker = _artifact(chat, tmp_path, proposal, effect="write", path="src/app.py",
                            content=b"pass\n# independent promotion\n")
        record_pending("s", blocker)

    async def during_validation(_policy):
        if change == "supersede":
            record_pending("s", replacement)
        else:
            with chat.factory() as db:
                row = db.get(MobsPromotion, blocker["id"])
                row.status = "promotion_interrupted_or_uncertain"
                db.commit()
        return {"exit_code": 0, "output": "2 passed", "trusted_execution": {
            "adapter": "windows_appcontainer_job_v1", "effects": [],
            "validated_artifact_digest": candidate["artifact_digest"],
            "target_before_sha256": candidate["target_inventory_sha256"],
            "target_after_sha256": candidate["target_inventory_sha256"], "timed_out": False}}

    monkeypatch.setattr(WindowsExecutionPolicy, "execute", during_validation)
    reference = {"promotion_id": candidate["id"], "promotion_digest": candidate["artifact_digest"]}
    with pytest.raises(PromotionError, match="no longer pending|quarantined"):
        asyncio.run(validate_private_artifact("s", reference, "python -m pytest tests/test_app.py",
                                              authenticated_actor(chat.trust)))
    with chat.factory() as db:
        row = db.get(MobsPromotion, candidate["id"])
        if change == "supersede":
            assert row.status == "promotion_blocked"
            assert json.loads(row.outcome_json)["reason"] == "superseded_by_new_candidate"
        else:
            assert row.status == "human_approval_required"
            assert "validation" not in json.loads(row.outcome_json or "{}")


@pytest.mark.parametrize("second", ["write", "create"])
def test_validated_pair_promotes_exact_inventory(chat, tmp_path, second):
    proposal, _ = _context(chat)
    artifact = _sealed_two(chat, tmp_path, proposal, second=second)
    before = inventory(chat.target, include_git=True)
    assert record_pending("s", artifact)["status"] == "human_approval_required"
    _validate_receipt(chat, artifact)
    result = approve_and_apply("s", {"promotion_id": artifact["id"],
                                     "promotion_digest": artifact["artifact_digest"]},
                               authenticated_actor(chat.trust))
    assert result["status"] == "promotion_applied_verified"
    after = inventory(chat.target, include_git=True)
    expected = dict(before)
    expected.update({entry["path"]: entry["content_sha256"] for entry in artifact["effects"]})
    assert after == expected
    with pytest.raises(PromotionError, match="no longer pending"):
        approve_and_apply("s", {"promotion_id": artifact["id"],
                                "promotion_digest": artifact["artifact_digest"]}, authenticated_actor(chat.trust))


def test_multifile_self_development_still_requires_human(chat, tmp_path, monkeypatch):
    install_junior_operational_profile(monkeypatch, tmp_path, self_development_preauthorized=True)
    monkeypatch.setenv("MOBS_SELF_DEVELOPMENT_ROOT", str(chat.target))
    proposal, _ = _context(chat)
    artifact = _sealed_two(chat, tmp_path, proposal)
    assert artifact["self_development"] is True
    assert record_pending("s", artifact)["status"] == "human_approval_required"


@pytest.mark.parametrize("mutate", [False, True])
def test_private_validation_overlays_exact_pair_and_rejects_candidate_mutation(chat, tmp_path, monkeypatch, mutate):
    proposal, _ = _context(chat)
    artifact = _sealed_two(chat, tmp_path, proposal)
    baseline = inventory(chat.target, include_git=True)
    def stage(_executable, private, _include_pytest=False):
        toolchain = private / ".odysseus-toolchain"
        toolchain.mkdir()
        executable = toolchain / "python.exe"
        executable.write_bytes(b"synthetic toolchain")
        return executable
    def observe(_executable, _arguments, private, _environment, _timeout, _stop, _write, _create):
        assert (private / "src/app.py").read_text() == "print('ok')\n"
        assert (private / "tests/test_app.py").read_text() == "assert True\n"
        if mutate:
            (private / "tests/test_app.py").write_text("changed during validation\n")
        return {"stdout": "test output", "stderr": "", "exit_code": 0, "timed_out": False,
                "profile_effects": [], "native_configuration": {"synthetic_observer": True}}
    monkeypatch.setattr("src.windows_native_execution._stage_python_toolchain", stage)
    monkeypatch.setattr("src.windows_native_execution._run_appcontainer", observe)
    policy = WindowsExecutionPolicy(str(chat.target), ("python", "-m", "pytest", "tests/test_app.py"),
                                    ("src/**", "tests/**"), ("src/**", "tests/**"), (), 30,
                                    validation_artifact=artifact)
    if mutate:
        with pytest.raises(TrustedExecutionUnavailable, match="sealed candidate"):
            policy._execute_sync(threading.Event())
    else:
        result = policy._execute_sync(threading.Event())
        assert result["trusted_execution"]["validated_artifact_digest"] == artifact["artifact_digest"]
    assert inventory(chat.target, include_git=True) == baseline


def test_second_publication_failure_restores_both_preimages(chat, tmp_path, monkeypatch):
    proposal, _ = _context(chat)
    artifact = _sealed_two(chat, tmp_path, proposal)
    record_pending("s", artifact); _validate_receipt(chat, artifact)
    before = inventory(chat.target, include_git=True)
    real_replace = os.replace
    failed = False
    def fail_second(source, destination):
        nonlocal failed
        if str(destination).endswith("test_app.py") and not failed:
            failed = True
            raise OSError("second publication failed")
        return real_replace(source, destination)
    monkeypatch.setattr("src.mobs_controlled_promotion.os.replace", fail_second)
    with pytest.raises(OSError, match="second publication failed"):
        approve_and_apply("s", {"promotion_id": artifact["id"], "promotion_digest": artifact["artifact_digest"]},
                          authenticated_actor(chat.trust))
    assert inventory(chat.target, include_git=True) == before
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact["id"]).status == "promotion_blocked"


def test_recovery_drift_is_uncertain_and_reapplication_blocked(chat, tmp_path, monkeypatch):
    proposal, _ = _context(chat)
    artifact = _sealed_two(chat, tmp_path, proposal)
    record_pending("s", artifact); _validate_receipt(chat, artifact)
    real_replace = os.replace
    def drift_then_fail(source, destination):
        if str(destination).endswith("test_app.py"):
            (chat.target / "src/app.py").write_text("external drift\n")
            raise OSError("second publication failed")
        return real_replace(source, destination)
    monkeypatch.setattr("src.mobs_controlled_promotion.os.replace", drift_then_fail)
    with pytest.raises(OSError, match="second publication failed"):
        approve_and_apply("s", {"promotion_id": artifact["id"], "promotion_digest": artifact["artifact_digest"]},
                          authenticated_actor(chat.trust))
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact["id"]).status == "promotion_interrupted_or_uncertain"
    with pytest.raises(PromotionError, match="no longer pending"):
        approve_and_apply("s", {"promotion_id": artifact["id"], "promotion_digest": artifact["artifact_digest"]},
                          authenticated_actor(chat.trust))


def test_drift_in_unrelated_path_blocks_entire_pair(chat, tmp_path):
    proposal, _ = _context(chat)
    artifact = _sealed_two(chat, tmp_path, proposal)
    record_pending("s", artifact); _validate_receipt(chat, artifact)
    (chat.target / "docs/readme.md").write_text("external change\n")
    with pytest.raises(PromotionError, match="drift"):
        approve_and_apply("s", {"promotion_id": artifact["id"], "promotion_digest": artifact["artifact_digest"]},
                          authenticated_actor(chat.trust))
    assert (chat.target / "src/app.py").read_text() == "pass\n"
    assert (chat.target / "tests/test_app.py").read_text() == "pass\n"
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact["id"]).status == "promotion_blocked"


def test_http_validation_binds_exact_pair_and_does_not_autoapprove(chat, tmp_path, monkeypatch):
    proposal, _ = _context(chat)
    artifact = _sealed_two(chat, tmp_path, proposal)
    record_pending("s", artifact)
    async def validated(policy):
        assert policy.validation_artifact["artifact_digest"] == artifact["artifact_digest"]
        assert len(policy.validation_artifact["effects"]) == 2
        return {"exit_code": 0, "output": "2 passed", "trusted_execution": {
            "adapter": "windows_appcontainer_job_v1", "effects": [],
            "validated_artifact_digest": artifact["artifact_digest"],
            "target_before_sha256": artifact["target_inventory_sha256"],
            "target_after_sha256": artifact["target_inventory_sha256"], "timed_out": False}}
    monkeypatch.setattr(WindowsExecutionPolicy, "execute", validated)
    result = event(chat.post("validate_promotion", message="python -m pytest tests/test_app.py",
                             mobs_promotion_id=artifact["id"], mobs_promotion_digest=artifact["artifact_digest"]),
                   "mobs_promotion_validated")
    assert result["status"] == "validated_pending_human_approval"
    assert result["validation"]["artifact_digest"] == artifact["artifact_digest"]
    with chat.factory() as db:
        assert db.get(MobsPromotion, artifact["id"]).status == "human_approval_required"
