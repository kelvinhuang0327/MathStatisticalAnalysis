"""Outcome-blind fixed K235 candidates and paired retrospective scoring.

The native adapters, ticket-quality gate and official prize contract retain
their original semantics. Binomial inversion follows the mathematical method
also used by the read-only R1 study; this is a new, independently identified run.
Only stdlib dependencies are needed. Scores rank numbers, not calibrated odds.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Callable, Sequence
from itertools import pairwise
from typing import Any

from lottolab.application.use_cases.generate_bet import instantiate_portfolio_adapter
from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import evaluate_big_lotto_ticket
from lottolab.research.b649_k235_output_quality import (
    FAIR_DRAW_EXACT_COVERAGE_FRACTIONS,
    evaluate_candidate_quality,
)
from lottolab.strategies.adapters.base import (
    BetAdapterError,
    CausalDrawRow,
    InsufficientHistory,
    PortfolioBetAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

Record = dict[str, Any]
Tickets = tuple[tuple[int, ...], ...]
Generator = Callable[[str, int, tuple[CausalDrawRow, ...]], Tickets]
K_VALUES = (2, 3, 5)
MODELS = ("M0", "M1", "M2", "M3")
BASELINES = {
    2: "b649_new_horizon_minimax_disagreement_r1",
    3: "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2",
    5: "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
}
MODEL_CONFIGS: Record = {
    "M0": {
        "strategies": BASELINES,
        "parameters": "native constructors, no overrides",
        "selection": "R1 frozen validation-selected identities; no reselection",
        "seed": "native causal-history seed protocol; no retries",
    },
    "M1": {"windows": [50, 300, 750], "weights": [0.5, 0.3, 0.2]},
    "M2": {
        "half_life_draws": 50,
        "alpha": 1 - 2 ** (-1 / 50),
        "max_history": 750,
        "initial_level": 6 / 49,
        "order": "oldest to newest",
    },
    "M3": {
        "max_history": 750,
        "prior_mean": 6 / 49,
        "prior_strength": 50,
        "states": "previous main-number presence; adjacent transitions only",
    },
}
ASSEMBLY = "descending score, ascending number ties; top 6K; rank round-robin; sort each ticket"
STATISTICS = {
    "family_size": 9,
    "alternative": "candidate greater than M0",
    "block_length": 20,
    "replicates": 10000,
    "seed": 20261020,
    "interval": "marginal two-sided 95% percentile circular block bootstrap",
}
LIMITATIONS = [
    "RETROSPECTIVE_EXPLORATORY; previously exposed period; no pristine holdout.",
    "Current imported history has dates, not historical availability/revision timestamps; "
    "strict earlier-date AND earlier-period prefixes are conservative, not historical-as-of proof.",
    "M0 and candidates use different assembly rules: effects concern complete methods, "
    "not causal contributions of individual features; scores are not calibrated probabilities.",
    "Exact paired binomial diagnosis assumes independent paired observations and equal "
    "discordance probabilities under the null; adaptive time sequences need not satisfy it.",
    "Circular block bootstrap is approximate, assumes sufficient stationarity and sample size; "
    "fixed 20-draw blocks; marginal 95% intervals are not nine simultaneous intervals.",
    "Fair-baseline binomial diagnosis assumes independent draws, identical conditional fair "
    "success probability and outcome-blind qualified portfolios; supplementary only.",
    "Bonferroni covers only this fixed family of nine, not all previous project exploration.",
    "No supported lift is not proof that every strategy is ineffective; NO_ADOPT throughout.",
]


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def model_hash(model: str) -> str:
    return digest(
        {"model": MODEL_CONFIGS[model], "assembly": "native" if model == "M0" else ASSEMBLY}
    )


def causal_history(snapshot: Sequence[Record], target: Record) -> tuple[CausalDrawRow, ...]:
    """No outcome/special number is carried across the generation boundary."""
    return tuple(
        CausalDrawRow(r["draw"], r["date"], tuple(r["numbers"]))
        for r in snapshot
        if int(r["draw"]) < int(target["draw"]) and r["date"] < target["date"]
    )


def effective_windows(model: str, k: int, n: int) -> Record:
    if model == "M0":
        windows = {2: (30, 120, n), 3: (50,), 5: (500, 100)}[k]
        return {str(w): min(w, n) for w in windows}
    if model == "M1":
        return {str(w): min(w, n) for w in (50, 300, 750)}
    return {"draws": min(750, n), "transitions": max(0, min(750, n) - 1) if model == "M3" else 0}


def scores(model: str, history: tuple[CausalDrawRow, ...]) -> tuple[float, ...]:
    if not history:
        raise InsufficientHistory("UNAVAILABLE: no causal history")
    if model == "M1":
        counts = [Counter(j for row in history[-w:] for j in row.numbers) for w in (50, 300, 750)]
        return tuple(
            sum(
                weight * count[j] / min(w, len(history))
                for w, weight, count in zip((50, 300, 750), (0.5, 0.3, 0.2), counts, strict=True)
            )
            for j in range(1, 50)
        )
    recent = history[-750:]
    if model == "M2":
        alpha = 1 - 2 ** (-1 / 50)
        levels = [6 / 49] * 49
        for row in recent:
            present = set(row.numbers)
            levels = [alpha * int(j in present) + (1 - alpha) * levels[j - 1] for j in range(1, 50)]
        return tuple(levels)
    if model == "M3":
        states = [set(row.numbers) for row in recent]
        result: list[float] = []
        for j in range(1, 50):
            a = j in states[-1]
            transitions = [(j in nxt) for prev, nxt in pairwise(states) if (j in prev) == a]
            result.append((sum(transitions) + 50 * (6 / 49)) / (len(transitions) + 50))
        return tuple(result)
    raise ValueError(f"Unknown scored model: {model}")


def assemble(values: Sequence[float], k: int) -> Tickets:
    if k not in K_VALUES or len(values) != 49 or not all(map(math.isfinite, values)):
        raise ValueError("Expected 49 finite scores and K2/K3/K5")
    ordered = sorted(range(1, 50), key=lambda j: (-values[j - 1], j))[: 6 * k]
    tickets = tuple(tuple(sorted(ordered[i::k])) for i in range(k))
    if not evaluate_candidate_quality(tickets, k).is_valid:
        raise ValueError("Invalid assembled portfolio")
    return tickets


def native_adapters() -> dict[int, PortfolioBetAdapter]:
    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    adapters: dict[int, PortfolioBetAdapter] = {}
    for k, sid in BASELINES.items():
        adapter = instantiate_portfolio_adapter(sid, registry.load_adapter(sid))
        descriptor = catalog.get(sid)
        if (adapter.native_ticket_count, adapter.strategy_version, adapter.min_history) != (
            k,
            descriptor.version,
            descriptor.min_history,
        ):
            raise ValueError("Native adapter identity mismatch")
        adapters[k] = adapter
    return adapters


def generator(adapters: dict[int, PortfolioBetAdapter]) -> Generator:
    def generate(model: str, k: int, history: tuple[CausalDrawRow, ...]) -> Tickets:
        if model == "M0":
            return tuple(
                e.emitted_main_numbers
                for e in adapters[k].get_bets_with_emission(history, LotteryType.BIG_LOTTO)
            )
        return assemble(scores(model, history), k)

    return generate


def score_tickets(tickets: Tickets, outcome: Record) -> tuple[list[Record], bool]:
    evaluations = [
        evaluate_big_lotto_ticket(
            predicted_main_numbers=t,
            predicted_special_number=None,
            winning_main_numbers=tuple(outcome["numbers"]),
            winning_special_number=outcome["special"],
        )
        for t in tickets
    ]
    return [e.canonical_dict() for e in evaluations], any(e.is_winner for e in evaluations)


def observation(
    snapshot: Sequence[Record],
    target: Record,
    model: str,
    k: int,
    snapshot_hash: str,
    generate: Generator,
) -> Record:
    history = causal_history(snapshot, target)
    tickets: Tickets = ()
    status, reason = "OK", ""
    try:
        tickets = generate(model, k, history)
    except InsufficientHistory as error:
        status, reason = "UNAVAILABLE", str(error)
    except BetAdapterError as error:
        status, reason = "STRATEGY_REJECTED", f"{type(error).__name__}: {error}"
    except Exception as error:
        status, reason = "TECHNICAL_FAILURE", f"{type(error).__name__}: {error}"
    quality = evaluate_candidate_quality(tickets, k).canonical_dict()
    if status == "OK" and not quality["is_valid"]:
        status, reason = "INVALID_TICKETS", "; ".join(quality["rejection_reasons"])
    outcome = next((r for r in snapshot if r["draw"] == target["draw"]), None)
    evaluations, success = None, None
    if outcome is not None and status == "OK":
        evaluations, success = score_tickets(tickets, outcome)
    return {
        "study_spec_id": "B649_K235_SHARED_EVAL_FIRST_BATCH_R1",
        "target_draw": target["draw"],
        "target_date": target["date"],
        "model_id": model,
        "model_config_hash": model_hash(model),
        "K": k,
        "planned_ticket_count": k,
        "actual_history_cutoff": {"draw": history[-1].draw, "date": history[-1].date}
        if history
        else None,
        "history_length": len(history),
        "effective_window_lengths": effective_windows(model, k, len(history)),
        "input_snapshot_hash": snapshot_hash,
        "generated_tickets": tickets,
        "ticket_quality": quality,
        "generation_status": status,
        "execution_status": "MISSING_OUTCOME" if outcome is None else status,
        "official_outcome": None
        if outcome is None
        else {"numbers": outcome["numbers"], "special": outcome["special"]},
        "ticket_evaluations": evaluations,
        "official_any_prize": success,
        "failure_reason": reason or ("No official outcome" if outcome is None else ""),
    }


def binomial_tail(wins: int, n: int, p: float) -> float:
    if not 0 <= wins <= n or not 0 <= p <= 1:
        raise ValueError("Invalid binomial arguments")
    if wins == 0:
        return 1.0
    if p == 0:
        return 0.0
    if p == 1:
        return 1.0
    logs = [
        math.lgamma(n + 1)
        - math.lgamma(j + 1)
        - math.lgamma(n - j + 1)
        + j * math.log(p)
        + (n - j) * math.log1p(-p)
        for j in range(wins, n + 1)
    ]
    largest = max(logs)
    return min(1.0, math.exp(largest) * math.fsum(math.exp(v - largest) for v in logs))


def exact_ci(wins: int, n: int) -> list[float] | None:
    if n == 0:
        return None

    def inverse(s: int, probability: float) -> float:
        low, high = 0.0, 1.0
        for _ in range(55):
            mid = (low + high) / 2
            if binomial_tail(s, n, mid) < probability:
                low = mid
            else:
                high = mid
        return (low + high) / 2

    return [
        0.0 if wins == 0 else inverse(wins, 0.025),
        1.0 if wins == n else inverse(wins + 1, 0.975),
    ]


def circular_interval(
    differences: Sequence[int],
    *,
    block_length: int = 20,
    replicates: int = 10000,
    seed: int = 20261020,
) -> Record:
    n = len(differences)
    if not n:
        return {"ci95_pp": None, "degeneracy": ["NO_PAIRS"]}
    if block_length <= 0 or replicates < 2:
        raise ValueError("Invalid bootstrap settings")
    full, remainder = divmod(n, block_length)
    block_sums = [
        sum(differences[(start + j) % n] for j in range(block_length)) for start in range(n)
    ]
    tails = [sum(differences[(start + j) % n] for j in range(remainder)) for start in range(n)]
    rng = random.Random(seed)
    means = sorted(
        100
        * (
            sum(block_sums[rng.randrange(n)] for _ in range(full))
            + (tails[rng.randrange(n)] if remainder else 0)
        )
        / n
        for _ in range(replicates)
    )

    def quantile(p: float) -> float:
        position = (replicates - 1) * p
        left = int(position)
        return means[left] + (position - left) * (
            means[min(left + 1, replicates - 1)] - means[left]
        )

    flags: list[str] = []
    if all(d == 0 for d in differences):
        flags.append("ALL_ZERO_DIFFERENCES_NOT_PROOF_OF_NO_UNCERTAINTY")
    elif len(set(differences)) == 1:
        flags.append("CONSTANT_DIFFERENCES")
    if full < 2:
        flags.append("FEWER_THAN_TWO_FULL_BLOCKS")
    return {
        "ci95_pp": [quantile(0.025), quantile(0.975)],
        "degeneracy": flags,
        "full_blocks_per_sample": full,
        "remainder_draws": remainder,
        "block_length": block_length,
        "replicates": replicates,
        "seed": seed,
        "index_rule": "uniform circular starts; concatenate blocks, truncate to n; "
        "same sampled indices applied to paired difference",
    }


def paired(candidate: Sequence[Record], baseline: Sequence[Record]) -> Record:
    if [r["target_draw"] for r in candidate] != [r["target_draw"] for r in baseline]:
        raise ValueError("Mismatched paired target order")
    pairs = [
        (a, z)
        for a, z in zip(candidate, baseline, strict=True)
        if a["official_outcome"] is not None and z["official_outcome"] is not None
    ]
    a = [int(x["official_any_prize"] is True) for x, _ in pairs]
    z = [int(x["official_any_prize"] is True) for _, x in pairs]
    b = sum(x == 1 and y == 0 for x, y in zip(a, z, strict=True))
    c = sum(x == 0 and y == 1 for x, y in zip(a, z, strict=True))
    both = sum(x == y == 1 for x, y in zip(a, z, strict=True))
    p = binomial_tail(b, b + c, 0.5)
    n = len(pairs)
    return {
        "paired_target_n": n,
        "excluded_missing_outcome_pairs": len(candidate) - n,
        "candidate_success_n": sum(a),
        "baseline_success_n": sum(z),
        "both_success_n": both,
        "both_failure_n": n - both - b - c,
        "b": b,
        "c": c,
        "delta_pp": 100 * (b - c) / n if n else None,
        "p_pair": p,
        "p_adjusted": min(1.0, 9 * p),
        "candidate_delivery_failure_n": sum(x["generation_status"] != "OK" for x, _ in pairs),
        "baseline_delivery_failure_n": sum(x["generation_status"] != "OK" for _, x in pairs),
        "bootstrap": circular_interval([x - y for x, y in zip(a, z, strict=True)]),
    }


def summarize(records: Sequence[Record], targets: Sequence[Record]) -> Record:
    expected = {(t["draw"], m, k) for t in targets for m in MODELS for k in K_VALUES}
    actual = [(r["target_draw"], r["model_id"], r["K"]) for r in records]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Missing, duplicate or unexpected target/model/K records")
    groups = {
        (m, k): sorted(
            [r for r in records if r["model_id"] == m and r["K"] == k],
            key=lambda r: (r["target_date"], int(r["target_draw"])),
        )
        for m in MODELS
        for k in K_VALUES
    }
    metrics: Record = {}
    for (m, k), rows in groups.items():
        known = [r for r in rows if r["official_outcome"] is not None]
        qualified = [
            r for r in known if r["generation_status"] == "OK" and r["ticket_quality"]["is_valid"]
        ]
        wins = sum(r["official_any_prize"] is True for r in qualified)
        numerator, denominator = FAIR_DRAW_EXACT_COVERAGE_FRACTIONS[k]
        n = len(qualified)
        failures = Counter(r["generation_status"] for r in rows if r["generation_status"] != "OK")
        missing = len(rows) - len(known)
        metrics[f"{m}_K{k}"] = {
            "target_n": len(rows),
            "known_outcome_n": len(known),
            "qualified_known_n": n,
            "success_n": wins,
            "usable_rate": wins / len(known) if known else None,
            "qualified_rate": wins / n if n else None,
            "failure_counts": dict(failures),
            "technical_failure_n": failures["TECHNICAL_FAILURE"],
            "technical_failure_rate": failures["TECHNICAL_FAILURE"] / len(rows),
            "invalid_ticket_n": failures["INVALID_TICKETS"],
            "invalid_ticket_rate": failures["INVALID_TICKETS"] / len(rows),
            "delivery_failure_n": sum(failures.values()),
            "delivery_failure_rate": sum(failures.values()) / len(rows),
            "missing_outcome_n": missing,
            "missing_outcome_rate": missing / len(rows),
            "fair_baseline": {
                "numerator": numerator,
                "denominator": denominator,
                "probability": numerator / denominator,
                "applies_to": "qualified portfolios with known outcomes only",
                "delta_pp": 100 * (wins / n - numerator / denominator) if n else None,
                "ci95_clopper_pearson": exact_ci(wins, n),
                "p_one_sided": binomial_tail(wins, n, numerator / denominator) if n else None,
            },
        }
    comparisons: list[Record] = []
    for m in MODELS[1:]:
        for k in K_VALUES:
            comparison = paired(groups[m, k], groups["M0", k])
            comparison.update({"candidate": m, "baseline": "M0", "K": k})
            comparisons.append(comparison)
    signals = [
        c
        for c in comparisons
        if c["delta_pp"] is not None
        and c["delta_pp"] > 0
        and c["p_adjusted"] < 0.05
        and c["bootstrap"]["ci95_pp"][0] > 0
        and not c["bootstrap"]["degeneracy"]
    ]
    research = (
        "INSUFFICIENT_DATA"
        if any(c["paired_target_n"] < 40 for c in comparisons)
        else "RETROSPECTIVE_SIGNAL"
        if signals
        else "NO_SUPPORTED_LIFT"
    )
    return {
        "record_n": len(records),
        "target_n": len(targets),
        "metrics": metrics,
        "comparisons": comparisons,
        "RESEARCH_RESULT": research,
        "signal_rule": "positive delta, adjusted paired p<0.05, block CI lower>0, "
        "no bootstrap degeneracy; fewer than 40 pairs is insufficient",
        "EVIDENCE_CLASS": "RETROSPECTIVE_EXPLORATORY",
        "ADOPTION_STATUS": "NO_ADOPT",
        "PRODUCTION_CHANGE": "NONE",
        "limitations": LIMITATIONS,
    }


def verify_records(
    snapshot: Sequence[Record],
    targets: Sequence[Record],
    records: Sequence[Record],
    snapshot_hash: str,
) -> Record:
    """Recompute quality, outcome, prizes and summaries WITHOUT any generator."""
    by_draw = {r["draw"]: r for r in snapshot}
    by_target = {r["draw"]: r for r in targets}
    for r in records:
        target = by_target[r["target_draw"]]
        history = causal_history(snapshot, target)
        cutoff = {"draw": history[-1].draw, "date": history[-1].date} if history else None
        if (
            r["input_snapshot_hash"] != snapshot_hash
            or r["model_config_hash"] != model_hash(r["model_id"])
            or r["actual_history_cutoff"] != cutoff
            or r["history_length"] != len(history)
            or r["effective_window_lengths"]
            != effective_windows(r["model_id"], r["K"], len(history))
            or r["planned_ticket_count"] != r["K"]
            or r["target_date"] != target["date"]
        ):
            raise ValueError("Input/config/history identity mismatch")
        quality = evaluate_candidate_quality(r["generated_tickets"], r["K"]).canonical_dict()
        if quality != r["ticket_quality"]:
            raise ValueError("Ticket quality mismatch")
        status = r["generation_status"]
        if status not in {
            "OK",
            "TECHNICAL_FAILURE",
            "UNAVAILABLE",
            "STRATEGY_REJECTED",
            "INVALID_TICKETS",
        } or (status == "OK" and not quality["is_valid"]):
            raise ValueError("Inconsistent generation status")
        if status != "OK" and not r["failure_reason"]:
            raise ValueError("Failure must retain a reason")
        outcome = by_draw.get(r["target_draw"])
        official = (
            None
            if outcome is None
            else {"numbers": outcome["numbers"], "special": outcome["special"]}
        )
        if r["official_outcome"] != official or r["execution_status"] != (
            "MISSING_OUTCOME" if outcome is None else status
        ):
            raise ValueError("Official outcome/status mismatch")
        evaluations, success = None, None
        if outcome is not None and status == "OK":
            tickets = tuple(tuple(t) for t in r["generated_tickets"])
            evaluations, success = score_tickets(tickets, outcome)
        if evaluations != r["ticket_evaluations"] or success != r["official_any_prize"]:
            raise ValueError("Official scoring mismatch")
    return summarize(records, targets)
