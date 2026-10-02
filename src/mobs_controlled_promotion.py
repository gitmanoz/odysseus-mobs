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
import sys
import tempfile
import uuid
from dataclasses import replace
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


def _self_development_target(target: Path) -> bool:
    """Recognize only the checkout explicitly pinned by backend configuration."""
    configured = os.environ.get("MOBS_SELF_DEVELOPMENT_ROOT", "")
    if not configured or not Path(configured).is_absolute():
        return False
    try:
        root = Path(configured).resolve(strict=True)
        selected = target.resolve(strict=True)
        if root != selected:
            return False
        from src.mobs_institutional_boot import capture_repository
        return Path(capture_repository(str(selected))["path"]) == root
    except (OSError, RuntimeError, ValueError):
        return False


def _require_separate_runtime(target: Path) -> None:
    """Reject overlap with code, interpreter, or state of the active install."""
    from src.runtime_paths import get_app_root
    from src.constants import DATA_DIR
    from src import mobs_reviewer_authorization

    try:
        target = target.resolve(strict=True)
        active = [Path(get_app_root()), Path(sys.executable), Path(DATA_DIR)]
        for name in ("src.agent_loop", "src.mobs_controlled_promotion",
                     "src.windows_native_execution", "routes.chat_routes", "core.database"):
            module = sys.modules.get(name)
            if module is not None and getattr(module, "__file__", None):
                active.append(Path(module.__file__))
        for name in (os.environ.get("MOBS_OPERATIONAL_AUTHORITY_FILE"),
                     mobs_reviewer_authorization._ANCHOR.path):
            if name:
                active.append(Path(name))
        resolved = [path.resolve(strict=True) for path in active]
    except (OSError, RuntimeError, ValueError) as exc:
        raise PromotionError("Physical runtime separation cannot be established") from exc
    runtime = resolved[0]
    if (target == runtime or target.is_relative_to(runtime)
            or any(path.is_relative_to(target) for path in resolved)):
        raise PromotionError("Self-development target overlaps the active runtime installation")


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
    self_development_result = policy.get("self_development_promotion_result")
    if self_development_result is not None and (
            policy["version"] < 2 or self_development_result != "preauthorized"):
        raise PromotionError("Operational Authority Profile self-development policy is invalid")
    identity = {"id": policy["id"], "version": policy["version"], "mode": "junior",
                "result": "human_approval_required", "sha256": hashlib.sha256(raw).hexdigest()}
    if self_development_result is not None:
        identity["self_development_result"] = self_development_result
    return identity


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


def _lock_promotion_transition(db) -> None:
    """Serialize target-state checks with promotion registration/application."""
    from sqlalchemy import text

    if db.bind.dialect.name != "sqlite":
        raise PromotionError("Atomic promotion transition is unavailable for this database")
    db.execute(text("BEGIN IMMEDIATE"))


def seal_private_effect(private_root: Path, effect: dict[str, str], *, binding: dict[str, Any]) -> dict[str, Any]:
    """Copy one eligible regular-file effect to backend storage before cleanup."""
    if effect.get("effect") not in {"create", "write"} or not isinstance(effect.get("path"), str):
        raise PromotionError("Only one regular-file create or write can be promoted")
    relative = effect["path"]
    source = (private_root / relative).resolve()
    if not source.is_relative_to(private_root.resolve()) or source.is_symlink() or not source.is_file():
        raise PromotionError("Promotion effect is not a confined regular file")
    target = _target_from_binding(binding)
    self_development = _self_development_target(target)
    _require_separate_runtime(target)
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
    preimage_sha256 = binding.get("private_before", {}).get(relative)
    if self_development and effect["effect"] == "write":
        original = target / relative
        if not original.is_file() or _file_digest(original) != preimage_sha256:
            raise PromotionError("Self-development preimage differs from target")
        with original.open("rb") as input_stream, (directory / "preimage.bin").open("xb") as output_stream:
            for block in iter(lambda: input_stream.read(1024 * 1024), b""):
                output_stream.write(block)
            output_stream.flush(); os.fsync(output_stream.fileno())
        if _file_digest(directory / "preimage.bin") != preimage_sha256:
            raise PromotionError("Self-development preimage could not be preserved")
    artifact = {"id": artifact_id, "effect": effect["effect"], "path": relative,
                "content_sha256": content_sha256, "content_bytes": content.stat().st_size,
                "preimage_sha256": preimage_sha256,
                "self_development": self_development,
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


def seal_private_effects(private_root: Path, effects: list[dict[str, str]], *, binding: dict[str, Any]) -> dict[str, Any]:
    """Seal exactly two effects as one indivisible approval and validation unit."""
    from src.mobs_institutional_boot import _portable_path

    if len(effects) != 2 or any(effect.get("effect") not in {"create", "write"} for effect in effects):
        raise PromotionError("Multi-file artifact requires exactly two create/write effects")
    ordered = sorted(effects, key=lambda effect: effect["path"].casefold())
    paths = [_portable_path(effect["path"], "promotion path") for effect in ordered]
    if len({path.casefold() for path in paths}) != 2:
        raise PromotionError("Multi-file artifact has duplicate paths")
    target = _target_from_binding(binding)
    _require_separate_runtime(target)
    expected_inventory = binding.get("target_inventory_sha256")
    if not isinstance(expected_inventory, str):
        raise PromotionError("Promotion target inventory binding is invalid")
    _verify_target_inventory(target, expected_inventory)
    policy = _policy()
    root = _store_root_for_target(target)
    artifact_id = uuid.uuid4().hex
    directory = root / artifact_id
    directory.mkdir(mode=0o700)
    manifest_effects = []
    before = binding.get("private_before") or {}
    for index, (effect, relative) in enumerate(zip(ordered, paths)):
        source = (private_root / relative).resolve()
        if not source.is_relative_to(private_root.resolve()) or source.is_symlink() or not source.is_file():
            raise PromotionError("Multi-file effect is not a confined regular file")
        preimage = before.get(relative)
        if effect["effect"] == "create" and (preimage is not None or (target / relative).exists()):
            raise PromotionError("Create effect has a preimage")
        if effect["effect"] == "write" and (not isinstance(preimage, str)
                                             or not (target / relative).is_file()
                                             or _file_digest(target / relative) != preimage):
            raise PromotionError("Write preimage differs from target")
        content_path = directory / f"content-{index}.bin"
        with source.open("rb") as input_stream, content_path.open("xb") as output_stream:
            for block in iter(lambda: input_stream.read(1024 * 1024), b""):
                output_stream.write(block)
            output_stream.flush(); os.fsync(output_stream.fileno())
        entry = {"effect": effect["effect"], "path": relative,
                 "content_sha256": _file_digest(content_path),
                 "content_bytes": content_path.stat().st_size,
                 "preimage_sha256": preimage}
        if effect["effect"] == "write":
            backup = directory / f"preimage-{index}.bin"
            with (target / relative).open("rb") as input_stream, backup.open("xb") as output_stream:
                for block in iter(lambda: input_stream.read(1024 * 1024), b""):
                    output_stream.write(block)
                output_stream.flush(); os.fsync(output_stream.fileno())
            if _file_digest(backup) != preimage:
                raise PromotionError("Write preimage could not be preserved")
        manifest_effects.append(entry)
    artifact = {"format_version": 2, "id": artifact_id, "effects": manifest_effects,
                "self_development": _self_development_target(target),
                "target_inventory_sha256": expected_inventory,
                "source_baseline": binding["source_baseline"],
                "target_baseline": binding["target_baseline"],
                "proposal_id": binding["proposal_id"],
                "proposal_digest": binding["proposal_digest"],
                "authority_snapshot": binding["authority_snapshot"],
                "review_authorization": binding["review_authorization"],
                "operational_policy": policy}
    artifact["artifact_digest"] = _digest(artifact)
    with (directory / "artifact.json").open("x", encoding="utf-8") as stream:
        json.dump(artifact, stream, sort_keys=True, separators=(",", ":"))
        stream.flush(); os.fsync(stream.fileno())
    _verify_target_inventory(target, expected_inventory)
    return artifact


def record_pending(session_id: str, artifact: dict[str, Any]) -> dict[str, Any]:
    from core.database import MobsPromotion, SessionLocal
    db = SessionLocal()
    try:
        if artifact.get("format_version") == 2:
            if artifact.get("artifact_digest") != _digest({k: v for k, v in artifact.items()
                                                           if k != "artifact_digest"}):
                raise PromotionError("Multi-file artifact digest is invalid")
            _verified_artifact_contents(artifact, _target_from_binding(artifact))
        _lock_promotion_transition(db)
        if db.query(MobsPromotion).filter(MobsPromotion.artifact_digest == artifact["artifact_digest"]).first():
            raise PromotionError("Promotion artifact already recorded")
        policy = _policy()
        if artifact["operational_policy"] != policy:
            raise PromotionError("Operational Authority Profile changed before artifact recording")
        if artifact.get("self_development") and not _self_development_target(_target_from_binding(artifact)):
            raise PromotionError("Self-development target identity changed")
        target = _target_from_binding(artifact)
        _assert_target_not_quarantined(db, target)
        if artifact.get("format_version") == 2:
            # Supersession and insertion share one commit: a failed registration
            # must not discard the previous candidate or its validation record.
            previous = (db.query(MobsPromotion)
                        .filter(MobsPromotion.session_id == session_id,
                                MobsPromotion.proposal_id == artifact["proposal_id"],
                                MobsPromotion.proposal_digest == artifact["proposal_digest"],
                                MobsPromotion.status == "human_approval_required").all())
            for candidate in previous:
                sealed = _load_artifact(candidate)
                if sealed.get("format_version") != 2:
                    continue
                if _target_from_binding(sealed) != target:
                    raise PromotionError("Pending proposal has a conflicting target")
                candidate.status = "promotion_blocked"
                candidate.outcome_json = json.dumps({
                    "status": "promotion_blocked", "reason": "superseded_by_new_candidate",
                    "superseded_by": artifact["id"],
                    "previous_outcome": json.loads(candidate.outcome_json or "{}"),
                }, sort_keys=True)
        status = ("promotion_preauthorized" if not artifact.get("effects") and artifact.get("self_development")
                  and policy.get("self_development_result") == "preauthorized"
                  else "human_approval_required")
        row = MobsPromotion(id=artifact["id"], session_id=session_id, proposal_id=artifact["proposal_id"],
                            proposal_digest=artifact["proposal_digest"], artifact_digest=artifact["artifact_digest"],
                            status=status, artifact_json=json.dumps(artifact))
        db.add(row); db.commit()
        return promotion_summary(artifact, row.status)
    finally:
        db.close()


def promotion_summary(artifact: dict[str, Any], status: str) -> dict[str, Any]:
    if artifact.get("format_version") == 2:
        return {key: artifact[key] for key in ("id", "effects", "artifact_digest", "proposal_id",
                                                "proposal_digest", "authority_snapshot", "operational_policy",
                                                "self_development")} | {"status": status}
    return {key: artifact[key] for key in ("id", "effect", "path", "content_sha256", "content_bytes", "artifact_digest", "proposal_id", "proposal_digest", "authority_snapshot", "operational_policy", "self_development")} | {"status": status}


def _record_outcome(db, row, status: str, reason: str, **facts) -> None:
    row.status = status
    row.outcome_json = json.dumps({"status": status, "reason": reason, **facts}, sort_keys=True)
    db.commit()


def _load_artifact(row) -> dict[str, Any]:
    artifact = json.loads(row.artifact_json)
    if artifact.get("artifact_digest") != _digest({k: v for k, v in artifact.items() if k != "artifact_digest"}):
        raise PromotionError("Stored promotion artifact is invalid")
    return artifact


def _assert_target_not_quarantined(db, target: Path, *, exclude_id: str | None = None) -> None:
    """An unresolved real application quarantines its physical target."""
    from core.database import MobsPromotion

    target = target.resolve(strict=True)
    rows = (db.query(MobsPromotion)
            .filter(MobsPromotion.status.in_(("promotion_applying",
                                              "promotion_interrupted_or_uncertain"))).all())
    for row in rows:
        if row.id == exclude_id:
            continue
        try:
            baseline = json.loads(row.artifact_json)["target_baseline"]["path"]
            if not isinstance(baseline, str) or not Path(baseline).is_absolute():
                raise ValueError("invalid target path")
            quarantined = Path(baseline).resolve(strict=False)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise PromotionError("Unresolved promotion has an unverifiable target") from exc
        if quarantined == target:
            raise PromotionError("Target is quarantined by an unresolved promotion")


def promotion_requires_human(session_id: str, reference: dict[str, str]) -> bool:
    """Resolve the gate from persisted, sealed state; client input selects no policy."""
    from core.database import MobsPromotion, SessionLocal
    db = SessionLocal()
    try:
        row = db.query(MobsPromotion).filter(MobsPromotion.id == reference.get("promotion_id")).first()
        if (row is None or row.session_id != session_id
                or row.artifact_digest != reference.get("promotion_digest")):
            raise PromotionError("Stale or unknown promotion")
        artifact = _load_artifact(row)
        if row.status == "promotion_applying":
            _record_outcome(db, row, "promotion_interrupted_or_uncertain", "application_interrupted")
            raise PromotionError("Promotion application was interrupted and cannot be retried")
        _assert_target_not_quarantined(db, _target_from_binding(artifact), exclude_id=row.id)
        if artifact.get("format_version") == 2:
            if row.status != "human_approval_required":
                raise PromotionError("Multi-file promotion requires human approval")
            return True
        if row.status == "promotion_preauthorized":
            if (not artifact.get("self_development")
                    or artifact["operational_policy"].get("self_development_result") != "preauthorized"
                    or _policy() != artifact["operational_policy"]
                    or not _self_development_target(_target_from_binding(artifact))):
                raise PromotionError("Operational preauthorization is invalid")
            return False
        if row.status != "human_approval_required":
            raise PromotionError("Promotion is no longer pending")
        return True
    finally:
        db.close()


def _load_content(artifact: dict[str, Any], target: Path) -> Path:
    path = _store_root_for_target(target) / artifact["id"] / "content.bin"
    if path.is_symlink() or not path.is_file() or _file_digest(path) != artifact["content_sha256"]:
        raise PromotionError("Sealed promotion content is missing or altered")
    return path


def _verified_artifact_content(artifact: dict[str, Any], target: Path) -> Path:
    """Backend-only entry point used to hydrate the exact sealed candidate."""
    if _self_development_target(target) != artifact.get("self_development", False):
        raise PromotionError("Self-development target identity changed")
    _require_separate_runtime(target)
    return _load_content(artifact, target)


def _verified_artifact_contents(artifact: dict[str, Any], target: Path) -> list[Path]:
    """Verify every sealed byte stream before an exact two-file validation."""
    if artifact.get("format_version") != 2 or len(artifact.get("effects", [])) != 2:
        raise PromotionError("Invalid multi-file artifact")
    if _self_development_target(target) != artifact.get("self_development", False):
        raise PromotionError("Self-development target identity changed")
    _require_separate_runtime(target)
    directory = _store_root_for_target(target) / artifact["id"]
    contents = []
    for index, effect in enumerate(artifact["effects"]):
        content = directory / f"content-{index}.bin"
        if content.is_symlink() or not content.is_file() or _file_digest(content) != effect["content_sha256"]:
            raise PromotionError("Sealed multi-file content is missing or altered")
        if effect["effect"] == "write":
            backup = directory / f"preimage-{index}.bin"
            if backup.is_symlink() or not backup.is_file() or _file_digest(backup) != effect["preimage_sha256"]:
                raise PromotionError("Sealed multi-file preimage is missing or altered")
        contents.append(content)
    return contents


async def validate_private_artifact(session_id: str, reference: dict[str, str], command: str,
                                    reviewer) -> dict[str, Any]:
    """Run an approved command against the exact sealed candidate, never the target."""
    from core.database import MobsPromotion, SessionLocal
    from src.mobs_mandate_builder import (load_proposal, load_authority_review,
                                           validate_execution_review, MandateProposalError)
    from src.mobs_institutional_boot import institutional_boot, capture_repository
    from src.mobs_reviewer_authorization import authorize_reviewer
    from src.windows_native_execution import inventory

    db = SessionLocal()
    row = None
    try:
        row = db.query(MobsPromotion).filter(MobsPromotion.id == reference.get("promotion_id")).first()
        if row is None or row.session_id != session_id:
            raise PromotionError("Stale or unknown promotion")
        if row.artifact_digest != reference.get("promotion_digest"):
            raise PromotionError("Stale or unknown promotion")
        if row.status == "promotion_applying":
            _record_outcome(db, row, "promotion_interrupted_or_uncertain", "application_interrupted")
            raise PromotionError("Promotion application was interrupted and cannot be retried")
        if row.status not in {"human_approval_required", "promotion_preauthorized"}:
            raise PromotionError("Promotion is no longer pending")
        artifact = _load_artifact(row)
        _assert_target_not_quarantined(db, _target_from_binding(artifact), exclude_id=row.id)
        multi = artifact.get("format_version") == 2
        if not artifact.get("self_development") and not multi:
            raise PromotionError("Private artifact validation is reserved for self-development")
        try:
            proposal = load_proposal(session_id)
        except MandateProposalError as exc:
            _record_outcome(db, row, "promotion_blocked", "mandate_or_operational_profile_changed")
            raise PromotionError("Promotion mandate or Operational Authority Profile changed") from exc
        if (not proposal or proposal.get("proposal_id") != artifact["proposal_id"]
                or proposal.get("proposal_digest") != artifact["proposal_digest"]):
            raise PromotionError("Promotion mandate has been replaced")
        preauthorized = row.status == "promotion_preauthorized"
        review = load_authority_review(artifact["authority_snapshot"],
                                       None if preauthorized else reviewer.username)
        if review is None:
            raise PromotionError("Institutional review authorization changed")
        try:
            validate_execution_review(proposal, review)
        except MandateProposalError as exc:
            raise PromotionError("Institutional review authorization changed") from exc
        current_auth = (review["authorization"] if preauthorized
                        else authorize_reviewer(proposal, reviewer))
        if current_auth != artifact["review_authorization"]:
            raise PromotionError("Institutional review authorization changed")
        if proposal.get("operational_authority_profile") != artifact["operational_policy"] or _policy() != artifact["operational_policy"]:
            raise PromotionError("Operational Authority Profile changed")
        candidate = {**proposal, "authority_review": "consistent", "review_record": review,
                     "_promotion_session_id": session_id}
        context = institutional_boot(candidate, candidate["target"]["path"])
        target = Path(context.target["path"]).resolve(strict=True)
        _require_separate_runtime(target)
        if (capture_repository(str(target)) != artifact["target_baseline"]
                or _inventory_digest_proxy(inventory(target, include_git=True)) != artifact["target_inventory_sha256"]):
            raise PromotionError("Target baseline drift blocks artifact validation")
        if multi:
            _verified_artifact_contents(artifact, target)
        else:
            _verified_artifact_content(artifact, target)
        pending = context.authorize_tool("bash", command)
        if pending is None or pending.boundary_policy is None:
            raise PromotionError("Validation command lacks a governed execution policy")
        policy = replace(pending.boundary_policy, promotion_binding=None, validation_artifact=artifact)
        result = await policy.execute()
        context.complete_command(replace(pending, boundary_policy=policy), result)
        if result.get("exit_code") != 0:
            raise PromotionError("Private validation command did not succeed")
        evidence = result.get("trusted_execution") or {}
        if (evidence.get("validated_artifact_digest") != artifact["artifact_digest"]
                or evidence.get("target_before_sha256") != artifact["target_inventory_sha256"]
                or evidence.get("target_after_sha256") != artifact["target_inventory_sha256"]
                or evidence.get("timed_out")):
            raise PromotionError("Private validation evidence does not identify the sealed artifact")
        if _inventory_digest_proxy(inventory(target, include_git=True)) != artifact["target_inventory_sha256"]:
            raise PromotionError("Target drift during private validation")
        db.rollback()
        _lock_promotion_transition(db)
        row = db.get(MobsPromotion, artifact["id"])
        if row.status != ("promotion_preauthorized" if preauthorized else "human_approval_required"):
            raise PromotionError("Promotion is no longer pending")
        _assert_target_not_quarantined(db, target, exclude_id=row.id)
        receipt = {"artifact_digest": artifact["artifact_digest"],
                   "proposal_digest": artifact["proposal_digest"],
                   "authority_snapshot": artifact["authority_snapshot"],
                   "target_baseline": artifact["target_baseline"],
                   "target_inventory_sha256": artifact["target_inventory_sha256"],
                   "command": pending.command, "exit_code": result["exit_code"],
                   "boundary": evidence}
        row.outcome_json = json.dumps({"status": row.status, "validation": receipt}, sort_keys=True)
        db.commit()
        return {"promotion_id": artifact["id"], "artifact_digest": artifact["artifact_digest"],
                "status": ("validated_preauthorized" if preauthorized else "validated_pending_human_approval"),
                "validation": receipt}
    except Exception as exc:
        db.rollback()
        if row is not None and row.status in {"human_approval_required", "promotion_preauthorized"}:
            # A failed validation cannot be mistaken for a prior successful one.
            row.outcome_json = json.dumps({"status": row.status, "validation_error": type(exc).__name__}, sort_keys=True)
            db.commit()
        raise
    finally:
        db.close()


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
        if row.status == "promotion_applying":
            _record_outcome(db, row, "promotion_interrupted_or_uncertain", "application_interrupted")
            raise PromotionError("Promotion application was interrupted and cannot be retried")
        if row.status not in {"human_approval_required", "promotion_preauthorized"}:
            raise PromotionError("Promotion is no longer pending")
        artifact = _load_artifact(row)
        _assert_target_not_quarantined(db, _target_from_binding(artifact), exclude_id=row.id)
        preauthorized = row.status == "promotion_preauthorized"
        if preauthorized and (not artifact.get("self_development")
                              or artifact["operational_policy"].get("self_development_result") != "preauthorized"):
            raise PromotionError("Operational preauthorization is invalid")
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
        review = load_authority_review(artifact["authority_snapshot"],
                                       None if preauthorized else reviewer.username)
        if review is None:
            raise PromotionError("No valid institutional review exists for this snapshot")
        try:
            validate_execution_review(proposal, review)
        except Exception as exc:
            raise PromotionError("Institutional review authorization changed") from exc
        current_auth = (review["authorization"] if preauthorized
                        else authorize_reviewer(proposal, reviewer))
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
        multi = artifact.get("format_version") == 2
        if multi:
            _verified_artifact_contents(artifact, target)
        else:
            content = _verified_artifact_content(artifact, target)
        if capture_repository(str(target)) != artifact["target_baseline"]:
            _record_outcome(db, row, "promotion_blocked", "target_baseline_drift")
            raise PromotionError("Target repository baseline drift blocks promotion")
        from src.windows_native_execution import inventory, _reparse
        initial_inventory = inventory(target, include_git=True)
        if _inventory_digest_proxy(initial_inventory) != artifact["target_inventory_sha256"]:
            _record_outcome(db, row, "promotion_blocked", "target_inventory_drift")
            raise PromotionError("Target workspace drift blocks promotion")
        validation = (json.loads(row.outcome_json or "{}") or {}).get("validation")
        if multi:
            return _apply_multi_file(db, row, artifact, context, target, initial_inventory,
                                     validation, reviewer, current_auth)
        if artifact.get("self_development"):
            if (not isinstance(validation, dict)
                    or validation.get("artifact_digest") != artifact["artifact_digest"]
                    or validation.get("proposal_digest") != artifact["proposal_digest"]
                    or validation.get("authority_snapshot") != artifact["authority_snapshot"]
                    or validation.get("target_baseline") != artifact["target_baseline"]
                    or validation.get("target_inventory_sha256") != artifact["target_inventory_sha256"]
                    or validation.get("exit_code") != 0
                    or validation.get("boundary", {}).get("validated_artifact_digest") != artifact["artifact_digest"]
                    or validation.get("boundary", {}).get("target_before_sha256") != artifact["target_inventory_sha256"]
                    or validation.get("boundary", {}).get("target_after_sha256") != artifact["target_inventory_sha256"]):
                raise PromotionError("Exact sealed artifact has no valid private validation")
            if artifact["effect"] == "write":
                backup = _store_root_for_target(target) / artifact["id"] / "preimage.bin"
                if backup.is_symlink() or not backup.is_file() or _file_digest(backup) != artifact["preimage_sha256"]:
                    raise PromotionError("Self-development preimage evidence is missing or altered")
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
        db.rollback()
        _lock_promotion_transition(db)
        row = db.get(MobsPromotion, artifact["id"])
        if row.status not in {"human_approval_required", "promotion_preauthorized"}:
            raise PromotionError("Promotion is no longer pending")
        _assert_target_not_quarantined(db, target, exclude_id=row.id)
        if inventory(target, include_git=True) != pre_apply_inventory:
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
            if observed_pre_apply != pre_apply_inventory:
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
        row.approval_json = json.dumps(
            ({"type": "operational_preauthorization", "policy": artifact["operational_policy"],
              "artifact_digest": artifact["artifact_digest"]} if preauthorized else
             {"type": "human_approval", "reviewer": reviewer.username, "authorization": current_auth,
              "artifact_digest": artifact["artifact_digest"]}), sort_keys=True)
        row.outcome_json = json.dumps({"status": row.status, "reason": "exact_post_apply_inventory_verified",
                                       "authorization_type": ("operational_preauthorization" if preauthorized
                                                              else "human_approval"),
                                       "validation": validation,
                                       "preimage_sha256": artifact["preimage_sha256"],
                                       "post_apply_inventory_sha256": _inventory_digest_proxy(post_apply_inventory)}, sort_keys=True)
        db.commit()
        return promotion_summary(artifact, row.status)
    except PromotionError as exc:
        db.rollback()
        if row is not None and application_started and row.status != "promotion_interrupted_or_uncertain":
            _record_outcome(db, row, "promotion_interrupted_or_uncertain", "application_validation_or_staging_failed",
                            error=type(exc).__name__)
        elif row is not None and row.status in {"human_approval_required", "promotion_preauthorized"}:
            _record_outcome(db, row, "promotion_blocked", "pre_apply_validation_failed",
                            error=type(exc).__name__)
        raise
    except Exception as exc:
        db.rollback()
        if row is not None and row.status not in {"promotion_blocked", "promotion_interrupted_or_uncertain"}:
            try:
                status = "promotion_interrupted_or_uncertain" if application_started or row.status == "promotion_applying" else "promotion_blocked"
                reason = "application_exception" if application_started else "pre_apply_exception"
                _record_outcome(db, row, status, reason, error=type(exc).__name__)
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()


def _apply_multi_file(db, row, artifact: dict[str, Any], context, target: Path,
                      initial_inventory: dict[str, str], validation: dict | None,
                      reviewer, current_auth: dict) -> dict[str, Any]:
    """Apply the sealed pair sequentially; verify or conservatively recover."""
    from core.database import MobsPromotion
    from src.mobs_institutional_boot import _path_is_allowed, _portable_path
    from src.windows_native_execution import inventory, _reparse

    effects = artifact.get("effects")
    if (artifact.get("format_version") != 2 or not isinstance(effects, list) or len(effects) != 2
            or effects != sorted(effects, key=lambda item: item["path"].casefold())):
        raise PromotionError("Invalid two-file artifact manifest")
    paths = [_portable_path(effect["path"], "promotion path") for effect in effects]
    if len({path.casefold() for path in paths}) != 2:
        raise PromotionError("Duplicate promotion paths")
    if (not isinstance(validation, dict) or validation.get("artifact_digest") != artifact["artifact_digest"]
            or validation.get("proposal_digest") != artifact["proposal_digest"]
            or validation.get("authority_snapshot") != artifact["authority_snapshot"]
            or validation.get("target_baseline") != artifact["target_baseline"]
            or validation.get("target_inventory_sha256") != artifact["target_inventory_sha256"]
            or validation.get("exit_code") != 0
            or validation.get("boundary", {}).get("validated_artifact_digest") != artifact["artifact_digest"]
            or validation.get("boundary", {}).get("target_before_sha256") != artifact["target_inventory_sha256"]
            or validation.get("boundary", {}).get("target_after_sha256") != artifact["target_inventory_sha256"]):
        raise PromotionError("Exact two-file artifact has no valid private validation")
    contents = _verified_artifact_contents(artifact, target)
    prepared = []
    for effect, relative, content in zip(effects, paths, contents):
        if effect["effect"] not in {"create", "write"}:
            raise PromotionError("Multi-file promotion permits only create or write")
        allowed = (context.execution.allowed_create_paths if effect["effect"] == "create"
                   else context.execution.allowed_write_paths)
        if not _path_is_allowed(relative, allowed):
            raise PromotionError("Multi-file path is outside mandate")
        destination = target / relative
        parent = destination.parent.resolve(strict=True)
        if not parent.is_relative_to(target) or _reparse(parent) or destination.is_symlink():
            raise PromotionError("Multi-file path cannot be physically confined")
        if effect["effect"] == "create":
            if destination.exists() or relative in initial_inventory or effect.get("preimage_sha256") is not None:
                raise PromotionError("Create destination or preimage is incompatible")
        elif (not destination.is_file() or _reparse(destination)
              or initial_inventory.get(relative) != effect.get("preimage_sha256")
              or _file_digest(destination) != effect["preimage_sha256"]):
            raise PromotionError("Write preimage drift blocks multi-file promotion")
        prepared.append((effect, relative, destination, parent, content))
    pre_apply = inventory(target, include_git=True)
    if pre_apply != initial_inventory:
        raise PromotionError("Target drift immediately before multi-file promotion")
    db.rollback()
    _lock_promotion_transition(db)
    row = db.get(MobsPromotion, artifact["id"])
    if row.status != "human_approval_required":
        raise PromotionError("Promotion is no longer pending")
    _assert_target_not_quarantined(db, target, exclude_id=row.id)
    if inventory(target, include_git=True) != pre_apply:
        raise PromotionError("Target drift immediately before multi-file promotion")
    expected_final = dict(pre_apply)
    for effect, relative, *_ in prepared:
        expected_final[relative] = effect["content_sha256"]
    # Claim the exact pending row before the first target-local staging file.
    claimed = (db.query(MobsPromotion)
               .filter(MobsPromotion.id == row.id, MobsPromotion.status == "human_approval_required")
               .update({MobsPromotion.status: "promotion_applying",
                        MobsPromotion.outcome_json: json.dumps({
                            "status": "promotion_applying", "reason": "real_mutation_started",
                            "pre_apply_inventory_sha256": _inventory_digest_proxy(pre_apply),
                            "published": []}, sort_keys=True)}, synchronize_session=False))
    db.commit()
    if claimed != 1:
        raise PromotionError("Promotion is no longer pending")
    db.refresh(row)
    staged: dict[str, str] = {}
    published: list[str] = []
    published_identity: dict[str, tuple[int, int]] = {}
    try:
        for effect, relative, _destination, parent, content in prepared:
            fd, name = tempfile.mkstemp(prefix=".odysseus-promote-", dir=parent)
            staged[relative] = name
            with os.fdopen(fd, "wb") as output, content.open("rb") as input_stream:
                for block in iter(lambda: input_stream.read(1024 * 1024), b""):
                    output.write(block)
                output.flush(); os.fsync(output.fileno())
            if _file_digest(Path(name)) != effect["content_sha256"]:
                raise PromotionError("Prepared multi-file content failed verification")
        expected_step = dict(pre_apply)
        for effect, relative, destination, _parent, _content in prepared:
            if destination.parent.resolve(strict=True) != _parent or destination.is_symlink():
                raise PromotionError("Promotion path changed during application")
            observed = inventory(target, include_git=True)
            stage_relatives = {Path(name).resolve().relative_to(target).as_posix()
                               for name in staged.values() if os.path.exists(name)}
            actual_step = {path: digest for path, digest in observed.items() if path not in stage_relatives}
            if (actual_step != expected_step or
                    any(observed.get(Path(name).resolve().relative_to(target).as_posix()) != item["content_sha256"]
                        for item, name in ((entry, staged[entry["path"]]) for entry in effects)
                        if os.path.exists(name))):
                raise PromotionError("Target drift during multi-file application")
            stage_stat = Path(staged[relative]).stat()
            if effect["effect"] == "create":
                os.link(staged[relative], destination)
            else:
                os.replace(staged[relative], destination)
            published.append(relative)
            published_identity[relative] = (stage_stat.st_dev, stage_stat.st_ino)
            expected_step[relative] = effect["content_sha256"]
            _record_outcome(db, row, "promotion_applying", "effect_published",
                            pre_apply_inventory_sha256=_inventory_digest_proxy(pre_apply),
                            published=list(published))
        for name in staged.values():
            if os.path.exists(name):
                os.unlink(name)
        staged.clear()
        post = inventory(target, include_git=True)
        if post != expected_final:
            raise PromotionError("Multi-file post-apply inventory differs from exact artifact")
        row.approval_json = json.dumps({"type": "human_approval", "reviewer": reviewer.username,
                                        "authorization": current_auth,
                                        "artifact_digest": artifact["artifact_digest"]}, sort_keys=True)
        _record_outcome(db, row, "promotion_applied_verified", "exact_two_file_inventory_verified",
                        validation=validation,
                        post_apply_inventory_sha256=_inventory_digest_proxy(post),
                        published=list(published))
        return promotion_summary(artifact, row.status)
    except Exception:
        # A hash mismatch means another actor may own the path. Never overwrite it.
        recovery_safe = True
        for name in staged.values():
            if os.path.exists(name):
                try:
                    os.unlink(name)
                except OSError:
                    recovery_safe = False
        for effect, relative, destination, parent, _content in reversed(prepared):
            if relative not in published:
                continue
            try:
                current_stat = destination.stat() if destination.is_file() else None
                if (current_stat is None or _reparse(destination)
                        or (current_stat.st_dev, current_stat.st_ino) != published_identity.get(relative)
                        or _file_digest(destination) != effect["content_sha256"]):
                    recovery_safe = False
                    continue
                if effect["effect"] == "create":
                    os.unlink(destination)
                else:
                    backup = _store_root_for_target(target) / artifact["id"] / f"preimage-{paths.index(relative)}.bin"
                    if backup.is_symlink() or _file_digest(backup) != effect["preimage_sha256"]:
                        recovery_safe = False
                        continue
                    fd, restore = tempfile.mkstemp(prefix=".odysseus-promote-", dir=parent)
                    try:
                        with os.fdopen(fd, "wb") as output, backup.open("rb") as input_stream:
                            for block in iter(lambda: input_stream.read(1024 * 1024), b""):
                                output.write(block)
                            output.flush(); os.fsync(output.fileno())
                        if _file_digest(Path(restore)) != effect["preimage_sha256"]:
                            raise PromotionError("Preimage restoration failed verification")
                        os.replace(restore, destination)
                    finally:
                        if os.path.exists(restore): os.unlink(restore)
            except (OSError, PromotionError):
                recovery_safe = False
        try:
            recovered = recovery_safe and inventory(target, include_git=True) == pre_apply
        except Exception:
            recovered = False
        _record_outcome(db, row, "promotion_blocked" if recovered else "promotion_interrupted_or_uncertain",
                        "application_failed_rolled_back" if recovered else "application_partial_or_drift",
                        published=list(published),
                        pre_apply_inventory_sha256=_inventory_digest_proxy(pre_apply))
        raise


def _inventory_digest_proxy(entries: dict[str, str]) -> str:
    h = hashlib.sha256()
    for path, value in sorted(entries.items()):
        h.update(path.encode("utf-8", "surrogateescape")); h.update(b"\0"); h.update(value.encode()); h.update(b"\0")
    return h.hexdigest()
