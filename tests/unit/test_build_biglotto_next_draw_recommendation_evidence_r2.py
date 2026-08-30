"""Synthetic contract tests for the R2 Next-Draw evidence assembler."""

from __future__ import annotations

import copy
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest
from tools import build_biglotto_next_draw_recommendation_evidence_r2 as assembler

from lottolab.evidence.canonical_json import (
    canonical_bytes,
    canonical_file_bytes,
    self_key_removed_sha256,
    sha256_hex,
)
from lottolab.strategies.catalog import production_catalog

Manifest = dict[str, Any]
ManifestSet = tuple[Manifest, Manifest, Manifest, Manifest]

_PLAN_BINDING_FIELDS = (
    "protocol_version",
    "canonicalization",
    "old_84_reuse",
    "source_fingerprint",
    "dataset_fingerprint",
    "runtime_fingerprint",
    "target_identity",
    "evaluator_contract",
    "strategy_order_sha256",
    "strategy_universe_sha256",
    "rng_classification_sha256",
    "strategy_universe",
    "zone_exclusion",
    "execution_contract",
)


def _fraction_pair(value: Fraction) -> dict[str, str]:
    return {
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
    }


def _strategy_universe() -> list[Manifest]:
    catalog = production_catalog()
    rows: list[Manifest] = []
    for strategy_id in assembler.EXPECTED_STRATEGY_IDS:
        descriptor = catalog.get(strategy_id)
        assert descriptor.adapter_path is not None
        rows.append(
            {
                "strategy_id": descriptor.strategy_id,
                "strategy_version": descriptor.version,
                "adapter_path": descriptor.adapter_path,
                "min_history": descriptor.min_history,
                "native_ticket_count": descriptor.native_ticket_count,
                "response_shape": "SINGLE_TICKET",
            }
        )
    return rows


def _common_fields() -> Manifest:
    runtime_details: Manifest = {
        "implementation": "synthetic-test-runtime",
        "python_version": "3.13",
    }
    universe = _strategy_universe()
    assert sha256_hex(canonical_bytes([row["strategy_id"] for row in universe])) == (
        assembler.EXPECTED_STRATEGY_ORDER_SHA256
    )
    assert sha256_hex(canonical_bytes(universe)) == assembler.EXPECTED_STRATEGY_UNIVERSE_SHA256
    return {
        "protocol_version": assembler.PROTOCOL_VERSION,
        "canonicalization": assembler.CANONICALIZATION_VERSION,
        "old_84_reuse": False,
        "source_fingerprint": {
            "repository_head": assembler.REPOSITORY_HEAD,
            "repository_tree": assembler.REPOSITORY_TREE,
            "source_tree_sha256": "1" * 64,
            "source_draw_db_sha256": "2" * 64,
        },
        "dataset_fingerprint": {
            "lottery_type": "BIG_LOTTO",
            "dataset_schema_version": "SYNTHETIC_DRAW_DATASET_V1",
            "logical_dataset_sha256": "3" * 64,
            "source_draw_count": 900,
            "last_causal_draw_id": "synthetic-0900",
        },
        "runtime_fingerprint": {
            "fingerprint_sha256": sha256_hex(canonical_bytes(runtime_details)),
            "details": runtime_details,
        },
        "target_identity": {
            "target_count": assembler.EXPECTED_REPLAY_DEPTH,
            "target_order_sha256": "4" * 64,
        },
        "evaluator_contract": {
            "evaluator_semantic_version": "base_method_evaluation/1.0.0",
            "lottery_type": "BIG_LOTTO",
            "hit_tier_id": assembler.EXPECTED_HIT_TIER_ID,
            "window_order": list(assembler.EXPECTED_WINDOW_ORDER),
            "eligible_draw_counts": list(assembler.EXPECTED_WINDOW_ELIGIBLE_COUNTS),
            "random_reference": _fraction_pair(assembler.EXPECTED_RANDOM_REFERENCE),
            "native_ticket_count": 1,
        },
        "strategy_order_sha256": assembler.EXPECTED_STRATEGY_ORDER_SHA256,
        "strategy_universe_sha256": assembler.EXPECTED_STRATEGY_UNIVERSE_SHA256,
        "rng_classification_sha256": assembler.EXPECTED_RNG_CLASSIFICATION_SHA256,
        "strategy_universe": universe,
        "zone_exclusion": {
            "strategy_id": assembler.ZONE_STRATEGY_ID,
            "catalog_ordinal": 19,
            "status": "DRIVER_ERROR",
            "windows": [],
        },
        "execution_contract": {
            "process_model": "ONE_PROCESS_PER_STRATEGY",
            "seed_timing": "POST_IMPORT_CATALOG_ADAPTER_CONSTRUCTION_PRE_TARGET_1",
            "cache_policy": "NO_REPLAY_RESULT_CACHE",
            "cache_constructor": "ReplayHistoricalPredictions(cache=None)",
            "parallelization": "SERIAL_ONLY_R1",
            "max_concurrency": 1,
            "replay_depth": assembler.EXPECTED_REPLAY_DEPTH,
            "source_import_policy": "EXACT_REPLAY_SOURCE_TREE",
        },
    }


def _plan_manifest() -> Manifest:
    payload: Manifest = {
        "manifest_schema_version": assembler.PLAN_MANIFEST_SCHEMA_VERSION,
        **_common_fields(),
        "manifest_sha256": "0" * 64,
        "operational": {"fixture_role": "plan"},
    }
    return assembler.seal_manifest(payload)


def _plan_binding(plan: Manifest) -> Manifest:
    return {field: copy.deepcopy(plan[field]) for field in _PLAN_BINDING_FIELDS}


def _success_count(strategy_index: int, window_index: int, eligible_count: int) -> int:
    return (strategy_index * 7 + window_index * 11) % (eligible_count + 1)


def _evaluation_records() -> list[Manifest]:
    catalog = production_catalog()
    records: list[Manifest] = []
    for strategy_index, strategy_id in enumerate(assembler.EXPECTED_STRATEGY_IDS, 1):
        descriptor = catalog.get(strategy_id)
        windows = [
            {
                "window_kind": window_kind,
                "window_status": "COMPLETE",
                "eligible_draw_count": eligible_count,
                "success_count": _success_count(
                    strategy_index,
                    window_index,
                    eligible_count,
                ),
            }
            for window_index, (window_kind, eligible_count) in enumerate(
                zip(
                    assembler.EXPECTED_WINDOW_ORDER,
                    assembler.EXPECTED_WINDOW_ELIGIBLE_COUNTS,
                    strict=True,
                )
            )
        ]
        records.append(
            {
                "strategy_id": strategy_id,
                "strategy_name": descriptor.strategy_name,
                "native_ticket_count": 1,
                "hit_tier_id": assembler.EXPECTED_HIT_TIER_ID,
                "windows": windows,
            }
        )
    return records


def _run_manifest(plan: Manifest, *, run_label: str) -> Manifest:
    payload: Manifest = {
        "manifest_schema_version": assembler.RUN_MANIFEST_SCHEMA_VERSION,
        "plan_manifest_sha256": plan["manifest_sha256"],
        **_plan_binding(plan),
        "evaluation_records": _evaluation_records(),
        "deterministic_payload_sha256": "0" * 64,
        "manifest_sha256": "0" * 64,
        "operational": {"run_label": run_label},
    }
    return assembler.seal_run_manifest(payload)


def _acceptance_manifest(
    plan: Manifest,
    run_a: Manifest,
    run_b: Manifest,
    *,
    acceptance_status: str = "PASS",
    comparison_status: str = "PASS",
) -> Manifest:
    payload: Manifest = {
        "manifest_schema_version": assembler.ACCEPTANCE_MANIFEST_SCHEMA_VERSION,
        "plan_manifest_sha256": plan["manifest_sha256"],
        "run_a_manifest_sha256": run_a["manifest_sha256"],
        "run_b_manifest_sha256": run_b["manifest_sha256"],
        **_plan_binding(plan),
        "comparison": {
            "status": comparison_status,
            "run_a_deterministic_payload_sha256": run_a["deterministic_payload_sha256"],
            "run_b_deterministic_payload_sha256": run_b["deterministic_payload_sha256"],
            "evaluated_strategy_count": assembler.EXPECTED_STRATEGY_COUNT,
            "eligible_cell_count": assembler.EXPECTED_EVALUATED_CELL_COUNT,
            "zone_status": "DRIVER_ERROR",
            "target_order_sha256": plan["target_identity"]["target_order_sha256"],
        },
        "acceptance_status": acceptance_status,
        "manifest_sha256": "0" * 64,
        "operational": {"fixture_role": "acceptance"},
    }
    return assembler.seal_manifest(payload)


def _accepted_manifests() -> ManifestSet:
    plan = _plan_manifest()
    run_a = _run_manifest(plan, run_label="A")
    run_b = _run_manifest(plan, run_label="B")
    acceptance = _acceptance_manifest(plan, run_a, run_b)
    return plan, run_a, run_b, acceptance


def _assemble(manifests: ManifestSet) -> assembler.NextDrawRecommendationEvidenceArtifact:
    return assembler.assemble_artifact(*manifests)


def test_accepted_r2_material_projects_exact_55_record_census() -> None:
    artifact = _assemble(_accepted_manifests())
    payload = cast(Manifest, artifact.canonical_dict())
    payload_records = cast(list[Manifest], payload["records"])

    assert len(artifact.records) == 55
    assert sum(record["status"] == "EVALUATED" for record in payload_records) == 54
    assert sum(record["status"] == "DRIVER_ERROR" for record in payload_records) == 1
    expected_ids: list[str] = list(assembler.EXPECTED_STRATEGY_IDS)
    expected_ids.insert(18, assembler.ZONE_STRATEGY_ID)
    assert [record.strategy_id for record in artifact.records] == expected_ids

    zone = artifact.records[18]
    assert zone.strategy_id == assembler.ZONE_STRATEGY_ID
    assert payload_records[18]["status"] == "DRIVER_ERROR"
    assert zone.windows == ()


def test_projection_uses_exact_window_order_counts_and_reduced_fractions() -> None:
    artifact = _assemble(_accepted_manifests())
    reachable_index = 0
    for record in artifact.records:
        if record.strategy_id == assembler.ZONE_STRATEGY_ID:
            continue
        reachable_index += 1
        assert tuple(window.window_kind for window in record.windows) == (
            assembler.EXPECTED_WINDOW_ORDER
        )
        assert tuple(window.eligible_draw_count for window in record.windows) == (
            assembler.EXPECTED_WINDOW_ELIGIBLE_COUNTS
        )
        for window_index, window in enumerate(record.windows):
            eligible_count = assembler.EXPECTED_WINDOW_ELIGIBLE_COUNTS[window_index]
            expected_observed = Fraction(
                _success_count(reachable_index, window_index, eligible_count),
                eligible_count,
            )
            assert window.observed_value == expected_observed
            assert window.random_reference == Fraction(4654, 249711)
            assert window.delta_vs_random == expected_observed - Fraction(4654, 249711)

    payload = cast(Manifest, artifact.canonical_dict())
    payload_records = cast(list[Manifest], payload["records"])
    first_windows = cast(list[Manifest], payload_records[0]["windows"])
    for raw_window in first_windows:
        for fraction_key in ("observed_value", "random_reference", "delta_vs_random"):
            pair = cast(dict[str, str], raw_window[fraction_key])
            value = Fraction(int(pair["numerator"]), int(pair["denominator"]))
            assert pair == _fraction_pair(value)


def test_repeated_assembly_has_identical_canonical_bytes_and_digest() -> None:
    manifests = _accepted_manifests()
    _, run_a, run_b, _ = manifests
    assert run_a["deterministic_payload_sha256"] == run_b["deterministic_payload_sha256"]
    assert run_a["manifest_sha256"] != run_b["manifest_sha256"]
    artifact_a = _assemble(manifests)
    artifact_b = _assemble(copy.deepcopy(manifests))

    file_bytes_a = assembler.artifact_canonical_file_bytes(artifact_a)
    file_bytes_b = assembler.artifact_canonical_file_bytes(artifact_b)
    assert file_bytes_a == file_bytes_b
    assert artifact_a.artifact_sha256 == artifact_b.artifact_sha256
    assert file_bytes_a.endswith(b"\n")
    assert not file_bytes_a.endswith(b"\n\n")
    assert assembler.artifact_canonical_bytes(artifact_a) + b"\n" == file_bytes_a
    assert artifact_a.artifact_sha256 == self_key_removed_sha256(
        artifact_a.canonical_dict(), "artifact_sha256"
    )


@pytest.mark.parametrize("manifest_index", [0, 1, 2, 3])
def test_operational_metadata_is_bound_by_each_manifest_self_digest(
    manifest_index: int,
) -> None:
    manifests = list(_accepted_manifests())
    tampered_manifest = manifests[manifest_index]
    original_run_digest = tampered_manifest.get("deterministic_payload_sha256")
    tampered_manifest["operational"]["post_seal_tamper"] = True

    if original_run_digest is not None:
        assert assembler.deterministic_run_sha256(tampered_manifest) == original_run_digest
    assert assembler.manifest_sha256(tampered_manifest) != tampered_manifest["manifest_sha256"]
    with pytest.raises(
        assembler.EvidenceAssemblyError,
        match="manifest_sha256 does not match",
    ):
        _assemble(cast(ManifestSet, tuple(manifests)))


def test_same_run_manifest_cannot_satisfy_both_acceptance_slots() -> None:
    plan, run_a, _, _ = _accepted_manifests()
    acceptance = _acceptance_manifest(plan, run_a, run_a)

    with pytest.raises(
        assembler.EvidenceAssemblyError,
        match="two distinct run manifest identities are required",
    ):
        assembler.assemble_artifact(plan, run_a, run_a, acceptance)


def test_artifact_round_trip_and_tamper_rejection(tmp_path: Path) -> None:
    artifact = _assemble(_accepted_manifests())
    artifact_path = tmp_path / "assembled.json"
    artifact_path.write_bytes(assembler.artifact_canonical_file_bytes(artifact))
    assert assembler.load_artifact_file(artifact_path) == artifact

    tampered = cast(Manifest, copy.deepcopy(artifact.canonical_dict()))
    tampered["source_draw_count"] = int(tampered["source_draw_count"]) + 1
    with pytest.raises(assembler.EvidenceAssemblyError, match="self digest mismatch"):
        assembler.validate_assembled_artifact(tampered)

    self_hashed_but_invalid = cast(Manifest, copy.deepcopy(artifact.canonical_dict()))
    invalid_records = cast(list[Manifest], self_hashed_but_invalid["records"])
    invalid_windows = cast(list[Manifest], invalid_records[0]["windows"])
    delta = cast(dict[str, str], invalid_windows[0]["delta_vs_random"])
    delta["numerator"] = "1"
    delta["denominator"] = "1"
    self_hashed_but_invalid["artifact_sha256"] = self_key_removed_sha256(
        self_hashed_but_invalid, "artifact_sha256"
    )
    with pytest.raises(assembler.EvidenceAssemblyError, match="delta fraction mismatch"):
        assembler.validate_assembled_artifact(self_hashed_but_invalid)


def test_path_wrapper_consumes_only_canonical_manifests(tmp_path: Path) -> None:
    plan, run_a, run_b, acceptance = _accepted_manifests()
    input_payloads = {
        "plan.json": plan,
        "run-a.json": run_a,
        "run-b.json": run_b,
        "acceptance.json": acceptance,
    }
    for name, payload in input_payloads.items():
        (tmp_path / name).write_bytes(canonical_file_bytes(payload))

    output = tmp_path / "artifact.json"
    artifact = assembler.assemble_from_paths(
        plan_path=tmp_path / "plan.json",
        run_a_path=tmp_path / "run-a.json",
        run_b_path=tmp_path / "run-b.json",
        acceptance_path=tmp_path / "acceptance.json",
        output_path=output,
    )
    assert output.read_bytes() == assembler.artifact_canonical_file_bytes(artifact)

    noncanonical_plan = tmp_path / "noncanonical-plan.json"
    noncanonical_plan.write_bytes(canonical_file_bytes(plan) + b"\n")
    with pytest.raises(assembler.EvidenceAssemblyError, match="exactly one LF"):
        assembler.load_manifest_file(noncanonical_plan)


@pytest.mark.parametrize("case", ["duplicate", "missing", "extra", "reordered"])
def test_duplicate_missing_extra_or_reordered_strategy_records_reject(case: str) -> None:
    plan, run_a, run_b, acceptance = _accepted_manifests()
    records = run_a["evaluation_records"]
    if case == "duplicate":
        records[1]["strategy_id"] = records[0]["strategy_id"]
    elif case == "missing":
        records.pop()
    elif case == "extra":
        extra = copy.deepcopy(records[-1])
        extra["strategy_id"] = "synthetic_extra_strategy"
        records.append(extra)
    else:
        records[0], records[1] = records[1], records[0]

    with pytest.raises(assembler.EvidenceAssemblyError):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)


@pytest.mark.parametrize("case", ["duplicate", "missing", "extra", "reordered"])
def test_duplicate_missing_extra_or_reordered_windows_reject(case: str) -> None:
    plan, run_a, run_b, acceptance = _accepted_manifests()
    windows = run_a["evaluation_records"][0]["windows"]
    if case == "duplicate":
        windows[1] = copy.deepcopy(windows[0])
    elif case == "missing":
        windows.pop()
    elif case == "extra":
        windows.append(copy.deepcopy(windows[-1]))
    else:
        windows[0], windows[1] = windows[1], windows[0]

    with pytest.raises(assembler.EvidenceAssemblyError):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("old_84_reuse", True, "old_84_reuse must be false"),
        (
            "protocol_version",
            "NEXT_DRAW_54_REACHABLE_FULL_REPLAY_PROTOCOL_R1",
            "old protocol is forbidden",
        ),
        (
            "protocol_version",
            "NEXT_DRAW_REPLAY_STRATEGY_ISOLATED_MANIFEST_SEED_V1",
            "old protocol is forbidden",
        ),
    ],
)
def test_old84_reuse_and_old_protocols_reject(field: str, value: object, message: str) -> None:
    plan, run_a, run_b, acceptance = _accepted_manifests()
    plan[field] = value
    with pytest.raises(assembler.EvidenceAssemblyError, match=message):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)


def test_mixed_protocol_run_rejects() -> None:
    plan, run_a, run_b, acceptance = _accepted_manifests()
    run_a["protocol_version"] = "NEXT_DRAW_54_REACHABLE_FULL_REPLAY_PROTOCOL_R1"
    with pytest.raises(assembler.EvidenceAssemblyError, match="old protocol is forbidden"):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)


@pytest.mark.parametrize(
    ("acceptance_status", "comparison_status"),
    [("FAIL", "PASS"), ("PASS", "FAIL")],
)
def test_two_run_acceptance_must_be_pass(
    acceptance_status: str,
    comparison_status: str,
) -> None:
    plan, run_a, run_b, _ = _accepted_manifests()
    acceptance = _acceptance_manifest(
        plan,
        run_a,
        run_b,
        acceptance_status=acceptance_status,
        comparison_status=comparison_status,
    )
    with pytest.raises(assembler.EvidenceAssemblyError, match="must be PASS"):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)


def test_two_runs_must_be_deterministically_identical() -> None:
    plan, run_a, run_b, _ = _accepted_manifests()
    run_b["evaluation_records"][0]["windows"][0]["success_count"] += 1
    run_b = assembler.seal_run_manifest(run_b)
    acceptance = _acceptance_manifest(plan, run_a, run_b)

    with pytest.raises(assembler.EvidenceAssemblyError, match="two runs differ deterministically"):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("native_ticket_count", 2, "native_ticket_count must be one"),
        ("hit_tier_id", "M2_PLUS", "hit tier must be M3_PLUS"),
    ],
)
def test_incorrect_record_ticket_count_or_hit_tier_rejects(
    field: str,
    value: object,
    message: str,
) -> None:
    plan, run_a, run_b, acceptance = _accepted_manifests()
    run_a["evaluation_records"][0][field] = value
    with pytest.raises(assembler.EvidenceAssemblyError, match=message):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)


def test_wrong_target_identity_and_fingerprint_drift_reject() -> None:
    plan, run_a, run_b, acceptance = _accepted_manifests()
    plan["target_identity"]["target_count"] = 799
    with pytest.raises(assembler.EvidenceAssemblyError, match="exactly 800 targets"):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)

    plan, run_a, run_b, acceptance = _accepted_manifests()
    run_a["dataset_fingerprint"]["logical_dataset_sha256"] = "5" * 64
    with pytest.raises(assembler.EvidenceAssemblyError, match="does not match the accepted plan"):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)

    plan, run_a, run_b, acceptance = _accepted_manifests()
    run_a["runtime_fingerprint"]["details"]["implementation"] = "tampered"
    with pytest.raises(
        assembler.EvidenceAssemblyError, match="runtime fingerprint digest mismatch"
    ):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)


@pytest.mark.parametrize("mutation", ["extra", "missing"])
def test_closed_manifest_schema_rejects_unknown_or_missing_fields(mutation: str) -> None:
    plan, run_a, run_b, acceptance = _accepted_manifests()
    if mutation == "extra":
        plan["unexpected"] = "forbidden"
    else:
        del plan["source_fingerprint"]
    with pytest.raises(assembler.EvidenceAssemblyError, match="keys mismatch"):
        assembler.assemble_artifact(plan, run_a, run_b, acceptance)


def test_packaged_strategy_evidence_output_is_refused(tmp_path: Path) -> None:
    protected_output = (
        tmp_path / "src/lottolab/strategies/data/biglotto_next_draw_recommendation_evidence_v1.json"
    )
    with pytest.raises(assembler.EvidenceAssemblyError, match="refusing to overwrite"):
        assembler.assemble_from_paths(
            plan_path=tmp_path / "unused-plan.json",
            run_a_path=tmp_path / "unused-run-a.json",
            run_b_path=tmp_path / "unused-run-b.json",
            acceptance_path=tmp_path / "unused-acceptance.json",
            output_path=protected_output,
        )
