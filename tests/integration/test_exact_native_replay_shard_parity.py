"""Integration tests: parity between the canonicalized exact-native BIG_LOTTO
replay engine and the pinned POST-PR231 donor evidence stream.

The full-donor parity test exercises the complete
:func:`replay_exact_native_target_range` orchestration -- including
``source_freeze``'s clean-git-tree guard -- so it requires a clean working
tree (the state expected once this migration's own commit lands) and takes
several minutes (2165 targets x 7 bindings = 15155 cells). It writes only to
a pytest ``tmp_path``, never to ``.task-data``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lottolab.application.use_cases.replay_exact_native_targets import (
    ReplayTargetRangeRequest,
    catalog_freeze,
    causal_row,
    load_authoritative_draws,
    replay_cell,
    replay_exact_native_target_range,
    runtime_bindings,
)
from lottolab.domain.exact_native_replay import Draw, freeze_visible_draws
from lottolab.domain.exact_native_replay import target_windows as compute_target_windows
from lottolab.evidence.exact_native_replay_manifest import (
    canonical_json_bytes,
    history_fingerprint,
    sha256_file,
)
from lottolab.infrastructure.persistence.draw_schema import resolve_local_data_paths

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "replay"
    / "biglotto_exact_native_115000083_parity_slice.jsonl"
)
RUN_ID = "B649_K5_K10_K20_EXACT_NATIVE_REFRESH_115000083_R1"
MAX_VISIBLE_DRAW = "115000083"
EXPECTED_MAIN_NUMBERS = (9, 20, 23, 26, 36, 44)
EXPECTED_SPECIAL_NUMBER = 4
EXPECTED_FULL_DONOR_SHA256 = "af576eb93a9a503ceae02825ef7723875b4e0894978c84725cf8757239d47702"
EXPECTED_FULL_DONOR_ROWS = 15155


def _draw_data_path() -> Path:
    return resolve_local_data_paths().database


draw_authority_present = pytest.mark.skipif(
    not _draw_data_path().is_file(),
    reason="the real LottoLab draw-authority database is not present on this machine",
)


def _fixture_rows() -> list[dict[str, object]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _current_universe() -> tuple[Draw, ...]:
    loaded_draws, _authority = load_authoritative_draws(_draw_data_path())
    return freeze_visible_draws(
        loaded_draws,
        max_visible_draw=MAX_VISIBLE_DRAW,
        expected_main_numbers=EXPECTED_MAIN_NUMBERS,
        expected_special_number=EXPECTED_SPECIAL_NUMBER,
    )


def test_committed_fixture_is_140_rows_of_20_targets_by_7_bindings() -> None:
    rows = _fixture_rows()
    assert len(rows) == 140
    targets = {row["target_draw_number"] for row in rows}
    assert len(targets) == 20
    assert all(row["schema_version"] == "B649_EXACT_NATIVE_TARGET_EVIDENCE_V1" for row in rows)


@draw_authority_present
def test_canonical_engine_reproduces_committed_fixture_rows_byte_identically() -> None:
    """Replays the fixture's own 20 targets (10 earliest + 10 latest of the
    full visible history) and checks every produced row against the
    committed fixture, in order."""

    descriptors, _universe = catalog_freeze()
    bindings = runtime_bindings(descriptors)
    all_draws = _current_universe()
    windows = compute_target_windows(all_draws)

    fixture_rows = _fixture_rows()
    target_indices = list(range(10)) + list(range(len(all_draws) - 10, len(all_draws)))
    produced_rows: list[dict[str, object]] = []
    for target_index in target_indices:
        target = all_draws[target_index]
        history = all_draws[:target_index]
        causal_rows = tuple(causal_row(d) for d in history)
        fingerprint = history_fingerprint(history)
        for binding in bindings:
            row = replay_cell(
                binding,
                target,
                history,
                windows,
                RUN_ID,
                causal_rows=causal_rows,
                history_fingerprint=fingerprint,
            )
            produced_rows.append(row)

    assert len(produced_rows) == len(fixture_rows) == 140
    for index, (produced, expected) in enumerate(zip(produced_rows, fixture_rows, strict=True)):
        assert canonical_json_bytes(produced) == canonical_json_bytes(expected), (
            f"row {index} mismatch"
        )


@draw_authority_present
def test_db_before_and_after_sha256_invariant_across_a_range_call(tmp_path: Path) -> None:
    db_path = _draw_data_path()
    sha_before_real = sha256_file(db_path)

    request = ReplayTargetRangeRequest(
        run_id=RUN_ID,
        draw_authority_db=db_path,
        repository_root=REPO_ROOT,
        output_path=tmp_path / "target_evidence.jsonl",
        start_index=0,
        end_index=10,
    )
    result = replay_exact_native_target_range(request)

    assert result.draw_authority["sha256_before"] == result.draw_authority["sha256_after"]
    sha_after_real = sha256_file(db_path)
    assert sha_after_real == sha_before_real


@draw_authority_present
def test_canonical_engine_reproduces_full_donor_evidence_byte_identically(tmp_path: Path) -> None:
    """The one required full donor parity execution: 2165 targets x 7 bindings
    = 15155 cells, byte-identical to the pinned POST-PR231 donor. Several
    minutes; writes only under ``tmp_path``."""

    all_draws = _current_universe()
    request = ReplayTargetRangeRequest(
        run_id=RUN_ID,
        draw_authority_db=_draw_data_path(),
        repository_root=REPO_ROOT,
        output_path=tmp_path / "target_evidence.jsonl",
        start_index=0,
        end_index=len(all_draws),
    )
    result = replay_exact_native_target_range(request)

    assert result.actual_rows == EXPECTED_FULL_DONOR_ROWS
    assert result.binding_count == 7
    assert result.evidence_sha256 == EXPECTED_FULL_DONOR_SHA256
