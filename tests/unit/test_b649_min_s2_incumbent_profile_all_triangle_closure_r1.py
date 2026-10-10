"""Focused checks for the all-T closure of the incumbent min-S2 profile 55555555555511111100."""

from __future__ import annotations

import copy
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from lottolab.research import b649_min_s2_incumbent_profile_all_triangle_closure_r1 as x

EXTERNAL = pytest.mark.skipif(
    not x.external_inputs_present(), reason="local proof origins or verifier worktree absent"
)
RELAXED = {1: 256, 2: 246, 3: 240, 4: 238, 5: 240, 6: 246, 7: 246, 8: 250, 9: 246, 10: 246,
           11: 249, 12: 256}  # fmt: skip


@pytest.fixture(scope="module")
def parsed() -> dict[str, dict[str, object]]:
    return x.load_sources()


@pytest.fixture(scope="module")
def authority() -> x.chase.Authority:
    return x.chase.load_authority()


@pytest.fixture(scope="module")
def ledger(authority: x.chase.Authority) -> dict[str, x.chase.Row]:
    return x.frozen_ledger(authority, x.chase_result())


def archive_copy(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    shutil.copytree(x.ROOT / x.SOURCE_DIRECTORY, root / x.SOURCE_DIRECTORY)
    return root


def test_archived_sources_are_pinned_and_state_their_claims(
    parsed: dict[str, dict[str, object]],
) -> None:
    tree = Path(__file__).resolve().parents[2]
    assert tree == x.ROOT and Path(x.__file__).resolve().is_relative_to(tree / "src")
    claims = x.check_claims(parsed)
    assert {k: x.object_row(v)["STATUS"] for k, v in claims.items()} == dict.fromkeys(
        ("T256_T262", "T263_T268", "T269", "T270"), "PASS"
    )
    gap_cells = sorted(t for s in x.SOURCES if s.key in ("T256_T262", "T263_T268", "T269")
                       for t in s.cells)  # fmt: skip
    assert gap_cells == list(range(256, 270))
    t270 = x.object_row(claims["T270"])
    assert t270["EXACT_CELL_MAX"] == 313_263_888 == x.INCUMBENT
    assert t270["CLASS_COUNTS"] == [313263867, 313263881, 313263881, 313263888, 313263888]
    assert t270["STS_REPRESENTATIVES_REBUILT_HERE"] is False


def test_tampered_archive_or_claim_fails_closed(
    tmp_path: Path, parsed: dict[str, dict[str, object]]
) -> None:
    root = archive_copy(tmp_path)
    target = root / x.SOURCE_DIRECTORY / "t269/result.json"
    target.write_bytes(target.read_bytes().replace(b"PROVED_EMPTY", b"PROVED_EMPTZ", 1))
    with pytest.raises(x.ClosureError, match="T269 result differs"):
        x.load_sources(root)
    t263 = copy.deepcopy(parsed["T263_T268"])
    t263["T266_STATUS"] = "NOT_CLOSED_BY_THIS_ARGUMENT"
    with pytest.raises(x.ClosureError, match="T263_T268 claim"):
        x.check_t263(t263)
    slice1 = copy.deepcopy(parsed["T270_COMMITTED_VERIFIER"])
    arithmetic = x.object_row(x.object_row(slice1["T270_EXACT_CLOSURE"])["STRUCTURAL_ARITHMETIC"])
    arithmetic["REALIZABLE_T"] = [270, 271]
    with pytest.raises(x.ClosureError, match="T270 claim"):
        x.check_t270(parsed["T270"], slice1)
    t256 = copy.deepcopy(parsed["T256_T262"])
    t256["EQUALITY_M12"] = "OPEN"
    with pytest.raises(x.ClosureError, match="equality-case"):
        x.graph_theorem(x.relaxation_table(), t256)


def test_independent_arithmetic_of_every_range(parsed: dict[str, dict[str, object]]) -> None:
    assert x.arm_term_minimum() == 4 and x.K12_PLUS_K8_MINUS_E == 270 and x.T_MAX == 272
    trace = x.above_exact_trace()
    assert [(t["T"], t["OPEN_WEDGES"], t["EVEN_C"]) for t in trace] == [
        (271, 3, [0]),
        (272, 0, [0]),
    ]
    table = x.relaxation_table()
    assert {m: row["RELAXED_BOUND"] for m, row in table.items()} == RELAXED
    theorem = x.graph_theorem(table, parsed["T256_T262"])
    assert theorem["NON_270_CEILING"] == 255 and theorem["EQUALITY_CASES_256_TO_255"] == [1, 12]
    assert x.gap_case_bounds() == {2: 30, 4: 30, 6: 36, 8: 28, 10: 30, 12: 30}
    recorded = x.object_row(x.check_t263(parsed["T263_T268"])["CASE_O_LOWER_BOUNDS"])
    assert x.gap_cells(recorded)["STATUS"] == "PASS"
    assert x.t269_cases()["H_INTERNAL_OPEN_WEDGE_FLOOR"] == {"2": 10, "4": 18}
    # Teeth: a weaker arm lemma or a missing F-degree cap no longer closes the ranges.
    with pytest.raises(x.ClosureError, match="T=271"):
        x.above_exact_trace(arm=2)
    with pytest.raises(x.ClosureError, match="unproved c"):
        x.gap_cells(recorded, arm=2)
    with pytest.raises(x.ClosureError, match="T269 c set"):
        x.t269_cases(arm=3)
    with pytest.raises(x.ClosureError, match="T269 is not excluded"):
        x.t269_cases(open_wedges=10)  # the c = 2 floor of 10 is tight by one
    uncapped = max(sum(d * d for d in p) for p in x.graphic_sequences(9, 12, 11))
    assert 270 - 20 * 9 + uncapped + table[9]["V_M"] == 258 > 255


def test_route_b_cap255_and_existing_cap() -> None:
    route = x.route_b_summary()
    assert route["ALL_T_MAX_BOUND"] == 313_263_412 and route["TERM_COUNT"] == 255 - 22 + 1
    assert x.object_row(route["ARGMAX"])["T"] == 255 and route["MARGIN_BELOW_INCUMBENT"] == 476
    assert route["ROUTE_B_AT_CAP_256_ABOVE_INCUMBENT"] == 313_272_568
    cap = x.existing_cap()
    assert (cap["NB_CAP"], cap["R18_CLASS_CAP"], cap["COMBINED_CAP"]) == (272, 270, 270)
    with pytest.raises(x.ClosureError, match="existing triangle cap"):
        x.existing_cap(269)


def test_partition_is_a_disjoint_cover_that_closes_the_profile() -> None:
    ranges = x.partition()
    cover = x.coverage(ranges)
    assert cover["PROFILE_OFFICIAL_MAX_UB"] == x.INCUMBENT < x.STRICT_GAIN_THRESHOLD
    with pytest.raises(x.ClosureError, match="disjoint cover"):
        x.coverage([r for r in ranges if r.low != 269])
    with pytest.raises(x.ClosureError, match="disjoint cover"):
        x.coverage([*ranges, x.Range(255, 255, "UPPER_BOUND", 1, ("X",))])
    with pytest.raises(x.ClosureError, match="not a source cell"):
        x.coverage([replace(r, authority=("T269",)) if r.low == 256 else r for r in ranges])


def test_single_profile_ledger_update(ledger: dict[str, x.chase.Row]) -> None:
    update = x.single_profile_update(ledger, x.INCUMBENT)
    assert (update["PROFILE_ROW_BEFORE"], update["PROFILE_ROW_AFTER"]) == (313_402_304, x.INCUMBENT)
    assert update["LEDGER_MAX_BEFORE"] == update["LEDGER_MAX_AFTER"] == 313_404_008
    assert update["FAMILY_UB_BEFORE"] == update["FAMILY_UB_AFTER"] == 313_404_008
    assert update["FAMILY_OWNER_IDS_AFTER"] == ["66666555555311100000"]
    assert update["NEXT_COMPETING_IDS_BEFORE"] == [x.PROFILE]
    assert (update["NEXT_COMPETING_BOUND_AFTER"], update["NEXT_COMPETING_IDS_AFTER"]) == (
        313_401_852,
        ["66655555555440000000"],
    )
    assert (update["ROWS_ABOVE_INCUMBENT_BEFORE"], update["ROWS_ABOVE_INCUMBENT_AFTER"]) == (
        1381,
        1380,
    )
    assert update["CHANGED_ROW_IDS"] == [x.PROFILE] and update["ROW_COUNT"] == 4647
    assert x.rows_digest(ledger) == x.LEDGER_ROWS_SHA256 == update["ROWS_SHA256_BEFORE"]
    assert all(row["APPLIED_HERE"] is False for row in x.unintegrated(ledger))
    with pytest.raises(x.ClosureError, match="does not tighten"):
        x.single_profile_update(ledger, x.LEDGER_ROW_BOUND)
    tampered = dict(ledger)
    tampered[x.PROFILE] = replace(ledger[x.PROFILE], cap=271)
    with pytest.raises(x.ClosureError, match="pinned R32 row"):
        x.single_profile_update(tampered, x.INCUMBENT)


@EXTERNAL
def test_reexecution_rejects_a_changed_frozen_result(tmp_path: Path) -> None:
    root = archive_copy(tmp_path)
    target = root / x.SOURCE_DIRECTORY / "t256-t262/result.json"
    target.write_bytes(target.read_bytes().replace(b'"T262_STATUS": "PROVED_EMPTY"',
                                                   b'"T262_STATUS": "OPEN"'))  # fmt: skip
    with pytest.raises(x.ClosureError, match="T256_T262 re-execution differs"):
        x.reproduce_verifiers(root, tmp_path / "work")


@EXTERNAL
def test_committed_result_is_reproduced(authority: x.chase.Authority, tmp_path: Path) -> None:
    result = x.compute_result(authority, tmp_path)
    assert x.RESULT_PATH.read_text(encoding="utf-8") == x.render(result)
    runs = x.object_row(result["SOURCE_REEXECUTION"])
    assert {k: x.object_row(v)["NORMALIZED_EQUAL"] for k, v in runs.items()} == dict.fromkeys(
        ("T256_T262", "T263_T268", "T269"), True
    )
    origins = [x.object_row(o) for o in x.rows(result["ORIGIN_BINDING"])]
    assert len(origins) == 12 and {o["STATUS"] for o in origins} == {"BYTE_IDENTICAL"}
    assert x.object_row(result["COMMITTED_T270_VERIFIER"])["STATUS"] == "PASS"
    assert result["INCUMBENT_PROFILE_OFFICIAL_MAX_UB"] == x.INCUMBENT
    assert result["FULL_PROFILE_NO_STRICT_GAIN"] == "PASS"
