"""Model probability of the exact frozen A/D portfolios, with no replay or DB IO.

For each uniform six-subset W, integrate the remaining special number exactly:
43 winning specials if any ticket has >=3 main hits, otherwise the union of
non-W numbers on tickets with exactly two hits. Independent seeded draws within
each frozen target are shared by A/D and K10/K20. The estimand is the equally
weighted mean Q over ALL 1,761 saved target portfolios, not a future win rate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from statistics import NormalDist

import numpy as np

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT

TASK_ID = "B649_FROZEN_MIN_OVERLAP_SUCCESS_PROBABILITY_R1"
INPUT_COMMIT = "d7665ee5d00fac09fdc593908e81e54ae080f2ba"
INPUT_TREE = "5a9cbff94817c82163c32f1274f7c73d19bc8426"
INPUT_SHA256 = "af1291ad73b8e78665a7181f4403c243b245855b2d1ce24e64ee950d23294ec3"
INPUT_PATH = "docs/research/branch2-portfolio-geometry-four-arm-oos-r1-result.json"
EXPECTED_TARGETS = 1761
ARMS = ("RAW_MAJORITY", "MIN_OVERLAP")
KS = (10, 20)
METRICS = ("official_any_prize", "p_max_hits_ge_3", "p_max_hits_ge_4")
SAMPLES_PER_TARGET = 32768
ROOT_SEED = 649
MAX_SECONDS = 900
PRECISION_PP = 0.05
DELTA_ALPHA = 0.025  # Bonferroni: simultaneous >=95% for the two full-cohort deltas.
PRIZE_SHA256 = "976c977eee7475ea9b824ff6da2725308df6eef801ae8e257497bdec67ca4228"
FOUR_ARM_SHA256 = "2754cc9765e83df63ec11da2fc69665393fa5f804ca78bcc621c78c880b7d375"
FROZEN_MODULES = {
    "domain/lottery_rules.py": "622e19e926dd74c4145c1e1e70da4c0f13a895b2b17ae61b6545c4c70227aba2",
    "domain/prize_evaluation.py": PRIZE_SHA256,
    "research/b649_portfolio_geometry_four_arm_oos.py": FOUR_ARM_SHA256,
}


@dataclass(frozen=True)
class FrozenTarget:
    target_draw: str
    candidate_count: int
    portfolios: dict[int, tuple[tuple[tuple[int, ...], ...], ...]]


def mask(numbers: tuple[int, ...]) -> int:
    return sum(1 << (n - 1) for n in numbers)


def validate_contract() -> None:
    rule = BIG_LOTTO_RULE_CONTRACT
    assert rule.prize_rule is not None
    signatures = {(t.main_hits, t.special_hit) for t in rule.prize_rule.tiers}
    if (
        (
            rule.main_number_count,
            rule.main_number_min,
            rule.main_number_max,
            rule.special_number_count,
            rule.special_number_min,
            rule.special_number_max,
        )
        != (6, 1, 49, 1, 1, 49)
        or rule.main_special_overlap_allowed
        or signatures
        != {
            (6, False),
            (5, True),
            (5, False),
            (4, True),
            (4, False),
            (3, True),
            (3, False),
            (2, True),
        }
    ):
        raise ValueError("FROZEN_OFFICIAL_PRIZE_CONTRACT_MISMATCH")


def load_frozen(path: Path) -> tuple[FrozenTarget, ...]:
    """Validate the exact bytes; access saved tickets, never scores or producers."""
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise ValueError("FROZEN_ARTIFACT_IDENTITY_MISMATCH")
    data = json.loads(raw)
    rows = {k: data["by_k"][str(k)]["paired_draws"] for k in KS}
    ids = [r["target_draw"] for r in rows[10]]
    if len(ids) != EXPECTED_TARGETS or len(set(ids)) != EXPECTED_TARGETS:
        raise ValueError("INCOMPLETE_OR_DUPLICATED_FROZEN_TARGETS")
    if ids != [r["target_draw"] for r in rows[20]]:
        raise ValueError("K_TARGET_PAIRING_MISMATCH")
    targets = []
    for i, target_draw in enumerate(ids):
        candidate_count = rows[10][i]["candidate_count"]
        portfolios = {}
        for k in KS:
            row = rows[k][i]
            if row["k"] != k or row["candidate_count"] != candidate_count:
                raise ValueError("FROZEN_ROW_METADATA_MISMATCH")
            pair = tuple(tuple(tuple(t) for t in row["tickets"][arm]) for arm in ARMS)
            for tickets in pair:
                if len(tickets) != k or len(set(tickets)) != k:
                    raise ValueError("SAME_K_OR_DISTINCT_TICKETS_VIOLATION")
                for ticket in tickets:
                    if (
                        len(ticket) != 6
                        or tuple(sorted(set(ticket))) != ticket
                        or any(type(n) is not int or not 1 <= n <= 49 for n in ticket)
                    ):
                        raise ValueError("ILLEGAL_FROZEN_TICKET")
            if candidate_count == k and set(pair[0]) != set(pair[1]):
                raise ValueError("FORCED_SELECTION_PORTFOLIOS_DIFFER")
            portfolios[k] = pair
        targets.append(FrozenTarget(target_draw, candidate_count, portfolios))
    return tuple(targets)


def conditional_units(
    tickets: tuple[tuple[int, ...], ...], winning: tuple[int, ...], pool_size: int = 49
) -> tuple[int, int, int]:
    """Scalar exact reference: any-prize numerator, >=3 indicator, >=4 indicator."""
    w = mask(winning)
    hits = [(mask(t) & w).bit_count() for t in tickets]
    maximum = max(hits, default=0)
    if maximum >= 3:
        return pool_size - len(winning), 1, int(maximum >= 4)
    union = 0
    for ticket, hit in zip(tickets, hits, strict=True):
        if hit == 2:
            union |= mask(ticket) & ~w
    return union.bit_count(), 0, 0


def exact_small(tickets: tuple[tuple[int, ...], ...], pool_size: int) -> tuple[Fraction, ...]:
    """Bounded exact oracle only; production-sized enumeration is prohibited."""
    if not 7 <= pool_size <= 14:
        raise ValueError("EXACT_ORACLE_SMALL_DOMAIN_ONLY")
    if any(len(t) != 6 or len(set(t)) != 6 or min(t) < 1 or max(t) > pool_size for t in tickets):
        raise ValueError("INVALID_SMALL_DOMAIN_TICKET")
    totals = [0, 0, 0]
    for winning in combinations(range(1, pool_size + 1), 6):
        for i, value in enumerate(conditional_units(tickets, winning, pool_size)):
            totals[i] += value
    count = math.comb(pool_size, 6)
    return tuple(
        Fraction(v, count * (pool_size - 6 if i == 0 else 1)) for i, v in enumerate(totals)
    )


def target_seed(target_draw: str) -> int:
    text = f"{TASK_ID}|{ROOT_SEED}|{target_draw}"
    return int.from_bytes(hashlib.sha256(text.encode("ascii")).digest()[:16], "big")


def sample_main_masks(rng: np.random.Generator, count: int, pool_size: int = 49) -> np.ndarray:
    """IID uniform six-subsets: reject duplicates from IID discrete uniforms.

    Each accepted ordered six-tuple has equal probability; sorting gives every
    subset exactly 6! preimages. Rejected rows are replaced, never repaired.
    """
    if count < 1 or not 7 <= pool_size <= 49:
        raise ValueError("INVALID_SAMPLING_DOMAIN")
    values = np.sort(rng.integers(0, pool_size, size=(count, 6), dtype=np.uint64), axis=1)
    duplicates = np.any(values[:, 1:] == values[:, :-1], axis=1)
    while duplicates.any():
        values[duplicates] = np.sort(
            rng.integers(0, pool_size, size=(int(duplicates.sum()), 6), dtype=np.uint64),
            axis=1,
        )
        duplicates = np.any(values[:, 1:] == values[:, :-1], axis=1)
    return np.bitwise_or.reduce(np.left_shift(np.uint64(1), values), axis=1)


def score_masks(
    portfolios: tuple[tuple[tuple[int, ...], ...], ...], draws: np.ndarray, pool_size: int = 49
) -> tuple[np.ndarray, ...]:
    """Reuse main-hit counts across the four saved portfolios of one target."""
    unique = sorted({t for portfolio in portfolios for t in portfolio})
    indices = {t: i for i, t in enumerate(unique)}
    ticket_masks = np.asarray([mask(t) for t in unique], dtype=np.uint64)
    hits = np.bitwise_count(draws[:, None] & ticket_masks[None, :])
    outputs = []
    for portfolio in portfolios:
        selected = [indices[t] for t in portfolio]
        selected_hits = hits[:, selected]
        maximum = selected_hits.max(axis=1)
        remaining_union = (
            np.bitwise_or.reduce(
                np.where(selected_hits == 2, ticket_masks[selected], np.uint64(0)),
                axis=1,
            )
            & ~draws
        )
        official = np.where(maximum >= 3, pool_size - 6, np.bitwise_count(remaining_union))
        outputs.append(np.stack((official, maximum >= 3, maximum >= 4), axis=1))
    return tuple(outputs)


def pair_moments(a: np.ndarray, d: np.ndarray) -> dict[str, list[int]]:
    a, d = a.astype(np.int64), d.astype(np.int64)
    diff = d - a
    return {
        "sum_a": a.sum(axis=0).tolist(),
        "sum_d": d.sum(axis=0).tolist(),
        "sum_delta": diff.sum(axis=0).tolist(),
        "sumsq_a": (a * a).sum(axis=0).tolist(),
        "sumsq_d": (d * d).sum(axis=0).tolist(),
        "sumsq_delta": (diff * diff).sum(axis=0).tolist(),
    }


def summarize(rows: list[dict], k: int) -> dict:
    """Stratified MC error: sum within-target variances / (n * T^2).

    Between-target portfolio variation is part of the fixed estimand, not
    sampling uncertainty. No target bootstrap and no historical labels.
    """
    if not rows:
        return {"target_count": 0, "status": "NO_TARGETS"}
    n = SAMPLES_PER_TARGET
    metrics = {}
    same = all(row["by_k"][str(k)]["identical_ticket_sets"] for row in rows)
    for j, metric in enumerate(METRICS):
        scale = 43 if j == 0 else 1
        estimates = {}
        for name in ("a", "d", "delta"):
            moments = [row["by_k"][str(k)]["moments"] for row in rows]
            sums = [m[f"sum_{name}"][j] for m in moments]
            squares = [m[f"sumsq_{name}"][j] for m in moments]
            mean = sum(sums) / (len(rows) * n * scale)
            variance = sum(
                max(0.0, sq - s * s / n) / (n - 1) for s, sq in zip(sums, squares, strict=True)
            )
            se = math.sqrt(variance / (n * len(rows) ** 2)) / scale
            half = NormalDist().inv_cdf(0.975) * se
            estimates[name] = {
                "probability": mean,
                "mc_standard_error": se,
                "mc_normal_95_interval": [mean - half, mean + half],
            }
        delta = estimates["delta"]
        # Independent bounded delta samples lie in [-1, 1]; no variance estimate needed.
        bound = 0.0 if same else math.sqrt(2 * math.log(2 / DELTA_ALPHA) / (len(rows) * n))
        delta.update(
            {
                "percentage_points": 100 * delta["probability"],
                "hoeffding_97_5_interval": [
                    max(-1.0, delta["probability"] - bound),
                    min(1.0, delta["probability"] + bound),
                ],
                "hoeffding_halfwidth_pp": 100 * bound,
                "exact_zero_from_identical_portfolios": same,
            }
        )
        metrics[metric] = estimates
    return {
        "target_count": len(rows),
        "simulated_main_draws": len(rows) * n,
        "identical_ticket_set_targets": sum(
            row["by_k"][str(k)]["identical_ticket_sets"] for row in rows
        ),
        "metrics": metrics,
    }


def protocol() -> dict:
    return {
        "model": "UNIFORM_6_OF_49_WITHOUT_REPLACEMENT_SPECIAL_UNIFORM_REMAINING_43",
        "estimand": "EQUAL_WEIGHT_MEAN_Q_OF_ALL_FROZEN_ELIGIBLE_TARGET_PORTFOLIOS",
        "samples_per_target": SAMPLES_PER_TARGET,
        "root_seed": ROOT_SEED,
        "seed_derivation": "SHA256(task_id|root_seed|target_draw) first 128 bits big endian",
        "generator": "numpy.random.PCG64",
        "sample_method": "IID_REJECTION_OF_DUPLICATES",
        "special_number": "EXACT_CONDITIONAL_INTEGRATION_NOT_ADDITIONAL_MC_SAMPLES",
        "pairing": "SAME_W_FOR_A_D_AND_BOTH_K_WITHIN_TARGET; INDEPENDENT_TARGET_STREAMS",
        "full_cohort_delta_precision_halfwidth_pp": PRECISION_PP,
        "decision_interval": "HOEFFDING_97.5_EACH; SIMULTANEOUS_95_OVER_K10_K20",
        "subgroup_intervals": "DESCRIPTIVE; NO_SIMULTANEOUS_SUBGROUP_CLAIM",
        "max_seconds": MAX_SECONDS,
        "cpu_workers": 1,
        "stop_rule": "ONE_FIXED_BUDGET; NO_ADAPTIVE_SAMPLES_OR_SEEDS; INCOMPLETE_COHORT_UNRESOLVED",
        "primary_k": 10,
        "secondary_k": 20,
        "subgroups": "candidate_count=20,21,22",
        "prospective_draw_count_added": 0,
    }


def evaluate(targets: tuple[FrozenTarget, ...]) -> dict:
    validate_contract()
    seed_values = [target_seed(t.target_draw) for t in targets]
    if len(seed_values) != len(set(seed_values)):
        raise ValueError("TARGET_SEED_COLLISION")
    start = time.monotonic()
    rows = []
    for target, seed in zip(targets, seed_values, strict=True):
        if time.monotonic() - start >= MAX_SECONDS:
            break
        draws = sample_main_masks(np.random.Generator(np.random.PCG64(seed)), SAMPLES_PER_TARGET)
        portfolios = tuple(p for k in KS for p in target.portfolios[k])
        scores = score_masks(portfolios, draws)
        row = {
            "target_draw": target.target_draw,
            "candidate_count": target.candidate_count,
            "seed_decimal": str(seed),
            "samples": SAMPLES_PER_TARGET,
            "by_k": {},
        }
        for offset, k in enumerate(KS):
            a, d = target.portfolios[k]
            row["by_k"][str(k)] = {
                "identical_ticket_sets": set(a) == set(d),
                "moments": pair_moments(scores[2 * offset], scores[2 * offset + 1]),
            }
        rows.append(row)
        if len(rows) % 100 == 0:
            print(f"completed {len(rows)}/{len(targets)} frozen targets", flush=True)
    complete = len(rows) == len(targets) == EXPECTED_TARGETS
    by_k = {}
    for k in KS:
        full = summarize(rows, k)
        verdict = "INSUFFICIENT_PRECISION_INCOMPLETE_COHORT"
        if complete:
            delta = full["metrics"]["official_any_prize"]["delta"]
            lo, hi = delta["hoeffding_97_5_interval"]
            if delta["hoeffding_halfwidth_pp"] > PRECISION_PP:
                verdict = "INSUFFICIENT_PRECISION"
            elif lo > 0:
                verdict = "POSITIVE_MODEL_GEOMETRY_GAIN"
            elif hi <= 0:
                verdict = "NO_POSITIVE_MODEL_GEOMETRY_GAIN"
            else:
                verdict = "INSUFFICIENT_PRECISION_TO_RESOLVE_SIGN"
        by_k[str(k)] = {
            "role": "PRIMARY" if k == 10 else "SECONDARY",
            "full": full,
            "by_candidate_count": {
                str(c): summarize([row for row in rows if row["candidate_count"] == c], k)
                for c in (20, 21, 22)
            },
            "forced_selection": summarize([row for row in rows if row["candidate_count"] == k], k),
            "verdict": verdict,
        }
    return {
        "task": TASK_ID,
        "evidence_type": "MODEL_BASED_GEOMETRY_EVIDENCE",
        "protocol": protocol(),
        "complete_cohort": complete,
        "expected_target_count": EXPECTED_TARGETS,
        "evaluated_target_count": len(rows),
        "simulated_main_draw_samples": len(rows) * SAMPLES_PER_TARGET,
        "elapsed_seconds": time.monotonic() - start,
        "by_k": by_k,
        "per_target": rows,
        "limitations": [
            "CONDITIONAL_ON_THESE_FIXED_PORTFOLIOS_AND_FAIR_MODEL",
            "MC_INTERVALS_ARE_NUMERICAL_ERROR_NOT_FUTURE_OOS_UNCERTAINTY",
            "NO_PREDICTION_EDGE_PAYOUT_JACKPOT_OR_ADOPTION_CLAIM",
            "PROSPECTIVE_PROTOCOL_AND_VERDICT_UNCHANGED",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(INPUT_PATH))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("OUTPUT_EXISTS_REUSE_OR_INSPECT_NO_SILENT_RERUN")
    root = Path(__file__).resolve().parents[1]
    for relative, expected in FROZEN_MODULES.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise SystemExit(f"FROZEN_EVALUATOR_MISMATCH: {relative}")
    targets = load_frozen(args.input)
    frozen_protocol = json.dumps(protocol(), sort_keys=True, separators=(",", ":"))
    print("FROZEN_PROTOCOL " + frozen_protocol, flush=True)
    result = evaluate(targets)
    result["input"] = {
        "commit": INPUT_COMMIT,
        "tree": INPUT_TREE,
        "path": INPUT_PATH,
        "sha256": INPUT_SHA256,
        "frozen_evaluator_sha256": FROZEN_MODULES,
    }
    result["implementation_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["protocol_sha256"] = hashlib.sha256(frozen_protocol.encode()).hexdigest()
    result["numpy_version"] = np.__version__
    with args.output.open("x") as output:
        json.dump(result, output, sort_keys=True, separators=(",", ":"))
        output.write("\n")
    print(json.dumps({k: v["full"] for k, v in result["by_k"].items()}, sort_keys=True))


if __name__ == "__main__":
    main()
