"""Focused checks for profile 66655555555411110000. Defects hit the shipped functions."""

from __future__ import annotations

import copy
import json
import random
from collections.abc import Mapping
from fractions import Fraction
from itertools import combinations
from math import ceil
from typing import cast

import pytest

from lottolab.research import b649_min_s2_owner_6665555555541111_exact_cert_r1 as cert

FIVE_ZERO_PROFILE = "66655555555421100000"


@pytest.fixture(scope="module")
def result() -> cert.Document:
    return cert.compute_result()


def _inputs(pid: str = cert.TARGET_PROFILE) -> dict[str, int]:
    facts = cert.profile_facts(pid)
    degrees = cert.profile_degrees(pid)
    return {
        "allowance": sum(value * (6 + value - 2) for value in degrees) // 3,
        "choose3": facts["SUM_CHOOSE3"],
        "degree_max": max(6 + value for value in degrees),
        "global_floor": cert.GLOBAL_S4_FLOOR,
        "wedges": facts["W"],
    }


def _ceiling(base: int, floor: int) -> int:
    rational = Fraction(base) - Fraction(4 * floor, 7)
    integral = base - (4 * floor) // 7
    assert ceil(rational) == integral
    assert 0 <= integral - rational < 1
    return integral


def test_profile_facts_and_unpinned_authorities(result: cert.Document) -> None:
    facts = cert.require_target(cert.TARGET_PROFILE)
    assert facts == result["PROFILE_FACTS"]
    assert facts["SUM_D"] == 66
    assert facts["E"] == 93
    assert facts["W"] == 827
    assert facts["SUM_CHOOSE3"] == 2320
    assert facts["GOODMAN"] == 293
    assert facts["CORE_VERTICES"] == 16
    assert facts["ZERO_VERTICES"] == 4
    assert result["TARGET_PROFILE"] == cert.TARGET_PROFILE
    assert result["SEALED_SCALAR_BOUND"] == cert.SEALED_SCALAR_BOUND == 313_391_740
    assert result["CURRENT_T_AUTHORITY"] == "NOT_PINNED_IN_SEALED_FAMILY_RESULT"
    assert result["CURRENT_S5_AUTHORITY"] == "NOT_PINNED"
    assert result["NEW_PROVEN_S5"] == "NOT_USED"
    assert "NOT_RERUN" in str(result["PREVIOUS_T267_DISPOSITION"])
    pins = cast(dict[str, object], result["SOURCE_PINS"])
    off_base = cast(dict[str, str], pins["OFF_BASE_1300AE27"])
    assert off_base["STATUS"] == "NOT_PINNED"
    assert result["RECONSTRUCTED_ROUTE_B_EQUALS_SEALED_SCALAR"] is False
    assert result["LEGAL_ATTAINMENT"] == "UNKNOWN"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["HEAVY_SOLVER_STARTED"] == "NO"
    assert result["REMOTE_WRITE"] == "NO"
    gates = cast(dict[str, str], result["G01_TO_G18"])
    for gate in (f"G{index:02d}" for index in range(1, 16)):
        assert gates[gate] == "PASS"
    assert gates["G16"] == gates["G17"] == gates["G18"] == "NOT_VERIFIED"


def test_hilo_choices_cover_degree_one_shadows(result: cert.Document) -> None:
    degrees = cert.profile_degrees(cert.TARGET_PROFILE)
    high, low = cert.hilo_shores(degrees)
    assert (len(high), len(low)) == (12, 8)
    degree_six = cert.hilo_choices(6, high, low)
    assert degree_six == tuple((block, 0) for block in range(1, 5))
    degree_one = cert.hilo_choices(1, low, high)
    assert {block for block, _pair in degree_one} == {0, 1, 2}
    assert all(0 <= pair <= 5 and block + pair <= 12 for block, pair in degree_one)
    degree_zero = cert.hilo_choices(0, low, high)
    assert all(block == 0 and 0 <= pair <= 6 for block, pair in degree_zero)
    offset = len(low) - 1 - 7
    assert cert.class_scores_multiset(1, 4, degree_one, offset) == cert.class_scores_vertex_dp(
        4, degree_one, offset
    )
    relaxation = cert.hilo_relaxation(cert.TARGET_PROFILE)
    cells = cast(list[list[int]], relaxation["ALL_CELLS"])
    cap = max(row[4] for row in cells)
    assert cap == relaxation["CAP"] == result["NEW_PROVEN_T_CAP"]
    assert cap <= 264
    assert relaxation["REALIZABILITY"] == "NOT_ASSERTED"
    assert relaxation["P_LOWER_BOUND"] == 0


def test_every_t_term_matches_both_roundings(result: cert.Document) -> None:
    facts = cert.require_target(cert.TARGET_PROFILE)
    relaxation_cap = cast(int, result["NEW_PROVEN_T_CAP"])
    terms = cert.full_envelope(cert.TARGET_PROFILE, relaxation_cap)
    bound = cert.require_complete_envelope(terms, relaxation_cap)
    assert bound == result["NEW_FULL_PROFILE_BOUND"]
    assert bound <= cert.SEALED_SCALAR_BOUND - 1
    recorded = cast(list[dict[str, int]], result["T_TERMS"])
    assert [row["T"] for row in recorded] == list(range(22, relaxation_cap + 1))
    inputs = _inputs()
    for term, row in zip(terms, recorded, strict=True):
        again = cert.envelope_term(term[0], **inputs)
        assert again == term
        s3, open_wedges = cert.s3_pair(facts["W"], term[0])
        k4 = cert.k4_floor(facts["SUM_CHOOSE3"] - (inputs["degree_max"] - 2) * open_wedges)
        _contained, floor = cert.s4_lower(k4, inputs["allowance"], cert.GLOBAL_S4_FLOOR)
        assert _ceiling(cert.S1 - cert.S2 + s3, floor) == term[1] == row["BOUND"]
        assert (term[0], term[1], term[2], term[3], term[4], term[5], term[6]) == (
            row["T"],
            row["BOUND"],
            row["K4_FLOOR"],
            row["CONTAINED_K4"],
            row["S4"],
            row["S3"],
            row["OPEN_WEDGES"],
        )
    wedge_cap = facts["W"] // 3
    wedge = cert.full_envelope(cert.TARGET_PROFILE, wedge_cap)
    wedge_bound = cert.require_complete_envelope(wedge, wedge_cap)
    assert wedge_bound == result["UNRESTRICTED_WEDGE_ROUTE_B_BOUND"]
    assert wedge_bound > cert.SEALED_SCALAR_BOUND
    assert result["UNRESTRICTED_WEDGE_ROUTE_B_ADOPTED"] is False
    assert next(term[1] for term in wedge if term[0] == 265) == cert.SEALED_SCALAR_BOUND
    assert next(term[1] for term in wedge if term[0] == 267) > cert.SEALED_SCALAR_BOUND


def test_s4_plus_one_does_not_beat_the_sealed_scalar() -> None:
    inputs = _inputs()
    term = cert.envelope_term(265, **inputs)
    base = cert.S1 - cert.S2 + term[5]
    assert _ceiling(base, term[4] + 1) == cert.SEALED_SCALAR_BOUND
    assert _ceiling(base, term[4] + 2) == cert.SEALED_SCALAR_BOUND - 1
    assert cert.minimum_s4_for_term(265, cert.SEALED_SCALAR_BOUND - 1) == term[4] + 2
    pinned = dict(inputs)
    pinned["global_floor"] = term[4]
    lowered = cert.envelope_term(260, **pinned)
    pinned["global_floor"] = lowered[4] + 7
    assert cert.envelope_term(260, **pinned)[1] == lowered[1] - 4


def test_k4_floor_and_s4_direction() -> None:
    assert cert.k4_floor(-8) == cert.k4_floor(0) == 0
    assert cert.k4_floor(1) == 1
    assert cert.k4_floor(4) == 1
    assert cert.k4_floor(5) == 2
    _contained, low = cert.s4_lower(10, 197, 112)
    _contained, high = cert.s4_lower(11, 197, 112)
    assert high > low


def test_two_shore_identity_on_finite_graphs() -> None:
    rng = random.Random(260)
    empty: set[tuple[int, int]] = set()
    samples: list[set[tuple[int, int]]] = [empty, {(0, 1), (1, 2), (0, 2), (2, 3)}]
    samples.extend(
        {pair for pair in combinations(range(20), 2) if rng.random() < 0.45} for _trial in range(4)
    )
    for edges in samples:
        triangles, objective, remainder = cert.shore_split(edges, set(range(12)))
        assert remainder >= 0
        assert triangles == objective - remainder


def test_family_replay_changes_only_the_target(result: cert.Document) -> None:
    base = cert.load_base()
    rows = cert.ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = cert.ledger(cert.obj(base["CURSOR"])["COARSE_BOUND_PROJECTION"])
    assert len(rows) == 4647 and len(cursor) == 197
    assert rows[cert.TARGET_PROFILE] == rows[cert.OTHER_OWNER] == cert.SEALED_SCALAR_BOUND
    new_bound = cast(int, result["NEW_FULL_PROFILE_BOUND"])
    fingerprint = cert.sha(cert.render(dict(sorted(cursor.items()))))
    updated, state = cert.replay_family(
        rows,
        cursor,
        {cert.TARGET_PROFILE: new_bound},
        cursor_fingerprint=fingerprint,
    )
    changed = sorted(profile for profile, bound in rows.items() if updated[profile] != bound)
    assert changed == [cert.TARGET_PROFILE]
    assert updated[cert.OTHER_OWNER] == cert.SEALED_SCALAR_BOUND
    assert state["FAMILY_BOUND"] == cert.SEALED_SCALAR_BOUND
    assert state["OWNER_IDS"] == [cert.OTHER_OWNER]
    before = cast(Mapping[str, object], result["FAMILY_BEFORE"])
    after = cast(Mapping[str, object], result["FAMILY_AFTER_SINGLE_ROW"])
    assert before["FAMILY_BOUND"] == after["FAMILY_BOUND"] == cert.SEALED_SCALAR_BOUND
    assert before["STILL_OPEN_PROFILE_COUNT"] == after["STILL_OPEN_PROFILE_COUNT"]
    assert before["CURSOR_MAXIMUM"] == after["CURSOR_MAXIMUM"]
    assert before["OWNER_IDS"] == [cert.OTHER_OWNER, cert.TARGET_PROFILE]
    assert after["OWNER_IDS"] == [cert.OTHER_OWNER]
    assert result["FAMILY_DELTA"] == 0
    assert result["OTHER_ROWS_UNCHANGED"] == 4646
    assert result["CURSOR_PRESERVED"] is True
    assert result["CURSOR_PROFILES"] == 197
    assert result["RESOLVED_ROWS"] == 4647


def test_wrong_profile_and_five_zero_mix_are_rejected() -> None:
    other = cert.profile_facts(cert.OTHER_OWNER)
    mixed = cert.profile_facts(FIVE_ZERO_PROFILE)
    assert other["ZERO_VERTICES"] == mixed["ZERO_VERTICES"] == 5
    assert other["SUM_CHOOSE3"] == 2318
    assert mixed["SUM_CHOOSE3"] != 2320
    with pytest.raises(ValueError, match="wrong profile"):
        cert.require_target(cert.OTHER_OWNER)
    with pytest.raises(ValueError, match="wrong profile"):
        cert.require_target(FIVE_ZERO_PROFILE)
    with pytest.raises(ValueError, match="wrong profile"):
        cert.full_envelope(FIVE_ZERO_PROFILE, 260)
    with pytest.raises(ValueError, match="wrong profile"):
        cert.hilo_relaxation(cert.OTHER_OWNER)


def test_choose3_swap_sign_and_s5_are_rejected() -> None:
    with pytest.raises(ValueError, match="2318/2320 constant swap"):
        cert.full_envelope(cert.TARGET_PROFILE, 260, choose3=cert.OTHER_OWNER_CHOOSE3)
    inputs = _inputs()
    with pytest.raises(ValueError, match="invalid S4/S5 sign"):
        cert.envelope_term(40, **inputs, s4_sign=1)
    with pytest.raises(ValueError, match="unsupported S5 authority"):
        cert.envelope_term(40, **inputs, s5_upper=0)


def test_incomplete_and_non_monotone_envelopes_are_rejected(result: cert.Document) -> None:
    cap = cast(int, result["NEW_PROVEN_T_CAP"])
    terms = cert.full_envelope(cert.TARGET_PROFILE, cap)
    with pytest.raises(ValueError, match="incomplete T envelope"):
        cert.require_complete_envelope(terms[:-1], cap)
    gap = list(terms)
    gap[0] = (21, *gap[0][1:])
    with pytest.raises(ValueError, match="missing T term"):
        cert.require_complete_envelope(gap, cap)
    swapped = list(terms)
    left, right = swapped[0], swapped[1]
    swapped[0] = (left[0], right[1], *left[2:])
    swapped[1] = (right[0], left[1], *right[2:])
    with pytest.raises(ValueError, match="envelope not increasing"):
        cert.require_complete_envelope(swapped, cap)


def test_equality_at_t265_is_not_a_strict_gain(monkeypatch: pytest.MonkeyPatch) -> None:
    def equality_cap(pid: str) -> cert.Document:
        cert.require_target(pid)
        return {"CAP": 265}

    monkeypatch.setattr(cert, "hilo_relaxation", equality_cap)
    with pytest.raises(ValueError, match="no strict profile gain"):
        cert.compute_result()


def test_false_family_gain_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original_replay = cert.replay_family

    def proved_cap(pid: str) -> cert.Document:
        cert.require_target(pid)
        return {"CAP": 260}

    def moved(
        rows: Mapping[str, int],
        cursor: Mapping[str, int],
        replacement: Mapping[str, int],
        *,
        cursor_fingerprint: str,
    ) -> tuple[dict[str, int], cert.Document]:
        updated, state = original_replay(
            rows,
            cursor,
            replacement,
            cursor_fingerprint=cursor_fingerprint,
        )
        state["FAMILY_BOUND"] = replacement[cert.TARGET_PROFILE]
        return updated, state

    monkeypatch.setattr(cert, "hilo_relaxation", proved_cap)
    monkeypatch.setattr(cert, "replay_family", moved)
    with pytest.raises(ValueError, match="false family gain"):
        cert.compute_result()


def test_source_hash_and_cursor_mutation_are_rejected() -> None:
    with pytest.raises(ValueError, match="source hash mismatch"):
        cert.blob(
            cert.BASE_HEAD,
            "src/lottolab/research/b649_k20_min_s2_higher_order_closure_r2.py",
            "0" * 64,
        )
    base = cert.load_base()
    rows = cert.ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = cert.ledger(cert.obj(base["CURSOR"])["COARSE_BOUND_PROJECTION"])
    fingerprint = cert.sha(cert.render(dict(sorted(cursor.items()))))
    mutated = dict(cursor)
    key = next(iter(mutated))
    mutated[key] += 1
    with pytest.raises(ValueError, match="cursor mutation"):
        cert.replay_family(
            rows,
            mutated,
            {cert.TARGET_PROFILE: cert.SEALED_SCALAR_BOUND - 1},
            cursor_fingerprint=fingerprint,
        )
    with pytest.raises(ValueError, match="replacement scope"):
        cert.replay_family(
            rows,
            cursor,
            {cert.TARGET_PROFILE: 1, cert.OTHER_OWNER: cert.SEALED_SCALAR_BOUND},
            cursor_fingerprint=fingerprint,
        )
    forged = dict(rows)
    forged[cert.OTHER_OWNER] = cert.SEALED_SCALAR_BOUND - 1
    with pytest.raises(ValueError, match="other owner changed"):
        cert.replay_family(
            forged,
            cursor,
            {cert.TARGET_PROFILE: cert.SEALED_SCALAR_BOUND - 1},
            cursor_fingerprint=fingerprint,
        )


def test_working_evaluator_bytes_are_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cert.working_bytes

    def altered(path: str) -> bytes:
        payload = original(path)
        return payload + b"\n" if path.endswith("r2.py") else payload

    monkeypatch.setattr(cert, "working_bytes", altered)
    with pytest.raises(ValueError, match="evaluator pin mismatch"):
        cert.load_base()


def test_result_bytes_reject_a_forged_improvement(result: cert.Document) -> None:
    payload = (cert.ROOT / cert.RESULT).read_bytes()
    assert payload == cert.render(result)
    cert.verify_result(json.loads(payload))
    forged = copy.deepcopy(result)
    forged["FAMILY_DELTA"] = -1
    forged["NEW_FULL_PROFILE_BOUND"] = cert.SEALED_SCALAR_BOUND
    with pytest.raises(ValueError, match="deterministic result mismatch"):
        cert.verify_result(forged)
