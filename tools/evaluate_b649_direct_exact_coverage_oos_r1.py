#!/usr/bin/env python3
"""Two-phase strict PRE_DRAW evaluation of the frozen B649 selector.

``freeze`` reads only timestamped strategy predictions and pool provenance,
then writes the complete candidate and sealed-v6 portfolios to an immutable
artifact. ``score`` refuses to run without that artifact and only then opens
the outcome database read-only. This separation makes it auditable that every
target portfolio was fixed before any target outcome was read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import sys
import types
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPERATION_ROOT = REPO_ROOT.parent / ".task-data" / "B649_OPERATIONAL_PREDICTION_LOOP_R1"
DEFAULT_RESULT_DIR = (
    REPO_ROOT / "docs/research/matrix-native-results/b649-direct-exact-success-coverage-oos-r1"
)
DEFAULT_FREEZE_FILE = DEFAULT_RESULT_DIR / "frozen-portfolios.json"
DEFAULT_RESULT_FILE = DEFAULT_RESULT_DIR / "result.json"
DEFAULT_REPORT_FILE = DEFAULT_RESULT_DIR / "report.md"

TASK_ID = "B649_DIRECT_EXACT_SUCCESS_COVERAGE_VS_SEALED_V6_OOS_R1"
AS_OF_DATE = "2026-09-30"
WINDOW_START = 79
WINDOW_END = 93
PRIMARY_K = 10
SECONDARY_K = 20
KS = (PRIMARY_K, SECONDARY_K)

FROZEN_CANDIDATE_HEAD = "ff5b6006df61dc6df4e58fe77cbc93c4b8fda4d1"
FROZEN_CANDIDATE_TREE = "42dad2614cc3a43ec76599d44178251a38274700"
FROZEN_CANDIDATE_MODULE = "src/lottolab/research/b649_direct_exact_coverage_selector.py"
FROZEN_CANDIDATE_MODULE_SHA256 = "ff0d0ddf2ea05c80df7c0148ffc306bea79278a319d24d36156bc28df132362b"
CANONICAL_MAIN_HEAD = "87f2462558f5c5d5e0487d2230816b8f7bf8b386"
SEALED_V6_PATH = "src/lottolab/application/b649_sealed_geometry_portfolio.py"
SEALED_V6_BLOB = "46cf088e255b08b79beca22d6c2bb07e4b7a56ad"

POOL_AUTHORITY_COMMIT = "fbed3da52e4b6b8907afe71eed52e802b51a5cb0"
POOL_AUTHORITY_MODULE = "src/lottolab/application/b649_k_dpp_portfolio_selector.py"
POOL_AUTHORITY_MODULE_BLOB = "4178aaf1322e81f5249914312c7582a5ae76aae0"
POOL_BUILDER_MODULE = "src/lottolab/application/b649_operational_portfolio_selector.py"
POOL_BUILDER_BLOB = "0835137b804e245edd39850d8248c2b2c91a1076"
POOL_AUTHORITY_MODULE_SHA256 = "fb96b7f481d08dbea55b6dee42143fed5fa7cfe63055e1b581e92f3befb82576"

PREDICTION_SCHEMA = "b649-operational-prediction-v1"
OFFICIAL_SOURCE_NAME = "TAIWAN_LOTTERY_OFFICIAL_API"
_OUTCOME_KEYS = frozenset(
    {
        "outcome",
        "result",
        "result_numbers",
        "winning_numbers",
        "winning_main_numbers",
        "winning_special_number",
        "target_result",
        "target_result_used",
    }
)


class ReplayInputError(RuntimeError):
    """A source failed a strict replay authority or causality check."""


def _git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=not binary,
    )
    return completed.stdout if binary else completed.stdout.strip()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")


def _ticket_list(tickets: Sequence[Sequence[int]]) -> list[list[int]]:
    return [list(ticket) for ticket in tickets]


def _portfolio_sha256(tickets: Sequence[Sequence[int]]) -> str:
    return _sha256_bytes(_canonical_json(_ticket_list(tickets)))


def _pool_sha256(tickets: Sequence[Sequence[int]]) -> str:
    return _sha256_bytes(_canonical_json(_ticket_list(tickets)))


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _load_project_modules() -> None:
    src = str(REPO_ROOT / "src")
    repo = str(REPO_ROOT)
    if src not in sys.path:
        sys.path.insert(0, src)
    if repo not in sys.path:
        sys.path.insert(0, repo)


def _load_exact_pool_builder(repo: Path) -> tuple[Any, Any, dict[str, str]]:
    builder_blob = str(_git(repo, "rev-parse", f"{POOL_AUTHORITY_COMMIT}:{POOL_BUILDER_MODULE}"))
    authority_blob = str(
        _git(repo, "rev-parse", f"{POOL_AUTHORITY_COMMIT}:{POOL_AUTHORITY_MODULE}")
    )
    if builder_blob != POOL_BUILDER_BLOB:
        raise ReplayInputError(f"pinned pool builder blob drift: {builder_blob}")
    if authority_blob != POOL_AUTHORITY_MODULE_BLOB:
        raise ReplayInputError(f"pinned K-DPP authority blob drift: {authority_blob}")

    authority_bytes = _git(
        repo,
        "show",
        f"{POOL_AUTHORITY_COMMIT}:{POOL_AUTHORITY_MODULE}",
        binary=True,
    )
    builder_bytes = _git(
        repo,
        "show",
        f"{POOL_AUTHORITY_COMMIT}:{POOL_BUILDER_MODULE}",
        binary=True,
    )
    assert isinstance(authority_bytes, bytes) and isinstance(builder_bytes, bytes)
    authority_sha256 = _sha256_bytes(authority_bytes)
    if authority_sha256 != POOL_AUTHORITY_MODULE_SHA256:
        raise ReplayInputError(f"pinned K-DPP authority SHA-256 drift: {authority_sha256}")
    authority_text = authority_bytes.decode("utf-8")
    if "entries = build_candidate_pool(candidates, {})" not in authority_text:
        raise ReplayInputError("pinned K-DPP module no longer uses the empty-quality pool")

    module_name = "_b649_oos_r1_pinned_operational_pool_builder"
    module = types.ModuleType(module_name)
    module.__file__ = f"git:{POOL_AUTHORITY_COMMIT}:{POOL_BUILDER_MODULE}"
    sys.modules[module_name] = module
    exec(compile(builder_bytes, module.__file__, "exec"), module.__dict__)
    provenance = {
        "k_dpp_authority_commit": POOL_AUTHORITY_COMMIT,
        "k_dpp_authority_path": POOL_AUTHORITY_MODULE,
        "k_dpp_authority_blob": authority_blob,
        "k_dpp_authority_sha256": authority_sha256,
        "pool_builder_path": POOL_BUILDER_MODULE,
        "pool_builder_blob": builder_blob,
        "pool_builder_sha256": _sha256_bytes(builder_bytes),
        "pool_quality_map": "EMPTY",
        "pool_order": "support_count DESC, ticket ASC",
    }
    return module.build_candidate_pool, module.StrategyCandidate, provenance


def _validate_authorities(repo: Path) -> dict[str, object]:
    _load_project_modules()
    head = str(_git(repo, "rev-parse", "HEAD"))
    tree = str(_git(repo, "rev-parse", "HEAD^{tree}"))
    if (head, tree) != (FROZEN_CANDIDATE_HEAD, FROZEN_CANDIDATE_TREE):
        raise ReplayInputError(f"frozen candidate tree drift: HEAD={head} TREE={tree}")
    origin_main = str(_git(repo, "rev-parse", "origin/main"))
    remote_line = str(_git(repo, "ls-remote", "origin", "refs/heads/main"))
    remote_main = remote_line.split()[0] if remote_line else ""
    if origin_main != CANONICAL_MAIN_HEAD or remote_main != CANONICAL_MAIN_HEAD:
        raise ReplayInputError(
            f"CANONICAL_BASELINE_DRIFT: origin/main={origin_main}, remote/main={remote_main}"
        )

    candidate_path = repo / FROZEN_CANDIDATE_MODULE
    candidate_sha256 = _sha256_file(candidate_path)
    if candidate_sha256 != FROZEN_CANDIDATE_MODULE_SHA256:
        raise ReplayInputError(f"frozen candidate module SHA-256 drift: {candidate_sha256}")
    origin_sealed_blob = str(_git(repo, "rev-parse", f"origin/main:{SEALED_V6_PATH}"))
    head_sealed_blob = str(_git(repo, "rev-parse", f"HEAD:{SEALED_V6_PATH}"))
    if origin_sealed_blob != SEALED_V6_BLOB or head_sealed_blob != SEALED_V6_BLOB:
        raise ReplayInputError(
            "CANONICAL_BASELINE_DRIFT: sealed-v6 source blob differs from the resolved baseline"
        )

    from lottolab.application.b649_sealed_geometry_portfolio import (
        SEALED_GEOMETRY_METHOD_ID,
        SEALED_GEOMETRY_METHOD_VERSION,
        SEALED_GEOMETRY_PORTFOLIOS,
        sealed_geometry_buckets,
        verify_sealed_geometry_portfolio,
    )
    from lottolab.research.b649_direct_exact_coverage_selector import (
        GREEDY_TIE_BREAK,
        MAX_ACCEPTED_SWAPS,
        METHOD_ID,
        METHOD_VERSION,
        SWAP_TIE_BREAK,
    )
    from lottolab.research.b649_direct_exact_coverage_selector import (
        PRIMARY_K as CANDIDATE_PRIMARY_K,
    )
    from lottolab.research.b649_direct_exact_coverage_selector import (
        SECONDARY_K as CANDIDATE_SECONDARY_K,
    )

    if (SEALED_GEOMETRY_METHOD_ID, SEALED_GEOMETRY_METHOD_VERSION) != (
        "B649_SEALED_GEOMETRY_PORTFOLIO",
        "6.0.0",
    ):
        raise ReplayInputError(
            f"canonical baseline method drift: {SEALED_GEOMETRY_METHOD_ID} "
            f"{SEALED_GEOMETRY_METHOD_VERSION}"
        )
    if (METHOD_ID, METHOD_VERSION, CANDIDATE_PRIMARY_K, CANDIDATE_SECONDARY_K) != (
        "B649_DIRECT_EXACT_SUCCESS_COVERAGE_SELECTOR",
        "1.0.0",
        PRIMARY_K,
        SECONDARY_K,
    ):
        raise ReplayInputError("frozen candidate identity or K drift")
    if MAX_ACCEPTED_SWAPS != 2:
        raise ReplayInputError("frozen candidate swap bound drift")
    if GREEDY_TIE_BREAK != "EARLIEST_POOL_POSITION" or SWAP_TIE_BREAK != (
        "LEXICOGRAPHICALLY_SMALLEST_RESULTING_ASCENDING_RANK_VECTOR"
    ):
        raise ReplayInputError("frozen candidate tie-break drift")
    for k in KS:
        verify_sealed_geometry_portfolio(SEALED_GEOMETRY_PORTFOLIOS[k])
    sealed_geometry_buckets(KS)
    pool_builder, strategy_candidate_type, pool_provenance = _load_exact_pool_builder(repo)

    from tools.b649_operational_prediction_loop import STRATEGY_STREAMS

    enabled = tuple(stream for stream in STRATEGY_STREAMS if stream.enabled)
    if len(enabled) != 11 or len({stream.strategy_id for stream in enabled}) != 11:
        raise ReplayInputError("frozen operational stream catalog is not the expected 11 streams")
    registry = {
        stream.strategy_id: {
            "strategy_version": stream.strategy_version,
            "native_ticket_count": stream.native_ticket_count,
            "strategy_config": dict(stream.strategy_config),
            "producer_fingerprint": stream.producer_fingerprint,
            "pinned_implementation": stream.pinned_implementation,
        }
        for stream in enabled
    }
    return {
        "candidate_head": head,
        "candidate_tree": tree,
        "candidate_module_path": FROZEN_CANDIDATE_MODULE,
        "candidate_module_sha256": candidate_sha256,
        "canonical_origin_main_head": origin_main,
        "canonical_remote_main_head": remote_main,
        "canonical_sealed_v6_path": SEALED_V6_PATH,
        "canonical_sealed_v6_blob": origin_sealed_blob,
        "pool_authority": pool_provenance,
        "stream_catalog": registry,
        "pool_builder": pool_builder,
        "strategy_candidate_type": strategy_candidate_type,
    }


def _parse_aware(value: object, label: str) -> datetime:
    if type(value) is not str:
        raise ReplayInputError(f"{label} must be a timestamp string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReplayInputError(f"{label} is not ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReplayInputError(f"{label} must include a timezone")
    return parsed


def _validate_ticket(raw: object, label: str) -> tuple[int, ...]:
    if not isinstance(raw, list) or len(raw) != 6:
        raise ReplayInputError(f"{label} must contain six numbers")
    if any(type(n) is not int or not 1 <= n <= 49 for n in raw):
        raise ReplayInputError(f"{label} contains an out-of-range or non-integer number")
    ticket = tuple(raw)
    if tuple(sorted(set(ticket))) != ticket:
        raise ReplayInputError(f"{label} must be six distinct ascending numbers")
    return ticket


def _validate_prediction_record(
    record: Mapping[str, object],
    *,
    target: str,
    expected_streams: Mapping[str, Mapping[str, object]],
) -> tuple[str, tuple[tuple[int, ...], ...]]:
    if record.get("schema_version") != PREDICTION_SCHEMA:
        raise ReplayInputError(f"{target}: unexpected prediction schema")
    if record.get("task_id") != "B649_OPERATIONAL_PREDICTION_LOOP_R1":
        raise ReplayInputError(f"{target}: prediction task identity drift")
    if record.get("lottery_type") != "BIG_LOTTO" or str(record.get("draw_number")) != target:
        raise ReplayInputError(f"{target}: prediction target identity mismatch")
    strategy_id = record.get("strategy_id")
    if type(strategy_id) is not str or strategy_id not in expected_streams:
        raise ReplayInputError(f"{target}: unknown strategy id {strategy_id!r}")
    expected = expected_streams[strategy_id]
    for field in (
        "strategy_version",
        "strategy_config",
        "producer_fingerprint",
        "pinned_implementation",
    ):
        if record.get(field) != expected[field]:
            raise ReplayInputError(f"{target}/{strategy_id}: frozen stream {field} drift")
    legacy_single_stream_record = "availability" not in record
    if legacy_single_stream_record and strategy_id != "b649_new_horizon_minimax_disagreement_r1":
        raise ReplayInputError(f"{target}/{strategy_id}: unexpected legacy prediction schema")
    if (
        not legacy_single_stream_record
        and record.get("native_ticket_count") != expected["native_ticket_count"]
    ):
        raise ReplayInputError(f"{target}/{strategy_id}: native ticket count drift")
    if not legacy_single_stream_record and record.get("availability") != "AVAILABLE":
        raise ReplayInputError(
            f"{target}/{strategy_id}: unavailable stream {record.get('unavailable_reason')!r}"
        )
    if record.get("prediction_temporal_class") != "PRE_DRAW":
        raise ReplayInputError(f"{target}/{strategy_id}: prediction is not PRE_DRAW")
    created = _parse_aware(record.get("prediction_created_at"), "prediction_created_at")
    scheduled = _parse_aware(record.get("scheduled_at"), "scheduled_at")
    if not created < scheduled:
        raise ReplayInputError(f"{target}/{strategy_id}: prediction was not created before draw")
    if (
        not isinstance(record.get("draw_date"), str)
        or date.fromisoformat(record["draw_date"]) != scheduled.date()
    ):
        raise ReplayInputError(f"{target}/{strategy_id}: draw date and schedule disagree")
    cutoff = record.get("history_cutoff")
    if not isinstance(cutoff, Mapping):
        raise ReplayInputError(f"{target}/{strategy_id}: missing history cutoff")
    cutoff_date = date.fromisoformat(str(cutoff.get("draw_date")))
    target_date = date.fromisoformat(str(record["draw_date"]))
    cutoff_draw = str(cutoff.get("draw_number"))
    if not (cutoff_date < target_date and cutoff_draw.isdigit() and int(cutoff_draw) < int(target)):
        raise ReplayInputError(f"{target}/{strategy_id}: history cutoff is not strictly causal")
    if type(record.get("history_draw_count")) is not int or record["history_draw_count"] < 1:
        raise ReplayInputError(f"{target}/{strategy_id}: invalid history draw count")
    history_sha = record.get("history_sha256")
    if type(history_sha) is not str or len(history_sha) != 64:
        raise ReplayInputError(f"{target}/{strategy_id}: invalid history SHA-256")
    if _OUTCOME_KEYS.intersection(record):
        raise ReplayInputError(f"{target}/{strategy_id}: outcome-bearing field in prediction input")

    tickets_raw = record.get("tickets")
    if not isinstance(tickets_raw, list) or len(tickets_raw) != expected["native_ticket_count"]:
        raise ReplayInputError(f"{target}/{strategy_id}: ticket count does not match catalog")
    tickets: list[tuple[int, ...]] = []
    for position, item in enumerate(tickets_raw, start=1):
        if not isinstance(item, Mapping) or item.get("ticket_position") != position:
            raise ReplayInputError(f"{target}/{strategy_id}: ticket positions are not canonical")
        tickets.append(_validate_ticket(item.get("predicted_numbers"), f"{target}/{strategy_id}"))
    return str(strategy_id), tuple(tickets)


def _read_target_records(
    prediction_root: Path,
    target: str,
    expected_streams: Mapping[str, Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[str, tuple[tuple[int, ...], ...]], dict[str, str]]:
    target_dir = prediction_root / target
    paths = sorted(target_dir.rglob("*.json")) if target_dir.exists() else []
    records: list[dict[str, object]] = []
    tickets_by_stream: dict[str, tuple[tuple[int, ...], ...]] = {}
    file_hashes: dict[str, str] = {}
    for path in paths:
        try:
            raw = path.read_bytes()
            record = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise ReplayInputError(f"cannot read {path}: {exc}") from exc
        if not isinstance(record, dict):
            raise ReplayInputError(f"prediction record is not an object: {path}")
        strategy_id, tickets = _validate_prediction_record(
            record,
            target=target,
            expected_streams=expected_streams,
        )
        if strategy_id in tickets_by_stream:
            raise ReplayInputError(f"{target}: multiple runs for strategy {strategy_id}")
        tickets_by_stream[strategy_id] = tickets
        file_hashes[strategy_id] = _sha256_bytes(raw)
        record["_source_path"] = str(path)
        records.append(record)
    return records, tickets_by_stream, file_hashes


def _verify_saved_pool_manifests(
    operation_root: Path,
    target: str,
    records: Sequence[Mapping[str, object]],
    tickets_by_stream: Mapping[str, tuple[tuple[int, ...], ...]],
    file_hashes: Mapping[str, str],
    pool: Sequence[Sequence[int]],
) -> list[dict[str, object]]:
    forecast_root = operation_root / "forecasts" / target
    if not forecast_root.exists():
        return []
    checks: list[dict[str, object]] = []
    prediction_by_id = {str(record["strategy_id"]): record for record in records}
    for path in sorted(forecast_root.rglob("final_portfolio_payload.json")):
        try:
            raw = path.read_bytes()
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise ReplayInputError(f"cannot read saved pool manifest {path}: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise ReplayInputError(f"saved pool manifest is not an object: {path}")
        if payload.get("portfolio_method_id") not in (
            "B649_OPERATIONAL_PORTFOLIO_SELECTOR",
            "B649_SEALED_GEOMETRY_PORTFOLIO",
        ):
            continue
        if payload.get("target_result_used") is not False or payload.get("outcome_used") != "NO":
            raise ReplayInputError(f"{path}: saved pool manifest declares target-outcome use")
        if payload.get("portfolio_status") != "COMPLETE":
            raise ReplayInputError(f"{path}: saved pool manifest is not complete")
        manifest = payload.get("candidate_manifest")
        if not isinstance(manifest, list):
            raise ReplayInputError(f"{path}: missing candidate manifest")
        if {entry.get("strategy_id") for entry in manifest if isinstance(entry, Mapping)} != set(
            tickets_by_stream
        ):
            raise ReplayInputError(f"{path}: candidate manifest stream set differs from inputs")
        for entry in manifest:
            if not isinstance(entry, Mapping):
                raise ReplayInputError(f"{path}: malformed candidate manifest row")
            strategy_id = str(entry.get("strategy_id"))
            record = prediction_by_id[strategy_id]
            if (
                entry.get("prediction_run_id") != record.get("prediction_run_id")
                or entry.get("prediction_created_at") != record.get("prediction_created_at")
                or entry.get("prediction_sha256") != file_hashes[strategy_id]
            ):
                raise ReplayInputError(f"{path}: saved candidate manifest input hash mismatch")
        if payload.get("portfolio_method_id") == "B649_OPERATIONAL_PORTFOLIO_SELECTOR":
            for k in KS:
                if payload.get(f"k{k}_status") != "COMPLETE":
                    raise ReplayInputError(f"{path}: saved raw-majority K{k} is incomplete")
                saved = payload.get(f"k{k}")
                if not isinstance(saved, list):
                    raise ReplayInputError(f"{path}: saved raw-majority K{k} is malformed")
                observed = [item.get("predicted_numbers") for item in saved]
                if observed != _ticket_list(pool[:k]):
                    raise ReplayInputError(
                        f"{path}: reconstructed pinned pool does not match saved raw-majority K{k}"
                    )
        checks.append(
            {
                "path": str(path),
                "sha256": _sha256_bytes(raw),
                "method_id": payload.get("portfolio_method_id"),
                "method_version": payload.get("portfolio_method_version"),
                "outcome_free_flag": True,
                "manifest_stream_count": len(manifest),
            }
        )
    return checks


def _select_and_seal(
    *,
    target: str,
    records: Sequence[Mapping[str, object]],
    tickets_by_stream: Mapping[str, tuple[tuple[int, ...], ...]],
    file_hashes: Mapping[str, str],
    build_candidate_pool: Any,
    strategy_candidate_type: Any,
    operation_root: Path,
) -> dict[str, object]:
    from lottolab.application.b649_sealed_geometry_portfolio import (
        SEALED_GEOMETRY_PORTFOLIOS,
        sealed_geometry_buckets,
    )
    from lottolab.research.b649_direct_exact_coverage_selector import (
        select_direct_exact_coverage,
    )

    if len(tickets_by_stream) != 11:
        raise ReplayInputError(f"{target}: expected all 11 pre-draw streams")
    history_identities = {
        (
            str(record["history_cutoff"]["draw_number"]),
            str(record["history_cutoff"]["draw_date"]),
            str(record["history_draw_count"]),
            str(record["history_sha256"]),
        )
        for record in records
    }
    if len(history_identities) != 1:
        raise ReplayInputError(f"{target}: stream inputs do not share one history identity")
    candidates = [
        strategy_candidate_type(strategy_id, tickets_by_stream[strategy_id])
        for strategy_id in sorted(tickets_by_stream)
    ]
    entries = build_candidate_pool(candidates, {})
    pool = tuple(tuple(entry.ticket) for entry in entries)
    if len(pool) != len(set(pool)):
        raise ReplayInputError(f"{target}: canonical pool contains duplicate tickets")
    if len(pool) < SECONDARY_K:
        raise ReplayInputError(f"{target}: complete stream pool has fewer than K20 tickets")

    target_record = records[0]
    schedule = str(target_record["scheduled_at"])
    target_date = str(target_record["draw_date"])
    history_cutoff = target_record["history_cutoff"]
    saved_pool_checks = _verify_saved_pool_manifests(
        operation_root,
        target,
        records,
        tickets_by_stream,
        file_hashes,
        pool,
    )
    sealed = sealed_geometry_buckets(KS)
    target_selections: dict[str, object] = {}
    for k in KS:
        print(f"FREEZE_START draw={target} K={k} pool={len(pool)}", flush=True)
        started = datetime.now(UTC)
        selected = select_direct_exact_coverage(pool, k)
        elapsed = (datetime.now(UTC) - started).total_seconds()
        tickets = selected.tickets
        target_selections[str(k)] = {
            "tickets": _ticket_list(tickets),
            "portfolio_sha256": _portfolio_sha256(tickets),
            "selected_pool_ranks": list(selected.final_ranks),
            "greedy_pool_ranks": list(selected.greedy_ranks),
            "greedy_pick_order": list(selected.greedy_pick_order),
            "accepted_swaps": [
                {
                    "outgoing_rank": swap.outgoing_rank,
                    "incoming_rank": swap.incoming_rank,
                    "resulting_ranks": list(swap.resulting_ranks),
                    "previous_outcome_count": swap.previous_outcome_count,
                    "resulting_outcome_count": swap.resulting_outcome_count,
                }
                for swap in selected.swaps
            ],
            "local_optimum_certified_within_two_swap_bound": selected.local_optimum_certified,
            "official_any_prize_fair_probability": _fraction_text(
                selected.final_probability.official_any_prize
            ),
            "official_any_prize_outcome_count": (
                selected.final_probability.official_any_prize_outcome_count
            ),
            "candidate_gain_evaluations": selected.candidate_gain_evaluations,
            "canonical_evaluations": selected.canonical_evaluations,
            "elapsed_seconds": round(elapsed, 6),
        }
        print(
            f"FREEZE_DONE draw={target} K={k} swaps={len(selected.swaps)} "
            f"probability={_fraction_text(selected.final_probability.official_any_prize)} "
            f"seconds={elapsed:.2f}",
            flush=True,
        )

    baseline = {
        str(k): {
            "method_id": "B649_SEALED_GEOMETRY_PORTFOLIO",
            "method_version": "6.0.0",
            "tickets": _ticket_list(sealed[k]),
            "portfolio_sha256": SEALED_GEOMETRY_PORTFOLIOS[k].portfolio_sha256,
            "official_any_prize_fair_probability": _fraction_text(
                SEALED_GEOMETRY_PORTFOLIOS[k].official_any_prize_probability
            ),
        }
        for k in KS
    }
    prediction_hash_manifest = [
        {
            "strategy_id": strategy_id,
            "prediction_run_id": next(
                str(record["prediction_run_id"])
                for record in records
                if record["strategy_id"] == strategy_id
            ),
            "prediction_sha256": file_hashes[strategy_id],
            "prediction_created_at": next(
                str(record["prediction_created_at"])
                for record in records
                if record["strategy_id"] == strategy_id
            ),
        }
        for strategy_id in sorted(tickets_by_stream)
    ]
    return {
        "draw_number": target,
        "draw_date": target_date,
        "scheduled_at": schedule,
        "history_cutoff": dict(history_cutoff),
        "history_draw_count": int(target_record["history_draw_count"]),
        "history_sha256": str(target_record["history_sha256"]),
        "pre_draw_stream_count": len(records),
        "input_prediction_manifest": prediction_hash_manifest,
        "candidate_pool_count": len(pool),
        "candidate_pool_sha256": _pool_sha256(pool),
        "ordered_candidate_pool": _ticket_list(pool),
        "candidate_selections": target_selections,
        "sealed_v6_baseline": baseline,
        "saved_pool_manifest_checks": saved_pool_checks,
    }


def _write_new_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise ReplayInputError(f"refusing to overwrite existing result artifact: {path}") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def freeze_portfolios(
    *,
    operation_root: Path = DEFAULT_OPERATION_ROOT,
    freeze_path: Path = DEFAULT_FREEZE_FILE,
    evaluation_cutoff: str = AS_OF_DATE,
) -> dict[str, object]:
    """Build every in-scope portfolio without opening any outcome source."""
    cutoff = date.fromisoformat(evaluation_cutoff)
    if evaluation_cutoff != AS_OF_DATE:
        raise ReplayInputError(f"evaluation cutoff must stay fixed at {AS_OF_DATE}")
    if freeze_path.exists():
        raise ReplayInputError(f"frozen portfolio file already exists: {freeze_path}")

    authority = _validate_authorities(REPO_ROOT)
    prediction_root = operation_root / "predictions"
    registry = authority["stream_catalog"]
    assert isinstance(registry, dict)
    build_candidate_pool = authority.pop("pool_builder")
    strategy_candidate_type = authority.pop("strategy_candidate_type")

    selected_targets: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    for number in range(WINDOW_START, WINDOW_END + 1):
        target = f"115000{number:03d}"
        records, tickets_by_stream, file_hashes = _read_target_records(
            prediction_root,
            target,
            registry,
        )
        if not records:
            exclusions.append(
                {
                    "draw_number": target,
                    "excluded_for_k": list(KS),
                    "reason": "NO_SAVED_PREDRAW_STREAMS",
                    "available_stream_count": 0,
                    "candidate_pool_count": 0,
                }
            )
            continue

        if len(records) != len(registry):
            partial_candidates = [
                strategy_candidate_type(strategy_id, tickets_by_stream[strategy_id])
                for strategy_id in sorted(tickets_by_stream)
            ]
            partial_pool = build_candidate_pool(partial_candidates, {})
            exclusions.append(
                {
                    "draw_number": target,
                    "excluded_for_k": list(KS),
                    "reason": "INCOMPLETE_PRE_DRAW_STREAM_SET",
                    "available_stream_count": len(records),
                    "expected_stream_count": len(registry),
                    "candidate_pool_count": len(partial_pool),
                    "pool_below_k": {str(k): len(partial_pool) < k for k in KS},
                }
            )
            continue

        if len(tickets_by_stream) != len(registry):
            raise ReplayInputError(f"{target}: complete stream set has unexpected identities")
        target_dates = {str(record["draw_date"]) for record in records}
        if len(target_dates) != 1:
            raise ReplayInputError(f"{target}: strategy records disagree on target date")
        target_date = date.fromisoformat(next(iter(target_dates)))
        if target_date > cutoff:
            candidates = [
                strategy_candidate_type(strategy_id, tickets_by_stream[strategy_id])
                for strategy_id in sorted(tickets_by_stream)
            ]
            pool = build_candidate_pool(candidates, {})
            exclusions.append(
                {
                    "draw_number": target,
                    "draw_date": target_date.isoformat(),
                    "excluded_for_k": list(KS),
                    "reason": "TARGET_AFTER_EVALUATION_CUTOFF",
                    "evaluation_cutoff": cutoff.isoformat(),
                    "available_stream_count": len(records),
                    "candidate_pool_count": len(pool),
                }
            )
            continue

        sealed_record = _select_and_seal(
            target=target,
            records=records,
            tickets_by_stream=tickets_by_stream,
            file_hashes=file_hashes,
            build_candidate_pool=build_candidate_pool,
            strategy_candidate_type=strategy_candidate_type,
            operation_root=operation_root,
        )
        if int(sealed_record["candidate_pool_count"]) < SECONDARY_K:
            exclusions.append(
                {
                    "draw_number": target,
                    "draw_date": sealed_record["draw_date"],
                    "excluded_for_k": [
                        k for k in KS if int(sealed_record["candidate_pool_count"]) < k
                    ],
                    "reason": "CANDIDATE_POOL_BELOW_K",
                    "candidate_pool_count": sealed_record["candidate_pool_count"],
                }
            )
            continue
        selected_targets.append(sealed_record)

    if not selected_targets:
        raise ReplayInputError("no complete historical candidate pools were available")
    authorities = {key: value for key, value in authority.items()}
    frozen = {
        "schema_version": "b649-direct-exact-success-coverage-oos-frozen-v1",
        "artifact_kind": "OUTCOME_BLIND_FROZEN_PORTFOLIOS",
        "task_id": TASK_ID,
        "frozen_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "evaluation_cutoff_date": cutoff.isoformat(),
        "target_window": {
            "first_draw_number": f"115000{WINDOW_START:03d}",
            "last_draw_number": f"115000{WINDOW_END:03d}",
            "selection_filter": "saved PRE_DRAW input records only; never target outcomes",
        },
        "authorities": authorities,
        "pool_contract": {
            "method": "B649_KDPP_RAW_MAJORITY_QUALITY_DIVERSITY candidate pool",
            "quality_weights": {},
            "pool_order": "support_count DESC, ticket ASC",
            "candidate_pool_builder_source": (
                "pinned Git source loaded from the frozen K-DPP authority commit"
            ),
        },
        "candidate_contract": {
            "method_id": "B649_DIRECT_EXACT_SUCCESS_COVERAGE_SELECTOR",
            "method_version": "1.0.0",
            "primary_k": PRIMARY_K,
            "secondary_k": SECONDARY_K,
            "max_accepted_swaps": 2,
            "greedy_tie_break": "EARLIEST_POOL_POSITION",
            "swap_tie_break": "LEXICOGRAPHICALLY_SMALLEST_RESULTING_ASCENDING_RANK_VECTOR",
        },
        "baseline_contract": {
            "method_id": "B649_SEALED_GEOMETRY_PORTFOLIO",
            "method_version": "6.0.0",
            "comparison": "same target draw and K",
        },
        "excluded_before_selection": exclusions,
        "frozen_targets": selected_targets,
    }
    _write_new_json(freeze_path, frozen)
    frozen["frozen_artifact_path"] = str(freeze_path)
    frozen["frozen_artifact_sha256"] = _sha256_file(freeze_path)
    print(
        f"FROZEN targets={len(selected_targets)} excluded={len(exclusions)} "
        f"sha256={frozen['frozen_artifact_sha256']} path={freeze_path}",
        flush=True,
    )
    return frozen


def _binomial_cdf_half(n: int, through: int) -> Fraction:
    return Fraction(sum(math.comb(n, i) for i in range(through + 1)), 2**n)


def exact_mcnemar_two_sided(candidate_only: int, sealed_only: int) -> Fraction:
    """Exact two-sided McNemar p-value conditional on discordant pairs."""
    if type(candidate_only) is not int or type(sealed_only) is not int:
        raise TypeError("discordant counts must be integers")
    if candidate_only < 0 or sealed_only < 0:
        raise ValueError("discordant counts must be non-negative")
    n = candidate_only + sealed_only
    if n == 0:
        return Fraction(1, 1)
    lower = min(candidate_only, sealed_only)
    return min(Fraction(1, 1), 2 * _binomial_cdf_half(n, lower))


def summarize_pairs(rows: Sequence[Mapping[str, object]], k: int) -> dict[str, object]:
    eligible = len(rows)
    candidate_wins = sum(bool(row["candidate_win"]) for row in rows)
    sealed_wins = sum(bool(row["sealed_v6_win"]) for row in rows)
    candidate_only = sum(
        bool(row["candidate_win"]) and not bool(row["sealed_v6_win"]) for row in rows
    )
    sealed_only = sum(bool(row["sealed_v6_win"]) and not bool(row["candidate_win"]) for row in rows)
    both_win = sum(bool(row["candidate_win"]) and bool(row["sealed_v6_win"]) for row in rows)
    both_lose = eligible - candidate_only - sealed_only - both_win
    discordant = candidate_only + sealed_only
    delta = Fraction(candidate_wins - sealed_wins, eligible) if eligible else None
    relative_lift = Fraction(candidate_wins - sealed_wins, sealed_wins) if sealed_wins else None
    pvalue = exact_mcnemar_two_sided(candidate_only, sealed_only)
    portfolios_changed = any(
        row[f"candidate_portfolio_sha256_k{k}"] != row[f"sealed_v6_portfolio_sha256_k{k}"]
        for row in rows
    )
    if eligible and not portfolios_changed:
        verdict = "NO_DECISION_LEVERAGE"
    elif delta is not None and delta > 0 and pvalue < Fraction(1, 20):
        verdict = "POSITIVE_LIFT_VALIDATED"
    elif delta is not None and delta < 0 and pvalue < Fraction(1, 20):
        verdict = "NEGATIVE_LIFT_VALIDATED"
    elif discordant < 6:
        # With fewer than six discordant pairs, even a unanimous direction has
        # exact two-sided p >= 0.0625; this test cannot validate lift at 5%.
        verdict = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = "INCONCLUSIVE"
    return {
        "k": k,
        "eligible_paired_draws": eligible,
        "candidate_wins": candidate_wins,
        "sealed_v6_wins": sealed_wins,
        "candidate_only": candidate_only,
        "sealed_only": sealed_only,
        "both_win": both_win,
        "both_lose": both_lose,
        "discordant_count": discordant,
        "absolute_delta_fraction": None if delta is None else _fraction_text(delta),
        "absolute_delta_rate": None if delta is None else float(delta),
        "absolute_delta_percentage_points": None if delta is None else float(delta * 100),
        "relative_lift_fraction": None if relative_lift is None else _fraction_text(relative_lift),
        "relative_lift_percent": None if relative_lift is None else float(relative_lift * 100),
        "relative_lift_meaningful": relative_lift is not None,
        "paired_statistical_evidence": {
            "test": "Exact two-sided McNemar test (conditional binomial test on discordant pairs)",
            "null": "candidate-only and sealed-only are equally likely among discordant draws",
            "alpha": 0.05,
            "exact_p_value_fraction": _fraction_text(pvalue),
            "exact_p_value": float(pvalue),
            "discordant_pairs": discordant,
        },
        "verdict": verdict,
    }


def _portfolio_any_prize(
    tickets: Sequence[Sequence[int]],
    main: tuple[int, ...],
    special: int,
) -> bool:
    from lottolab.domain.prize_evaluation import evaluate_big_lotto_ticket

    return any(
        evaluate_big_lotto_ticket(
            predicted_main_numbers=tuple(ticket),
            predicted_special_number=None,
            winning_main_numbers=main,
            winning_special_number=special,
        ).is_winner
        for ticket in tickets
    )


def _load_official_outcomes(
    database: Path, targets: Sequence[Mapping[str, object]]
) -> tuple[dict[str, dict[str, object]], str, str]:
    before_hash = _sha256_file(database)
    uri = f"{database.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only = ON")
    outcomes: dict[str, dict[str, object]] = {}
    try:
        for target in targets:
            draw_number = str(target["draw_number"])
            row = connection.execute(
                """
                SELECT draw_date, main_numbers_json, special_numbers_json,
                       source_name, source_reference, normalized_record_hash
                FROM draws
                WHERE lottery_type = 'BIG_LOTTO' AND draw_number = ?
                """,
                (draw_number,),
            ).fetchone()
            if row is None:
                continue
            draw_date, main_json, special_json, source_name, source_reference, record_hash = row
            if source_name != OFFICIAL_SOURCE_NAME:
                raise ReplayInputError(
                    f"{draw_number}: outcome source is not the official API: {source_name!r}"
                )
            if draw_date != target.get("draw_date"):
                raise ReplayInputError(
                    f"{draw_number}: official outcome date mismatches PRE_DRAW target"
                )
            main = tuple(sorted(json.loads(main_json)))
            special_values = tuple(json.loads(special_json))
            if (
                len(main) != 6
                or len(set(main)) != 6
                or any(type(value) is not int or not 1 <= value <= 49 for value in main)
                or len(special_values) != 1
                or type(special_values[0]) is not int
                or not 1 <= special_values[0] <= 49
                or special_values[0] in main
            ):
                raise ReplayInputError(f"{draw_number}: malformed official BIG_LOTTO outcome")
            outcomes[draw_number] = {
                "draw_date": draw_date,
                "main_numbers": list(main),
                "special_number": special_values[0],
                "source_name": source_name,
                "source_reference": source_reference,
                "normalized_record_hash": record_hash,
            }
    finally:
        connection.close()
    after_hash = _sha256_file(database)
    if before_hash != after_hash:
        raise ReplayInputError("outcome database changed during the read-only scoring phase")
    return outcomes, before_hash, after_hash


def _geometry_summary(rows: Sequence[Mapping[str, object]], k: int) -> dict[str, object]:
    from lottolab.application.b649_sealed_geometry_portfolio import SEALED_GEOMETRY_PORTFOLIOS

    probabilities = [Fraction(str(row[f"candidate_fair_geometry_k{k}"])) for row in rows]
    baseline = SEALED_GEOMETRY_PORTFOLIOS[k].official_any_prize_probability
    mean = sum(probabilities, Fraction(0, 1)) / len(probabilities)
    return {
        "interpretation": "fair-draw structural diagnostic only; not realized OOS lift",
        "shared_outcome_space": (
            "C(49,6) main draws x 43 eligible special balls = 601,304,088 outcomes"
        ),
        "candidate_per_draw_probabilities": [
            {
                "draw_number": row["draw_number"],
                "probability": str(row[f"candidate_fair_geometry_k{k}"]),
            }
            for row in rows
        ],
        "candidate_mean_probability_fraction": _fraction_text(mean),
        "candidate_mean_probability": float(mean),
        "candidate_min_probability_fraction": _fraction_text(min(probabilities)),
        "candidate_max_probability_fraction": _fraction_text(max(probabilities)),
        "sealed_v6_probability_fraction": _fraction_text(baseline),
        "sealed_v6_probability": float(baseline),
        "candidate_mean_minus_sealed_v6_fraction": _fraction_text(mean - baseline),
        "candidate_mean_minus_sealed_v6_percentage_points": float((mean - baseline) * 100),
    }


def _build_report(result: Mapping[str, object]) -> str:
    k_results = result["k_results"]
    assert isinstance(k_results, Mapping)
    lines = [
        "# B649 Direct Exact Success Coverage vs Sealed v6: strict PRE_DRAW OOS R1",
        "",
        f"Evaluation cutoff: **{result['evaluation_cutoff_date']} (Asia/Taipei)**<br>",
        "Primary K: **K10**<br>",
        "Secondary K: **K20 (descriptive only)**<br>",
        f"Primary verdict: **{result['primary_verdict']}**<br>",
        f"READY_FOR_BRANCH6_ADOPTION: **{result['ready_for_branch6_adoption']}**",
        "",
        "## Protocol",
        "",
        "The candidate was generated from each target's timestamped PRE_DRAW 11-stream records. "
        "The frozen ordered pool uses the pinned K-DPP pool builder with an empty quality map "
        "(support count descending, then ticket ascending). The selector and sealed-v6 portfolios "
        "were written to the outcome-blind freeze artifact before the replay opened the result "
        "database.",
        "",
        "Each eligible pair uses the same target draw and official BIG_LOTTO outcome. The scoring "
        "phase used the canonical prize evaluator and read the application database in query-only "
        "mode. The exact fair-draw probabilities below are structural diagnostics; they are not "
        "observed OOS lift.",
        "",
        f"Frozen portfolio artifact SHA-256: `{result['frozen_artifact_sha256']}`",
        "Read-only outcome database SHA-256 (unchanged across scoring): "
        f"`{result['outcome_database_sha256_before']}`",
        "Official result reference: "
        "[Taiwan Lottery Lotto 649 results](https://apislb.taiwanlottery.com/lotto/result/lotto649/).",
        "",
        "## Paired PRE_DRAW results",
        "",
        "| "
        + " | ".join(
            (
                "K",
                "Eligible pairs",
                "Candidate wins",
                "Sealed-v6 wins",
                "Candidate-only",
                "Sealed-only",
                "Both win",
                "Both lose",
                "Discordant",
                "Absolute delta",
                "Relative lift",
                "Exact McNemar p",
                "Assessment",
            )
        )
        + " |",
        "| " + " | ".join(("---:",) * 12 + ("---",)) + " |",
    ]
    for k in KS:
        r = k_results[str(k)]
        delta = r["absolute_delta_percentage_points"]
        lift = r["relative_lift_percent"]
        cells = (
            f"K{k}",
            str(r["eligible_paired_draws"]),
            str(r["candidate_wins"]),
            str(r["sealed_v6_wins"]),
            str(r["candidate_only"]),
            str(r["sealed_only"]),
            str(r["both_win"]),
            str(r["both_lose"]),
            str(r["discordant_count"]),
            "n/a" if delta is None else f"{delta:.2f} pp",
            "n/a" if lift is None else f"{lift:.2f}%",
            str(r["paired_statistical_evidence"]["exact_p_value_fraction"]),
            str(r.get("verdict", "DESCRIPTIVE ONLY")),
        )
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "### Per-draw paired outcomes",
            "",
            "| Draw | Date | K10 candidate / v6 | K20 candidate / v6 | Official API outcome |",
            "|---|---|---|---|---|",
        ]
    )
    per_draw_k10 = k_results["10"]["per_draw"]
    per_draw_k20 = k_results["20"]["per_draw"]
    k20_by_draw = {row["draw_number"]: row for row in per_draw_k20}
    for row in per_draw_k10:
        row20 = k20_by_draw[row["draw_number"]]
        outcomes = row["official_outcome"]
        k10_result = (
            f"{'win' if row['candidate_win'] else 'loss'} / "
            f"{'win' if row['sealed_v6_win'] else 'loss'}"
        )
        k20_result = (
            f"{'win' if row20['candidate_win'] else 'loss'} / "
            f"{'win' if row20['sealed_v6_win'] else 'loss'}"
        )
        outcome_text = ",".join(map(str, outcomes["main_numbers"]))
        outcome_text += f" + special {outcomes['special_number']}"
        lines.append(
            f"| {row['draw_number']} | {row['draw_date']} | "
            f"{k10_result} | {k20_result} | {outcome_text} |"
        )
    lines.extend(["", "## Exact fair-draw geometry (diagnostic only)", ""])
    for k in KS:
        geometry = k_results[str(k)]["fair_draw_geometry_diagnostic"]
        mean_geometry = (
            f"Candidate mean across eligible per-draw portfolios: "
            f"`{geometry['candidate_mean_probability_fraction']}` "
            f"({geometry['candidate_mean_probability']:.6%}); range "
            f"`{geometry['candidate_min_probability_fraction']}` to "
            f"`{geometry['candidate_max_probability_fraction']}`."
        )
        sealed_geometry = (
            f"Sealed v6: `{geometry['sealed_v6_probability_fraction']}` "
            f"({geometry['sealed_v6_probability']:.6%})."
        )
        geometry_delta = (
            f"Mean geometry difference: "
            f"`{geometry['candidate_mean_minus_sealed_v6_fraction']}` "
            f"({geometry['candidate_mean_minus_sealed_v6_percentage_points']:.6f} pp)."
        )
        lines.extend(
            [
                f"### K{k}",
                "",
                mean_geometry,
                sealed_geometry,
                geometry_delta,
                "",
                "These exact uniform-draw quantities describe portfolio geometry. "
                "The paired PRE_DRAW outcome counts above determine the OOS result.",
                "",
            ]
        )
        lines.extend(
            [
                "| Draw | Candidate exact probability | Sealed-v6 exact probability |",
                "|---|---:|---:|",
            ]
        )
        for item in geometry["candidate_per_draw_probabilities"]:
            lines.append(
                f"| {item['draw_number']} | `{item['probability']}` | "
                f"`{geometry['sealed_v6_probability_fraction']}` |"
            )
        lines.append("")
    lines.extend(["## Excluded targets and reasons", ""])
    excluded = result["excluded_draws"]
    if excluded:
        for item in excluded:
            details: list[str] = []
            stream_count = item.get("available_stream_count")
            expected_count = item.get("expected_stream_count")
            pool_count = item.get("candidate_pool_count")
            if stream_count is not None and expected_count is not None:
                details.append(f"{stream_count}/{expected_count} stream snapshots")
            elif stream_count is not None:
                details.append(f"{stream_count} stream snapshots")
            if pool_count is not None:
                details.append(f"pool={pool_count}")
            if item.get("draw_date") is not None:
                details.append(f"target date {item['draw_date']}")
            if item.get("evaluation_cutoff") is not None:
                details.append(f"after cutoff {item['evaluation_cutoff']}")
            suffix = f"; {', '.join(details)}" if details else ""
            lines.append(
                f"- {item['draw_number']}: {item['reason']} "
                f"(excluded for K{', K'.join(map(str, item['excluded_for_k']))}{suffix})."
            )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Verdict rule",
            "",
            "A positive or negative lift is validated only when the paired exact two-sided "
            "McNemar p-value is below 0.05 and the delta has the same direction. "
            "If fewer than six pairs are discordant, even a unanimous direction cannot reach "
            "0.05 in this exact test, so the verdict is INSUFFICIENT_EVIDENCE. "
            "K20 cannot change the primary K10 verdict.",
            "",
            "## Boundaries",
            "",
            "Candidate algorithm, two-swap bound, tie-breaks, pool order, and K were not tuned. "
            "Sealed v6 was read-only. "
            "No production activation, Lane3 mutation, push, PR, or merge occurred.",
            "",
        ]
    )
    return "\n".join(lines)


def score_frozen_portfolios(
    *,
    freeze_path: Path = DEFAULT_FREEZE_FILE,
    result_path: Path = DEFAULT_RESULT_FILE,
    report_path: Path = DEFAULT_REPORT_FILE,
    database: Path | None = None,
) -> dict[str, object]:
    """Read the frozen portfolios, then access official outcomes read-only."""
    if not freeze_path.is_file():
        raise ReplayInputError(f"outcome-blind frozen portfolio artifact is missing: {freeze_path}")
    if result_path.exists() or report_path.exists():
        raise ReplayInputError("refusing to repeat or overwrite the one authorized scoring run")
    freeze_bytes = freeze_path.read_bytes()
    frozen = json.loads(freeze_bytes)
    if (
        not isinstance(frozen, Mapping)
        or frozen.get("artifact_kind") != "OUTCOME_BLIND_FROZEN_PORTFOLIOS"
    ):
        raise ReplayInputError("freeze file is not an outcome-blind portfolio artifact")
    if frozen.get("candidate_contract", {}).get("method_version") != "1.0.0":
        raise ReplayInputError("frozen portfolio artifact candidate identity drift")
    targets = frozen.get("frozen_targets")
    if not isinstance(targets, list) or not targets:
        raise ReplayInputError("frozen portfolio artifact contains no targets")
    _load_project_modules()
    if database is None:
        from lottolab.infrastructure.persistence.draw_schema import resolve_local_data_paths

        database = resolve_local_data_paths().database
    outcomes, database_hash_before, database_hash_after = _load_official_outcomes(database, targets)

    exclusions = list(frozen.get("excluded_before_selection", []))
    scored_by_k: dict[str, list[dict[str, object]]] = {str(k): [] for k in KS}
    for target in targets:
        draw_number = str(target["draw_number"])
        outcome = outcomes.get(draw_number)
        if outcome is None:
            exclusions.append(
                {
                    "draw_number": draw_number,
                    "draw_date": target.get("draw_date"),
                    "excluded_for_k": list(KS),
                    "reason": "OFFICIAL_OUTCOME_NOT_AVAILABLE_AT_EVALUATION_CUTOFF",
                    "candidate_pool_count": target.get("candidate_pool_count"),
                }
            )
            continue
        main = tuple(int(value) for value in outcome["main_numbers"])
        special = int(outcome["special_number"])
        for k in KS:
            candidate = target["candidate_selections"][str(k)]
            baseline = target["sealed_v6_baseline"][str(k)]
            candidate_tickets = candidate["tickets"]
            baseline_tickets = baseline["tickets"]
            candidate_win = _portfolio_any_prize(candidate_tickets, main, special)
            baseline_win = _portfolio_any_prize(baseline_tickets, main, special)
            scored_by_k[str(k)].append(
                {
                    "draw_number": draw_number,
                    "draw_date": target["draw_date"],
                    "candidate_win": candidate_win,
                    "sealed_v6_win": baseline_win,
                    "candidate_portfolio_sha256_k10": target["candidate_selections"]["10"][
                        "portfolio_sha256"
                    ],
                    "sealed_v6_portfolio_sha256_k10": target["sealed_v6_baseline"]["10"][
                        "portfolio_sha256"
                    ],
                    "candidate_portfolio_sha256_k20": target["candidate_selections"]["20"][
                        "portfolio_sha256"
                    ],
                    "sealed_v6_portfolio_sha256_k20": target["sealed_v6_baseline"]["20"][
                        "portfolio_sha256"
                    ],
                    "candidate_fair_geometry_k10": target["candidate_selections"]["10"][
                        "official_any_prize_fair_probability"
                    ],
                    "candidate_fair_geometry_k20": target["candidate_selections"]["20"][
                        "official_any_prize_fair_probability"
                    ],
                    "sealed_v6_fair_geometry_k10": target["sealed_v6_baseline"]["10"][
                        "official_any_prize_fair_probability"
                    ],
                    "sealed_v6_fair_geometry_k20": target["sealed_v6_baseline"]["20"][
                        "official_any_prize_fair_probability"
                    ],
                    "official_outcome": outcome,
                }
            )

    k_results: dict[str, object] = {}
    for k in KS:
        rows = scored_by_k[str(k)]
        summary = summarize_pairs(rows, k)
        summary["assessment_role"] = (
            "PRIMARY_K10" if k == PRIMARY_K else "SECONDARY_DESCRIPTIVE_ONLY"
        )
        if k != PRIMARY_K:
            summary.pop("verdict", None)
        summary["excluded_draws"] = [
            item for item in exclusions if k in item.get("excluded_for_k", [])
        ]
        summary["per_draw"] = [
            {
                "draw_number": row["draw_number"],
                "draw_date": row["draw_date"],
                "candidate_win": row["candidate_win"],
                "sealed_v6_win": row["sealed_v6_win"],
                "candidate_portfolio_sha256": row[f"candidate_portfolio_sha256_k{k}"],
                "sealed_v6_portfolio_sha256": row[f"sealed_v6_portfolio_sha256_k{k}"],
                f"candidate_fair_geometry_k{k}": row[f"candidate_fair_geometry_k{k}"],
                f"sealed_v6_fair_geometry_k{k}": row[f"sealed_v6_fair_geometry_k{k}"],
                "official_outcome": row["official_outcome"],
            }
            for row in rows
        ]
        summary["fair_draw_geometry_diagnostic"] = _geometry_summary(rows, k)
        k_results[str(k)] = summary

    primary_verdict = str(k_results[str(PRIMARY_K)]["verdict"])
    result: dict[str, object] = {
        "schema_version": "b649-direct-exact-success-coverage-oos-result-v1",
        "task_id": TASK_ID,
        "scored_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "evaluation_cutoff_date": frozen["evaluation_cutoff_date"],
        "frozen_portfolios_artifact": str(freeze_path),
        "frozen_artifact_sha256": _sha256_bytes(freeze_bytes),
        "outcome_database_path": str(database),
        "outcome_database_sha256_before": database_hash_before,
        "outcome_database_sha256_after": database_hash_after,
        "outcome_source_required": OFFICIAL_SOURCE_NAME,
        "official_outcome_url": "https://apislb.taiwanlottery.com/lotto/result/lotto649/",
        "candidate": {
            "method_id": "B649_DIRECT_EXACT_SUCCESS_COVERAGE_SELECTOR",
            "version": "1.0.0",
            "head": frozen["authorities"]["candidate_head"],
            "tree": frozen["authorities"]["candidate_tree"],
        },
        "baseline": {
            "method_id": "B649_SEALED_GEOMETRY_PORTFOLIO",
            "version": "6.0.0",
            "origin_main_head": frozen["authorities"]["canonical_origin_main_head"],
            "source_blob": frozen["authorities"]["canonical_sealed_v6_blob"],
        },
        "primary_k": PRIMARY_K,
        "secondary_k_role": "DESCRIPTIVE_ONLY_CANNOT_RESCUE_K10",
        "paired_comparison_rule": "same target draw, same K, same official outcome",
        "k_results": k_results,
        "excluded_draws": exclusions,
        "primary_verdict": primary_verdict,
        "ready_for_branch6_adoption": "YES"
        if primary_verdict == "POSITIVE_LIFT_VALIDATED"
        else "NO",
        "mutation_boundaries": {
            "candidate_tuned": False,
            "sealed_v6_modified": False,
            "production_mutation": "NONE",
            "lane3_mutation": False,
            "push": False,
            "pull_request": False,
            "merge": False,
        },
    }
    report = _build_report(result)
    result["report_path"] = str(report_path)
    _write_new_json(result_path, result)
    try:
        descriptor = os.open(report_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise ReplayInputError(f"refusing to overwrite existing report: {report_path}") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(report)
        stream.flush()
        os.fsync(stream.fileno())
    print(
        f"SCORED pairs_k10={k_results['10']['eligible_paired_draws']} "
        f"verdict={primary_verdict} "
        f"READY_FOR_BRANCH6_ADOPTION={result['ready_for_branch6_adoption']} "
        f"result={result_path}",
        flush=True,
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser("freeze", help="create outcome-blind target portfolios")
    freeze.add_argument("--operation-root", type=Path, default=DEFAULT_OPERATION_ROOT)
    freeze.add_argument("--freeze-file", type=Path, default=DEFAULT_FREEZE_FILE)
    freeze.add_argument("--evaluation-cutoff", default=AS_OF_DATE)
    score = subparsers.add_parser("score", help="score an existing freeze artifact read-only")
    score.add_argument("--freeze-file", type=Path, default=DEFAULT_FREEZE_FILE)
    score.add_argument("--result-file", type=Path, default=DEFAULT_RESULT_FILE)
    score.add_argument("--report-file", type=Path, default=DEFAULT_REPORT_FILE)
    score.add_argument("--database", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "freeze":
            freeze_portfolios(
                operation_root=args.operation_root,
                freeze_path=args.freeze_file,
                evaluation_cutoff=args.evaluation_cutoff,
            )
        else:
            score_frozen_portfolios(
                freeze_path=args.freeze_file,
                result_path=args.result_file,
                report_path=args.report_file,
                database=args.database,
            )
    except ReplayInputError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
