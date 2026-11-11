"""Read-only API for the receipt-pinned A/D strategy identity crosswalk."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

API_VERSION = "v1"
SOURCE_VERSION = "NUMBER2_A_CURRENT_D_RANK_IDENTITY_CROSSWALK_20261103_R1"
DEFAULT_SOURCE_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261103/"
    "NUMBER2_A_CURRENT_D_RANK_IDENTITY_CROSSWALK_20261103_R1"
)
SOURCE_ROOT_ENV = "NUMBER2_AD_CROSSWALK_SOURCE_ROOT"
CROSSWALK_CSV_PATH = DEFAULT_SOURCE_ROOT / "current_ad_crosswalk.csv"
CROSSWALK_UNMATCHED_CSV_PATH = DEFAULT_SOURCE_ROOT / "unmatched_ad_identities.csv"
CROSSWALK_RESULT_PATH = DEFAULT_SOURCE_ROOT / "result.json"
CROSSWALK_SUMMARY_PATH = DEFAULT_SOURCE_ROOT / "crosswalk_summary.json"
PINNED_CSV_SHA256 = "0abb159bb1ce161770b5a4d9937adc54e1cbc94a09d1f15c708cdc20944c68ba"
PINNED_UNMATCHED_CSV_SHA256 = "82e9343e1ee0253be1ec62d026bb3711f437e9a12c24efda6d1e57d753327ba9"
PINNED_RESULT_SHA256 = "0605a5be5bb1097081c0fc0db9b48feabd68919706bf57cccac0a7c4e77ef098"
PINNED_SUMMARY_SHA256 = "ec35988052b93744c293ece911efcd22eae91664958bfccad3d26c9730bee48a"
EXPECTED_SOURCE_ROWS = 559
EXPECTED_UNMATCHED_ROWS = 553
EXPECTED_LEGACY_D58_ROWS = 58
LEGACY_D58_SCOPE = "LEGACY_A_D58_RETAINED"
LEGACY_D58_STATUS = "LEGACY_UNMATCHED_RETAINED"
EXPECTED_SCORE_IDENTITY_COUNTS = {
    "EXACT_MATCH": 64,
    "PARTIAL_IDENTITY": 108,
    "UNMATCHED": 30,
}
EXPECTED_SCOPE_COUNTS = {
    "SCORED_IDENTITY": 202,
    "STATUS_ONLY_IDENTITY": 326,
    "UNKNOWN_STATUS_IDENTITY": 31,
}
EXPECTED_ROW_STATUS_COUNTS = {
    "EXACT_MATCH": 64,
    "PARTIAL_IDENTITY": 358,
    "UNMATCHED": 106,
    "UNKNOWN": 31,
}
MATCH_STATUSES = frozenset(EXPECTED_ROW_STATUS_COUNTS)
ALL_MATCH_STATUSES = MATCH_STATUSES | {LEGACY_D58_STATUS}
IDENTITY_SCOPES = frozenset(EXPECTED_SCOPE_COUNTS)
EXPECTED_HEADERS = frozenset(
    {
        "identity_scope",
        "identity_key",
        "game",
        "strategy_id",
        "strategy_version",
        "policy_version",
        "algorithm_version",
        "variant_type",
        "configured_seed",
        "source_variant",
        "match_status",
        "identity_relation",
        "exact_gap",
        "app_identity_mapping_status",
        "app_catalog_version_candidates_json",
        "a_locator",
        "a_source_locator",
        "a_strategy_source_locator",
        "a_strategy_source_sha256",
        "a_source_sha256s_json",
        "a_k_windows_json",
        "a_full_denominators_json",
        "d_source_task_ids_json",
        "d_source_sha256s_json",
        "d_locators_json",
        "d_score_evidence_json",
        "d_status_evidence_json",
        "d_rank_evidence_json",
        "d_k_windows_json",
        "d_history_denominators_json",
        "legacy_d58_pair_overlap",
    }
)
SOURCE_GROUP_RE = re.compile(r'"source_group"\s*:\s*("(?:\\.|[^"\\])*")')
QUERY_PARAMETERS = frozenset(
    {"strategy_id", "strategy_version", "match_status", "source_group", "limit", "offset"}
)
SORT_FIELDS = (
    "game",
    "strategy_id",
    "strategy_version",
    "policy_version",
    "algorithm_version",
    "variant_type",
    "identity_scope",
    "identity_key",
)
LOCAL_ABSOLUTE_PATH_RE = re.compile(r"/Users/[^\s,;\"'<>\]}]+")
_SOURCE_FILE_NAMES = {
    "current_csv": "current_ad_crosswalk.csv",
    "legacy_csv": "unmatched_ad_identities.csv",
    "result": "result.json",
    "summary": "crosswalk_summary.json",
}


class CrosswalkReadError(RuntimeError):
    """Raised when pinned Crosswalk inputs cannot be read without ambiguity."""


class _BadRequest(ValueError):
    """Raised for malformed or unsupported query parameters."""


def _resolve_configured_source_root(raw_root: str | Path) -> Path:
    value = str(raw_root)
    if not value.strip() or value != value.strip():
        raise CrosswalkReadError(f"{SOURCE_ROOT_ENV} must be a nonblank absolute directory.")
    candidate = Path(value)
    if not candidate.is_absolute():
        raise CrosswalkReadError(f"{SOURCE_ROOT_ENV} must be an absolute directory.")
    try:
        root = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise CrosswalkReadError("Configured Crosswalk source root is unavailable.") from exc
    if not root.is_dir():
        raise CrosswalkReadError("Configured Crosswalk source root is not a directory.")
    return root


def _source_paths(source_root: str | Path | None) -> Mapping[str, Path]:
    if source_root is None:
        return {
            "current_csv": CROSSWALK_CSV_PATH,
            "legacy_csv": CROSSWALK_UNMATCHED_CSV_PATH,
            "result": CROSSWALK_RESULT_PATH,
            "summary": CROSSWALK_SUMMARY_PATH,
        }

    root = _resolve_configured_source_root(source_root)
    paths: dict[str, Path] = {}
    for label, filename in _SOURCE_FILE_NAMES.items():
        candidate = root / filename
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as exc:
            raise CrosswalkReadError(
                f"Configured Crosswalk source is unavailable: {label}."
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise CrosswalkReadError(
                f"Configured Crosswalk source escapes its root: {label}."
            ) from exc
        if not resolved.is_file():
            raise CrosswalkReadError(f"Configured Crosswalk source is not a file: {label}.")
        paths[label] = resolved
    return paths


@dataclass(frozen=True)
class CrosswalkReadModel:
    rows: tuple[Mapping[str, Any], ...]
    legacy_rows: tuple[Mapping[str, Any], ...]
    row_status_counts: Mapping[str, int]
    scope_counts: Mapping[str, int]
    score_identity_status_counts: Mapping[str, int]
    source_groups: frozenset[str]


def _read_pinned_bytes(path: Path, expected_sha256: str, label: str) -> bytes:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise CrosswalkReadError(f"Pinned {label} is unavailable.") from exc
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if actual_sha256 != expected_sha256:
        raise CrosswalkReadError(f"Pinned {label} SHA-256 does not match its receipt.")
    return content


def _read_json_receipt(content: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CrosswalkReadError(f"Pinned {label} is not valid JSON.") from exc
    if not isinstance(value, dict):
        raise CrosswalkReadError(f"Pinned {label} has an invalid structure.")
    return value


def _verify_receipt_links(result: Mapping[str, Any], summary: Mapping[str, Any]) -> None:
    if (
        result.get("task_id") != SOURCE_VERSION
        or result.get("task_lifecycle_state") != "COMPLETED"
    ):
        raise CrosswalkReadError("Crosswalk completion receipt has an unexpected identity.")
    output = result.get("outputs", {}).get("current_ad_crosswalk.csv", {})
    if output.get("sha256") != PINNED_CSV_SHA256 or output.get("rows") != EXPECTED_SOURCE_ROWS:
        raise CrosswalkReadError("Crosswalk completion receipt does not match the pinned CSV.")
    counts = summary.get("counts", {})
    if counts.get("current_bridge_rows") != EXPECTED_SOURCE_ROWS:
        raise CrosswalkReadError("Crosswalk summary row count does not match the pinned CSV.")
    expected_scored_identities = sum(EXPECTED_SCORE_IDENTITY_COUNTS.values())
    if counts.get("d_score_identity_keys_variant") != expected_scored_identities:
        raise CrosswalkReadError("Crosswalk summary scored identity count is inconsistent.")
    summary_statuses = counts.get("d_score_identity_match_status_counts", {})
    if summary_statuses != EXPECTED_SCORE_IDENTITY_COUNTS:
        raise CrosswalkReadError("Crosswalk summary identity statuses do not match the pinned CSV.")
    unmatched_output = result.get("outputs", {}).get("unmatched_ad_identities.csv", {})
    if (
        unmatched_output.get("sha256") != PINNED_UNMATCHED_CSV_SHA256
        or unmatched_output.get("rows") != EXPECTED_UNMATCHED_ROWS
        or counts.get("unmatched_output_rows") != EXPECTED_UNMATCHED_ROWS
        or counts.get("legacy_rows_retained_in_unmatched_output") != EXPECTED_LEGACY_D58_ROWS
        or counts.get("old_d58_distinct_strategy_version_pairs") != EXPECTED_LEGACY_D58_ROWS
    ):
        raise CrosswalkReadError("Crosswalk legacy D58 receipt does not match its pinned source.")


def _source_groups(raw_evidence: str) -> frozenset[str]:
    groups: set[str] = set()
    for match in SOURCE_GROUP_RE.finditer(raw_evidence):
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise CrosswalkReadError("Crosswalk source group evidence is malformed.") from exc
        if isinstance(value, str) and value:
            groups.add(value)
    return frozenset(groups)


def _walk_embedded_json(value: Any) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        records.append(value)
        for nested in value.values():
            records.extend(_walk_embedded_json(nested))
    elif isinstance(value, list):
        for nested in value:
            records.extend(_walk_embedded_json(nested))
    elif isinstance(value, str) and value[:1] in {"[", "{"}:
        try:
            records.extend(_walk_embedded_json(json.loads(value)))
        except json.JSONDecodeError:
            return records
    return records


def _legacy_groups(row: Mapping[str, Any]) -> frozenset[str]:
    groups: set[str] = set()
    for field in (
        "d_locators_json",
        "d_score_evidence_json",
        "d_status_evidence_json",
        "d_rank_evidence_json",
    ):
        for record in _walk_embedded_json(row.get(field, "")):
            group = record.get("source_group")
            if isinstance(group, str) and group:
                groups.add(group)
    return frozenset(groups)


def _parse_legacy_rows(content: bytes) -> tuple[tuple[Mapping[str, Any], ...], frozenset[str]]:
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8"), newline=""))
        headers = frozenset(reader.fieldnames or ())
        if not headers >= EXPECTED_HEADERS:
            raise CrosswalkReadError("Legacy D58 CSV is missing required identity fields.")
        all_rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CrosswalkReadError("Pinned legacy D58 CSV cannot be parsed.") from exc

    rows = [row for row in all_rows if row.get("identity_scope") == LEGACY_D58_SCOPE]
    if len(all_rows) != EXPECTED_UNMATCHED_ROWS or len(rows) != EXPECTED_LEGACY_D58_ROWS:
        raise CrosswalkReadError(
            "Legacy D58 row counts do not match the pinned completion receipt."
        )
    if any(
        row.get("match_status") != LEGACY_D58_STATUS
        or row.get("legacy_d58_pair_overlap") != "true"
        for row in rows
    ):
        raise CrosswalkReadError("Legacy D58 rows lost their historical unmatched status.")
    identity_keys = [row.get("identity_key", "") for row in rows]
    pairs = {(row.get("strategy_id"), row.get("strategy_version")) for row in rows}
    if (
        any(not identity_key for identity_key in identity_keys)
        or len(set(identity_keys)) != EXPECTED_LEGACY_D58_ROWS
        or len(pairs) != EXPECTED_LEGACY_D58_ROWS
    ):
        raise CrosswalkReadError("Legacy D58 identities are missing or duplicated.")

    groups: set[str] = set()
    frozen_rows: list[Mapping[str, Any]] = []
    for row in rows:
        row_groups = _legacy_groups(row)
        groups.update(row_groups)
        frozen_rows.append({**row, "_source_groups": tuple(sorted(row_groups))})
    frozen_rows.sort(key=lambda row: tuple(str(row.get(field) or "") for field in SORT_FIELDS))
    return tuple(frozen_rows), frozenset(groups)


@lru_cache(maxsize=1)
def _parse_crosswalk_csv(content: bytes) -> CrosswalkReadModel:
    try:
        decoded = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded, newline=""))
        headers = frozenset(reader.fieldnames or ())
        if not headers >= EXPECTED_HEADERS:
            raise CrosswalkReadError("Crosswalk CSV is missing required identity fields.")
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CrosswalkReadError("Pinned Crosswalk CSV cannot be parsed.") from exc

    if len(rows) != EXPECTED_SOURCE_ROWS:
        raise CrosswalkReadError("Crosswalk CSV row count does not match its completion receipt.")
    identity_keys = [row.get("identity_key", "") for row in rows]
    if any(not identity_key for identity_key in identity_keys) or len(set(identity_keys)) != len(
        rows
    ):
        raise CrosswalkReadError("Crosswalk identity keys are missing or duplicated.")

    row_status_counts = Counter(row.get("match_status", "") for row in rows)
    scope_counts = Counter(row.get("identity_scope", "") for row in rows)
    score_identity_status_counts = Counter(
        row.get("match_status", "")
        for row in rows
        if row.get("identity_scope") == "SCORED_IDENTITY"
    )
    if dict(row_status_counts) != EXPECTED_ROW_STATUS_COUNTS:
        raise CrosswalkReadError(
            "Crosswalk row statuses do not match the pinned completion summary."
        )
    if dict(scope_counts) != EXPECTED_SCOPE_COUNTS:
        raise CrosswalkReadError(
            "Crosswalk identity scopes do not match the pinned completion summary."
        )
    if dict(score_identity_status_counts) != EXPECTED_SCORE_IDENTITY_COUNTS:
        raise CrosswalkReadError(
            "Scored identity statuses do not match the pinned completion summary."
        )
    if any(row.get("identity_scope") not in IDENTITY_SCOPES for row in rows):
        raise CrosswalkReadError("Crosswalk contains an unknown identity scope.")
    if any(row.get("match_status") not in MATCH_STATUSES for row in rows):
        raise CrosswalkReadError("Crosswalk contains an unknown match status.")
    if any(
        row.get("identity_scope") != "SCORED_IDENTITY"
        or row.get("variant_type") != "NATIVE"
        or row.get("policy_version")
        or row.get("algorithm_version")
        for row in rows
        if row.get("match_status") == "EXACT_MATCH"
    ):
        raise CrosswalkReadError("Crosswalk exact identities do not meet the native-version rule.")
    legacy_pairs = {
        (row.get("strategy_id"), row.get("strategy_version"))
        for row in rows
        if row.get("legacy_d58_pair_overlap") == "true"
    }
    if len(legacy_pairs) != EXPECTED_LEGACY_D58_ROWS:
        raise CrosswalkReadError("Current crosswalk does not retain all legacy D58 version pairs.")

    frozen_rows: list[Mapping[str, Any]] = []
    source_groups: set[str] = set()
    for row in rows:
        groups = _source_groups(row.get("d_status_evidence_json", ""))
        source_groups.update(groups)
        frozen_rows.append({**row, "_source_groups": tuple(sorted(groups))})
    frozen_rows.sort(key=lambda row: tuple(str(row.get(field) or "") for field in SORT_FIELDS))
    return CrosswalkReadModel(
        rows=tuple(frozen_rows),
        legacy_rows=(),
        row_status_counts=dict(sorted(row_status_counts.items())),
        scope_counts=dict(sorted(scope_counts.items())),
        score_identity_status_counts=dict(sorted(score_identity_status_counts.items())),
        source_groups=frozenset(source_groups),
    )


def load_crosswalk_read_model(source_root: str | Path | None = None) -> CrosswalkReadModel:
    """Load only the exact CSV and completion receipts pinned by this module."""
    paths = _source_paths(source_root)
    result_content = _read_pinned_bytes(
        paths["result"], PINNED_RESULT_SHA256, "Crosswalk completion receipt"
    )
    summary_content = _read_pinned_bytes(
        paths["summary"], PINNED_SUMMARY_SHA256, "Crosswalk summary"
    )
    csv_content = _read_pinned_bytes(paths["current_csv"], PINNED_CSV_SHA256, "Crosswalk CSV")
    unmatched_content = _read_pinned_bytes(
        paths["legacy_csv"],
        PINNED_UNMATCHED_CSV_SHA256,
        "legacy D58 crosswalk source",
    )
    _verify_receipt_links(
        _read_json_receipt(result_content, "Crosswalk completion receipt"),
        _read_json_receipt(summary_content, "Crosswalk summary"),
    )
    current = _parse_crosswalk_csv(csv_content)
    legacy_rows, legacy_groups = _parse_legacy_rows(unmatched_content)
    return CrosswalkReadModel(
        rows=current.rows,
        legacy_rows=legacy_rows,
        row_status_counts=current.row_status_counts,
        scope_counts=current.scope_counts,
        score_identity_status_counts=current.score_identity_status_counts,
        source_groups=current.source_groups | legacy_groups,
    )


def _query(query_string: str) -> dict[str, str]:
    try:
        parsed = parse_qs(query_string, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise _BadRequest("Malformed query string") from exc
    unknown = set(parsed).difference(QUERY_PARAMETERS)
    if unknown:
        raise _BadRequest(f"Unsupported query parameters: {', '.join(sorted(unknown))}")
    result: dict[str, str] = {}
    for key, values in parsed.items():
        if len(values) != 1:
            raise _BadRequest(f"Parameter must appear once: {key}")
        if values[0] == "":
            raise _BadRequest(f"Parameter must not be empty: {key}")
        result[key] = values[0]
    return result


def _parse_pagination(query: Mapping[str, str]) -> tuple[int, int]:
    try:
        offset = int(query.get("offset", "0"))
        limit = int(query.get("limit", "100"))
    except ValueError as exc:
        raise _BadRequest("offset and limit must be integers") from exc
    if offset < 0 or offset > 1_000_000:
        raise _BadRequest("offset must be between 0 and 1000000")
    if limit < 1 or limit > 500:
        raise _BadRequest("limit must be between 1 and 500")
    return offset, limit


def _json_cell(row: Mapping[str, Any], key: str, default: Any) -> Any:
    raw = row.get(key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CrosswalkReadError("Pinned Crosswalk contains malformed JSON evidence.") from exc


def _logical_locator(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    locator, separator, fragment = value.partition("#")
    filename = locator.replace("\\", "/").rsplit("/", 1)[-1]
    if not filename:
        return None
    return f"{filename}#{fragment}" if separator else filename


def _logical_locators(values: list[str]) -> list[str]:
    result: set[str] = set()
    for value in values:
        logical = _logical_locator(value)
        if logical is not None:
            result.add(logical)
    return sorted(result)


def _legacy_locators(row: Mapping[str, Any]) -> list[str]:
    values = [str(row.get("a_locator") or "")]
    for field in (
        "d_locators_json",
        "d_score_evidence_json",
        "d_status_evidence_json",
        "d_rank_evidence_json",
    ):
        for record in _walk_embedded_json(_json_cell(row, field, [])):
            for key in ("source_locator", "input_locator", "result_locator", "locator"):
                locator = record.get(key)
                if isinstance(locator, str):
                    values.append(locator)
    return _logical_locators(values)


def _legacy_hashes(row: Mapping[str, Any]) -> list[str]:
    values = _strings(_json_cell(row, "a_source_sha256s_json", []))
    values.extend(_strings(_json_cell(row, "d_source_sha256s_json", [])))
    for field in (
        "d_locators_json",
        "d_score_evidence_json",
        "d_status_evidence_json",
        "d_rank_evidence_json",
    ):
        for record in _walk_embedded_json(_json_cell(row, field, [])):
            for key in ("source_sha256", "sha256"):
                digest = record.get(key)
                if isinstance(digest, str) and len(digest) == 64:
                    values.append(digest)
    return sorted(set(values))


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str) and item})


def _sanitize_public(value: Any) -> Any:
    if isinstance(value, str):
        return LOCAL_ABSOLUTE_PATH_RE.sub(
            lambda match: _logical_locator(match.group(0)) or "source", value
        )
    if isinstance(value, list):
        return [_sanitize_public(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_public(item) for item in value]
    if isinstance(value, Mapping):
        return {key: _sanitize_public(item) for key, item in value.items()}
    return value


def _row_identity(row: Mapping[str, Any], *, legacy: bool = False) -> dict[str, Any]:
    identity_key = str(row["identity_key"])
    if legacy:
        a_locators = _logical_locators([str(row.get("a_locator") or "")])
        d_locators = _legacy_locators(row)
        a_sha256s = _strings(_json_cell(row, "a_source_sha256s_json", []))
        d_sha256s = _legacy_hashes(row)
        source_file = "unmatched_ad_identities.csv"
        source_sha256 = PINNED_UNMATCHED_CSV_SHA256
        collection = "legacy_d58_snapshot"
    else:
        a_locators = _logical_locators(
            [
                str(row.get("a_locator") or ""),
                str(row.get("a_source_locator") or ""),
                str(row.get("a_strategy_source_locator") or ""),
            ]
        )
        d_locators = _logical_locators(_strings(_json_cell(row, "d_locators_json", [])))
        a_sha256s = _strings(_json_cell(row, "a_source_sha256s_json", []))
        strategy_sha = row.get("a_strategy_source_sha256")
        if strategy_sha:
            a_sha256s = sorted(set(a_sha256s) | {str(strategy_sha)})
        d_sha256s = _strings(_json_cell(row, "d_source_sha256s_json", []))
        source_file = "current_ad_crosswalk.csv"
        source_sha256 = PINNED_CSV_SHA256
        collection = "current_crosswalk"
    return {
        "crosswalk": {
            "collection": collection,
            "locator": f"{source_file}#identity_key={identity_key}",
            "version": SOURCE_VERSION,
            "sha256": source_sha256,
        },
        "a": {
            "locators": a_locators,
            "sha256s": a_sha256s,
            "catalog_version_candidates": _json_cell(
                row, "app_catalog_version_candidates_json", []
            ),
        },
        "d": {
            "locators": d_locators,
            "task_ids": _strings(_json_cell(row, "d_source_task_ids_json", [])),
            "sha256s": d_sha256s,
        },
    }


def _project_row(row: Mapping[str, Any], *, legacy: bool = False) -> dict[str, Any]:
    return {
        "identity_scope": row.get("identity_scope"),
        "identity_key": row.get("identity_key"),
        "game": row.get("game") or None,
        "strategy_id": row.get("strategy_id") or None,
        "strategy_version": row.get("strategy_version") or None,
        "policy_version": row.get("policy_version") or None,
        "algorithm_version": row.get("algorithm_version") or None,
        "variant_type": row.get("variant_type") or None,
        "configured_seed": row.get("configured_seed") or None,
        "source_variant": row.get("source_variant") or None,
        "match_status": row.get("match_status"),
        "identity_relation": row.get("identity_relation") or None,
        "app_identity_mapping_status": row.get("app_identity_mapping_status") or None,
        "source_groups": list(row.get("_source_groups", ())),
        "source_identity": _row_identity(row, legacy=legacy),
        "D_window_contract": {
            "history_denominators": _json_cell(row, "d_history_denominators_json", {}),
            "K_windows": _json_cell(row, "d_k_windows_json", []),
        },
        "App_window_contract": {
            "FULL_denominators": _json_cell(row, "a_full_denominators_json", []),
            "K_windows": _json_cell(row, "a_k_windows_json", []),
        },
        "exact_gap": row.get("exact_gap") or None,
    }


def _response_for(model: CrosswalkReadModel, query_string: str) -> dict[str, Any]:
    query = _query(query_string)
    match_status = query.get("match_status")
    if match_status is not None and match_status not in ALL_MATCH_STATUSES:
        raise _BadRequest(
            "match_status must be EXACT_MATCH, PARTIAL_IDENTITY, UNMATCHED, UNKNOWN, "
            "or LEGACY_UNMATCHED_RETAINED"
        )
    source_group = query.get("source_group")
    if source_group is not None and source_group not in model.source_groups:
        raise _BadRequest("source_group must match a source group present in the pinned crosswalk")
    offset, limit = _parse_pagination(query)

    matches = [
        row
        for row in model.rows
        if ("strategy_id" not in query or row.get("strategy_id") == query["strategy_id"])
        and (
            "strategy_version" not in query
            or row.get("strategy_version") == query["strategy_version"]
        )
        and (match_status is None or row.get("match_status") == match_status)
        and (source_group is None or source_group in row.get("_source_groups", ()))
    ]
    legacy_matches = [
        row
        for row in model.legacy_rows
        if ("strategy_id" not in query or row.get("strategy_id") == query["strategy_id"])
        and (
            "strategy_version" not in query
            or row.get("strategy_version") == query["strategy_version"]
        )
        and (match_status is None or row.get("match_status") == match_status)
        and (source_group is None or source_group in row.get("_source_groups", ()))
    ]
    page = matches[offset : offset + limit]
    return {
        "api_version": API_VERSION,
        "source": {
            "version": SOURCE_VERSION,
            "locator": "current_ad_crosswalk.csv",
            "sha256": PINNED_CSV_SHA256,
        },
        "counts": {
            "source_rows": EXPECTED_SOURCE_ROWS,
            "legacy_d58_rows": EXPECTED_LEGACY_D58_ROWS,
            "row_match_statuses": dict(model.row_status_counts),
            "identity_scopes": dict(model.scope_counts),
            "scored_identity_match_statuses": dict(model.score_identity_status_counts),
        },
        "source_group_values": sorted(model.source_groups),
        "query": {
            "strategy_id": query.get("strategy_id"),
            "strategy_version": query.get("strategy_version"),
            "match_status": match_status,
            "source_group": source_group,
            "offset": offset,
            "limit": limit,
        },
        "total": len(matches),
        "returned": len(page),
        "identities": [_project_row(row) for row in page],
        "legacy_d58": {
            "source": {
                "version": "legacy D58 snapshot preserved by the current Crosswalk receipt",
                "locator": "unmatched_ad_identities.csv",
                "sha256": PINNED_UNMATCHED_CSV_SHA256,
            },
            "total": len(legacy_matches),
            "returned": len(legacy_matches[offset : offset + limit]),
            "identities": [
                _project_row(row, legacy=True)
                for row in legacy_matches[offset : offset + limit]
            ],
        },
    }


def create_research_crosswalk_router(
    read_model_provider: Callable[[], CrosswalkReadModel] | None = None,
) -> APIRouter:
    """Register the pinned A/D identity crosswalk on the host FastAPI app."""
    router = APIRouter(prefix="/api/v1/research/backtests", tags=["research-crosswalk"])
    configured_value = os.environ.get(SOURCE_ROOT_ENV)
    configured_source_root: Path | None = None
    configuration_error: CrosswalkReadError | None = None
    if configured_value is not None:
        try:
            configured_source_root = _resolve_configured_source_root(configured_value)
        except CrosswalkReadError as exc:
            configuration_error = exc

    def configured_provider() -> CrosswalkReadModel:
        if configuration_error is not None:
            raise CrosswalkReadError(str(configuration_error)) from configuration_error
        return load_crosswalk_read_model(configured_source_root)

    @router.get("/identity-crosswalk")
    def identity_crosswalk(request: Request) -> JSONResponse:
        try:
            provider = read_model_provider or configured_provider
            model = provider()
            payload = _response_for(model, request.url.query)
            status = HTTPStatus.OK
        except _BadRequest as exc:
            status = HTTPStatus.BAD_REQUEST
            payload = {
                "api_version": API_VERSION,
                "error": "invalid_request",
                "message": str(exc),
            }
        except CrosswalkReadError as exc:
            status = HTTPStatus.SERVICE_UNAVAILABLE
            payload = {
                "api_version": API_VERSION,
                "error": "source_unavailable",
                "message": str(exc),
            }
        except Exception:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            payload = {
                "api_version": API_VERSION,
                "error": "internal_error",
                "message": "The identity crosswalk request could not be completed.",
            }
        return JSONResponse(
            status_code=status.value,
            content=_sanitize_public(payload),
            headers={"Cache-Control": "no-store"},
        )

    return router
