"""Independent degree-domain completeness and exact rational all-T verification."""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from fractions import Fraction
from itertools import combinations_with_replacement, product
from math import ceil, comb, floor

import pytest

from lottolab.research import b649_k20_min_s2_d6_generic_cap238_certificate_r1 as x
from lottolab.research import b649_k20_min_s2_next_owner_d6_cap260_certificate_r1 as old


def havel_hakimi(degrees: Sequence[int]) -> bool:
    """Constructive graph criterion, independent of the theorem's Erdős-Gallai."""
    residual = list(degrees)
    while residual:
        residual.sort(reverse=True)
        highest = residual.pop(0)
        if highest < 0 or highest > len(residual):
            return False
        for i in range(highest):
            residual[i] -= 1
        if any(v < 0 for v in residual):
            return False
    return True


def bipartite_havel_hakimi(left: Sequence[int], right: Sequence[int]) -> bool:
    """Constructive bipartite criterion, independent of Gale-Ryser inequalities."""
    if sum(left) != sum(right):
        return False
    residual = list(right)
    for highest in sorted(left, reverse=True):
        residual.sort(reverse=True)
        if highest < 0 or highest > len(residual):
            return False
        for i in range(highest):
            residual[i] -= 1
        if any(v < 0 for v in residual):
            return False
    return not any(residual)


def independent_domain() -> set[tuple[tuple[int, ...], tuple[int, ...], int]]:
    d = tuple(map(int, x.TARGET_PROFILE[:14]))
    options = [
        list(combinations_with_replacement(range(7 - v), count))
        for v, count in [(6, 4), (5, 6), (4, 2), (2, 2)]
    ]
    zeros = list(combinations_with_replacement(range(1, 7), 6))
    assert len(zeros) == 462
    assert len(list(product(*options))) == 630
    accepted: set[tuple[tuple[int, ...], tuple[int, ...], int]] = set()
    for pieces in product(*options):
        sigma = tuple(s for piece in pieces for s in piece)
        h = tuple(7 - v + s for v, s in zip(d, sigma, strict=True))
        residual = tuple(6 - v - s for v, s in zip(d, sigma, strict=True))
        if not havel_hakimi(h) or not havel_hakimi(residual):
            continue
        for zeta in zeros:
            if sum(sigma) != sum(zeta):
                continue
            if not havel_hakimi(tuple(v - 1 for v in zeta)):
                continue
            if not havel_hakimi(tuple(6 - v for v in zeta)):
                continue
            if not bipartite_havel_hakimi(sigma, zeta):
                continue
            # Independently expand F; Phi=296 and its constant part is 242.
            f = (
                242
                + sum(s * (s + 4 - v) for v, s in zip(d, sigma, strict=True))
                + sum(v * (v - 8) for v in zeta)
            )
            accepted.add((sigma, zeta, f))
    return accepted


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    with pytest.MonkeyPatch.context() as patch:

        def forbidden(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("solver, family replay or old D6 reproof is forbidden")

        for module, name in (
            (x.current, "load_authority"),
            (x.current, "chase"),
            (x.model, "support_union_model"),
            (x.model, "solve_group"),
            (x.model, "import_module"),
            (x.split, "conditional_p_floor"),
            (old, "verify_arithmetic"),
            (old, "current_row"),
            (old, "theorem_provenance"),
        ):
            patch.setattr(module, name, forbidden)
        derived = x.compute_result()
    assert not any(name.startswith("ortools") for name in sys.modules)
    return derived


def test_universal_identity_and_exact_target_premises() -> None:
    p = tuple(map(int, x.TARGET_PROFILE))
    assert Counter(p) == {6: 4, 5: 6, 4: 2, 2: 2, 0: 6}
    assert sum(p) == 3 * 22 == 66
    assert sum(6 - d for d in p) == 2 * 27 == 54
    assert sum(6 + d for d in p) == 2 * 93
    assert sum(13 - d for d in p) == 2 * 97
    assert sum(comb(13 - d, 2) for d in p) - 606 == 296
    assert comb(20, 3) - 18 * 97 == -606
    for q in range(4):
        assert 1 - q + (comb(q, 2) if q >= 2 else 0) - int(q == 3) == int(q == 0)


def test_independent_complete_necessary_domain_and_graph_cap() -> None:
    independent = independent_domain()
    reused = {(c.sigma, c.zeta, c.f) for c in x.split.degree_configurations(x.TARGET_PROFILE)}
    assert reused == independent
    assert len(independent) == 620
    assert max(f for _s, _z, f in independent) == 238
    assert (tuple([0] * 12 + [4, 4]), (1, 1, 1, 1, 2, 2), 238) in independent
    cert = x.degree_certificate()
    assert cert["P0_TRIANGLE_CAP"] == cert["TRIANGLE_CAP"] == 238
    assert cert["BRANCH_COUNTS"] == {"A_NONNEGATIVE_P": 620}
    assert cert["CONDITIONAL_CONFIGURATIONS"] == []
    assert (
        sum(x.current.integer(v) for v in x.current.object_row(cert["F_HISTOGRAM"]).values()) == 620
    )


def test_complete_triangle_domain_and_preserved_s4(result: dict[str, object]) -> None:
    expected: list[list[int]] = []
    for t in range(22, 239):
        k4 = max(0, ceil(Fraction(2342 - 10 * (830 - 3 * t), 4)))
        contained = min(k4, 199)
        s4 = max(112, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * 830 + 11872 * (t - 22) - 30800
        bound = 372228640 - 63838600 + s3 - floor(Fraction(4 * s4, 7))
        expected.append([t, bound, k4, contained, s4, s3])
    assert result["ALL_T_TERMS"] == expected
    assert result["TRIANGLE_DOMAIN"] == [22, 238]
    assert result["TERM_COUNT"] == len(expected) == 217
    assert max(expected, key=lambda t: t[1]) == [238, 313_159_012, 296, 199, 155_015, 4_857_552]
    assert result["ARGMAX_TERM"] == expected[-1]
    assert result["S4_BASE"] == 112 and result["A_MAX"] == 199
    # Both quartet types occur at the endpoint; using 448 for all K4 is unsound.
    assert expected[-1][4] == 448 * 199 + 679 * 97


def test_strict_gain_exclusion_and_comparison_only(result: dict[str, object]) -> None:
    assert result["EXISTING_CERTIFIED_CAP"] == 260 and result["PROVEN_NEW_CAP"] == 238
    assert result["OLD_PROFILE_BOUND"] == 313_356_176
    assert result["NEW_PROFILE_BOUND"] == 313_159_012
    assert result["EXACT_PROFILE_DELTA"] == 197_164
    assert result["BELOW_INCUMBENT_BY"] == 104_876
    assert result["STRICT_GAIN_POTENTIAL_FOR_PROFILE"] == "PROVED_EXCLUDED"
    comparison = x.current.object_row(result["FAMILY_COMPARISON"])
    assert comparison["TARGET_BELOW_THAT_BOUND_BY"] == 242_168
    assert comparison["SHARED_LEDGER_UPDATED"] is False
    assert comparison["FAMILY_BOUND_EFFECT"] == "NOT_VERIFIED_OTHER_TERMS_NOT_INTEGRATED"


def test_pinned_source_and_model_authority(result: dict[str, object]) -> None:
    authority = x.current.object_row(result["GENERIC_THEOREM_IDENTITY"])
    assert authority["THEOREM_HEAD"] == x.THEOREM_HEAD
    assert authority["THEOREM_BLOB"] == x.THEOREM_BLOB
    assert authority["THEOREM_SHA256"] == x.THEOREM_SHA256
    assert authority["OLD_RESULT_SHA256"] == x.OLD_RESULT_SHA256
    assert authority["MODEL_SHA256"] == x.MODEL_SHA256
    assert authority["CONDITIONAL_P12_USED"] is False
    assert result["THEOREM_APPLICABILITY"] == result["MODEL_SEMANTICS"] == "PASS"


def test_fail_closed_scope_provenance_and_missing_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="only the target"):
        x.degree_certificate(x.split.SPECIAL)
    monkeypatch.setattr(x, "THEOREM_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="pinned input changed"):
        x.source_authority()
    monkeypatch.undo()
    source = list(x.split.degree_configurations(x.TARGET_PROFILE))

    def missing_configuration(_profile: str | Sequence[int]) -> Iterator[x.split.Configuration]:
        return iter(source[:-1])

    monkeypatch.setattr(x.split, "degree_configurations", missing_configuration)
    with pytest.raises(AssertionError, match="does not establish cap238"):
        x.degree_certificate()


def test_stale_cap260_envelope_is_rejected() -> None:
    accepted, _ = x.source_authority()
    accepted["ALL_T_TERMS"] = []
    with pytest.raises(AssertionError, match="accepted S4 terms differ"):
        x.envelope(accepted, 238)


def test_exact_result_replay_and_forbidden_work_guards(result: dict[str, object]) -> None:
    assert x.RESULT_PATH.read_text(encoding="utf-8") == x.render(result)
    assert result["PROOF_SHA256"] == x.digest(x.PROOF.encode())
    for key in (
        "EXISTING_D6_CERTIFICATE_MUTATED",
        "SHARED_LEDGER_MUTATED",
        "RUN1_MUTATED",
        "HEAVY_SOLVER_STARTED",
        "REMOTE_WRITE",
    ):
        assert result[key] == "NO"
    for key in ("SOLVER_CALLS", "SUPPORT_MODELS_BUILT", "PORTFOLIO_ENUMERATIONS"):
        assert result[key] == 0
