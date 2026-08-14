"""Structural consistency checks for the Strategy Matrix ledger.

Does not re-verify any individual cell's underlying research (that
verification happened, and is recorded, when each cell was sealed) --
only that the ledger file itself stays internally consistent and that
its generated Markdown view can still be produced from it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

LEDGER_PATH = Path("docs/research/cross_lottery_research_ledger_r1.json")
SCHEMA_DOC_PATH = Path("docs/research/cross-lottery-research-ledger-r1-schema.md")
REPORT_GENERATOR_PATH = Path("tools/generate_research_ledger_report.py")
REPORT_PATH = Path("docs/research/cross-lottery-research-ledger-r1.md")

_VALID_RECORD_STATES = {
    "REPORTED_LEGACY",
    "SEALED",
    "DESIGN_ABANDONED",
    "INVALIDATED",
    "SUPERSEDED",
}
_VALID_SOURCE_TYPES = {"STRATEGY_MATRIX_NATIVE", "EXTERNAL_PROJECT_RESEARCH_RESULT"}


def _load_ledger() -> dict[str, Any]:
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def _cells() -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = _load_ledger()["cells"]
    return cells


def _priors() -> list[dict[str, Any]]:
    priors: list[dict[str, Any]] = _load_ledger()["priors"]
    return priors


def test_ledger_and_schema_doc_exist() -> None:
    assert LEDGER_PATH.is_file()
    assert SCHEMA_DOC_PATH.is_file()


def test_ledger_has_expected_top_level_shape() -> None:
    ledger = _load_ledger()
    assert ledger["schema_version"] == "1.0.0"
    assert ledger["ledger_id"] == "CROSS_LOTTERY_RESEARCH_LEDGER_R1"
    assert len(_priors()) > 0
    assert len(_cells()) > 0


def test_cell_ids_are_unique() -> None:
    cell_ids = [cell["cell_id"] for cell in _cells()]
    assert len(cell_ids) == len(set(cell_ids))


def test_every_cell_has_a_valid_record_state_and_source_type() -> None:
    for cell in _cells():
        assert cell["record_state"] in _VALID_RECORD_STATES, cell["cell_id"]
        assert cell["source_type"] in _VALID_SOURCE_TYPES, cell["cell_id"]


def test_legacy_cells_are_honestly_marked_unverified() -> None:
    for cell in _cells():
        if cell["record_state"] == "REPORTED_LEGACY":
            assert cell["evidence_grade"] == "REPORTED_UNVERIFIED", cell["cell_id"]
            assert cell["preregistration_grade"] == "NOT_PREREGISTERED_UNDER_R1", cell["cell_id"]


def test_b649_diversification_cell_is_sealed_and_unchanged() -> None:
    cells = {cell["cell_id"]: cell for cell in _cells()}
    b649 = cells["DIVERSIFICATION_COVERAGE_B649_V1__BIG_LOTTO"]
    assert b649["record_state"] == "SEALED"
    assert b649["evidence_type"] == "EXACT_COMBINATORIAL"
    assert b649["descriptive_classification"] == "OUTPERFORMS_RANDOM_EXPECTED_COVERAGE"
    assert b649["hypothesis_family_id"] == "DIVERSIFICATION"
    assert b649["lottery_type"] == "BIG_LOTTO"


def test_t539_diversification_cell_replicates_b649() -> None:
    cells = {cell["cell_id"]: cell for cell in _cells()}
    t539 = cells["DIVERSIFICATION_COVERAGE_T539_V1__DAILY_539"]
    assert t539["record_state"] == "SEALED"
    assert t539["evidence_type"] == "EXACT_COMBINATORIAL"
    assert t539["descriptive_classification"] == "OUTPERFORMS_RANDOM_EXPECTED_COVERAGE"
    assert t539["hypothesis_family_id"] == "DIVERSIFICATION"
    assert t539["lottery_type"] == "DAILY_539"
    assert t539["related_legacy_evidence"] == []
    for artifact_path in t539["artifact_paths"]:
        assert Path(artifact_path).is_file(), artifact_path


def test_p638_zone1_diversification_cell_replicates_b649_and_t539() -> None:
    cells = {cell["cell_id"]: cell for cell in _cells()}
    p638 = cells["DIVERSIFICATION_COVERAGE_P638_ZONE1_V1__POWER_LOTTO_zone1"]
    assert p638["record_state"] == "SEALED"
    assert p638["evidence_type"] == "EXACT_COMBINATORIAL"
    assert p638["descriptive_classification"] == "OUTPERFORMS_RANDOM_EXPECTED_COVERAGE"
    assert p638["hypothesis_family_id"] == "DIVERSIFICATION"
    assert p638["lottery_type"] == "POWER_LOTTO"
    assert p638["zone"] == "zone1"
    assert p638["related_legacy_evidence"] == []
    for artifact_path in p638["artifact_paths"]:
        assert Path(artifact_path).is_file(), artifact_path


def test_report_generator_runs_and_covers_every_cell_id() -> None:
    subprocess.run([sys.executable, str(REPORT_GENERATOR_PATH)], check=True, capture_output=True)
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    for cell in _cells():
        assert cell["cell_id"] in report_text


def test_report_generation_is_deterministic_across_fresh_processes() -> None:
    # Each subprocess is a fresh Python process with its own (by default
    # randomized) string-hash seed. The family-order table groups cells by
    # `hypothesis_family_id` and breaks ties among same-`next_priority`
    # families using a *set*-derived ordering unless that ordering is
    # explicitly stabilized (see `generate_research_ledger_report.main`) --
    # without a stable tie-break, two fresh runs against the same ledger
    # could legitimately disagree on row order with no underlying data
    # change, which would show up as unrelated noise in every future diff.
    outputs: list[str] = []
    for _ in range(2):
        subprocess.run(
            [sys.executable, str(REPORT_GENERATOR_PATH)], check=True, capture_output=True
        )
        outputs.append(REPORT_PATH.read_text(encoding="utf-8"))
    assert outputs[0] == outputs[1]
