"""Sealed, single-file controlled promotion for the private Windows adapter.

This module deliberately owns neither an agent loop nor a tool dispatcher.  It
receives one already-authorized private effect, stores it before the private
workspace is removed, and applies it only after a separate human decision.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import uuid
from pathlib import Path
from typing import Any


class PromotionError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _store_root_for_target(target: Path) -> Path:
    """Return backend storage only when it is physically outside the target.

    The check deliberately happens before creating the store directory: a bad
    installation setting must not leave an artifact directory in the real
    project.  ``resolve`` follows links/reparse points on the platforms that
    expose them through ``pathlib``, so containment is evaluated on the
    effective path rather than the spelling supplied by configuration.
    """
    raw = os.environ.get("MOBS_PROMOTION_STORE", "")
    if not raw:
        raise PromotionError("Controlled Promotion storage is not provisioned")
    configured = Path(raw)
    if not configured.is_absolute():
        raise PromotionError("Controlled Promotion storage is invalid")
    target = target.resolve(strict=True)
    root = configured.resolve(strict=False)
    try:
        root.relative_to(target)
    except ValueError:
        pass
    else:
        raise PromotionError("Controlled Promotion storage cannot reside in the target workspace")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _policy() -> dict:
    """Read an installation-pinned operational policy; only Junior is known."""
    name = os.environ.get("MOBS_OPERATIONAL_AUTHORITY_FILE", "")
    pinned = os.environ.get("MOBS_OPERATIONAL_AUTHORITY_SHA256", "")
    installation = os.environ.get("ODYSSEUS_INSTALLATION_ID", "")
    if not name or not pinned or not installation:
        raise PromotionError("Operational Authority Profile is not provisioned")
    raw = Path(name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise PromotionError("Operational Authority Profile integrity check failed")
    try:
        policy = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PromotionError("Operational Authority Profile is invalid") from exc
    if not isinstance(policy, dict) or policy.get("format_version") != 1:
        raise PromotionError("Operational Authority Profile is invalid")
    if policy.get("installation_id") != installation or policy.get("state") != "active":
        raise PromotionError("Operational Authority Profile is not active for this installation")
    if policy.get("mode") != "junior" or policy.get("promotion_result") != "human_approval_required":
        raise PromotionError("Operational Authority Profile is not provisioned for this mode")
    if not isinstance(policy.get("id"), str) or not isinstance(policy.get("version"), int):
        raise PromotionError("Operational Authority Profile identity is invalid")
    return {"id": policy["id"], "version": policy["version"], "mode": "junior",
            "result": "human_approval_required", "sha256": hashlib.sha256(raw).hexdigest()}


def operational_profile_identity() -> dict:
    """Return the exact trusted policy identity that must enter a mandate."""
    return _policy()


def _target_from_binding(binding: dict[str, Any]) -> Path:
    try:
        path = binding["target_baseline"]["path"]
    except (KeyError, TypeError) as exc:
        raise PromotionError("Promotion target baseline is invalid") from exc
    if not isinstance(path, str):
        raise PromotionError("Promotion target baseline is invalid")
    try:
        return Path(path).resolve(strict=True)
    except OSError as exc:
        raise PromotionError("Promotion target workspace is unavailable") from exc


def _target_inventory(target: Path) -> dict[str, str]:
    # Kept local to avoid making the Windows adapter an architectural owner of
    # Controlled Promotion while reusing its exact inventory semantics.
    from src.windows_native_execution import inventory
    return inventory(target, include_git=True)


def _verify_target_inventory(target: Path, expected_digest: str) -> None:
    if _inventory_digest_proxy(_target_inventory(target)) != expected_digest:
        raise PromotionError("Target workspace drift blocks promotion artifact sealing")


def seal_private_effect(private_root: Path, effect: dict[str, str], *, binding: dict[str, Any]) -> dict[str, Any]:
    """Copy one eligible regular-file effect to backend storage before cleanup."""
    if effect.get("effect") not in {"create", "write"} or not isinstance(effect.get("path"), str):
        raise PromotionError("Only one regular-file create or write can be promoted")
    relative = effect["path"]
    source = (private_root / relative).resolve()
    if not source.is_relative_to(private_root.resolve()) or source.is_symlink() or not source.is_file():
        raise PromotionError("Promotion effect is not a confined regular file")
    target = _target_from_binding(binding)
    expected_inventory = binding.get("target_inventory_sha256")
    if not isinstance(expected_inventory, str):
        raise PromotionError("Promotion target inventory binding is invalid")
    _verify_target_inventory(target, expected_inventory)
    policy = _policy()
    root = _store_root_for_target(target)
    artifact_id = uuid.uuid4().hex
    directory = root / artifact_id
    directory.mkdir(mode=0o700)
    content = directory / "content.bin"
    with source.open("rb") as input_stream, content.open("xb") as output_stream:
        for block in iter(lambda: input_stream.read(1024 * 1024), b""):
            output_stream.write(block)
        output_stream.flush()
        os.fsync(output_stream.fileno())
    content_sha256 = _file_digest(content)
    artifact = {"id": artifact_id, "effect": effect["effect"], "path": relative,
                "content_sha256": content_sha256, "content_bytes": content.stat().st_size,
                "preimage_sha256": binding.get("private_before", {}).get(relative),
                "target_inventory_sha256": binding["target_inventory_sha256"],
                "source_baseline": binding["source_baseline"], "target_baseline": binding["target_baseline"],
                "proposal_id": binding["proposal_id"], "proposal_digest": binding["proposal_digest"],
                "authority_snapshot": binding["authority_snapshot"],
                "review_authorization": binding["review_authorization"],
                "operational_policy": policy}
    artifact["artifact_digest"] = _digest(artifact)
    with (directory / "artifact.json").open("x", encoding="utf-8") as stream:
        json.dump(artifact, stream, sort_keys=True, separators=(",", ":"))
        stream.flush()
        os.fsync(stream.fileno())
    # The private execution must never mutate its real target while sealing.
    _verify_target_inventory(target, expected_inventory)
    return artifact


def record_pending(session_id: str, artifact: dict[str, Any]) -> dict[str, Any]:
    from core.database import MobsPromotion, SessionLocal
    db = SessionLocal()
    try:
        if db.query(MobsPromotion).filter(MobsPromotion.artifact_digest == artifact["artifact_digest"]).first():
            raise PromotionError("Promotion artifact already recorded")
        row = MobsPromotion(id=artifact["id"], session_id=session_id, proposal_id=artifact["proposal_id"],
                            proposal_digest=artifact["proposal_digest"], artifact_digest=artifact["artifact_digest"],
                            status="human_approval_required", artifact_json=json.dumps(artifact))
        db.add(row); db.commit()
        return promotion_summary(artifact, row.status)
    finally:
        db.close()


def promotion_summary(artifact: dict[str, Any], status: str) -> dict[str, Any]:
    return {key: artifact[key] for key in ("id", "effect", "path", "content_sha256", "content_bytes", "artifact_digest", "proposal_id", "proposal_digest", "authority_snapshot", "operational_policy")} | {"status": status}


def _record_outcome(db, row, status: str, reason: str, **facts) -> None:
    row.status = status
    row.outcome_json = json.dumps({"status": status, "reason": reason, **facts}, sort_keys=True)
    db.commit()


def _load_artifact(row) -> dict[str, Any]:
    artifact = json.loads(row.artifact_json)
    if artifact.get("artifact_digest") != _digest({k: v for k, v in artifact.items() if k != "artifact_digest"}):
        raise PromotionError("Stored promotion artifact is invalid")
    return artifact


def _load_content(artifact: dict[str, Any], target: Path) -> Path:
    path = _store_root_for_target(target) / artifact["id"] / "content.bin"
    if path.is_symlink() or not path.is_file() or _file_digest(path) != artifact["content_sha256"]:
        raise PromotionError("Sealed promotion content is missing or altered")
    return path


def approve_and_apply(session_id: str, reference: dict[str, str], reviewer) -> dict[str, Any]:
    """Revalidate trusted state and atomically apply exactly the sealed effect."""
    from core.database import MobsPromotion, SessionLocal
    from src.mobs_mandate_builder import load_proposal, validate_execution_review
    from src.mobs_institutional_boot import InstitutionalBootError, capture_repository, institutional_boot, _path_is_allowed
    from src.mobs_reviewer_authorization import authorize_reviewer
    db = SessionLocal(); row = None; application_started = False
    try:
        row = db.query(MobsPromotion).filter(MobsPromotion.id == reference.get("promotion_id")).first()
        if row is None or row.session_id != session_id:
            raise PromotionError("Stale or unknown promotion")
        if row.artifact_digest != reference.get("promotion_digest"):
            _record_outcome(db, row, "promotion_blocked", "stale_promotion_reference")
            raise PromotionError("Stale or unknown promotion")
        if row.status != "human_approval_required":
            raise PromotionError("Promotion is no longer pending human approval")
        artifact = _load_artifact(row)
        try:
            proposal = load_proposal(session_id)
        except Exception as exc:
            _record_outcome(db, row, "promotion_blocked", "mandate_or_operational_profile_changed")
            raise PromotionError("Promotion mandate or Operational Authority Profile changed") from exc
        if not proposal or proposal.get("proposal_id") != artifact["proposal_id"] or proposal.get("proposal_digest") != artifact["proposal_digest"]:
            raise PromotionError("Promotion mandate has been replaced")
        review = proposal.get("review_record")
        # proposal persistence stores review separately; retrieve the exact persisted receipt.
        from src.mobs_mandate_builder import load_authority_review
        review = load_authority_review(artifact["authority_snapshot"], reviewer.username)
        if review is None:
            raise PromotionError("Current reviewer has no valid institutional review")
        current_auth = authorize_reviewer(proposal, reviewer)
        if current_auth != artifact["review_authorization"]:
            raise PromotionError("Reviewer authorization changed; promotion requires a new review")
        if proposal.get("operational_authority_profile") != artifact["operational_policy"] or _policy() != artifact["operational_policy"]:
            _record_outcome(db, row, "promotion_blocked", "operational_policy_changed")
            raise PromotionError("Operational Authority Profile changed; promotion is invalid")
        candidate = {**proposal, "authority_review": "consistent", "review_record": review}
        try:
            context = institutional_boot(candidate, candidate["target"]["path"])
        except InstitutionalBootError as exc:
            raise PromotionError("Authority or baseline drift blocks promotion") from exc
        target = Path(context.target["path"]).resolve(strict=True)
        content = _load_content(artifact, target)
        if capture_repository(str(target)) != artifact["target_baseline"]:
            _record_outcome(db, row, "promotion_blocked", "target_baseline_drift")
            raise PromotionError("Target repository baseline drift blocks promotion")
        from src.windows_native_execution import inventory, _reparse
        initial_inventory = inventory(target, include_git=True)
        if _inventory_digest_proxy(initial_inventory) != artifact["target_inventory_sha256"]:
            _record_outcome(db, row, "promotion_blocked", "target_inventory_drift")
            raise PromotionError("Target workspace drift blocks promotion")
        relative = artifact["path"]
        allowed = context.execution.allowed_create_paths if artifact["effect"] == "create" else context.execution.allowed_write_paths
        if not _path_is_allowed(relative, allowed):
            _record_outcome(db, row, "promotion_blocked", "path_outside_mandate")
            raise PromotionError("Promotion path is outside the exact mandate")
        destination = (target / relative)
        parent = destination.parent.resolve(strict=True)
        if not parent.is_relative_to(target) or _reparse(parent) or destination.is_symlink():
            _record_outcome(db, row, "promotion_blocked", "physical_confinement_failed")
            raise PromotionError("Promotion path cannot be physically confined")
        if artifact["effect"] == "create":
            if destination.exists():
                _record_outcome(db, row, "promotion_blocked", "create_destination_exists")
                raise PromotionError("Promotion create destination already exists")
        else:
            if not destination.is_file() or _reparse(destination) or _file_digest(destination) != artifact["preimage_sha256"]:
                _record_outcome(db, row, "promotion_blocked", "write_preimage_drift")
                raise PromotionError("Promotion write preimage drift blocks promotion")
        # The sealed artifact is already backend-controlled, content-complete
        # preparation.  Capture the full target state before declaring the
        # first target-local staging file a real mutation attempt.
        pre_apply_inventory = inventory(target, include_git=True)
        if pre_apply_inventory != initial_inventory:
            _record_outcome(db, row, "promotion_blocked", "pre_apply_concurrent_drift")
            raise PromotionError("Target drift immediately before promotion")
        expected = dict(pre_apply_inventory)
        expected[relative] = artifact["content_sha256"]
        _record_outcome(db, row, "promotion_applying", "real_mutation_started",
                        pre_apply_inventory_sha256=_inventory_digest_proxy(pre_apply_inventory))
        application_started = True
        temp_name = None
        try:
            # This staging file lives beside the destination to retain atomic
            # same-volume publication.  It is created only after the durable
            # applying state above, so every subsequent failure is factual
            # uncertainty rather than a pending approval.
            fd, temp_name = tempfile.mkstemp(prefix=".odysseus-promote-", dir=parent)
            with os.fdopen(fd, "wb") as output, content.open("rb") as input_stream:
                for block in iter(lambda: input_stream.read(1024 * 1024), b""):
                    output.write(block)
                output.flush(); os.fsync(output.fileno())
            if _file_digest(Path(temp_name)) != artifact["content_sha256"]:
                raise PromotionError("Prepared promotion content failed verification")
            temp_relative = Path(temp_name).resolve().relative_to(target).as_posix()
            observed_with_staging = inventory(target, include_git=True)
            if observed_with_staging.get(temp_relative) != artifact["content_sha256"]:
                raise PromotionError("Prepared promotion staging file is not attributable")
            observed_pre_apply = {path: digest for path, digest in observed_with_staging.items()
                                   if path != temp_relative}
            if pre_apply_inventory != initial_inventory:
                raise PromotionError("Target drift during promotion staging")
            # A single same-directory atomic publication is the only real-world mutation in v0.
            if artifact["effect"] == "create":
                os.link(temp_name, destination)
            else:
                os.replace(temp_name, destination)
        finally:
            if temp_name is not None and os.path.exists(temp_name): os.unlink(temp_name)
        post_apply_inventory = inventory(target, include_git=True)
        if (not destination.is_file() or _file_digest(destination) != artifact["content_sha256"]
                or post_apply_inventory != expected):
            _record_outcome(db, row, "promotion_interrupted_or_uncertain", "post_apply_verification_failed")
            raise PromotionError("Promotion result is uncertain; verification failed")
        row.status = "promotion_applied_verified"
        row.approval_json = json.dumps({"reviewer": reviewer.username, "authorization": current_auth,
                                        "artifact_digest": artifact["artifact_digest"]})
        row.outcome_json = json.dumps({"status": row.status, "reason": "exact_post_apply_inventory_verified",
                                       "post_apply_inventory_sha256": _inventory_digest_proxy(post_apply_inventory)}, sort_keys=True)
        db.commit()
        return promotion_summary(artifact, row.status)
    except PromotionError as exc:
        db.rollback()
        if row is not None and application_started and row.status != "promotion_interrupted_or_uncertain":
            _record_outcome(db, row, "promotion_interrupted_or_uncertain", "application_validation_or_staging_failed",
                            error=type(exc).__name__)
        elif row is not None and row.status == "human_approval_required":
            _record_outcome(db, row, "promotion_blocked", "pre_apply_validation_failed",
                            error=type(exc).__name__)
        raise
    except Exception as exc:
        db.rollback()
        if row is not None:
            try:
                status = "promotion_interrupted_or_uncertain" if application_started else "promotion_blocked"
                reason = "application_exception" if application_started else "pre_apply_exception"
                _record_outcome(db, row, status, reason, error=type(exc).__name__)
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()


def _inventory_digest_proxy(entries: dict[str, str]) -> str:
    h = hashlib.sha256()
    for path, value in sorted(entries.items()):
        h.update(path.encode("utf-8", "surrogateescape")); h.update(b"\0"); h.update(value.encode()); h.update(b"\0")
    return h.hexdigest()
