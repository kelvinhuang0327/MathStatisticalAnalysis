"""Direct canonical Runner-contract tests for the R2 artifact assembler."""

from __future__ import annotations

import copy
import inspect
import os
import random
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import pytest
from tools import build_biglotto_next_draw_recommendation_evidence_r2 as assembler

from lottolab.evidence.canonical_json import (
    canonical_bytes,
    canonical_file_bytes,
    sha256_hex,
)
from lottolab.strategies.catalog import production_catalog

Document = dict[str, Any]
ZERO_SHA = "0" * 64
REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_WORKTREE_NAME = "NEXT_DRAW_54_REPLAY_PROTOCOL_R2_RUNNER_IMPLEMENTATION_R1"


@dataclass
class Bundle:
    plan: Document
    run_a: Document
    run_b: Document
    acceptance: Document


def _digest(value: object) -> str:
    return sha256_hex(canonical_bytes(value))


def _file_digest(value: object) -> str:
    return sha256_hex(canonical_file_bytes(value))


def _seal(value: Document, key: str) -> Document:
    sealed = copy.deepcopy(value)
    sealed.pop(key, None)
    sealed[key] = _digest(sealed)
    return sealed


def _pair(value: Fraction) -> dict[str, str]:
    return {
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
    }


def _rng_class(strategy_id: str) -> str:
    if strategy_id in assembler.PRIVATE_RNG_STRATEGY_IDS:
        return "ADAPTER_LOCAL_DETERMINISTIC_RNG"
    if strategy_id in assembler.GLOBAL_RNG_STRATEGY_IDS:
        return "PROCESS_GLOBAL_PYTHON_RANDOM"
    return "NO_RNG"


def _strategy_contract() -> Document:
    catalog = production_catalog()
    identities: list[Document] = []
    names: list[Document] = []
    for strategy_id in assembler.EXPECTED_STRATEGY_IDS:
        descriptor = catalog.get(strategy_id)
        assert descriptor.adapter_path is not None
        identities.append(
            {
                "strategy_id": descriptor.strategy_id,
                "strategy_version": descriptor.version,
                "adapter_path": descriptor.adapter_path,
                "min_history": descriptor.min_history,
                "native_ticket_count": descriptor.native_ticket_count,
                "response_shape": "SINGLE_TICKET",
            }
        )
        names.append(
            {
                "strategy_id": descriptor.strategy_id,
                "strategy_name": descriptor.strategy_name,
            }
        )
    classifications = [
        {
            "strategy_id": row["strategy_id"],
            "strategy_version": row["strategy_version"],
            "rng_class": _rng_class(cast(str, row["strategy_id"])),
        }
        for row in identities
    ]
    excluded = catalog.get(assembler.ZONE_STRATEGY_ID)
    result: Document = {
        "count": 54,
        "records": identities,
        "names": names,
        "excluded": {
            "strategy_id": assembler.ZONE_STRATEGY_ID,
            "strategy_name": excluded.strategy_name,
            "filtered_catalog_ordinal": 19,
            "status": "DRIVER_ERROR",
            "windows": [],
        },
        "strategy_order_sha256": assembler.EXPECTED_STRATEGY_ORDER_SHA256,
        "strategy_universe_sha256": assembler.EXPECTED_STRATEGY_UNIVERSE_SHA256,
        "rng_classification": classifications,
        "rng_classification_sha256": assembler.EXPECTED_RNG_CLASSIFICATION_SHA256,
    }
    assert _digest([row["strategy_id"] for row in identities]) == (
        assembler.EXPECTED_STRATEGY_ORDER_SHA256
    )
    assert _digest(identities) == assembler.EXPECTED_STRATEGY_UNIVERSE_SHA256
    assert _digest(classifications) == assembler.EXPECTED_RNG_CLASSIFICATION_SHA256
    return result


def _snapshot(*, synthetic: bool, draw_count: int) -> Document:
    first = date(2020, 1, 1)
    draws = [
        {
            "source_row_id": index + 1,
            "draw_date": (first + timedelta(days=index)).isoformat(),
            "draw_number": f"{index + 1:09d}",
            "main_numbers": [1, 2, 3, 4, 5, 6],
            "special_number": 7,
        }
        for index in range(draw_count)
    ]
    return {
        "snapshot_schema_version": "NEXT_DRAW_54_SOURCE_SNAPSHOT_V2",
        "kind": (assembler.SYNTHETIC_DATA_KIND if synthetic else assembler.REAL_DATA_KIND),
        "lottery_type": "BIG_LOTTO",
        "draws": draws,
    }


def _module_path(name: str) -> str:
    stem = "src/" + name.replace(".", "/")
    return stem + "/__init__.py" if name == "lottolab" else stem + ".py"


def _authority(strategies: Document) -> Document:
    modules = {
        "lottolab",
        "lottolab.application.use_cases.replay_historical_predictions",
        "lottolab.strategies.catalog",
        *(row["adapter_path"].split(":")[0] for row in strategies["records"]),
    }
    paths = {_module_path(name) for name in modules} | {"uv.lock"}
    inventory: list[Document] = []
    for path in sorted(paths):
        sha256 = _digest(path)
        git_blob = _digest("blob:" + path)[:40]
        if path == "src/lottolab/strategies/catalog.py":
            sha256 = assembler.CATALOG_SHA256
            git_blob = assembler.CATALOG_GIT_BLOB
        elif path == "uv.lock":
            sha256 = assembler.UV_LOCK_SHA256
        inventory.append(
            {
                "path": path,
                "sha256": sha256,
                "git_blob": git_blob,
                "mode": "100644",
            }
        )
    return {
        "repository_head": assembler.REPOSITORY_HEAD,
        "repository_tree": assembler.REPOSITORY_TREE,
        "catalog_git_blob": assembler.CATALOG_GIT_BLOB,
        "catalog_sha256": assembler.CATALOG_SHA256,
        "uv_lock_sha256": assembler.UV_LOCK_SHA256,
        "load_bearing_blobs": inventory,
        "source_inventory_sha256": _digest(inventory),
    }


def _runtime(authority: Document) -> Document:
    return {
        "schema_version": "NEXT_DRAW_54_REPLAY_RUNTIME_V2",
        "python": {"fixture": "canonical-runner-shape"},
        "platform": {"fixture": "canonical-runner-shape"},
        "numeric": {"fixture": "canonical-runner-shape"},
        "distributions": [],
        "installer": {"fixture": "canonical-runner-shape"},
        "environment": [],
        "source_inventory_sha256": authority["source_inventory_sha256"],
        "runner_files": [
            {
                "path": "tools/next_draw_54_replay_r2.py",
                "sha256": "2" * 64,
            },
            {
                "path": "tools/next_draw_54_replay_r2_lib.py",
                "sha256": "3" * 64,
            },
            {
                "path": "tools/next_draw_54_replay_r2_runtime.py",
                "sha256": "4" * 64,
            },
        ],
    }


def _private_exceptions() -> list[Document]:
    return [
        {
            "strategy_id": strategy_id,
            "policy": (
                "DONOR_HISTORY_JSON_SHA256_PRIVATE_RANDOM_THREE_SEQUENTIAL_SAMPLES"
                if index < 3
                else "PRIVATE_RANDOM_LEN_HISTORY_EVERY_TRANSITIVE_INVOCATION"
            ),
        }
        for index, strategy_id in enumerate(assembler.PRIVATE_RNG_STRATEGY_IDS)
    ]


def _rng(strategies: Document, common_hash: str) -> Document:
    seeds: list[Document] = []
    for identity in strategies["records"]:
        parts = [
            assembler.PROTOCOL_VERSION,
            common_hash,
            identity["strategy_id"],
            identity["strategy_version"],
            identity["adapter_path"],
        ]
        digest = sha256_hex(b"\x00".join(part.encode("utf-8") for part in parts))
        seeds.append(
            {
                "strategy_id": identity["strategy_id"],
                "strategy_version": identity["strategy_version"],
                "adapter_path": identity["adapter_path"],
                "seed_digest": digest,
                "seed_integer": str(int(digest, 16)),
            }
        )
    return {
        "seed_policy": "MANIFEST_BOUND_PER_STRATEGY_SHA256",
        "seed_timing": "POST_IMPORT_CATALOG_ADAPTER_CONSTRUCTION_PRE_TARGET_1",
        "global_random_policy": (
            "PER_STRATEGY_STDLIB_MODULE_GLOBAL_RANDOM_CONTINUOUS_800_TARGET_STREAM"
        ),
        "private_rng_policy": "PRIVATE_RNG_SOURCE_SEMANTICS_PRESERVED_EXACTLY",
        "private_rng_exceptions": _private_exceptions(),
        "seeds": seeds,
    }


def _plan(*, synthetic: bool) -> Document:
    strategies = _strategy_contract()
    authority = _authority(strategies)
    largest_minimum = max(row["min_history"] for row in strategies["records"])
    snapshot = _snapshot(
        synthetic=synthetic,
        draw_count=assembler.EXPECTED_REPLAY_DEPTH + largest_minimum,
    )
    dataset: Document = {
        "dataset_id": "NEXT_DRAW_BIG_LOTTO_R2",
        "dataset_version": _digest(snapshot),
        "snapshot": snapshot,
        "dataset_snapshot_sha256": _digest(snapshot),
        "source_db": {
            "sha256": "5" * 64,
            "size_bytes": 1,
            "read_only": True,
            "sqlite_mode": "ro_immutable_no_wal",
        },
        "rule_contract": copy.deepcopy(assembler.EXPECTED_RULE_CONTRACT),
        "rule_contract_sha256": _digest(assembler.EXPECTED_RULE_CONTRACT),
    }
    targets: Document = {
        "order": "BOUND_800_VECTOR_OLDEST_FIRST",
        "count": 800,
        "vector": [
            {"draw_date": row["draw_date"], "draw_number": row["draw_number"]}
            for row in snapshot["draws"][-assembler.EXPECTED_REPLAY_DEPTH :]
        ],
    }
    targets["target_order_sha256"] = _digest(targets["vector"])
    runtime = _runtime(authority)
    runtime_hash = _digest(runtime)
    common: Document = {
        "canonicalization_version": assembler.CANONICALIZATION_VERSION,
        "protocol_version": assembler.PROTOCOL_VERSION,
        "repository_head": assembler.REPOSITORY_HEAD,
        "repository_tree": assembler.REPOSITORY_TREE,
        "source_draw_db_sha256": dataset["source_db"]["sha256"],
        "dataset_snapshot_sha256": dataset["dataset_snapshot_sha256"],
        "target_count": 800,
        "target_order_sha256": targets["target_order_sha256"],
        "strategy_count": 54,
        "strategy_order_sha256": assembler.EXPECTED_STRATEGY_ORDER_SHA256,
        "strategy_universe_sha256": assembler.EXPECTED_STRATEGY_UNIVERSE_SHA256,
        "rng_classification_sha256": assembler.EXPECTED_RNG_CLASSIFICATION_SHA256,
        "runtime_fingerprint_sha256": runtime_hash,
        "process_model": "ONE_PROCESS_PER_STRATEGY",
        "seed_timing": "POST_IMPORT_CATALOG_ADAPTER_CONSTRUCTION_PRE_TARGET_1",
        "global_random_policy": (
            "PER_STRATEGY_STDLIB_MODULE_GLOBAL_RANDOM_CONTINUOUS_800_TARGET_STREAM"
        ),
        "cache_policy": "NO_REPLAY_RESULT_CACHE",
        "strategy_parallelization": "SERIAL_ONLY",
        "max_concurrency": 1,
        "failure_restart_boundary": "ENTIRE_STRATEGY_PROCESS",
        "metric_contract": "M3_PLUS",
        "window_order": list(assembler.EXPECTED_WINDOW_ORDER),
        "excluded_strategy_id": assembler.ZONE_STRATEGY_ID,
        "old_84_reuse": False,
    }
    common_hash = _digest(common)
    return _seal(
        {
            "manifest_schema_version": assembler.PLAN_MANIFEST_SCHEMA_VERSION,
            "canonicalization_version": assembler.CANONICALIZATION_VERSION,
            "protocol_version": assembler.PROTOCOL_VERSION,
            "common_manifest": common,
            "common_manifest_sha256": common_hash,
            "authority": authority,
            "dataset": dataset,
            "targets": targets,
            "strategies": strategies,
            "rng": _rng(strategies, common_hash),
            "runtime_fingerprint": runtime,
            "runtime_fingerprint_sha256": runtime_hash,
            "execution": copy.deepcopy(assembler.EXPECTED_EXECUTION),
            "evaluation": copy.deepcopy(assembler.EXPECTED_EVALUATION),
        },
        "plan_manifest_sha256",
    )


def _success_count(strategy_index: int, window_index: int, eligible: int) -> int:
    count_50 = (strategy_index * 7) % 51
    count_300 = count_50 + (strategy_index * 11) % 251
    count_750 = count_300 + (strategy_index * 13) % 451
    count_800 = count_750 + (strategy_index * 17) % 51
    assert eligible == assembler.EXPECTED_WINDOW_ELIGIBLE_COUNTS[window_index]
    return (count_50, count_300, count_750, count_800)[window_index]


def _draw_key(row: Document) -> tuple[str, int]:
    return cast(str, row["draw_date"]), int(cast(str, row["draw_number"]))


def _target_identity(row: Document) -> Document:
    return {"draw_date": row["draw_date"], "draw_number": row["draw_number"]}


def _causal_row(row: Document) -> Document:
    return {key: row[key] for key in ("draw_date", "draw_number", "main_numbers", "special_number")}


def _adapter_row(row: Document) -> Document:
    return {
        "draw": row["draw_number"],
        "date": row["draw_date"],
        "numbers": row["main_numbers"],
    }


def _target_contexts(plan: Document) -> list[Document]:
    rows = cast(list[Document], plan["dataset"]["snapshot"]["draws"])
    by_number = {row["draw_number"]: row for row in rows}
    contexts: list[Document] = []
    for target in plan["targets"]["vector"]:
        history = [row for row in rows if _draw_key(row) < _draw_key(target)]
        outcome = _causal_row(by_number[target["draw_number"]])
        contexts.append(
            {
                "target": target,
                "outcome": outcome,
                "outcome_sha256": _digest(outcome),
                "causal_history_count": len(history),
                "cutoff": _target_identity(history[-1]),
                "causal_history_sha256": _digest([_causal_row(row) for row in history]),
                "adapter_input_sha256": _digest([_adapter_row(row) for row in history]),
            }
        )
    return contexts


def _seeded_state_digest(seed: Document) -> str:
    state = random.Random(int(seed["seed_integer"])).getstate()
    assert len(state) == 3 and state[0] == 3 and state[2] is None
    return _digest(
        {
            "state_version": 3,
            "mt19937_state": list(state[1]),
            "gaussian_cache": "NONE",
        }
    )


def _snapshot_hash(plan: Document, identity: Document, context: Document, ticket: list[int]) -> str:
    strategy_name = next(
        row["strategy_name"]
        for row in plan["strategies"]["names"]
        if row["strategy_id"] == identity["strategy_id"]
    )
    return _digest(
        {
            "snapshot_schema_version": "1.0.0",
            "dataset_id": plan["dataset"]["dataset_id"],
            "dataset_version": plan["dataset"]["dataset_version"],
            "lottery_type": "BIG_LOTTO",
            "source_mode": "TARGET_NATIVE",
            "target_draw_number": context["target"]["draw_number"],
            "target_draw_date": context["target"]["draw_date"],
            "cutoff_draw_number": context["cutoff"]["draw_number"],
            "cutoff_draw_date": context["cutoff"]["draw_date"],
            "strategy_id": identity["strategy_id"],
            "strategy_version": identity["strategy_version"],
            "adapter_strategy_id": identity["strategy_id"],
            "adapter_strategy_name": strategy_name,
            "adapter_strategy_version": identity["strategy_version"],
            "history_status": "OK",
            "causal_history_count": context["causal_history_count"],
            "causal_history_sha256": context["causal_history_sha256"],
            "prediction_status": "OK",
            "predicted_main_numbers": ticket,
        }
    )


def _source_integrity(plan: Document, identity: Document) -> Document:
    inventory = {row["path"]: row["sha256"] for row in plan["authority"]["load_bearing_blobs"]}
    names = sorted(
        {
            "lottolab",
            "lottolab.application.use_cases.replay_historical_predictions",
            "lottolab.strategies.catalog",
            identity["adapter_path"].split(":")[0],
        }
    )
    modules = [
        {
            "module": name,
            "path": _module_path(name),
            "sha256": inventory[_module_path(name)],
        }
        for name in names
    ]
    return {
        "repository_head": assembler.REPOSITORY_HEAD,
        "repository_tree": assembler.REPOSITORY_TREE,
        "source_inventory_sha256_before": plan["authority"]["source_inventory_sha256"],
        "source_inventory_sha256_after": plan["authority"]["source_inventory_sha256"],
        "source_draw_db_sha256_before": plan["dataset"]["source_db"]["sha256"],
        "source_draw_db_sha256_after": plan["dataset"]["source_db"]["sha256"],
        "import_anchor_verified": True,
        "imported_modules": modules,
    }


def _success_flags(strategy_index: int) -> list[bool]:
    count_50, count_300, count_750, count_800 = [
        _success_count(strategy_index, index, eligible)
        for index, eligible in enumerate(assembler.EXPECTED_WINDOW_ELIGIBLE_COUNTS)
    ]
    shell_counts = (
        count_800 - count_750,
        count_750 - count_300,
        count_300 - count_50,
        count_50,
    )
    shell_ranges = ((0, 50), (50, 500), (500, 750), (750, 800))
    flags = [False] * assembler.EXPECTED_REPLAY_DEPTH
    for count, (start, stop) in zip(shell_counts, shell_ranges, strict=True):
        assert 0 <= count <= stop - start
        for index in range(start, start + count):
            flags[index] = True
    return flags


def _strategy_result(
    plan: Document,
    contexts: list[Document],
    identity: Document,
    strategy_index: int,
) -> Document:
    seed = cast(list[Document], plan["rng"]["seeds"])[strategy_index - 1]
    state = _seeded_state_digest(seed)
    cells: list[Document] = []
    for context, success in zip(contexts, _success_flags(strategy_index), strict=True):
        ticket = [1, 2, 3, 8, 9, 10] if success else [8, 9, 10, 11, 12, 13]
        cell: Document = {
            **context,
            "strategy_id": identity["strategy_id"],
            "strategy_version": identity["strategy_version"],
            "history_status": "OK",
            "history_reason": "NONE",
            "prediction_status": "OK",
            "prediction_reason": "NONE",
            "emitted_ticket": ticket,
            "legal_ticket": ticket,
            "hit_count": 3 if success else 0,
            "rng_before_sha256": state,
            "rng_after_sha256": state,
            "replay_result_sha256": _snapshot_hash(plan, identity, context, ticket),
        }
        cell["cell_sha256"] = _digest(cell)
        cells.append(cell)
    result: Document = {
        "result_schema_version": "NEXT_DRAW_54_STRATEGY_RESULT_V2",
        "strategy_identity": identity,
        "seed": seed,
        "rng_class": _rng_class(cast(str, identity["strategy_id"])),
        "bootstrap_rng_guard": {"unchanged": True, "state_version": 3},
        "post_seed_rng_sha256": state,
        "final_rng_sha256": state,
        "adapter_invocation_count": assembler.EXPECTED_REPLAY_DEPTH,
        "cache": copy.deepcopy(assembler.EXPECTED_CACHE_ZERO),
        "source_integrity": _source_integrity(plan, identity),
        "runtime_fingerprint_sha256": plan["runtime_fingerprint_sha256"],
        "cells": cells,
        "final_status": "COMPLETE",
    }
    result["strategy_output_sha256"] = _digest(result)
    return result


def _strategy_results(plan: Document) -> list[Document]:
    contexts = _target_contexts(plan)
    return [
        _strategy_result(plan, contexts, identity, index)
        for index, identity in enumerate(plan["strategies"]["records"], 1)
    ]


def _evaluation_records() -> list[Document]:
    records: list[Document] = []
    for strategy_index, strategy_id in enumerate(assembler.EXPECTED_STRATEGY_IDS, 1):
        windows: list[Document] = []
        for window_index, (label, eligible) in enumerate(
            zip(
                assembler.EXPECTED_WINDOW_ORDER,
                assembler.EXPECTED_WINDOW_ELIGIBLE_COUNTS,
                strict=True,
            )
        ):
            success = _success_count(strategy_index, window_index, eligible)
            windows.append(
                {
                    "window": label,
                    "success_count": success,
                    "eligible_draw_count": eligible,
                    "observed_value": _pair(Fraction(success, eligible)),
                }
            )
        records.append({"strategy_id": strategy_id, "windows": windows})
    return records


def _artifact(plan: Document, evaluations: list[Document], *, synthetic: bool) -> Document:
    names = {row["strategy_id"]: row["strategy_name"] for row in plan["strategies"]["names"]}
    records: list[Document] = []
    for evaluation in evaluations:
        windows: list[Document] = []
        for source in evaluation["windows"]:
            observed = Fraction(source["success_count"], source["eligible_draw_count"])
            windows.append(
                {
                    "window_kind": source["window"],
                    "window_status": "COMPLETE",
                    "eligible_draw_count": source["eligible_draw_count"],
                    "observed_value": _pair(observed),
                    "random_reference": _pair(assembler.EXPECTED_RANDOM_REFERENCE),
                    "delta_vs_random": _pair(observed - assembler.EXPECTED_RANDOM_REFERENCE),
                }
            )
        strategy_id = evaluation["strategy_id"]
        records.append(
            {
                "strategy_id": strategy_id,
                "strategy_name": names[strategy_id],
                "native_ticket_count": 1,
                "status": "EVALUATED",
                "hit_tier_id": "M3_PLUS",
                "windows": windows,
            }
        )
    excluded = plan["strategies"]["excluded"]
    records.insert(
        18,
        {
            "strategy_id": excluded["strategy_id"],
            "strategy_name": excluded["strategy_name"],
            "native_ticket_count": 1,
            "status": "DRIVER_ERROR",
            "hit_tier_id": "M3_PLUS",
            "windows": [],
        },
    )
    return _seal(
        {
            "artifact_schema_version": assembler.ARTIFACT_SCHEMA_VERSION,
            "evaluator_version": "base_method_evaluation/1.0.0",
            "window_order": list(assembler.EXPECTED_WINDOW_ORDER),
            "computation_status": (
                assembler.SYNTHETIC_COMPUTATION_STATUS
                if synthetic
                else assembler.REAL_COMPUTATION_STATUS
            ),
            "lottery_type": "BIG_LOTTO",
            "source_draw_db_sha256": plan["dataset"]["source_db"]["sha256"],
            "source_draw_count": len(plan["dataset"]["snapshot"]["draws"]),
            "last_causal_draw_id": plan["targets"]["vector"][-1]["draw_number"],
            "replay_depth": 800,
            "hit_tier_id": "M3_PLUS",
            "records": records,
        },
        "artifact_sha256",
    )


def _deterministic_payload(plan: Document, *, synthetic: bool) -> Document:
    strategy_results = _strategy_results(plan)
    evaluations = _evaluation_records()
    artifact = _artifact(plan, evaluations, synthetic=synthetic)
    matrix = [
        result["cells"][target_index]["cell_sha256"]
        for target_index in range(assembler.EXPECTED_REPLAY_DEPTH)
        for result in strategy_results
    ]
    return {
        "runtime_fingerprint": copy.deepcopy(plan["runtime_fingerprint"]),
        "authority": copy.deepcopy(plan["authority"]),
        "strategy_results": strategy_results,
        "matrix_order": "TARGET_MAJOR_STRATEGY_MINOR",
        "matrix_cell_count": assembler.EXPECTED_EVALUATED_CELL_COUNT,
        "matrix": matrix,
        "matrix_sha256": _digest(matrix),
        "evaluation_records": evaluations,
        "evaluation_sha256": _digest(evaluations),
        "excluded_strategy": copy.deepcopy(plan["strategies"]["excluded"]),
        "artifact": artifact,
        "artifact_content_sha256": artifact["artifact_sha256"],
        "artifact_file_sha256": _file_digest(artifact),
        "old_84_reuse": False,
        "final_status": (
            assembler.SYNTHETIC_FINAL_STATUS if synthetic else assembler.REAL_FINAL_STATUS
        ),
    }


def _timestamp(day_offset: int) -> str:
    value = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day_offset)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _operational(results: list[Document], label: str, *, day_offset: int) -> Document:
    attempts = [
        {
            "attempt_id": f"{label}-{index:02d}-01",
            "strategy_id": result["strategy_identity"]["strategy_id"],
            "ordinal": 1,
            "pid": 1000 + index,
            "started_at_utc": _timestamp(day_offset),
            "ended_at_utc": _timestamp(day_offset),
            "elapsed_ns": 1,
            "exit_status": 0,
            "status": "SUCCEEDED",
            "failure_kind": "",
            "previous_attempt_id": "",
            "result_sha256": result["strategy_output_sha256"],
            "partial_output_sha256": "",
            "bootstrap_before_sha256": ZERO_SHA,
            "bootstrap_after_sha256": ZERO_SHA,
        }
        for index, result in enumerate(results, 1)
    ]
    return {
        "run_id": label,
        "output_root": f"/fixture/{label}",
        "source_root": "/fixture/source",
        "source_db_path": "/fixture/source.sqlite3",
        "host_label": "fixture-host",
        "started_at_utc": _timestamp(day_offset),
        "ended_at_utc": _timestamp(day_offset),
        "elapsed_ns": 54,
        "attempts": attempts,
    }


def _run(plan: Document, deterministic: Document, label: str, day_offset: int) -> Document:
    results = cast(list[Document], deterministic["strategy_results"])
    return _seal(
        {
            "manifest_schema_version": assembler.RUN_MANIFEST_SCHEMA_VERSION,
            "canonicalization_version": assembler.CANONICALIZATION_VERSION,
            "protocol_version": assembler.PROTOCOL_VERSION,
            "plan_manifest_sha256": plan["plan_manifest_sha256"],
            "common_manifest_sha256": plan["common_manifest_sha256"],
            "campaign_label": f"CAMPAIGN_{label.upper()}",
            "operational_envelope": _operational(results, label, day_offset=day_offset),
            "deterministic_payload": copy.deepcopy(deterministic),
            "deterministic_payload_sha256": _digest(deterministic),
        },
        "run_manifest_sha256",
    )


def _acceptance(plan: Document, run_a: Document, run_b: Document) -> Document:
    return _seal(
        {
            "manifest_schema_version": assembler.ACCEPTANCE_MANIFEST_SCHEMA_VERSION,
            "canonicalization_version": assembler.CANONICALIZATION_VERSION,
            "protocol_version": assembler.PROTOCOL_VERSION,
            "plan_manifest_sha256": plan["plan_manifest_sha256"],
            "common_manifest_sha256": plan["common_manifest_sha256"],
            "run_a_manifest_file_sha256": _file_digest(run_a),
            "run_b_manifest_file_sha256": _file_digest(run_b),
            "run_a_deterministic_payload_sha256": run_a["deterministic_payload_sha256"],
            "run_b_deterministic_payload_sha256": run_b["deterministic_payload_sha256"],
            "comparison_contract": "EXACT_LF_FREE_LCJ1_DETERMINISTIC_PAYLOAD_BYTES",
            "comparison_results": copy.deepcopy(assembler.EXPECTED_COMPARISON_RESULTS),
            "old_84_reuse_attestation": False,
            "final_status": run_a["deterministic_payload"]["final_status"],
        },
        "acceptance_manifest_sha256",
    )


@lru_cache(maxsize=2)
def _cached_bundle(synthetic: bool) -> Bundle:
    plan = _plan(synthetic=synthetic)
    deterministic = _deterministic_payload(plan, synthetic=synthetic)
    run_a = _run(plan, deterministic, "run-a", 0)
    run_b = _run(plan, deterministic, "run-b", 1)
    return Bundle(plan, run_a, run_b, _acceptance(plan, run_a, run_b))


def _bundle(*, synthetic: bool = True) -> Bundle:
    return copy.deepcopy(_cached_bundle(synthetic))


def _assemble(bundle: Bundle, *, synthetic_test: bool = True) -> Document:
    return assembler.assemble_artifact(
        bundle.plan,
        bundle.run_a,
        bundle.run_b,
        bundle.acceptance,
        synthetic_test=synthetic_test,
    )


def _resign_run(run: Document) -> Document:
    deterministic = run["deterministic_payload"]
    artifact = _seal(deterministic["artifact"], "artifact_sha256")
    deterministic["artifact"] = artifact
    deterministic["artifact_content_sha256"] = artifact["artifact_sha256"]
    deterministic["artifact_file_sha256"] = _file_digest(artifact)
    deterministic["matrix_sha256"] = _digest(deterministic["matrix"])
    deterministic["evaluation_sha256"] = _digest(deterministic["evaluation_records"])
    run["deterministic_payload_sha256"] = _digest(deterministic)
    return _seal(run, "run_manifest_sha256")


def _rebind_plan_and_downstream_documents(bundle: Bundle) -> Bundle:
    plan = bundle.plan
    snapshot = plan["dataset"]["snapshot"]
    plan["dataset"]["dataset_version"] = _digest(snapshot)
    plan["dataset"]["dataset_snapshot_sha256"] = _digest(snapshot)
    plan["targets"]["target_order_sha256"] = _digest(plan["targets"]["vector"])
    plan["common_manifest"]["dataset_snapshot_sha256"] = plan["dataset"]["dataset_snapshot_sha256"]
    plan["common_manifest"]["target_order_sha256"] = plan["targets"]["target_order_sha256"]
    plan["common_manifest_sha256"] = _digest(plan["common_manifest"])
    plan["rng"] = _rng(plan["strategies"], plan["common_manifest_sha256"])
    bundle.plan = _seal(plan, "plan_manifest_sha256")

    for field in ("run_a", "run_b"):
        run = getattr(bundle, field)
        run["plan_manifest_sha256"] = bundle.plan["plan_manifest_sha256"]
        run["common_manifest_sha256"] = bundle.plan["common_manifest_sha256"]
        setattr(bundle, field, _resign_run(run))
    bundle.acceptance = _acceptance(bundle.plan, bundle.run_a, bundle.run_b)
    return bundle


def test_four_direct_canonical_runner_documents_round_trip_embedded_artifact() -> None:
    bundle = _bundle()
    artifact = _assemble(bundle)
    direct = bundle.run_a["deterministic_payload"]["artifact"]

    assert canonical_bytes(artifact) == canonical_bytes(direct)
    assert artifact["artifact_sha256"] == direct["artifact_sha256"]
    assert len(artifact["records"]) == 55
    assert sum(record["status"] == "EVALUATED" for record in artifact["records"]) == 54
    assert artifact["records"][18]["strategy_id"] == assembler.ZONE_STRATEGY_ID
    assert artifact["records"][18]["status"] == "DRIVER_ERROR"
    assert artifact["records"][18]["windows"] == []


def test_run_a_b_are_operationally_distinct_but_deterministically_identical() -> None:
    bundle = _bundle()
    assert bundle.run_a["run_manifest_sha256"] != bundle.run_b["run_manifest_sha256"]
    assert canonical_file_bytes(bundle.run_a) != canonical_file_bytes(bundle.run_b)
    assert bundle.run_a["campaign_label"] != bundle.run_b["campaign_label"]
    assert (
        bundle.run_a["operational_envelope"]["run_id"]
        != bundle.run_b["operational_envelope"]["run_id"]
    )
    assert canonical_bytes(bundle.run_a["deterministic_payload"]) == canonical_bytes(
        bundle.run_b["deterministic_payload"]
    )
    assert canonical_bytes(bundle.run_a["deterministic_payload"]["artifact"]) == (
        canonical_bytes(bundle.run_b["deterministic_payload"]["artifact"])
    )
    _assemble(bundle)


def test_frozen_windows_counts_metric_and_reduced_fraction_semantics() -> None:
    artifact = _assemble(_bundle())
    for record in artifact["records"]:
        if record["strategy_id"] == assembler.ZONE_STRATEGY_ID:
            continue
        assert [window["window_kind"] for window in record["windows"]] == list(
            assembler.EXPECTED_WINDOW_ORDER
        )
        assert [window["eligible_draw_count"] for window in record["windows"]] == list(
            assembler.EXPECTED_WINDOW_ELIGIBLE_COUNTS
        )
        for window in record["windows"]:
            assert Fraction(
                int(window["random_reference"]["numerator"]),
                int(window["random_reference"]["denominator"]),
            ) == Fraction(4654, 249711)


def test_real_pass_path_accepts_and_synthetic_path_is_strictly_separated() -> None:
    real = _bundle(synthetic=False)
    artifact = _assemble(real, synthetic_test=False)
    assert real.acceptance["final_status"] == "PASS"
    assert artifact["computation_status"] == "FRESH_UNREVIEWED"

    with pytest.raises(assembler.EvidenceAssemblyError, match="SYNTHETIC_TEST_ONLY"):
        _assemble(_bundle(), synthetic_test=False)
    with pytest.raises(assembler.EvidenceAssemblyError, match="synthetic-test path"):
        _assemble(real, synthetic_test=True)


def test_exact_canonical_files_use_lcj1_one_lf_and_emit_direct_artifact(
    tmp_path: Path,
) -> None:
    bundle = _bundle()
    documents = {
        "plan.json": bundle.plan,
        "run-a.json": bundle.run_a,
        "run-b.json": bundle.run_b,
        "acceptance.json": bundle.acceptance,
    }
    for name, document in documents.items():
        raw = canonical_file_bytes(document)
        assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
        (tmp_path / name).write_bytes(raw)

    output = tmp_path / "artifact.json"
    artifact = assembler.assemble_from_paths(
        plan_path=tmp_path / "plan.json",
        run_a_path=tmp_path / "run-a.json",
        run_b_path=tmp_path / "run-b.json",
        acceptance_path=tmp_path / "acceptance.json",
        output_path=output,
        synthetic_test=True,
    )
    assert output.read_bytes() == canonical_file_bytes(
        bundle.run_a["deterministic_payload"]["artifact"]
    )
    assert assembler.load_artifact_file(output, synthetic_test=True) == artifact

    invalid = tmp_path / "invalid-plan.json"
    invalid.write_bytes(canonical_file_bytes(bundle.plan) + b"\n")
    with pytest.raises(assembler.EvidenceAssemblyError, match="exactly one"):
        assembler.load_manifest_file(invalid)


def test_no_old_wrapper_translation_or_compatibility_api_remains() -> None:
    assert not hasattr(assembler, "build_evidence")
    assert not hasattr(assembler, "seal_manifest")
    assert not hasattr(assembler, "seal_run_manifest")
    assert not hasattr(assembler, "deterministic_run_sha256")
    parameters = list(inspect.signature(assembler.assemble_artifact).parameters)
    assert parameters == ["plan", "run_a", "run_b", "acceptance", "synthetic_test"]
    source = inspect.getsource(assembler)
    for translated_key in (
        '"canonicalization"',
        '"manifest_sha256"',
        '"acceptance_status"',
        '"run_a_manifest_sha256"',
        '"run_b_manifest_sha256"',
    ):
        assert translated_key not in source


@pytest.mark.parametrize("document_name", ["plan", "run_a", "run_b", "acceptance"])
def test_each_document_self_hash_is_load_bearing(document_name: str) -> None:
    bundle = _bundle()
    document = getattr(bundle, document_name)
    document["post_seal_tamper"] = True
    with pytest.raises(assembler.EvidenceAssemblyError):
        _assemble(bundle)


@pytest.mark.parametrize("document_name", ["plan", "run_a", "acceptance"])
def test_superseded_protocol_is_rejected_directly(document_name: str) -> None:
    bundle = _bundle()
    document = getattr(bundle, document_name)
    document["protocol_version"] = "NEXT_DRAW_54_REACHABLE_FULL_REPLAY_PROTOCOL_R1"
    key = {
        "plan": "plan_manifest_sha256",
        "run_a": "run_manifest_sha256",
        "acceptance": "acceptance_manifest_sha256",
    }[document_name]
    setattr(bundle, document_name, _seal(document, key))
    with pytest.raises(assembler.EvidenceAssemblyError, match="superseded"):
        _assemble(bundle)


def test_one_run_identity_cannot_fill_both_slots() -> None:
    bundle = _bundle()
    acceptance = _acceptance(bundle.plan, bundle.run_a, bundle.run_a)
    with pytest.raises(assembler.EvidenceAssemblyError, match="distinct run identities"):
        assembler.assemble_artifact(
            bundle.plan,
            bundle.run_a,
            bundle.run_a,
            acceptance,
            synthetic_test=True,
        )


@pytest.mark.parametrize("field", ["run_id", "output_root"])
def test_run_operational_identities_must_be_distinct(field: str) -> None:
    bundle = _bundle()
    bundle.run_b["operational_envelope"][field] = bundle.run_a["operational_envelope"][field]
    bundle = Bundle(
        bundle.plan,
        bundle.run_a,
        _resign_run(bundle.run_b),
        bundle.acceptance,
    )
    bundle = Bundle(
        bundle.plan,
        bundle.run_a,
        bundle.run_b,
        _acceptance(bundle.plan, bundle.run_a, bundle.run_b),
    )
    with pytest.raises(assembler.EvidenceAssemblyError, match=r"run IDs|output roots"):
        _assemble(bundle)


@pytest.mark.parametrize("case", ["reordered", "missing", "duplicate"])
def test_strategy_order_missing_and_duplicate_controls(case: str) -> None:
    bundle = _bundle()
    records = bundle.plan["strategies"]["records"]
    if case == "reordered":
        records[0], records[1] = records[1], records[0]
    elif case == "missing":
        records.pop()
    else:
        records[1]["strategy_id"] = records[0]["strategy_id"]
    bundle.plan = _seal(bundle.plan, "plan_manifest_sha256")
    with pytest.raises(assembler.EvidenceAssemblyError):
        _assemble(bundle)


def test_fully_resealed_and_rebound_target_reorder_is_rejected() -> None:
    bundle = _bundle()
    vector = bundle.plan["targets"]["vector"]
    vector[0], vector[1] = vector[1], vector[0]
    bundle = _rebind_plan_and_downstream_documents(bundle)

    assert bundle.run_a["plan_manifest_sha256"] == bundle.plan["plan_manifest_sha256"]
    assert bundle.run_b["common_manifest_sha256"] == bundle.plan["common_manifest_sha256"]
    assert bundle.acceptance["run_a_manifest_file_sha256"] == _file_digest(bundle.run_a)
    assert bundle.acceptance["run_b_manifest_file_sha256"] == _file_digest(bundle.run_b)
    with pytest.raises(
        assembler.EvidenceAssemblyError,
        match="exact dataset-derived frozen 800-target vector",
    ):
        _assemble(bundle)


def test_fully_resealed_plan_with_ineligible_target_history_is_rejected() -> None:
    bundle = _bundle()
    snapshot = bundle.plan["dataset"]["snapshot"]
    snapshot["draws"] = snapshot["draws"][-assembler.EXPECTED_REPLAY_DEPTH :]
    bundle = _rebind_plan_and_downstream_documents(bundle)

    assert bundle.plan["targets"]["vector"] == [
        {"draw_date": row["draw_date"], "draw_number": row["draw_number"]}
        for row in snapshot["draws"]
    ]
    with pytest.raises(
        assembler.EvidenceAssemblyError,
        match="all 43,200 cells must be eligible",
    ):
        _assemble(bundle)


def test_old_84_reuse_true_is_rejected_even_when_plan_is_resealed() -> None:
    bundle = _bundle()
    bundle.plan["execution"]["old_84_reuse"] = True
    bundle.plan = _seal(bundle.plan, "plan_manifest_sha256")
    with pytest.raises(assembler.EvidenceAssemblyError, match=r"plan\.execution"):
        _assemble(bundle)


def test_nonaccepted_final_status_is_rejected() -> None:
    bundle = _bundle()
    bundle.acceptance["final_status"] = "FAIL"
    bundle.acceptance = _seal(bundle.acceptance, "acceptance_manifest_sha256")
    with pytest.raises(assembler.EvidenceAssemblyError, match="final_status"):
        _assemble(bundle)


def test_empirical_zone_record_is_rejected() -> None:
    bundle = _bundle()
    zone = bundle.run_a["deterministic_payload"]["artifact"]["records"][18]
    zone["status"] = "EVALUATED"
    bundle = Bundle(
        bundle.plan,
        _resign_run(bundle.run_a),
        bundle.run_b,
        bundle.acceptance,
    )
    with pytest.raises(assembler.EvidenceAssemblyError, match="DRIVER_ERROR"):
        _assemble(bundle)


def test_altered_window_contract_is_rejected() -> None:
    bundle = _bundle()
    window = bundle.run_a["deterministic_payload"]["artifact"]["records"][0]["windows"][0]
    window["eligible_draw_count"] = 49
    bundle = Bundle(
        bundle.plan,
        _resign_run(bundle.run_a),
        bundle.run_b,
        bundle.acceptance,
    )
    with pytest.raises(assembler.EvidenceAssemblyError, match="window contract"):
        _assemble(bundle)


def test_deterministic_payload_mismatch_is_rejected_after_valid_resealing() -> None:
    bundle = _bundle()
    bundle.run_b["deterministic_payload"]["matrix"][0] = "9" * 64
    run_b = _resign_run(bundle.run_b)
    acceptance = _acceptance(bundle.plan, bundle.run_a, run_b)
    mismatched = Bundle(bundle.plan, bundle.run_a, run_b, acceptance)
    with pytest.raises(assembler.EvidenceAssemblyError, match=r"matrix\.canonical_cells"):
        _assemble(mismatched)


def test_fully_resigned_cells_to_renamed_cells_is_rejected() -> None:
    bundle = _bundle()
    for field in ("run_a", "run_b"):
        run = getattr(bundle, field)
        result = run["deterministic_payload"]["strategy_results"][0]
        result["renamed_cells"] = result.pop("cells")
        result = _seal(result, "strategy_output_sha256")
        run["deterministic_payload"]["strategy_results"][0] = result
        run["operational_envelope"]["attempts"][0]["result_sha256"] = result[
            "strategy_output_sha256"
        ]
        setattr(bundle, field, _resign_run(run))
    bundle.acceptance = _acceptance(bundle.plan, bundle.run_a, bundle.run_b)

    with pytest.raises(assembler.EvidenceAssemblyError, match="canonical Runner keys"):
        _assemble(bundle)


def test_fully_resigned_matrix_inconsistent_with_canonical_cells_is_rejected() -> None:
    bundle = _bundle()
    for field in ("run_a", "run_b"):
        run = getattr(bundle, field)
        run["deterministic_payload"]["matrix"][0] = "9" * 64
        setattr(bundle, field, _resign_run(run))
    bundle.acceptance = _acceptance(bundle.plan, bundle.run_a, bundle.run_b)

    with pytest.raises(assembler.EvidenceAssemblyError, match="canonical_cells"):
        _assemble(bundle)


def test_acceptance_file_hash_binding_is_load_bearing() -> None:
    bundle = _bundle()
    bundle.acceptance["run_a_manifest_file_sha256"] = "8" * 64
    bundle.acceptance = _seal(bundle.acceptance, "acceptance_manifest_sha256")
    with pytest.raises(assembler.EvidenceAssemblyError, match="file_sha256"):
        _assemble(bundle)


@pytest.mark.parametrize("kind", ["wrapper", "renamed_plan", "renamed_run", "renamed_acceptance"])
def test_old_local_wrapper_and_translated_fields_are_rejected(kind: str) -> None:
    bundle = _bundle()
    if kind == "wrapper":
        plan: Document = {"plan": bundle.plan}
    else:
        plan = bundle.plan
        target = {
            "renamed_plan": plan,
            "renamed_run": bundle.run_a,
            "renamed_acceptance": bundle.acceptance,
        }[kind]
        old, new = {
            "renamed_plan": ("canonicalization_version", "canonicalization"),
            "renamed_run": ("run_manifest_sha256", "manifest_sha256"),
            "renamed_acceptance": (
                "acceptance_manifest_sha256",
                "manifest_sha256",
            ),
        }[kind]
        target[new] = target.pop(old)
    with pytest.raises(assembler.EvidenceAssemblyError, match="canonical Runner keys"):
        assembler.assemble_artifact(
            plan,
            bundle.run_a,
            bundle.run_b,
            bundle.acceptance,
            synthetic_test=True,
        )


def test_packaged_v1_output_is_refused_before_input_reads(tmp_path: Path) -> None:
    protected = (
        tmp_path / "src/lottolab/strategies/data/biglotto_next_draw_recommendation_evidence_v1.json"
    )
    with pytest.raises(assembler.EvidenceAssemblyError, match="refusing to overwrite"):
        assembler.assemble_from_paths(
            plan_path=tmp_path / "unused-plan.json",
            run_a_path=tmp_path / "unused-run-a.json",
            run_b_path=tmp_path / "unused-run-b.json",
            acceptance_path=tmp_path / "unused-acceptance.json",
            output_path=protected,
        )


def _runner_root() -> Path:
    configured = os.environ.get("NEXT_DRAW_R2_RUNNER_ROOT")
    if configured:
        return Path(configured)
    return REPO_ROOT.parent / RUNNER_WORKTREE_NAME


def test_exact_runner_generated_objects_and_files_are_accepted_without_mapping(
    tmp_path: Path,
) -> None:
    runner_root = _runner_root()
    runner_test = runner_root / "tests/unit/test_next_draw_54_replay_r2.py"
    if not runner_test.is_file():
        pytest.skip("pinned Runner worktree is not available for cross-component integration")

    script = r"""
import copy
import importlib.util
import sys
from pathlib import Path

runner_root = Path(sys.argv[1])
assembler_root = Path(sys.argv[2])
output_root = Path(sys.argv[3])
sys.path.insert(0, str(assembler_root / "src"))
sys.path.insert(0, str(runner_root))

runner_spec = importlib.util.spec_from_file_location(
    "runner_contract_tests", runner_root / "tests/unit/test_next_draw_54_replay_r2.py"
)
assert runner_spec is not None and runner_spec.loader is not None
runner_tests = importlib.util.module_from_spec(runner_spec)
sys.modules[runner_spec.name] = runner_tests
runner_spec.loader.exec_module(runner_tests)
bundle = runner_tests._build_synthetic_bundle()
c = runner_tests.c

assembler_spec = importlib.util.spec_from_file_location(
    "direct_runner_assembler",
    assembler_root / "tools/build_biglotto_next_draw_recommendation_evidence_r2.py",
)
assert assembler_spec is not None and assembler_spec.loader is not None
assembler = importlib.util.module_from_spec(assembler_spec)
sys.modules[assembler_spec.name] = assembler
assembler_spec.loader.exec_module(assembler)

c.validate_run(bundle.plan, bundle.run_a)
artifact = assembler.assemble_artifact(
    bundle.plan, bundle.run_a, bundle.run_b, bundle.acceptance, synthetic_test=True
)
direct = bundle.run_a["deterministic_payload"]["artifact"]
assert c.canonical_bytes(artifact) == c.canonical_bytes(direct)

paths = {}
for name, document in (
    ("plan", bundle.plan),
    ("run-a", bundle.run_a),
    ("run-b", bundle.run_b),
    ("acceptance", bundle.acceptance),
):
    path = output_root / f"{name}.json"
    path.write_bytes(c.file_bytes(document))
    paths[name] = path
artifact_path = output_root / "artifact.json"
from_files = assembler.assemble_from_paths(
    plan_path=paths["plan"],
    run_a_path=paths["run-a"],
    run_b_path=paths["run-b"],
    acceptance_path=paths["acceptance"],
    output_path=artifact_path,
    synthetic_test=True,
)
assert c.canonical_bytes(from_files) == c.canonical_bytes(direct)
assert artifact_path.read_bytes() == c.file_bytes(direct)

def seal_run(run):
    run["deterministic_payload_sha256"] = c.digest(run["deterministic_payload"])
    return c.seal(run, "run_manifest_sha256")

def seal_acceptance(original, run_a, run_b):
    acceptance = copy.deepcopy(original)
    acceptance["run_a_manifest_file_sha256"] = c.sha256(c.file_bytes(run_a))
    acceptance["run_b_manifest_file_sha256"] = c.sha256(c.file_bytes(run_b))
    acceptance["run_a_deterministic_payload_sha256"] = run_a[
        "deterministic_payload_sha256"
    ]
    acceptance["run_b_deterministic_payload_sha256"] = run_b[
        "deterministic_payload_sha256"
    ]
    return c.seal(acceptance, "acceptance_manifest_sha256")

def assert_runner_and_assembler_reject(run_a, run_b, acceptance):
    try:
        c.validate_run(bundle.plan, run_a)
    except c.ProtocolError:
        pass
    else:
        raise AssertionError("canonical Runner admitted semantic tampering")
    try:
        assembler.assemble_artifact(
            bundle.plan, run_a, run_b, acceptance, synthetic_test=True
        )
    except assembler.EvidenceAssemblyError:
        pass
    else:
        raise AssertionError("Assembler admitted Runner-rejected semantic tampering")

renamed_a, renamed_b = copy.deepcopy(bundle.run_a), copy.deepcopy(bundle.run_b)
for run in (renamed_a, renamed_b):
    result = run["deterministic_payload"]["strategy_results"][0]
    result["renamed_cells"] = result.pop("cells")
    result = c.seal(result, "strategy_output_sha256")
    run["deterministic_payload"]["strategy_results"][0] = result
    run["operational_envelope"]["attempts"][0]["result_sha256"] = result[
        "strategy_output_sha256"
    ]
renamed_a, renamed_b = seal_run(renamed_a), seal_run(renamed_b)
renamed_acceptance = seal_acceptance(bundle.acceptance, renamed_a, renamed_b)
assert_runner_and_assembler_reject(renamed_a, renamed_b, renamed_acceptance)

matrix_a, matrix_b = copy.deepcopy(bundle.run_a), copy.deepcopy(bundle.run_b)
for run in (matrix_a, matrix_b):
    payload = run["deterministic_payload"]
    payload["matrix"][0] = "9" * 64
    payload["matrix_sha256"] = c.digest(payload["matrix"])
matrix_a, matrix_b = seal_run(matrix_a), seal_run(matrix_b)
matrix_acceptance = seal_acceptance(bundle.acceptance, matrix_a, matrix_b)
assert_runner_and_assembler_reject(matrix_a, matrix_b, matrix_acceptance)
"""
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(
        [sys.executable, "-c", script, str(runner_root), str(REPO_ROOT), str(tmp_path)],
        cwd=runner_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr
