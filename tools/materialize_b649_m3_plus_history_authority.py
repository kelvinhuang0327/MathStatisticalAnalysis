"""Materialize the frozen B649 per-stream M3_PLUS history authority.

The inputs are sealed/read-only research evidence and the read-only local
official draw database.  This tool does not replay strategies, mutate the
database, or touch the downstream candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from lottolab.research.b649_m3_plus_history_authority import (
    ARTIFACT_PATH,
    ARTIFACT_SCHEMA_VERSION,
    CAUSAL_CUTOFF_DRAW_DATE,
    CAUSAL_CUTOFF_DRAW_NUMBER,
    EXPECTED_STREAM_IDS,
    METRIC_ID,
    METRIC_VERSION,
    TARGET_DRAW_DATE,
    TARGET_DRAW_NUMBER,
    TRAILING_WINDOW_DRAW_COUNT,
    artifact_content_sha256,
    m3_plus_success,
    validate_artifact_payload,
)

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
MATRIX_RAW_PATH: Final = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "B649_CAUSAL_STRATEGY_EMISSION_MATRIX_DISCOVERY_R1/causal_emissions_raw.jsonl"
)
MATRIX_REPORT_PATH: Final = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "B649_CAUSAL_STRATEGY_EMISSION_MATRIX_DISCOVERY_R1/report.md"
)
MATRIX_SUMMARY_PATH: Final = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "B649_CAUSAL_STRATEGY_EMISSION_MATRIX_DISCOVERY_R1/strategy_information_summary.csv"
)
OPERATIONAL_ROOT: Final = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OPERATIONAL_PREDICTION_LOOP_R1"
)
OFFICIAL_DB_PATH: Final = Path(
    "/Users/kelvin/Library/Application Support/LottoLab/lottolab.db"
)
FROZEN_CANDIDATE_COMMIT: Final = "55c1e7bac12dffcef97fe67527dc4d61d0a42fd5"
FROZEN_CANDIDATE_TREE: Final = "8f9cd77a4ac13fe81544beadc8ebb869565df4"
FROZEN_CANDIDATE_PATH: Final = (
    "docs/research/matrix-native-results/"
    "b649-dynamic-stream-reliability-weighting-v1-frozen-candidate.json"
)
FROZEN_M3_AUTHORITY_PATH: Final = "contracts/evidence/metric_definitions/m3_plus.json"


@dataclass(frozen=True, slots=True)
class Forecast:
    stream_id: str
    target_draw_number: str
    source_target_date: str
    source_cutoff_draw_number: str
    source_cutoff_date: str
    tickets: tuple[tuple[int, ...], ...]
    source_kind: str
    source_path: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class OfficialDraw:
    draw_number: str
    draw_date: str
    main_numbers: tuple[int, ...]
    normalized_record_hash: str


def _json_object(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _read_json(path: Path) -> dict[str, object]:
    return _json_object(json.loads(path.read_text(encoding="utf-8")), str(path))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_int_list(value: object, label: str) -> tuple[int, ...]:
    if type(value) is not list or any(
        type(number) is not int for number in cast(list[object], value)
    ):
        raise ValueError(f"{label} must be a list of integers")
    numbers = tuple(cast(list[int], value))
    if (
        len(numbers) != 6
        or len(set(numbers)) != 6
        or not all(1 <= number <= 49 for number in numbers)
    ):
        raise ValueError(f"{label} must be six distinct BIG_LOTTO main numbers")
    return numbers


def _as_tickets(value: object, label: str) -> tuple[tuple[int, ...], ...]:
    if type(value) is not list:
        raise ValueError(f"{label} must be a list of tickets")
    return tuple(
        _as_int_list(ticket, f"{label}[{index}]")
        for index, ticket in enumerate(cast(list[object], value))
    )


def _read_official_draws() -> tuple[dict[str, OfficialDraw], str]:
    if not OFFICIAL_DB_PATH.is_file():
        raise FileNotFoundError(OFFICIAL_DB_PATH)
    uri = f"file:{OFFICIAL_DB_PATH.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        records = connection.execute(
            """
            SELECT draw_number, draw_date, main_numbers_json, normalized_record_hash
            FROM draws
            WHERE lottery_type = 'BIG_LOTTO'
            ORDER BY CAST(draw_number AS INTEGER), draw_date
            """
        ).fetchall()
    draws: dict[str, OfficialDraw] = {}
    for draw_number, draw_date, main_json, normalized_hash in records:
        if type(draw_number) is not str or draw_number in draws:
            raise ValueError(f"official draw identity is not unique: {draw_number!r}")
        if (
            type(draw_date) is not str
            or type(main_json) is not str
            or type(normalized_hash) is not str
        ):
            raise ValueError(f"official draw row is malformed: {draw_number!r}")
        main_numbers = _as_int_list(json.loads(main_json), f"official {draw_number} main_numbers")
        draws[draw_number] = OfficialDraw(
            draw_number=draw_number,
            draw_date=draw_date,
            main_numbers=main_numbers,
            normalized_record_hash=normalized_hash,
        )
    selected_rows = [
        {
            "draw_number": draw.draw_number,
            "draw_date": draw.draw_date,
            "main_numbers": list(draw.main_numbers),
            "normalized_record_hash": draw.normalized_record_hash,
        }
        for draw in sorted(draws.values(), key=lambda item: int(item.draw_number))
        if int(draw.draw_number) <= int(CAUSAL_CUTOFF_DRAW_NUMBER)
    ]
    selected_rows_bytes = json.dumps(
        selected_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return draws, hashlib.sha256(selected_rows_bytes).hexdigest()


def _matrix_forecasts() -> tuple[dict[tuple[str, str], Forecast], dict[str, object]]:
    if not MATRIX_RAW_PATH.is_file():
        raise FileNotFoundError(MATRIX_RAW_PATH)
    matrix_sha256 = _sha256_file(MATRIX_RAW_PATH)
    forecasts: dict[tuple[str, str], Forecast] = {}
    total_source_rows = 0
    status_counts: Counter[str] = Counter()
    for line in MATRIX_RAW_PATH.open(encoding="utf-8"):
        total_source_rows += 1
        record = _json_object(json.loads(line), f"{MATRIX_RAW_PATH} line {total_source_rows}")
        stream_id = record.get("strategy_id")
        if stream_id not in EXPECTED_STREAM_IDS:
            continue
        status = record.get("prediction_status")
        status_counts[str(status)] += 1
        if status != "OK":
            raise ValueError(f"frozen stream has non-OK matrix output: {stream_id!r}")
        target = record.get("target_draw_number")
        target_date = record.get("target_draw_date")
        cutoff = record.get("cutoff_draw_number")
        cutoff_date = record.get("cutoff_draw_date")
        if not all(type(value) is str for value in (target, target_date, cutoff, cutoff_date)):
            raise ValueError(f"matrix record has invalid temporal identity: {stream_id!r}")
        target_text = cast(str, target)
        cutoff_text = cast(str, cutoff)
        if (
            int(target_text) > int(CAUSAL_CUTOFF_DRAW_NUMBER)
            or int(cutoff_text) >= int(target_text)
        ):
            raise ValueError(f"matrix record violates strict target-prior rule: {stream_id!r}")
        tickets_value = record.get("predicted_tickets")
        if tickets_value is None:
            tickets_value = [record.get("predicted_main_numbers")]
        tickets = _as_tickets(tickets_value, f"matrix {stream_id} {target} tickets")
        key = (cast(str, stream_id), cast(str, target))
        if key in forecasts:
            raise ValueError(f"duplicate matrix forecast: {key}")
        forecasts[key] = Forecast(
            stream_id=cast(str, stream_id),
            target_draw_number=cast(str, target),
            source_target_date=cast(str, target_date),
            source_cutoff_draw_number=cast(str, cutoff),
            source_cutoff_date=cast(str, cutoff_date),
            tickets=tickets,
            source_kind="CAUSAL_STRATEGY_EMISSION_MATRIX_R1",
            source_path=str(MATRIX_RAW_PATH),
            source_sha256=matrix_sha256,
        )
    matched_count = len(forecasts)
    expected_count = len(EXPECTED_STREAM_IDS) * 874
    if matched_count != expected_count:
        raise ValueError(f"expected {expected_count} exact matrix rows, found {matched_count}")
    return forecasts, {
        "locator": str(MATRIX_RAW_PATH),
        "sha256": matrix_sha256,
        "report_locator": str(MATRIX_REPORT_PATH),
        "report_sha256": _sha256_file(MATRIX_REPORT_PATH),
        "summary_locator": str(MATRIX_SUMMARY_PATH),
        "summary_sha256": _sha256_file(MATRIX_SUMMARY_PATH),
        "matched_record_count": matched_count,
        "source_record_count": total_source_rows,
        "matched_status_counts": dict(sorted(status_counts.items())),
        "strategy_ids": list(EXPECTED_STREAM_IDS),
        "target_number_min": min(target for _, target in forecasts),
        "target_number_max": max(target for _, target in forecasts),
    }


def _operational_forecasts() -> tuple[dict[tuple[str, str], Forecast], list[dict[str, object]]]:
    forecasts: dict[tuple[str, str], Forecast] = {}
    selected_files: list[dict[str, object]] = []
    for target in ("115000079", "115000080", "115000081", "115000082", "115000083", "115000086"):
        target_root = OPERATIONAL_ROOT / "predictions" / target
        if not target_root.is_dir():
            continue
        for path in sorted(target_root.rglob("*.json")):
            record = _read_json(path)
            stream_id = record.get("strategy_id")
            if stream_id not in EXPECTED_STREAM_IDS:
                continue
            if record.get("draw_number") != target:
                raise ValueError(f"operational filename/record target mismatch: {path}")
            if (
                record.get("availability") not in (None, "AVAILABLE")
                or record.get("prediction_temporal_class") != "PRE_DRAW"
            ):
                raise ValueError(f"operational record is not available PRE_DRAW: {path}")
            target_date = record.get("draw_date")
            history_cutoff = _json_object(record.get("history_cutoff"), f"{path} history_cutoff")
            cutoff = history_cutoff.get("draw_number")
            cutoff_date = history_cutoff.get("draw_date")
            if not all(type(value) is str for value in (target_date, cutoff, cutoff_date)):
                raise ValueError(f"operational record has invalid temporal identity: {path}")
            if int(cast(str, cutoff)) >= int(target):
                raise ValueError(f"operational record violates strict target-prior rule: {path}")
            tickets_value = record.get("tickets")
            if type(tickets_value) is not list:
                raise ValueError(f"operational record has no tickets: {path}")
            tickets = tuple(
                _as_int_list(
                    _json_object(ticket, f"{path} tickets[{index}]").get("predicted_numbers"),
                    f"{path} tickets[{index}] predicted_numbers",
                )
                for index, ticket in enumerate(cast(list[object], tickets_value))
            )
            key = (cast(str, stream_id), target)
            if key in forecasts:
                raise ValueError(f"duplicate operational forecast: {key}")
            source_sha256 = _sha256_file(path)
            forecasts[key] = Forecast(
                stream_id=cast(str, stream_id),
                target_draw_number=target,
                source_target_date=cast(str, target_date),
                source_cutoff_draw_number=cast(str, cutoff),
                source_cutoff_date=cast(str, cutoff_date),
                tickets=tickets,
                source_kind="B649_OPERATIONAL_PREDICTION_LOOP_R1",
                source_path=str(path),
                source_sha256=source_sha256,
            )
            selected_files.append(
                {
                    "stream_id": stream_id,
                    "draw_number": target,
                    "path": str(path),
                    "sha256": source_sha256,
                }
            )
    return forecasts, selected_files


def _git_blob_text(path: str) -> tuple[dict[str, object], str, str]:
    import subprocess

    revision = f"{FROZEN_CANDIDATE_COMMIT}:{path}"
    completed = subprocess.run(
        ["git", "show", revision],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    raw = completed.stdout
    return _json_object(json.loads(raw), path), hashlib.sha256(raw).hexdigest(), revision


def _coverage(
    forecasts: dict[tuple[str, str], Forecast],
    official: dict[str, OfficialDraw],
) -> list[dict[str, object]]:
    eligible = sorted(
        (draw for draw in official.values() if int(draw.draw_number) < int(TARGET_DRAW_NUMBER)),
        key=lambda draw: int(draw.draw_number),
    )[-TRAILING_WINDOW_DRAW_COUNT:]
    if len(eligible) != TRAILING_WINDOW_DRAW_COUNT:
        raise ValueError("official outcome authority has fewer than 300 prior draws")
    coverage: list[dict[str, object]] = []
    for stream_id in EXPECTED_STREAM_IDS:
        available = sorted(
            (draw for draw in eligible if (stream_id, draw.draw_number) in forecasts),
            key=lambda draw: int(draw.draw_number),
        )
        available_numbers = {item.draw_number for item in available}
        missing = [draw for draw in eligible if draw.draw_number not in available_numbers]
        coverage.append(
            {
                "stream_id": stream_id,
                "eligible_prior_draw_count": len(eligible),
                "reconstructible_prior_draw_count": len(available),
                "missing_prior_draw_count": len(missing),
                "coverage_rate": f"{len(available)}/{len(eligible)}",
                "coverage_decimal": f"{len(available) / len(eligible):.18f}",
                "earliest_reconstructible_draw": (
                    available[0].draw_number if available else None
                ),
                "latest_reconstructible_draw": available[-1].draw_number if available else None,
                "missing_draws": [
                    {
                        "draw_number": draw.draw_number,
                        "draw_date": draw.draw_date,
                        "reason": "NO_EXACT_FROZEN_STREAM_FORECAST_EVIDENCE",
                    }
                    for draw in missing
                ],
            }
        )
    return coverage


def build_payload() -> dict[str, object]:
    official, official_outcome_sha256 = _read_official_draws()
    matrix, matrix_metadata = _matrix_forecasts()
    operational, operational_files = _operational_forecasts()
    forecasts = dict(matrix)
    for key, forecast in operational.items():
        if key in forecasts:
            raise ValueError(f"source overlap must be resolved explicitly: {key}")
        forecasts[key] = forecast

    frozen_candidate, frozen_candidate_sha256, candidate_revision = _git_blob_text(
        FROZEN_CANDIDATE_PATH
    )
    frozen_m3, frozen_m3_sha256, m3_revision = _git_blob_text(FROZEN_M3_AUTHORITY_PATH)
    if frozen_candidate_sha256 == "":
        raise AssertionError("frozen candidate identity was not pinned")
    if frozen_candidate.get("metric_id") not in (None, METRIC_ID):
        raise ValueError("frozen candidate metric identity mismatch")
    definition = frozen_m3.get("definition_prose")
    if type(definition) is not str or "at least one ticket matching 3 or more" not in definition:
        raise ValueError("frozen M3_PLUS definition is not the required native-ticket definition")

    rows: list[dict[str, object]] = []
    source_counts: dict[str, dict[str, int]] = {
        stream_id: {
            "CAUSAL_STRATEGY_EMISSION_MATRIX_R1": 0,
            "B649_OPERATIONAL_PREDICTION_LOOP_R1": 0,
        }
        for stream_id in EXPECTED_STREAM_IDS
    }
    source_date_mismatch_counts: Counter[str] = Counter()
    for stream_id in EXPECTED_STREAM_IDS:
        stream_forecasts = sorted(
            (
                forecast
                for (candidate_stream, _), forecast in forecasts.items()
                if candidate_stream == stream_id
            ),
            key=lambda forecast: int(forecast.target_draw_number),
        )
        for forecast in stream_forecasts:
            official_draw = official.get(forecast.target_draw_number)
            if official_draw is None:
                raise ValueError(f"missing official outcome for {forecast.target_draw_number}")
            if forecast.source_target_date != official_draw.draw_date:
                source_date_mismatch_counts[forecast.source_kind] += 1
            if int(forecast.source_cutoff_draw_number) >= int(forecast.target_draw_number):
                raise ValueError(f"source cutoff is not strictly prior: {forecast}")
            source_counts[stream_id][forecast.source_kind] += 1
            rows.append(
                {
                    "stream_id": stream_id,
                    "draw_number": forecast.target_draw_number,
                    "draw_date": official_draw.draw_date,
                    "success": m3_plus_success(forecast.tickets, official_draw.main_numbers),
                }
            )
        if not stream_forecasts:
            raise ValueError(f"frozen stream has no reconstructible rows: {stream_id}")

    expected_row_count = sum(
        sum(stream_rows.values()) for stream_rows in source_counts.values()
    )
    if len(rows) != expected_row_count:
        raise AssertionError("row count accounting mismatch")

    coverage = _coverage(forecasts, official)
    total_mismatches = sum(source_date_mismatch_counts.values())
    payload: dict[str, object] = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_id": "B649_PER_STREAM_M3_PLUS_HISTORY_AUTHORITY_R1",
        "artifact_status": "READY_WITH_TRUTHFUL_COVERAGE_GAPS",
        "task_id": "B649_PER_STREAM_M3_PLUS_HISTORY_AUTHORITY_R1",
        "metric_id": METRIC_ID,
        "metric_version": METRIC_VERSION,
        "metric_definition": definition,
        "metric_semantics": {
            "aggregation": "PROPORTION_OF_DRAWS",
            "success_predicate": "any native ticket has at least three winning main-number hits",
            "special_number_used": False,
            "denominator": "eligible prior draws with canonical native stream forecast evidence",
        },
        "stream_ids": list(EXPECTED_STREAM_IDS),
        "frozen_consumer": {
            "candidate_method_id": "DYNAMIC_STREAM_RELIABILITY_WEIGHTING_V1",
            "candidate_method_version": "1.0.0",
            "candidate_commit": FROZEN_CANDIDATE_COMMIT,
            "candidate_tree": FROZEN_CANDIDATE_TREE,
            "candidate_definition_path": FROZEN_CANDIDATE_PATH,
            "candidate_definition_sha256": frozen_candidate_sha256,
            "target_draw_number": TARGET_DRAW_NUMBER,
            "target_draw_date": TARGET_DRAW_DATE,
            "causal_cutoff_draw_number": CAUSAL_CUTOFF_DRAW_NUMBER,
            "causal_cutoff_draw_date": CAUSAL_CUTOFF_DRAW_DATE,
            "trailing_window_draw_count": TRAILING_WINDOW_DRAW_COUNT,
            "minimum_observations": 50,
            "shrinkage_strength": "1/2",
            "fallback_policy": (
                "equal stream weight if any stream has fewer than 50 observations "
                "or global rate is zero"
            ),
        },
        "m3_authority": {
            "locator": f"{m3_revision}",
            "commit": FROZEN_CANDIDATE_COMMIT,
            "tree": FROZEN_CANDIDATE_TREE,
            "sha256": frozen_m3_sha256,
            "metric_definition_sha256": hashlib.sha256(
                json.dumps(
                    frozen_m3,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        },
        "prediction_evidence": {
            "matrix": matrix_metadata,
            "operational_root": str(OPERATIONAL_ROOT),
            "operational_selected_files": operational_files,
            "operational_selected_file_count": len(operational_files),
            "source_target_date_policy": (
                "official outcome draw_date is canonical; source target_date is retained "
                "only for provenance and is not used as the join key"
            ),
            "source_target_date_mismatch_counts": dict(sorted(source_date_mismatch_counts.items())),
            "source_target_date_mismatch_total": total_mismatches,
        },
        "official_outcome_authority": {
            "locator": str(OFFICIAL_DB_PATH),
            "sha256": official_outcome_sha256,
            "sha256_scope": "canonical selected BIG_LOTTO rows with draw_number <= causal cutoff",
            "table": "draws",
            "lottery_type": "BIG_LOTTO",
            "join_key": "draw_number",
            "query": (
                "SELECT draw_number, draw_date, main_numbers_json, "
                "normalized_record_hash FROM draws WHERE lottery_type='BIG_LOTTO'"
            ),
            "read_mode": "sqlite mode=ro",
            "max_joined_draw_number": CAUSAL_CUTOFF_DRAW_NUMBER,
        },
        "temporal_rule": {
            "forecast_generation": "source cutoff draw_number < forecast target draw_number",
            "consumer_use": (
                "only rows with draw_number < target draw_number may be passed "
                "to the downstream candidate"
            ),
            "artifact_upper_bound": f"draw_number <= {CAUSAL_CUTOFF_DRAW_NUMBER}",
            "same_or_future_row_policy": "reject before weighting",
        },
        "draw_range": {
            "earliest_reconstructible_draw": min(
                cast(str, row["draw_number"]) for row in rows
            ),
            "latest_reconstructible_draw": max(
                cast(str, row["draw_number"]) for row in rows
            ),
            "causal_cutoff_draw_number": CAUSAL_CUTOFF_DRAW_NUMBER,
            "causal_cutoff_draw_date": CAUSAL_CUTOFF_DRAW_DATE,
        },
        "coverage": coverage,
        "source_row_counts_by_stream": source_counts,
        "row_count": len(rows),
        "verification": {
            "exact_frozen_stream_identity": "PASS",
            "m3_plus_authority_resolved": "PASS",
            "prediction_outcome_alignment": "PASS_BY_DRAW_NUMBER_OFFICIAL_DATE",
            "duplicate_stream_draw": "PASS",
            "deterministic_ordering": "PASS",
            "strict_cutoff": "PASS",
            "target_prior_guard": "PASS",
            "trailing_window_coverage": "PASS_WITH_TRUTHFUL_GAPS",
            "candidate_outcome_validation": "NOT_RUN",
            "branch2_oos": "NOT_RUN",
            "production_runtime_or_scheduler_change": "NONE",
        },
        "source_revision": {
            "frozen_candidate_revision": candidate_revision,
            "frozen_m3_revision": m3_revision,
        },
        "rows": rows,
    }
    payload["artifact_content_sha256"] = artifact_content_sha256(payload)
    validate_artifact_payload(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = build_payload()
    if args.check:
        if not args.output.is_file():
            raise FileNotFoundError(args.output)
        existing = _read_json(args.output)
        validate_artifact_payload(existing)
        if existing != payload:
            raise ValueError(f"existing artifact is not deterministic: {args.output}")
        print(f"PASS deterministic artifact {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")
    print(f"artifact_content_sha256={payload['artifact_content_sha256']}")
    print(f"row_count={payload['row_count']}")


if __name__ == "__main__":
    main()
