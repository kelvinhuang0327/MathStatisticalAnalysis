"""Focused prospective BIG_LOTTO edge evaluator unit tests (Python 3.9).

Pure synthetic fixtures only: no real predictions or outcomes, no TSA request,
no history replay. Covers exact baselines, per-draw adaptive baselines, the
e-process identities, experiment identity binding, and provenance fail-closed.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import inspect
import itertools
import json
import sys
import unittest
from fractions import Fraction
from math import comb
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "tools" / "evaluate_biglotto_prospective_edge_r1.py"
SPEC = importlib.util.spec_from_file_location("prospective_edge_r1_under_test", SOURCE)
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)

DENOMINATOR = 13983816
DISJOINT_2 = [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]
DISJOINT_5 = [
    [1, 2, 3, 4, 5, 6],
    [7, 8, 9, 10, 11, 12],
    [13, 14, 15, 16, 17, 18],
    [19, 20, 21, 22, 23, 24],
    [25, 26, 27, 28, 29, 30],
]
SHARED_CORE_5 = [
    [1, 2, 3, 4, 5, 6],
    [1, 2, 3, 7, 8, 9],
    [1, 2, 3, 10, 11, 12],
    [1, 2, 3, 13, 14, 15],
    [1, 2, 3, 16, 17, 18],
]
DISJOINT_WEIGHTS = [27132, 5093064, 7564500, 1230100, 67725, 1290, 5]
SHARED_CORE_WEIGHTS = [736281, 7299756, 4917834, 964705, 63945, 1290, 5]
P_DISJOINT = Fraction(1299120, DENOMINATOR)
P_SHARED_CORE = Fraction(1029945, DENOMINATOR)
HIT_NUMBERS = [1, 2, 3, 40, 41, 42]  # the first ticket of every fixture has 3 hits
MISS_NUMBERS = [1, 2, 40, 41, 42, 43]  # every ticket of every fixture has <= 2 hits

EXPERIMENT_ID = "SYNTHETIC_EDGE_EVALUATOR_R1"
STRATEGY = "synthetic-edge-strategy@version:1"
DRAWS = [f"1990000{n:02d}" for n in range(1, 17)]


def make_contract(draws=None, ticket_count=5, **overrides):
    contract = {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "STRATEGY_IDENTITY": STRATEGY,
        "TICKET_COUNT": ticket_count,
        "EXPECTED_DRAW_IDS": list(DRAWS[:2] if draws is None else draws),
        "DRAW_MODEL": "FAIR_6_OF_49",
        "NUMBER_POOL": 49,
        "DRAW_SIZE": 6,
        "OUTCOME_DENOMINATOR": DENOMINATOR,
        "PRIMARY_SUCCESS_EVENT": "MAX_HITS>=3",
        "PRIMARY_STATISTIC": "LIKELIHOOD_RATIO_E_PROCESS",
        "ALTERNATIVE_MULTIPLIER": "3/2",
        "ALPHA": "1/20",
        "EVIDENCE_THRESHOLD": 20,
    }
    contract.update(overrides)
    return contract


def pinned(contract):
    """Independent canonical-JSON SHA-256, matching the existing verifier's definition."""
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_record(contract, index, tickets, official, **overrides):
    draw = contract["EXPECTED_DRAW_IDS"][index]
    day = index + 1
    record = {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "DRAW_ID": draw,
        "TICKET_COUNT": len(tickets),
        "PREDICTED_TICKETS": copy.deepcopy(tickets),
        "STRATEGY_IDENTITY": STRATEGY,
        "INPUT_SNAPSHOT_SHA256": "c" * 64,
        "EXPERIMENT_CONTRACT_SHA256": pinned(contract),
        "RFC3161_EVIDENCE_REFERENCE": "synthetic://unverified-rfc3161/" + draw,
        "OFFICIAL_RESULT_REFERENCE": "synthetic://not-an-official-result/" + draw,
        "SIX_OFFICIAL_MAIN_NUMBERS": list(official),
        "INPUT_CUTOFF": f"2098-01-{day:02d}T00:00:00+08:00",
        "PREDICTION_CAPTURE_ID": "synthetic-capture-" + draw,
        "PREDICTION_CAPTURE_TIME": f"2098-01-{day:02d}T12:00:00+08:00",
        "DRAW_TIME": f"2098-01-{day:02d}T20:30:00+08:00",
    }
    record.update(overrides)
    return record


def make_records(contract, portfolios, outcomes):
    return [
        make_record(contract, i, tickets, HIT_NUMBERS if outcomes[i] else MISS_NUMBERS)
        for i, tickets in enumerate(portfolios)
    ]


def run(contract, records, **overrides):
    params = {
        "experiment_contract": contract,
        "expected_contract_sha256": pinned(contract),
        "experiment_id": contract["EXPERIMENT_ID"],
        "strategy_identity": contract["STRATEGY_IDENTITY"],
        "expected_draw_ids": list(contract["EXPECTED_DRAW_IDS"]),
        "ticket_count": contract["TICKET_COUNT"],
    }
    params.update(overrides)
    return evaluator.evaluate_biglotto_prospective_edge(records, **params)


def independent_max_hit_weights(tickets):
    """Exact MAX_HITS weights by counting draws per ticket-membership class (no scorer code)."""
    sizes = {}
    for number in range(1, 50):
        key = tuple(number in ticket for ticket in tickets)
        sizes[key] = sizes.get(key, 0) + 1
    keys = list(sizes)
    weights = [0] * 7

    def walk(index, left, chosen):
        if index == len(keys):
            if left == 0:
                weight, hits = 1, [0] * len(tickets)
                for position, count in enumerate(chosen):
                    key = keys[position]
                    weight *= comb(sizes[key], count)
                    for j, member in enumerate(key):
                        hits[j] += count if member else 0
                weights[max(hits)] += weight
            return
        for count in range(min(left, sizes[keys[index]]) + 1):
            walk(index + 1, left - count, [*chosen, count])

    walk(0, 6, [])
    return weights


def failure_factor(success_weight):
    """(1 - q) / (1 - p) with p = W / D and q = 3W / (2D), written independently."""
    return Fraction(2 * DENOMINATOR - 3 * success_weight, 2 * (DENOMINATOR - success_weight))


class ExactBaselineTests(unittest.TestCase):
    """AC1: exact original fair baselines from the existing K235 scorer."""

    def test_disjoint_five_ticket_baseline(self):
        self.assertEqual(independent_max_hit_weights(DISJOINT_5), DISJOINT_WEIGHTS)
        self.assertEqual(evaluator.exact_success_probability(DISJOINT_5), P_DISJOINT)
        contract = make_contract(DRAWS[:1])
        row = run(contract, make_records(contract, [DISJOINT_5], [0]))["PER_DRAW"][0]
        self.assertEqual(row["MAX_HIT_WEIGHTS"], DISJOINT_WEIGHTS)
        self.assertEqual(row["SUCCESS_WEIGHT"], 1299120)
        self.assertEqual(Fraction(row["P_SUCCESS"]), P_DISJOINT)

    def test_shared_three_number_core_baseline(self):
        self.assertEqual(independent_max_hit_weights(SHARED_CORE_5), SHARED_CORE_WEIGHTS)
        self.assertEqual(evaluator.exact_success_probability(SHARED_CORE_5), P_SHARED_CORE)
        contract = make_contract(DRAWS[:1])
        row = run(contract, make_records(contract, [SHARED_CORE_5], [0]))["PER_DRAW"][0]
        self.assertEqual(row["MAX_HIT_WEIGHTS"], SHARED_CORE_WEIGHTS)
        self.assertEqual(row["SUCCESS_WEIGHT"], 1029945)
        self.assertEqual(Fraction(row["P_SUCCESS"]), P_SHARED_CORE)

    def test_two_ticket_contract_uses_its_own_exact_baseline(self):
        weights = independent_max_hit_weights(DISJOINT_2)
        contract = make_contract(DRAWS[:1], ticket_count=2)
        row = run(contract, make_records(contract, [DISJOINT_2], [1]))["PER_DRAW"][0]
        self.assertEqual(row["MAX_HIT_WEIGHTS"], weights)
        self.assertEqual(Fraction(row["P_SUCCESS"]), Fraction(sum(weights[3:]), DENOMINATOR))

    def test_exact_counting_not_float_simulation(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertNotIn("random", imported)
        self.assertNotIn("secrets", imported)
        contract = make_contract(DRAWS[:1])
        result = run(contract, make_records(contract, [DISJOINT_5], [1]))
        exact = Fraction(result["PER_DRAW"][0]["P_SUCCESS"])
        self.assertEqual(DENOMINATOR % exact.denominator, 0)
        self.assertEqual(exact * DENOMINATOR, 1299120)


class SequenceStatisticsTests(unittest.TestCase):
    """AC2 and AC7 sequence cases."""

    def test_zero_draw(self):
        contract = make_contract(DRAWS[:2])
        result = run(contract, [], allow_interim_prefix=True)
        self.assertEqual(result["OBSERVED_DRAW_COUNT"], 0)
        self.assertEqual(result["SCHEDULE_STATUS"], "INTERIM_PREFIX")
        self.assertEqual(result["UNOBSERVED_SCHEDULED_DRAW_IDS"], DRAWS[:2])
        self.assertEqual(result["E_VALUE"], "1")
        self.assertEqual(result["FAIR_EXPECTED_SUCCESSES"], "0")
        self.assertEqual(result["OBSERVED_SUCCESSES"], 0)
        self.assertIsNone(result["FAIR_EXPECTED_RATE"])
        self.assertIsNone(result["OBSERVED_SUCCESS_RATE"])
        self.assertEqual(result["STATISTICAL_SIGNAL"], "THRESHOLD_NOT_REACHED")
        self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        with self.assertRaises(evaluator.ContractError) as ctx:
            run(contract, [])
        self.assertEqual(ctx.exception.code, "MISSING_DRAW_ID")

    def test_one_draw_success(self):
        contract = make_contract(DRAWS[:1])
        records = make_records(contract, [DISJOINT_5], [1])
        before = copy.deepcopy(records)
        result = run(contract, records)
        self.assertEqual(records, before)
        row = result["PER_DRAW"][0]
        self.assertEqual((row["MAX_HITS"], row["Y"]), (3, 1))
        self.assertEqual(Fraction(row["E_FACTOR"]), Fraction(3, 2))
        self.assertEqual(Fraction(result["E_VALUE"]), Fraction(3, 2))
        self.assertEqual(result["OBSERVED_SUCCESSES"], 1)
        self.assertEqual(Fraction(result["FAIR_EXPECTED_SUCCESSES"]), P_DISJOINT)
        self.assertEqual(Fraction(result["EXCESS_SUCCESS_COUNT"]), 1 - P_DISJOINT)
        self.assertEqual(Fraction(result["OBSERVED_SUCCESS_RATE"]), 1)
        self.assertEqual(Fraction(result["FAIR_EXPECTED_RATE"]), P_DISJOINT)
        self.assertEqual(result["SCHEDULE_STATUS"], "COMPLETE")

    def test_one_draw_failure(self):
        contract = make_contract(DRAWS[:1])
        result = run(contract, make_records(contract, [DISJOINT_5], [0]))
        row = result["PER_DRAW"][0]
        self.assertEqual((row["MAX_HITS"], row["Y"]), (2, 0))
        expected = (1 - Fraction(3, 2) * P_DISJOINT) / (1 - P_DISJOINT)
        self.assertEqual(expected, failure_factor(1299120))
        self.assertEqual(Fraction(result["E_VALUE"]), expected)
        self.assertLess(Fraction(result["E_VALUE"]), 1)
        self.assertEqual(result["OBSERVED_SUCCESSES"], 0)
        self.assertEqual(Fraction(result["EXCESS_SUCCESS_COUNT"]), -P_DISJOINT)
        self.assertEqual(Fraction(result["OBSERVED_SUCCESS_RATE"]), 0)

    def test_two_draw_mixed(self):
        contract = make_contract(DRAWS[:2])
        result = run(contract, make_records(contract, [DISJOINT_5, DISJOINT_5], [1, 0]))
        self.assertEqual([row["Y"] for row in result["PER_DRAW"]], [1, 0])
        self.assertEqual(Fraction(result["E_VALUE"]), Fraction(3, 2) * failure_factor(1299120))
        self.assertEqual(result["OBSERVED_SUCCESSES"], 1)
        self.assertEqual(Fraction(result["FAIR_EXPECTED_SUCCESSES"]), 2 * P_DISJOINT)
        self.assertEqual(Fraction(result["OBSERVED_SUCCESS_RATE"]), Fraction(1, 2))
        self.assertEqual(Fraction(result["EXCESS_SUCCESS_COUNT"]), 1 - 2 * P_DISJOINT)

    def test_multidraw_different_baselines(self):
        contract = make_contract(DRAWS[:2])
        result = run(contract, make_records(contract, [DISJOINT_5, SHARED_CORE_5], [0, 1]))
        rows = result["PER_DRAW"]
        self.assertEqual([Fraction(r["P_SUCCESS"]) for r in rows], [P_DISJOINT, P_SHARED_CORE])
        self.assertNotEqual(rows[0]["P_SUCCESS"], rows[1]["P_SUCCESS"])
        self.assertEqual(
            [r["MAX_HIT_WEIGHTS"] for r in rows], [DISJOINT_WEIGHTS, SHARED_CORE_WEIGHTS]
        )
        fair = P_DISJOINT + P_SHARED_CORE
        self.assertEqual(Fraction(result["FAIR_EXPECTED_SUCCESSES"]), fair)
        self.assertEqual(Fraction(result["FAIR_EXPECTED_RATE"]), fair / 2)
        self.assertEqual(Fraction(rows[0]["CUMULATIVE_FAIR_EXPECTED_SUCCESSES"]), P_DISJOINT)
        self.assertEqual(Fraction(result["EXCESS_SUCCESS_COUNT"]), 1 - fair)


class EProcessMathTests(unittest.TestCase):
    """AC3: exact null expectation and multiplicative identity."""

    PROBABILITIES = (
        P_DISJOINT,
        P_SHARED_CORE,
        Fraction(260624, DENOMINATOR),
        Fraction(1, DENOMINATOR),
        Fraction(2, 3),
    )

    def test_e_process_null_expectation(self):
        for p in self.PROBABILITIES:
            win = evaluator.e_process_factor(p, 1)
            lose = evaluator.e_process_factor(p, 0)
            self.assertIsInstance(win, Fraction)
            self.assertIsInstance(lose, Fraction)
            q = Fraction(3, 2) * p
            self.assertEqual(win, q / p)
            self.assertEqual(lose, (1 - q) / (1 - p))
            self.assertGreaterEqual(lose, 0)
            self.assertEqual(p * win + (1 - p) * lose, 1)

    def test_e_process_factor_rejects_inexact_or_invalid_inputs(self):
        cases = (
            (0.0929, 1, "INVALID_SUCCESS_PROBABILITY"),
            (Fraction(0), 1, "INVALID_SUCCESS_PROBABILITY"),
            (Fraction(1), 0, "INVALID_SUCCESS_PROBABILITY"),
            (Fraction(3, 4), 0, "ALTERNATIVE_NOT_A_PROBABILITY"),
            (P_DISJOINT, True, "INVALID_SUCCESS_INDICATOR"),
            (P_DISJOINT, 2, "INVALID_SUCCESS_INDICATOR"),
        )
        for p, y, code in cases:
            with self.subTest(p=p, y=y), self.assertRaises(evaluator.ContractError) as ctx:
                evaluator.e_process_factor(p, y)
            self.assertEqual(ctx.exception.code, code)

    def test_e_process_multiplicative_identity(self):
        contract = make_contract(DRAWS[:4])
        portfolios = [DISJOINT_5, SHARED_CORE_5, DISJOINT_5, SHARED_CORE_5]
        result = run(contract, make_records(contract, portfolios, [1, 0, 0, 1]))
        running = Fraction(1)
        for row in result["PER_DRAW"]:
            factor = Fraction(row["E_FACTOR"])
            p = Fraction(row["SUCCESS_WEIGHT"], DENOMINATOR)
            self.assertEqual(Fraction(row["P_SUCCESS"]), p)
            self.assertEqual(Fraction(row["Q_ALTERNATIVE"]), Fraction(3, 2) * p)
            expected = Fraction(3, 2) if row["Y"] else failure_factor(row["SUCCESS_WEIGHT"])
            self.assertEqual(factor, expected)
            running *= factor
            self.assertEqual(Fraction(row["E_VALUE"]), running)
        self.assertEqual(Fraction(result["E_VALUE"]), running)
        self.assertEqual(
            running,
            Fraction(9, 4) * failure_factor(1029945) * failure_factor(1299120),
        )

    def test_threshold_crossing_and_ville_sup_semantics(self):
        contract = make_contract(DRAWS[:7])
        result = run(contract, make_records(contract, [DISJOINT_5] * 7, [1] * 7))
        self.assertEqual(Fraction(result["E_VALUE"]), Fraction(3, 2) ** 7)
        self.assertEqual(result["STATISTICAL_SIGNAL"], "THRESHOLD_NOT_REACHED")
        self.assertIsNone(result["THRESHOLD_FIRST_CROSSED_DRAW_ID"])

        contract = make_contract(DRAWS[:13])
        outcomes = [1] * 8 + [0] * 5
        result = run(contract, make_records(contract, [DISJOINT_5] * 13, outcomes))
        self.assertEqual(result["THRESHOLD_FIRST_CROSSED_DRAW_ID"], DRAWS[7])
        self.assertEqual(Fraction(result["PER_DRAW"][7]["E_VALUE"]), Fraction(6561, 256))
        self.assertEqual(Fraction(result["MAX_E_VALUE"]), Fraction(6561, 256))
        self.assertLess(Fraction(result["E_VALUE"]), 20)
        self.assertEqual(result["STATISTICAL_SIGNAL"], "THRESHOLD_REACHED")
        self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        self.assertEqual(result["PREDICTIVE_SUCCESS_IMPROVEMENT"], "NOT_ESTABLISHED")
        self.assertEqual(result["CERTIFIED_PROSPECTIVE_DRAW_COUNT"], 0)


class AdaptiveValidityTests(unittest.TestCase):
    """AC4: adaptive portfolios, per-draw baselines, sequential observation."""

    @staticmethod
    def adaptive_portfolio(history):
        if not history:
            return DISJOINT_5
        return SHARED_CORE_5 if sum(history) % 2 else DISJOINT_5

    def test_adaptive_strategy_null_expectation_is_exactly_one(self):
        contract = make_contract(DRAWS[:3])
        total = Fraction(0)
        for path in itertools.product((0, 1), repeat=3):
            portfolios = [self.adaptive_portfolio(path[:i]) for i in range(3)]
            p_values = [P_SHARED_CORE if t is SHARED_CORE_5 else P_DISJOINT for t in portfolios]
            result = run(contract, make_records(contract, portfolios, path))
            self.assertEqual([r["Y"] for r in result["PER_DRAW"]], list(path))
            self.assertEqual([Fraction(r["P_SUCCESS"]) for r in result["PER_DRAW"]], p_values)
            null_probability = Fraction(1)
            for i, p in enumerate(p_values):
                null_probability *= p if path[i] else 1 - p
            total += null_probability * Fraction(result["E_VALUE"])
            self.assertNotIn("P_VALUE", result)
        self.assertEqual(total, 1)

    def test_sequential_interim_prefixes_match_complete_trajectory(self):
        contract = make_contract(DRAWS[:4])
        portfolios = [DISJOINT_5, SHARED_CORE_5, SHARED_CORE_5, DISJOINT_5]
        records = make_records(contract, portfolios, [0, 1, 1, 0])
        complete = run(contract, records)
        trajectory = ["1"] + [row["E_VALUE"] for row in complete["PER_DRAW"]]
        for k in range(5):
            interim = run(contract, records[:k], allow_interim_prefix=True)
            self.assertEqual(interim["E_VALUE"], trajectory[k])
            self.assertEqual(interim["OBSERVED_DRAW_IDS"], DRAWS[:k])
            self.assertEqual(interim["SCHEDULE_STATUS"], "COMPLETE" if k == 4 else "INTERIM_PREFIX")

    def test_strategy_switch_mid_sequence_is_rejected(self):
        contract = make_contract(DRAWS[:2])
        records = make_records(contract, [DISJOINT_5, DISJOINT_5], [0, 1])
        records[1]["STRATEGY_IDENTITY"] = "synthetic-edge-strategy@version:2"
        with self.assertRaises(evaluator.ContractError) as ctx:
            run(contract, records)
        self.assertEqual(ctx.exception.code, "STRATEGY_IDENTITY_CHANGED")

    def test_schedule_must_be_chronological(self):
        contract = make_contract(DRAWS[:2])
        records = make_records(contract, [DISJOINT_5, DISJOINT_5], [0, 1])
        records[1].update(
            {
                "INPUT_CUTOFF": "2097-12-01T00:00:00+08:00",
                "PREDICTION_CAPTURE_TIME": "2097-12-01T12:00:00+08:00",
                "DRAW_TIME": "2097-12-01T20:30:00+08:00",
            }
        )
        with self.assertRaises(evaluator.ContractError) as ctx:
            run(contract, records)
        self.assertEqual(ctx.exception.code, "DRAW_SCHEDULE_NOT_CHRONOLOGICAL")

    def test_existing_scorer_temporal_checks_stay_active(self):
        contract = make_contract(DRAWS[:1])
        records = make_records(contract, [DISJOINT_5], [1])
        records[0]["PREDICTION_CAPTURE_TIME"] = "2098-01-01T21:00:00+08:00"
        with self.assertRaises(evaluator.ContractError) as ctx:
            run(contract, records)
        self.assertEqual(ctx.exception.code, "PREDICTION_AFTER_DRAW")


class ExperimentIdentityTests(unittest.TestCase):
    """AC6: fail-closed experiment identity and draw-set binding."""

    def assertCode(self, code, contract, records, **overrides):
        with self.assertRaises(evaluator.ContractError) as ctx:
            run(contract, records, **overrides)
        self.assertEqual(ctx.exception.code, code)

    def setUp(self):
        self.contract = make_contract(DRAWS[:2])
        self.records = make_records(self.contract, [DISJOINT_5, SHARED_CORE_5], [1, 0])

    def test_duplicate_draw_id(self):
        self.assertCode("DUPLICATE_DRAW_ID", self.contract, [*self.records, self.records[0]])
        duplicated = make_contract([DRAWS[0], DRAWS[0]])
        self.assertCode("DUPLICATE_DRAW_ID", duplicated, [])

    def test_missing_draw_id(self):
        self.assertCode("MISSING_DRAW_ID", self.contract, self.records[:1])
        self.assertCode(
            "MISSING_DRAW_ID", self.contract, self.records[1:], allow_interim_prefix=True
        )

    def test_unexpected_draw_id(self):
        extra = make_record(self.contract, 0, DISJOINT_5, HIT_NUMBERS, DRAW_ID=DRAWS[5])
        self.assertCode("UNEXPECTED_DRAW_ID", self.contract, [*self.records, extra])

    def test_draw_set_changed(self):
        for requested in (DRAWS[:1], DRAWS[1::-1], DRAWS[:3], []):
            with self.subTest(requested=requested):
                self.assertCode(
                    "DRAW_SET_CHANGED", self.contract, self.records, expected_draw_ids=requested
                )

    def test_ticket_count_changed(self):
        self.assertCode("TICKET_COUNT_CHANGED", self.contract, self.records, ticket_count=3)
        self.assertCode("TICKET_COUNT_CHANGED", self.contract, self.records, ticket_count=True)
        declared = copy.deepcopy(self.records)
        declared[1]["TICKET_COUNT"] = 3
        self.assertCode("TICKET_COUNT_CHANGED", self.contract, declared)
        mixed = copy.deepcopy(self.records)
        mixed[1].update({"TICKET_COUNT": 2, "PREDICTED_TICKETS": copy.deepcopy(DISJOINT_2)})
        self.assertCode("TICKET_COUNT_CHANGED", self.contract, mixed)
        short = copy.deepcopy(self.records)
        short[0]["PREDICTED_TICKETS"] = copy.deepcopy(DISJOINT_5[:3])
        self.assertCode("TICKET_COUNT_CHANGED", self.contract, short)

    def test_strategy_and_experiment_identity_changed(self):
        self.assertCode(
            "STRATEGY_IDENTITY_CHANGED", self.contract, self.records, strategy_identity="other@1"
        )
        self.assertCode("EXPERIMENT_ID_CHANGED", self.contract, self.records, experiment_id="OTHER")
        renamed = copy.deepcopy(self.records)
        renamed[0]["EXPERIMENT_ID"] = "OTHER"
        self.assertCode("EXPERIMENT_ID_CHANGED", self.contract, renamed)

    def test_contract_hash_changed(self):
        self.assertCode(
            "CONTRACT_HASH_CHANGED", self.contract, self.records, expected_contract_sha256="d" * 64
        )
        self.assertCode(
            "CONTRACT_HASH_CHANGED",
            self.contract,
            self.records,
            expected_contract_sha256=pinned(self.contract).upper(),
        )
        rebound = copy.deepcopy(self.records)
        rebound[1]["EXPERIMENT_CONTRACT_SHA256"] = "d" * 64
        self.assertCode("CONTRACT_HASH_CHANGED", self.contract, rebound)

    def test_malformed_tickets(self):
        bad_tickets = (
            [1, 2, 3, 4, 5],
            [1, 2, 3, 4, 5, 50],
            [1, 1, 2, 3, 4, 5],
            [True, 2, 3, 4, 5, 6],
            ["1", 2, 3, 4, 5, 6],
            "123456",
        )
        for bad in bad_tickets:
            records = copy.deepcopy(self.records)
            records[0]["PREDICTED_TICKETS"][2] = bad
            with self.subTest(bad=bad):
                self.assertCode("MALFORMED_TICKETS", self.contract, records)
        records = copy.deepcopy(self.records)
        records[0]["PREDICTED_TICKETS"] = "not-a-portfolio"
        self.assertCode("MALFORMED_TICKETS", self.contract, records)


class ProvenanceBoundaryTests(unittest.TestCase):
    """AC5 and AC6: evidence status cannot be raised by assertion."""

    def setUp(self):
        self.contract = make_contract(DRAWS[:2])
        self.records = make_records(self.contract, [DISJOINT_5, SHARED_CORE_5], [1, 1])

    def assertCode(self, code, records, **overrides):
        with self.assertRaises(evaluator.ContractError) as ctx:
            run(self.contract, records, **overrides)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception

    def test_dependencies_resolve_to_this_checkout(self):
        for function in (
            evaluator.portfolio_exact_baseline,
            evaluator.verify_biglotto_portfolio_predraw_boundary,
        ):
            module_file = Path(sys.modules[function.__module__].__file__).resolve()
            self.assertEqual(module_file.parent, SOURCE.parent)

    def test_default_result_is_diagnostic_only(self):
        result = run(self.contract, self.records)
        self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        self.assertEqual(result["PREDRAW_EVIDENCE_STATUS"], "NOT_VERIFIED")
        self.assertEqual(result["OFFICIAL_OUTCOME_STATUS"], "NOT_AUTHENTICATED")
        self.assertEqual(result["CERTIFIED_PROSPECTIVE_DRAW_COUNT"], 0)
        self.assertEqual(result["PREDICTIVE_SUCCESS_IMPROVEMENT"], "NOT_ESTABLISHED")

    def test_missing_provenance(self):
        for field, code in (
            ("RFC3161_EVIDENCE_REFERENCE", "UNVERIFIED_PREDRAW_EVIDENCE"),
            ("OFFICIAL_RESULT_REFERENCE", "UNAUTHENTICATED_OUTCOME"),
        ):
            for value in (None, "", " padded ", "VERIFIED", "verified", "PASS", True, 1):
                records = copy.deepcopy(self.records)
                if value is None:
                    del records[1][field]
                else:
                    records[1][field] = value
                with self.subTest(field=field, value=value):
                    self.assertCode(code, records)

    def test_self_asserted_verification_fields_are_rejected(self):
        for field, value in (
            ("PREDRAW_EVIDENCE_VERIFIED", True),
            ("EVIDENCE_STATUS", "VERIFIED"),
            ("OFFICIAL_OUTCOME_AUTHENTICATED", True),
        ):
            records = copy.deepcopy(self.records)
            records[0][field] = value
            with self.subTest(field=field):
                self.assertCode("UNEXPECTED_FIELD", records)
        claimed = make_contract(DRAWS[:2], EVIDENCE_STATUS="VERIFIED")
        with self.assertRaises(evaluator.ContractError) as ctx:
            run(claimed, self.records)
        self.assertEqual(ctx.exception.code, "INVALID_CONTRACT")

    def test_flag_or_status_string_cannot_certify(self):
        for flag in (True, "VERIFIED", 1):
            with self.subTest(flag=flag):
                self.assertCode("UNVERIFIED_PREDRAW_EVIDENCE", self.records, certification=flag)
        self.assertCode(
            "UNVERIFIED_PREDRAW_EVIDENCE", self.records, certification={"predraw_verified": True}
        )

    def test_existing_verifier_refusal_is_unverified_predraw_evidence(self):
        error = self.assertCode("UNVERIFIED_PREDRAW_EVIDENCE", self.records, certification={})
        self.assertIsInstance(error.__cause__, evaluator.ContractError)
        empty = make_contract(DRAWS[:2])
        with self.assertRaises(evaluator.ContractError) as ctx:
            run(empty, [], allow_interim_prefix=True, certification={})
        self.assertEqual(ctx.exception.code, "UNVERIFIED_PREDRAW_EVIDENCE")

    def test_passing_predraw_verifier_still_leaves_outcome_unauthenticated(self):
        fake = {"EVIDENCE_STATUS": "VERIFIED", "PREDICTIVE_SUCCESS_IMPROVEMENT": "ESTABLISHED"}
        with patch.object(
            evaluator, "verify_biglotto_portfolio_predraw_boundary", return_value=fake
        ) as verifier:
            self.assertCode(
                "UNAUTHENTICATED_OUTCOME",
                self.records,
                certification={"evidence_bundle": {}, "pinned_tsa_cert_sha256": "e" * 64},
            )
        args, kwargs = verifier.call_args
        predictions, outcomes, verifier_contract = args
        self.assertIs(kwargs["require_independent_verification"], True)
        self.assertEqual(kwargs["pinned_tsa_cert_sha256"], "e" * 64)
        self.assertEqual(verifier_contract["EXPECTED_DRAW_IDS"], DRAWS[:2])
        self.assertEqual(verifier_contract["EXPERIMENT_CONTRACT_SHA256"], pinned(self.contract))
        self.assertEqual([p["DRAW_ID"] for p in predictions], DRAWS[:2])
        self.assertEqual({p["TICKET_COUNT"] for p in predictions}, {5})
        self.assertEqual(
            predictions[0]["PREDRAW_EVIDENCE_LOCATOR"],
            self.records[0]["RFC3161_EVIDENCE_REFERENCE"],
        )
        self.assertEqual(
            outcomes[1]["OFFICIAL_RESULT_SOURCE"], self.records[1]["OFFICIAL_RESULT_REFERENCE"]
        )

    def test_public_signature_has_no_status_or_parameter_overrides(self):
        parameters = inspect.signature(evaluator.evaluate_biglotto_prospective_edge).parameters
        self.assertEqual(
            list(parameters),
            [
                "records",
                "experiment_contract",
                "expected_contract_sha256",
                "experiment_id",
                "strategy_identity",
                "expected_draw_ids",
                "ticket_count",
                "allow_interim_prefix",
                "certification",
            ],
        )
        self.assertEqual(parameters["certification"].default, None)
        self.assertEqual(parameters["allow_interim_prefix"].default, False)

    def test_interim_flag_must_be_bool(self):
        self.assertCode("INVALID_ARGUMENT", self.records, allow_interim_prefix="yes")


class PosthocParameterTests(unittest.TestCase):
    """AC3: preregistered design cannot be mutated after seeing results."""

    MUTATIONS = (
        ("ALTERNATIVE_MULTIPLIER", "2"),
        ("ALTERNATIVE_MULTIPLIER", "1.5"),
        ("ALPHA", "1/10"),
        ("EVIDENCE_THRESHOLD", 10),
        ("EVIDENCE_THRESHOLD", 20.0),
        ("PRIMARY_SUCCESS_EVENT", "MAX_HITS>=2"),
        ("PRIMARY_STATISTIC", "POISSON_BINOMIAL_P_VALUE"),
        ("DRAW_MODEL", "FAIR_6_OF_42"),
        ("OUTCOME_DENOMINATOR", 5245786),
    )

    def setUp(self):
        self.contract = make_contract(DRAWS[:2])
        self.records = make_records(self.contract, [DISJOINT_5, DISJOINT_5], [1, 1])

    def test_posthoc_parameter_mutation_breaks_pinned_hash(self):
        for field, value in self.MUTATIONS:
            mutated = make_contract(DRAWS[:2], **{field: value})
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(evaluator.ContractError) as ctx,
            ):
                run(mutated, self.records, expected_contract_sha256=pinned(self.contract))
            self.assertEqual(ctx.exception.code, "CONTRACT_HASH_CHANGED")

    def test_repinned_mutation_is_not_this_preregistered_design(self):
        for field, value in self.MUTATIONS:
            mutated = make_contract(DRAWS[:2], **{field: value})
            records = make_records(mutated, [DISJOINT_5, DISJOINT_5], [1, 1])
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(evaluator.ContractError) as ctx,
            ):
                run(mutated, records)
            self.assertEqual(ctx.exception.code, "PREREGISTERED_PARAMETER_CHANGED")

    def test_missing_design_field_is_invalid_contract(self):
        incomplete = make_contract(DRAWS[:2])
        del incomplete["ALTERNATIVE_MULTIPLIER"]
        with self.assertRaises(evaluator.ContractError) as ctx:
            run(incomplete, self.records)
        self.assertEqual(ctx.exception.code, "INVALID_CONTRACT")

    def test_fixed_constants_are_consistent(self):
        self.assertEqual(evaluator.ALTERNATIVE_MULTIPLIER, Fraction(3, 2))
        self.assertEqual(evaluator.ALPHA, Fraction(1, 20))
        self.assertEqual(evaluator.EVIDENCE_THRESHOLD, 20)
        self.assertEqual(1 / evaluator.ALPHA, evaluator.EVIDENCE_THRESHOLD)
        design = evaluator.PREREGISTERED_DESIGN
        self.assertEqual(
            Fraction(design["ALTERNATIVE_MULTIPLIER"]), evaluator.ALTERNATIVE_MULTIPLIER
        )
        self.assertEqual(Fraction(design["ALPHA"]), evaluator.ALPHA)
        self.assertEqual(design["OUTCOME_DENOMINATOR"], comb(49, 6))
        result = run(self.contract, self.records)
        self.assertEqual(
            (result["ALTERNATIVE_MULTIPLIER"], result["ALPHA"], result["EVIDENCE_THRESHOLD"]),
            ("3/2", "1/20", 20),
        )


class Python39CompatibilityTests(unittest.TestCase):
    """AC7: Python 3.9 compatibility of source and tests."""

    def test_python39_syntax_and_runtime(self):
        for path in (SOURCE, Path(__file__).resolve()):
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, feature_version=(3, 9))
            futures = [
                node
                for node in tree.body
                if isinstance(node, ast.ImportFrom) and node.module == "__future__"
            ]
            self.assertTrue(futures, path.name)
            strict_zip = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "zip"
                and any(keyword.arg == "strict" for keyword in node.keywords)
            ]
            self.assertEqual(strict_zip, [], path.name)
        self.assertGreaterEqual(sys.version_info[:2], (3, 9))


if __name__ == "__main__":
    unittest.main()
