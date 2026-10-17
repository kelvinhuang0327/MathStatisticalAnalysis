"""Focused prospective BIG_LOTTO portfolio scorer unit tests (Python 3.9).

Pure synthetic fixtures only; no real predictions or lottery outcomes.
Tests Gates A-I: exact multivariate hypergeometric baselines, regression vectors,
marginal parity, multi-draw scoring, and fail-closed contract validation.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "score_biglotto_portfolio_prospective_r1.py"
)
SPEC = importlib.util.spec_from_file_location("portfolio_r1_under_test", SOURCE)
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def synthetic_tickets(ticket_count: int, pattern: str = "disjoint") -> list[list[int]]:
    disjoint_map = {
        2: [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]],
        3: [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12], [13, 14, 15, 16, 17, 18]],
        5: [
            [1, 2, 3, 4, 5, 6],
            [7, 8, 9, 10, 11, 12],
            [13, 14, 15, 16, 17, 18],
            [19, 20, 21, 22, 23, 24],
            [25, 26, 27, 28, 29, 30],
        ],
    }
    if pattern == "disjoint" and ticket_count in disjoint_map:
        return disjoint_map[ticket_count]
    elif pattern == "identical":
        base = [1, 2, 3, 4, 5, 6]
        return [list(base) for _ in range(ticket_count)]
    elif pattern == "shared_core_3":
        core = [1, 2, 3]
        if ticket_count == 3:
            return [
                [*core, 4, 5, 6],
                [*core, 7, 8, 9],
                [*core, 10, 11, 12],
            ]
        elif ticket_count == 5:
            return [
                [*core, 4, 5, 6],
                [*core, 7, 8, 9],
                [*core, 10, 11, 12],
                [*core, 13, 14, 15],
                [*core, 16, 17, 18],
            ]
    raise ValueError(f"unknown pattern {pattern} for ticket_count {ticket_count}")


def synthetic_portfolio_draw(
    draw: str = "199000001",
    ticket_count: int = 2,
    tickets: list[list[int]] | None = None,
    hits_per_ticket: list[int] | None = None,
    official_numbers: list[int] | None = None,
):
    if tickets is None:
        tickets = synthetic_tickets(ticket_count, "disjoint")

    prediction = {
        "EXPERIMENT_ID": "SYNTHETIC_PORTFOLIO_R1",
        "DRAW_ID": draw,
        "PREDICTED_TICKETS": copy.deepcopy(tickets),
        "STRATEGY_IDENTITY": "synthetic-portfolio-strategy@version:1",
        "INPUT_SNAPSHOT_SHA256": "b" * 64,
        "INPUT_CUTOFF": "2098-12-30T00:00:00+08:00",
        "PREDICTION_CAPTURE_ID": "synthetic-capture-" + draw,
        "PREDICTION_CAPTURE_TIME": "2098-12-31T00:00:00+08:00",
        "PREDRAW_EVIDENCE_LOCATOR": "synthetic://unverified/" + draw,
    }

    if official_numbers is None:
        if hits_per_ticket is not None:
            # Construct official numbers that match specified hits on ticket 0
            h0 = hits_per_ticket[0]
            official_numbers = sorted(list(tickets[0][:h0]) + list(range(35, 35 + (6 - h0))))
        else:
            # Default: 3 hits on ticket 0
            official_numbers = sorted([*list(tickets[0][:3]), 35, 36, 37])

    outcome = {
        "DRAW_ID": draw,
        "SIX_OFFICIAL_MAIN_NUMBERS": list(official_numbers),
        "DRAW_TIME": "2099-01-01T00:00:00+08:00",
        "OFFICIAL_RESULT_SOURCE": "synthetic://not-an-official-result/" + draw,
    }
    return prediction, outcome


def evaluate_portfolio(
    predictions,
    outcomes,
    *,
    ticket_count: int = 2,
    expected_draw_ids: list[str] | None = None,
    experiment_id: str = "SYNTHETIC_PORTFOLIO_R1",
    strategy_identity: str = "synthetic-portfolio-strategy@version:1",
    **kwargs,
):
    contract = {
        "experiment_id": experiment_id,
        "strategy_identity": strategy_identity,
        "expected_draw_ids": expected_draw_ids if expected_draw_ids is not None else ["199000001"],
        "ticket_count": ticket_count,
    }
    contract.update(kwargs)
    return scorer.score_biglotto_portfolio_prospective(predictions, outcomes, **contract)


class PortfolioExactBaselineTests(unittest.TestCase):
    """Gate A, B, C mathematical and normalization tests."""

    def test_gate_a_ticket_count_validation(self):
        # Only 2, 3, 5 are allowed
        for m in (2, 3, 5):
            res = scorer.portfolio_exact_baseline(synthetic_tickets(m))
            self.assertEqual(res["TICKET_COUNT"], m)

        # Invalid counts
        for m_invalid in (0, 1, 4, 6, 7):
            t = [[1, 2, 3, 4, 5, 6] for _ in range(m_invalid)]
            with self.assertRaises(scorer.ContractError) as ctx:
                scorer.portfolio_exact_baseline(t)
            self.assertEqual(ctx.exception.code, "INVALID_TICKET_COUNT")

        with self.assertRaises(scorer.ContractError) as ctx:
            scorer.portfolio_exact_baseline("not-a-list")
        self.assertEqual(ctx.exception.code, "INVALID_TICKET_COUNT")

    def test_gate_a_ticket_validation_failures(self):
        cases = [
            ([[1, 2, 3, 4, 5]], "INVALID_TICKET_SIZE"),
            ([[1, 2, 3, 4, 5, 6, 7]], "INVALID_TICKET_SIZE"),
            ([[]], "INVALID_TICKET_SIZE"),
            (["1,2,3,4,5,6"], "INVALID_TICKET_SIZE"),
            ([[1, 2, 3, 4, 5, 5]], "DUPLICATE_NUMBERS"),
            ([[0, 2, 3, 4, 5, 6]], "OUT_OF_RANGE_NUMBER"),
            ([[1, 2, 3, 4, 5, 50]], "OUT_OF_RANGE_NUMBER"),
            ([[True, 2, 3, 4, 5, 6]], "INVALID_NUMBER_TYPE"),
            ([[1.0, 2, 3, 4, 5, 6]], "INVALID_NUMBER_TYPE"),
            ([["1", 2, 3, 4, 5, 6]], "INVALID_NUMBER_TYPE"),
        ]
        for bad_ticket, expected_code in cases:
            # Pair with a valid second ticket
            tickets = [bad_ticket[0], [7, 8, 9, 10, 11, 12]]
            with self.subTest(bad_ticket=bad_ticket, code=expected_code):
                with self.assertRaises(scorer.ContractError) as ctx:
                    scorer.portfolio_exact_baseline(tickets)
                self.assertEqual(ctx.exception.code, expected_code)

    def test_gate_b_exact_mathematics_normalization(self):
        for m in (2, 3, 5):
            res = scorer.portfolio_exact_baseline(synthetic_tickets(m))
            self.assertEqual(res["DENOMINATOR"], 13983816)
            self.assertEqual(sum(res["MAX_HIT_WEIGHTS"]), 13983816)
            self.assertEqual(len(res["MAX_HIT_WEIGHTS"]), 7)
            probs = [Fraction(w, 13983816) for w in res["MAX_HIT_WEIGHTS"]]
            self.assertEqual(sum(probs), 1)
            self.assertEqual(res["PROBABILITY_SUM"], 1)

            # Marginal weights for each ticket must equal single ticket vector
            for marg in res["SINGLE_TICKET_MARGINAL_WEIGHTS"]:
                self.assertEqual(marg, list(scorer.SINGLE_TICKET_WEIGHT_VECTOR))

            # Expected sum of hits = 36 * m / 49
            self.assertEqual(res["EXACT_EXPECTED_SUM_HITS"], f"{36 * m}/49")
            self.assertAlmostEqual(res["EXPECTED_SUM_HITS"], float(Fraction(36 * m, 49)))

    def test_gate_c_fixed_regression_vectors_disjoint(self):
        # m=2 disjoint
        res2 = scorer.portfolio_exact_baseline(synthetic_tickets(2, "disjoint"))
        expected_w2 = [2324784, 7608384, 3529800, 493240, 27090, 516, 2]
        self.assertEqual(res2["MAX_HIT_WEIGHTS"], expected_w2)
        self.assertEqual(sum(expected_w2[3:]), 520848)

        # m=3 disjoint
        res3 = scorer.portfolio_exact_baseline(synthetic_tickets(3, "disjoint"))
        expected_w3 = [736281, 7427538, 5039325, 739260, 40635, 774, 3]
        self.assertEqual(res3["MAX_HIT_WEIGHTS"], expected_w3)
        self.assertEqual(sum(expected_w3[3:]), 780672)

        # m=5 disjoint
        res5 = scorer.portfolio_exact_baseline(synthetic_tickets(5, "disjoint"))
        expected_w5 = [27132, 5093064, 7564500, 1230100, 67725, 1290, 5]
        self.assertEqual(res5["MAX_HIT_WEIGHTS"], expected_w5)
        self.assertEqual(sum(expected_w5[3:]), 1299120)

    def test_gate_c_fixed_regression_vectors_shared_cores(self):
        # m=3 shared 3 numbers core
        res3_core = scorer.portfolio_exact_baseline(synthetic_tickets(3, "shared_core_3"))
        expected_w3_core = [2324784, 7223769, 3753603, 641436, 39447, 774, 3]
        self.assertEqual(res3_core["MAX_HIT_WEIGHTS"], expected_w3_core)

        # m=5 shared 3 numbers core
        res5_core = scorer.portfolio_exact_baseline(synthetic_tickets(5, "shared_core_3"))
        expected_w5_core = [736281, 7299756, 4917834, 964705, 63945, 1290, 5]
        self.assertEqual(res5_core["MAX_HIT_WEIGHTS"], expected_w5_core)

    def test_gate_c_identical_tickets_degenerate_case(self):
        # Fully overlapping tickets collapse to single ticket vector for m=2, 3, 5
        for m in (2, 3, 5):
            res = scorer.portfolio_exact_baseline(synthetic_tickets(m, "identical"))
            self.assertEqual(res["MAX_HIT_WEIGHTS"], list(scorer.SINGLE_TICKET_WEIGHT_VECTOR))

    def test_gate_c_same_union_different_overlap_distributions(self):
        # Two 3-ticket portfolios with the exact same union size (12),
        # but different higher-order overlap geometry
        # Portfolio A: all 3 share {1,2,3}, remainder disjoint (triple overlap = 3)
        port_a = [
            [1, 2, 3, 4, 5, 6],
            [1, 2, 3, 7, 8, 9],
            [1, 2, 3, 10, 11, 12],
        ]
        # Portfolio B: pairwise sharing 2 numbers each, triple overlap = 0
        port_b = [
            [1, 2, 3, 4, 5, 6],
            [1, 2, 7, 8, 9, 10],
            [3, 4, 7, 8, 11, 12],
        ]
        union_a = set(port_a[0]) | set(port_a[1]) | set(port_a[2])
        union_b = set(port_b[0]) | set(port_b[1]) | set(port_b[2])
        self.assertEqual(len(union_a), 12)
        self.assertEqual(len(union_b), 12)

        res_a = scorer.portfolio_exact_baseline(port_a)
        res_b = scorer.portfolio_exact_baseline(port_b)

        self.assertEqual(
            res_a["MAX_HIT_WEIGHTS"],
            [2324784, 7223769, 3753603, 641436, 39447, 774, 3],
        )
        self.assertEqual(
            res_b["MAX_HIT_WEIGHTS"],
            [2324784, 6878004, 4047949, 691774, 40528, 774, 3],
        )
        self.assertNotEqual(res_a["MAX_HIT_WEIGHTS"], res_b["MAX_HIT_WEIGHTS"])
        # P(MAX_HITS >= 3) differs
        self.assertEqual(sum(res_a["MAX_HIT_WEIGHTS"][3:]), 681660)
        self.assertEqual(sum(res_b["MAX_HIT_WEIGHTS"][3:]), 733079)

    def test_baseline_internal_guard_rejects_corrupted_combinatorics(self):
        with patch.object(scorer, "comb", return_value=1):
            with self.assertRaises(scorer.ContractError) as ctx:
                scorer.portfolio_exact_baseline(synthetic_tickets(2))
            self.assertEqual(ctx.exception.code, "INCORRECT_BASELINE_NORMALIZATION")


class ProspectivePortfolioScoreTests(unittest.TestCase):
    """Gate D, E, F, G multi-draw prospective scoring and fail-closed matrix tests."""

    def assert_rejected(self, predictions, outcomes, expected_code, **kwargs):
        with self.assertRaises(scorer.ContractError) as caught:
            evaluate_portfolio(predictions, outcomes, **kwargs)
        self.assertEqual(caught.exception.code, expected_code)

    def test_valid_single_draw_m2(self):
        pred, out = synthetic_portfolio_draw(
            "199000001",
            ticket_count=2,
            official_numbers=[1, 2, 3, 35, 36, 37],
        )
        result = evaluate_portfolio([pred], [out], ticket_count=2)
        self.assertEqual(result["TARGET_COUNT"], 1)
        self.assertEqual(result["TICKET_COUNT"], 2)
        self.assertEqual(result["FIXED_EXPERIMENT_ID"], "SYNTHETIC_PORTFOLIO_R1")
        self.assertEqual(result["OBSERVED_MAX_HIT_HISTOGRAM_0_TO_6"], [0, 0, 0, 1, 0, 0, 0])
        self.assertEqual(result["OBSERVED_MEAN_MAX_HITS"], 3.0)
        self.assertEqual(result["OBSERVED_MEAN_SUM_HITS"], 3.0)
        self.assertEqual(len(result["PER_DRAW"]), 1)
        draw_row = result["PER_DRAW"][0]
        self.assertEqual(draw_row["DRAW_ID"], "199000001")
        self.assertEqual(draw_row["TICKET_HITS"], [3, 0])
        self.assertEqual(draw_row["MAX_HITS"], 3)
        self.assertEqual(draw_row["SUM_HITS"], 3)
        self.assertIn("DRAW_EXACT_BASELINE", draw_row)

    def test_valid_single_draw_m3_and_m5(self):
        for m in (3, 5):
            pred, out = synthetic_portfolio_draw(
                "199000001",
                ticket_count=m,
                official_numbers=[1, 2, 7, 8, 35, 36],
            )
            result = evaluate_portfolio([pred], [out], ticket_count=m)
            self.assertEqual(result["TICKET_COUNT"], m)
            self.assertEqual(result["PER_DRAW"][0]["MAX_HITS"], 2)
            self.assertEqual(result["PER_DRAW"][0]["SUM_HITS"], 4)

    def test_multi_draw_with_dynamic_per_draw_baselines(self):
        # Draw 1 uses disjoint tickets; Draw 2 uses shared core tickets
        t_disjoint = synthetic_tickets(3, "disjoint")
        t_core = synthetic_tickets(3, "shared_core_3")

        p1, o1 = synthetic_portfolio_draw(
            "199000001",
            ticket_count=3,
            tickets=t_disjoint,
            official_numbers=[1, 2, 3, 4, 35, 36],
        )
        p2, o2 = synthetic_portfolio_draw(
            "199000002",
            ticket_count=3,
            tickets=t_core,
            official_numbers=[1, 2, 3, 4, 7, 35],
        )

        result = evaluate_portfolio(
            [p1, p2],
            [o1, o2],
            ticket_count=3,
            expected_draw_ids=["199000001", "199000002"],
        )
        self.assertEqual(result["TARGET_COUNT"], 2)
        # Check per-draw exact baselines differ between draws
        b1 = result["PER_DRAW"][0]["DRAW_EXACT_BASELINE"]["MAX_HIT_WEIGHTS"]
        b2 = result["PER_DRAW"][1]["DRAW_EXACT_BASELINE"]["MAX_HIT_WEIGHTS"]
        self.assertEqual(b1, [736281, 7427538, 5039325, 739260, 40635, 774, 3])
        self.assertEqual(b2, [2324784, 7223769, 3753603, 641436, 39447, 774, 3])

        # Cross-draw baseline correctly aggregates expected max hits histogram
        exp_hist = result["PORTFOLIO_BASELINE"]["EXPECTED_MAX_HIT_HISTOGRAM_0_TO_6"]
        self.assertAlmostEqual(sum(exp_hist), 2.0)
        self.assertEqual(
            result["PORTFOLIO_BASELINE"]["EXACT_MEAN_EXPECTED_SUM_HITS"],
            f"{36 * 3}/49",
        )

    def test_evidence_boundary_diagnostics_only(self):
        pred, out = synthetic_portfolio_draw(
            "199000001",
            ticket_count=2,
            official_numbers=[1, 2, 3, 4, 5, 6],
        )
        result = evaluate_portfolio([pred], [out], ticket_count=2)
        self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        self.assertIs(result["CAPTURE_TIME_INDEPENDENTLY_VERIFIED"], False)
        self.assertEqual(result["ORIGINAL_HISTORICAL_PARITY"], "NOT_VERIFIED")
        self.assertEqual(result["PREDICTIVE_SUCCESS_IMPROVEMENT"], "NOT_ESTABLISHED")
        self.assertEqual(result["PREDICTIVE_SUCCESS_EVIDENCE"], "NOT_ESTABLISHED")

    def test_fail_closed_gate_g_matrix(self):
        # Test all 16 required fail-closed rejections from Gate G:
        p, o = synthetic_portfolio_draw(ticket_count=2)

        # 1. INVALID_TICKET_COUNT (in contract ticket_count argument)
        self.assert_rejected([p], [o], "INVALID_TICKET_COUNT", ticket_count=4)
        self.assert_rejected([p], [o], "INVALID_TICKET_COUNT", ticket_count=1)

        # INVALID_TICKET_COUNT (in prediction tickets container)
        p_bad_tc = copy.deepcopy(p)
        p_bad_tc["PREDICTED_TICKETS"] = "invalid"
        self.assert_rejected([p_bad_tc], [o], "INVALID_TICKET_COUNT", ticket_count=2)

        # 2. INVALID_TICKET_SIZE
        p_bad_size = copy.deepcopy(p)
        p_bad_size["PREDICTED_TICKETS"][0] = [1, 2, 3, 4, 5]
        self.assert_rejected([p_bad_size], [o], "INVALID_TICKET_SIZE", ticket_count=2)

        # 3. DUPLICATE_NUMBERS
        p_dup_num = copy.deepcopy(p)
        p_dup_num["PREDICTED_TICKETS"][0] = [1, 2, 3, 4, 5, 5]
        self.assert_rejected([p_dup_num], [o], "DUPLICATE_NUMBERS", ticket_count=2)

        # 4. INVALID_NUMBER_TYPE
        p_bad_type = copy.deepcopy(p)
        p_bad_type["PREDICTED_TICKETS"][0] = [True, 2, 3, 4, 5, 6]
        self.assert_rejected([p_bad_type], [o], "INVALID_NUMBER_TYPE", ticket_count=2)

        # 5. OUT_OF_RANGE_NUMBER
        p_range = copy.deepcopy(p)
        p_range["PREDICTED_TICKETS"][0] = [0, 2, 3, 4, 5, 6]
        self.assert_rejected([p_range], [o], "OUT_OF_RANGE_NUMBER", ticket_count=2)

        # 6. DUPLICATE_DRAW
        p2 = copy.deepcopy(p)
        self.assert_rejected([p, p2], [o], "DUPLICATE_DRAW", ticket_count=2)

        # 7. MISSING_INPUT_CUTOFF
        p_no_cut = copy.deepcopy(p)
        del p_no_cut["INPUT_CUTOFF"]
        self.assert_rejected([p_no_cut], [o], "MISSING_INPUT_CUTOFF", ticket_count=2)
        p_empty_cut = copy.deepcopy(p)
        p_empty_cut["INPUT_CUTOFF"] = ""
        self.assert_rejected([p_empty_cut], [o], "MISSING_INPUT_CUTOFF", ticket_count=2)

        # 8. CUTOFF_AFTER_TARGET
        p_late_cut = copy.deepcopy(p)
        p_late_cut["INPUT_CUTOFF"] = "2099-01-01T00:00:00+08:00"  # Same as draw time
        self.assert_rejected([p_late_cut], [o], "CUTOFF_AFTER_TARGET", ticket_count=2)
        p_cut_after_cap = copy.deepcopy(p)
        p_cut_after_cap["INPUT_CUTOFF"] = "2098-12-31T01:00:00+08:00"  # After capture time
        self.assert_rejected([p_cut_after_cap], [o], "CUTOFF_AFTER_TARGET", ticket_count=2)

        # 9. PREDICTION_AFTER_DRAW
        p_late_cap = copy.deepcopy(p)
        p_late_cap["PREDICTION_CAPTURE_TIME"] = "2099-01-01T00:00:00+08:00"
        self.assert_rejected([p_late_cap], [o], "PREDICTION_AFTER_DRAW", ticket_count=2)

        # 10. DRAW_SET_MISMATCH
        self.assert_rejected(
            [p],
            [o],
            "DRAW_SET_MISMATCH",
            ticket_count=2,
            expected_draw_ids=["199000002"],
        )

        # 11. MIXED_EXPERIMENTS
        p_diff_exp = copy.deepcopy(p)
        p_diff_exp["EXPERIMENT_ID"] = "OTHER_EXPERIMENT"
        self.assert_rejected([p_diff_exp], [o], "MIXED_EXPERIMENTS", ticket_count=2)

        # 12. MIXED_TICKET_COUNTS (draw 1 has 2 tickets, draw 2 has 3 tickets)
        p_m2, o_m2 = synthetic_portfolio_draw("199000001", ticket_count=2)
        p_m3, o_m3 = synthetic_portfolio_draw("199000002", ticket_count=3)
        self.assert_rejected(
            [p_m2, p_m3],
            [o_m2, o_m3],
            "MIXED_TICKET_COUNTS",
            ticket_count=2,
            expected_draw_ids=["199000001", "199000002"],
        )
        # Prediction tickets count != contract ticket_count
        self.assert_rejected(
            [p_m2],
            [o_m2],
            "MIXED_TICKET_COUNTS",
            ticket_count=3,
            expected_draw_ids=["199000001"],
        )

        # 13. HINDSIGHT_TARGET_REUSE
        p_hind, o_hind = synthetic_portfolio_draw("102000010", ticket_count=2)
        self.assert_rejected(
            [p_hind],
            [o_hind],
            "HINDSIGHT_TARGET_REUSE",
            ticket_count=2,
            expected_draw_ids=["102000010"],
        )

        # 14. FALSE_SUCCESS_CLAIM
        p_false_claim = copy.deepcopy(p)
        p_false_claim["PREDICTIVE_SUCCESS_IMPROVEMENT"] = "ESTABLISHED"
        self.assert_rejected([p_false_claim], [o], "FALSE_SUCCESS_CLAIM", ticket_count=2)
        p_false_claim2 = copy.deepcopy(p)
        p_false_claim2["FALSE_SUCCESS_CLAIM"] = True
        self.assert_rejected([p_false_claim2], [o], "FALSE_SUCCESS_CLAIM", ticket_count=2)

        # 15. UNEXPECTED_FIELD
        p_unexp = copy.deepcopy(p)
        p_unexp["UNKNOWN_EXTRA_PARAMETER"] = "unauthorized"
        self.assert_rejected([p_unexp], [o], "UNEXPECTED_FIELD", ticket_count=2)

        # 16. INCORRECT_BASELINE_NORMALIZATION
        with patch.object(scorer, "comb", return_value=1):
            with self.assertRaises(scorer.ContractError) as ctx:
                scorer.portfolio_exact_baseline(synthetic_tickets(2))
            self.assertEqual(ctx.exception.code, "INCORRECT_BASELINE_NORMALIZATION")

    def test_alternative_ticket_field_names(self):
        # Supports PORTFOLIO_PREDICTED_NUMBERS and TICKETS as alternatives to PREDICTED_TICKETS
        for field in ("PORTFOLIO_PREDICTED_NUMBERS", "TICKETS"):
            p, o = synthetic_portfolio_draw(ticket_count=2)
            tickets = p.pop("PREDICTED_TICKETS")
            p[field] = tickets
            result = evaluate_portfolio([p], [o], ticket_count=2)
            self.assertEqual(result["TICKET_COUNT"], 2)

    def test_python39_syntax(self):
        ast.parse(SOURCE.read_text(), feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
