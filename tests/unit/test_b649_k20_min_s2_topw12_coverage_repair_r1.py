"""Complete profile universe, the twelve W=835..837 certificates, tamper and family replay."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from fractions import Fraction
from time import monotonic
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_topw12_coverage_repair_r1 as x

Start = tuple[x.Chase, x.CapAuthorities, dict[str, object]]
Derived = tuple[dict[str, object], x.Chase]
TOP_BOUNDS = {
    "66666665444331000000": 313_380_116, "66666655544421000000": 313_389_272,
    "66666555555321000000": 313_407_196, "66666555544440000000": 313_416_740,
    "66665555555430000000": 313_443_432, "66666655444440000000": 313_419_672,
    "66666555554430000000": 313_437_596, "66665555555511000000": 313_455_520,
    "66666664444440000000": 313_422_604, "66666655544430000000": 313_422_604,
    "66666555555330000000": 313_440_528, "66665555555520000000": 313_476_764,
}  # fmt: skip
SHADOW_IDS = {
    "66666665444430000000", "66666665444421000000", "66666665444411100000",
    "66666555555510000000", "66666555555420000000", "66666555555411000000",
}  # fmt: skip
FAMILY = 313_476_764
OWNERS = ["66665555555520000000"]
GAP = 212_876
NEXT_COMPETING = 313_455_520
FINAL_LEDGER_COUNT = 4_647
FINAL_LEDGER_SHA256 = "4a6da0e0a2880656b34ee6c853bc116c454e647c73c9584738531d77c14d82e9"
RESULT_SHA256 = "b49eae19b944e3b631933b26bb9aa707e750b14ae36049dd2744d51f6357595b"


@pytest.fixture(scope="module")
def batch() -> dict[str, object]:
    return x.batch_authority()


@pytest.fixture(scope="module")
def universe() -> x.Universe:
    return x.build_universe()


@pytest.fixture(scope="module")
def earlier() -> dict[str, dict[str, object]]:
    return x.earlier_results()


@pytest.fixture(scope="module")
def sealed() -> dict[str, object]:
    return x.object_row(json.loads(x.result_path().read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def start() -> Start:
    return x.start_chase(monotonic() + 900)


@pytest.fixture
def chase(start: Start) -> x.Chase:
    fresh = copy.deepcopy(start[0])
    fresh.deadline = monotonic() + 900
    return fresh


@pytest.fixture(scope="module")
def derived(start: Start) -> Derived:
    fresh = copy.deepcopy(start[0])
    fresh.deadline = monotonic() + 900
    return x.certify_coverage(fresh, start[1], start[2]), fresh


def _certificates(result: dict[str, object]) -> list[dict[str, object]]:
    return [x.object_row(raw) for raw in x.rows(result["TOP_W_CERTIFICATES"])]


def _top_profiles(universe: x.Universe) -> list[x.DegreeProfile]:
    return sorted(universe.band(835, 837), reverse=True)


def test_raw_universe_and_screens(universe: x.Universe, monkeypatch: pytest.MonkeyPatch) -> None:
    assert len(universe.raw) == x.RAW_COUNT == 5_126
    assert len(universe.admissible) == x.ADMISSIBLE_COUNT == 4_844
    assert len(universe.exclusions) == 282
    assert set(universe.excluded_by(x.SCREEN_SHADOW)) == {x.decode_profile(i) for i in SHADOW_IDS}
    census = {p for members in universe.census.values() for p in members}
    assert census == set(universe.admissible) and min(universe.census) == 774
    assert max(universe.census) == 837 and len(universe.census[837]) == 4
    r8_profile = x.decode_profile("66666665444421000000")
    assert x.screen_results(r8_profile)[x.SCREEN_SHADOW] == (7, 84, 83)
    eleven_sixes = (6,) * 11 + (0,) * 9
    assert x.first_failure(x.screen_results(eleven_sixes)) is not None
    assert all(x.integer(row[4]) > x.integer(row[5]) for row in x.exclusion_rows(universe))

    real_eg = x.erdos_gallai_witness

    def loose_eg(degrees: list[int]) -> x.Witness | None:
        witness = real_eg(degrees)
        return None if witness is not None and witness[1] == witness[2] + 1 else witness

    monkeypatch.setattr(x, "erdos_gallai_witness", loose_eg)
    with pytest.raises(AssertionError, match="disagrees with R8"):
        x.build_universe()
    print("MUTATION_KILLED erdos-gallai-off-by-one")
    monkeypatch.undo()

    def no_pair_screen(_profile: x.DegreeProfile) -> x.Witness | None:
        return None

    monkeypatch.setattr(x, "pair_capacity_witness", no_pair_screen)
    with pytest.raises(AssertionError, match="pair-capacity witness disagrees with R4"):
        x.build_universe()
    print("MUTATION_KILLED pair-capacity-screen-disabled")
    monkeypatch.undo()

    raw = x.raw_universe()
    monkeypatch.setattr(x, "raw_universe", lambda: raw[1:])
    with pytest.raises(AssertionError, match="raw histogram count changed"):
        x.build_universe()
    print("MUTATION_KILLED raw-histogram-dropped")
    monkeypatch.undo()

    full = x.nbb.census_by_wedges()
    short = dict(full) | {837: full[837][1:]}
    monkeypatch.setattr(x.nbb, "census_by_wedges", lambda: short)
    with pytest.raises(AssertionError, match="differ from the census enumerator"):
        x.build_universe()
    print("MUTATION_KILLED census-top-profile-dropped")
    monkeypatch.undo()

    monkeypatch.setattr(x, "SCREENS", tuple(reversed(x.SCREENS)))
    with pytest.raises(AssertionError, match="first failing screen disagrees"):
        x.build_universe()
    print("MUTATION_KILLED screen-order-swapped")


def test_earlier_authority(
    universe: x.Universe,
    earlier: dict[str, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = x.earlier_exclusion_authority(universe, earlier)
    shadow = x.object_row(report["SHADOW_ERDOS_GALLAI"])
    assert set(shadow) == SHADOW_IDS
    locators = sorted(x.text(x.object_row(row)["LOCATOR"]) for row in shadow.values())
    assert locators == [
        "R10:PROFILE_BOUNDS[0]", "R5:CLOSED_DANGEROUS_PROFILES[0]",
        "R5:CLOSED_DANGEROUS_PROFILES[1]", "R5:CLOSED_DANGEROUS_PROFILES[2]",
        "R6:TOP_PROFILE_RESOLUTIONS[2]", "R8:ACTIVE_PROFILE",
    ]  # fmt: skip
    ranking = x.ranking_reconciliation(universe, earlier)
    assert ranking["R5_RANKED_COUNT"] == 4_850
    assert set(x.rows(ranking["R5_RANKED_MINUS_ADMISSIBLE"])) == SHADOW_IDS
    history = x.top_history(universe.band(835, 837), earlier)
    assert set(history) == set(TOP_BOUNDS)
    for identity, raw in history.items():
        row = x.object_row(raw)
        assert row["REALIZABILITY"] == "REALIZABLE" and row["USED_FOR_FAMILY_BOUND"] is False
        assert x.integer(row["HISTORICAL_PROFILE_BOUND"]) > TOP_BOUNDS[identity]

    tampered = copy.deepcopy(earlier)
    obstruction = x.object_row(
        x.object_row(x.rows(tampered["R6"]["TOP_PROFILE_RESOLUTIONS"])[2])["OBSTRUCTION"]
    )
    obstruction["RIGHT_HAND_SIDE"] = 60
    with pytest.raises(AssertionError, match="R6 Erdos-Gallai witness differs"):
        x.earlier_exclusion_authority(universe, tampered)
    print("MUTATION_KILLED earlier-witness-tampered")
    tampered = copy.deepcopy(earlier)
    x.object_row(x.rows(tampered["R10"]["PROFILE_BOUNDS"])[0])["REALIZABILITY"] = "UNKNOWN"
    with pytest.raises(AssertionError, match="has no earlier sealed closure"):
        x.earlier_exclusion_authority(universe, tampered)
    print("MUTATION_KILLED earlier-closure-missing")
    tampered = copy.deepcopy(earlier)
    x.object_row(x.rows(tampered["R9"]["PROFILE_BOUNDS"])[1])["REALIZABILITY"] = "UNKNOWN"
    with pytest.raises(AssertionError, match="not exactly the twelve"):
        x.top_history(universe.band(835, 837), tampered)
    print("MUTATION_KILLED top-history-row-missing")
    tampered = copy.deepcopy(earlier)
    x.object_row(tampered["R5"]["PROFILE_COUNTS"])["PAIR_CAPACITY_COMPATIBLE_PROFILES"] = 4_851
    with pytest.raises(AssertionError, match="sealed R5 profile counts disagree"):
        x.ranking_reconciliation(universe, tampered)
    print("MUTATION_KILLED r5-counts-tampered")
    monkeypatch.setitem(x.EARLIER_RESULTS, "R8", (x.EARLIER_RESULTS["R8"][0], "0" * 64))
    with pytest.raises(AssertionError, match="sealed fingerprint changed"):
        x.earlier_results()
    print("MUTATION_KILLED earlier-digest-pin")
    monkeypatch.setattr(x, "BATCH_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="sealed fingerprint changed"):
        x.batch_authority()
    print("MUTATION_KILLED batch-digest-pin")


def test_top_certificates_all_t(
    universe: x.Universe, batch: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    predecessor = x.predecessor_top_bounds(batch)
    assert predecessor == TOP_BOUNDS
    top = _top_profiles(universe)
    assert len(top) == 12
    certificates = [x.top_certificate(p, predecessor[x.profile_id(p)]) for p in top]
    for certificate in certificates:
        cap = x.integer(certificate["TRIANGLE_CAP"])
        terms = [list(cast("list[int]", term)) for term in x.rows(certificate["ALL_T_TERMS"])]
        assert [term[0] for term in terms] == list(range(22, cap + 1))
        for t, bound, k4, contained, s4, s3 in terms:
            exact = Fraction(x.K20_S1 - x.K20_S2 + s3) - Fraction(4 * s4, 7)
            assert bound == -((-exact.numerator) // exact.denominator)
            assert s4 == max(
                x.integer(certificate["S4_BASE"]), 448 * contained + 679 * (k4 - contained)
            )
            assert contained == min(k4, x.integer(certificate["A_MAX"])) and t <= cap
        assert max(term[1] for term in terms) == certificate["ALL_T_MAX_BOUND"]
        assert certificate["ALL_T_MAX_BOUND"] == TOP_BOUNDS[x.text(certificate["PROFILE_ID"])]
        assert cap == min(
            x.integer(certificate["NB_TRIANGLE_CAP"]), x.integer(certificate["R18_TRIANGLE_CAP"])
        )
    assert max(TOP_BOUNDS.values()) == FAMILY == x.PROVISIONAL_TOP_MAX
    owner = x.decode_profile(OWNERS[0])
    bound = TOP_BOUNDS[OWNERS[0]]

    monkeypatch.setattr(x.w8, "ceil_fraction", x.w8.floor_fraction)
    with pytest.raises(AssertionError, match="integer rounding disagrees"):
        x.top_certificate(owner, bound)
    print("MUTATION_KILLED route-b-ceil-to-floor")
    monkeypatch.undo()
    real_nb = x.nbb.exact_nb_cap

    def loose_nb(profile: x.DegreeProfile) -> tuple[int, int, int]:
        wedges, floor, cap = real_nb(profile)
        return wedges, floor, cap + 1

    monkeypatch.setattr(x.nbb, "exact_nb_cap", loose_nb)
    with pytest.raises(AssertionError, match="NB cap disagrees"):
        x.top_certificate(owner, bound)
    print("MUTATION_KILLED nb-cap-independent-derivation")
    monkeypatch.undo()

    def weakest(nb_cap: int, class_cap: int, catalog_cap: int | None = None) -> int:
        return max(nb_cap, class_cap)

    monkeypatch.setattr(x.nb, "combined_triangle_cap", weakest)
    with pytest.raises(AssertionError, match="not the strongest verified cap"):
        x.top_certificate(owner, bound)
    print("MUTATION_KILLED cap-not-minimum")
    monkeypatch.undo()
    with pytest.raises(AssertionError, match="closed-form cross-check"):
        x.top_certificate(owner, bound - 4)
    print("MUTATION_KILLED predecessor-cross-check")
    with pytest.raises(AssertionError, match=r"outside the W=835\.\.837 band"):
        x.top_certificate(x.decode_profile(x.LEDGER_DEFINED_OWNER_IDS[0]), bound)
    print("MUTATION_KILLED top-band-gate")
    with pytest.raises(AssertionError, match="fails a necessary condition"):
        x.top_certificate(x.decode_profile("66666555555411000000"), bound)
    print("MUTATION_KILLED excluded-profile-certified")
    stored = copy.deepcopy(certificates[0])
    x.audit_top_certificate(stored, predecessor)
    terms = cast("list[list[int]]", stored["ALL_T_TERMS"])
    terms[-1][1] -= 1
    with pytest.raises(AssertionError, match="ALL_T_TERMS"):
        x.audit_top_certificate(stored, predecessor)
    print("MUTATION_KILLED all-t-term-tampered")


def test_partition_set_difference(
    chase: x.Chase, universe: x.Universe, monkeypatch: pytest.MonkeyPatch
) -> None:
    parts = x.partition(chase, universe)
    assert {name: len(members) for name, members in parts.items()} == {
        x.PART_LEDGER: 1_795, x.PART_W809: 133, x.PART_W808: 147, x.PART_BATCH: 2_560,
        x.PART_FRONTIER: 197, x.PART_TOP: 12, x.PART_EXCLUDED: 282,
    }  # fmt: skip
    assert {x.profile_id(p) for p in parts[x.PART_TOP]} == set(TOP_BOUNDS)
    order = x.top_ids_in_batch_order(universe)
    assert hashlib.sha256(json.dumps(order).encode()).hexdigest() == x.TOP_IDS_SHA256
    union = set[x.DegreeProfile]().union(*parts.values())
    assert sum(map(len, parts.values())) == len(union) == 5_126

    dropped = copy.deepcopy(chase)
    member = next(p for p in parts[x.PART_BATCH] if x.overlap_wedge_count(p) == 807)
    del dropped.bounds[member], dropped.catalog[member]
    with pytest.raises(AssertionError, match="is not the whole admissible band"):
        x.partition(dropped, universe)
    print("MUTATION_KILLED ledger-row-missing")
    smuggled = copy.deepcopy(chase)
    top = x.decode_profile(OWNERS[0])
    smuggled.bounds[top] = 0
    smuggled.catalog[top] = x.Certificate(top, 0, x.BATCH_RESULT, "X", "X", 0, 0, 0, "X")
    with pytest.raises(AssertionError, match="has no unique source part"):
        x.partition(smuggled, universe)
    print("MUTATION_KILLED top-profile-silently-ledgered")
    lowered = copy.deepcopy(chase)
    lowered.cursor_bound = x.CURSOR_BOUND - 1
    with pytest.raises(AssertionError, match="cursor is not in its own frontier"):
        x.partition(lowered, universe)
    print("MUTATION_KILLED cursor-coarse-dominance")
    monkeypatch.setitem(x.OPEN_PARTS, x.PART_TOP, (11, 835, 837))
    with pytest.raises(AssertionError, match="is not the whole admissible band"):
        x.partition(chase, universe)
    print("MUTATION_KILLED top-count-pinned")


def test_install_and_family(
    chase: x.Chase, start: Start, derived: Derived, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, after = derived
    assert result["FINAL_COMPLETE_FAMILY_UPPER_BOUND"] == FAMILY
    assert result["FINAL_BOUND_OWNER_IDS"] == OWNERS
    assert result["REMAINING_GAP"] == GAP == FAMILY - x.INCUMBENT
    assert result["NEXT_COMPETING_BOUND"] == NEXT_COMPETING
    assert result["LEDGER_DEFINED_MAX"] == 313_404_784 < FAMILY
    assert result["LEDGER_DEFINED_MAX_IS_COMPLETE_FAMILY_MAX"] is False
    assert result["PREVIOUS_REPORTED_BOUND_REMAINS_VALID"] is True
    assert (result["COVERED_PROFILE_COUNT"], result["UNCOVERED_PROFILE_COUNT"]) == (4_844, 0)
    assert result["PROFILE_COVERAGE_STATUS"] == "COMPLETE"
    assert result["MISSING_TOP_W_PROFILE_COUNT"] == result["MISSING_TOP_W_CERTIFIED_COUNT"] == 12
    assert result["MISSING_TOP_W_MAX"] == FAMILY
    assert result["FINAL_LEDGER_COUNT"] == len(after.bounds) == FINAL_LEDGER_COUNT
    assert result["FINAL_LEDGER_SHA256"] == FINAL_LEDGER_SHA256
    assert result["PREVIOUS_LEDGER_ROWS_SHA256"] == x.LEDGER_SHA256
    assert all(after.bounds[p] == b for p, b in start[0].bounds.items())
    assert result["WITNESS_SOUNDNESS_STATUS"] == "PASS"
    assert result["SOLVER_CALLS"] == result["OUTCOME_ENUMERATIONS"] == 0
    assert x.nb.small_graph_soundness(5)["STATUS"] == "PASS"

    certificates = _certificates(result)
    partial = copy.deepcopy(chase)
    x.install_top(partial, certificates[1:])
    universe = x.build_universe()
    parts = x.partition(chase, universe)
    with pytest.raises(AssertionError, match="previous rows plus the twelve"):
        x.coverage_after(partial, universe, parts)
    print("MUTATION_KILLED top-profile-not-installed")
    drifted = copy.deepcopy(chase)
    some = next(iter(drifted.bounds))
    drifted.bounds[some] -= 1
    with pytest.raises(AssertionError, match="no longer reproduce the sealed digest"):
        x.install_top(drifted, certificates)
    print("MUTATION_KILLED previous-ledger-row-drift")
    real_install = x.install_top

    def install_lower(target: x.Chase, rows: list[dict[str, object]]) -> None:
        real_install(target, rows)
        target.bounds[x.decode_profile(OWNERS[0])] = x.LEDGER_DEFINED_MAX
        target.catalog[x.decode_profile(OWNERS[0])] = x.Certificate(
            x.decode_profile(OWNERS[0]), x.LEDGER_DEFINED_MAX, "X", "X", "X", 0, 0, 0, "X"
        )

    monkeypatch.setattr(x, "install_top", install_lower)
    with pytest.raises(AssertionError, match="family recompute disagreement"):
        x.certify_coverage(copy.deepcopy(chase), start[1], start[2])
    print("MUTATION_KILLED owner-bound-lowered-on-install")


def test_sealed_result_and_tamper(
    derived: Derived, sealed: dict[str, object], batch: dict[str, object]
) -> None:
    assert x.nb.same_result(sealed, derived[0])
    assert hashlib.sha256(x.result_path().read_bytes()).hexdigest() == RESULT_SHA256
    assert x.audit_sealed_result(sealed, batch)["STATUS"] == "PASS"

    def rejects(mutate: Callable[[dict[str, object]], None], match: str, label: str) -> None:
        tampered = copy.deepcopy(sealed)
        mutate(tampered)
        with pytest.raises(AssertionError, match=match):
            x.audit_sealed_result(tampered, batch)
        print(f"MUTATION_KILLED {label}")

    def lower_bound(result: dict[str, object]) -> None:
        _certificates_live(result)[0]["ALL_T_MAX_BOUND"] = 1

    def drop_top(result: dict[str, object]) -> None:
        cast("list[object]", result["TOP_W_CERTIFICATES"]).pop()

    def duplicate_top(result: dict[str, object]) -> None:
        rows = cast("list[object]", result["TOP_W_CERTIFICATES"])
        rows.append(copy.deepcopy(rows[0]))

    def drop_exclusion(result: dict[str, object]) -> None:
        cast("list[object]", result["EXCLUSIONS"]).pop()

    def swap_screen(result: dict[str, object]) -> None:
        cast("list[list[object]]", result["EXCLUSIONS"])[0][2] = x.SCREEN_RESIDUAL

    def ledger_max_as_family(result: dict[str, object]) -> None:
        result["FINAL_COMPLETE_FAMILY_UPPER_BOUND"] = x.LEDGER_DEFINED_MAX

    def hide_uncovered(result: dict[str, object]) -> None:
        result["UNCOVERED_PROFILE_COUNT"] = 1

    def shrink_part(result: dict[str, object]) -> None:
        part = x.object_row(x.object_row(result["PROFILE_PARTITION_BEFORE_REPAIR"])[x.PART_TOP])
        part["COUNT"] = 11

    rejects(lower_bound, "ALL_T_MAX_BOUND", "sealed-top-bound-lowered")
    rejects(drop_top, "not exactly the twelve", "sealed-top-row-dropped")
    rejects(duplicate_top, "not exactly the twelve", "sealed-top-row-duplicated")
    rejects(drop_exclusion, "exclusion rows differ", "sealed-exclusion-dropped")
    rejects(swap_screen, "exclusion rows differ", "sealed-exclusion-screen-swapped")
    rejects(ledger_max_as_family, "family or coverage totals", "sealed-ledger-max-published")
    rejects(hide_uncovered, "family or coverage totals", "sealed-uncovered-count")
    rejects(shrink_part, "partition part", "sealed-partition-count")


def _certificates_live(result: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", result["TOP_W_CERTIFICATES"])
