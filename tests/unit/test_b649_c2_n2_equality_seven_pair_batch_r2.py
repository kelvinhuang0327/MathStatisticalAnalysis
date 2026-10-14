"""Focused R2 identity, 7_SET unit regression and compact sealing; no native gain calls."""
from __future__ import annotations

import gc
import importlib.util
import json
import sys
import tempfile
import unittest
import weakref
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("seven_pair_r2", ROOT/"tools/b649_c2_n2_equality_seven_pair_batch_r2.py")
r2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2)
core = r2.core


class TrackedList(list[Any]):
    __slots__ = ("__weakref__",)


class SevenPairR2Tests(unittest.TestCase):
    identities: list[dict[str, Any]]

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

    def row(
        self, identity: dict[str, Any] | None = None, *, cij: int = 5,
        histogram: list[list[int]] | None = None,
    ) -> dict[str, Any]:
        identity = identity or {
            "PAIR_ORDERED": [0, 0], "PAIR_ENGINE": [0, 0], "ORBIT_INDEX": 0, "ORBIT_SIZE": 1,
        }
        histogram = histogram if histogram is not None else [[2, 3], [3, 1], [5, 2]]
        exact, table = r2.equality_count()(histogram, cij, complete=True)
        return {
            **identity, "STATUS": "COMPLETE", "HISTOGRAM_COMPLETE": True, "HISTOGRAM": histogram,
            "C_ij": cij, "E": exact, "COMPLEMENTARY_BUCKET_TABLE": table,
            "HISTOGRAM_SHA256": core.sha(core.compact(histogram)),
            "COMPLEMENTARY_TABLE_SHA256": core.sha(core.compact(table)), "ELAPSED_SECONDS": 0.1,
        }

    def test_compact_archive_reparse_integrity_and_caps(self):
        folder = self.folder/"compact"
        folder.mkdir()
        full_row: dict[str, Any] = self.row(self.identities[0])
        rows: list[dict[str, Any]] = [full_row] + [core.empty_row(i) for i in self.identities[1:]]
        self.assertEqual(full_row["E"], 3)
        result: dict[str, Any] = {"TASK_STATUS": "PARTIAL", "SEVEN_PAIRS": rows}
        path = folder/"r2.json"
        archived_row: dict[str, Any] = dict(full_row)
        expected: bytes = r2.encode(result)
        size = r2.archive(result, path, folder)
        data: bytes = path.read_bytes()
        self.assertEqual(data, expected)
        self.assertEqual(core.sha(data), core.sha(expected))
        self.assertEqual(size, len(data))
        self.assertEqual(json.loads(data)["SEVEN_PAIRS"][0], archived_row)
        self.assertNotIn("HISTOGRAM", result["SEVEN_PAIRS"][0])
        self.assertEqual(result["SEVEN_PAIRS"][0]["FILE_LOCATOR"], str(path.resolve()))
        self.assertNotIn(b"\n ", data)
        for key, value in (("E", 4), ("HISTOGRAM_SHA256", "0"*64), ("COMPLEMENTARY_TABLE_SHA256", "0"*64), ("C_ij", 6)):
            broken_rows: list[dict[str, Any]] = [
                {**archived_row, key: value}, *result["SEVEN_PAIRS"][1:],
            ]
            broken: dict[str, Any] = {**result, "SEVEN_PAIRS": broken_rows}
            with self.assertRaisesRegex(core.StopBatch, "ARCHIVE_REPARSE_MISMATCH"):
                r2.archive(broken, path, folder)
            self.assertEqual(path.read_bytes(), data)
        for caps, reason in (({"result_limit": 10}, "RESULT_CAPACITY"), ({"temp_limit": core.folder_bytes(self.folder)+10}, "TEMP_CAPACITY")):
            with self.assertRaisesRegex(core.StopBatch, reason):
                r2.archive(result, path, folder, **caps)
            self.assertEqual(path.read_bytes(), data)

    def test_consecutive_archives_release_duplicates_and_reload_payloads(self):
        folder = self.folder/"consecutive"
        folder.mkdir()
        identity0, identity1, identity2 = self.identities[:3]
        histogram: TrackedList = TrackedList([[2, 3], [3, 1], [5, 2]])
        exact: int
        table_values: list[dict[str, Any]]
        exact, table_values = r2.equality_count()(histogram, 5, complete=True)
        table: TrackedList = TrackedList(table_values)
        histogram_sha: str = core.sha(core.compact(histogram))
        table_sha: str = core.sha(core.compact(table))

        rows: list[dict[str, Any]] = [self.row(identity0)] + [
            core.empty_row(i) for i in self.identities[1:]
        ]
        result: dict[str, Any] = {"TASK_STATUS": "PARTIAL", "SEVEN_PAIRS": rows}
        path = folder/"r2.json"
        first_bytes: bytes = r2.encode(result)
        r2.archive(result, path, folder)
        self.assertEqual(path.read_bytes(), first_bytes)
        first_summary: dict[str, Any] = result["SEVEN_PAIRS"][0]
        self.assertEqual(first_summary["E"], 3)

        candidate: dict[str, Any] = {**result, "SEVEN_PAIRS": list(result["SEVEN_PAIRS"])}
        candidate["SEVEN_PAIRS"][1] = {
            **identity1, "STATUS": "COMPLETE", "HISTOGRAM_COMPLETE": True,
            "HISTOGRAM": histogram, "C_ij": 5, "E": exact,
            "COMPLEMENTARY_BUCKET_TABLE": table, "HISTOGRAM_SHA256": histogram_sha,
            "COMPLEMENTARY_TABLE_SHA256": table_sha, "ELAPSED_SECONDS": 0.1,
        }
        del table_values
        pair_times: dict[int, dict[str, Any]] = {
            0: {"PAIR_TOTAL_WALL_THROUGH_ARCHIVE_SECONDS": 0.12},
        }
        expected_rows: dict[str, Any] = r2.materialize_completed_rows(candidate, path, pair_times)
        second_bytes: bytes = r2.encode(expected_rows)
        del expected_rows
        histogram_ref, table_ref = weakref.ref(histogram), weakref.ref(table)
        r2.archive(candidate, path, folder, row_metadata=pair_times)
        result = candidate
        self.assertEqual(path.read_bytes(), second_bytes)
        self.assertEqual(core.sha(path.read_bytes()), core.sha(second_bytes))
        self.assertEqual(result["SEVEN_PAIRS"][0]["HISTOGRAM_SHA256"], histogram_sha)
        self.assertEqual(result["SEVEN_PAIRS"][1]["COMPLEMENTARY_TABLE_SHA256"], table_sha)
        self.assertEqual(set(result["SEVEN_PAIRS"][1]), set(r2.SUMMARY_FIELDS) | {"FILE_LOCATOR"})
        del histogram, table
        gc.collect()
        self.assertIsNone(histogram_ref())
        self.assertIsNone(table_ref())

        loaded: dict[str, Any] = r2.materialize_completed_rows(result, path, pair_times)
        r2.verify_reparsed(path.read_bytes(), loaded)
        self.assertEqual(loaded["SEVEN_PAIRS"][0]["E"], 3)
        self.assertEqual(loaded["SEVEN_PAIRS"][1]["HISTOGRAM"], [[2, 3], [3, 1], [5, 2]])
        self.assertEqual(loaded["SEVEN_PAIRS"][0]["PAIR_TOTAL_WALL_THROUGH_ARCHIVE_SECONDS"], 0.12)
        del loaded

        candidate = {**result, "SEVEN_PAIRS": list(result["SEVEN_PAIRS"])}
        candidate["SEVEN_PAIRS"][2] = self.row(identity2, cij=0)
        candidate["COMPLETED_REPRESENTATIVES"] = sum(
            row["STATUS"] == "COMPLETE" for row in candidate["SEVEN_PAIRS"]
        )
        candidate["COVERED_ORIGINAL_PAIRS"] = sum(
            row["ORBIT_SIZE"] for row in candidate["SEVEN_PAIRS"] if row["STATUS"] == "COMPLETE"
        )
        pair_times[1] = {"PAIR_TOTAL_WALL_THROUGH_ARCHIVE_SECONDS": 0.34}
        expected_rows = r2.materialize_completed_rows(candidate, path, pair_times)
        third_bytes = r2.encode(expected_rows)
        del expected_rows
        r2.archive(candidate, path, folder, row_metadata=pair_times)
        result = candidate
        self.assertEqual(path.read_bytes(), third_bytes)
        final_row: list[dict[str, Any]] = json.loads(path.read_bytes())["SEVEN_PAIRS"]
        self.assertEqual((final_row[0]["E"], final_row[2]["E"]), (3, 0))
        self.assertEqual(final_row[0]["HISTOGRAM_SHA256"], histogram_sha)
        self.assertEqual(final_row[1]["HISTOGRAM_SHA256"], histogram_sha)
        self.assertEqual(final_row[0]["PAIR_TOTAL_WALL_THROUGH_ARCHIVE_SECONDS"], 0.12)
        self.assertEqual(final_row[1]["PAIR_TOTAL_WALL_THROUGH_ARCHIVE_SECONDS"], 0.34)
        self.assertEqual(result["COMPLETED_REPRESENTATIVES"], 3)
        self.assertEqual(
            result["COVERED_ORIGINAL_PAIRS"], sum(i["ORBIT_SIZE"] for i in self.identities[:3])
        )
        self.assertTrue(all(row["E"] is None for row in final_row[3:]))

        pair_times[2] = {"PAIR_TOTAL_WALL_THROUGH_ARCHIVE_SECONDS": 0.56}
        final_expected: bytes = r2.encode(r2.materialize_completed_rows(result, path, pair_times))
        r2.archive(result, path, folder, row_metadata=pair_times)
        final_rows: list[dict[str, Any]] = json.loads(path.read_bytes())["SEVEN_PAIRS"]
        self.assertEqual(path.read_bytes(), final_expected)
        self.assertEqual(final_rows[2]["PAIR_TOTAL_WALL_THROUGH_ARCHIVE_SECONDS"], 0.56)
        self.assertTrue(all(row["E"] is None for row in final_rows[3:]))

    def test_failed_pair_archive_preserves_prior_completed_seal_and_null_e(self):
        folder = self.folder/"failure"
        folder.mkdir()
        result: dict[str, Any] = {
            "TASK_STATUS": "PARTIAL", "SEVEN_PAIRS": [self.row(self.identities[0])]
            + [core.empty_row(i) for i in self.identities[1:]],
        }
        path = folder/"r2.json"
        r2.archive(result, path, folder)
        previous: bytes = path.read_bytes()
        candidate: dict[str, Any] = {**result, "SEVEN_PAIRS": list(result["SEVEN_PAIRS"])}
        candidate["SEVEN_PAIRS"][1] = self.row(self.identities[1], cij=0)
        with patch.object(
            r2.os, "replace", side_effect=OSError("synthetic archive failure")
        ), self.assertRaisesRegex(OSError, "synthetic archive failure"):
            r2.archive(candidate, path, folder)
        self.assertEqual(path.read_bytes(), previous)
        self.assertEqual(core.sha(path.read_bytes()), core.sha(previous))
        self.assertEqual(result["SEVEN_PAIRS"][0]["STATUS"], "COMPLETE")
        result["SEVEN_PAIRS"][1].update({"STATUS": "PARTIAL", "E": None})
        r2.archive(result, path, folder)
        sealed_rows: list[dict[str, Any]] = json.loads(path.read_bytes())["SEVEN_PAIRS"]
        self.assertEqual(sealed_rows[0]["HISTOGRAM"], [[2, 3], [3, 1], [5, 2]])
        self.assertEqual(sealed_rows[0]["E"], 3)
        self.assertEqual(sealed_rows[1]["STATUS"], "PARTIAL")
        self.assertIsNone(sealed_rows[1]["E"])
        self.assertTrue(
            all(row["E"] is None for row in sealed_rows[1:] if row["STATUS"] != "COMPLETE")
        )

    def test_seven_pilot_sized_histograms_fit_temp_cap_only_when_compact(self):
        histogram = [[494024+5*i, 1+i % 97] for i in range(242242)]
        doc = {"SEVEN_PAIRS": [{"HISTOGRAM": histogram, "COMPLEMENTARY_BUCKET_TABLE": []}]*7}
        self.assertLess(len(r2.encode(doc))+(2 << 20), core.TEMP_LIMIT)
        self.assertGreater(len(json.dumps(doc, ensure_ascii=False, indent=2).encode()), core.TEMP_LIMIT)
        self.assertEqual((core.TEMP_LIMIT, core.RESULT_LIMIT, core.BATCH_WALL, core.PAIR_WALL), (64 << 20, 128 << 20, 120.0, 15.0))


if __name__ == "__main__":
    unittest.main()
