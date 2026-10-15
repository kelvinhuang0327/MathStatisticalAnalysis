"""Synthetic-only focused contract tests; no real prediction or result fixtures."""

import ast
import copy
import importlib.util
import math
from fractions import Fraction
from pathlib import Path
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[2] / "tools" / "score_biglotto_prospective_r1.py"
SPEC = importlib.util.spec_from_file_location("prospective_r1_under_test", SOURCE)
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def synthetic(draw="199000001", hits=3):
    prediction = {
        "EXPERIMENT_ID": "SYNTHETIC_ONLY_R1",
        "DRAW_ID": draw,
        "SIX_PREDICTED_NUMBERS": [1, 2, 3, 4, 5, 6],
        "STRATEGY_IDENTITY": "synthetic-no-strategy@version:1",
        "INPUT_SNAPSHOT_SHA256": "a" * 64,
        "INPUT_CUTOFF": "2098-12-30T00:00:00+08:00",
        "PREDICTION_CAPTURE_ID": "synthetic-capture-" + draw,
        "PREDICTION_CAPTURE_TIME": "2098-12-31T00:00:00+08:00",
        "PREDRAW_EVIDENCE_LOCATOR": "synthetic://unverified/" + draw,
    }
    outcome = {
        "DRAW_ID": draw,
        "SIX_OFFICIAL_MAIN_NUMBERS": list(range(1, hits + 1)) + list(range(7, 13 - hits)),
        "DRAW_TIME": "2099-01-01T00:00:00+08:00",
        "OFFICIAL_RESULT_SOURCE": "synthetic://not-an-official-result/" + draw,
    }
    return prediction, outcome


def evaluate(predictions, outcomes, targets=None, **kwargs):
    contract = {
        "experiment_id": "SYNTHETIC_ONLY_R1",
        "strategy_identity": "synthetic-no-strategy@version:1",
        "expected_draw_ids": targets if targets is not None else ["199000001"],
    }
    contract.update(kwargs)
    return scorer.score_biglotto_prospective(predictions, outcomes, **contract)


class ProspectiveScoreTests(unittest.TestCase):
    def assert_rejected(self, predictions, outcomes, code, **kwargs):
        with self.assertRaises(scorer.ContractError) as caught:
            evaluate(predictions, outcomes, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_valid_single_draw(self):
        prediction, outcome = synthetic()
        result = evaluate([prediction], [outcome])
        self.assertEqual(result["TARGET_COUNT"], 1)
        self.assertEqual(result["HIT_HISTOGRAM_0_TO_6"], [0, 0, 0, 1, 0, 0, 0])
        self.assertEqual(result["MEAN_HITS"], 3)
        self.assertEqual(result["FIXED_EXPERIMENT_ID"], "SYNTHETIC_ONLY_R1")
        self.assertEqual(result["PER_DRAW"], [{"DRAW_ID": "199000001", "HIT_COUNT": 3}])

    def test_valid_multiple_draws_all_hit_counts_and_full_histogram(self):
        pairs = [synthetic("19900000" + str(k + 1), k) for k in range(7)]
        predictions = [p for p, _ in pairs]
        outcomes = [o for _, o in pairs]
        targets = [p["DRAW_ID"] for p in predictions]
        result = evaluate(predictions[::-1], outcomes[::-1], targets)
        self.assertEqual(result["TARGET_COUNT"], 7)
        self.assertEqual(result["HIT_HISTOGRAM_0_TO_6"], [1] * 7)
        self.assertEqual(result["MEAN_HITS"], 3)
        self.assertEqual([r["HIT_COUNT"] for r in result["PER_DRAW"]], list(range(7)))
        self.assertEqual(result["BASELINE"]["DRAW_IDS"], targets)
        self.assertEqual(result["BASELINE"]["TICKETS_PER_DRAW"], 1)
        self.assertAlmostEqual(sum(result["BASELINE"]["EXPECTED_HIT_HISTOGRAM_0_TO_6"]), 7)

    def test_hit_count_zero(self):
        p, o = synthetic(hits=0)
        self.assertEqual(evaluate([p], [o])["HIT_HISTOGRAM_0_TO_6"], [1, 0, 0, 0, 0, 0, 0])

    def test_hit_count_six(self):
        p, o = synthetic(hits=6)
        self.assertEqual(evaluate([p], [o])["HIT_HISTOGRAM_0_TO_6"], [0, 0, 0, 0, 0, 0, 1])

    def test_number_order_is_set_semantics_and_inputs_are_unchanged(self):
        p, o = synthetic()
        p["SIX_PREDICTED_NUMBERS"].reverse()
        o["SIX_OFFICIAL_MAIN_NUMBERS"].reverse()
        original = copy.deepcopy((p, o))
        self.assertEqual(evaluate([p], [o])["MEAN_HITS"], 3)
        self.assertEqual((p, o), original)

    def test_fail_closed_prediction_matrix(self):
        cases = [
            ("MISSING_CUTOFF", "INPUT_CUTOFF", None),
            ("MISSING_CUTOFF", "INPUT_CUTOFF", ""),
            ("MISSING_CAPTURE_ID", "PREDICTION_CAPTURE_ID", None),
            ("MISSING_PREDRAW_EVIDENCE", "PREDRAW_EVIDENCE_LOCATOR", None),
            ("MISSING_PREDRAW_EVIDENCE", "PREDRAW_EVIDENCE_LOCATOR", "  "),
            ("MISSING_FIELD", "PREDICTION_CAPTURE_TIME", None),
            ("MIXED_EXPERIMENTS", "EXPERIMENT_ID", "another-experiment"),
            ("WRONG_STRATEGY_IDENTITY", "STRATEGY_IDENTITY", "another@version:2"),
            ("INVALID_SNAPSHOT_SHA256", "INPUT_SNAPSHOT_SHA256", "abc"),
            ("INVALID_TIMESTAMP", "INPUT_CUTOFF", "2098-12-30T00:00:00"),
            ("INVALID_TIMESTAMP", "INPUT_CUTOFF", "not-a-date"),
            ("TARGET_INSIDE_INPUT", "INPUT_CUTOFF", "2099-01-01T00:00:00+08:00"),
            ("TARGET_INSIDE_INPUT", "INPUT_CUTOFF", "2099-01-02T00:00:00+08:00"),
            ("PREDICTION_AFTER_DRAW", "PREDICTION_CAPTURE_TIME", "2099-01-01T00:00:00+08:00"),
            ("PREDICTION_AFTER_DRAW", "PREDICTION_CAPTURE_TIME", "2099-01-02T00:00:00+08:00"),
            ("CUTOFF_NOT_BEFORE_CAPTURE", "INPUT_CUTOFF", "2098-12-31T00:00:00+08:00"),
            ("CUTOFF_NOT_BEFORE_CAPTURE", "INPUT_CUTOFF", "2098-12-31T01:00:00+08:00"),
            ("TARGET_INSIDE_INPUT", "INPUT_DRAW_IDS", ["199000001"]),
            ("TARGET_INSIDE_INPUT", "INPUT_DRAW_IDS", ["199000002"]),
            ("INVALID_INPUT_DRAW_IDS", "INPUT_DRAW_IDS", ["198000001", "198000001"]),
            ("INVALID_INPUT_DRAW_IDS", "INPUT_DRAW_IDS", [["198000001"]]),
            ("UNEXPECTED_FIELD", "EVIDENCE_STATUS", "VERIFIED"),
            ("INVALID_DRAW_ID", "DRAW_ID", "19900001"),
            ("INVALID_FIELD", "DRAW_ID", 199000001),
        ]
        for code, field, value in cases:
            with self.subTest(code=code, field=field, value=value):
                p, o = synthetic()
                if value is None:
                    del p[field]
                else:
                    p[field] = value
                self.assert_rejected([p], [o], code)

    def test_six_number_validation_on_both_record_types(self):
        cases = [
            ([1, 2, 3, 4, 5, 5], "DUPLICATE_NUMBERS"),
            ([0, 2, 3, 4, 5, 6], "OUT_OF_RANGE_NUMBER"),
            ([1, 2, 3, 4, 5, 50], "OUT_OF_RANGE_NUMBER"),
            ([True, 2, 3, 4, 5, 6], "INVALID_NUMBER_TYPE"),
            ([1.0, 2, 3, 4, 5, 6], "INVALID_NUMBER_TYPE"),
            (["1", 2, 3, 4, 5, 6], "INVALID_NUMBER_TYPE"),
            ([1, 2, 3, 4, 5], "INVALID_NUMBER_COUNT"),
            ([], "INVALID_NUMBER_COUNT"),
            ("1,2,3,4,5,6", "INVALID_NUMBERS"),
            ([1, 2, 3, 4, 5, 6, 7], "MULTIPLE_TICKETS_WITHOUT_CONTRACT"),
            ([[1, 2, 3, 4, 5, 6]], "MULTIPLE_TICKETS_WITHOUT_CONTRACT"),
            (list(range(1, 13)), "MULTIPLE_TICKETS_WITHOUT_CONTRACT"),
        ]
        for side, field in [(0, "SIX_PREDICTED_NUMBERS"), (1, "SIX_OFFICIAL_MAIN_NUMBERS")]:
            for numbers, code in cases:
                with self.subTest(side=side, numbers=numbers):
                    pair = synthetic()
                    pair[side][field] = numbers
                    self.assert_rejected([pair[0]], [pair[1]], code)

    def test_duplicate_prediction_draw(self):
        p, o = synthetic()
        second = copy.deepcopy(p)
        second["PREDICTION_CAPTURE_ID"] = "different-capture"
        second["SIX_PREDICTED_NUMBERS"] = [7, 8, 9, 10, 11, 12]
        self.assert_rejected([p, second], [o], "DUPLICATE_DRAW")

    def test_duplicate_official_draw(self):
        p, o = synthetic()
        self.assert_rejected([p], [o, copy.deepcopy(o)], "DUPLICATE_DRAW")

    def test_duplicate_contract_draw(self):
        p, o = synthetic()
        self.assert_rejected([p], [o], "DUPLICATE_DRAW", targets=[p["DRAW_ID"]] * 2)

    def test_full_fixed_draw_set_is_required_no_best_draw_selection(self):
        p, o = synthetic()
        p2, o2 = synthetic("199000002")
        for predictions, outcomes, targets in [
            ([], [o], [p["DRAW_ID"]]),
            ([p], [], [p["DRAW_ID"]]),
            ([p, p2], [o], [p["DRAW_ID"]]),
            ([p], [o, o2], [p["DRAW_ID"]]),
            ([p], [o], [p["DRAW_ID"], p2["DRAW_ID"]]),
        ]:
            with self.subTest(predictions=len(predictions), outcomes=len(outcomes), targets=targets):
                self.assert_rejected(predictions, outcomes, "DRAW_SET_MISMATCH", targets=targets)

    def test_hindsight_target_reuse_in_every_entry_point(self):
        p, o = synthetic("102000010")
        self.assert_rejected([p], [o], "HINDSIGHT_TARGET_REUSE", targets=["102000010"])
        good_p, good_o = synthetic()
        self.assert_rejected([p], [good_o], "HINDSIGHT_TARGET_REUSE")
        self.assert_rejected([good_p], [o], "HINDSIGHT_TARGET_REUSE")

    def test_unverified_capture_timestamp_remains_diagnostic(self):
        p, o = synthetic(hits=6)
        p["PREDRAW_EVIDENCE_LOCATOR"] = "https://example.invalid/claimed-trusted-receipt"
        result = evaluate([p], [o])
        self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        self.assertIs(result["CAPTURE_TIME_INDEPENDENTLY_VERIFIED"], False)
        self.assertEqual(result["PREDICTIVE_SUCCESS_EVIDENCE"], "NOT_ESTABLISHED")
        self.assertEqual(result["ORIGINAL_HISTORICAL_PARITY"], "NOT_VERIFIED")
        for key in ["IMPROVED_WIN_PROBABILITY", "HISTORICAL_PARITY", "SIGNIFICANT_LIFT",
                    "PROVEN_ROI_INCREASE"]:
            self.assertNotIn(key, result)

    def test_six_number_baseline_exact_normalization_and_mean(self):
        baseline = scorer.six_number_baseline()
        probabilities = [Fraction(p) for p in baseline["EXACT_PROBABILITIES_0_TO_6"]]
        self.assertEqual(sum(probabilities), 1)
        self.assertEqual(sum(k * p for k, p in enumerate(probabilities)), Fraction(36, 49))
        self.assertEqual(probabilities[0], Fraction(math.comb(43, 6), math.comb(49, 6)))
        self.assertEqual(probabilities[6], Fraction(1, 13983816))
        # Independent recurrence checks every cell, not a copy of the implementation formula.
        for k in range(6):
            self.assertEqual(probabilities[k + 1] / probabilities[k],
                             Fraction((6 - k) ** 2, (k + 1) * (38 + k)))
        self.assertAlmostEqual(sum(baseline["PROBABILITIES_0_TO_6"]), 1)
        self.assertEqual(baseline["EXACT_MEAN_HITS"], "36/49")

    def test_baseline_internal_guard_rejects_corrupted_combinatorics(self):
        with patch.object(scorer, "comb", return_value=1):
            with self.assertRaises(ArithmeticError):
                scorer.six_number_baseline()

    def test_baseline_same_contract_and_deterministic(self):
        p, o = synthetic()
        result = evaluate([p], [o])
        self.assertEqual(result, evaluate([p], [o]))
        self.assertEqual(result["BASELINE"]["DRAW_IDS"], result["FIXED_DRAW_IDS"])
        self.assertEqual(result["BASELINE"]["TICKETS_PER_DRAW"], result["TICKETS_PER_DRAW"])
        self.assertEqual(result["BASELINE"]["INPUT_CUTOFF_RULE"],
                         "SAME_AS_STRATEGY; cutoff < capture < draw")
        self.assertIn("six main numbers only", result["BASELINE"]["SUCCESS_EVENT"])

    def test_special_number_is_not_accepted_as_a_main_hit_or_extra_schema(self):
        p, o = synthetic(hits=0)
        self.assertEqual(evaluate([p], [o])["MEAN_HITS"], 0)
        o["SPECIAL_NUMBER"] = 1
        self.assert_rejected([p], [o], "UNEXPECTED_FIELD")

    def test_timezone_offsets_are_compared_as_instants(self):
        p, o = synthetic()
        p["PREDICTION_CAPTURE_TIME"] = "2098-12-31T16:00:00Z"
        self.assert_rejected([p], [o], "PREDICTION_AFTER_DRAW")
        p["PREDICTION_CAPTURE_TIME"] = "2098-12-31T15:59:59Z"
        self.assertEqual(evaluate([p], [o])["MEAN_HITS"], 3)

    def test_input_inventory_allows_only_unique_prior_draws(self):
        p, o = synthetic()
        p["INPUT_DRAW_IDS"] = ["102000010", "198000001"]
        self.assertEqual(evaluate([p], [o])["TARGET_COUNT"], 1)

    def test_official_fields_are_required_and_typed(self):
        for field in ["DRAW_TIME", "OFFICIAL_RESULT_SOURCE", "SIX_OFFICIAL_MAIN_NUMBERS"]:
            p, o = synthetic()
            del o[field]
            self.assert_rejected([p], [o], "MISSING_FIELD")
        p, o = synthetic()
        o["OFFICIAL_RESULT_SOURCE"] = ""
        self.assert_rejected([p], [o], "INVALID_FIELD")
        o["OFFICIAL_RESULT_SOURCE"] = "synthetic://source"
        o["DRAW_TIME"] = "2099-01-01"
        self.assert_rejected([p], [o], "INVALID_TIMESTAMP")

    def test_contract_and_record_containers_fail_closed(self):
        p, o = synthetic()
        self.assert_rejected([p], [o], "INVALID_DRAW_SET", targets=[])
        self.assert_rejected([p], [o], "WRONG_STRATEGY_IDENTITY", strategy_identity="UNKNOWN")
        self.assert_rejected(p, [o], "INVALID_RECORDS")
        self.assert_rejected([None], [o], "INVALID_RECORD")
        self.assert_rejected([p], [None], "INVALID_RECORD")

    def test_duplicate_capture_id_is_rejected(self):
        p, o = synthetic()
        p2, o2 = synthetic("199000002")
        p2["PREDICTION_CAPTURE_ID"] = p["PREDICTION_CAPTURE_ID"]
        self.assert_rejected([p, p2], [o, o2], "DUPLICATE_CAPTURE_ID",
                             targets=[p["DRAW_ID"], p2["DRAW_ID"]])

    def test_python39_syntax(self):
        ast.parse(SOURCE.read_text(), feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
