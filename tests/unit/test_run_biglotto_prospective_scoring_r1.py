"""Synthetic-only integration tests for prospective BIG_LOTTO scoring CLI and adapter.

Tests run_biglotto_prospective_scoring and CLI entry point against Gate A through Gate E.
Standard library only; no real prediction generation, network access, or DB mutation.
"""

from __future__ import annotations

import ast
import copy
import io
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.run_biglotto_prospective_scoring_r1 as runner_mod
from tools.run_biglotto_prospective_scoring_r1 import (
    ContractError,
    main,
    run_biglotto_prospective_scoring,
)
import tools.score_biglotto_prospective_r1 as original_scorer

CLI_PATH = REPO_ROOT / "tools" / "run_biglotto_prospective_scoring_r1.py"


def synthetic(draw: str = "199000001", hits: int = 3):
    prediction = {
        "EXPERIMENT_ID": "SYNTHETIC_CLI_R1",
        "DRAW_ID": draw,
        "SIX_PREDICTED_NUMBERS": [1, 2, 3, 4, 5, 6],
        "STRATEGY_IDENTITY": "synthetic-cli-strategy@version:1",
        "INPUT_SNAPSHOT_SHA256": "f" * 64,
        "INPUT_CUTOFF": "2098-12-30T00:00:00+08:00",
        "PREDICTION_CAPTURE_ID": "synthetic-cli-capture-" + draw,
        "PREDICTION_CAPTURE_TIME": "2098-12-31T00:00:00+08:00",
        "PREDRAW_EVIDENCE_LOCATOR": "synthetic://unverified/" + draw,
    }
    outcome = {
        "DRAW_ID": draw,
        "SIX_OFFICIAL_MAIN_NUMBERS": list(range(1, hits + 1)) + list(range(7, 13 - hits)),
        "DRAW_TIME": "2099-01-01T00:00:00+08:00",
        "OFFICIAL_RESULT_SOURCE": "synthetic://official-source/" + draw,
    }
    return prediction, outcome


def synthetic_contract(draws=None, **kwargs):
    c = {
        "experiment_id": "SYNTHETIC_CLI_R1",
        "strategy_identity": "synthetic-cli-strategy@version:1",
        "expected_draw_ids": draws if draws is not None else ["199000001"],
    }
    c.update(kwargs)
    return c


class RunBigLottoProspectiveScoringTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_json(self, name: str, data) -> Path:
        p = self.temp_path / name
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return p

    def assert_rejected(self, predictions, outcomes, contract, expected_code: str, **kwargs):
        with self.assertRaises(ContractError) as caught:
            run_biglotto_prospective_scoring(predictions, outcomes, contract, **kwargs)
        self.assertEqual(caught.exception.code, expected_code)

    # --- Gate A: Genuine reuse of original scoring tool ---
    def test_gate_a_original_scorer_invoked_directly(self):
        p, o = synthetic()
        c = synthetic_contract()
        with patch.object(
            runner_mod.scorer_engine,
            "score_biglotto_prospective",
            wraps=runner_mod.scorer_engine.score_biglotto_prospective,
        ) as mock_scorer:
            result = run_biglotto_prospective_scoring([p], [o], c)
            self.assertTrue(mock_scorer.called)
            self.assertEqual(mock_scorer.call_count, 1)
        self.assertEqual(result["TARGET_COUNT"], 1)
        self.assertEqual(result["HIT_HISTOGRAM_0_TO_6"], [0, 0, 0, 1, 0, 0, 0])

    # --- Gate B & Gate C: CLI Execution, Output Schema, Hit Counts, Baseline ---
    def test_gate_b_c_single_draw_in_memory_and_file_paths(self):
        p, o = synthetic(hits=3)
        c = synthetic_contract()

        # In-memory execution
        res_mem = run_biglotto_prospective_scoring([p], [o], c)
        self.assertEqual(res_mem["EXPERIMENT_ID"], "SYNTHETIC_CLI_R1")
        self.assertEqual(res_mem["TARGET_COUNT"], 1)
        self.assertEqual(res_mem["HIT_HISTOGRAM_0_TO_6"], [0, 0, 0, 1, 0, 0, 0])
        self.assertEqual(res_mem["MEAN_HITS"], 3.0)
        self.assertEqual(res_mem["BASELINE_IDENTITY"], "HYPERGEOMETRIC_6_OF_49_SINGLE_TICKET")
        self.assertEqual(res_mem["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        self.assertIs(res_mem["CAPTURE_TIME_INDEPENDENTLY_VERIFIED"], False)
        self.assertEqual(res_mem["ORIGINAL_HISTORICAL_PARITY"], "NOT_VERIFIED")
        self.assertEqual(res_mem["PREDICTIVE_SUCCESS_EVIDENCE"], "NOT_ESTABLISHED")

        # File paths execution
        p_file = self._write_json("preds.json", [p])
        o_file = self._write_json("outs.json", [o])
        c_file = self._write_json("contract.json", c)

        res_file = run_biglotto_prospective_scoring(p_file, o_file, c_file)
        self.assertEqual(res_mem, res_file)

    def test_gate_c_all_hit_counts_histogram_and_baseline_properties(self):
        pairs = [synthetic("19900000" + str(k + 1), k) for k in range(7)]
        predictions = [p for p, _ in pairs]
        outcomes = [o for _, o in pairs]
        targets = [p["DRAW_ID"] for p in predictions]
        c = synthetic_contract(draws=targets)

        result = run_biglotto_prospective_scoring(predictions, outcomes, c)
        self.assertEqual(result["TARGET_COUNT"], 7)
        self.assertEqual(result["HIT_HISTOGRAM_0_TO_6"], [1] * 7)
        self.assertEqual(result["MEAN_HITS"], 3.0)
        self.assertEqual([r["HIT_COUNT"] for r in result["PER_DRAW"]], list(range(7)))
        self.assertEqual(result["BASELINE_IDENTITY"], "HYPERGEOMETRIC_6_OF_49_SINGLE_TICKET")
        self.assertEqual(result["BASELINE"]["EXACT_MEAN_HITS"], "36/49")
        self.assertAlmostEqual(result["BASELINE"]["MEAN_HITS"], 36 / 49)

    def test_input_immutability(self):
        p, o = synthetic(hits=4)
        c = synthetic_contract()
        p_copy = copy.deepcopy(p)
        o_copy = copy.deepcopy(o)
        c_copy = copy.deepcopy(c)

        run_biglotto_prospective_scoring([p], [o], c)
        self.assertEqual(p, p_copy)
        self.assertEqual(o, o_copy)
        self.assertEqual(c, c_copy)

    # --- Gate B: CLI Entry Point (main) via arguments and stdout ---
    def test_gate_b_cli_main_flags_mode(self):
        p, o = synthetic(hits=2)
        c = synthetic_contract()
        p_file = self._write_json("preds.json", [p])
        o_file = self._write_json("outs.json", [o])
        c_file = self._write_json("contract.json", c)

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
            ret = main([
                "--predictions", str(p_file),
                "--outcomes", str(o_file),
                "--contract", str(c_file),
            ])
        self.assertEqual(ret, 0)
        out_json = json.loads(stdout_buf.getvalue())
        self.assertEqual(out_json["TARGET_COUNT"], 1)
        self.assertEqual(out_json["HIT_HISTOGRAM_0_TO_6"], [0, 0, 1, 0, 0, 0, 0])
        self.assertEqual(out_json["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")

    def test_gate_b_cli_main_positional_mode(self):
        p, o = synthetic(hits=5)
        c = synthetic_contract()
        p_file = self._write_json("preds.json", [p])
        o_file = self._write_json("outs.json", [o])
        c_file = self._write_json("contract.json", c)

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
            ret = main([str(p_file), str(o_file), str(c_file)])
        self.assertEqual(ret, 0)
        out_json = json.loads(stdout_buf.getvalue())
        self.assertEqual(out_json["HIT_HISTOGRAM_0_TO_6"], [0, 0, 0, 0, 0, 1, 0])

    def test_gate_b_cli_main_combined_file_mode(self):
        p, o = synthetic(hits=1)
        combined = {
            "predictions": [p],
            "outcomes": [o],
            "contract": synthetic_contract(),
        }
        comb_file = self._write_json("combined.json", combined)

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
            ret = main([str(comb_file)])
        self.assertEqual(ret, 0)
        out_json = json.loads(stdout_buf.getvalue())
        self.assertEqual(out_json["HIT_HISTOGRAM_0_TO_6"], [0, 1, 0, 0, 0, 0, 0])

    def test_gate_b_cli_missing_args_fails(self):
        stderr_buf = io.StringIO()
        with patch("sys.stderr", stderr_buf):
            ret = main([])
        self.assertEqual(ret, 1)
        self.assertIn("WRONG_INPUT_FORMAT", stderr_buf.getvalue())

    def test_gate_b_cli_subprocess_execution(self):
        p, o = synthetic(hits=6)
        c = synthetic_contract()
        p_file = self._write_json("preds.json", [p])
        o_file = self._write_json("outs.json", [o])
        c_file = self._write_json("contract.json", c)

        proc = subprocess.run(
            [
                sys.executable,
                str(CLI_PATH),
                "--predictions", str(p_file),
                "--outcomes", str(o_file),
                "--contract", str(c_file),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        out_json = json.loads(proc.stdout)
        self.assertEqual(out_json["HIT_HISTOGRAM_0_TO_6"], [0, 0, 0, 0, 0, 0, 1])
        self.assertEqual(out_json["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")

    # --- Gate D: Diagnostic Only and Absence of Verification Claims ---
    def test_gate_d_diagnostic_only_evidence_status_preserved(self):
        p, o = synthetic(hits=6)
        c = synthetic_contract()
        result = run_biglotto_prospective_scoring([p], [o], c)
        self.assertEqual(result["EVIDENCE_STATUS"], "DIAGNOSTIC_ONLY")
        self.assertIs(result["CAPTURE_TIME_INDEPENDENTLY_VERIFIED"], False)
        self.assertEqual(result["ORIGINAL_HISTORICAL_PARITY"], "NOT_VERIFIED")
        self.assertEqual(result["PREDICTIVE_SUCCESS_EVIDENCE"], "NOT_ESTABLISHED")
        for forbidden in (
            "ORIGINAL_PARITY",
            "PREDICTIVE_IMPROVEMENT",
            "SIGNIFICANT_LIFT",
            "ROI_IMPROVED",
            "PROVEN_ROI_INCREASE",
        ):
            self.assertNotIn(forbidden, result)

    # --- Gate E: Complete Fail-Closed Matrix (All 14 Cases) ---

    # 1. WRONG_INPUT_FORMAT
    def test_gate_e_01_wrong_input_format(self):
        p, o = synthetic()
        c = synthetic_contract()
        # Non-existent file
        self.assert_rejected("non_existent_file.json", [o], c, "WRONG_INPUT_FORMAT")
        # Non-array predictions
        self.assert_rejected({"DRAW_ID": "199000001"}, [o], c, "WRONG_INPUT_FORMAT")
        # Non-array outcomes
        self.assert_rejected([p], {"DRAW_ID": "199000001"}, c, "WRONG_INPUT_FORMAT")
        # Non-mapping contract
        self.assert_rejected([p], [o], "not-a-mapping", "WRONG_INPUT_FORMAT")
        # Missing contract keys
        bad_c = copy.deepcopy(c)
        del bad_c["experiment_id"]
        self.assert_rejected([p], [o], bad_c, "WRONG_INPUT_FORMAT")
        # Malformed JSON file
        bad_json = self.temp_path / "bad.json"
        bad_json.write_text("{bad: json}", encoding="utf-8")
        self.assert_rejected(bad_json, [o], c, "WRONG_INPUT_FORMAT")

    # 2. DUPLICATE_DRAW
    def test_gate_e_02_duplicate_draw(self):
        p, o = synthetic()
        c = synthetic_contract()
        p2 = copy.deepcopy(p)
        p2["PREDICTION_CAPTURE_ID"] = "diff-cap-id"
        self.assert_rejected([p, p2], [o], c, "DUPLICATE_DRAW")
        self.assert_rejected([p], [o, copy.deepcopy(o)], c, "DUPLICATE_DRAW")
        bad_c = synthetic_contract(draws=["199000001", "199000001"])
        self.assert_rejected([p], [o], bad_c, "DUPLICATE_DRAW")

    # 3. INVALID_TICKET
    def test_gate_e_03_invalid_ticket(self):
        c = synthetic_contract()
        cases = [
            ([1, 2, 3, 4, 5, 5]),      # duplicate numbers
            ([0, 2, 3, 4, 5, 6]),      # out of range low
            ([1, 2, 3, 4, 5, 50]),     # out of range high
            ([1.0, 2, 3, 4, 5, 6]),    # invalid type float
            (["1", 2, 3, 4, 5, 6]),    # invalid type string
            ([1, 2, 3, 4, 5]),         # wrong count (5)
            ([1, 2, 3, 4, 5, 6, 7]),   # multiple / excess tickets
            ([[1, 2, 3, 4, 5, 6]]),    # nested ticket
            ("1, 2, 3, 4, 5, 6"),      # string instead of list
        ]
        for numbers in cases:
            with self.subTest(numbers=numbers):
                p, o = synthetic()
                p["SIX_PREDICTED_NUMBERS"] = numbers
                self.assert_rejected([p], [o], c, "INVALID_TICKET")

    # 4. MISSING_INPUT_CUTOFF
    def test_gate_e_04_missing_input_cutoff(self):
        c = synthetic_contract()
        p, o = synthetic()
        del p["INPUT_CUTOFF"]
        self.assert_rejected([p], [o], c, "MISSING_INPUT_CUTOFF")
        p2, o2 = synthetic()
        p2["INPUT_CUTOFF"] = ""
        self.assert_rejected([p2], [o2], c, "MISSING_INPUT_CUTOFF")

    # 5. CUTOFF_AFTER_TARGET
    def test_gate_e_05_cutoff_after_target(self):
        c = synthetic_contract()
        p, o = synthetic()
        # Cutoff at draw time
        p["INPUT_CUTOFF"] = "2099-01-01T00:00:00+08:00"
        self.assert_rejected([p], [o], c, "CUTOFF_AFTER_TARGET")
        # Cutoff after draw time
        p2, o2 = synthetic()
        p2["INPUT_CUTOFF"] = "2099-01-02T00:00:00+08:00"
        self.assert_rejected([p2], [o2], c, "CUTOFF_AFTER_TARGET")
        # Cutoff not before capture time
        p3, o3 = synthetic()
        p3["INPUT_CUTOFF"] = "2098-12-31T00:00:00+08:00"
        self.assert_rejected([p3], [o3], c, "CUTOFF_AFTER_TARGET")
        # Target inside input draw IDs
        p4, o4 = synthetic()
        p4["INPUT_DRAW_IDS"] = ["199000001"]
        self.assert_rejected([p4], [o4], c, "CUTOFF_AFTER_TARGET")

    # 6. PREDICTION_AFTER_DRAW
    def test_gate_e_06_prediction_after_draw(self):
        c = synthetic_contract()
        p, o = synthetic()
        p["PREDICTION_CAPTURE_TIME"] = "2099-01-01T00:00:00+08:00"
        self.assert_rejected([p], [o], c, "PREDICTION_AFTER_DRAW")
        p2, o2 = synthetic()
        p2["PREDICTION_CAPTURE_TIME"] = "2099-01-02T00:00:00+08:00"
        self.assert_rejected([p2], [o2], c, "PREDICTION_AFTER_DRAW")

    # 7. MISSING_CAPTURE_ID
    def test_gate_e_07_missing_capture_id(self):
        c = synthetic_contract()
        p, o = synthetic()
        del p["PREDICTION_CAPTURE_ID"]
        self.assert_rejected([p], [o], c, "MISSING_CAPTURE_ID")
        p2, o2 = synthetic()
        p2["PREDICTION_CAPTURE_ID"] = "  "
        self.assert_rejected([p2], [o2], c, "MISSING_CAPTURE_ID")

    # 8. HINDSIGHT_TARGET_REUSE
    def test_gate_e_08_hindsight_target_reuse(self):
        p, o = synthetic(draw="102000010")
        c = synthetic_contract(draws=["102000010"])
        self.assert_rejected([p], [o], c, "HINDSIGHT_TARGET_REUSE")

    # 9. MIXED_EXPERIMENTS
    def test_gate_e_09_mixed_experiments(self):
        c = synthetic_contract()
        p, o = synthetic()
        p["EXPERIMENT_ID"] = "OTHER_EXPERIMENT_ID"
        self.assert_rejected([p], [o], c, "MIXED_EXPERIMENTS")

    # 10. FALSE_VERIFIED_STATUS
    def test_gate_e_10_false_verified_status(self):
        p, o = synthetic()
        # In contract
        for key in ("EVIDENCE_STATUS", "ORIGINAL_PARITY", "ORIGINAL_HISTORICAL_PARITY"):
            bad_c = synthetic_contract(**{key: "VERIFIED"})
            self.assert_rejected([p], [o], bad_c, "FALSE_VERIFIED_STATUS")
        # In prediction
        p2, o2 = synthetic()
        p2["EVIDENCE_STATUS"] = "VERIFIED"
        self.assert_rejected([p2], [o2], synthetic_contract(), "FALSE_VERIFIED_STATUS")
        # In outcome
        p3, o3 = synthetic()
        o3["EVIDENCE_STATUS"] = "VERIFIED"
        self.assert_rejected([p3], [o3], synthetic_contract(), "FALSE_VERIFIED_STATUS")

    # 11. FALSE_SUCCESS_CLAIM
    def test_gate_e_11_false_success_claim(self):
        p, o = synthetic()
        # In contract
        for key in ("PREDICTIVE_IMPROVEMENT", "SIGNIFICANT_LIFT", "ROI_IMPROVED"):
            bad_c = synthetic_contract(**{key: True})
            self.assert_rejected([p], [o], bad_c, "FALSE_SUCCESS_CLAIM")
            bad_c_str = synthetic_contract(**{key: "PROVED"})
            self.assert_rejected([p], [o], bad_c_str, "FALSE_SUCCESS_CLAIM")
        # In prediction
        p2, o2 = synthetic()
        p2["SIGNIFICANT_LIFT"] = True
        self.assert_rejected([p2], [o2], synthetic_contract(), "FALSE_SUCCESS_CLAIM")
        # In outcome
        p3, o3 = synthetic()
        o3["ROI_IMPROVED"] = "TRUE"
        self.assert_rejected([p3], [o3], synthetic_contract(), "FALSE_SUCCESS_CLAIM")

    # 12. WRONG_BASELINE
    def test_gate_e_12_wrong_baseline(self):
        p, o = synthetic()
        # Wrong BASELINE_IDENTITY
        bad_c1 = synthetic_contract(BASELINE_IDENTITY="POISSON_MODEL")
        self.assert_rejected([p], [o], bad_c1, "WRONG_BASELINE")
        # Wrong MEAN_BASELINE
        bad_c2 = synthetic_contract(MEAN_BASELINE="50/49")
        self.assert_rejected([p], [o], bad_c2, "WRONG_BASELINE")
        # Overriding BASELINE
        bad_c3 = synthetic_contract(BASELINE={"CUSTOM": 123})
        self.assert_rejected([p], [o], bad_c3, "WRONG_BASELINE")

    # 13. SPECIAL_NUMBER_INCLUDED
    def test_gate_e_13_special_number_included(self):
        c = synthetic_contract()
        # Special number in outcome
        p, o = synthetic()
        o["SPECIAL_NUMBER"] = 7
        self.assert_rejected([p], [o], c, "SPECIAL_NUMBER_INCLUDED")
        # Special number in prediction
        p2, o2 = synthetic()
        p2["SPECIAL_NUMBER"] = 7
        self.assert_rejected([p2], [o2], c, "SPECIAL_NUMBER_INCLUDED")

    # 14. UNEXPECTED_OUTPUT_PATH
    def test_gate_e_14_unexpected_output_path(self):
        p, o = synthetic()
        c = synthetic_contract()
        # Passed to public function
        self.assert_rejected([p], [o], c, "UNEXPECTED_OUTPUT_PATH", output_path="/tmp/output.json")
        # Specified in contract
        bad_c = synthetic_contract(output_path="/tmp/output.json")
        self.assert_rejected([p], [o], bad_c, "UNEXPECTED_OUTPUT_PATH")
        # CLI flag --output
        p_file = self._write_json("preds.json", [p])
        o_file = self._write_json("outs.json", [o])
        c_file = self._write_json("contract.json", c)
        for flag in ("--output", "--out", "--output-path", "--output-file", "-o"):
            stderr_buf = io.StringIO()
            with patch("sys.stderr", stderr_buf):
                ret = main([
                    str(p_file), str(o_file), str(c_file),
                    flag, "/tmp/out.json"
                ])
            self.assertEqual(ret, 1)
            self.assertIn("UNEXPECTED_OUTPUT_PATH", stderr_buf.getvalue())

    # --- Python 3.9 Compatibility ---
    def test_python39_syntax(self):
        ast.parse(CLI_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
