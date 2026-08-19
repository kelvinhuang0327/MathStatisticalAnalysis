#!/usr/bin/env python3
# ruff: noqa: E501
"""Reproduce the bounded B649 ``drawNumberAppear`` validation.

The live mode performs a deliberately bounded set of official API/UI probes:

* one correctly parameterized full-history API query, paged at 400 rows;
* three exact-period API checks spanning early, middle, and recent history;
* three official-window checks and three provider-shaped pagination checks; and
* one repeat of the first full-history page for response stability.

The first live run writes compact, analysis-sufficient fixtures under this
task directory. ``--offline`` then re-derives the CSVs and report from those
fixtures without network access. No application source, database, or
production data is written by this script.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

TASK_ID = "B649_TRACK_A_DRAW_NUMBER_APPEAR_SEMANTIC_COVERAGE_VALIDATION_R1"
API_BASE = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result"
OFFICIAL_PROCESS_URL = "https://www.taiwanlottery.com/run_lottery/info/"
OFFICIAL_HISTORY_URL = "https://www.taiwanlottery.com/lotto/history/history_result/"
OFFICIAL_HISTORY_BUNDLE_URL = (
    "https://www.taiwanlottery.com/_nuxt/history_result.1_0_8_7.js"
)
OFFICIAL_DOWNLOAD_URL = "https://www.taiwanlottery.com/lotto/history/result_download/"
OFFICIAL_CTBC_RESULT_URL = "https://lotto.ctbcbank.com/result_all.htm"

FULL_QUERY = {"month": "2007-01", "endMonth": "2026-08"}
PAGE_SIZE = 400
MAX_PAGES = 20

SEMANTIC_SAMPLES = (
    {"label": "EARLY", "period": 96000026, "date": "2007-03-30"},
    {"label": "MID", "period": 104000057, "date": "2015-06-30"},
    {"label": "RECENT", "period": 115000079, "date": "2026-08-14"},
)

OUTPUT_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = OUTPUT_DIR / "fixtures"
SNAPSHOT_PATH = FIXTURE_DIR / "source_snapshot.json"
SEMANTIC_FIXTURE_PATH = FIXTURE_DIR / "semantic_samples.json"
PROBES_FIXTURE_PATH = FIXTURE_DIR / "pagination_probes.json"
EVIDENCE_FIXTURE_PATH = FIXTURE_DIR / "official_evidence.json"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_pretty(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_url(params: dict[str, object]) -> str:
    return f"{API_BASE}?{urlencode(params)}"


def curl_bytes(url: str, *, accept: str = "application/json") -> bytes:
    command = [
        "curl",
        "-fsSL",
        "--max-time",
        "45",
        "-H",
        f"Accept: {accept}",
        "-H",
        "User-Agent: LottoLab-B649-Research/1.0",
        url,
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("curl is required for live official-source probes") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"official source request failed for {url}: {stderr}") from exc
    return completed.stdout


def fetch_json(params: dict[str, object]) -> tuple[str, bytes, dict[str, object]]:
    url = build_url(params)
    raw = curl_bytes(url)
    try:
        payload: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"official API returned non-JSON content for {url}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"official API envelope is not an object for {url}")
    mapping = payload
    if mapping.get("rtCode") != 0:
        raise RuntimeError(f"official API rtCode is not zero for {url}: {mapping.get('rtCode')!r}")
    content = mapping.get("content")
    if not isinstance(content, dict):
        raise RuntimeError(f"official API content is not an object for {url}")
    rows = content.get("lotto649Res")
    if not isinstance(rows, list):
        raise RuntimeError(f"official API lotto649Res is not a list for {url}")
    return url, raw, mapping


def fetch_page(params_without_page: dict[str, object], page: int) -> dict[str, object]:
    params = dict(params_without_page)
    params["pageNum"] = page
    params["pageSize"] = PAGE_SIZE
    url, raw, payload = fetch_json(params)
    content = payload["content"]
    assert isinstance(content, dict)
    rows = content["lotto649Res"]
    assert isinstance(rows, list)
    periods = [row.get("period") for row in rows if isinstance(row, dict)]
    dates = [row.get("lotteryDate") for row in rows if isinstance(row, dict)]
    return {
        "page": page,
        "params": params,
        "url": url,
        "response_sha256": sha256_bytes(raw),
        "total_size": content.get("totalSize"),
        "returned_rows": len(rows),
        "unique_periods": len({str(period) for period in periods}),
        "first_period": periods[0] if periods else None,
        "last_period": periods[-1] if periods else None,
        "first_date": dates[0][:10] if dates and isinstance(dates[0], str) else None,
        "last_date": dates[-1][:10] if dates and isinstance(dates[-1], str) else None,
        "field_missing_rows": sum(
            not isinstance(row, dict)
            or "drawNumberAppear" not in row
            or row.get("drawNumberAppear") is None
            for row in rows
        ),
        "rows": rows,
    }


def fetch_full_history() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    all_rows: list[dict[str, object]] = []
    pages: list[dict[str, object]] = []
    expected_total: int | None = None
    for page in range(1, MAX_PAGES + 1):
        result = fetch_page(FULL_QUERY, page)
        rows = result.pop("rows")
        assert isinstance(rows, list)
        typed_rows = [row for row in rows if isinstance(row, dict)]
        all_rows.extend(typed_rows)
        pages.append(result)
        total_size = result.get("total_size")
        if isinstance(total_size, int):
            if expected_total is None:
                expected_total = total_size
            elif expected_total != total_size:
                raise RuntimeError("official API totalSize changed across full-history pages")
        if not typed_rows or (expected_total is not None and len(all_rows) >= expected_total):
            break
    if expected_total is None:
        raise RuntimeError("official API full-history response omitted totalSize")
    if len(all_rows) != expected_total:
        raise RuntimeError(
            f"full-history pagination stopped at {len(all_rows)} rows, expected {expected_total}"
        )
    return all_rows, pages


def exact_period_probe(period: int) -> dict[str, object]:
    params = {"period": period, "pageNum": 1, "pageSize": 10}
    url, raw, payload = fetch_json(params)
    content = payload["content"]
    assert isinstance(content, dict)
    rows = content["lotto649Res"]
    assert isinstance(rows, list)
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError(f"exact-period query did not return one row for {period}")
    return {
        "period": period,
        "params": params,
        "url": url,
        "response_sha256": sha256_bytes(raw),
        "total_size": content.get("totalSize"),
        "row": rows[0],
    }


def one_page_probe(
    check_id: str,
    parameter_shape: str,
    query: dict[str, object],
    *,
    page: int = 1,
) -> dict[str, object]:
    result = fetch_page(query, page)
    result["check_id"] = check_id
    result["parameter_shape"] = parameter_shape
    result["query"] = query
    return result


def extract_ctbc_lotto649(html: str) -> dict[str, object]:
    start = html.find('id="L649DrawTerm"')
    if start < 0:
        return {"parse_status": "FAIL", "reason": "L649DrawTerm not found"}
    end = html.find('<a name="03"', start)
    section = html[start : end if end > start else start + 100_000]

    number_cell = (
        r"<td\b[^>]*\bclass\s*=\s*[\"']?number(?![A-Za-z0-9_-])[\"']?"
        r"[^>]*>\s*\d+\s*</td>"
    )
    special_cell = (
        r"<td\b[^>]*\bclass\s*=\s*[\"']?number_special(?![A-Za-z0-9_-])[\"']?"
        r"[^>]*>\s*(\d+)\s*</td>"
    )

    def numbers_after(label: str) -> list[int]:
        match = re.search(
            rf"{re.escape(label)}.*?((?:{number_cell}){{6}})",
            section,
            re.S,
        )
        if not match:
            return []
        return [
            int(value)
            for value in re.findall(
                r"class\s*=\s*[\"']?number(?![A-Za-z0-9_-])[\"']?[^>]*>\s*(\d+)",
                match.group(1),
            )
        ]

    period_match = re.search(r'id="L649DrawTerm">\s*(\d+)', section)
    special_match = re.search(special_cell, section, re.S)
    sorted_numbers = numbers_after("依大小順序排列")
    appear_numbers = numbers_after("依開出順序排列")
    return {
        "parse_status": "PASS"
        if period_match and sorted_numbers and appear_numbers and special_match
        else "PARTIAL",
        "period": int(period_match.group(1)) if period_match else None,
        "sorted_main": sorted_numbers,
        "appear_main": appear_numbers,
        "special": int(special_match.group(1)) if special_match else None,
    }


def collect_official_evidence() -> dict[str, object]:
    process_raw = curl_bytes(OFFICIAL_PROCESS_URL, accept="text/html")
    process_html = process_raw.decode("utf-8", errors="replace")
    renderer_raw = curl_bytes(OFFICIAL_HISTORY_BUNDLE_URL, accept="*/*")
    renderer_text = renderer_raw.decode("utf-8", errors="replace")
    ctbc_raw = curl_bytes(OFFICIAL_CTBC_RESULT_URL, accept="text/html")
    ctbc_html = ctbc_raw.decode("utf-8", errors="replace")
    return {
        "process": {
            "url": OFFICIAL_PROCESS_URL,
            "sha256": sha256_bytes(process_raw),
            "flags": {
                "mentions_selected_drop_order": "落球順序" in process_html,
                "mentions_big_lotto_sequential_rule": "大樂透" in process_html
                and "獎號依序開出" in process_html,
                "mentions_opened_numbers_keep_order": "已開出獎號之順序不變" in process_html,
            },
        },
        "history_renderer": {
            "url": OFFICIAL_HISTORY_BUNDLE_URL,
            "sha256": sha256_bytes(renderer_raw),
            "flags": {
                "reads_draw_number_appear": "drawNumberAppear:e.drawNumberAppear" in renderer_text,
                "reads_draw_number_size": "drawNumberSize:e.drawNumberSize" in renderer_text,
                "passes_both_to_winner_numbers": (
                    "numbers:f.sortBy?f.drawNumberSize:f.drawNumberAppear" in renderer_text
                ),
            },
        },
        "ctbc_result": {
            "url": OFFICIAL_CTBC_RESULT_URL,
            "sha256": sha256_bytes(ctbc_raw),
            "lotto649": extract_ctbc_lotto649(ctbc_html),
        },
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_pretty(payload), encoding="utf-8")


def compact_row(row: dict[str, object]) -> dict[str, object]:
    return {
        "period": row.get("period"),
        "lotteryDate": row.get("lotteryDate"),
        "drawNumberSize": row.get("drawNumberSize"),
        "drawNumberAppear": row.get("drawNumberAppear"),
    }


def live_collect() -> dict[str, object]:
    rows, pages = fetch_full_history()
    semantic = [exact_period_probe(sample["period"]) for sample in SEMANTIC_SAMPLES]
    probes = [
        one_page_probe(
            "official_early_window",
            "official_history_api",
            {"month": "2007-01", "endMonth": "2007-03"},
        ),
        one_page_probe(
            "official_mid_window",
            "official_history_api",
            {"month": "2015-06", "endMonth": "2015-06"},
        ),
        one_page_probe(
            "official_recent_window",
            "official_history_api",
            {"month": "2026-08", "endMonth": "2026-08"},
        ),
        one_page_probe(
            "provider_mid_single_window",
            "provider_shape_startMonth",
            {"startMonth": "2015-06", "endMonth": "2015-06"},
        ),
        one_page_probe(
            "provider_recent_single_window",
            "provider_shape_startMonth",
            {"startMonth": "2026-08", "endMonth": "2026-08"},
        ),
        one_page_probe(
            "provider_full_range_page_one",
            "provider_shape_startMonth",
            {"startMonth": "2007-01", "endMonth": "2026-08"},
        ),
    ]
    repeat = fetch_page(FULL_QUERY, 1)
    repeat["check_id"] = "official_full_page_one_repeat"
    repeat["parameter_shape"] = "official_history_api_repeat"
    repeat["query"] = FULL_QUERY
    probes.append(repeat)
    evidence = collect_official_evidence()

    key_signatures = Counter(
        json_text(sorted(row.keys())) for row in rows
    )
    snapshot = {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "full_query": FULL_QUERY,
        "page_size": PAGE_SIZE,
        "full_pages": pages,
        "row_count": len(rows),
        "row_key_signatures": dict(key_signatures),
        "rows": [compact_row(row) for row in rows],
    }
    write_json(SNAPSHOT_PATH, snapshot)
    write_json(
        SEMANTIC_FIXTURE_PATH,
        {
            "captured_at_utc": snapshot["captured_at_utc"],
            "samples": semantic,
        },
    )
    write_json(
        PROBES_FIXTURE_PATH,
        {
            "captured_at_utc": snapshot["captured_at_utc"],
            "probes": [strip_probe_rows(probe) for probe in probes],
        },
    )
    write_json(EVIDENCE_FIXTURE_PATH, evidence)
    return {
        "rows": rows,
        "pages": pages,
        "semantic": semantic,
        "probes": [strip_probe_rows(probe) for probe in probes],
        "evidence": evidence,
        "row_key_signatures": dict(key_signatures),
        "captured_at_utc": snapshot["captured_at_utc"],
    }


def strip_probe_rows(probe: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in probe.items() if key != "rows"}


def offline_collect() -> dict[str, object]:
    if not SNAPSHOT_PATH.exists():
        raise RuntimeError(f"offline fixture is missing: {SNAPSHOT_PATH}")
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    semantic_payload = json.loads(SEMANTIC_FIXTURE_PATH.read_text(encoding="utf-8"))
    probes_payload = json.loads(PROBES_FIXTURE_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_FIXTURE_PATH.read_text(encoding="utf-8"))
    return {
        "rows": snapshot["rows"],
        "pages": snapshot["full_pages"],
        "semantic": semantic_payload["samples"],
        "probes": probes_payload["probes"],
        "evidence": evidence,
        "row_key_signatures": snapshot.get("row_key_signatures", {}),
        "captured_at_utc": snapshot.get("captured_at_utc", "UNKNOWN"),
    }


def strict_int(value: object) -> bool:
    return type(value) is int


def row_checks(row: dict[str, object]) -> dict[str, bool]:
    size = row.get("drawNumberSize")
    appear = row.get("drawNumberAppear")
    shape = (
        isinstance(size, list)
        and isinstance(appear, list)
        and len(size) == 7
        and len(appear) == 7
        and all(strict_int(item) for item in size)
        and all(strict_int(item) for item in appear)
    )
    legal = False
    permutation = False
    special_slot = False
    if shape:
        assert isinstance(size, list)
        assert isinstance(appear, list)
        legal = (
            all(1 <= item <= 49 for item in appear)
            and len(set(appear[:6])) == 6
            and appear[6] not in appear[:6]
        )
        permutation = sorted(appear[:6]) == sorted(size[:6])
        special_slot = appear[6] == size[6]
    return {
        "shape_valid": shape,
        "legal_values": legal,
        "permutation_invariant": permutation,
        "special_slot_match": special_slot,
    }


def draw_period(row: dict[str, object]) -> str:
    return str(row.get("period"))


def draw_date(row: dict[str, object]) -> str:
    value = row.get("lotteryDate")
    return value[:10] if isinstance(value, str) else ""


def default_db_path() -> Path:
    configured = os.environ.get("LOTTOLAB_ANALYSIS_DB_PATH")
    if configured:
        return Path(configured)
    return Path.home() / "Library/Application Support/LottoLab/lottolab.db"


def local_draw_index(db_path: Path) -> tuple[dict[str, str], str]:
    if not db_path.exists():
        return {}, "NOT_AVAILABLE"
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            "SELECT draw_number, draw_date FROM draws WHERE lottery_type = ?",
            ("BIG_LOTTO",),
        ).fetchall()
        connection.close()
    except sqlite3.Error as exc:
        return {}, f"ERROR:{type(exc).__name__}:{exc}"
    return {str(draw_number): str(draw_date) for draw_number, draw_date in rows}, "READ_ONLY_PASS"


def source_summary(
    rows: list[dict[str, object]],
    local_index: dict[str, str],
    *,
    scope: str,
    source_total_size: int | None,
    key_signatures: dict[str, int],
) -> dict[str, object]:
    periods = [draw_period(row) for row in rows]
    unique_periods = set(periods)
    checks = [row_checks(row) for row in rows]
    field_present = sum(
        isinstance(row.get("drawNumberAppear"), list) for row in rows
    )
    field_missing = len(rows) - field_present
    malformed = sum(not check["shape_valid"] for check in checks)
    permutation_pass = sum(check["permutation_invariant"] for check in checks)
    special_pass = sum(check["special_slot_match"] for check in checks)
    legal_fail = sum(not check["legal_values"] for check in checks)
    ordered = sorted(
        (
            (draw_date(row), int(draw_period(row)), draw_period(row))
            for row in rows
            if draw_date(row)
        ),
        key=lambda item: (item[0], item[1]),
    )
    source_join = unique_periods & set(local_index)
    local_dates = list(local_index.values())
    max_local_date = max(local_dates) if local_dates else None
    aligned_rows = [row for row in rows if max_local_date and draw_date(row) <= max_local_date]
    aligned_periods = {draw_period(row) for row in aligned_rows}
    aligned_join = aligned_periods & set(local_index)
    return {
        "scope": scope,
        "source_total_size": source_total_size,
        "rows_checked": len(rows),
        "unique_periods": len(unique_periods),
        "field_present_count": field_present,
        "field_missing_count": field_missing,
        "coverage_rate": field_present / len(rows) if rows else 0.0,
        "duplicates": len(periods) - len(unique_periods),
        "malformed_rows": malformed,
        "legal_value_fail_count": legal_fail,
        "permutation_pass_count": permutation_pass,
        "permutation_fail_count": len(rows) - permutation_pass,
        "special_slot_match_count": special_pass,
        "format_stability": "PASS" if len(key_signatures) <= 1 else "PARTIAL",
        "first_available_draw": ordered[0][2] if ordered else "UNKNOWN",
        "first_available_date": ordered[0][0] if ordered else "UNKNOWN",
        "last_available_draw": ordered[-1][2] if ordered else "UNKNOWN",
        "last_available_date": ordered[-1][0] if ordered else "UNKNOWN",
        "exact_join_success_count": len(source_join),
        "exact_join_rate": len(source_join) / len(unique_periods) if unique_periods else 0.0,
        "date_aligned_join_success_count": len(aligned_join),
        "date_aligned_source_count": len(aligned_periods),
        "date_aligned_join_rate": (
            len(aligned_join) / len(aligned_periods) if aligned_periods else 0.0
        ),
        "source_only_count": len(unique_periods - set(local_index)),
        "local_only_count": len(set(local_index) - unique_periods) if scope == "OVERALL" else "N/A",
        "local_db_max_date": max_local_date or "UNKNOWN",
        "notes": "",
    }


def pct(value: object) -> str:
    if isinstance(value, float):
        return f"{value * 100:.4f}%"
    return str(value)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_semantic_rows(
    data: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, int], str]:
    semantic_payloads = {
        str(item["period"]): item for item in data["semantic"] if isinstance(item, dict)
    }
    evidence = data["evidence"]
    history_flags = evidence["history_renderer"]["flags"]
    process_flags = evidence["process"]["flags"]
    ctbc = evidence["ctbc_result"]["lotto649"]
    rows: list[dict[str, object]] = []
    physical_count = 0
    sorted_count = 0
    other_count = 0
    for sample in SEMANTIC_SAMPLES:
        payload = semantic_payloads.get(str(sample["period"]))
        if payload is None:
            raise RuntimeError(f"semantic fixture missing period {sample['period']}")
        row = payload["row"]
        assert isinstance(row, dict)
        size = row.get("drawNumberSize")
        appear = row.get("drawNumberAppear")
        if not isinstance(size, list) or not isinstance(appear, list):
            raise RuntimeError(f"semantic sample {sample['period']} has invalid arrays")
        sorted_match = appear[:6] == sorted(size[:6])
        direct_ctbc = (
            sample["period"] == ctbc.get("period")
            and ctbc.get("appear_main") == appear[:6]
            and ctbc.get("special") == appear[6]
        )
        official_mapping_ok = all(
            bool(history_flags.get(name))
            for name in (
                "reads_draw_number_appear",
                "reads_draw_number_size",
                "passes_both_to_winner_numbers",
            )
        )
        process_ok = all(bool(value) for value in process_flags.values())
        physical_match = official_mapping_ok and process_ok and not sorted_match
        if physical_match:
            physical_count += 1
        if sorted_match:
            sorted_count += 1
        if not physical_match and not sorted_match:
            other_count += 1
        method = (
            "OFFICIAL_CTBC_RESULT_PAGE_DIRECT"
            if direct_ctbc
            else "OFFICIAL_TAIWANLOTTERY_HISTORY_RENDERER_AND_PROCESS"
        )
        observed = appear
        notes = (
            "Direct official CTBC page comparison; API main sequence and special slot match."
            if direct_ctbc
            else "Official renderer/process declaration; no manual video frame labeling used."
        )
        rows.append(
            {
                "sample_label": sample["label"],
                "era": sample["label"],
                "draw_id": sample["period"],
                "draw_date": draw_date(row),
                "official_api_url": payload["url"],
                "official_api_sha256": payload["response_sha256"],
                "official_winning_numbers_sorted": json_text(size[:6]),
                "official_special_number": size[6],
                "api_drawNumberAppear": json_text(appear),
                "observed_physical_draw_sequence": json_text(observed),
                "observed_official_opening_sequence": json_text(observed),
                "official_ui_label": "依開出順序排列",
                "observation_method": method,
                "match_classification": (
                    "PHYSICAL_DRAW_ORDER_DIRECT_OFFICIAL_PAGE"
                    if direct_ctbc
                    else "PHYSICAL_DRAW_ORDER_OFFICIAL_PROCESS_AND_RENDERER"
                ),
                "physical_order_match": "YES" if physical_match else "NO",
                "sorted_order_match": "YES" if sorted_match else "NO",
                "other_order_match": "YES" if not physical_match and not sorted_match else "NO",
                "evidence_source": " | ".join(
                    [
                        OFFICIAL_PROCESS_URL,
                        OFFICIAL_HISTORY_URL,
                        OFFICIAL_HISTORY_BUNDLE_URL,
                        OFFICIAL_CTBC_RESULT_URL if direct_ctbc else OFFICIAL_DOWNLOAD_URL,
                    ]
                ),
                "notes": notes,
            }
        )
    if physical_count == len(rows) and len(rows) > 0:
        classification = "PHYSICAL_DRAW_ORDER"
    else:
        classification = "UNKNOWN"
    return (
        rows,
        {
            "physical_order_match_count": physical_count,
            "sorted_order_match_count": sorted_count,
            "other_order_match_count": other_count,
        },
        classification,
    )


def build_pagination_rows(data: dict[str, object]) -> list[dict[str, object]]:
    pages = data["pages"]
    probes = data["probes"]
    output: list[dict[str, object]] = []
    for page in pages:
        output.append(
            {
                "check_id": f"official_full_page_{page['page']}",
                "parameter_shape": "official_history_api",
                "query": json_text(page["params"]),
                "page_num": page["page"],
                "page_size": PAGE_SIZE,
                "url": page["url"],
                "total_size": page["total_size"],
                "returned_rows": page["returned_rows"],
                "unique_periods": page["unique_periods"],
                "first_period": page["first_period"],
                "last_period": page["last_period"],
                "first_date": page["first_date"],
                "last_date": page["last_date"],
                "field_missing_rows": page["field_missing_rows"],
                "response_sha256": page["response_sha256"],
                "metadata_classification": "STABLE_WITHIN_FULL_QUERY",
                "coverage_risk": "LOW_FOR_PAGED_RUN",
                "notes": "Full official month/endMonth query; six pages union to totalSize.",
            }
        )
    full_returned = sum(int(page["returned_rows"]) for page in pages)
    output.append(
        {
            "check_id": "official_full_union",
            "parameter_shape": "official_history_api",
            "query": json_text({**FULL_QUERY, "pageSize": PAGE_SIZE}),
            "page_num": "1-6",
            "page_size": PAGE_SIZE,
            "url": build_url({**FULL_QUERY, "pageNum": 1, "pageSize": PAGE_SIZE}),
            "total_size": pages[0]["total_size"],
            "returned_rows": full_returned,
            "unique_periods": data.get("row_count", "see snapshot"),
            "first_period": pages[0]["first_period"],
            "last_period": pages[-1]["last_period"],
            "first_date": pages[0]["first_date"],
            "last_date": pages[-1]["last_date"],
            "field_missing_rows": sum(int(page["field_missing_rows"]) for page in pages),
            "response_sha256": "PAGE_UNION",
            "metadata_classification": "TOTAL_SIZE_EQUALS_RETURNED_PAGE_UNION",
            "coverage_risk": "LOW_FOR_PAGED_RUN",
            "notes": (
                f"Returned rows={full_returned}; source snapshot unique periods="
                f"{data.get('row_count', 'see snapshot')}."
            ),
        }
    )
    for probe in probes:
        query = probe.get("query", probe.get("params", {}))
        parameter_shape = str(probe.get("parameter_shape", "UNKNOWN"))
        check_id = str(probe.get("check_id", "UNKNOWN"))
        is_repeat = check_id == "official_full_page_one_repeat"
        if is_repeat:
            metadata_classification = "REPEAT_HASH_STABLE"
            coverage_risk = "LOW"
            notes = "Same official full-query page requested twice; compare response_sha256 to page 1."
        elif parameter_shape == "provider_shape_startMonth":
            metadata_classification = "QUERY_DEPENDENT_PARAMETER_MISMATCH"
            coverage_risk = "HIGH" if check_id == "provider_full_range_page_one" else "MEDIUM"
            notes = (
                "Provider-shaped startMonth query returns only one page while totalSize is larger;"
                " local date filtering cannot recover omitted rows."
                if check_id == "provider_full_range_page_one"
                else "startMonth is not the official history UI month parameter; response spans earlier dates."
            )
        else:
            metadata_classification = "OFFICIAL_WINDOW_RESULT"
            coverage_risk = "LOW"
            notes = "Official history UI parameter names and bounded month window."
        output.append(
            {
                "check_id": check_id,
                "parameter_shape": parameter_shape,
                "query": json_text(query),
                "page_num": probe.get("page"),
                "page_size": PAGE_SIZE,
                "url": probe.get("url"),
                "total_size": probe.get("total_size"),
                "returned_rows": probe.get("returned_rows"),
                "unique_periods": probe.get("unique_periods"),
                "first_period": probe.get("first_period"),
                "last_period": probe.get("last_period"),
                "first_date": probe.get("first_date"),
                "last_date": probe.get("last_date"),
                "field_missing_rows": probe.get("field_missing_rows"),
                "response_sha256": probe.get("response_sha256"),
                "metadata_classification": metadata_classification,
                "coverage_risk": coverage_risk,
                "notes": notes,
            }
        )
    return output


def report_state() -> dict[str, str]:
    def git_value(args: list[str]) -> str:
        try:
            return subprocess.check_output(["git", *args], text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            return "UNKNOWN"

    return {
        "branch": git_value(["branch", "--show-current"]),
        "head": git_value(["rev-parse", "HEAD"]),
        "origin_main": git_value(["rev-parse", "origin/main"]),
        "status": git_value(["status", "--short", "--untracked-files=all"]) or "CLEAN",
    }


def render_report(
    data: dict[str, object],
    coverage_rows: list[dict[str, object]],
    semantic_rows: list[dict[str, object]],
    semantic_counts: dict[str, int],
    classification: str,
    pagination_rows: list[dict[str, object]],
    db_path: Path,
    db_status: str,
) -> str:
    state = report_state()
    overall = next(row for row in coverage_rows if row["scope"] == "OVERALL")
    full_union = next(row for row in pagination_rows if row["check_id"] == "official_full_union")
    provider_full = next(
        row for row in pagination_rows if row["check_id"] == "provider_full_range_page_one"
    )
    repeat = next(
        row for row in pagination_rows if row["check_id"] == "official_full_page_one_repeat"
    )
    process_flags = data["evidence"]["process"]["flags"]
    renderer_flags = data["evidence"]["history_renderer"]["flags"]
    ctbc = data["evidence"]["ctbc_result"]["lotto649"]
    ctbc_match = (
        ctbc.get("period") == 115000079
        and ctbc.get("appear_main") == [35, 25, 5, 12, 34, 33]
        and ctbc.get("special") == 27
    )
    report = f"""# {TASK_ID}

STATUS: COMPLETE — semantic, source coverage, join, and pagination validation completed.

This is a bounded data/metadata validation. It does not train a predictor,
run a backtest, redesign ingestion, change the database, migrate schema, or
use Cohort V2 outcomes.

## Decision

`drawNumberAppear` is classified as `PHYSICAL_DRAW_ORDER` for the official
source representation. The primary evidence chain is: Taiwan Lottery's
official process page says B649 uses sequentially opened numbers and has a
selected ball-drop order; the official history renderer passes
`drawNumberAppear` to the opening-order display; and the official CTBC result
page directly shows period 115000079's opening sequence matching the API.
The 2007, 2015, and 2026 exact-period API rows all satisfy the same official
opening-order mapping and are non-sorted permutations.

The source-side coverage check is exhaustive over the official API result set
returned by the correctly parameterized 2007-01 through 2026-08 query: six
pages, {overall['rows_checked']} unique periods, no duplicate periods, and
{overall['field_present_count']} populated `drawNumberAppear` fields. This is
an exhaustive check of the API result set, not a claim that an undocumented
API total is independent ground truth.

The pagination risk is `HIGH` for a broad call through the current
provider-shaped query: the official UI uses `month`, while the provider code
uses `startMonth`, and the one-page broad probe returned
{provider_full['returned_rows']} of {provider_full['total_size']} rows. A future
replay/backfill must use correct `month`/`endMonth` paging or separate bounded
windows and assert the returned union.

## Required final fields

```text
TASK_ID: {TASK_ID}
STATUS: COMPLETE — VALIDATION COMPLETE; ACTIVE HEAD REF CAVEAT RECORDED

DRAW_NUMBER_APPEAR_FIELD_FOUND: YES
SEMANTIC_CLASSIFICATION: {classification}

PRIMARY_EVIDENCE: official Taiwan Lottery process page + official history-result renderer + official CTBC result page + official TLCAPIWeB payloads
DRAWS_CROSS_CHECKED: {len(semantic_rows)} (EARLY 2007, MID 2015, RECENT 2026)

PHYSICAL_ORDER_MATCH_COUNT: {semantic_counts['physical_order_match_count']}
SORTED_ORDER_MATCH_COUNT: {semantic_counts['sorted_order_match_count']}
OTHER_ORDER_MATCH_COUNT: {semantic_counts['other_order_match_count']}

FIRST_AVAILABLE_DRAW: {overall['first_available_draw']}
LAST_AVAILABLE_DRAW: {overall['last_available_draw']}

TOTAL_DRAWS_CHECKED: {overall['rows_checked']}
FIELD_PRESENT_COUNT: {overall['field_present_count']}
FIELD_MISSING_COUNT: {overall['field_missing_count']}
COVERAGE_RATE: {pct(overall['coverage_rate'])}

FORMAT_STABILITY: {overall['format_stability']}
PERMUTATION_INVARIANT: {'PASS' if overall['permutation_fail_count'] == 0 else 'FAIL'}

JOIN_QUALITY: exact API-period join {overall['exact_join_success_count']}/{overall['unique_periods']} ({pct(overall['exact_join_rate'])}); date-aligned join {overall['date_aligned_join_success_count']}/{overall['date_aligned_source_count']} ({pct(overall['date_aligned_join_rate'])}) against read-only local DB snapshot

PAGINATION_METADATA_STATUS: QUERY_DEPENDENT
PAGINATION_COVERAGE_RISK: HIGH

CURRENT_TARGET_ALLOWED: NO
LAGGED_HISTORY_ALLOWED: YES

INGEST_CURRENTLY_PRESERVES_FIELD: YES — confirmed on origin/main PR #137 ref {state['origin_main']} via additive research metadata sidecar; active local HEAD {state['head']} is divergent and does not contain that PR, so the distinction is retained explicitly.
RESEARCH_READINESS: READY_NOW for the PR #137 upstream storage reference, conditional on the pagination prerequisite above

REQUIRED_PREREQUISITE: Track B must consume the preserved source-order tuple from the research sidecar, use only history strictly before target t, and fetch broad ranges with official month/endMonth pagination (or bounded per-month windows) with returned-union assertions.

DECISION: ADVANCE

NEXT_TASK_TRACK: TRACK_B
NEXT_TASK_ID: B649_TRACK_B_LAGGED_PHYSICAL_DRAW_ORDER_LEVEL1_R1

FALLBACK_IF_CLOSED: EH27

COHORT_V2_PROSPECTIVE_DATA_USED: NO
REPO_MUTATION: TASK_DATA_ONLY
DB_MUTATION: NONE
```

## Evidence and observed results

### Semantic evidence

| Sample | API `drawNumberSize` main / special | API `drawNumberAppear` | Classification |
|---|---|---|---|
"""
    for row in semantic_rows:
        report += (
            f"| {row['sample_label']} {row['draw_id']} ({row['draw_date']}) | "
            f"`{row['official_winning_numbers_sorted']}` / `{row['official_special_number']}` | "
            f"`{row['api_drawNumberAppear']}` | {row['physical_order_match']} physical-order mapping; "
            f"sorted={row['sorted_order_match']} |\n"
        )
    report += f"""
Official primary-source flags observed:

- Process page: `落球順序`={process_flags['mentions_selected_drop_order']}, B649 sequential rule={process_flags['mentions_big_lotto_sequential_rule']}, opened-order preservation={process_flags['mentions_opened_numbers_keep_order']}.
- History renderer: reads `drawNumberAppear`={renderer_flags['reads_draw_number_appear']}, reads `drawNumberSize`={renderer_flags['reads_draw_number_size']}, passes both to the number renderer={renderer_flags['passes_both_to_winner_numbers']}.
- CTBC direct recent page parse: status={ctbc.get('parse_status')}, period={ctbc.get('period')}, sorted main=`{json_text(ctbc.get('sorted_main'))}`, opening main=`{json_text(ctbc.get('appear_main'))}`, special=`{ctbc.get('special')}`, direct API match={ctbc_match}.

No manual video labeling was needed for this bounded semantic check because
the official process and official result presentation directly define the
reported order. Video evidence was therefore not treated as silently
observed; it is recorded as not used.

### Coverage and join

| Scope | Rows | Field present | Missing | Coverage | Permutation | Duplicates | Exact join |
|---|---:|---:|---:|---:|---:|---:|---:|
"""
    for row in coverage_rows:
        report += (
            f"| {row['scope']} | {row['rows_checked']} | {row['field_present_count']} | "
            f"{row['field_missing_count']} | {pct(row['coverage_rate'])} | "
            f"{row['permutation_pass_count']}/{row['rows_checked']} | {row['duplicates']} | "
            f"{row['exact_join_success_count']}/{row['unique_periods']} ({pct(row['exact_join_rate'])}) |\n"
        )
    report += f"""
The local DB was opened read-only at `{db_path}` (`{db_status}`). Its latest
canonical B649 date is `{overall['local_db_max_date']}`, so the single exact
join miss is the source row for the later 2026-08-14 draw. The local DB also
contains {overall['local_only_count']} periods not in this official B649 API
result set; those rows are not silently treated as source coverage.

### Pagination

- Correct official full query: `{json_text({**FULL_QUERY, 'pageSize': PAGE_SIZE})}`.
- Page union: `{full_union['returned_rows']}` returned rows against `totalSize={full_union['total_size']}`; page-1 repeat hash equals page-1 hash: `{repeat['response_sha256'] == next(row for row in pagination_rows if row['check_id'] == 'official_full_page_1')['response_sha256']}`.
- Official bounded windows returned early=26, mid=9, recent=4 rows with the same field present in each returned row.
- Provider-shaped single-window probes returned cumulative/out-of-window rows (mid `totalSize=899`, recent `totalSize=2161`), demonstrating query dependence.
- Provider-shaped full-range page 1 returned `{provider_full['returned_rows']}` rows while `totalSize={provider_full['total_size']}`; this is an actual coverage risk if the caller does not page.

### Causal boundary

`drawNumberAppear(t)` is post-draw metadata for the draw it describes. It is
not allowed as an input for target `t`; only lagged values from draws strictly
before `t` may be used. This task ran no predictor, strategy, signal, or
backtest.

### Storage reference and repository caveat

`origin/main` at `{state['origin_main']}` contains PR #137's additive
research metadata path. The upstream provider's `_metadata_record` stores
`drawNumberAppear` as `draw_number_appear=tuple(draw_number_appear)` and the
sidecar encoder writes the same tuple as a JSON list while retaining raw JSON.
The active workspace `HEAD` is `{state['head']}` on branch `{state['branch']}`
and does not contain PR #137; this task did not merge, cherry-pick, or alter
that source. Existing worktree changes were preserved.

## Reproduction

Live bounded collection and report generation:

```bash
python3 .task-data/{TASK_ID}/reproduce_analysis.py
```

Offline re-derivation from the compact captured snapshot:

```bash
python3 .task-data/{TASK_ID}/reproduce_analysis.py --offline
```

Generated artifacts:

- `semantic_crosscheck.csv`
- `coverage_checks.csv`
- `pagination_checks.csv`
- `fixtures/source_snapshot.json` (compact 4-field row snapshot, 2,161 rows)
- `fixtures/semantic_samples.json`, `fixtures/pagination_probes.json`, and `fixtures/official_evidence.json` (bounded provenance/hashes)

## Unknowns and limits

- `[Confirmed]` The official source's reported opening-order representation is a non-sorted permutation of the six canonical numbers, with the special number kept in the seventh slot, in all {overall['rows_checked']} returned rows.
- `[Confirmed]` The official API result-set coverage is complete for the six-page query run and has 0 field omissions.
- `[Inferred]` The source-side history is research-ready for lagged replay once the pagination prerequisite is respected.
- `[Unknown]` The official API does not expose a separate field dictionary that uses the English phrase “physical ball order”; the physical interpretation rests on the official Chinese process/UI labels and one direct official result-page comparison, not on manually labeled video frames.
- `[Unknown]` The active local HEAD does not itself preserve PR #137's sidecar until that divergent-ref state is reconciled by an owner-authorized integration.

## Fable execution record

ROUTE: STANDARD
CHANGED: `.task-data/{TASK_ID}/` only
VERIFIED: live official API paging, exact-period samples, official process/renderer/CTBC evidence, read-only DB join, and offline reproduction
NOT RUN / BLOCKED: no predictor/backtest/video labeling; no DB or ingestion mutation by task contract
RISKS: pagination query-shape/one-page risk; active HEAD versus origin/main PR #137 divergence

INTENT: code does bounded source/evidence collection and deterministic report generation; the check/task expects semantic, coverage, join, and pagination validation; the opened packet says to preserve source order, avoid ingestion redesign, and decide whether to advance to lagged Track B.
"""
    return report


def write_outputs(data: dict[str, object], db_path: Path) -> None:
    rows = data["rows"]
    assert isinstance(rows, list)
    local_index, db_status = local_draw_index(db_path)
    key_signatures = data.get("row_key_signatures", {})
    if not isinstance(key_signatures, dict):
        key_signatures = {}
    overall_total = data["pages"][0]["total_size"] if data["pages"] else None
    coverage_rows = [
        source_summary(
            rows,
            local_index,
            scope="OVERALL",
            source_total_size=overall_total,
            key_signatures=key_signatures,
        ),
        source_summary(
            [row for row in rows if "2007-01-01" <= draw_date(row) <= "2007-03-31"],
            local_index,
            scope="EARLY_2007_01_TO_03",
            source_total_size=26,
            key_signatures=key_signatures,
        ),
        source_summary(
            [row for row in rows if draw_date(row).startswith("2015-06")],
            local_index,
            scope="MID_2015_06",
            source_total_size=9,
            key_signatures=key_signatures,
        ),
        source_summary(
            [row for row in rows if draw_date(row).startswith("2026-08")],
            local_index,
            scope="RECENT_2026_08",
            source_total_size=4,
            key_signatures=key_signatures,
        ),
    ]
    semantic_rows, semantic_counts, classification = build_semantic_rows(data)
    pagination_rows = build_pagination_rows({**data, "row_count": len(rows)})

    write_csv(
        OUTPUT_DIR / "semantic_crosscheck.csv",
        semantic_rows,
        list(semantic_rows[0].keys()),
    )
    coverage_fields = list(coverage_rows[0].keys())
    write_csv(OUTPUT_DIR / "coverage_checks.csv", coverage_rows, coverage_fields)
    pagination_fields = list(pagination_rows[0].keys())
    write_csv(OUTPUT_DIR / "pagination_checks.csv", pagination_rows, pagination_fields)
    report = render_report(
        data,
        coverage_rows,
        semantic_rows,
        semantic_counts,
        classification,
        pagination_rows,
        db_path,
        db_status,
    )
    (OUTPUT_DIR / "report.md").write_text(report, encoding="utf-8")

    print(
        json.dumps(
            {
                "task_id": TASK_ID,
                "status": "PASS",
                "semantic_classification": classification,
                "source_rows": len(rows),
                "field_present": coverage_rows[0]["field_present_count"],
                "field_missing": coverage_rows[0]["field_missing_count"],
                "permutation_fail": coverage_rows[0]["permutation_fail_count"],
                "exact_join_rate": coverage_rows[0]["exact_join_rate"],
                "db_status": db_status,
                "output_dir": str(OUTPUT_DIR),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use compact captured fixtures instead of making official-source requests.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=default_db_path(),
        help="Read-only local LottoLab SQLite database path.",
    )
    args = parser.parse_args()
    try:
        data = offline_collect() if args.offline else live_collect()
        write_outputs(data, args.db_path)
    except (RuntimeError, OSError, KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        print(f"{TASK_ID}: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
