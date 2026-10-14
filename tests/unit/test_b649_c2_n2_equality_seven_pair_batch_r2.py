"""Focused R2 identity, 7_SET unit regression and compact sealing; no native gain calls."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("seven_pair_r2", ROOT/"tools/b649_c2_n2_equality_seven_pair_batch_r2.py")
r2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2)
core = r2.core


class SevenPairR2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="b649-seven-r2-focused-")
        cls.folder = Path(cls.temp.name)
        cls.identities, _, _ = core.load_inputs()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_core_bytes_pinned(self):
        self.assertEqual(core.sha((ROOT/r2.CORE_REL).read_bytes()), r2.CORE_SHA)
        with self.assertRaisesRegex(ValueError, "corrected adapter SHA mismatch"):
            r2.load_core(expected="0"*64)

    def test_unit_precheck_accepts_7_set_and_rejects_outcome_count(self):
        report = r2.unit_precheck(self.identities)
        self.assertEqual((report["SOURCE_COVERAGE_7SET"], report["SOURCE_OUTCOME_COUNT"]), (44751984, 313263888))
        self.assertEqual(44751984*7, 313263888)
        self.assertTrue(all(c["PASS"] for c in report["CASES"]))
        self.assertEqual([c["OBSERVED"] for c in report["CASES"]], ["ACCEPT", "ACCEPT"]+["REJECT"]*4)
        with self.assertRaisesRegex(ValueError, "non-7_SET source"):
            r2.unit_precheck([{**i, "EXPECTED_COVERED_P_7_SET": 313263888} for i in self.identities])
        with self.assertRaisesRegex(ValueError, "preset C_ij"):
            r2.unit_precheck([{**i, "C_ij": 3598090} for i in self.identities])
        # Falsifiability: a validator that accepts every source must fail the precheck.
        with patch.object(core, "validate_source_coverage", lambda data, identity: None):
            with self.assertRaisesRegex(ValueError, "unit precheck failed: OUTCOME_COUNT_AS_7_SET_DATA_REJECTED"):
                r2.unit_precheck(self.identities)

    def test_r2_identity_destination_and_r1_preserved(self):
        self.assertEqual(r2.TASK_ID, "B649_C2_N2_EQUALITY_SEVEN_PAIR_BATCH_R2")
        self.assertTrue(r2.RESULT_REL.endswith("b649-c2-n2-equality-seven-pair-batch-r2-result.json"))
        self.assertNotEqual(r2.RESULT_REL, r2.R1_RESULT_REL)
        r1 = r2.r1_preserved()
        self.assertEqual((r1["SHA256"], r1["COMPLETED_REPRESENTATIVES"], r1["VALUES_REUSED_IN_R2"]), (r2.R1_RESULT_SHA, 0, False))
        existing = self.folder/"existing.json"
        existing.write_text("{}")
        with patch.object(r2, "RESULT", existing), patch.object(sys, "argv", ["r2", "run"]):
            with self.assertRaisesRegex(SystemExit, "retry/resume forbidden"):
                r2.main()
        existing.unlink()

    def row(self):
        histogram = [[2, 3], [3, 1], [5, 2]]
        exact, table = r2.equality_count()(histogram, 5, complete=True)
        return {"STATUS": "COMPLETE", "HISTOGRAM_COMPLETE": True, "HISTOGRAM": histogram, "C_ij": 5, "E": exact,
                "COMPLEMENTARY_BUCKET_TABLE": table, "HISTOGRAM_SHA256": core.sha(core.compact(histogram)),
                "COMPLEMENTARY_TABLE_SHA256": core.sha(core.compact(table)), "ELAPSED_SECONDS": 0.1}

    def test_compact_archive_reparse_integrity_and_caps(self):
        rows = [self.row()] + [core.empty_row(i) for i in self.identities[1:]]
        self.assertEqual(rows[0]["E"], 3)
        result = {"TASK_STATUS": "PARTIAL", "SEVEN_PAIRS": rows}
        path = self.folder/"r2.json"
        size = r2.archive(result, path, self.folder)
        data = path.read_bytes()
        self.assertEqual(data, r2.encode(result))
        self.assertEqual(size, len(data))
        self.assertEqual(json.loads(data), result)
        self.assertNotIn(b"\n ", data)
        for key, value in (("E", 4), ("HISTOGRAM_SHA256", "0"*64), ("COMPLEMENTARY_TABLE_SHA256", "0"*64), ("C_ij", 6)):
            broken = {**result, "SEVEN_PAIRS": [{**rows[0], key: value}] + rows[1:]}
            with self.assertRaisesRegex(core.StopBatch, "ARCHIVE_REPARSE_MISMATCH"):
                r2.archive(broken, path, self.folder)
            self.assertEqual(path.read_bytes(), data)
        for caps, reason in (({"result_limit": 10}, "RESULT_CAPACITY"), ({"temp_limit": core.folder_bytes(self.folder)+10}, "TEMP_CAPACITY")):
            with self.assertRaisesRegex(core.StopBatch, reason):
                r2.archive(result, path, self.folder, **caps)
            self.assertEqual(path.read_bytes(), data)
        path.unlink()

    def test_seven_pilot_sized_histograms_fit_temp_cap_only_when_compact(self):
        histogram = [[494024+5*i, 1+i % 97] for i in range(242242)]
        doc = {"SEVEN_PAIRS": [{"HISTOGRAM": histogram, "COMPLEMENTARY_BUCKET_TABLE": []}]*7}
        self.assertLess(len(r2.encode(doc))+(2 << 20), core.TEMP_LIMIT)
        self.assertGreater(len(json.dumps(doc, ensure_ascii=False, indent=2).encode()), core.TEMP_LIMIT)
        self.assertEqual((core.TEMP_LIMIT, core.RESULT_LIMIT, core.BATCH_WALL, core.PAIR_WALL), (64 << 20, 128 << 20, 120.0, 15.0))


if __name__ == "__main__":
    unittest.main()
