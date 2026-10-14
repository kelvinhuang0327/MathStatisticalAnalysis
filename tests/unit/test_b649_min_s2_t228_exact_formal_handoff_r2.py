"""Focused independent arithmetic, coverage and adversarial certificate checks."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from random import Random

import pytest

from lottolab.research import b649_min_s2_t228_exact_formal_handoff_r2 as cert


def test_frozen_graph_identities_and_algebra() -> None:
    facts = cert.model_facts()
    assert (
        facts["E"],
        facts["W"],
        facts["GOODMAN_SUM"],
        facts["SUM_CHOOSE3_DEGREES"],
        facts["A_MAX"],
        facts["K4_CONSTANT"],
    ) == (93, 828, 294, 2324, 198, 5956)
    for a, b, c, f in product(range(4), range(4), range(5), range(9)):
        sigmas = [0] * 3 + [1] * f + [0] * (8 - f) + [a, b, c]
        contribution = sum(s * (s + 3 - d) for s, d in zip(sigmas, cert.DEGREES[:14], strict=True))
        assert contribution == a * a + b * b + c * (c + 1) - f
        assert sum(sigmas) == a + b + c + f
        assert all(s <= 6 - d for s, d in zip(sigmas, cert.DEGREES[:14], strict=True))


def test_partition_counts_and_goodman_on_arbitrary_graphs() -> None:
    # Graphs need not be support realizations: the partition identity is general.
    rng = Random(228)
    for probability in [0.0, 0.15, 0.5, 0.8, 1.0]:
        for _ in range(8):
            graph: list[set[int]] = [set() for _ in range(20)]
            for u, v in combinations(range(20), 2):
                if rng.random() < probability:
                    graph[u].add(v)
                    graph[v].add(u)
            audit = cert.partition_audit(graph)
            parts = [cert.integer(v) for v in cert.items(audit["P_PARTS"])]
            assert audit["P"] == sum(parts) >= 0


def test_all_core_states_are_ordered_and_complete() -> None:
    states = cert.core_states()
    cert.check_core_coverage(states)
    assert len(states) == 720
    assert (3, 0, 4, 8) in states and (0, 3, 4, 8) in states


def test_independent_graph_and_havel_hakimi_histograms() -> None:
    expected: Counter[tuple[int, ...]] = Counter()
    edges = list(combinations(range(6), 2))
    for mask in range(1 << len(edges)):
        adjacency = [0] * 6
        for bit, (u, v) in enumerate(edges):
            if (mask >> bit) % 2:
                adjacency[u] |= 1 << v
                adjacency[v] |= 1 << u
        zeta = tuple(sorted(6 - row.bit_count() for row in adjacency))
        expected[zeta] += 1
        assert sum(zeta) == 36 - 2 * mask.bit_count()
    assert expected == cert.zero_histograms()
    candidates = list(combinations_with_replacement(range(1, 7), 6))
    hh: set[tuple[int, ...]] = set()
    for z in candidates:
        degrees = [6 - x for x in z]
        while degrees:
            degrees.sort(reverse=True)
            degree = degrees.pop(0)
            if degree < 0 or degree > len(degrees):
                break
            for i in range(degree):
                degrees[i] -= 1
        else:
            hh.add(z)
    assert len(candidates) == 462 and len(hh) == len(expected) == 102
    assert hh == set(expected) == {z for z in candidates if cert.erdos_gallai(z)}
    assert len([z for z in hh if sum(z) <= 18]) == 38


def test_seven_r_class_maxima_and_split_redistribution() -> None:
    counts = cert.zero_histograms()
    maxima: dict[int, int] = {}
    for r in range(6, 19, 2):
        best = -1000
        for a in range(4):
            for b in range(4):
                for c in range(5):
                    f = r - a - b - c
                    if not 0 <= f <= 8:
                        continue
                    sigma = [0] * 3 + [1] * f + [0] * (8 - f) + [a, b, c]
                    for z in counts:
                        if sum(z) != r:
                            continue
                        original = (
                            240
                            - 10 * r
                            + sum(
                                s * (s + 7 - d)
                                for s, d in zip(sigma, cert.DEGREES[:14], strict=True)
                            )
                            + sum(x * (x - 1) for x in z)
                        )
                        simplified = (
                            240 + a * a + b * b + c * (c + 1) - f + sum(x * (x - 7) for x in z)
                        )
                        assert original == simplified
                        best = max(best, simplified)
        maxima[r] = best
    assert maxima == {6: 228, 8: 226, 10: 228, 12: 222, 14: 218, 16: 216, 18: 210}
    assert cert.relaxation()["R_CLASS_MAXIMA"] == {str(r): b for r, b in maxima.items()}


def test_all_envelope_terms_independently_as_fractions() -> None:
    for cap, count in [(265, 244), (228, 207)]:
        terms = cert.independent_envelope(cap)
        assert len(terms) == count
        for t, bound, k4, contained, s4, s3 in terms:
            excess = 2324 - 10 * (828 - 3 * t)
            assert k4 == max(0, -(-excess // 4))
            assert contained == min(k4, 198)
            assert s4 == max(112, 448 * contained + 679 * (k4 - contained))
            assert s3 == 154000 + 20272 * (t - 22) + 2800 * (828 - 3 * t)
            rational = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
            assert Fraction(bound - 1) < rational <= bound
        cert.check_envelope(terms, cap)
    assert cert.independent_envelope(228)[-1] == (228, 313063660, 221, 198, 104321, 4733232)
    assert max(t[1] for t in cert.independent_envelope(265)) == 313395060
    assert max(t[1] for t in cert.independent_envelope(228)) == 313063660


def test_immutable_inputs_family_and_exact_stored_replay() -> None:
    result = cert.compute_result()
    assert cert.RESULT.read_bytes() == cert.render(result)
    family = cert.obj(result["FAMILY"])
    assert family["ROWS_REPLAYED"] == 4647
    assert family["OTHER_ROWS_PRESERVED"] == 4646
    assert family["CURSOR_PROFILES_REEVALUATED"] == 197
    assert family["FAMILY_AFTER_SINGLE_ROW"] == 313395060
    assert family["SINGLE_ROW_FAMILY_DELTA"] == 0
    assert family["OWNERS_AFTER"] == [cert.OTHER_OWNER]
    assert result["PROFILE_DELTA"] == 331400
    assert result["BELOW_INCUMBENT_BY"] == 200228
    assert result["PRIOR_ART_ORIGINAL_STATUS"] == (
        "PROVEN_IMPROVEMENT; PENDING_ONE_FRESH_FOCUSED_SCIENTIFIC_REVIEW"
    )
    assert result["GLOBAL_K20_OPTIMUM"] == result["LEGAL_SUPPORT_ATTAINMENT"] == "UNKNOWN"


def test_negative_omitted_core_state() -> None:
    with pytest.raises(ValueError, match="core states"):
        cert.relaxation(cert.core_states()[:-1])


def test_negative_omitted_zero_graph() -> None:
    with pytest.raises(ValueError, match="omitted zero graphs"):
        cert.zero_histograms(range(32767))


def test_negative_duplicate_zero_graph() -> None:
    with pytest.raises(ValueError, match="duplicate zero graph"):
        cert.zero_histograms([0, 0])


def test_negative_histogram_omission() -> None:
    counts = cert.zero_histograms()
    counts.pop((1, 1, 1, 1, 1, 1))
    with pytest.raises(ValueError, match="Erdos-Gallai disagreement"):
        cert.relaxation(counts=counts)


@pytest.mark.parametrize("parts,direction", [((1, 2, 3, 4), 1), ((-1,), -1)])
def test_negative_invalid_penalty(parts: tuple[int, ...], direction: int) -> None:
    with pytest.raises(ValueError, match="P direction"):
        cert.drop_penalty(240, parts, direction)


def test_negative_wrong_profile_and_capacity_model() -> None:
    with pytest.raises(ValueError, match="wrong degree profile"):
        cert.model_facts(cert.OTHER_OWNER)
    model = dict(cert.MODEL)
    model["pair_linearity"] = False
    with pytest.raises(ValueError, match="wrong degree profile/model"):
        cert.model_facts(model=model)


def test_negative_source_mismatch() -> None:
    with pytest.raises(ValueError, match="source SHA256 mismatch"):
        cert.blob(cert.PRIOR_HEAD, cert.PRIOR_RESULT, "0" * 64)
    with pytest.raises(ValueError, match="source tree mismatch"):
        cert.identity(cert.BASE_HEAD, cert.PRIOR_TREE)
    with pytest.raises(ValueError, match="local source mismatch"):
        cert.local_matches(cert.BASE_RESULT, b"altered source")


def test_negative_wrong_t248_constant() -> None:
    with pytest.raises(ValueError, match="wrong K4 constant"):
        cert.independent_envelope(228, 5954)
    wrong = cert.independent_envelope(228)
    t, bound, k4, contained, s4, s3 = wrong[-1]
    wrong[-1] = (t, bound, k4 + 1, contained, s4, s3)
    with pytest.raises(ValueError, match="rounding error"):
        cert.check_envelope(wrong, 228)


def test_negative_final_rounding_error_and_omitted_term() -> None:
    wrong = cert.independent_envelope(228)
    t, bound, k4, contained, s4, s3 = wrong[-1]
    wrong[-1] = (t, bound - 1, k4, contained, s4, s3)
    with pytest.raises(ValueError, match="rounding error"):
        cert.check_envelope(wrong, 228)
    with pytest.raises(ValueError, match="incomplete"):
        cert.check_envelope(cert.independent_envelope(228)[:-1], 228)


def test_negative_missing_family_row_and_altered_cursor() -> None:
    base, _, _ = cert.load_inputs()
    altered = deepcopy(base)
    cert.obj(altered["RESOLVED_ROW_BOUNDS"]).pop(cert.PROFILE)
    with pytest.raises(ValueError, match="altered Base authority"):
        cert.replay_family(altered, 313063660)
    altered = deepcopy(base)
    cert.obj(cert.obj(altered["CURSOR"])["COARSE_BOUND_PROJECTION"]).popitem()
    with pytest.raises(ValueError, match="altered Base authority"):
        cert.replay_family(altered, 313063660)


def test_negative_stored_result_tampering() -> None:
    stored = cert.decode(cert.RESULT.read_bytes())
    stored["NEW_PROVEN_CAP"] = 227
    with pytest.raises(ValueError, match="not exactly reproducible"):
        cert.verify_result(stored)
