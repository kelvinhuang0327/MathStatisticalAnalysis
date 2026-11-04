"""Pure schema and owner-binding tests for versioned lineage successors."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from multiprocessing import get_context
from pathlib import Path
from threading import Barrier
from typing import cast
from uuid import uuid4

import pytest
from tools import b649_production_cutover as cutover
from tools import b649_protected_cutover as protected

# pyright: reportPrivateUsage=false

NOW = datetime.now(UTC).replace(microsecond=0)


@pytest.mark.parametrize(
    "protected_path",
    [
        Path(
            "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
            "B649_OPERATIONAL_PREDICTION_LOOP_R1/scheduler/b649-control-owner-reservation.json"
        ),
        Path(
            "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
            "B649_PRODUCTION_56c9715ca60bb9af3afe3b5faae83b0dc0471d8f/tools/example.py"
        ),
        Path("/Users/kelvin/Library/LaunchAgents/com.lottolab.b649-goalc-r1.plist"),
        Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/data/databases/example.db"),
    ],
)
def test_production_path_guard_rejects_resolution(protected_path: Path) -> None:
    with pytest.raises(RuntimeError, match="forbidden production-path access"):
        protected_path.resolve(strict=False)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _write_sealed_json(path: Path, value: dict[str, object]) -> tuple[bytes, str, str]:
    unsigned = dict(value)
    record_sha256 = protected.digest(unsigned)
    raw = (protected.canonical({**unsigned, "record_sha256": record_sha256}) + "\n").encode()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(0o600)
    return raw, hashlib.sha256(raw).hexdigest(), record_sha256


def _target(path: Path, head: str, tree: str) -> dict[str, str]:
    return {
        "source_worktree": str(path),
        "head": head,
        "tree": tree,
        "durable_ref": f"refs/heads/runtime/b649/{head}",
    }


def _successor_record(tmp_path: Path, *, phase: str = "PREPARED") -> dict[str, object]:
    control = {
        "head": "1" * 40,
        "tree": "2" * 40,
        "worktree": str(tmp_path / "successor-control"),
    }
    original_control = {
        "head": cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_CONTROL_HEAD,
        "tree": cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_CONTROL_TREE,
        "worktree": str(tmp_path / "original-control"),
    }
    source_old = _target(tmp_path / "source-old", cutover.V5_SOURCE_HEAD, cutover.V5_SOURCE_TREE)
    predecessor_target = dict(cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_TARGET)
    target = _target(tmp_path / "new-target", "9" * 40, "a" * 40)
    owner_path = tmp_path / "scheduler" / cutover.CONTROL_OWNER_NAME
    retirement_path = tmp_path / "scheduler" / cutover.FAILED_TERMINAL_RETIREMENT_V2_NAME
    owner_sha = _sha("owner-bytes")
    retirement_sha = _sha("retirement-bytes")
    pending_reservation = cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_RESERVATION_ID
    pending_operation = cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_OPERATION_ID
    auth_sha = _sha("old authorization")
    transition_id = str(uuid4())
    pending_archive_path = (
        tmp_path
        / "scheduler"
        / "b649-lineage-successor-archives"
        / transition_id
        / f"pending_owner.{owner_sha}.{transition_id}.json"
    )

    ancestor_ids = sorted(cutover.LINEAGE_SUCCESSOR_ANCESTOR_NODE_IDS)
    byte_hashes = [_sha(f"ancestor-bytes-{index}") for index in range(len(ancestor_ids))]
    record_hashes = [_sha(f"ancestor-record-{index}") for index in range(len(ancestor_ids))]
    ancestors: list[dict[str, object]] = []
    ancestor_by_id: dict[str, dict[str, object]] = {}
    for index, node_id in enumerate(ancestor_ids):
        ancestor: dict[str, object] = {
            "node_id": node_id,
            "path": str(
                pending_archive_path
                if node_id == "current-owner-2899"
                else tmp_path / "history" / f"{node_id}.json"
            ),
            "bytes_sha256": (
                owner_sha if node_id == "current-owner-2899" else byte_hashes[index]
            ),
            "record_sha256": (
                _sha("owner seal")
                if node_id == "current-owner-2899"
                else record_hashes[index]
            ),
            "schema": "fixture-evidence-v1",
            "identity": {
                "reservation_id": (
                    pending_reservation if node_id == "current-owner-2899" else str(uuid4())
                ),
                "operation_id": (
                    pending_operation
                    if node_id == "current-owner-2899"
                    else _sha(f"operation-{index}")[:32]
                ),
            },
            "previous_evidence_sha256": [],
        }
        ancestors.append(ancestor)
        ancestor_by_id[node_id] = ancestor
    for node_id, parent_ids in cutover.LINEAGE_SUCCESSOR_ANCESTOR_PARENTS.items():
        ancestor = ancestor_by_id[node_id]
        ancestor["previous_evidence_sha256"] = [
            cast(str, ancestor_by_id[parent]["bytes_sha256"]) for parent in parent_ids
        ]

    known_gaps = [
        {"id": gap_id, "status": "UNRESOLVED", "source_document": "L1 gap register"}
        for gap_id in sorted(cutover.LINEAGE_SUCCESSOR_GAP_IDS)
    ]
    archives = [
        {
            "kind": "pending_owner",
            "source_path": str(owner_path),
            "archive_path": str(pending_archive_path),
            "source_sha256": owner_sha,
            "source_record_sha256": _sha("owner seal"),
            "archive_sha256": owner_sha,
            "readback_status": "VERIFIED",
            "source_state": "PRESENT",
        },
        {
            "kind": "retirement",
            "source_path": str(retirement_path),
            "archive_path": str(
                tmp_path / "scheduler" / f"retirement.{retirement_sha}.archive.json"
            ),
            "source_sha256": retirement_sha,
            "source_record_sha256": _sha("retirement seal"),
            "archive_sha256": retirement_sha,
            "readback_status": "VERIFIED",
            "source_state": "PRESENT",
        },
    ]
    evidence: dict[str, object] = {
        "schema": cutover.LINEAGE_SUCCESSOR_SCHEMA,
        "transition_id": transition_id,
        "phase": phase,
        "control_identity": control,
        "original_control_identity": original_control,
        "source_old": source_old,
        "predecessor_target": predecessor_target,
        "target": target,
        "plan": {
            "path": str(tmp_path / "plan.json"),
            "sha256": _sha("plan bytes"),
            "digest": _sha("plan digest"),
            "prestate_digest": _sha("prestate digest"),
        },
        "claim_root": str(tmp_path / "claims"),
        "pending_owner_snapshot": {
            "path": str(owner_path),
            "bytes_sha256": owner_sha,
            "record_sha256": _sha("owner seal"),
            "reservation_id": pending_reservation,
            "operation_id": pending_operation,
            "phase": "AUTHORIZED_PENDING",
            "action": "apply",
            "target": predecessor_target,
            "control_identity": original_control,
            "authorization_sha256": auth_sha,
            "predecessor_release_evidence_sha256": (
                cutover.LINEAGE_SUCCESSOR_REVIEWED_PREDECESSOR_EVIDENCE_SHA256
            ),
            "mutation_started": False,
        },
        "released_owner": None,
        "retirement": {
            "path": str(retirement_path),
            "bytes_sha256": retirement_sha,
            "record_sha256": _sha("retirement seal"),
            "schema": cutover.FAILED_TERMINAL_RETIREMENT_V2_SCHEMA,
            "candidate": {
                "reservation_id": cutover.RELEASED_INTERMEDIATE_RESERVATION_ID,
                "operation_id": cutover.RELEASED_INTERMEDIATE_OPERATION_ID,
                "target": _target(
                    Path(cutover.RELEASED_INTERMEDIATE_TARGET_WORKTREE),
                    cutover.V7_SOURCE_HEAD,
                    cutover.V7_SOURCE_TREE,
                ),
                "plan_sha256": cutover.V7_CANDIDATE_PLAN_SHA256,
                "claim_root": None,
            },
        },
        "ancestor_evidence": ancestors,
        "known_gaps": known_gaps,
        "archives": archives,
        "owner_approval": {},
        "transition_sha256": "",
        "record_sha256": "",
    }
    transition_digest = cutover._sha256_json(cutover._lineage_successor_core(evidence))
    approval: dict[str, object] = {
        "signer_identity": "test-owner",
        "signature": "test-signature",
        "scope": "B649_LINEAGE_SUCCESSOR_RESERVATION",
        "target": target,
        "reservation_id": "22222222-2222-4222-8222-222222222222",
        "operation_id": _sha("new operation"),
        "transition_digest": transition_digest,
        "revoked_authorization_sha256": auth_sha,
        "known_gaps_decision": "PRESERVE_UNRESOLVED_AND_CONTINUE",
        "owner_confirmed_gaps": sorted(cutover.LINEAGE_SUCCESSOR_GAP_IDS),
        "retention_policy": cutover.LINEAGE_SUCCESSOR_RETAIN_POLICY,
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(minutes=2)).isoformat(),
        "nonce": str(uuid4()),
    }
    approval["confirmation_digest"] = cutover._sha256_json(
        {key: value for key, value in approval.items() if key != "signature"}
    )
    evidence["owner_approval"] = approval
    evidence["transition_sha256"] = transition_digest
    evidence["record_sha256"] = cutover._sha256_json(
        {key: value for key, value in evidence.items() if key != "record_sha256"}
    )
    if phase not in {"PREPARED", "CANCELLED"}:
        released_owner = {
            "path": str(owner_path),
            "bytes_sha256": _sha("released owner bytes"),
            "record_sha256": _sha("released owner seal"),
            "reservation_id": pending_reservation,
            "operation_id": pending_operation,
            "phase": "RELEASED",
            "release_kind": cutover.EXPLICIT_ABANDON_RELEASE_KIND,
            "authorization_sha256": auth_sha,
            "control_identity": original_control,
            "mutation_started": False,
        }
        evidence["released_owner"] = released_owner
        archives[0]["source_state"] = "CHANGED"
        if phase in {
            "AUTHORIZED_PENDING",
            "APPLY_STARTED",
            "RELEASED_SUCCESS",
            "RECOVERY_REQUIRED",
        }:
            archives[1]["source_state"] = "ABSENT"
        archives.append(
            {
                "kind": "released_owner",
                "source_path": str(owner_path),
                "archive_path": str(tmp_path / "scheduler" / "released-owner.archive.json"),
                "source_sha256": cast(str, released_owner["bytes_sha256"]),
                "source_record_sha256": cast(str, released_owner["record_sha256"]),
                "archive_sha256": cast(str, released_owner["bytes_sha256"]),
                "readback_status": "VERIFIED",
                "source_state": (
                    "CHANGED"
                    if phase
                    in {
                        "AUTHORIZED_PENDING",
                        "APPLY_STARTED",
                        "RELEASED_SUCCESS",
                        "RECOVERY_REQUIRED",
                    }
                    else "PRESENT"
                ),
            }
        )
        evidence["record_sha256"] = cutover._sha256_json(
            {key: value for key, value in evidence.items() if key != "record_sha256"}
        )
    return evidence


def _reseal(evidence: dict[str, object]) -> None:
    evidence["transition_sha256"] = cutover._sha256_json(cutover._lineage_successor_core(evidence))
    approval = cast(dict[str, object], evidence["owner_approval"])
    approval["transition_digest"] = evidence["transition_sha256"]
    approval["confirmation_digest"] = cutover._sha256_json(
        {
            key: value
            for key, value in approval.items()
            if key not in {"signature", "confirmation_digest"}
        }
    )
    evidence["record_sha256"] = cutover._sha256_json(
        {key: value for key, value in evidence.items() if key != "record_sha256"}
    )


def test_lineage_successor_record_validates_without_filesystem_access(tmp_path: Path) -> None:
    evidence = _successor_record(tmp_path)
    assert cutover._validate_lineage_successor_transition(
        evidence, now=NOW, expected_signer="test-owner"
    ) == evidence


def test_lineage_successor_signature_verification_requires_configured_verifier(
    tmp_path: Path,
) -> None:
    evidence = _successor_record(tmp_path)
    with pytest.raises(cutover.CutoverSafetyError, match="verifier is not configured"):
        cutover._validate_lineage_successor_transition(evidence, now=NOW, verify_signature=True)
    assert cutover._validate_lineage_successor_transition(
        evidence,
        now=NOW,
        expected_signer="test-owner",
        approval_verifier=lambda signer, digest, signature: (
            signer == "test-owner" and digest != "" and signature == "test-signature"
        ),
        verify_signature=True,
    ) == evidence


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_schema",
        "unknown_top_level_key",
        "missing_required_key",
        "unknown_phase",
        "transition_seal",
        "record_seal",
        "target",
        "plan_hash",
        "control_tree",
        "owner_authorization_sha",
        "retirement_sha",
        "ancestor_count",
        "ancestor_hash",
        "ancestor_identity",
        "ancestor_edge_count",
        "gap_missing",
        "gap_fabricated_as_resolved",
        "gap_extra",
        "gap_owner_confirmation",
        "retention_policy",
        "authorization_scope",
        "authorization_target",
        "authorization_nonce",
        "authorization_confirmation",
        "authorization_signature",
        "pending_mutation_started",
        "pending_phase",
        "archive_readback",
        "archive_sha",
        "source_and_target_same",
    ],
)
def test_lineage_successor_schema_rejects_each_mutated_binding(
    tmp_path: Path, mutation: str
) -> None:
    evidence = _successor_record(tmp_path)
    approval = cast(dict[str, object], evidence["owner_approval"])
    ancestors = cast(list[dict[str, object]], evidence["ancestor_evidence"])
    gaps = cast(list[dict[str, object]], evidence["known_gaps"])
    archives = cast(list[dict[str, object]], evidence["archives"])
    pending = cast(dict[str, object], evidence["pending_owner_snapshot"])
    target = cast(dict[str, str], evidence["target"])
    original_confirmation_digest = cast(dict[str, object], evidence["owner_approval"])[
        "confirmation_digest"
    ]
    if mutation == "unknown_schema":
        evidence["schema"] = "b649-lineage-successor-v2"
    elif mutation == "unknown_top_level_key":
        evidence["unreviewed"] = True
    elif mutation == "missing_required_key":
        del evidence["claim_root"]
    elif mutation == "unknown_phase":
        evidence["phase"] = "MAGIC_SUCCESS"
    elif mutation == "transition_seal":
        evidence["transition_sha256"] = "0" * 64
    elif mutation == "record_seal":
        evidence["record_sha256"] = "0" * 64
    elif mutation == "target":
        target["head"] = "f" * 40
    elif mutation == "plan_hash":
        cast(dict[str, object], evidence["plan"])["sha256"] = "0" * 64
    elif mutation == "control_tree":
        cast(dict[str, object], evidence["control_identity"])["tree"] = "0" * 40
    elif mutation == "owner_authorization_sha":
        pending["authorization_sha256"] = "0" * 64
    elif mutation == "retirement_sha":
        cast(dict[str, object], evidence["retirement"])["bytes_sha256"] = "0" * 64
    elif mutation == "ancestor_count":
        ancestors.pop()
    elif mutation == "ancestor_hash":
        ancestors[0]["bytes_sha256"] = "0" * 64
    elif mutation == "ancestor_identity":
        cast(dict[str, object], ancestors[0]["identity"])["unexpected"] = "value"
    elif mutation == "ancestor_edge_count":
        cast(list[str], ancestors[0]["previous_evidence_sha256"]).append("0" * 64)
    elif mutation == "gap_missing":
        gaps.pop()
    elif mutation == "gap_fabricated_as_resolved":
        gaps[0]["status"] = "RESOLVED"
    elif mutation == "gap_extra":
        gaps.append({"id": "new-gap", "status": "UNRESOLVED", "source_document": "L1"})
    elif mutation == "gap_owner_confirmation":
        approval["owner_confirmed_gaps"] = []
    elif mutation == "retention_policy":
        approval["retention_policy"] = "DELETE_AFTER_30_DAYS"
    elif mutation == "authorization_scope":
        approval["scope"] = "ALL_TARGETS"
    elif mutation == "authorization_target":
        approval["target"] = _target(tmp_path / "wrong", "d" * 40, "e" * 40)
    elif mutation == "authorization_nonce":
        approval["nonce"] = "replayed"
    elif mutation == "authorization_confirmation":
        approval["confirmation_digest"] = "0" * 64
    elif mutation == "authorization_signature":
        approval["signature"] = ""
    elif mutation == "pending_mutation_started":
        pending["mutation_started"] = True
    elif mutation == "pending_phase":
        pending["phase"] = "RELEASED"
    elif mutation == "archive_readback":
        archives[0]["readback_status"] = "UNKNOWN"
    elif mutation == "archive_sha":
        archives[0]["archive_sha256"] = "0" * 64
    elif mutation == "source_and_target_same":
        evidence["target"] = evidence["predecessor_target"]
    if mutation not in {"transition_seal", "record_seal", "authorization_confirmation"}:
        _reseal(evidence)
    with pytest.raises(cutover.CutoverSafetyError):
        cutover._validate_lineage_successor_transition(
            evidence,
            now=NOW,
            expected_signer="test-owner",
            approval_verifier=lambda signer, digest, signature: (
                signer == "test-owner"
                and digest == original_confirmation_digest
                and signature == "test-signature"
            ),
            verify_signature=True,
        )


def test_lineage_successor_rejects_expired_and_overlong_authorization(tmp_path: Path) -> None:
    expired = _successor_record(tmp_path)
    approval = cast(dict[str, object], expired["owner_approval"])
    approval["issued_at"] = (NOW - timedelta(minutes=2)).isoformat()
    approval["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
    _reseal(expired)
    with pytest.raises(cutover.CutoverSafetyError, match="expired or replayed"):
        cutover._validate_lineage_successor_transition(expired, now=NOW)

    overlong = _successor_record(tmp_path)
    long_approval = cast(dict[str, object], overlong["owner_approval"])
    long_approval["expires_at"] = (NOW + timedelta(minutes=6)).isoformat()
    _reseal(overlong)
    with pytest.raises(cutover.CutoverSafetyError, match="expired or replayed"):
        cutover._validate_lineage_successor_transition(overlong, now=NOW)


def test_lineage_successor_requires_explicit_gap_decision_after_owner_release(
    tmp_path: Path,
) -> None:
    evidence = _successor_record(tmp_path, phase="OLD_OWNER_RELEASED")
    approval = cast(dict[str, object], evidence["owner_approval"])
    approval["known_gaps_decision"] = "PENDING_OWNER_DECISION"
    approval["owner_confirmed_gaps"] = []
    _reseal(evidence)
    with pytest.raises(cutover.CutoverSafetyError, match="no explicit Owner decision"):
        cutover._validate_lineage_successor_transition(evidence, now=NOW)


def test_production_predecessor_validator_accepts_only_the_new_sealed_variant(
    tmp_path: Path,
) -> None:
    transition = _successor_record(tmp_path, phase="OLD_OWNER_RELEASED")
    owner = cast(dict[str, object], transition["owner_approval"])
    new_owner: cutover.Record = {
        "reservation_id": owner["reservation_id"],
        "operation_id": owner["operation_id"],
        "managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "target": transition["target"],
    }
    released = cast(dict[str, object], transition["released_owner"])
    unsigned: cutover.Record = {
        "schema": cutover.PROTECTED_PREDECESSOR_RELEASE_SCHEMA,
        "prior_reservation_id": released["reservation_id"],
        "prior_operation_id": released["operation_id"],
        "prior_authorization_sha256": released["authorization_sha256"],
        "prior_release_evidence": {
            "kind": cutover.EXPLICIT_ABANDON_RELEASE_KIND,
            "verified": True,
        },
        "prior_protected_receipt_sha256": cutover.V5_PROTECTED_RECEIPT_SHA256,
        "prior_managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "new_reservation_id": new_owner["reservation_id"],
        "new_operation_id": new_owner["operation_id"],
        "lineage_successor_transition": transition,
    }
    proof = {**unsigned, "evidence_sha256": cutover._sha256_json(unsigned)}
    assert cutover._validate_predecessor_release_evidence(proof, new_owner) == proof

    wrong_owner = {**new_owner, "target": _target(tmp_path / "wrong", "c" * 40, "d" * 40)}
    with pytest.raises(cutover.CutoverSafetyError):
        cutover._validate_predecessor_release_evidence(proof, wrong_owner)


def _lineage_owner_cas_fixture(
    tmp_path: Path,
) -> tuple[cutover.CutoverConfig, cutover.Record, cutover.Record, Path, cutover.Record]:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    claim_root = tmp_path / "claims"
    claim_root.mkdir(mode=0o700)
    target = _target(tmp_path / "new-target", "9" * 40, "a" * 40)
    config = cutover.CutoverConfig(
        launch_domain=f"gui/{os.getuid() + 1000000}",
        source_worktree=Path(target["source_worktree"]),
        plist_path=tmp_path / "LaunchAgents" / f"{cutover.LABEL}.plist",
        canonical_repository=tmp_path / "repo",
        operation_root=tmp_path / "operation",
        scheduler_root=scheduler_root,
        data_root=tmp_path / "data",
        database=tmp_path / "data" / "lottolab.db",
        announcement=tmp_path / "data" / "announcement.json",
        health_path=scheduler_root / "health.json",
        stdout_path=scheduler_root / "stdout.log",
        stderr_path=scheduler_root / "stderr.log",
        primary_lock_path=scheduler_root / "primary.lock",
        shadow_lock_path=scheduler_root / "shadow.lock",
        cutover_lock_path=scheduler_root / "cutover.lock",
        receipt_path=scheduler_root / "managed-receipt.json",
        expected_head=target["head"],
        expected_tree=target["tree"],
        durable_ref=target["durable_ref"],
    )
    transition = _successor_record(tmp_path, phase="OLD_OWNER_RELEASED")
    current_control = cast(dict[str, str], transition["control_identity"])
    original_control = cast(
        dict[str, str], transition["original_control_identity"]
    )
    predecessor_target = cast(
        dict[str, str], transition["predecessor_target"]
    )
    prior_reservation = cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_RESERVATION_ID
    prior_operation = cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_OPERATION_ID
    managed_sha = _sha("owner managed receipt")
    authorization: cutover.Record = {
        "reservation_id": prior_reservation,
        "operation_id": prior_operation,
        "managed_receipt_sha256": managed_sha,
        "control_head": original_control["head"],
        "control_tree": original_control["tree"],
        "action": "apply",
        "target": predecessor_target,
    }
    prior_owner = cutover._seal_control_owner(
        {
            "schema": cutover.CONTROL_OWNER_SCHEMA,
            "reservation_id": prior_reservation,
            "owner_kind": "protected",
            "owner_pid": os.getpid(),
            "action": "apply",
            "target": predecessor_target,
            "control_head": original_control["head"],
            "control_tree": original_control["tree"],
            "operation_id": prior_operation,
            "managed_receipt_sha256": managed_sha,
            "phase": "RELEASED",
            "created_at": NOW.isoformat(),
            "updated_at": NOW.isoformat(),
            "authorization": authorization,
            "mutation_started": False,
            "terminal": None,
            "release_evidence": {
                "kind": cutover.EXPLICIT_ABANDON_RELEASE_KIND,
                "verified": True,
            },
        }
    )
    owner_path = config.receipt_path.with_name(cutover.CONTROL_OWNER_NAME)
    cutover.write_control_json(owner_path, prior_owner, expected=None)
    stored_owner = cutover.inspect_control_owner(config)
    assert stored_owner is not None

    released = cast(dict[str, object], transition["released_owner"])
    archives = cast(list[dict[str, object]], transition["archives"])
    auth_sha = cutover._sha256_json(authorization)
    owner_identity = cutover._read_control_owner(config)
    assert owner_identity is not None
    owner_record, file_identity = owner_identity
    released["bytes_sha256"] = file_identity.sha256
    released["record_sha256"] = cast(str, owner_record["record_sha256"])
    released["authorization_sha256"] = auth_sha
    cast(dict[str, object], transition["pending_owner_snapshot"])[
        "authorization_sha256"
    ] = auth_sha
    cast(dict[str, object], transition["owner_approval"])[
        "revoked_authorization_sha256"
    ] = auth_sha
    archives[2]["source_sha256"] = file_identity.sha256
    archives[2]["source_record_sha256"] = cast(str, owner_record["record_sha256"])
    archives[2]["archive_sha256"] = file_identity.sha256
    _reseal(transition)

    previous_protected_sha = _sha("prior protected receipt")
    unsigned_proof: cutover.Record = {
        "schema": cutover.PROTECTED_PREDECESSOR_RELEASE_SCHEMA,
        "prior_reservation_id": prior_reservation,
        "prior_operation_id": prior_operation,
        "prior_authorization_sha256": auth_sha,
        "prior_release_evidence": prior_owner["release_evidence"],
        "prior_protected_receipt_sha256": previous_protected_sha,
        "prior_managed_receipt_sha256": managed_sha,
        "new_reservation_id": cast(
            dict[str, object], transition["owner_approval"]
        )["reservation_id"],
        "new_operation_id": cast(
            dict[str, object], transition["owner_approval"]
        )["operation_id"],
        "lineage_successor_transition": transition,
    }
    proof = {**unsigned_proof, "evidence_sha256": cutover._sha256_json(unsigned_proof)}
    del current_control
    return config, stored_owner, proof, claim_root, transition


def test_lineage_owner_cas_requires_live_verifier_and_claim_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, prior_owner, proof, claim_root, transition = _lineage_owner_cas_fixture(tmp_path)
    control = cast(dict[str, object], transition["control_identity"])
    version = {"head": control["head"], "tree": control["tree"]}
    monkeypatch.setattr(cutover, "control_version", lambda: version)
    approval = cast(dict[str, object], transition["owner_approval"])

    with pytest.raises(
        cutover.CutoverSafetyError,
        match="lineage successor requires exact owner and ClaimStore revalidation",
    ):
        cutover.acquire_control_owner(
            config,
            action="apply",
            target=cast(cutover.Record, transition["target"]),
            owner_kind="protected",
            reservation_id=cast(str, approval["reservation_id"]),
            version=version,
            operation_id=cast(str, approval["operation_id"]),
            managed_receipt_sha256=cast(str, prior_owner["managed_receipt_sha256"]),
            predecessor_release_evidence=proof,
            predecessor_claim_root=claim_root,
        )


def test_lineage_owner_cas_runs_live_verifier_before_sealed_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _prior_owner, proof, claim_root, transition = _lineage_owner_cas_fixture(tmp_path)
    control = cast(dict[str, object], transition["control_identity"])
    version = {"head": control["head"], "tree": control["tree"]}
    monkeypatch.setattr(cutover, "control_version", lambda: version)
    approval = cast(dict[str, object], transition["owner_approval"])
    verified: list[str] = []

    def verify() -> None:
        verified.append("claim-transaction-live-check")

    owner = cutover.acquire_control_owner(
        config,
        action="apply",
        target=cast(cutover.Record, transition["target"]),
        owner_kind="protected",
        reservation_id=cast(str, approval["reservation_id"]),
        version=version,
        operation_id=cast(str, approval["operation_id"]),
        managed_receipt_sha256=cast(str, proof["prior_managed_receipt_sha256"]),
        predecessor_release_evidence=proof,
        predecessor_live_verifier=verify,
        predecessor_claim_root=claim_root,
    )

    assert owner["phase"] == "AUTHORIZATION_PENDING"
    assert owner["predecessor_release_evidence"] == proof
    assert verified == ["claim-transaction-live-check"]
    inspected = cutover.inspect_control_owner(config)
    assert inspected is not None
    assert inspected["record_sha256"] == owner["record_sha256"]


def test_two_lineage_successor_reservations_have_one_cas_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, prior_owner, base_proof, claim_root, base_transition = (
        _lineage_owner_cas_fixture(tmp_path)
    )
    control = cast(dict[str, object], base_transition["control_identity"])
    version = {"head": control["head"], "tree": control["tree"]}
    monkeypatch.setattr(cutover, "control_version", lambda: version)
    target = cast(cutover.Record, base_transition["target"])
    competitors: list[tuple[str, str, cutover.Record]] = []
    for index in range(2):
        transition = copy.deepcopy(base_transition)
        approval = cast(cutover.Record, transition["owner_approval"])
        reservation_id = str(uuid4())
        operation_id = _sha(f"competing-operation-{index}")[:32]
        approval["reservation_id"] = reservation_id
        approval["operation_id"] = operation_id
        _reseal(transition)
        proof_unsigned = {
            key: value
            for key, value in base_proof.items()
            if key != "evidence_sha256"
        }
        proof_unsigned["new_reservation_id"] = reservation_id
        proof_unsigned["new_operation_id"] = operation_id
        proof_unsigned["lineage_successor_transition"] = transition
        proof = {
            **proof_unsigned,
            "evidence_sha256": cutover._sha256_json(proof_unsigned),
        }
        competitors.append((reservation_id, operation_id, proof))

    start = Barrier(2)

    def reserve(candidate: tuple[str, str, cutover.Record]) -> tuple[str, object]:
        reservation_id, operation_id, proof = candidate
        start.wait(timeout=5)
        try:
            result = cutover.acquire_control_owner(
                config,
                action="apply",
                target=target,
                owner_kind="protected",
                reservation_id=reservation_id,
                version=version,
                operation_id=operation_id,
                managed_receipt_sha256=cast(str, prior_owner["managed_receipt_sha256"]),
                predecessor_release_evidence=proof,
                predecessor_live_verifier=lambda: None,
                predecessor_claim_root=claim_root,
            )
            return "success", result
        except cutover.CutoverError as exc:
            return "rejected", str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, competitors))

    successes = [value for status, value in results if status == "success"]
    rejections = [value for status, value in results if status == "rejected"]
    assert len(successes) == len(rejections) == 1
    winner = cutover.inspect_control_owner(config)
    assert winner is not None
    assert winner["reservation_id"] in {item[0] for item in competitors}
    assert winner["phase"] == "AUTHORIZATION_PENDING"


def test_lineage_owner_authorize_requires_live_transition_revalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _prior_owner, proof, claim_root, transition = _lineage_owner_cas_fixture(tmp_path)
    control = cast(dict[str, object], transition["control_identity"])
    version = {"head": control["head"], "tree": control["tree"]}
    monkeypatch.setattr(cutover, "control_version", lambda: version)
    approval = cast(dict[str, object], transition["owner_approval"])
    owner = cutover.acquire_control_owner(
        config,
        action="apply",
        target=cast(cutover.Record, transition["target"]),
        owner_kind="protected",
        reservation_id=cast(str, approval["reservation_id"]),
        version=version,
        operation_id=cast(str, approval["operation_id"]),
        managed_receipt_sha256=cast(str, proof["prior_managed_receipt_sha256"]),
        predecessor_release_evidence=proof,
        predecessor_live_verifier=lambda: None,
        predecessor_claim_root=claim_root,
    )
    del owner
    inspected = cutover.inspect_control_owner(config)
    assert inspected is not None
    auth = cutover.control_owner_authorization(inspected)
    with pytest.raises(
        cutover.CutoverSafetyError,
        match="versioned successor authorization requires live transition revalidation",
    ):
        cutover.authorize_control_owner(
            config,
            cast(str, approval["reservation_id"]),
            auth,
        )


def _lineage_request_builder_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[cutover.CutoverConfig, argparse.Namespace, dict[str, object], cutover.Record]:
    config, _released_owner, _proof, claim_root, transition_template = (
        _lineage_owner_cas_fixture(tmp_path)
    )
    target = cast(dict[str, str], transition_template["target"])
    source_old = _target(tmp_path / "source-old", cutover.V5_SOURCE_HEAD, cutover.V5_SOURCE_TREE)
    plan_file = tmp_path / "candidate-plan.json"
    plan_sha = _sha("candidate plan")
    plan_digest = _sha("candidate plan digest")
    prestate_digest = _sha("candidate prestate")
    plan: cutover.Record = {
        "source": {"old": source_old, "new": target},
        "prestate": {"prestate_digest": prestate_digest},
    }
    request = protected.Request(
        config,
        Path(source_old["source_worktree"]),
        source_old["head"],
        source_old["tree"],
        plan_file,
        plan_digest,
        plan_sha,
        claim_root,
        reservation_id="22222222-2222-4222-8222-222222222222",
        operation_id="c" * 32,
        managed_receipt_sha256=cutover.V5_MANAGED_RECEIPT_SHA256,
        control_head="1" * 40,
        control_tree="2" * 40,
        prior_execution_receipt_sha256=cutover.V5_PROTECTED_RECEIPT_SHA256,
    )
    def load_plan(_self: protected.Request) -> cutover.Record:
        return plan

    def make_request(*_args: object, **_kwargs: object) -> protected.Request:
        return request

    def prove_old(*_args: object, **_kwargs: object) -> cutover.Record:
        return {}

    def control_version() -> cutover.Record:
        return {"head": "1" * 40, "tree": "2" * 40}

    def pid_state(_pid: int) -> str:
        return "STALE_PROCESS"

    def validate_predecessor(_value: object, _owner: cutover.Record) -> cutover.Record:
        return {}

    monkeypatch.setattr(protected.Request, "load_plan", load_plan)
    monkeypatch.setattr(protected, "make_request", make_request)
    monkeypatch.setattr(protected, "_prove_plan_old_live", prove_old)
    monkeypatch.setattr(cutover, "control_version", control_version)
    monkeypatch.setattr(cutover, "_pid_state", pid_state)
    monkeypatch.setattr(cutover, "_validate_predecessor_release_evidence", validate_predecessor)

    owner_path = config.receipt_path.with_name(cutover.CONTROL_OWNER_NAME)
    owner: cutover.Record = {
        "schema": cutover.CONTROL_OWNER_SCHEMA,
        "reservation_id": cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_RESERVATION_ID,
        "owner_kind": "protected",
        "owner_pid": 99999999,
        "action": "apply",
        "target": cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_TARGET,
        "control_head": cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_CONTROL_HEAD,
        "control_tree": cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_CONTROL_TREE,
        "operation_id": cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_OPERATION_ID,
        "managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "phase": "AUTHORIZED_PENDING",
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
        "authorization": None,
        "mutation_started": False,
        "terminal": None,
        "release_evidence": None,
        "predecessor_release_evidence": {
            "evidence_sha256": cutover.LINEAGE_SUCCESSOR_REVIEWED_PREDECESSOR_EVIDENCE_SHA256
        },
    }
    owner["authorization"] = cutover._owner_identity(owner)
    owner = cutover._seal_control_owner(owner)
    owner_sha = cast(
        str,
        cast(dict[str, object], transition_template["pending_owner_snapshot"])["bytes_sha256"],
    )
    owner_record_sha = owner["record_sha256"]
    owner_identity = cutover.FileIdentity(
        str(owner_path), 1, 2, stat.S_IFREG | 0o600, os.getuid(), 1, 128, 1, 1, owner_sha
    )
    def read_owner(_config: cutover.CutoverConfig) -> tuple[cutover.Record, cutover.FileIdentity]:
        return owner, owner_identity

    original_read_control_json = cutover.read_control_json

    def read_control_json(path: Path) -> tuple[cutover.Record, cutover.FileIdentity, bytes]:
        if path != config.receipt_path:
            return original_read_control_json(path)
        return (
            {"status": "SUCCESS", "phase": "COMPLETED"},
            cutover.FileIdentity(
                str(path), 1, 3, stat.S_IFREG | 0o600, os.getuid(), 1, 32, 1, 1,
                cutover.V5_MANAGED_RECEIPT_SHA256,
            ),
            b"managed receipt fixture",
        )

    monkeypatch.setattr(cutover, "_read_control_owner", read_owner)
    monkeypatch.setattr(cutover, "read_control_json", read_control_json)
    retirement: cutover.Record = {
        "schema": cutover.FAILED_TERMINAL_RETIREMENT_V2_SCHEMA,
        "candidate_reservation_id": cutover.RELEASED_INTERMEDIATE_RESERVATION_ID,
        "candidate_operation_id": cutover.RELEASED_INTERMEDIATE_OPERATION_ID,
        "candidate_target": _target(
            Path(cutover.RELEASED_INTERMEDIATE_TARGET_WORKTREE),
            cutover.V7_SOURCE_HEAD,
            cutover.V7_SOURCE_TREE,
        ),
        "candidate_plan_sha256": cutover.V7_CANDIDATE_PLAN_SHA256,
        "claim_root": None,
    }
    retirement["record_sha256"] = cutover._sha256_json(
        {key: value for key, value in retirement.items() if key != "record_sha256"}
    )
    retirement_raw = (protected.canonical(retirement) + "\n").encode()
    retirement_sha = hashlib.sha256(retirement_raw).hexdigest()
    retirement_path = config.scheduler_root / cutover.FAILED_TERMINAL_RETIREMENT_V2_NAME
    retirement_identity = cutover.FileIdentity(
        str(retirement_path), 1, 4, stat.S_IFREG | 0o600, os.getuid(), 1,
        len(retirement_raw), 1, 1, retirement_sha,
    )
    original_load_json = cutover._load_json  # pyright: ignore[reportPrivateUsage]

    def load_json(path: Path) -> tuple[cutover.Record, cutover.FileIdentity, bytes]:
        if path == retirement_path:
            return retirement, retirement_identity, retirement_raw
        return original_load_json(path)

    def validate_retirement(value: object) -> cutover.Record:
        return cast(cutover.Record, value)

    def verify_retirement(_config: cutover.CutoverConfig, _value: cutover.Record) -> None:
        return None

    monkeypatch.setattr(cutover, "_load_json", load_json)
    monkeypatch.setattr(
        cutover, "_validate_failed_terminal_retirement_evidence", validate_retirement
    )
    monkeypatch.setattr(cutover, "_verify_failed_terminal_retirement_inputs", verify_retirement)
    ancestor_by_id = {
        cast(str, item["node_id"]): item
        for item in cast(list[dict[str, object]], transition_template["ancestor_evidence"])
    }
    ancestor_by_id["current-owner-2899"]["bytes_sha256"] = owner_identity.sha256
    ancestor_by_id["current-owner-2899"]["record_sha256"] = owner_record_sha
    ancestor_by_id["retirement-v2"]["bytes_sha256"] = retirement_sha
    ancestor_by_id["retirement-v2"]["record_sha256"] = retirement["record_sha256"]
    request_document: dict[str, object] = {
        "schema": protected.LINEAGE_SUCCESSOR_REQUEST_SCHEMA,
        "transition_id": transition_template["transition_id"],
        "reservation_id": request.reservation_id,
        "control_identity": {
            "head": "1" * 40,
            "tree": "2" * 40,
            "worktree": str(protected.CONTROL_ROOT),
        },
        "original_control_identity": transition_template["original_control_identity"],
        "source_old": source_old,
        "target": target,
        "plan": {
            "path": str(plan_file),
            "sha256": plan_sha,
            "digest": plan_digest,
            "prestate_digest": prestate_digest,
        },
        "claim_root": str(claim_root),
        "ancestor_evidence": list(ancestor_by_id.values()),
        "known_gaps": transition_template["known_gaps"],
        "known_gaps_decision": "PRESERVE_UNRESOLVED_AND_CONTINUE",
        "signer_identity": "test-owner",
    }
    def claim_root_factory() -> Path:
        return claim_root

    def verify_ancestors(
        _transition: cutover.Record, *, skip_node_ids: set[str] | None = None
    ) -> None:
        del skip_node_ids

    monkeypatch.setattr(protected, "repository_claim_root", claim_root_factory)
    monkeypatch.setattr(protected, "_verify_lineage_ancestor_files", verify_ancestors)
    args = argparse.Namespace(
        legacy_worktree=str(source_old["source_worktree"]),
        legacy_head=source_old["head"],
        legacy_tree=source_old["tree"],
    )
    return config, args, request_document, {
        "owner": owner,
        "owner_sha": owner_sha,
        "transition_template": transition_template,
    }


def test_lineage_successor_draft_binds_live_owner_retirement_and_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, args, request_document, snapshot = _lineage_request_builder_fixture(
        tmp_path, monkeypatch
    )
    owner_snapshot = cast(cutover.Record, snapshot["owner"])
    transition, approval, owner_identity, request = protected._lineage_successor_request_transition(
        args,
        config,
        request_document,
        include_owner_approval=False,
    )

    assert transition["phase"] == "PREPARED"
    assert transition["transition_sha256"] == approval["transition_digest"]
    assert transition["pending_owner_snapshot"] == {
        "path": str(config.receipt_path.with_name(cutover.CONTROL_OWNER_NAME)),
        "bytes_sha256": owner_identity.sha256,
        "record_sha256": owner_snapshot["record_sha256"],
        "reservation_id": cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_RESERVATION_ID,
        "operation_id": cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_OPERATION_ID,
        "phase": "AUTHORIZED_PENDING",
        "action": "apply",
        "target": cutover.LINEAGE_SUCCESSOR_REVIEWED_OWNER_TARGET,
        "control_identity": transition["original_control_identity"],
        "authorization_sha256": protected.digest(owner_snapshot["authorization"]),
        "predecessor_release_evidence_sha256": (
            cutover.LINEAGE_SUCCESSOR_REVIEWED_PREDECESSOR_EVIDENCE_SHA256
        ),
        "mutation_started": False,
    }
    assert cast(cutover.Record, transition["plan"])["sha256"] == request.plan_sha256
    retirement = cast(cutover.Record, transition["retirement"])
    assert cast(cutover.Record, retirement["candidate"])["plan_sha256"] == (
        cutover.V7_CANDIDATE_PLAN_SHA256
    )


def _lineage_command_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    cutover.CutoverConfig,
    argparse.Namespace,
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    verify_ancestors = protected._verify_lineage_ancestor_files
    real_load_json = cutover._load_json  # pyright: ignore[reportPrivateUsage]
    config, args, request_document, snapshot = _lineage_request_builder_fixture(
        tmp_path, monkeypatch
    )
    owner_path = config.receipt_path.with_name(cutover.CONTROL_OWNER_NAME)
    owner = cast(cutover.Record, snapshot["owner"])
    existing_owner_identity, _ = cutover._file_identity(  # pyright: ignore[reportPrivateUsage]
        owner_path, missing_ok=False, require_mode=0o600
    )
    assert existing_owner_identity is not None
    owner_identity = cutover.write_control_json(
        owner_path, owner, expected=existing_owner_identity
    )
    owner_state: dict[str, object] = {"record": owner, "identity": owner_identity}

    def read_owner(_config: cutover.CutoverConfig) -> tuple[cutover.Record, cutover.FileIdentity]:
        return (
            cast(cutover.Record, owner_state["record"]),
            cast(cutover.FileIdentity, owner_state["identity"]),
        )

    monkeypatch.setattr(cutover, "_read_control_owner", read_owner)

    retirement_path = config.scheduler_root / cutover.FAILED_TERMINAL_RETIREMENT_V2_NAME
    retirement: cutover.Record = {
        "schema": cutover.FAILED_TERMINAL_RETIREMENT_V2_SCHEMA,
        "candidate_reservation_id": cutover.RELEASED_INTERMEDIATE_RESERVATION_ID,
        "candidate_operation_id": cutover.RELEASED_INTERMEDIATE_OPERATION_ID,
        "candidate_target": _target(
            Path(cutover.RELEASED_INTERMEDIATE_TARGET_WORKTREE),
            cutover.V7_SOURCE_HEAD,
            cutover.V7_SOURCE_TREE,
        ),
        "candidate_plan_sha256": cutover.V7_CANDIDATE_PLAN_SHA256,
        "claim_root": None,
    }
    retirement_raw, retirement_sha, retirement_seal = _write_sealed_json(
        retirement_path, retirement
    )
    retirement["record_sha256"] = retirement_seal
    retirement_identity, observed_retirement_raw = cutover._file_identity(  # pyright: ignore[reportPrivateUsage]
        retirement_path, missing_ok=False, require_mode=0o600
    )
    assert retirement_identity is not None
    assert observed_retirement_raw == retirement_raw

    def load_json(path: Path) -> tuple[cutover.Record, cutover.FileIdentity, bytes]:
        return real_load_json(path)

    monkeypatch.setattr(cutover, "_load_json", load_json)
    def validate_retirement(value: object) -> cutover.Record:
        return cast(cutover.Record, value)

    def verify_retirement_inputs(
        _config: cutover.CutoverConfig, _value: cutover.Record
    ) -> None:
        return None

    monkeypatch.setattr(
        cutover, "_validate_failed_terminal_retirement_evidence", validate_retirement
    )
    monkeypatch.setattr(
        cutover, "_verify_failed_terminal_retirement_inputs", verify_retirement_inputs
    )

    transition_template = cast(cutover.Record, snapshot["transition_template"])
    ancestors = cast(list[dict[str, object]], transition_template["ancestor_evidence"])
    for ancestor in ancestors:
        node_id = cast(str, ancestor["node_id"])
        if node_id == "current-owner-2899":
            ancestor["bytes_sha256"] = owner_identity.sha256
            ancestor["record_sha256"] = owner["record_sha256"]
            ancestor["schema"] = owner["schema"]
            ancestor["identity"] = {
                "reservation_id": owner["reservation_id"],
                "operation_id": owner["operation_id"],
            }
            continue
        if node_id == "retirement-v2":
            ancestor["bytes_sha256"] = retirement_sha
            ancestor["record_sha256"] = retirement_seal
            ancestor["schema"] = retirement["schema"]
            candidate = {
                "reservation_id": retirement["candidate_reservation_id"],
                "operation_id": retirement["candidate_operation_id"],
            }
            ancestor["identity"] = candidate
            continue
        ancestor_path = tmp_path / "history" / f"{node_id}.json"
        identity = cast(dict[str, object], ancestor["identity"])
        historical: cutover.Record = {
            "schema": ancestor["schema"],
            "identity": identity,
            "node_id": node_id,
        }
        raw, historical_sha, historical_seal = _write_sealed_json(
            ancestor_path, historical
        )
        assert raw
        ancestor["path"] = str(ancestor_path)
        ancestor["bytes_sha256"] = historical_sha
        ancestor["record_sha256"] = historical_seal

    ancestor_by_id = {cast(str, item["node_id"]): item for item in ancestors}
    for node_id, parent_ids in cutover.LINEAGE_SUCCESSOR_ANCESTOR_PARENTS.items():
        ancestor_by_id[node_id]["previous_evidence_sha256"] = [
            ancestor_by_id[parent]["bytes_sha256"] for parent in parent_ids
        ]
    request_document["ancestor_evidence"] = ancestors
    monkeypatch.setattr(protected, "_verify_lineage_ancestor_files", verify_ancestors)
    return config, args, request_document, owner_state, {
        "retirement": retirement,
        "retirement_path": retirement_path,
        "retirement_sha256": retirement_sha,
        "retirement_raw": retirement_raw,
    }


def _signed_lineage_request(
    config: cutover.CutoverConfig,
    args: argparse.Namespace,
    request_document: dict[str, object],
) -> tuple[Path, argparse.Namespace]:
    _transition, approval_template, _owner_identity, _request = (
        protected._lineage_successor_request_transition(
            args, config, request_document, include_owner_approval=False
        )
    )
    approval = dict(approval_template)
    approval["signature"] = "fixture-signature"
    request_document["owner_approval"] = approval
    request_path = config.scheduler_root / "lineage-successor-request.json"
    request_path.write_text(protected.canonical(request_document) + "\n", encoding="utf-8")
    request_path.chmod(0o600)
    return request_path, argparse.Namespace(
        **vars(args), lineage_successor_request=str(request_path)
    )


def _fixture_approval_verifier(signer: str, confirmation_digest: str, signature: str) -> bool:
    return (
        signer == "test-owner"
        and len(confirmation_digest) == 64
        and signature == "fixture-signature"
    )


def _patch_reservation_config(
    monkeypatch: pytest.MonkeyPatch, config: cutover.CutoverConfig
) -> None:
    def build_config(
        _args: argparse.Namespace, *, for_action: str
    ) -> cutover.CutoverConfig:
        del _args, for_action
        return config

    monkeypatch.setattr(protected, "build_reservation_config", build_config)


def test_lineage_successor_prepare_archives_pending_owner_and_writes_prepared_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, args, request_document, owner_state, _retirement = _lineage_command_fixture(
        tmp_path, monkeypatch
    )
    _patch_reservation_config(monkeypatch, config)
    request_path, prepare_args = _signed_lineage_request(config, args, request_document)
    del request_path

    result = protected.cmd_lineage_successor_prepare(
        prepare_args,
        expected_signer="test-owner",
        approval_verifier=_fixture_approval_verifier,
    )

    assert result["status"] == "PREPARED"
    assert result["idempotent_retry"] is False
    evidence_path = Path(cast(str, result["evidence_path"]))
    evidence, _identity, _raw = cutover.read_control_json(evidence_path)
    assert evidence["phase"] == "PREPARED"
    assert not os.path.lexists(config.scheduler_root / protected.RECEIPT_NAME)
    assert os.path.lexists(cutover._control_owner_path(config))  # pyright: ignore[reportPrivateUsage]
    current_owner = cutover._read_control_owner(config)  # pyright: ignore[reportPrivateUsage]
    assert current_owner is not None
    assert cast(cutover.FileIdentity, owner_state["identity"]).sha256 == current_owner[1].sha256
    status_args = argparse.Namespace(
        target_action="apply", lineage_successor_evidence=str(evidence_path)
    )
    status_before = cutover._file_identity(  # pyright: ignore[reportPrivateUsage]
        evidence_path, missing_ok=False
    )[0]
    status = protected.cmd_lineage_successor_status(status_args)
    status_after = cutover._file_identity(  # pyright: ignore[reportPrivateUsage]
        evidence_path, missing_ok=False
    )[0]
    assert status["phase"] == "PREPARED"
    assert status_before is not None and status_after is not None
    assert status_before.key() == status_after.key()

    retry = protected.cmd_lineage_successor_prepare(
        prepare_args,
        expected_signer="test-owner",
        approval_verifier=_fixture_approval_verifier,
    )
    assert retry["idempotent_retry"] is True


def test_lineage_successor_record_release_archives_exact_owner_and_retirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, args, request_document, owner_state, _retirement = _lineage_command_fixture(
        tmp_path, monkeypatch
    )
    _patch_reservation_config(monkeypatch, config)
    _request_path, prepare_args = _signed_lineage_request(config, args, request_document)
    prepared = protected.cmd_lineage_successor_prepare(
        prepare_args,
        expected_signer="test-owner",
        approval_verifier=_fixture_approval_verifier,
    )
    evidence_path = Path(cast(str, prepared["evidence_path"]))

    old_owner = cast(cutover.Record, owner_state["record"])
    released_owner = cutover._seal_control_owner(
        {
            **old_owner,
            "phase": "RELEASED",
            "release_evidence": {
                "kind": cutover.EXPLICIT_ABANDON_RELEASE_KIND,
                "verified": True,
            },
        }
    )
    released_identity = cutover.write_control_json(
        cutover._control_owner_path(config),  # pyright: ignore[reportPrivateUsage]
        released_owner,
        expected=cast(cutover.FileIdentity, owner_state["identity"]),
    )
    owner_state["record"] = released_owner
    owner_state["identity"] = released_identity
    release_args = argparse.Namespace(
        target_action="apply", lineage_successor_evidence=str(evidence_path)
    )

    result = protected.cmd_lineage_successor_record_release(
        release_args,
        expected_signer="test-owner",
        approval_verifier=_fixture_approval_verifier,
    )

    assert result["status"] == "OLD_OWNER_RELEASED"
    evidence, _identity, _raw = cutover.read_control_json(evidence_path)
    assert evidence["phase"] == "OLD_OWNER_RELEASED"
    released_snapshot = cast(cutover.Record, evidence["released_owner"])
    assert released_snapshot["bytes_sha256"] == released_identity.sha256
    assert os.path.lexists(cutover._control_owner_path(config))  # pyright: ignore[reportPrivateUsage]
    assert os.path.lexists(config.scheduler_root / cutover.FAILED_TERMINAL_RETIREMENT_V2_NAME)
    archive_paths = [
        Path(cast(str, item["archive_path"]))
        for item in cast(list[dict[str, object]], evidence["archives"])
    ]
    assert all(path.read_bytes() for path in archive_paths)
    evidence_identity_before = cutover._file_identity(  # pyright: ignore[reportPrivateUsage]
        evidence_path, missing_ok=False
    )[0]
    retry = protected.cmd_lineage_successor_record_release(
        release_args,
        expected_signer="test-owner",
        approval_verifier=_fixture_approval_verifier,
    )
    evidence_identity_after = cutover._file_identity(  # pyright: ignore[reportPrivateUsage]
        evidence_path, missing_ok=False
    )[0]
    assert retry["status"] == "OLD_OWNER_RELEASED"
    assert evidence_identity_before is not None and evidence_identity_after is not None
    assert evidence_identity_before.key() == evidence_identity_after.key()


@pytest.mark.parametrize(
    "phase",
    [
        "PREPARED",
        "OLD_OWNER_RELEASED",
        "AUTHORIZED_PENDING",
        "APPLY_STARTED",
        "RELEASED_SUCCESS",
        "RECOVERY_REQUIRED",
    ],
)
def test_lineage_successor_validator_accepts_only_phase_consistent_archive_states(
    tmp_path: Path, phase: str
) -> None:
    evidence = _successor_record(tmp_path, phase=phase)
    assert cutover._validate_lineage_successor_transition(
        evidence, now=NOW, expected_signer="test-owner"
    ) == evidence


@pytest.mark.parametrize(
    "phase,archive_kind,wrong_state",
    [
        ("PREPARED", "pending_owner", "CHANGED"),
        ("OLD_OWNER_RELEASED", "retirement", "ABSENT"),
        ("AUTHORIZED_PENDING", "retirement", "PRESENT"),
        ("APPLY_STARTED", "released_owner", "PRESENT"),
        ("RELEASED_SUCCESS", "pending_owner", "PRESENT"),
        ("RECOVERY_REQUIRED", "retirement", "PRESENT"),
    ],
)
def test_lineage_successor_validator_rejects_phase_archive_drift(
    tmp_path: Path, phase: str, archive_kind: str, wrong_state: str
) -> None:
    evidence = _successor_record(tmp_path, phase=phase)
    archives = cast(list[dict[str, object]], evidence["archives"])
    archive = next(item for item in archives if item["kind"] == archive_kind)
    archive["source_state"] = wrong_state
    _reseal(evidence)
    with pytest.raises(cutover.CutoverSafetyError):
        cutover._validate_lineage_successor_transition(evidence, now=NOW)


def test_lineage_successor_cancellation_cannot_be_fabricated_as_a_successor_phase(
    tmp_path: Path,
) -> None:
    evidence = _successor_record(tmp_path, phase="CANCELLED")
    with pytest.raises(
        cutover.CutoverSafetyError,
        match="lineage successor evidence schema or seal is invalid",
    ):
        cutover._validate_lineage_successor_transition(evidence, now=NOW)


@pytest.mark.parametrize(
    "current_phase,next_phase",
    [
        ("PREPARED", "APPLY_STARTED"),
        ("PREPARED", "AUTHORIZED_PENDING"),
        ("OLD_OWNER_RELEASED", "APPLY_STARTED"),
        ("AUTHORIZED_PENDING", "OLD_OWNER_RELEASED"),
        ("APPLY_STARTED", "AUTHORIZED_PENDING"),
        ("APPLY_STARTED", "OLD_OWNER_RELEASED"),
        ("RECOVERY_REQUIRED", "APPLY_STARTED"),
        ("RELEASED_SUCCESS", "APPLY_STARTED"),
        ("CANCELLED", "PREPARED"),
    ],
)
def test_lineage_successor_phase_updates_reject_skips_and_downgrades(
    tmp_path: Path, current_phase: str, next_phase: str
) -> None:
    evidence = _successor_record(tmp_path, phase=current_phase)
    with pytest.raises(protected.ProtectedError, match="phase transition is invalid"):
        protected._lineage_transition_with_updates(evidence, phase=next_phase)


@pytest.mark.parametrize(
    "defect",
    ["relative", "missing", "mode", "duplicate", "noncanonical", "oversized", "symlink"],
)
def test_lineage_request_reader_rejects_noncanonical_or_unsafe_input(
    tmp_path: Path, defect: str
) -> None:
    request_path = tmp_path / "request.json"
    payload = protected.canonical({"schema": protected.LINEAGE_SUCCESSOR_REQUEST_SCHEMA}) + "\n"
    request_path.write_text(payload, encoding="utf-8")
    request_path.chmod(0o600)
    selected_path = request_path
    if defect == "relative":
        selected_path = Path("request.json")
    elif defect == "missing":
        selected_path = tmp_path / "missing.json"
    elif defect == "mode":
        request_path.chmod(0o644)
    elif defect == "duplicate":
        request_path.write_text('{"schema":"x","schema":"y"}\n', encoding="utf-8")
        request_path.chmod(0o600)
    elif defect == "noncanonical":
        request_path.write_text('{"z":1,"a":2}\n', encoding="utf-8")
        request_path.chmod(0o600)
    elif defect == "oversized":
        request_path.write_bytes(b" " * (protected.MAX_RECEIPT_BYTES + 1))
        request_path.chmod(0o600)
    elif defect == "symlink":
        selected_path = tmp_path / "linked-request.json"
        selected_path.symlink_to(request_path)

    with pytest.raises(protected.ProtectedError):
        protected._read_lineage_successor_request(selected_path)


def _write_transition_file(
    scheduler_root: Path, evidence: dict[str, object], *, filename: str | None = None
) -> Path:
    scheduler_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    selected_name = filename or (
        f"{protected.LINEAGE_SUCCESSOR_EVIDENCE_NAME_PREFIX}"
        f"{evidence['transition_id']}.json"
    )
    path = scheduler_root / selected_name
    cutover.write_control_json(path, evidence, expected=None)
    return path


@pytest.mark.parametrize(
    "defect", ["outside", "nested", "wrong_name", "symlink", "unsafe_mode"]
)
def test_lineage_transition_file_reader_rejects_ambiguous_paths(
    tmp_path: Path, defect: str
) -> None:
    scheduler_root = tmp_path / "scheduler"
    evidence = _successor_record(tmp_path)
    correct_name = (
        f"{protected.LINEAGE_SUCCESSOR_EVIDENCE_NAME_PREFIX}"
        f"{evidence['transition_id']}.json"
    )
    valid_path = _write_transition_file(scheduler_root, evidence)
    selected_path = valid_path
    if defect == "outside":
        selected_path = tmp_path / correct_name
        cutover.write_control_json(selected_path, evidence, expected=None)
    elif defect == "nested":
        selected_path = _write_transition_file(
            scheduler_root / "nested", evidence, filename=correct_name
        )
    elif defect == "wrong_name":
        selected_path = _write_transition_file(scheduler_root, evidence, filename="other.json")
    elif defect == "symlink":
        selected_path.unlink()
        backing = scheduler_root / "backing.json"
        cutover.write_control_json(backing, evidence, expected=None)
        selected_path.symlink_to(backing)
    elif defect == "unsafe_mode":
        valid_path.chmod(0o644)

    with pytest.raises(protected.ProtectedError):
        protected._lineage_successor_transition_from_file(
            selected_path,
            scheduler_root,
            expected_signer="test-owner",
            approval_verifier=_accept_test_signature,
        )


def test_lineage_archive_rejects_second_snapshot_for_same_transition_kind(
    tmp_path: Path,
) -> None:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    transition_id = str(uuid4())
    first_source = scheduler_root / "owner-one.json"
    _, first_sha, first_seal = _write_sealed_json(
        first_source, {"schema": "fixture-owner-v1", "owner": "first"}
    )
    protected.archive_lineage_successor_source(
        scheduler_root, transition_id, "pending_owner", first_source, first_sha, first_seal
    )
    second_source = scheduler_root / "owner-two.json"
    _, second_sha, second_seal = _write_sealed_json(
        second_source, {"schema": "fixture-owner-v1", "owner": "second"}
    )

    with pytest.raises(protected.ProtectedError, match="conflicting bytes"):
        protected.archive_lineage_successor_source(
            scheduler_root, transition_id, "pending_owner", second_source, second_sha, second_seal
        )


def test_lineage_successor_release_refuses_retirement_drift_before_archiving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, args, request_document, owner_state, retirement_info = _lineage_command_fixture(
        tmp_path, monkeypatch
    )
    _patch_reservation_config(monkeypatch, config)
    _request_path, prepare_args = _signed_lineage_request(config, args, request_document)
    prepared = protected.cmd_lineage_successor_prepare(
        prepare_args,
        expected_signer="test-owner",
        approval_verifier=_fixture_approval_verifier,
    )
    evidence_path = Path(cast(str, prepared["evidence_path"]))
    owner = cast(cutover.Record, owner_state["record"])
    released = cutover._seal_control_owner(
        {
            **owner,
            "phase": "RELEASED",
            "release_evidence": {
                "kind": cutover.EXPLICIT_ABANDON_RELEASE_KIND,
                "verified": True,
            },
        }
    )
    released_identity = cutover.write_control_json(
        cutover._control_owner_path(config),  # pyright: ignore[reportPrivateUsage]
        released,
        expected=cast(cutover.FileIdentity, owner_state["identity"]),
    )
    owner_state.update({"record": released, "identity": released_identity})
    retirement_path = cast(Path, retirement_info["retirement_path"])
    retirement_path.write_bytes(cast(bytes, retirement_info["retirement_raw"]) + b" ")
    release_args = argparse.Namespace(
        target_action="apply", lineage_successor_evidence=str(evidence_path)
    )

    with pytest.raises(
        protected.ProtectedError,
        match="lineage successor owner/retirement bytes changed since prepare",
    ):
        protected.cmd_lineage_successor_record_release(
            release_args,
            expected_signer="test-owner",
            approval_verifier=_fixture_approval_verifier,
        )
    archive_root = config.scheduler_root / "b649-lineage-successor-archives"
    assert list(archive_root.rglob("released_owner.*.json")) == []
    assert list(archive_root.rglob("retirement.*.json")) == []


def test_lineage_successor_prepare_refuses_claim_residue_before_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, args, request_document, _owner_state, _retirement = _lineage_command_fixture(
        tmp_path, monkeypatch
    )
    _patch_reservation_config(monkeypatch, config)
    _request_path, prepare_args = _signed_lineage_request(config, args, request_document)

    def unknown_claim_status(
        _store: protected.claims.ClaimStore, _task_key: str
    ) -> dict[str, object]:
        return {"status": "UNKNOWN"}

    monkeypatch.setattr(
        protected.claims.ClaimStore,
        "inspect",
        unknown_claim_status,
    )

    with pytest.raises(
        protected.ProtectedError,
        match="active/unknown ClaimStore or child process prevents preparation",
    ):
        protected.cmd_lineage_successor_prepare(
            prepare_args,
            expected_signer="test-owner",
            approval_verifier=_fixture_approval_verifier,
        )
    assert not list(
        (config.scheduler_root / "b649-lineage-successor-archives").rglob("pending_owner.*.json")
    )


def test_lineage_archive_copies_exact_bytes_and_allows_only_exact_retry(tmp_path: Path) -> None:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    source = scheduler_root / "owner.json"
    raw, source_sha, record_sha = _write_sealed_json(
        source, {"schema": "fixture-owner-v1", "reservation_id": str(uuid4())}
    )
    transition_id = str(uuid4())

    first = protected.archive_lineage_successor_source(
        scheduler_root, transition_id, "pending_owner", source, source_sha, record_sha
    )
    second = protected.archive_lineage_successor_source(
        scheduler_root, transition_id, "pending_owner", source, source_sha, record_sha
    )

    assert first == second
    assert first["source_sha256"] == first["archive_sha256"] == source_sha
    assert first["source_record_sha256"] == record_sha
    assert first["readback_status"] == "VERIFIED"
    assert first["source_state"] == "PRESENT"
    assert source.read_bytes() == raw
    archive_path = Path(cast(str, first["archive_path"]))
    assert archive_path.read_bytes() == raw
    assert stat.S_IMODE(archive_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(archive_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(archive_path.parent.parent.stat().st_mode) == 0o700


def test_lineage_archive_refuses_conflicting_hash_qualified_archive(tmp_path: Path) -> None:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    source = scheduler_root / "owner.json"
    _, source_sha, record_sha = _write_sealed_json(source, {"schema": "fixture-owner-v1"})
    transition_id = str(uuid4())
    archive_parent = scheduler_root / "b649-lineage-successor-archives" / transition_id
    archive_parent.mkdir(mode=0o700, parents=True)
    archive_parent.parent.chmod(0o700)
    archive_parent.chmod(0o700)
    conflict = archive_parent / f"pending_owner.{source_sha}.{transition_id}.json"
    conflict.write_bytes(b"conflicting bytes")
    conflict.chmod(0o600)

    with pytest.raises(protected.ProtectedError, match="conflicting bytes"):
        protected.archive_lineage_successor_source(
            scheduler_root, transition_id, "pending_owner", source, source_sha, record_sha
        )


def test_lineage_archive_refuses_source_drift_since_prepare(tmp_path: Path) -> None:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    source = scheduler_root / "retirement.json"
    raw, source_sha, record_sha = _write_sealed_json(
        source, {"schema": "fixture-retirement-v1"}
    )
    source.write_bytes(raw + b"changed")
    source.chmod(0o600)

    with pytest.raises(protected.ProtectedError, match="source is missing or noncanonical"):
        protected.archive_lineage_successor_source(
            scheduler_root, str(uuid4()), "retirement", source, source_sha, record_sha
        )


def test_lineage_archive_refuses_path_outside_scheduler_root(tmp_path: Path) -> None:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    source = tmp_path / "outside.json"
    _, source_sha, record_sha = _write_sealed_json(source, {"schema": "fixture-owner-v1"})

    with pytest.raises(protected.ProtectedError, match="noncanonical"):
        protected.archive_lineage_successor_source(
            scheduler_root, str(uuid4()), "pending_owner", source, source_sha, record_sha
        )


def test_lineage_archive_refuses_symlink_parent(tmp_path: Path) -> None:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    source = outside / "owner.json"
    _, source_sha, record_sha = _write_sealed_json(source, {"schema": "fixture-owner-v1"})
    (scheduler_root / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(protected.ProtectedError, match="noncanonical"):
        protected.archive_lineage_successor_source(
            scheduler_root,
            str(uuid4()),
            "pending_owner",
            scheduler_root / "linked" / "owner.json",
            source_sha,
            record_sha,
        )


def test_lineage_archive_refuses_unsealed_source_and_unsafe_mode(tmp_path: Path) -> None:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    source = scheduler_root / "owner.json"
    raw, source_sha, record_sha = _write_sealed_json(source, {"schema": "fixture-owner-v1"})
    corrupt = raw.replace(record_sha.encode(), b"0" * 64)
    source.write_bytes(corrupt)
    source.chmod(0o600)
    with pytest.raises(protected.ProtectedError, match="record seal is invalid"):
        protected.archive_lineage_successor_source(
            scheduler_root,
            str(uuid4()),
            "pending_owner",
            source,
            hashlib.sha256(corrupt).hexdigest(),
            record_sha,
        )

    source.write_bytes(raw)
    source.chmod(0o644)
    with pytest.raises(cutover.CutoverSafetyError):
        protected.archive_lineage_successor_source(
            scheduler_root, str(uuid4()), "pending_owner", source, source_sha, record_sha
        )


def test_lineage_archive_rejects_unknown_evidence_kind(tmp_path: Path) -> None:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    source = scheduler_root / "owner.json"
    _, source_sha, record_sha = _write_sealed_json(source, {"schema": "fixture-owner-v1"})

    with pytest.raises(protected.ProtectedError, match="archive kind is unsupported"):
        protected.archive_lineage_successor_source(
            scheduler_root, str(uuid4()), "receipt", source, source_sha, record_sha
        )


def _retirement_restore_fixture(
    tmp_path: Path,
) -> tuple[dict[str, object], Path, Path, bytes, str, str]:
    evidence = _successor_record(tmp_path, phase="AUTHORIZED_PENDING")
    retirement = cast(dict[str, object], evidence["retirement"])
    archives = cast(list[dict[str, object]], evidence["archives"])
    source = Path(cast(str, retirement["path"]))
    unsigned: dict[str, object] = {
        "schema": cutover.FAILED_TERMINAL_RETIREMENT_V2_SCHEMA,
        "fixture": "restore",
    }
    raw, source_sha, record_sha = _write_sealed_json(source, unsigned)
    archive = archives[1]
    archive_path = Path(cast(str, archive["archive_path"]))
    archive_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive_path.write_bytes(raw)
    archive_path.chmod(0o600)
    source.unlink()
    retirement["bytes_sha256"] = source_sha
    retirement["record_sha256"] = record_sha
    archive["source_sha256"] = source_sha
    archive["source_record_sha256"] = record_sha
    archive["archive_sha256"] = source_sha
    archive["source_state"] = "ABSENT"
    archive["archive_path"] = str(
        archive_path.parent / f"retirement.{source_sha}.{evidence['transition_id']}.json"
    )
    Path(archive["archive_path"]).write_bytes(raw)
    Path(archive["archive_path"]).chmod(0o600)
    archive_path.unlink()
    _reseal(evidence)
    return evidence, source.parent, source, raw, source_sha, record_sha


def _accept_test_signature(signer: str, digest: str, signature: str) -> bool:
    return signer == "test-owner" and bool(digest) and signature == "test-signature"


def test_lineage_restore_restores_only_verified_bytes_to_an_absent_path(tmp_path: Path) -> None:
    evidence, scheduler_root, destination, raw, source_sha, record_sha = (
        _retirement_restore_fixture(tmp_path)
    )

    result = protected.restore_lineage_successor_archive(
        scheduler_root,
        evidence,
        "retirement",
        destination,
        expected_signer="test-owner",
        approval_verifier=_accept_test_signature,
        now_value=NOW,
    )

    assert result["status"] == "RESTORED"
    assert result["sha256"] == source_sha
    assert result["record_sha256"] == record_sha
    assert destination.read_bytes() == raw
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600


def test_lineage_restore_refuses_existing_destination_without_overwrite(tmp_path: Path) -> None:
    evidence, scheduler_root, destination, raw, _, _ = _retirement_restore_fixture(tmp_path)
    destination.write_bytes(b"preserve existing")
    destination.chmod(0o600)

    with pytest.raises(protected.ProtectedError, match="canonical-path reconciliation failed"):
        protected.restore_lineage_successor_archive(
            scheduler_root,
            evidence,
            "retirement",
            destination,
            expected_signer="test-owner",
            approval_verifier=_accept_test_signature,
            now_value=NOW,
        )
    assert destination.read_bytes() == b"preserve existing"
    assert raw != destination.read_bytes()


def test_lineage_restore_refuses_archive_tamper_and_bad_signature(tmp_path: Path) -> None:
    evidence, scheduler_root, destination, _, _, _ = _retirement_restore_fixture(tmp_path)
    archive = cast(dict[str, object], cast(list[object], evidence["archives"])[1])
    archive_path = Path(cast(str, archive["archive_path"]))
    original = archive_path.read_bytes()
    archive_path.write_bytes(original + b"tamper")
    archive_path.chmod(0o600)
    with pytest.raises(protected.ProtectedError, match="archive readback"):
        protected.restore_lineage_successor_archive(
            scheduler_root,
            evidence,
            "retirement",
            destination,
            expected_signer="test-owner",
            approval_verifier=_accept_test_signature,
            now_value=NOW,
        )
    assert not os.path.lexists(destination)
    archive_path.write_bytes(original)
    archive_path.chmod(0o600)
    with pytest.raises(protected.ProtectedError, match="differs from prepared"):
        protected.restore_lineage_successor_archive(
            scheduler_root,
            evidence,
            "retirement",
            destination,
            expected_signer="test-owner",
            approval_verifier=lambda _signer, _digest, _signature: False,
            now_value=NOW,
        )
    assert not os.path.lexists(destination)


@pytest.mark.parametrize(
    "defect",
    ["wrong_kind", "wrong_signer", "bad_signature", "outside", "existing", "symlink"],
)
def test_lineage_restore_refuses_invalid_archive_contract(
    tmp_path: Path, defect: str
) -> None:
    evidence, scheduler_root, destination, raw, _source_sha, _record_sha = (
        _retirement_restore_fixture(tmp_path)
    )
    selected_kind = "retirement"
    selected_destination = destination
    signer = "test-owner"
    verifier = _accept_test_signature
    archive = next(
        item
        for item in cast(list[dict[str, object]], evidence["archives"])
        if item.get("kind") == "retirement"
    )
    archive_path = Path(cast(str, archive["archive_path"]))
    if defect == "wrong_kind":
        selected_kind = "pending_owner"
    elif defect == "wrong_signer":
        signer = "unexpected-owner"
    elif defect == "bad_signature":
        def reject_signature(_signer: str, _digest: str, _signature: str) -> bool:
            return False

        verifier = reject_signature
    elif defect == "outside":
        selected_destination = tmp_path / "outside-retirement.json"
    elif defect == "existing":
        destination.write_bytes(b"preserve")
        destination.chmod(0o600)
    elif defect == "symlink":
        backing = scheduler_root / "backing.json"
        backing.write_bytes(raw)
        backing.chmod(0o600)
        archive_path.unlink()
        archive_path.symlink_to(backing)

    with pytest.raises((protected.ProtectedError, cutover.CutoverSafetyError)):
        protected.restore_lineage_successor_archive(
            scheduler_root,
            evidence,
            selected_kind,
            selected_destination,
            expected_signer=signer,
            approval_verifier=verifier,
            now_value=NOW,
        )
    if defect == "existing":
        assert destination.read_bytes() == b"preserve"
    elif selected_destination == destination:
        assert not os.path.lexists(destination)


def _lineage_apply_request(
    config: cutover.CutoverConfig,
    evidence: dict[str, object],
    evidence_path: Path,
) -> protected.Request:
    source_old = cast(dict[str, str], evidence["source_old"])
    plan = cast(dict[str, str], evidence["plan"])
    control = cast(dict[str, str], evidence["control_identity"])
    approval = cast(dict[str, str], evidence["owner_approval"])
    return protected.Request(
        config,
        Path(source_old["source_worktree"]),
        source_old["head"],
        source_old["tree"],
        Path(plan["path"]),
        plan["digest"],
        plan["sha256"],
        Path(cast(str, evidence["claim_root"])),
        reservation_id=approval["reservation_id"],
        operation_id=approval["operation_id"],
        managed_receipt_sha256=cutover.V5_MANAGED_RECEIPT_SHA256,
        control_head=control["head"],
        control_tree=control["tree"],
        prior_execution_receipt_sha256=cutover.V5_PROTECTED_RECEIPT_SHA256,
        lineage_successor_evidence=evidence_path,
        lineage_successor_transition_sha256=cast(str, evidence["transition_sha256"]),
    )


def _skip_lineage_archive_verification(
    _transition: cutover.Record, _scheduler_root: Path
) -> None:
    return None


def _skip_lineage_ancestor_verification(
    _transition: cutover.Record, *, skip_node_ids: set[str] | None = None
) -> None:
    del skip_node_ids
    return None


def _crash_after_lineage_apply_start(request: protected.Request) -> None:
    protected._verify_lineage_successor_archives = _skip_lineage_archive_verification
    protected._begin_lineage_successor_apply(
        request,
        expected_signer="test-owner",
        approval_verifier=_accept_test_signature,
    )
    os._exit(73)


def test_lineage_apply_start_marker_is_durable_and_idempotent_after_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    evidence = _successor_record(tmp_path, phase="AUTHORIZED_PENDING")
    evidence_path = scheduler_root / (
        f"{protected.LINEAGE_SUCCESSOR_EVIDENCE_NAME_PREFIX}{evidence['transition_id']}.json"
    )
    evidence_path.write_text(protected.canonical(evidence) + "\n", encoding="utf-8")
    evidence_path.chmod(0o600)
    target = cast(dict[str, str], evidence["target"])
    config = cutover.CutoverConfig(
        source_worktree=Path(target["source_worktree"]),
        scheduler_root=scheduler_root,
        receipt_path=scheduler_root / "managed-receipt.json",
        expected_head=target["head"],
        expected_tree=target["tree"],
        durable_ref=target["durable_ref"],
    )
    request = _lineage_apply_request(config, evidence, evidence_path)
    monkeypatch.setattr(
        protected, "_verify_lineage_successor_archives", _skip_lineage_archive_verification
    )

    first_transition, first_identity = protected._begin_lineage_successor_apply(
        request,
        expected_signer="test-owner",
        approval_verifier=_accept_test_signature,
    )
    second_transition, second_identity = protected._begin_lineage_successor_apply(
        request,
        expected_signer="test-owner",
        approval_verifier=_accept_test_signature,
    )

    assert first_transition["phase"] == "APPLY_STARTED"
    assert second_transition["phase"] == "APPLY_STARTED"
    assert first_identity.key() == second_identity.key()
    stored, stored_identity, _ = cutover.read_control_json(evidence_path)
    assert stored["phase"] == "APPLY_STARTED"
    assert stored_identity.key() == second_identity.key()


def test_lineage_apply_start_survives_abrupt_worker_exit(tmp_path: Path) -> None:
    scheduler_root = tmp_path / "scheduler"
    scheduler_root.mkdir(mode=0o700)
    evidence = _successor_record(tmp_path, phase="AUTHORIZED_PENDING")
    evidence_path = scheduler_root / (
        f"{protected.LINEAGE_SUCCESSOR_EVIDENCE_NAME_PREFIX}{evidence['transition_id']}.json"
    )
    evidence_path.write_text(protected.canonical(evidence) + "\n", encoding="utf-8")
    evidence_path.chmod(0o600)
    target = cast(dict[str, str], evidence["target"])
    config = cutover.CutoverConfig(
        source_worktree=Path(target["source_worktree"]),
        scheduler_root=scheduler_root,
        receipt_path=scheduler_root / "managed-receipt.json",
        expected_head=target["head"],
        expected_tree=target["tree"],
        durable_ref=target["durable_ref"],
    )
    request = _lineage_apply_request(config, evidence, evidence_path)
    worker = get_context("fork").Process(target=_crash_after_lineage_apply_start, args=(request,))

    worker.start()
    worker.join()

    assert worker.exitcode == 73
    stored, identity, raw = cutover.read_control_json(evidence_path)
    assert stored["phase"] == "APPLY_STARTED"
    assert raw.endswith(b"\n")
    assert identity.sha256 == hashlib.sha256(raw).hexdigest()


def test_lineage_apply_restart_accepts_started_owner_but_does_not_reissue_cas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _old_owner, _old_proof, claim_root, _template = _lineage_owner_cas_fixture(tmp_path)
    evidence = _successor_record(tmp_path, phase="AUTHORIZED_PENDING")
    approval = cast(dict[str, object], evidence["owner_approval"])
    approval["issued_at"] = (NOW - timedelta(minutes=10)).isoformat()
    approval["expires_at"] = (NOW - timedelta(minutes=5)).isoformat()
    approval["confirmation_digest"] = cutover._sha256_json(
        {
            key: value
            for key, value in approval.items()
            if key not in {"signature", "confirmation_digest"}
        }
    )
    evidence = protected._lineage_transition_with_updates(evidence, phase="APPLY_STARTED")
    _reseal(evidence)
    evidence_path = config.scheduler_root / (
        f"{protected.LINEAGE_SUCCESSOR_EVIDENCE_NAME_PREFIX}{evidence['transition_id']}.json"
    )
    evidence_path.write_text(protected.canonical(evidence) + "\n", encoding="utf-8")
    evidence_path.chmod(0o600)
    request = _lineage_apply_request(config, evidence, evidence_path)
    predecessor = {
        "prior_protected_receipt_sha256": cutover.V5_PROTECTED_RECEIPT_SHA256,
        "lineage_successor_transition": evidence,
    }
    current_owner: cutover.Record = {
        "schema": cutover.CONTROL_OWNER_SCHEMA,
        "reservation_id": approval["reservation_id"],
        "owner_kind": "protected",
        "owner_pid": os.getpid(),
        "action": "apply",
        "target": evidence["target"],
        "control_head": cast(dict[str, str], evidence["control_identity"])["head"],
        "control_tree": cast(dict[str, str], evidence["control_identity"])["tree"],
        "operation_id": approval["operation_id"],
        "managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "phase": "MUTATION_IN_PROGRESS",
        "authorization": None,
        "mutation_started": True,
        "predecessor_release_evidence": predecessor,
    }
    current_owner["authorization"] = cutover._owner_identity(current_owner)

    def reuse_request(*_args: object, **_kwargs: object) -> protected.Request:
        return request

    def fail_if_cas_replayed(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("an APPLY_STARTED restart must not repeat predecessor CAS")

    monkeypatch.setattr(protected, "make_request", reuse_request)
    monkeypatch.setattr(protected, "_finish_lineage_successor_owner_cas", fail_if_cas_replayed)
    monkeypatch.setattr(
        protected, "_verify_lineage_successor_archives", _skip_lineage_archive_verification
    )
    monkeypatch.setattr(
        protected, "_verify_lineage_ancestor_files", _skip_lineage_ancestor_verification
    )
    resumed_request, _proof, resumed, identity, path = (
        protected._resume_lineage_successor_reservation(
            argparse.Namespace(
                lineage_successor_evidence=str(evidence_path), takeover_stale=False
            ),
            config,
            current_owner,
            expected_signer="test-owner",
            approval_verifier=_accept_test_signature,
        )
    )

    assert resumed_request is request
    assert resumed["phase"] == "APPLY_STARTED"
    assert path == evidence_path
    stored, stored_identity, _ = cutover.read_control_json(evidence_path)
    assert stored["phase"] == "APPLY_STARTED"
    assert stored_identity.key() == identity.key()
    assert claim_root == request.claim_root

    unstarted_owner = copy.deepcopy(current_owner)
    unstarted_owner["phase"] = "AUTHORIZED_PENDING"
    unstarted_owner["mutation_started"] = False
    unstarted_owner["authorization"] = cutover._owner_identity(unstarted_owner)
    with pytest.raises(protected.ProtectedError, match="expired or replayed"):
        protected._resume_lineage_successor_reservation(
            argparse.Namespace(
                lineage_successor_evidence=str(evidence_path), takeover_stale=False
            ),
            config,
            unstarted_owner,
            expected_signer="test-owner",
            approval_verifier=_accept_test_signature,
        )


@pytest.mark.parametrize(
    "phase,accepted",
    [
        ("PREPARED", False),
        ("OLD_OWNER_RELEASED", False),
        ("AUTHORIZED_PENDING", False),
        ("APPLY_STARTED", True),
        ("RELEASED_SUCCESS", True),
        ("RECOVERY_REQUIRED", True),
    ],
)
def test_lineage_successor_approval_expiry_is_phase_bounded(
    tmp_path: Path, phase: str, accepted: bool
) -> None:
    evidence = _successor_record(tmp_path, phase=phase)
    approval = cast(dict[str, object], evidence["owner_approval"])
    approval["issued_at"] = (NOW - timedelta(minutes=10)).isoformat()
    approval["expires_at"] = (NOW - timedelta(minutes=5)).isoformat()
    approval["confirmation_digest"] = cutover._sha256_json(
        {
            key: value
            for key, value in approval.items()
            if key not in {"signature", "confirmation_digest"}
        }
    )
    _reseal(evidence)
    if accepted:
        assert cutover._validate_lineage_successor_transition(
            evidence, now=NOW, expected_signer="test-owner"
        ) == evidence
    else:
        with pytest.raises(cutover.CutoverSafetyError, match="expired or replayed"):
            cutover._validate_lineage_successor_transition(evidence, now=NOW)


def test_lineage_successor_apply_and_status_cli_bind_the_opt_in_evidence() -> None:
    apply_args = protected.parser().parse_args(
        [
            "apply",
            "--source-worktree",
            "/tmp/new",
            "--expected-head",
            "1" * 40,
            "--expected-tree",
            "2" * 40,
            "--legacy-worktree",
            "/tmp/old",
            "--legacy-head",
            "3" * 40,
            "--legacy-tree",
            "4" * 40,
            "--plan-file",
            "/tmp/plan.json",
            "--lineage-successor-evidence",
            "/tmp/scheduler/b649-lineage-successor-00000000-0000-4000-8000-000000000000.json",
        ]
    )
    status_args = protected.parser().parse_args(
        [
            "lineage-successor-status",
            "--for",
            "apply",
            "--source-worktree",
            "/tmp/new",
            "--expected-head",
            "1" * 40,
            "--expected-tree",
            "2" * 40,
            "--lineage-successor-evidence",
            "/tmp/scheduler/b649-lineage-successor-00000000-0000-4000-8000-000000000000.json",
        ]
    )
    assert apply_args.lineage_successor_evidence.endswith("000000000000.json")
    assert status_args.action == "lineage-successor-status"
    assert status_args.lineage_successor_evidence == apply_args.lineage_successor_evidence


@pytest.mark.parametrize(
    "defect,expected_error",
    [
        ("missing", "owner authorization binding is incomplete"),
        ("wrong_digest", "owner authorization differs from prepared transition/target"),
    ],
)
def test_lineage_successor_authorize_cli_requires_transition_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
    expected_error: str,
) -> None:
    config, _prior_owner, proof, _claim_root, transition = _lineage_owner_cas_fixture(tmp_path)
    approval = cast(dict[str, object], transition["owner_approval"])
    target = cast(dict[str, str], transition["target"])
    control = cast(dict[str, str], transition["control_identity"])
    owner: cutover.Record = {
        "reservation_id": approval["reservation_id"],
        "operation_id": approval["operation_id"],
        "owner_kind": "protected",
        "action": "apply",
        "target": target,
        "control_head": control["head"],
        "control_tree": control["tree"],
        "managed_receipt_sha256": cutover.V5_MANAGED_RECEIPT_SHA256,
        "phase": "AUTHORIZATION_PENDING",
        "authorization": None,
        "mutation_started": False,
        "predecessor_release_evidence": proof,
    }

    def build_config(_args: argparse.Namespace, *, for_action: str) -> cutover.CutoverConfig:
        assert for_action == "apply"
        return config

    def authorize_must_not_run(*_args: object, **_kwargs: object) -> cutover.Record:
        raise AssertionError("invalid lineage authorization must be rejected before owner CAS")

    def managed_receipt_sha(_path: Path) -> str:
        return cutover.V5_MANAGED_RECEIPT_SHA256

    def current_owner(_config: cutover.CutoverConfig) -> cutover.Record:
        return owner

    monkeypatch.setattr(protected, "build_reservation_config", build_config)
    monkeypatch.setattr(protected, "_existing_receipt_sha256", managed_receipt_sha)
    monkeypatch.setattr(cutover, "inspect_control_owner", current_owner)
    monkeypatch.setattr(cutover, "authorize_control_owner", authorize_must_not_run)
    args = argparse.Namespace(
        target_action="apply",
        reservation_id=approval["reservation_id"],
        operation_id=approval["operation_id"],
        managed_receipt_sha256=cutover.V5_MANAGED_RECEIPT_SHA256,
        control_head=control["head"],
        control_tree=control["tree"],
        target_source_worktree=target["source_worktree"],
        target_head=target["head"],
        target_tree=target["tree"],
        target_durable_ref=target["durable_ref"],
        transition_evidence_sha256=(
            None
            if defect == "missing"
            else "0" * 64
        ),
        plan_file=None if defect == "missing" else "/tmp/plan.json",
        lineage_successor_evidence=None if defect == "missing" else "/tmp/evidence.json",
    )
    with pytest.raises(protected.ProtectedError, match=expected_error):
        protected.cmd_authorize(
            args,
            lineage_expected_signer="test-owner",
            lineage_approval_verifier=_accept_test_signature,
        )


def test_historical_lineage_fixtures_match_provenance_and_have_no_private_paths() -> None:
    fixture_root = Path(__file__).resolve().parents[1] / "fixtures" / "b649_lineage_successor"
    manifest = json.loads((fixture_root / "provenance.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "b649-lineage-successor-fixture-provenance-v1"
    fixtures = cast(list[dict[str, object]], manifest["fixtures"])
    assert len(fixtures) == 2
    for fixture in fixtures:
        raw = (fixture_root / cast(str, fixture["path"])).read_bytes()
        assert len(raw) == fixture["bytes"]
        assert hashlib.sha256(raw).hexdigest() == fixture["sha256"]
        assert b"/Users/" not in raw
        assert b"/home/" not in raw
        assert b"-----BEGIN" not in raw
        assert b"ghp_" not in raw
        assert b"AKIA" not in raw

    historical_release = json.loads(
        (fixture_root / "historical_release_92740_sanitized.json").read_text(
            encoding="utf-8"
        )
    )
    record_seal = historical_release.pop("record_sha256")
    assert record_seal == protected.digest(historical_release)
    assert historical_release["mutation_started"] is False
