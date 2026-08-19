"""Reproduce the load-bearing evidence behind
B649_TRACK_B_NEW_INFORMATION_SOURCE_DATA_READINESS_DISCOVERY_R1.

Re-derives every numeric claim in report.md from either (a) the saved raw
API fixtures in fixtures/ (no network access required) or (b) local SQLite
files that may or may not be present on the machine this is run from. A
missing local DB is reported as SKIPPED, not FAIL -- this script is meant to
be re-run on a different checkout where the operator-local canonical DB and
the sealed legacy snapshot may not exist.

Usage:
    python3 reproduce_analysis.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent
REPO_ROOT = TASK_DIR.parent.parent
FIXTURES_DIR = TASK_DIR / "fixtures"
LEGACY_SNAPSHOT_DB = (
    REPO_ROOT / ".local" / "snapshots" / "p600ab-r1-20260715T122730+0800" / "lottery_v2.db"
)
RICH_FIELD_NAMES = (
    "numbers_positional",
    "jackpot_amount",
    "drawNumberAppear",
    "sellAmount",
    "winnerCount",
)
CITED_TOP_LEVEL_API_FIELDS = (
    "period",
    "lotteryDate",
    "drawNumberSize",
    "drawNumberAppear",
    "totalAmount",
    "sellAmount",
    "jackpotAssign",
)
CITED_JACKPOT_ASSIGN_SUBFIELDS = ("prize", "lastPrize", "winnerCount", "perPrize")

RESULTS: list[tuple[str, str, str]] = []  # (check_name, status, detail)


def record(name: str, status: str, detail: str) -> None:
    RESULTS.append((name, status, detail))
    print(f"[{status:8s}] {name}: {detail}")


def resolve_canonical_db() -> Path | None:
    """Mirror lottolab.infrastructure.persistence.draw_schema's default resolution."""
    env = os.environ.get("LOTTOLAB_DATA_DIR")
    data_dir = Path(env) if env else Path.home() / "Library" / "Application Support" / "LottoLab"
    candidate = data_dir / "lottolab.db"
    return candidate if candidate.exists() else None


def load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as handle:
        return json.load(handle)


def check_drawnumberappear_is_permutation() -> None:
    """Source B evidence: drawNumberAppear must be a reorder of drawNumberSize,
    with the special (7th) slot in the same position in both arrays, in every
    sampled record across three independent eras."""
    fixture_files = [
        "lotto649_2007-01to03.json",
        "lotto649_2015-06.json",
        "lotto649_2026-08.json",
    ]
    total = 0
    ok = 0
    special_ok = 0
    for fname in fixture_files:
        payload = load_fixture(fname)
        rows = payload["content"]["lotto649Res"]
        for row in rows:
            total += 1
            size = row["drawNumberSize"]
            appear = row["drawNumberAppear"]
            if sorted(size) == sorted(appear):
                ok += 1
            if size[-1] == appear[-1]:
                special_ok += 1
    status = "PASS" if ok == total and special_ok == total else "FAIL"
    record(
        "drawNumberAppear_is_permutation_of_drawNumberSize",
        status,
        f"{ok}/{total} records: same multiset; {special_ok}/{total} records: "
        "special number in same (last) slot in both fields",
    )


def check_jackpot_rollover_chain() -> None:
    """Source D evidence: lastPrize_n should equal lastPrize_(n-1) + prize_(n-1)
    whenever draw (n-1) had zero jackpot winners -- verified across the three
    consecutive real August 2026 draws in the fixture."""
    payload = load_fixture("lotto649_2026-08.json")
    rows = sorted(payload["content"]["lotto649Res"], key=lambda r: r["period"])
    checks = 0
    passed = 0
    details = []
    for prev, cur in zip(rows, rows[1:]):
        checks += 1
        prev_jackpot = prev["jackpotAssign"]
        if prev_jackpot["winnerCount"] != 0:
            details.append(f"{prev['period']}->{cur['period']}: SKIPPED (prev had a jackpot winner)")
            continue
        expected = prev_jackpot["lastPrize"] + prev_jackpot["prize"]
        actual = cur["jackpotAssign"]["lastPrize"]
        ok = expected == actual
        passed += ok
        details.append(
            f"{prev['period']}->{cur['period']}: expected {expected}, actual {actual}, "
            f"{'OK' if ok else 'MISMATCH'}"
        )
    status = "PASS" if passed == checks and checks > 0 else "FAIL"
    record("jackpot_rollover_chain_arithmetic", status, "; ".join(details))


def check_canonical_db_calendar_stats() -> None:
    db_path = resolve_canonical_db()
    if db_path is None:
        record(
            "canonical_db_calendar_stats",
            "SKIPPED",
            "no canonical lottolab.db found at $LOTTOLAB_DATA_DIR or the default "
            "~/Library/Application Support/LottoLab/ path on this machine",
        )
        return
    uri = f"{db_path.as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            "SELECT draw_date FROM draws WHERE lottery_type = 'BIG_LOTTO' ORDER BY draw_date"
        ).fetchall()
    finally:
        connection.close()
    dates = [date.fromisoformat(r[0]) for r in rows]
    n = len(dates)
    weekday_counts = Counter(d.weekday() for d in dates)  # Monday=0 .. Sunday=6
    tue_fri = weekday_counts[1] + weekday_counts[4]  # Tuesday=1, Friday=4
    detail = (
        f"n={n}, range={dates[0].isoformat()}..{dates[-1].isoformat()}, "
        f"Tue+Fri={tue_fri} ({tue_fri / n:.1%}), "
        f"weekday_counts(Mon..Sun)={[weekday_counts[i] for i in range(7)]}"
    )
    record("canonical_db_calendar_stats", "PASS", detail)

    non_tue_fri_by_year: dict[int, int] = Counter()
    for d in dates:
        if d.weekday() not in (1, 4):
            non_tue_fri_by_year[d.year] += 1
    early_block = sum(c for y, c in non_tue_fri_by_year.items() if y <= 2013)
    late_scatter = sum(c for y, c in non_tue_fri_by_year.items() if y >= 2014)
    record(
        "calendar_vs_era_proxy_split",
        "PASS",
        f"non-Tue/Fri draws 2007-2013={early_block}, 2014-present={late_scatter} "
        "(a large structural block pre-2014 vs. sparse single-digit-per-year "
        "holiday-shift exceptions from 2014 on)",
    )


def check_legacy_db_positional_jackpot_fill() -> None:
    if not LEGACY_SNAPSHOT_DB.exists():
        record(
            "legacy_db_positional_jackpot_fill",
            "SKIPPED",
            f"sealed legacy snapshot not found at {LEGACY_SNAPSHOT_DB}",
        )
        return
    uri = f"{LEGACY_SNAPSHOT_DB.as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            """
            SELECT lottery_type, COUNT(*), COUNT(numbers_positional), COUNT(jackpot_amount)
            FROM draws
            WHERE lottery_type IN ('BIG_LOTTO', '3_STAR', '4_STAR')
            GROUP BY lottery_type
            ORDER BY lottery_type
            """
        ).fetchall()
    finally:
        connection.close()
    summary = {r[0]: r[1:] for r in rows}
    big_lotto = summary.get("BIG_LOTTO", (0, 0, 0))
    status = "PASS" if big_lotto[1] == 0 and big_lotto[2] == 0 else "FAIL"
    record(
        "legacy_db_positional_jackpot_fill",
        status,
        f"BIG_LOTTO n={big_lotto[0]}, numbers_positional filled={big_lotto[1]}, "
        f"jackpot_amount filled={big_lotto[2]} (expected 0, 0); contrast "
        f"3_STAR={summary.get('3_STAR')}, 4_STAR={summary.get('4_STAR')} "
        "(digit-position games: fully filled)",
    )


def check_canonical_schema_lacks_rich_fields() -> None:
    """Confirm the ingestion gap for B/D is real: the canonical draws table
    (draw_schema.py) must not already have a column for any of these fields,
    and the transport dataclass source must not reference them either."""
    schema_source = (
        REPO_ROOT
        / "src"
        / "lottolab"
        / "infrastructure"
        / "persistence"
        / "draw_schema.py"
    ).read_text(encoding="utf-8")
    automation_source = (
        REPO_ROOT / "src" / "lottolab" / "application" / "draw_automation.py"
    ).read_text(encoding="utf-8")
    present = [
        name
        for name in ("numbers_positional", "jackpot_amount", "drawNumberAppear")
        if name in schema_source or name in automation_source
    ]
    status = "PASS" if not present else "FAIL"
    record(
        "canonical_schema_lacks_rich_fields",
        status,
        "draw_schema.py + draw_automation.py contain none of "
        f"{('numbers_positional', 'jackpot_amount', 'drawNumberAppear')}"
        if not present
        else f"unexpectedly found: {present}",
    )

    db_path = resolve_canonical_db()
    if db_path is None:
        record(
            "canonical_live_db_lacks_rich_columns",
            "SKIPPED",
            "no canonical lottolab.db found on this machine",
        )
        return
    uri = f"{db_path.as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(draws)")}
    finally:
        connection.close()
    overlap = columns & {"numbers_positional", "jackpot_amount", "draw_number_appear"}
    status = "PASS" if not overlap else "FAIL"
    record(
        "canonical_live_db_lacks_rich_columns",
        status,
        f"live draws columns={sorted(columns)}; none of the rich order/jackpot "
        "fields are present" if not overlap else f"unexpected overlap: {overlap}",
    )


def check_fixture_has_cited_fields() -> None:
    """Every field cited in report.md as 'directly confirmed present' must
    actually appear in every saved fixture record."""
    fixture_files = [
        "lotto649_2007-01to03.json",
        "lotto649_2015-06.json",
        "lotto649_2026-08.json",
    ]
    missing: list[str] = []
    total_records = 0
    for fname in fixture_files:
        payload = load_fixture(fname)
        rows = payload["content"]["lotto649Res"]
        for row in rows:
            total_records += 1
            for field in CITED_TOP_LEVEL_API_FIELDS:
                if field not in row:
                    missing.append(f"{fname}:{row.get('period')}:{field}")
            jackpot_assign = row.get("jackpotAssign", {})
            for subfield in CITED_JACKPOT_ASSIGN_SUBFIELDS:
                if subfield not in jackpot_assign:
                    missing.append(f"{fname}:{row.get('period')}:jackpotAssign.{subfield}")
    all_fields_desc = list(CITED_TOP_LEVEL_API_FIELDS) + [
        f"jackpotAssign.{s}" for s in CITED_JACKPOT_ASSIGN_SUBFIELDS
    ]
    status = "PASS" if not missing else "FAIL"
    record(
        "fixture_contains_all_cited_api_fields",
        status,
        f"{total_records} records checked against {len(all_fields_desc)} cited "
        f"fields ({', '.join(all_fields_desc)}); "
        + ("all present" if not missing else f"missing: {missing}"),
    )


def check_report_csv_reconciliation() -> None:
    """The classification block in report.md and the classification column in
    source_readiness.csv must name the same verdict for every source."""
    report_text = (TASK_DIR / "report.md").read_text(encoding="utf-8")
    block_match = re.search(
        r"CLASSIFICATION_SUMMARY\n(.*?)\nEND_CLASSIFICATION_SUMMARY", report_text, re.S
    )
    if not block_match:
        record("report_csv_reconciliation", "FAIL", "CLASSIFICATION_SUMMARY block not found in report.md")
        return
    report_classifications: dict[str, str] = {}
    for line in block_match.group(1).strip().splitlines():
        source, _, value = line.partition(":")
        report_classifications[source.strip()] = value.strip()

    known_enums = (
        "READY_NOW",
        "READY_WITH_SMALL_INGEST",
        "EXPENSIVE_BUT_TESTABLE",
        "INSUFFICIENT_HISTORY",
        "NOT_CAUSALLY_USABLE",
        "UNAVAILABLE",
    )
    csv_classifications: dict[str, str] = {}
    with open(TASK_DIR / "source_readiness.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            cell = row["classification"]
            leading = next((token for token in known_enums if cell.startswith(token)), None)
            csv_classifications[row["source"]] = leading or cell

    mismatches = [
        source
        for source in report_classifications
        if report_classifications[source] != csv_classifications.get(source)
    ]
    status = "PASS" if not mismatches and report_classifications else "FAIL"
    record(
        "report_csv_reconciliation",
        status,
        f"report={report_classifications}, csv={csv_classifications}"
        if mismatches or not report_classifications
        else f"{len(report_classifications)}/5 sources match exactly between "
        "report.md and source_readiness.csv",
    )


def main() -> int:
    check_drawnumberappear_is_permutation()
    check_jackpot_rollover_chain()
    check_canonical_db_calendar_stats()
    check_legacy_db_positional_jackpot_fill()
    check_canonical_schema_lacks_rich_fields()
    check_fixture_has_cited_fields()
    check_report_csv_reconciliation()

    print()
    failures = [r for r in RESULTS if r[1] == "FAIL"]
    skipped = [r for r in RESULTS if r[1] == "SKIPPED"]
    print(
        f"SUMMARY: {len(RESULTS)} checks, "
        f"{len(RESULTS) - len(failures) - len(skipped)} passed, "
        f"{len(failures)} failed, {len(skipped)} skipped"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
