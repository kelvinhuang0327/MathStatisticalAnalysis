"""Independent checks for the fixed M2 K5 vs M0 K5 paired detectability calculation."""

from __future__ import annotations

import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest
import tools.b649_k5_detectability_r1 as det

ALPHA = Fraction(1, 20)
BONFERRONI = Fraction(1, 180)
Q_MAIN = Fraction(121, 436)


def brute_reject(w: int, m: int, alpha: Fraction) -> bool:
    """Exact one-sided sign-test p-value P[Binomial(m,1/2) >= w] <= alpha; m = 0 never rejects."""
    if m == 0:
        return False
    tail = sum(math.comb(m, k) for k in range(w, m + 1))
    return Fraction(tail, 2**m) <= alpha


def brute_thresholds(m_max: int, alpha: Fraction) -> list[int]:
    """Smallest r with exact tail P[Binomial(m,1/2) >= r] <= alpha, scanning down from r = m+1."""
    thresholds: list[int] = []
    for m in range(m_max + 1):
        tail, r = 0, m + 1
        for k in range(m, -1, -1):
            tail += math.comb(m, k)
            if tail * alpha.denominator > alpha.numerator * 2**m:
                break
            r = k
        thresholds.append(r)
    return thresholds


def enumerate_power(n: int, q: Fraction, delta: Fraction, alpha: Fraction) -> Fraction:
    """Direct enumeration of all 3^N paired-difference sequences."""
    probability = {1: (q + delta) / 2, -1: (q - delta) / 2, 0: 1 - q}
    weight: dict[tuple[int, int], Fraction] = {}
    total = Fraction(0)
    for sequence in itertools.product((-1, 0, 1), repeat=n):
        wins, losses = sequence.count(1), sequence.count(-1)
        if not brute_reject(wins, wins + losses, alpha):
            continue
        key = (wins, losses)
        if key not in weight:
            weight[key] = math.prod((probability[d] for d in sequence), start=Fraction(1))
        total += weight[key]
    return total


def trinomial_power(n: int, q: Fraction, delta: Fraction, alpha: Fraction) -> Fraction:
    """Exact integer trinomial sum over (wins, losses), with brute-force thresholds."""
    p_plus, p_minus, p_zero = (q + delta) / 2, (q - delta) / 2, 1 - q
    den = math.lcm(p_plus.denominator, p_minus.denominator, p_zero.denominator)
    a, b, c = (int(p * den) for p in (p_plus, p_minus, p_zero))
    thresholds = brute_thresholds(n, alpha)
    a_pow, b_pow, c_pow = ([x**e for e in range(n + 1)] for x in (a, b, c))
    total = 0
    for wins in range(n + 1):
        for losses in range(n - wins + 1):
            m = wins + losses
            if wins >= thresholds[m]:
                ways = math.comb(n, m) * math.comb(m, wins)
                total += ways * a_pow[wins] * b_pow[losses] * c_pow[n - m]
    return Fraction(total, den**n)


def test_module_is_this_checkout() -> None:
    assert Path(det.__file__).resolve().parents[1] == Path(__file__).resolve().parents[2]


def test_fixed_grid_is_the_packet_grid() -> None:
    assert [v for _, v in det.Q_GRID] == [Fraction(15, 100), Fraction(121, 436), Fraction(3, 10)]
    assert list(det.DELTA_GRID) == [Fraction(p, 100) for p in (0, 1, 2, 3, 5)]
    assert det.N_GRID == (100, 250, 436, 500, 1000, 2000, 5000, 10000)
    assert [v for _, v, _ in det.ALPHA_GRID] == [Fraction(5, 100), Fraction(5, 100) / 9]
    assert det.DESIGN_EFFECTS == (1, 2, 4)
    keys = det.grid_keys()
    assert len(keys) == len(set(keys)) == 3 * 5 * 8 * 2 == 240


@pytest.mark.parametrize("q", [v for _, v in det.Q_GRID] + [Fraction(1), Fraction(0)])
@pytest.mark.parametrize("delta_scale", [Fraction(0), Fraction(1, 3), Fraction(1)])
def test_difference_distribution_is_exact(q: Fraction, delta_scale: Fraction) -> None:
    for delta in (q * delta_scale, -q * delta_scale):
        p_plus, p_minus, p_zero = det.difference_distribution(q, delta)
        assert (p_plus, p_minus, p_zero) == ((q + delta) / 2, (q - delta) / 2, 1 - q)
        assert p_plus + p_minus + p_zero == 1
        assert all(0 <= p <= 1 for p in (p_plus, p_minus, p_zero))
        assert p_plus - p_minus == delta and p_plus + p_minus == q
        theta = det.win_probability(q, delta)
        assert theta == (None if q == 0 else p_plus / q)


@pytest.mark.parametrize(
    ("n", "q", "delta", "alpha"),
    [
        (0, Q_MAIN, 0, ALPHA),
        (-5, Q_MAIN, 0, ALPHA),
        (100.0, Q_MAIN, 0, ALPHA),
        (True, Q_MAIN, 0, ALPHA),
        ("100", Q_MAIN, 0, ALPHA),
        (100, -0.01, 0, ALPHA),
        (100, 1.01, 0, ALPHA),
        (100, math.nan, 0, ALPHA),
        (100, math.inf, 0, ALPHA),
        (100, True, 0, ALPHA),
        (100, None, 0, ALPHA),
        (100, 0.15, 0.16, ALPHA),
        (100, 0.15, -0.16, ALPHA),
        (100, 0, 0.01, ALPHA),
        (100, 0.15, math.nan, ALPHA),
        (100, Q_MAIN, 0.02, 0),
        (100, Q_MAIN, 0.02, 1),
        (100, Q_MAIN, 0.02, -0.05),
        (100, Q_MAIN, 0.02, 1.5),
        (100, Q_MAIN, 0.02, math.nan),
        (100, Q_MAIN, 0.02, False),
    ],
)
def test_illegal_inputs_are_rejected(n: object, q: object, delta: object, alpha: object) -> None:
    with pytest.raises(ValueError):
        det.paired_power(n, q, delta, alpha)


def test_power_beyond_precomputed_range_is_rejected() -> None:
    calc = det.PairedSignTestPower(Q_MAIN, 0, ALPHA, 10)
    with pytest.raises(ValueError):
        calc.power(11)
    with pytest.raises(ValueError):
        calc.conditional_rejection(11)
    with pytest.raises(ValueError):
        det.critical_values(-1, ALPHA)


@pytest.mark.parametrize("alpha", [ALPHA, BONFERRONI])
def test_critical_values_match_brute_force(alpha: Fraction) -> None:
    thresholds, sizes = det.critical_values(1000, alpha)
    assert list(thresholds) == brute_thresholds(1000, alpha)
    for m in [*range(60), *range(60, 1001, 47)]:
        assert brute_reject(thresholds[m], m, alpha) or thresholds[m] == m + 1
        assert not brute_reject(thresholds[m] - 1, m, alpha)
        exact = Fraction(sum(math.comb(m, k) for k in range(thresholds[m], m + 1)), 2**m)
        assert exact <= alpha
        assert sizes[m] == float(exact)
        if thresholds[m] >= 1 and m > 0:
            above = Fraction(sum(math.comb(m, k) for k in range(thresholds[m] - 1, m + 1)), 2**m)
            assert above > alpha


def test_no_attainable_threshold_and_first_attainable_m() -> None:
    primary, _ = det.critical_values(20, ALPHA)
    supplementary, _ = det.critical_values(20, BONFERRONI)
    assert [primary[m] for m in range(5)] == [1, 2, 3, 4, 5]  # r(m) = m + 1
    assert primary[5] == 5  # 2^-5 = 0.03125 <= 0.05
    assert [supplementary[m] for m in range(8)] == list(range(1, 9))
    assert supplementary[8] == 8  # 2^-8 <= 1/180 < 2^-7


def test_m_zero_and_all_concordant_never_reject() -> None:
    calc = det.PairedSignTestPower(Q_MAIN, Fraction(1, 20), ALPHA, 50)
    assert calc.critical[0] == 1
    assert calc.conditional_rejection(0) == 0.0
    all_concordant = det.PairedSignTestPower(0, 0, ALPHA, 50)
    assert all_concordant.theta is None
    assert all_concordant.power(50).power == 0.0
    assert all_concordant.power(50).discordance_mass == 1.0


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_tiny_samples_cannot_reject_at_primary_alpha(n: int) -> None:
    assert det.paired_power(n, 1, 1, ALPHA) == 0.0
    assert det.paired_power(n, Q_MAIN, Fraction(1, 20), ALPHA) == 0.0


def test_legal_boundaries() -> None:
    assert det.paired_power(5, 1, 1, ALPHA) == pytest.approx(1.0, abs=1e-15)
    assert det.paired_power(7, 1, 1, BONFERRONI) == 0.0
    assert det.paired_power(8, 1, 1, BONFERRONI) == pytest.approx(1.0, abs=1e-15)
    assert det.paired_power(50, 1, -1, ALPHA) == 0.0
    assert det.paired_power(50, Fraction(3, 10), Fraction(-3, 10), ALPHA) == 0.0
    always_win = det.PairedSignTestPower(Fraction(3, 10), Fraction(3, 10), ALPHA, 30)
    assert [always_win.conditional_rejection(m) for m in range(8)] == [0.0] * 5 + [1.0] * 3


@pytest.mark.parametrize(
    ("p", "n"),
    [
        (Fraction(1, 2), 1),
        (Fraction(1, 2), 37),
        (Fraction(121, 436), 120),
        (Fraction(6486, 12100), 400),
        (Fraction(2, 3), 333),
        (Fraction(1, 1000), 50),
        (Fraction(999, 1000), 50),
    ],
)
def test_binomial_tail_matches_exact_sum(p: Fraction, n: int) -> None:
    dist = det.Binomial(p)
    a, d = p.numerator, p.denominator
    suffix = [0] * (n + 2)
    for j in range(n, -1, -1):
        suffix[j] = suffix[j + 1] + math.comb(n, j) * a**j * (d - a) ** (n - j)
    for k in range(-1, n + 2):
        exact = Fraction(suffix[min(max(k, 0), n + 1)], d**n)
        assert dist.sf(k, n) == pytest.approx(float(exact), rel=1e-11, abs=1e-15), k


@pytest.mark.parametrize(
    ("n", "q", "delta", "alpha"),
    [(n, Q_MAIN, Fraction(1, 20), ALPHA) for n in range(1, 11)]
    + [(n, Fraction(3, 10), Fraction(3, 100), BONFERRONI) for n in (8, 9, 10)]
    + [
        (10, Fraction(3, 20), Fraction(0), ALPHA),
        (9, Fraction(1, 2), Fraction(-1, 4), ALPHA),
        (6, Fraction(1), Fraction(1), ALPHA),
        (10, Fraction(4, 5), Fraction(1, 5), ALPHA),
    ],
)
def test_mixture_matches_direct_sequence_enumeration(
    n: int, q: Fraction, delta: Fraction, alpha: Fraction
) -> None:
    exact = enumerate_power(n, q, delta, alpha)
    assert det.paired_power(n, q, delta, alpha) == pytest.approx(float(exact), rel=1e-12, abs=1e-15)


@pytest.mark.parametrize(
    ("n", "q", "delta", "alpha"),
    [
        (100, Q_MAIN, Fraction(1, 50), ALPHA),
        (100, Fraction(3, 10), Fraction(1, 20), BONFERRONI),
        (436, Q_MAIN, Fraction(1, 50), ALPHA),
    ],
)
def test_grid_points_match_exact_trinomial_sum(
    n: int, q: Fraction, delta: Fraction, alpha: Fraction
) -> None:
    exact = trinomial_power(n, q, delta, alpha)
    calc = det.PairedSignTestPower(q, delta, alpha, max(det.N_GRID))
    assert calc.power(n).power == pytest.approx(float(exact), rel=1e-10, abs=1e-13)


@pytest.mark.parametrize("alpha", [ALPHA, BONFERRONI])
@pytest.mark.parametrize("q", [v for _, v in det.Q_GRID])
def test_null_rejection_never_exceeds_alpha(q: Fraction, alpha: Fraction) -> None:
    calc = det.PairedSignTestPower(q, 0, alpha, 2000)
    assert calc.theta == Fraction(1, 2)
    for m in range(2001):
        assert calc.conditional_rejection(m) == pytest.approx(calc.sizes[m], rel=1e-11, abs=1e-15)
        assert calc.sizes[m] <= float(alpha)
    for n in (100, 250, 436, 500, 1000, 2000):
        power = calc.power(n).power
        assert power <= float(alpha) + det.NULL_TOLERANCE
        assert power < float(alpha)  # discrete conservatism is expected, not an error


def test_rejection_direction_is_candidate_better() -> None:
    q = Fraction(3, 10)
    better = det.paired_power(1000, q, Fraction(1, 20), ALPHA)
    worse = det.paired_power(1000, q, Fraction(-1, 20), ALPHA)
    null = det.paired_power(1000, q, 0, ALPHA)
    assert worse < null < float(ALPHA) < better
    powers = [det.paired_power(1000, q, d, ALPHA) for d in det.DELTA_GRID]
    assert powers == sorted(powers)


def test_first_grid_n_is_first_reaching_without_monotonicity() -> None:
    series = [(100, 0.5), (250, 0.81), (436, 0.79), (500, 0.85), (1000, 0.95)]
    assert det.first_grid_n(series, 0.8) == 250
    assert det.first_grid_n(series, 0.9) == 1000
    assert det.first_grid_n(series, 0.99) is None
    summary = det.series_summary(series)
    assert summary["monotone_non_decreasing_in_grid"] is False
    t80 = cast(dict[str, dict[str, object]], summary["targets"])["80_PERCENT"]
    assert t80["first_grid_n"] == 250
    assert t80["all_later_grid_points_at_or_above_target"] is False
    assert t80["design_effect_draws"] == {"1": 250, "2": 500, "4": 1000}
    unreached = cast(
        dict[str, dict[str, object]], det.series_summary([(100, 0.1), (250, 0.2)])["targets"]
    )
    assert unreached["90_PERCENT"]["first_grid_n"] == det.NOT_REACHED
    assert unreached["90_PERCENT"]["design_effect_draws"] == {
        "1": det.NOT_REACHED,
        "2": det.NOT_REACHED,
        "4": det.NOT_REACHED,
    }


def synthetic_rows(power: float = 0.5) -> list[dict[str, object]]:
    return [
        {
            "scenario_id": f"{q}|{d}|{n}|{a}",
            "q_label": q,
            "delta_exact": det.fraction_text(det.DELTA_GRID[d]),
            "delta": float(det.DELTA_GRID[d]),
            "alpha_label": a,
            "N": n,
            "power": power if d else 0.001,
        }
        for q, d, a, n in det.grid_keys()
    ]


def test_grid_completeness_check_rejects_missing_and_duplicates() -> None:
    rows = synthetic_rows()
    assert det.check_grid(rows)["scenario_count"] == 240
    with pytest.raises(AssertionError):
        det.check_grid(rows[1:])
    with pytest.raises(AssertionError):
        det.check_grid([*rows[1:], rows[2]])
    with pytest.raises(AssertionError):
        det.check_grid([{**rows[0], "power": 1.5}, *rows[1:]])


def test_null_size_check_fails_closed_above_alpha() -> None:
    rows = synthetic_rows()
    assert all(c["status"] == "CONSERVATIVE_DISCRETE_TEST" for c in det.null_size_check(rows))
    bad = [{**r, "power": 0.051} if r["delta"] == 0.0 else r for r in rows]
    with pytest.raises(AssertionError):
        det.null_size_check(bad)


def write_per_draw(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def per_draw_row(model: str, k: int, draw: str, prize: bool | None) -> dict[str, object]:
    return {
        "K": k,
        "model_id": model,
        "target_draw": draw,
        "official_outcome": None if prize is None else {"numbers": [1, 2, 3, 4, 5, 6]},
        "official_any_prize": prize,
        "generated_tickets": [[1, 2, 3, 4, 5, 6]],
    }


def test_read_paired_k5_uses_only_m0_m2_k5(tmp_path: Path) -> None:
    flags = {"1": (True, False), "2": (False, True), "3": (True, True), "4": (False, False)}
    rows = [
        per_draw_row(m, 5, d, f[i]) for d, f in flags.items() for i, m in enumerate(("M2", "M0"))
    ]
    rows += [per_draw_row("M1", 5, d, True) for d in flags]
    rows += [per_draw_row("M2", 3, d, True) for d in flags]
    rows += [per_draw_row("M2", 5, "5", None), per_draw_row("M0", 5, "5", True)]
    per_draw = tmp_path / "per_draw.jsonl"
    write_per_draw(per_draw, rows)
    counts, extraction = det.read_paired_k5(per_draw, ["1", "2", "3", "4", "5"])
    assert (counts.b, counts.c, counts.both_success_n, counts.both_failure_n) == (1, 1, 1, 1)
    assert counts.paired_target_n == 4 and counts.excluded_missing_outcome_pairs == 1
    assert counts.q_observed == Fraction(1, 2)
    assert extraction["records_used"] == 10 and extraction["per_draw_lines_read"] == len(rows)
    assert extraction["prizes_rescored"] is False


def test_read_paired_k5_rejects_duplicates_and_target_mismatch(tmp_path: Path) -> None:
    per_draw = tmp_path / "per_draw.jsonl"
    base = [per_draw_row(m, 5, "1", True) for m in ("M0", "M2")]
    write_per_draw(per_draw, [*base, per_draw_row("M2", 5, "1", False)])
    with pytest.raises(ValueError, match="duplicate"):
        det.read_paired_k5(per_draw, ["1"])
    write_per_draw(per_draw, base)
    with pytest.raises(ValueError, match="targets differ"):
        det.read_paired_k5(per_draw, ["1", "2"])
    not_boolean = {**per_draw_row("M2", 5, "1", True), "official_any_prize": 1}
    write_per_draw(per_draw, [*base[:1], not_boolean])
    with pytest.raises(ValueError, match="boolean"):
        det.read_paired_k5(per_draw, ["1"])
