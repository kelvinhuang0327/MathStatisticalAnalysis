"""B649 M2 K5 vs M0 K5 paired-gain detectability: fixed-grid planning power.

Exact one-sided conditional sign test on discordant draws, under a stated IID
paired-difference model with q and delta fixed over the observation period.
The frozen first-batch artifacts are read only for input-consistency checks:
no ticket regeneration, no prize re-scoring, no DB, no new draw results.

Commands (Python 3.13, stdlib only):
  spec     verify fixed source identity and paired K5 inputs; write design_spec.json
  run      compute all 240 fixed scenarios; write detectability_results.json
  capture  run one verification command; record argv, exit code and output
Outputs are create-once: an existing file is never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from fractions import Fraction
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import cast

TASK_ID = "B649_M2_K5_DETECTABILITY_R1"
SOURCE_TASK_ID = "B649_K235_SHARED_EVAL_FIRST_BATCH_R1"
SOURCE_COMMIT = "2d0130f95d168f9a0afd2f7b2015923bed947974"
WORKSPACE = Path("/Users/kelvin/VibeCoding-WorkSpace")
SOURCE_ARTIFACT_ROOT = WORKSPACE / ".task-data" / SOURCE_TASK_ID
OUTPUT_ROOT = WORKSPACE / ".task-data" / TASK_ID
ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATHS = (
    "tools/b649_k5_detectability_r1.py",
    "tests/unit/test_b649_k5_detectability_r1.py",
)
REQUIRED_INPUTS = ("study_spec.json", "per_draw.jsonl", "summary.json", "judge.json")
CANDIDATE, BASELINE, K = "M2", "M0", 5
# Owner-reported first-batch values: consistency inputs only, never fitted to.
REPORTED = {
    "candidate_success_n": 75,
    "baseline_success_n": 66,
    "b": 65,
    "c": 56,
    "both_success_n": 10,
    "both_failure_n": 305,
    "paired_target_n": 436,
}

# Fixed planning grid (3 x 5 x 8 x 2 = 240); never edited after results exist.
Q_GRID = (("0.15", Fraction(3, 20)), ("121/436", Fraction(121, 436)), ("0.30", Fraction(3, 10)))
DELTA_GRID = (Fraction(0), Fraction(1, 100), Fraction(1, 50), Fraction(3, 100), Fraction(1, 20))
N_GRID = (100, 250, 436, 500, 1000, 2000, 5000, 10000)
ALPHA_GRID = (
    ("0.05", Fraction(1, 20), "PRIMARY_ONE_SIDED"),
    ("0.05/9", Fraction(1, 180), "SUPPLEMENTARY_MULTIPLICITY_COST_ONLY"),
)
TARGET_POWERS = (("80_PERCENT", Fraction(4, 5)), ("90_PERCENT", Fraction(9, 10)))
DESIGN_EFFECTS = (1, 2, 4)
MAIN_SCENARIO = (Fraction(121, 436), Fraction(1, 50), Fraction(1, 20))
NOT_REACHED = "NOT_REACHED_IN_GRID"
# Float lgamma/exp rounding is ~1e-11 relative per term; 1e-9 absolute leaves margin.
NULL_TOLERANCE = 1e-9
BORDERLINE_TOLERANCE = 1e-9
TAIL_REL_EPS = 1e-17

Record = dict[str, object]


# --------------------------------------------------------------------------- model


def real(value: object, name: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, int | float | Fraction):
        raise ValueError(f"{name} must be an int, float or Fraction, got {value!r}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return Fraction(value)


def validate_n(n: object) -> int:
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError(f"N must be an integer >= 1, got {n!r}")
    return n


def validate_alpha(alpha: object) -> Fraction:
    value = real(alpha, "alpha")
    if not 0 < value < 1:
        raise ValueError(f"alpha must satisfy 0 < alpha < 1, got {alpha!r}")
    return value


def validate_pair(q: object, delta: object) -> tuple[Fraction, Fraction]:
    qq, dd = real(q, "q"), real(delta, "delta")
    if not 0 <= qq <= 1:
        raise ValueError(f"q must satisfy 0 <= q <= 1, got {q!r}")
    if abs(dd) > qq:
        raise ValueError(f"|delta| must not exceed q, got q={q!r}, delta={delta!r}")
    return qq, dd


def difference_distribution(q: object, delta: object) -> tuple[Fraction, Fraction, Fraction]:
    """(P(d=1), P(d=-1), P(d=0)) = ((q+delta)/2, (q-delta)/2, 1-q), checked exactly."""
    qq, dd = validate_pair(q, delta)
    probabilities = ((qq + dd) / 2, (qq - dd) / 2, 1 - qq)
    if any(not 0 <= p <= 1 for p in probabilities) or sum(probabilities) != 1:
        raise ValueError(f"illegal difference distribution for q={q!r}, delta={delta!r}")
    return probabilities


def win_probability(q: object, delta: object) -> Fraction | None:
    """theta = P(d=1 | d != 0) = (q+delta)/(2q); None when q = 0 (no discordant draw)."""
    p_plus, _, _ = difference_distribution(q, delta)
    qq, _ = validate_pair(q, delta)
    return None if qq == 0 else p_plus / qq


@lru_cache(maxsize=8)
def critical_values(m_max: int, alpha: Fraction) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """r(m) and the exact conditional size P[Binomial(m,1/2) >= r(m)] for m = 0..m_max.

    r(m) is the smallest r with P[Binomial(m,1/2) >= r] <= alpha, decided in exact
    integer arithmetic; r(m) = m + 1 means no attainable rejection (size 0).
    Uses r(m+1) in {r(m), r(m)+1} and S(m+1, r) = 2 S(m, r) + C(m, r-1), where
    S(m, r) = sum_{k >= r} C(m, k); `below` carries C(m, r(m) - 1) exactly.
    """
    if type(m_max) is not int or m_max < 0:
        raise ValueError(f"m_max must be an integer >= 0, got {m_max!r}")
    level = validate_alpha(alpha)
    num, den = level.numerator, level.denominator
    r, upper, below = 1, 0, 1  # m = 0: S(0, 0) = 1 > alpha; S(0, 1) = 0; C(0, 0) = 1
    thresholds, sizes = [r], [0.0]
    for m in range(m_max):
        upper = 2 * upper + below
        below = below * (m + 1) // (m + 2 - r)  # C(m+1, r-1)
        if upper * den > num << (m + 1):
            below = below * (m + 2 - r) // r  # C(m+1, r)
            upper -= below
            r += 1
        thresholds.append(r)
        sizes.append(upper / (1 << (m + 1)))
    return tuple(thresholds), tuple(sizes)


class Binomial:
    """Binomial(n, p) probabilities for one fixed exact p, evaluated in log space."""

    def __init__(self, p: Fraction) -> None:
        if not 0 <= p <= 1:
            raise ValueError(f"p must satisfy 0 <= p <= 1, got {p!r}")
        self.p = p
        self._log_p = math.log(p) if p > 0 else -math.inf
        self._log_q = math.log(1 - p) if p < 1 else -math.inf
        self._odds = float(p / (1 - p)) if 0 < p < 1 else math.inf

    def pmf(self, k: int, n: int) -> float:
        if k < 0 or k > n:
            return 0.0
        if self.p == 0:
            return 1.0 if k == 0 else 0.0
        if self.p == 1:
            return 1.0 if k == n else 0.0
        log_choose = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
        return math.exp(log_choose + k * self._log_p + (n - k) * self._log_q)

    def sf(self, k: int, n: int) -> float:
        """P[X >= k], summing the short side away from the mode.

        Past the mode the term ratio is below 1 and decreasing, so the unsummed
        remainder after term t with ratio rho is at most t * rho / (1 - rho);
        summation stops once that bound is below TAIL_REL_EPS of the running sum.
        """
        if k <= 0:
            return 1.0
        if k > n:
            return 0.0
        if self.p == 0:
            return 0.0
        if self.p == 1:
            return 1.0
        mode = math.floor((n + 1) * self.p)
        if k > mode:
            return min(self._upper_sum(k, n), 1.0)
        return min(max(1.0 - self._lower_sum(k - 1, n), 0.0), 1.0)

    def _upper_sum(self, k: int, n: int) -> float:
        term, total, j = self.pmf(k, n), 0.0, k
        while True:
            total += term
            if j == n:
                return total
            ratio = (n - j) / (j + 1) * self._odds
            if ratio < 1.0 and term * ratio / (1.0 - ratio) <= TAIL_REL_EPS * total:
                return total
            term *= ratio
            j += 1

    def _lower_sum(self, k: int, n: int) -> float:
        if k < 0:
            return 0.0
        term, total, j = self.pmf(k, n), 0.0, k
        while True:
            total += term
            if j == 0:
                return total
            ratio = j / (n - j + 1) / self._odds
            if ratio < 1.0 and term * ratio / (1.0 - ratio) <= TAIL_REL_EPS * total:
                return total
            term *= ratio
            j -= 1


@dataclass(frozen=True, slots=True)
class PowerResult:
    power: float
    raw_power: float
    discordance_mass: float


class PairedSignTestPower:
    """Exact one-sided sign-test power for fixed (q, delta, alpha), any N <= m_max.

    Reject in favour of the candidate when W >= r(M), W = candidate-only wins.
    """

    def __init__(self, q: object, delta: object, alpha: object, m_max: int) -> None:
        self.q, self.delta = validate_pair(q, delta)
        self.alpha = validate_alpha(alpha)
        self.m_max = validate_n(m_max)
        self.theta = win_probability(self.q, self.delta)
        self.critical, self.sizes = critical_values(self.m_max, self.alpha)
        self._discord = Binomial(self.q)
        self._win = None if self.theta is None else Binomial(self.theta)
        self._conditional: dict[int, float] = {}

    def conditional_rejection(self, m: int) -> float:
        """P[W >= r(m) | M = m] with W | M=m ~ Binomial(m, theta); 0 for m = 0."""
        if not 0 <= m <= self.m_max:
            raise ValueError(f"m must satisfy 0 <= m <= {self.m_max}, got {m!r}")
        if m == 0 or self._win is None:
            return 0.0
        cached = self._conditional.get(m)
        if cached is None:
            cached = self._win.sf(self.critical[m], m)
            self._conditional[m] = cached
        return cached

    def power(self, n: object) -> PowerResult:
        """sum_{m=0..N} P(M=m) P[Binomial(m,theta) >= r(m)], M ~ Binomial(N, q).

        Terms whose float P(M=m) underflows to 0.0 contribute nothing and are skipped.
        """
        size = validate_n(n)
        if size > self.m_max:
            raise ValueError(f"N={size} exceeds precomputed m_max={self.m_max}")
        raw, mass = 0.0, 0.0
        for m in range(size + 1):
            weight = self._discord.pmf(m, size)
            if weight == 0.0:
                continue
            mass += weight
            raw += weight * self.conditional_rejection(m)
        return PowerResult(min(max(raw, 0.0), 1.0), raw, mass)


def paired_power(n: object, q: object, delta: object, alpha: object) -> float:
    size = validate_n(n)
    return PairedSignTestPower(q, delta, alpha, size).power(size).power


# ------------------------------------------------------------------- grid summaries


def fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else str(value)


def grid_keys() -> list[tuple[str, int, str, int]]:
    """(q_label, delta index, alpha_label, N) for every fixed scenario."""
    return [
        (q_label, d_index, a_label, n)
        for a_label, _, _ in ALPHA_GRID
        for q_label, _ in Q_GRID
        for d_index in range(len(DELTA_GRID))
        for n in N_GRID
    ]


def first_grid_n(series: Sequence[tuple[int, float]], target: float) -> int | None:
    """First grid N whose power is >= target; no monotonicity is assumed."""
    for n, power in series:
        if power >= target:
            return n
    return None


def series_summary(series: Sequence[tuple[int, float]]) -> Record:
    powers = [p for _, p in series]
    targets: Record = {}
    for label, target in TARGET_POWERS:
        goal = float(target)
        first = first_grid_n(series, goal)
        if first is None:
            targets[label] = {
                "target_power": goal,
                "first_grid_n": NOT_REACHED,
                "design_effect_draws": {str(d): NOT_REACHED for d in DESIGN_EFFECTS},
            }
            continue
        index = [n for n, _ in series].index(first)
        targets[label] = {
            "target_power": goal,
            "first_grid_n": first,
            "power_at_first_grid_n": powers[index],
            "previous_grid_n": series[index - 1][0] if index else None,
            "power_at_previous_grid_n": powers[index - 1] if index else None,
            "all_later_grid_points_at_or_above_target": all(p >= goal for p in powers[index:]),
            "design_effect_draws": {str(d): d * first for d in DESIGN_EFFECTS},
        }
    borderline = [
        {"N": n, "power": p, "target_power": float(t)}
        for n, p in series
        for _, t in TARGET_POWERS
        if abs(p - float(t)) <= BORDERLINE_TOLERANCE
    ]
    return {
        "monotone_non_decreasing_in_grid": all(b >= a for a, b in pairwise(powers)),
        "targets": targets,
        "borderline_within_numerical_tolerance": borderline,
    }


def compute_grid() -> tuple[list[Record], list[Record], Record]:
    rows: list[Record] = []
    summaries: list[Record] = []
    worst_mass_error = 0.0
    critical_meta: Record = {}
    for a_label, alpha, role in ALPHA_GRID:
        critical, sizes = critical_values(max(N_GRID), alpha)
        critical_meta[a_label] = {
            "first_m_with_attainable_rejection": next(
                m for m, r in enumerate(critical) if r <= m and m > 0
            ),
            "max_exact_conditional_size": max(sizes),
            "alpha": float(alpha),
        }
        for q_label, q in Q_GRID:
            for delta in DELTA_GRID:
                calc = PairedSignTestPower(q, delta, alpha, max(N_GRID))
                p_plus, p_minus, p_zero = difference_distribution(q, delta)
                series: list[tuple[int, float]] = []
                for n in N_GRID:
                    result = calc.power(n)
                    worst_mass_error = max(worst_mass_error, abs(result.discordance_mass - 1.0))
                    if not 0.0 <= result.power <= 1.0:
                        raise AssertionError("power outside [0, 1]")
                    series.append((n, result.power))
                    rows.append(
                        {
                            "scenario_id": (
                                f"q={q_label}|delta={fraction_text(delta)}|N={n}|alpha={a_label}"
                            ),
                            "q_label": q_label,
                            "q_exact": fraction_text(q),
                            "q": float(q),
                            "delta_exact": fraction_text(delta),
                            "delta": float(delta),
                            "delta_pp": int(delta * 100),
                            "N": n,
                            "alpha_label": a_label,
                            "alpha_exact": fraction_text(alpha),
                            "alpha": float(alpha),
                            "alpha_role": role,
                            "p_d_plus_1": float(p_plus),
                            "p_d_minus_1": float(p_minus),
                            "p_d_0": float(p_zero),
                            "theta": None if calc.theta is None else float(calc.theta),
                            "expected_discordant_draws": float(n * q),
                            "power": result.power,
                            "raw_power_before_clamp": result.raw_power,
                            "discordance_mass": result.discordance_mass,
                        }
                    )
                summaries.append(
                    {
                        "q_label": q_label,
                        "delta_exact": fraction_text(delta),
                        "delta_pp": int(delta * 100),
                        "alpha_label": a_label,
                        "alpha_role": role,
                        "power_by_grid_n": {str(n): p for n, p in series},
                        **series_summary(series),
                    }
                )
    numerics: Record = {
        "max_abs_discordance_mass_error": worst_mass_error,
        "critical_values": critical_meta,
    }
    return rows, summaries, numerics


def check_grid(rows: Sequence[Record]) -> Record:
    ids = [str(r["scenario_id"]) for r in rows]
    expected = len(Q_GRID) * len(DELTA_GRID) * len(N_GRID) * len(ALPHA_GRID)
    keys = {(r["q_label"], r["delta_exact"], r["alpha_label"], r["N"]) for r in rows}
    wanted = {
        (q_label, fraction_text(DELTA_GRID[d]), a_label, n)
        for q_label, d, a_label, n in grid_keys()
    }
    powers = [cast(float, r["power"]) for r in rows]
    result: Record = {
        "expected_scenarios": expected,
        "scenario_count": len(rows),
        "unique_scenario_ids": len(set(ids)),
        "missing": sorted(map(str, wanted - keys)),
        "unexpected": sorted(map(str, keys - wanted)),
        "all_power_in_unit_interval": all(0.0 <= p <= 1.0 for p in powers),
    }
    if (
        len(rows) != expected
        or len(set(ids)) != expected
        or keys != wanted
        or not result["all_power_in_unit_interval"]
    ):
        raise AssertionError(f"incomplete scenario grid: {result}")
    return result


def null_size_check(rows: Sequence[Record]) -> list[Record]:
    checks: list[Record] = []
    for a_label, alpha, _ in ALPHA_GRID:
        for q_label, _ in Q_GRID:
            null = [
                r
                for r in rows
                if r["alpha_label"] == a_label and r["q_label"] == q_label and r["delta"] == 0.0
            ]
            worst = max(cast(float, r["power"]) for r in null)
            if worst > float(alpha) + NULL_TOLERANCE:
                raise AssertionError(f"null rejection {worst} exceeds alpha {a_label}")
            checks.append(
                {
                    "q_label": q_label,
                    "alpha_label": a_label,
                    "alpha": float(alpha),
                    "max_null_rejection_over_grid_n": worst,
                    "slack_alpha_minus_max": float(alpha) - worst,
                    "status": (
                        "CONSERVATIVE_DISCRETE_TEST"
                        if worst < float(alpha) - NULL_TOLERANCE
                        else "AT_ALPHA_WITHIN_NUMERICAL_TOLERANCE"
                    ),
                    "null_rejection_by_grid_n": {str(r["N"]): r["power"] for r in null},
                }
            )
    return checks


def main_conclusion(summaries: Sequence[Record], rows: Sequence[Record]) -> Record:
    q, delta, alpha = MAIN_SCENARIO
    label = next(lbl for lbl, value in Q_GRID if value == q)
    a_label = next(lbl for lbl, value, _ in ALPHA_GRID if value == alpha)
    summary = next(
        s
        for s in summaries
        if s["q_label"] == label
        and s["delta_exact"] == fraction_text(delta)
        and s["alpha_label"] == a_label
    )
    targets = cast(dict[str, dict[str, object]], summary["targets"])
    p436 = next(
        cast(float, r["power"])
        for r in rows
        if r["q_label"] == label
        and r["delta_exact"] == fraction_text(delta)
        and r["alpha_label"] == a_label
        and r["N"] == 436
    )

    def describe(key: str) -> str:
        target = targets[key]
        first = target["first_grid_n"]
        if first == NOT_REACHED:
            return f"{key}: {NOT_REACHED} (N<=10000)"
        return f"N={first} (power {cast(float, target['power_at_first_grid_n']):.1%})"

    t80, t90 = targets["80_PERCENT"], targets["90_PERCENT"]
    de80 = cast(dict[str, object], t80["design_effect_draws"])
    zh = (
        f"IID 規劃模型下 (q=121/436 僅為歷史規劃估計, 真實增益固定 +2 個百分點, 單尾 alpha=0.05): "
        f"N=436 期新資料的檢出力只有 {p436:.1%}; 網格中首個達 80% 的是 {describe('80_PERCENT')}, "
        f"首個達 90% 的是 {describe('90_PERCENT')}. 這是網格首個達標值, 不是全域精確最小樣本數; "
        f"若存在時間相依, 期數須再乘上未知設計效應 (80% 目標在設計效應 2/4 情境為 "
        f"{de80['2']}/{de80['4']} 期). 此計算不是 M2 有效的證據."
    )
    en = (
        f"Under the IID planning model (q=121/436 as a planning estimate, true gain +2pp, "
        f"one-sided alpha=0.05): power at N=436 new draws is {p436:.1%}; the first grid N "
        f"reaching 80% is {describe('80_PERCENT')} and reaching 90% is {describe('90_PERCENT')}. "
        f"First grid N is not a global exact minimum; time dependence would multiply the draws "
        f"by an unknown design effect. This is not evidence that M2 works."
    )
    return {
        "scenario": {"q_exact": "121/436", "delta": 0.02, "delta_pp": 2, "alpha": 0.05},
        "power_at_N_436": p436,
        "power_by_grid_n": summary["power_by_grid_n"],
        "first_grid_n_80_percent": t80["first_grid_n"],
        "first_grid_n_90_percent": t90["first_grid_n"],
        "design_effect_draws_80_percent": t80["design_effect_draws"],
        "design_effect_draws_90_percent": t90["design_effect_draws"],
        "zh": zh,
        "en": en,
    }


# ------------------------------------------------------------------ inputs & identity


@dataclass(frozen=True, slots=True)
class PairedCounts:
    paired_target_n: int
    candidate_success_n: int
    baseline_success_n: int
    b: int
    c: int
    both_success_n: int
    both_failure_n: int
    excluded_missing_outcome_pairs: int

    @property
    def q_observed(self) -> Fraction:
        return Fraction(self.b + self.c, self.paired_target_n)


def as_record(value: object, where: str) -> Record:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected a JSON object")
    return cast(Record, value)


def as_list(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{where}: expected a JSON array")
    return cast(list[object], value)


def load_json(path: Path) -> Record:
    return as_record(json.loads(path.read_text(encoding="utf-8")), str(path))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_paired_k5(per_draw: Path, target_draws: Sequence[str]) -> tuple[PairedCounts, Record]:
    """Extract only K=5 M0/M2 outcome flags; tickets and prize tiers are not re-scored."""
    found: dict[str, dict[str, tuple[bool, bool]]] = {CANDIDATE: {}, BASELINE: {}}
    lines = 0
    with per_draw.open(encoding="utf-8") as handle:
        for line in handle:
            lines += 1
            row = as_record(json.loads(line), f"{per_draw}:{lines}")
            model = row.get("model_id")
            if row.get("K") != K or not isinstance(model, str) or model not in found:
                continue
            draw = row.get("target_draw")
            if not isinstance(draw, str):
                raise ValueError(f"{per_draw}:{lines}: target_draw must be a string")
            if draw in found[model]:
                raise ValueError(f"duplicate {model} K{K} record for target {draw}")
            known = row.get("official_outcome") is not None
            prize = row.get("official_any_prize")
            if known and not isinstance(prize, bool):
                raise ValueError(f"{per_draw}:{lines}: official_any_prize must be boolean")
            found[model][draw] = (known, prize is True)
    expected = list(target_draws)
    if len(set(expected)) != len(expected):
        raise ValueError("duplicate target draws in study_spec")
    for model, records in found.items():
        if set(records) != set(expected):
            raise ValueError(f"{model} K{K} targets differ from study_spec targets")
    known_pairs = [
        (found[CANDIDATE][d][1], found[BASELINE][d][1])
        for d in expected
        if found[CANDIDATE][d][0] and found[BASELINE][d][0]
    ]
    b = sum(a and not z for a, z in known_pairs)
    c = sum(z and not a for a, z in known_pairs)
    both = sum(a and z for a, z in known_pairs)
    n = len(known_pairs)
    if n == 0:
        raise ValueError("no paired K5 targets with known outcomes")
    counts = PairedCounts(
        paired_target_n=n,
        candidate_success_n=sum(a for a, _ in known_pairs),
        baseline_success_n=sum(z for _, z in known_pairs),
        b=b,
        c=c,
        both_success_n=both,
        both_failure_n=n - b - c - both,
        excluded_missing_outcome_pairs=len(expected) - n,
    )
    extraction: Record = {
        "per_draw_lines_read": lines,
        "records_used": sum(len(v) for v in found.values()),
        "records_used_by_model": {m: len(v) for m, v in found.items()},
        "fields_used": ["K", "model_id", "target_draw", "official_outcome", "official_any_prize"],
        "tickets_regenerated": False,
        "prizes_rescored": False,
    }
    return counts, extraction


def git(*args: str) -> str:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True, env=env
    )
    return completed.stdout.strip()


def source_identity() -> Record:
    commit = git("rev-parse", "--verify", f"{SOURCE_COMMIT}^{{commit}}")
    if commit != SOURCE_COMMIT:
        raise ValueError(f"source commit resolves to {commit}, expected {SOURCE_COMMIT}")
    return {
        "commit": commit,
        "tree": git("rev-parse", "--verify", f"{SOURCE_COMMIT}^{{tree}}"),
        "object_type": git("cat-file", "-t", SOURCE_COMMIT),
        "subject": git("log", "-1", "--format=%s", SOURCE_COMMIT),
        "resolved_from": "git object database (rev-parse ^{commit} / ^{tree})",
        "main_freshness_claim": False,
    }


def candidate_identity() -> Record:
    blobs: Record = {}
    for rel in CANDIDATE_PATHS:
        try:
            blobs[rel] = git("rev-parse", "--verify", f"HEAD:{rel}")
        except subprocess.CalledProcessError:
            blobs[rel] = None
    candidate_status = git("status", "--porcelain", "--untracked-files=all", "--", *CANDIDATE_PATHS)
    return {
        "worktree": str(ROOT),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "worktree_status_porcelain": git("status", "--porcelain", "--untracked-files=all"),
        "candidate_paths_committed_and_clean": candidate_status == ""
        and all(v is not None for v in blobs.values()),
        "candidate_head_blobs": blobs,
        "candidate_file_sha256": {rel: sha256(ROOT / rel) for rel in CANDIDATE_PATHS},
        "python": sys.version,
        "executable": sys.executable,
    }


def comparison_entry(summary: Record) -> Record:
    matches = [
        as_record(c, "summary.comparisons[]")
        for c in as_list(summary.get("comparisons"), "summary.comparisons")
        if as_record(c, "summary.comparisons[]").get("K") == K
        and as_record(c, "summary.comparisons[]").get("candidate") == CANDIDATE
        and as_record(c, "summary.comparisons[]").get("baseline") == BASELINE
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one K{K} {CANDIDATE} vs {BASELINE} comparison")
    return matches[0]


def verify_inputs(artifact_root: Path) -> Record:
    paths = {name: artifact_root / name for name in REQUIRED_INPUTS}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"required source artifacts missing: {missing}")
    hashes = {name: sha256(p) for name, p in paths.items()}
    spec, summary, judge = (
        load_json(paths[n]) for n in ("study_spec.json", "summary.json", "judge.json")
    )
    source = source_identity()
    spec_source = as_record(spec.get("source"), "study_spec.source")
    identity_checks = {
        "summary.per_draw_hash == sha256(per_draw.jsonl)": summary.get("per_draw_hash")
        == hashes["per_draw.jsonl"],
        "summary.study_spec_hash == sha256(study_spec.json)": summary.get("study_spec_hash")
        == hashes["study_spec.json"],
        "study_spec.source.head == SOURCE_COMMIT": spec_source.get("head") == SOURCE_COMMIT,
        "study_spec.source.tree == git tree": spec_source.get("tree") == source["tree"],
        "judge.source_head == SOURCE_COMMIT": judge.get("source_head") == SOURCE_COMMIT,
        "judge.source_tree == git tree": judge.get("source_tree") == source["tree"],
        "task ids": spec.get("task_id")
        == summary.get("task_id")
        == judge.get("task_id")
        == SOURCE_TASK_ID,
    }
    if not all(identity_checks.values()):
        raise ValueError(f"fixed source identity mismatch: {identity_checks}")
    targets = [
        as_record(t, "study_spec.targets[]").get("draw")
        for t in as_list(spec.get("targets"), "study_spec.targets")
    ]
    if not all(isinstance(t, str) for t in targets):
        raise ValueError("study_spec target draws must be strings")
    counts, extraction = read_paired_k5(paths["per_draw.jsonl"], cast(list[str], targets))
    recomputed = asdict(counts)
    entry = comparison_entry(summary)
    summary_fields = {key: entry.get(key) for key in recomputed}
    return {
        "artifact_root": str(artifact_root),
        "inputs": [
            {"name": n, "path": str(p), "bytes": p.stat().st_size, "sha256": hashes[n]}
            for n, p in paths.items()
        ],
        "source": source,
        "identity_checks": identity_checks,
        "original_status": {
            key: summary.get(key)
            for key in (
                "IMPLEMENTATION_STATUS",
                "RESEARCH_RESULT",
                "EVIDENCE_CLASS",
                "ADOPTION_STATUS",
                "PRODUCTION_CHANGE",
            )
        }
        | {"judge_verdict": judge.get("verdict"), "judge_mode": judge.get("mode")},
        "extraction": extraction,
        "paired_counts": recomputed,
        "summary_comparison_fields": summary_fields,
        "matches_summary_comparison": summary_fields == recomputed,
        "owner_reported_values": REPORTED,
        "matches_owner_reported_values": all(recomputed[k] == v for k, v in REPORTED.items()),
        "q_observed_exact": fraction_text(counts.q_observed),
        "q_observed": float(counts.q_observed),
        "q_observed_equals_grid_value_121_436": counts.q_observed == Fraction(121, 436),
        "observed_difference": f"+{counts.b - counts.c}/{counts.paired_target_n}",
        "q_role": "historical planning estimate from one retrospective period; "
        "not a known constant for future draws",
        "observed_difference_role": "not treated as a true effect; no post-hoc observed power",
    }


# ------------------------------------------------------------------------- documents

ASSUMPTIONS = [
    "Paired per-draw differences d = Y(M2 K5) - Y(M0 K5) in {-1, 0, 1} are independent and "
    "identically distributed over the N future draws.",
    "q = P(d != 0) and delta = P(Y_M2 = 1) - P(Y_M0 = 1) are fixed over the observation period.",
    "One future draw is one paired observation; tickets per draw, bootstrap replicates and "
    "model counts are not additional independent draws.",
    "Results are numerical calculations under this IID model, not unconditional guarantees "
    "for the real adaptive strategies.",
]
FORMULAS = {
    "P(d=1)": "(q + delta) / 2",
    "P(d=-1)": "(q - delta) / 2",
    "P(d=0)": "1 - q",
    "M": "number of discordant draws; M ~ Binomial(N, q)",
    "W | M=m": "candidate-only wins; W | M=m ~ Binomial(m, theta), theta = (q + delta) / (2q)",
    "r(m)": "smallest r in {0..m+1} with P[Binomial(m, 1/2) >= r] <= alpha, decided in exact "
    "integer arithmetic; r(m) = m + 1 when no threshold is attainable",
    "m = 0": "rejection probability 0",
    "decision": "reject H0 (delta <= 0) for H1 (delta > 0, candidate better) when W >= r(M)",
    "Power(N, q, delta, alpha)": "sum_{m=0..N} P(M=m) * P[Binomial(m, theta) >= r(m)]",
}
DEPENDENCE_LIMITATIONS = [
    "Real strategy outcomes may be time-dependent; independence and stationarity are not proven.",
    "Design effects 1, 2 and 4 are assumed draw multipliers for data-cost sensitivity only; "
    "they are not estimated from data and do not give exact power under dependence.",
    "The historical block bootstrap was not re-run; absence of detected autocorrelation "
    "would not establish independence.",
    "Multiple tickets per draw, bootstrap replicates or model counts are never counted as "
    "new independent draws.",
]
BOUNDARIES = [
    "The observed +9/436 is not fixed as a true effect; no post-hoc observed power is computed.",
    "No claim of an increased true success rate and no new prospective sample: 0 new draws used.",
    "Historical q = 121/436 is a planning estimate, not a known future constant.",
    "N values are planning scenarios, not an Owner-committed collection plan; delta values are "
    "not an approved minimum commercial gain.",
    "N = 436 is only a sample-size scenario; the historical 436 draws are not reused as a test.",
    "alpha = 0.05/9 only prices the multiplicity threshold; neither alpha changes the historical "
    "verdict, and one future candidate cannot retroactively turn the nine historical "
    "comparisons into one.",
    "First grid N reaching a power target is not a global exact minimum sample size; "
    "finite-sample power of this discrete test is not assumed monotone in N.",
    "No conversion to calendar years.",
]
STATUS = {
    "EVIDENCE_CLASS": "PLANNING_CALCULATION_UNDER_STATED_IID_MODEL",
    "ADOPTION_STATUS": "NO_ADOPT",
    "PRODUCTION_CHANGE": "NONE",
    "HISTORICAL_STRATEGY_GENERATION": "NOT RUN",
    "NEW_REAL_DRAW_OBSERVATIONS": 0,
}


def grid_document() -> Record:
    return {
        "q": [{"label": lbl, "exact": fraction_text(v), "value": float(v)} for lbl, v in Q_GRID],
        "delta": [
            {"exact": fraction_text(d), "value": float(d), "pp": int(d * 100)} for d in DELTA_GRID
        ],
        "N": list(N_GRID),
        "alpha": [
            {"label": lbl, "exact": fraction_text(v), "value": float(v), "role": role}
            for lbl, v, role in ALPHA_GRID
        ],
        "scenario_count": len(grid_keys()),
        "target_powers": [float(t) for _, t in TARGET_POWERS],
        "design_effects": list(DESIGN_EFFECTS),
        "main_scenario": {"q_exact": "121/436", "delta": 0.02, "alpha": 0.05},
    }


def now() -> str:
    return datetime.now(UTC).isoformat()


def write_once(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def spec(output_root: Path, artifact_root: Path) -> Record:
    document: Record = {
        "task_id": TASK_ID,
        "artifact": "design_spec",
        "created_at": now(),
        "command": sys.argv,
        **STATUS,
        "comparison": {
            "candidate": f"{CANDIDATE} K{K}",
            "baseline": f"{BASELINE} K{K}",
            "future_fixed_pair_only": True,
            "single_future_candidate": True,
        },
        "source_inputs": verify_inputs(artifact_root),
        "candidate": candidate_identity(),
        "grid": grid_document(),
        "model": {"assumptions": ASSUMPTIONS, "formulas": FORMULAS},
        "not_used": "two independent-proportion formulas (they ignore same-draw pairing)",
        "first_grid_n_rule": "first N in ascending grid order with power >= target; "
        f"{NOT_REACHED} when none; later grid points are reported, not assumed",
        "numerics": {
            "critical_values": "exact Python integer arithmetic",
            "binomial_probabilities": "log-space lgamma pmf; tails summed from the short side "
            f"with a geometric remainder bound (relative {TAIL_REL_EPS})",
            "mixture": "all m with float P(M=m) > 0; terms underflowing to 0.0 contribute nothing",
            "null_tolerance": NULL_TOLERANCE,
            "null_tolerance_reason": "float lgamma/exp rounding (~1e-11 relative per term); "
            "the exact critical values already guarantee conditional size <= alpha",
        },
        "dependence_limitations": DEPENDENCE_LIMITATIONS,
        "boundaries": BOUNDARIES,
    }
    write_once(output_root / "design_spec.json", document)
    return document


def run(output_root: Path, artifact_root: Path) -> Record:
    spec_path = output_root / "design_spec.json"
    design = load_json(spec_path)
    if design.get("grid") != json.loads(json.dumps(grid_document())):
        raise ValueError("design_spec grid differs from the fixed code grid")
    recorded = {
        as_record(i, "inputs[]").get("name"): as_record(i, "inputs[]").get("sha256")
        for i in as_list(as_record(design.get("source_inputs"), "source_inputs").get("inputs"), "")
    }
    current = {name: sha256(artifact_root / name) for name in REQUIRED_INPUTS}
    if recorded != current:
        raise ValueError("source artifacts changed since design_spec was written")
    started = time.monotonic()
    rows, summaries, numerics = compute_grid()
    completeness = check_grid(rows)
    document: Record = {
        "task_id": TASK_ID,
        "artifact": "detectability_results",
        "created_at": now(),
        "command": sys.argv,
        **STATUS,
        "design_spec": {"path": str(spec_path), "sha256": sha256(spec_path)},
        "source_input_sha256": current,
        "candidate": candidate_identity(),
        "observed_b_c_q": as_record(design.get("source_inputs"), "source_inputs").get(
            "paired_counts"
        ),
        "scenario_count": len(rows),
        "completeness": completeness,
        "main_planning_conclusion": main_conclusion(summaries, rows),
        "first_grid_n_by_series": summaries,
        "null_size_check": null_size_check(rows),
        "numerics": numerics | {"compute_seconds": time.monotonic() - started},
        "dependence_limitations": DEPENDENCE_LIMITATIONS,
        "boundaries": BOUNDARIES,
        "scenarios": rows,
    }
    write_once(output_root / "detectability_results.json", document)
    return document


def capture(name: str, command: Sequence[str], output_root: Path) -> int:
    started, clock = now(), time.monotonic()
    completed = subprocess.run(list(command), cwd=ROOT, capture_output=True, text=True, check=False)
    write_once(
        output_root / "captures" / f"{name}.json",
        {
            "name": name,
            "argv": list(command),
            "cwd": str(ROOT),
            "started_at": started,
            "ended_at": now(),
            "seconds": time.monotonic() - clock,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "candidate": candidate_identity(),
        },
    )
    return completed.returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--artifact-root", type=Path, default=SOURCE_ARTIFACT_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("spec")
    commands.add_parser("run")
    capture_parser = commands.add_parser("capture")
    capture_parser.add_argument("name")
    capture_parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    output_root, artifact_root = cast(Path, args.output_root), cast(Path, args.artifact_root)
    command = cast(str, args.command)
    if command == "capture":
        child = list(cast(list[str], args.argv))
        if child[:1] == ["--"]:
            child = child[1:]
        if not child:
            parser.error("capture needs a command after --")
        code = capture(cast(str, args.name), child, output_root)
        print(json.dumps({"capture": args.name, "exit_code": code}))
        return code
    if command == "spec":
        document = spec(output_root, artifact_root)
        inputs = as_record(document["source_inputs"], "source_inputs")
        print(json.dumps({"design_spec": "written", "paired_counts": inputs["paired_counts"]}))
        return 0
    document = run(output_root, artifact_root)
    print(
        json.dumps(
            {
                "scenario_count": document["scenario_count"],
                "main": as_record(document["main_planning_conclusion"], "main")["en"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
