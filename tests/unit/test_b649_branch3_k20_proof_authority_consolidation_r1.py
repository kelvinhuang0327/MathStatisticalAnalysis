"""Check the consolidated authority against its native frozen records and file bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lottolab.research.b649_k20_min_s2_higher_order_closure_r2 import (
    K20_INCUMBENT,
    K20_S1,
    K20_S2,
    K20_S3_BOUND,
    k20_min_s2_family_official_any_prize_upper_bound,
    k20_min_s2_s4_lower_bound_certificate,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs/research/matrix-native-results"
RECORD = RESULTS / "b649-branch3-k20-proof-authority-consolidation-r1.json"
MANIFEST = RESULTS / "b649-branch3-k20-proof-authority-consolidation-r1-sources.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_native_files_match_all_verified_source_and_baseline_hashes() -> None:
    manifest = _read(MANIFEST)
    copied = manifest["COPIED_FILES"]
    reused = manifest["REUSED_BASE_FILES"]
    assert len(copied) == 20
    assert {entry["source"] for entry in copied} == {"A", "B", "C", "D"}
    entries = copied + reused
    assert len({entry["path"] for entry in entries}) == len(entries)
    for entry in entries:
        content = (ROOT / entry["path"]).read_bytes()
        assert len(content) == entry["bytes"], entry["path"]
        assert hashlib.sha256(content).hexdigest() == entry["sha256"], entry["path"]
    known_paths = {entry["path"] for entry in entries}
    for module, dependencies in manifest["PYTHON_IMPORT_EDGES"].items():
        assert module in known_paths
        assert set(dependencies) <= known_paths
    assert not any("mass_ge13_global_bound" in entry["path"] for entry in copied)


def test_current_state_selects_the_frozen_authority_for_each_family() -> None:
    record = _read(RECORD)
    authorities = record["AUTHORITIES"]
    k10 = _read(ROOT / authorities["K10"]["record"])
    outside = _read(ROOT / authorities["K20_OUTSIDE_PAIR_LE1"]["record"])
    family_a = _read(ROOT / authorities["K20_FAMILY_A"]["record"])
    family_b = _read(ROOT / authorities["K20_FAMILY_B"]["record"])["CERTIFICATES"]
    family_c = _read(ROOT / authorities["K20_FAMILY_C"]["record"])["FAMILIES"]["C"]

    assert record["K10_GLOBAL_OPTIMUM_STATUS"] == k10["global_optimum_status"] == "PROVEN"
    assert record["K10_REMAINING_GAP"] == k10["remaining_gap"] == 0
    assert record["K20_INCUMBENT"] == K20_INCUMBENT == 313_239_661
    assert record["K20_MIN_S2_BOUND"] == k20_min_s2_family_official_any_prize_upper_bound()
    assert record["K20_MIN_S2_BOUND"] == 313_916_056
    assert record["K20_OUTSIDE_PAIR_LE1_BOUND"] == outside["FAMILIES"][0]["UPPER_BOUND"]
    assert record["K20_OUTSIDE_PAIR_LE1_BOUND"] == 311_435_293
    assert record["K20_FAMILY_A_BOUND"] == family_a["FAMILY_A_BOUND"] == 357_241_548
    assert record["K20_FAMILY_B_BOUND"] == family_b["FAMILY_B_BOUND"] == 357_794_343
    assert record["K20_FAMILY_C_BOUND"] == family_c["WEDGE_CERTIFICATE"]["upper_bound"]
    assert record["K20_FAMILY_C_BOUND"] == family_c["UPPER_BOUND"] == 311_499_152

    for family in ("MIN_S2", "OUTSIDE_PAIR_LE1", "FAMILY_A", "FAMILY_B", "FAMILY_C"):
        bound = record[f"K20_{family}_BOUND"]
        expected_status = "CLOSED" if bound < K20_INCUMBENT else "OPEN"
        assert record[f"K20_{family}_STATUS"] == expected_status


def test_global_bound_and_frozen_minimum_s2_terms_are_consistent() -> None:
    record = _read(RECORD)
    terms = record["AUTHORITIES"]["K20_MIN_S2"]["frozen_terms"]
    assert (terms["S1"], terms["S2"], terms["S3_UPPER"]) == (K20_S1, K20_S2, K20_S3_BOUND)
    assert terms["S4_LOWER"] == k20_min_s2_s4_lower_bound_certificate().s4_lower_bound == 112
    assert terms["FOURTH_ORDER_CREDIT"] == 4 * terms["S4_LOWER"] // 7 == 64
    assert record["K20_MIN_S2_BOUND"] == (
        terms["S1"] - terms["S2"] + terms["S3_UPPER"] - terms["FOURTH_ORDER_CREDIT"]
    )
    assert record["K20_MIN_S2_REMAINING_GAP"] == record["K20_MIN_S2_BOUND"] - K20_INCUMBENT
    assert record["K20_MIN_S2_REMAINING_GAP"] == 676_395
    bounds = [
        record[f"K20_{family}_BOUND"]
        for family in ("MIN_S2", "OUTSIDE_PAIR_LE1", "FAMILY_A", "FAMILY_B", "FAMILY_C")
    ]
    assert record["K20_GLOBAL_CERTIFIED_BOUND"] == max(bounds) == 357_794_343
    assert record["K20_REMAINING_GAP"] == record["K20_GLOBAL_CERTIFIED_BOUND"] - K20_INCUMBENT
    assert record["K20_REMAINING_GAP"] == 44_554_682


def test_recorded_verification_matches_the_integrated_focused_run() -> None:
    verification = _read(RECORD)["VERIFICATION"]
    assert verification["UV_SYNC"] == "PASS: uv sync --frozen --extra research"
    assert verification["FOCUSED_TESTS"] == "PASS: 40 passed across the 8 listed suites"
    assert verification["RUFF"] == "PASS: ruff check on all 15 changed Python files"
    assert verification["RUFF_FORMAT_CHECK"] == (
        "ADVISORY: 13 byte-for-byte imported source files differ from current formatter output"
    )
    assert verification["PYRIGHT"] == "PASS: scoped strict Pyright, 0 errors"
    assert verification["FALSIFIABILITY_CHECK"] == (
        "PASS: hash, Family B bound, and global bound mutations each failed their guarded test"
    )
