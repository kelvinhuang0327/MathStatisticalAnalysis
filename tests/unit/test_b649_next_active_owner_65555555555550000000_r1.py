"""Focused guards for the T<=255 cap of 65555555555550000000 on the frozen seven-row ledger."""

from __future__ import annotations

import math
import random
from dataclasses import replace
from itertools import combinations
from unittest.mock import patch

import pytest

from lottolab.research import b649_next_active_owner_65555555555550000000_r1 as c

Six = tuple[dict[str, object], dict[str, c.Row]]


@pytest.fixture(scope="module")
def six_row() -> Six:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("ledger replay executed a proof/search entrypoint")

    with (
        patch.object(c.split, "degree_configurations", forbidden),
        patch.object(c.split, "split_certificate", forbidden),
        patch.object(c.chase, "chase", forbidden),
        patch.object(c.chase, "refine", forbidden),
        patch.object(c.t256.three, "core_zero_theorem", forbidden),
        patch.object(c.t256, "compute_result", forbidden),
    ):
        return c.t256.six_row_authority()


@pytest.fixture(scope="module")
def result(six_row: Six) -> dict[str, object]:
    # Reuse only the genuine, digest-validated six-row replay above.
    with patch.object(c.t256, "six_row_authority", return_value=six_row):
        return c.compute_result()


def test_committed_result_is_reproduced_exactly(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.two.render(result)
    assert result["EXPECTED_VALUES_MATCH"] is True
    assert result["EXPECTED_VALUE_DIFFERENCES"] == {}


def test_source_row_and_headline(result: dict[str, object]) -> None:
    source = c.object_row(result["SOURCE_ROW"])
    assert (source["SOURCE_T_CAP"], source["SOURCE_S4_BASE"]) == (264, 1680)
    assert source["SOURCE_ROW_BOUND"] == result["OLD_BOUND"] == 313396120
    assert source["SOURCE"] == c.SOURCE_ROW
    context = c.object_row(result["FROZEN_LEDGER_CONTEXT"])
    assert context["EXISTING_CERTIFICATE_IN_FROZEN_AUTHORITY"] == "NONE"
    assert context["ROWS_ABOVE_TARGET_COUNT"] == 7
    assert (result["PROVED_T_CAP"], result["NEW_ADMISSIBLE_BOUND"]) == (255, 313315656)
    assert result["STRICT_OWNER_BOUND_DELTA"] == 80464
    assert result["NEW_BOUND_VS_CURSOR"] == 313394584 - 313315656
    assert result["PROOF_SCOPE"] == "FULL_PROFILE"
    assert result["FAMILY_BOUND_GAIN_CLAIMED"] == 0
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


def test_theorem_premises_and_cap() -> None:
    theorem = c.theorem()
    assert theorem["STATUS"] == "PROVEN"
    assert theorem["TRIANGLE_CAP"] == theorem["SEPARABLE_MAXIMUM"] == theorem["CONSTANT"] == 255
    assert (theorem["DEGREE_SUM"], theorem["DEGREE_SQUARE_SUM"]) == (66, 336)
    assert (theorem["CORE_COUNT"], theorem["ZERO_COUNT"]) == (13, 7)
    assert (theorem["G_EDGES"], theorem["H_EDGES"], theorem["WEDGES"]) == (93, 97, 831)
    assert theorem["PHI_INCLUSION_EXCLUSION"] == theorem["PHI_GOODMAN"] == 297
    assert theorem["TRIVIAL_T_CAPS"] == {"GOODMAN_T_H_NONNEGATIVE": 297, "WEDGE_IDENTITY": 277}
    assert theorem["SIGMA_RANGES"] == {"6": [0], "5": [0, 1]}
    assert theorem["ZETA_RANGE"] == list(range(7))
    assert (theorem["R_COEFFICIENT"], theorem["CHAIN_COEFFICIENT_R"]) == (-8, -2)
    assert theorem["EQUALITY_CHARACTERIZATION"] == "T=255 IFF r=0"
    assert theorem["IDENTITY_POINTS_CHECKED"] == 1 + 2 * 20


# Missing or widened premises.
@pytest.mark.parametrize(
    ("degree", "values"),
    [(5, range(3)), (6, range(2))],
)
def test_widened_core_range_breaks_the_chain(degree: int, values: range) -> None:
    sigma, zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=r"sum sigma\*h = 2r"):
        c.certify_cap({**sigma, degree: values}, zeta)


def test_widened_zero_range_breaks_the_chain() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=r"zeta\^2 <= 6 zeta"):
        c.certify_cap(sigma, range(8))


def test_narrowed_zero_range_changes_the_equality_set() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match="equality set changed"):
        c.certify_cap(sigma, range(6))


def test_negative_coordinate_rejected() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match="unexpected range shape"):
        c.certify_cap(sigma, range(-1, 7))


def test_separable_route_slack_boundary() -> None:
    # sigma(sigma+c-5) <= 0 on {0,1} exactly when c <= 4; the e44 identity pins c = 2.
    with patch.object(c, "CORE_TERM_CONSTANT", 4):
        assert c.certify_cap(*c.legal_ranges())["SEPARABLE_MAXIMUM"] == 255
    with (
        patch.object(c, "CORE_TERM_CONSTANT", 5),
        pytest.raises(AssertionError, match="separable maximum exceeds 255"),
    ):
        c.certify_cap(*c.legal_ranges())


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("PROVED_CAP", 254, "premises"),
        ("PROVED_CAP", 256, "premises"),
        ("GOODMAN_CONSTANT", 298, "premises"),
        ("WEDGE_TRIANGLE_LIMIT", 278, "premises"),
        ("TICKET_CAPACITY", 7, "premises"),
        ("TARGET_PROFILE", "66555555555540000000", "premises"),
        ("CORE_TERM_CONSTANT", 3, "e44 objective"),
        ("ZERO_TERM_CONSTANT", 5, "e44 objective"),
    ],
)
def test_tampered_constant_rejected(name: str, value: object, message: str) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match=message):
        c.theorem()


def test_dropping_p_breaks_the_complement_identity() -> None:
    rng = random.Random(20261013)
    core, zero = list(range(13)), list(range(13, 20))
    positive = 0
    for density in (0.3, 0.5, 0.7):
        for _ in range(4):
            g = {e for e in combinations(range(20), 2) if rng.random() < density}
            seen = c.t256.complement_split(core, zero, g)
            sigma, h = c.rows(seen["SIGMA"]), c.rows(seen["H_CORE"])
            zeta, a = c.rows(seen["ZETA"]), c.rows(seen["A_ZERO"])
            bare = (
                7 * c.integer(seen["M_EDGES"])
                + 13 * c.integer(seen["MZ_EDGES"])
                - sum(c.integer(s) * c.integer(v) for s, v in zip(sigma, h, strict=True))
                - sum(c.integer(s) * c.integer(v) for s, v in zip(zeta, a, strict=True))
            )
            assert seen["T_H"] == bare + c.integer(seen["P"])
            positive += c.integer(seen["P"]) > 0
    assert positive > 0  # P is exact, not decorative: without it the identity fails


# Wrong cap and attainment.
def test_witness_attains_255_by_direct_count() -> None:
    triples, pairs = c.witness()
    g = {c.edge(x, y) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    assert c.t256.three.triangles(range(20), g) == 255
    seen = c.realization_check(triples, pairs)
    assert (seen["TRIANGLES"], seen["R"], seen["P"]) == (255, 0, 0)
    with patch.object(c, "PROVED_CAP", 254), pytest.raises(AssertionError, match="T255 chain"):
        c.realization_check(triples, pairs)


def test_recorded_realization_obeys_the_chain(result: dict[str, object]) -> None:
    seen = c.object_row(result["RECORDED_ROW_REALIZATION"])
    assert seen["PROFILE_ID"] == c.TARGET_PROFILE
    t, r, p = (c.integer(seen[k]) for k in ("TRIANGLES", "R", "P"))
    assert (t, r, p, seen["T_H"]) == (193, 10, 2, 104)
    assert t <= 255 - 2 * r - p


def test_realization_of_another_profile_rejected() -> None:
    with pytest.raises(AssertionError, match="wrong profile"):
        c.realization_check(*c.t256.three.witness())


def random_structure(rng: random.Random) -> tuple[list[c.Support], list[c.Support]] | None:
    """Any legal structure: hub matching, 16 core triples, leave matching, Z = K7 - MZ."""
    fives = list(range(1, 13))
    rng.shuffle(fives)
    matching = [c.edge(fives[2 * i], fives[2 * i + 1]) for i in range(6)]
    used, need = set(matching), dict.fromkeys(range(1, 13), 4)
    core: list[c.Support] = []
    budget = [5000]

    def fill() -> bool:
        budget[0] -= 1
        if len(core) == 16 or budget[0] < 0:
            return len(core) == 16
        v = max(need, key=lambda x: (need[x], rng.random()))
        options = [w for w in range(1, 13) if w != v and need[w] and c.edge(v, w) not in used]
        rng.shuffle(options)
        for a, b in combinations(options, 2):
            block = tuple(sorted((v, a, b)))
            shadow = [c.edge(x, y) for x, y in combinations(block, 2)]
            if any(e in used for e in shadow):
                continue
            used.update(shadow)
            core.append(block)
            for x in block:
                need[x] -= 1
            if fill():
                return True
            core.pop()
            used.difference_update(shadow)
            for x in block:
                need[x] += 1
        return False

    if not fill():
        return None
    leave = [e for e in combinations(range(1, 13), 2) if e not in used]
    rng.shuffle(leave)
    chosen: list[c.Pair] = []
    for e in leave:
        if rng.random() < 0.5 and not {*e} & {v for q in chosen for v in q}:
            chosen.append(e)
    to_zero = [x for x in range(1, 13) if all(x not in q for q in chosen)]
    zz = list(combinations(range(13, 20), 2))
    mz = rng.sample(zz, len(to_zero) // 2)
    slots = [u for q in mz for u in q]
    rng.shuffle(slots)
    pairs = [*chosen, *(c.edge(x, u) for x, u in zip(to_zero, slots, strict=True))]
    triples = [(0, *m) for m in matching] + core
    return triples, [*pairs, *(q for q in zz if q not in mz)]


def test_random_legal_structures_respect_the_cap() -> None:
    rng = random.Random(65555555555550000000)
    seen: dict[int, int] = {}
    while sum(seen.values()) < 40:
        built = random_structure(rng)
        if built is None:
            continue
        check = c.realization_check(*built)
        r, t = c.integer(check["R"]), c.integer(check["TRIANGLES"])
        assert t <= 255 - 2 * r - c.integer(check["P"])
        assert (t == 255) == (r == 0)
        seen[r] = seen.get(r, 0) + 1
    assert len(seen) >= 3


def test_supplemental_superset() -> None:
    superset = c.superset_check()
    assert superset["COUNT"] == 201
    assert superset["MAX_F"] == 255
    assert superset["ARGMAX"] == [[[0] * 13, [0] * 7]]
    assert superset["ROLE"] == "SUPPLEMENTAL_NOT_PROOF"


# Route B, thresholds and off-by-one.
def test_route_b_envelope_and_off_by_one() -> None:
    terms, new = c.route_b(255)
    old_terms, old = c.route_b(264)
    plus_one, after = c.route_b(256)
    assert len(terms) == 234 and terms == old_terms[:234] == plus_one[:234]
    assert new["ARGMAX_TERM"] == [255, 313315656, 420, 200, 238980, 5062176]
    assert old["ALL_T_MAX_BOUND"] == 313396120
    assert after["ALL_T_MAX_BOUND"] == 313324424
    assert new["MIN_STEP"] == 8768 and new["ROUNDING_RESIDUES"] == ["0"]


def test_scored_domain_ends_at_the_wedge_limit() -> None:
    terms, domain = c.route_b_domain()
    assert (domain["T_MIN"], domain["T_MAX"], domain["REFUSED_AT"]) == (22, 277, 278)
    assert terms[-1][0] == 277
    with pytest.raises(AssertionError, match="wedge identity"):
        c.route_b(278)


def test_thresholds_are_clean_cuts(result: dict[str, object]) -> None:
    cuts = [
        c.object_row(result[k])
        for k in ("STRICT_REDUCTION_THRESHOLD", "CURSOR_THRESHOLD", "INCUMBENT_CLOSURE_THRESHOLD")
    ]
    assert [(x["CAP"], x["RELATION"]) for x in cuts] == [(263, "<"), (263, "<="), (249, "<=")]
    assert cuts[0]["BOUND_AT_CAP_PLUS_1"] == 313396120  # equal to the old bound: not strict
    assert cuts[1]["BOUND_AT_CAP"] == 313387352 <= 313394584 < cuts[1]["BOUND_AT_CAP_PLUS_1"]
    assert cuts[2]["BOUND_AT_CAP"] == 313261884 <= 313263888 < cuts[2]["BOUND_AT_CAP_PLUS_1"]
    terms, _domain = c.route_b_domain()
    with pytest.raises(AssertionError, match="outside the scanned domain"):
        c.threshold([t for t in terms if t[0] <= 263], c.SOURCE_BOUND, strict=True)


def test_non_multiple_of_seven_base_rounds_up() -> None:
    terms, meta = c.route_b(30, 1681)
    assert terms[0][4] == 1681 and "0" not in c.rows(meta["ROUNDING_RESIDUES"])
    with (
        patch.object(c, "ceil", math.floor),
        pytest.raises(AssertionError, match="independent Route-B recount differs"),
    ):
        c.route_b(30, 1681)


def test_tampered_route_b_term_rejected() -> None:
    real = c.r32.route_b_envelope

    def bumped(profile: tuple[int, ...], cap: int, base: int) -> list[c.Term]:
        terms = list(real(profile, cap, base))
        t, bound, k4, contained, s4, s3 = terms[-1]
        terms[-1] = (t, bound - 1, k4, contained, s4, s3)
        return terms

    with patch.object(c.r32, "route_b_envelope", bumped):
        with pytest.raises(AssertionError, match="implementations differ"):
            c.route_b(255)
        with (
            patch.object(c.split, "route_b_terms", bumped),
            pytest.raises(AssertionError, match="independent Route-B recount differs"),
        ):
            c.route_b(255)


# Source tampering.
@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("SOURCE_CAP", 263, "target row differs"),
        ("SOURCE_S4_BASE", 1681, "target row differs"),
        ("SOURCE_BOUND", 313396119, "target row differs"),
        ("SOURCE_ROW", "NB_CERTIFICATES[1612]", "target row differs"),
    ],
)
def test_tampered_target_row_rejected(six_row: Six, name: str, value: object, message: str) -> None:
    with (
        patch.object(c.t256, "six_row_authority", return_value=six_row),
        patch.object(c, name, value),
        pytest.raises(AssertionError, match=message),
    ):
        c.frozen_row(c.frozen_authority())


def test_tampered_ledger_replay_rejected(six_row: Six) -> None:
    six_result, ledger = six_row
    other = "66655555555521000000"
    bad = dict(ledger)
    bad[other] = replace(bad[other], bound=bad[other].bound - 1)
    with (
        patch.object(c.t256, "six_row_authority", return_value=(six_result, bad)),
        pytest.raises(AssertionError, match="seven-row ledger is not reproduced"),
    ):
        c.frozen_row(c.frozen_authority())


@pytest.mark.parametrize(
    ("name", "message"),
    [("FROZEN_TREE", "frozen tree mismatch"), ("FROZEN_RESULT_SHA256", "blob digest mismatch")],
)
def test_wrong_authority_pin_rejected(name: str, message: str) -> None:
    width = len(getattr(c, name))
    with patch.object(c, name, "0" * width), pytest.raises(AssertionError, match=message):
        c.frozen_authority()


def test_tampered_reused_source_rejected() -> None:
    real = c.chase.git
    target = f"{c.FROZEN_HEAD}:src/lottolab/research/{c.r32.__name__.rsplit('.', 1)[1]}.py"

    def altered(*args: str) -> bytes:
        raw = real(*args)
        return raw + b"\n" if args == ("show", target) else raw

    with patch.object(c.chase, "git", altered), pytest.raises(AssertionError, match="changed"):
        c.module_provenance()


def test_provenance_pins_every_reused_module() -> None:
    provenance = c.module_provenance()
    assert len(provenance) == 10
    assert f"src/lottolab/research/{c.t256.__name__.rsplit('.', 1)[1]}.py" in provenance
