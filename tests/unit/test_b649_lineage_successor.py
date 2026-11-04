"""Pure schema and owner-binding tests for versioned lineage successors."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from tools import b649_production_cutover as cutover

# pyright: reportPrivateUsage=false

NOW = datetime.now(UTC).replace(microsecond=0)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


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
        "head": "3" * 40,
        "tree": "4" * 40,
        "worktree": str(tmp_path / "original-control"),
    }
    old_target = _target(tmp_path / "old-target", "5" * 40, "6" * 40)
    predecessor_target = _target(tmp_path / "predecessor-target", "7" * 40, "8" * 40)
    target = _target(tmp_path / "new-target", "9" * 40, "a" * 40)
    owner_path = tmp_path / "scheduler" / cutover.CONTROL_OWNER_NAME
    retirement_path = tmp_path / "scheduler" / cutover.FAILED_TERMINAL_RETIREMENT_V2_NAME
    owner_sha = _sha("owner-bytes")
    retirement_sha = _sha("retirement-bytes")
    pending_reservation = "11111111-1111-4111-8111-111111111111"
    pending_operation = "b" * 32
    auth_sha = _sha("old authorization")

    ancestor_ids = sorted(cutover.LINEAGE_SUCCESSOR_ANCESTOR_NODE_IDS)
    byte_hashes = [_sha(f"ancestor-bytes-{index}") for index in range(len(ancestor_ids))]
    record_hashes = [_sha(f"ancestor-record-{index}") for index in range(len(ancestor_ids))]
    ancestors: list[dict[str, object]] = []
    for index, node_id in enumerate(ancestor_ids):
        ancestors.append(
            {
                "node_id": node_id,
                "path": str(tmp_path / "history" / f"{node_id}.json"),
                "bytes_sha256": byte_hashes[index],
                "record_sha256": record_hashes[index],
                "schema": "fixture-evidence-v1",
                "identity": {
                    "reservation_id": str(uuid4()),
                    "operation_id": _sha(f"operation-{index}")[:32],
                },
                "previous_evidence_sha256": [byte_hashes[index - 1]] if index < 12 else [],
            }
        )

    known_gaps = [
        {"id": gap_id, "status": "UNRESOLVED", "source_document": "L1 gap register"}
        for gap_id in sorted(cutover.LINEAGE_SUCCESSOR_GAP_IDS)
    ]
    archives = [
        {
            "kind": "pending_owner",
            "source_path": str(owner_path),
            "archive_path": str(tmp_path / "scheduler" / f"owner.{owner_sha}.archive.json"),
            "source_sha256": owner_sha,
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
            "archive_sha256": retirement_sha,
            "readback_status": "VERIFIED",
            "source_state": "PRESENT",
        },
    ]
    evidence: dict[str, object] = {
        "schema": cutover.LINEAGE_SUCCESSOR_SCHEMA,
        "transition_id": str(uuid4()),
        "phase": phase,
        "control_identity": control,
        "original_control_identity": original_control,
        "source_old": old_target,
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
            "mutation_started": False,
        },
        "released_owner": None,
        "retirement": {
            "path": str(retirement_path),
            "bytes_sha256": retirement_sha,
            "record_sha256": _sha("retirement seal"),
            "schema": cutover.FAILED_TERMINAL_RETIREMENT_V2_SCHEMA,
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
        archives.append(
            {
                "kind": "released_owner",
                "source_path": str(owner_path),
                "archive_path": str(tmp_path / "scheduler" / "released-owner.archive.json"),
                "source_sha256": cast(str, released_owner["bytes_sha256"]),
                "archive_sha256": cast(str, released_owner["bytes_sha256"]),
                "readback_status": "VERIFIED",
                "source_state": "PRESENT",
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
