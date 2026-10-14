"""Focused complete small-domain checks; never run the production pair sweep."""

from __future__ import annotations

import copy
import json
import math
import subprocess
import tempfile
import unittest
from collections import Counter
from itertools import combinations
from pathlib import Path
from unittest.mock import patch

from tools import b649_c2_n2_equality_histogram_pilot_r1 as adapter


def direct_relations(gains: list[int], target: int) -> tuple[int, int, int]:
    """Distinct indices, unordered: do not collapse equal-gain tickets."""
    counts = [0, 0, 0]
    for i, j in combinations(range(len(gains)), 2):
        total = gains[i] + gains[j]
        counts[0 if total < target else 1 if total == target else 2] += 1
    return tuple(counts)


def buckets(gains: list[int]) -> list[list[int]]:
    return [[g, c] for g, c in sorted(Counter(gains).items())]


class HistogramPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.identity, cls.donor = adapter.load_inputs()
        cls.source, cls.provenance = adapter.c_source(cls.donor)
        cls.temp = tempfile.TemporaryDirectory(prefix=adapter.TASK_ID + "-focused-")
        cls.binary, cls.compile_command = adapter.compile_c(cls.source, Path(cls.temp.name))
        cls.fixtures = []
        for n, portfolio in [
            (11, [[1, 2, 3, 4, 5, 6], [6, 7, 8, 9, 10, 11], [1, 2, 3, 7, 8, 9]]),
            (12, [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12], [1, 2, 3, 7, 8, 9]]),
        ]:
            run = subprocess.run(
                [str(cls.binary), "histogram"],
                input=adapter.input_text(n, portfolio, [0, 1]),
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            data = json.loads(run.stdout)
            tickets = list(combinations(range(1, n + 1), 6))
            outcomes = [set(w) for w in combinations(range(1, n + 1), 7)]
            untouched = set(portfolio[2])
            uncovered = [w for w in outcomes if len(w & untouched) < 3]
            gains = [sum(len(set(t) & w) >= 3 for w in uncovered) for t in tickets]
            legal_gains = [
                g for t, g in zip(tickets, gains, strict=True) if list(t) != portfolio[2]
            ]
            target = sum(any(len(set(t) & w) >= 3 for t in portfolio[:2]) for w in uncovered)
            cls.fixtures.append((n, portfolio, data, gains, legal_gains, target))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_fixed_pair_and_all_untouched_values(self) -> None:
        self.assertEqual(self.identity["PAIR_ORDERED"], [0, 1])
        self.assertEqual(self.identity["PAIR_ENGINE"], [0, 1])
        self.assertEqual(
            self.identity["REMOVED_TICKETS"], [[1, 2, 3, 4, 5, 21], [1, 6, 7, 8, 9, 22]]
        )
        self.assertEqual(len(self.identity["UNTOUCHED_TICKETS"]), 18)
        self.assertEqual(len({tuple(t) for t in self.identity["UNTOUCHED_TICKETS"]}), 18)
        engine = self.identity["ENGINE_TICKETS"]
        ordered = self.identity["REMOVED_TICKETS"] + self.identity["UNTOUCHED_TICKETS"]
        for i, j in enumerate(self.identity["ORDERED_TO_ENGINE_SLOTS"]):
            self.assertEqual(engine[j], ordered[i])

    def test_correct_indices_with_wrong_values_are_rejected(self) -> None:
        engine = copy.deepcopy(self.identity["ENGINE_TICKETS"])
        engine[0][-1] = 20
        ordered = self.identity["REMOVED_TICKETS"] + self.identity["UNTOUCHED_TICKETS"]
        with self.assertRaisesRegex(ValueError, "by-value"):
            adapter.pair_identity(ordered, engine, self.identity["ORDERED_TO_ENGINE_SLOTS"])

    def test_wrong_untouched_values_are_rejected(self) -> None:
        engine = copy.deepcopy(self.identity["ENGINE_TICKETS"])
        engine[18][-1] = 47
        ordered = self.identity["REMOVED_TICKETS"] + self.identity["UNTOUCHED_TICKETS"]
        with self.assertRaisesRegex(ValueError, "by-value"):
            adapter.pair_identity(ordered, engine, self.identity["ORDERED_TO_ENGINE_SLOTS"])

    def test_donor_core_and_sweep_storage_only_difference(self) -> None:
        self.assertEqual(adapter.sha(self.donor.encode()), adapter.DONOR_SHA)
        core = self.donor[
            self.donor.index("static void init_binom(") : self.donor.index(
                "/* Table-free two-ticket"
            )
        ]
        self.assertIn(core, self.source)
        start = self.donor.index(
            "    {\n        int x[6], s[6];", self.donor.index("/* Full g_R sweep")
        )
        sweep = self.donor[start : self.donor.index("    double t_sweep", start)]
        restored = self.source.replace(
            "                record_gain(r6, g, x, y);",
            "                G[r6].rank = r6;\n                G[r6].g = (int32_t)g;",
        )
        self.assertIn(sweep, restored)
        self.assertNotIn("for (int64_t p = 0; p < N6; p++)", self.source)
        self.assertNotIn("S1[a].mask | S2[b].mask", self.source)
        self.assertNotIn("build_covered7", self.source)

    def test_tampered_donor_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "identity"):
            adapter.c_source(self.donor.replace("C4 = 3", "C4 = 2", 1))

    def test_every_small_single_gain_matches_independent_outcome_enumeration(self) -> None:
        for n, _, data, gains, _, _ in self.fixtures:
            with self.subTest(n=n):
                self.assertEqual(data["SINGLE_GAINS_SMALL_TEST_ONLY"], gains)
                self.assertEqual(data["RAW_SINGLE_TICKETS"], math.comb(n, 6))

    def test_small_exclusion_histogram_and_removed_tickets(self) -> None:
        for n, portfolio, data, _, gains, _ in self.fixtures:
            with self.subTest(n=n):
                self.assertEqual(data["HISTOGRAM"], buckets(gains))
                self.assertEqual(data["REMOVED_TICKETS"], portfolio[:2])
                self.assertEqual(data["UNTOUCHED_TICKETS"], portfolio[2:])
                self.assertEqual(data["EXCLUDED_UNTOUCHED_TICKETS"], 1)
                self.assertEqual(data["LEGAL_SINGLE_TICKETS"], math.comb(n, 6) - 1)
                self.assertEqual(sum(c for _, c in data["HISTOGRAM"]), len(gains))

    def test_small_cij_odd_and_even_in_seven_set_units(self) -> None:
        self.assertEqual([fixture[-1] % 2 for fixture in self.fixtures], [1, 0])
        for n, _, data, _, _, target in self.fixtures:
            with self.subTest(n=n):
                self.assertEqual(data["COUNTING_UNIT"], "7_SET")
                self.assertEqual(data["C_ij"], target)
                self.assertEqual(data["COVERED_P"] - data["COVERED_R"], target)

    def test_small_complete_pair_less_equal_greater_partition(self) -> None:
        for n, _, data, _, gains, target in self.fixtures:
            with self.subTest(n=n):
                lower, equal, greater = direct_relations(gains, target)
                self.assertEqual(lower + equal + greater, math.comb(len(gains), 2))
                exact, table = adapter.equality_count(data["HISTOGRAM"], target, complete=True)
                self.assertEqual(exact, equal)
                self.assertEqual(sum(r["CONTRIBUTION"] for r in table), equal)

    def test_synthetic_odd_even_duplicate_gain_and_distinct_ticket_formula(self) -> None:
        for gains, target in [
            ([0, 1, 1, 2, 2, 3], 3),
            ([0, 1, 1, 2, 2, 3], 4),
            ([2], 4),
            ([2, 2, 2], 4),
            ([0, 0, 0], 0),
        ]:
            with self.subTest(gains=gains, target=target):
                relations = direct_relations(gains, target)
                self.assertEqual(sum(relations), math.comb(len(gains), 2))
                if len(gains) == 6:
                    self.assertTrue(all(count > 0 for count in relations))
                exact, _ = adapter.equality_count(buckets(gains), target, complete=True)
                self.assertEqual(exact, relations[1])
        self.assertEqual(adapter.equality_count([[2, 3]], 4, complete=True)[0], 3)
        self.assertEqual(adapter.equality_count([[2, 1]], 4, complete=True)[0], 0)

    def test_integer_exactness_beyond_float_precision(self) -> None:
        count = 2**54 + 3
        exact, _ = adapter.equality_count([[1, count], [2, count + 1]], 3, complete=True)
        self.assertEqual(exact, count * (count + 1))
        self.assertIs(type(exact), int)

    def test_invalid_float_duplicate_or_truncated_buckets_rejected(self) -> None:
        for bad in [[[1.0, 1]], [[1, 1.0]], [[1, 1], [1, 2]], [[1, 0]], [[-1, 2]]]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adapter.equality_count(bad, 2, complete=True)

    def test_partial_histogram_never_exact(self) -> None:
        with self.assertRaisesRegex(ValueError, "partial"):
            adapter.equality_count([[1, 2]], 2, complete=False)

    def test_pair_and_overlap_guards_reject_every_removed_donor_entry(self) -> None:
        for mode in self.provenance["GUARD_MODES"]:
            with self.subTest(mode=mode):
                run = subprocess.run(
                    [str(self.binary), mode], capture_output=True, text=True, timeout=5
                )
                self.assertEqual(run.returncode, 3)
                self.assertIn("FORBIDDEN", run.stderr)
                self.assertEqual(run.stdout, "")
        for _, _, data, _, _, _ in self.fixtures:
            self.assertEqual(data["PAIR_OVERLAP_CALLS"], 0)
            self.assertEqual(data["N2_PAIR_SWEEP_CALLS"], 0)
            self.assertEqual(data["EQUALITY_PAIRS_MATERIALIZED"], 0)

    def test_gain_mutation_is_detected_and_restored(self) -> None:
        altered = self.source.replace("C4 = 3", "C4 = 2", 1)
        binary, _ = adapter.compile_c(altered, Path(self.temp.name))
        n, portfolio, _, _, _, _ = self.fixtures[0]
        run = subprocess.run(
            [str(binary), "histogram"],
            input=adapter.input_text(n, portfolio, [0, 1]),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(run.returncode, 3)
        self.assertIn("small-domain donor direct/brute single gain mismatch", run.stderr)
        adapter.compile_c(self.source, Path(self.temp.name))
        restored = subprocess.run(
            [str(self.binary), "histogram"],
            input=adapter.input_text(n, portfolio, [0, 1]),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        self.assertEqual(json.loads(restored.stdout)["HISTOGRAM"], self.fixtures[0][2]["HISTOGRAM"])

    def test_formula_mutation_is_detected_without_persisted_source_edit(self) -> None:
        original = adapter.equality_count([[2, 3]], 4, complete=True)[0]
        self.assertEqual(original, 3)
        with patch.object(adapter.math, "comb", return_value=9):
            altered = adapter.equality_count([[2, 3]], 4, complete=True)[0]
            with self.assertRaises(AssertionError):
                self.assertEqual(altered, direct_relations([2, 2, 2], 4)[1])
        self.assertEqual(adapter.equality_count([[2, 3]], 4, complete=True)[0], original)


if __name__ == "__main__":
    unittest.main()
