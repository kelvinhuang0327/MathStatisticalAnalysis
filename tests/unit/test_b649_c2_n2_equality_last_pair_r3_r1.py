"""R3 identity and sealing seams only; no native gains or forbidden calls."""
import ast
import copy
import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("last_pair_r3", ROOT / "tools/b649_c2_n2_equality_last_pair_r3_r1.py")
r3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r3)


class LastPairR3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity, _, cls.provenance = r3.load_inputs()
        cls.pilot = r3.core.pilot_namespace()

    def fixture(self, *, same_bucket=False):
        h = [[0, r3.LEGAL - 4], [2, 4]] if same_bucket else [[0, r3.LEGAL - 6], [2, 3], [3, 3]]
        cij = 4 if same_bucket else 5
        exact, table = self.pilot["equality_count"](h, cij, complete=True)
        row = {**self.identity, "STATUS": "COMPLETE", "COUNTING_UNIT": "7_SET", "ARTIFACT_COMPLETE": True,
               "RAW_SINGLE_TICKETS": r3.RAW, "EXCLUDED_UNTOUCHED_TICKETS": 18, "LEGAL_SINGLE_TICKETS": r3.LEGAL,
               "COVERED_P": r3.COVERAGE, "COVERED_R": r3.COVERAGE - cij, "C_ij": cij,
               "HISTOGRAM_COMPLETE": True, "HISTOGRAM": h, "BUCKET_COUNT": len(h), "E": exact,
               "HISTOGRAM_SHA256": r3.core.sha(r3.core.compact(h)),
               "COMPLEMENTARY_BUCKET_TABLE": table, "COMPLEMENTARY_TABLE_SHA256": r3.core.sha(r3.core.compact(table))}
        return {"TASK_STATUS": "COMPLETE", "PAIR_IDENTITY": self.identity, "PAIR_RESULT": row,
                "C_ij": cij, "E": exact, "EXACT_EQUALITY_PAIR_COUNT": exact}

    def test_frozen_source_identity_and_7_set_unit(self):
        self.assertEqual(r3.core.sha((ROOT / r3.CORE_REL).read_bytes()), r3.CORE_SHA)
        self.assertEqual(r3.core.sha(r3.core.compact(self.identity["ORDERED_TICKETS"])), r3.ORDERED_SHA)
        self.assertEqual(self.provenance["START"]["COUNT"], 313263888)
        self.assertEqual(44751984 * 7, 313263888)
        with self.assertRaisesRegex(ValueError, "frozen gain core SHA"):
            r3.load_core(expected="0" * 64)
        for delta in ({"EXPECTED_COVERED_P_7_SET": 313263888}, {"C_ij": 1}):
            with self.assertRaisesRegex(ValueError, "source/unit identity"):
                r3.validate_identity({**self.identity, **delta})
        bad = self.fixture()
        bad["PAIR_RESULT"]["COUNTING_UNIT"] = "OUTCOME"
        with self.assertRaisesRegex(r3.core.StopBatch, "ACCOUNTING"):
            r3.independent_reparse(r3.encode(bad), bad)

    def test_removed_and_all_18_untouched_full_values(self):
        expected = [[1,2,3,4,5,21], [1,6,7,8,9,22], [2,6,10,11,12,23], [3,10,13,14,15,22],
                    [1,11,13,16,17,24], [4,6,14,16,18,25], [7,10,17,18,19,21], [2,8,13,19,20,25],
                    [3,7,12,16,20,26], [5,8,11,15,18,26], [5,9,12,14,19,24], [4,9,15,17,20,23],
                    [27,29,30,31,32,33], [27,34,35,36,37,38], [27,39,40,41,42,43],
                    [28,29,34,39,44,45], [28,30,35,40,46,47], [28,31,36,41,48,49]]
        self.assertEqual(self.identity["UNTOUCHED_TICKETS"], expected)
        self.assertEqual(self.identity["REMOVED_TICKETS"], [[32,37,42,44,46,48], [33,38,43,45,47,49]])
        for key in ("REMOVED_TICKETS", "UNTOUCHED_TICKETS", "ENGINE_TICKETS"):
            broken = copy.deepcopy(self.identity)
            broken[key][0][-1] -= 1
            with self.assertRaises(ValueError):
                r3.validate_identity(broken)
        # Native output uses engine order, which may differ from ordered slots.
        good = self.fixture()
        good["PAIR_RESULT"]["UNTOUCHED_TICKETS"] = sorted(expected)
        self.assertEqual(r3.independent_reparse(r3.encode(good), good), "PASS")
        good["PAIR_RESULT"]["UNTOUCHED_TICKETS"][0][-1] -= 1
        with self.assertRaisesRegex(r3.core.StopBatch, "TICKET_IDENTITY"):
            r3.independent_reparse(r3.encode(good), good)

    def test_integer_e_products_choose_two_and_float_precision(self):
        for same, expected in ((False, 9), (True, 6)):
            result = self.fixture(same_bucket=same)
            self.assertEqual(result["E"], expected)
            self.assertIs(type(result["E"]), int)
            self.assertEqual(r3.independent_reparse(r3.encode(result), result), "PASS")
        n = 2**54 + 3
        self.assertEqual(self.pilot["equality_count"]([[1,n],[2,n+1]], 3, complete=True)[0], n*(n+1))
        # Falsifiability: mutate the frozen formula through a fixture seam. The
        # independent reparse must reject, then pass after restoring it.
        with patch.object(r3.core.math, "comb", return_value=9):
            broken = self.fixture(same_bucket=True)
        with self.assertRaisesRegex(r3.core.StopBatch, "E_OR_SHA"):
            r3.independent_reparse(r3.encode(broken), broken)
        restored = self.fixture(same_bucket=True)
        self.assertEqual(r3.independent_reparse(r3.encode(restored), restored), "PASS")

    def test_compact_archive_reparse_and_capacity_preserve_bytes(self):
        result = self.fixture()
        with tempfile.TemporaryDirectory(prefix="b649-r3-focused-") as folder:
            path = Path(folder) / "result.json"
            r3.archive(result, path, folder)
            sealed = path.read_bytes()
            self.assertEqual(sealed, r3.encode(result))
            self.assertEqual(json.loads(sealed), result)
            self.assertEqual(sealed.count(b"\n"), 1)
            for key, value in (("E",10), ("C_ij",6), ("HISTOGRAM_SHA256","0"*64),
                               ("COMPLEMENTARY_TABLE_SHA256","0"*64), ("BUCKET_COUNT",2),
                               ("HISTOGRAM",[[0,r3.LEGAL-6],[2,3]])):
                broken = copy.deepcopy(result)
                broken["PAIR_RESULT"][key] = value
                with self.assertRaises(r3.core.StopBatch):
                    r3.archive(broken, path, folder)
                self.assertEqual(path.read_bytes(), sealed)
            for limits, reason in (({"result_limit":1},"RESULT_CAPACITY"), ({"temp_limit":1},"TEMP_CAPACITY")):
                with self.assertRaisesRegex(r3.core.StopBatch, reason):
                    r3.archive(result, path, folder, **limits)
                self.assertEqual(path.read_bytes(), sealed)

    def test_timeout_rss_and_validation_failures_force_partial_null_e(self):
        with tempfile.TemporaryDirectory(prefix="b649-r3-stop-focused-") as folder:
            for kind in ("PAIR_DEADLINE", "RSS_TARGET", "ARCHIVE_E_OR_SHA_MISMATCH"):
                result = self.fixture()
                r3.mark_partial(result, kind)
                self.assertEqual(result["TASK_STATUS"], "PARTIAL")
                self.assertIsNone(result["E"])
                self.assertIsNone(result["EXACT_EQUALITY_PAIR_COUNT"])
                self.assertIsNone(result["PAIR_RESULT"]["E"])
                self.assertFalse(result["PAIR_RESULT"]["HISTOGRAM_COMPLETE"])
                self.assertEqual(r3.independent_reparse(r3.encode(result), result), "PARTIAL_NULL_E")
                r3.archive(result, Path(folder) / "partial.json", folder)
            with self.assertRaisesRegex(r3.core.StopBatch, "BATCH_DEADLINE"):
                r3.core.check_limits(time.monotonic()-1, folder)
            with patch.object(r3.core, "peak_memory", return_value=r3.core.RSS_LIMIT+1):
                with self.assertRaisesRegex(r3.core.StopBatch, "RSS_TARGET"):
                    r3.core.check_limits(time.monotonic()+1, folder)
            broken = {"TASK_STATUS":"PARTIAL", "E":0, "EXACT_EQUALITY_PAIR_COUNT":None}
            with self.assertRaisesRegex(r3.core.StopBatch, "PARTIAL_E_MUST_BE_NULL"):
                r3.independent_reparse(r3.encode(broken), broken)

    def test_only_single_pair_can_reach_frozen_measurement(self):
        self.assertEqual(r3.core.ALLOWLIST, (((18,19),(18,19),93,1),))
        with patch.object(r3.core, "measured_row", return_value="fixture") as measured:
            self.assertEqual(r3.measure_once(None, None, self.identity, None, 60, 15), "fixture")
            measured.assert_called_once()
            for pair in ([0,1], [0,6], [0,12], [0,18], [12,13], [12,15], [12,18]):
                with self.assertRaisesRegex(ValueError, "single"):
                    r3.measure_once(None, None, {**self.identity, "PAIR_ORDERED":pair}, None, 60, 15)
            measured.assert_called_once()
        tree = ast.parse(Path(r3.__file__).read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        calls = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "measure_once"]
        self.assertEqual(len(calls), 1)
        for loop in (n for n in ast.walk(main) if isinstance(n, (ast.For, ast.While))):
            self.assertNotIn(calls[0], list(ast.walk(loop)))
        self.assertNotIn("seven_pair_batch_r2", Path(r3.__file__).read_text())

    def test_r3_identity_and_existing_execution_refuses_reentry(self):
        self.assertEqual(r3.TASK_ID, "B649_C2_N2_EQUALITY_LAST_PAIR_R3_R1")
        self.assertNotIn(r3.RESULT_REL, [p[1] for p in r3.PRIOR])
        with tempfile.TemporaryDirectory(prefix="b649-r3-reentry-focused-") as folder:
            existing = Path(folder) / "result.json"
            existing.write_text("{}")
            with patch.object(r3, "RESULT", existing), patch.object(sys, "argv", ["r3","run"]):
                with self.assertRaisesRegex(SystemExit, "retry/resume forbidden"):
                    r3.main()
            self.assertEqual(existing.read_text(), "{}")


if __name__ == "__main__":
    unittest.main()
