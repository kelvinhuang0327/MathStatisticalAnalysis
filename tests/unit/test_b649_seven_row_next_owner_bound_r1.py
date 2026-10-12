"""Focused integer proof guards; loaded by the sole bounded research process."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from itertools import combinations, product
from pathlib import Path
from unittest.mock import patch

if "b649_owner_candidate" in sys.modules:
    c = sys.modules["b649_owner_candidate"]
else:
    path = Path(__file__).resolve().parents[2] / "src/lottolab/research/b649_seven_row_next_owner_bound_r1.py"
    spec = importlib.util.spec_from_file_location("b649_owner_candidate", path)
    c = importlib.util.module_from_spec(spec)
    sys.modules["b649_owner_candidate"] = c
    spec.loader.exec_module(c)


class OwnerProofTests(unittest.TestCase):
    def test_full_local_majorant_and_boundary(self):
        positive = [d for d in c.PROFILE if d]
        for indices in combinations(range(len(positive)), 3):
            degrees = tuple(positive[i] for i in indices)
            self.assertLessEqual(4 + min(degrees), c.local_penalty(degrees))
        self.assertEqual([c.incidence_cap(m, e) for m, e in product((0, 1), repeat=2)],
                         [188, 191, 189, 192])

    def test_uniqueness_negative_cases(self):
        for m, e in ((2, 1), (1, 2), (-1, 0), (True, 1), (1, 0.5)):
            with self.assertRaisesRegex(ValueError, "binary"):
                c.incidence_cap(m, e)
        for degrees in ((0, 5, 6), (1, 1, 6), (2, 2, 6), (1, 2, 5.0)):
            with self.assertRaises(ValueError):
                c.local_penalty(degrees)

    def test_falsifiability_of_cap_guard(self):
        def guarded():
            self.assertLessEqual(max(c.incidence_cap(m, e)
                                     for m, e in product((0, 1), repeat=2)), c.NEW_A_CAP)
        guarded()
        with patch.object(c, "NEW_A_CAP", 191), self.assertRaises(AssertionError):
            guarded()
        guarded()

    def test_independent_seven_label_intersection_weights(self):
        self.assertEqual(c.local_counts(), {
            "SINGLE": 18611432, "DISJOINT_PAIR": 107800, "OVERLAP_PAIR": 574000,
            "THREE_ONE_EDGE": 0, "THREE_WEDGE": 2800,
            "THREE_PAIR_TRIANGLE": 20272, "THREE_SUPPORT_TRIANGLE": 7000,
            "FOUR_FIVE_EDGES": 112, "K4_PAIR_ONLY": 679, "K4_CONTAINED_TRIPLE": 448})
        for r in range(4, 8):
            excess = r - r * (r - 1) // 2 + r * (r - 1) * (r - 2) // 6 - 1
            self.assertGreaterEqual(7 * excess, 4 * c.comb(r, 4))

    def test_all_terms_rounding_and_direction(self):
        total = sum(d * (4 + d) for d in c.PROFILE)
        self.assertEqual(total, 602)
        self.assertTrue(3 * c.OLD_A_CAP <= total < 3 * (c.OLD_A_CAP + 1))
        self.assertEqual(20 * 18611432, 372228640)
        self.assertEqual(93 * 574000 + 97 * 107800, 63838600)
        prior = None
        for t in range(22, 265):
            old, new = c.envelope_term(t, 200), c.envelope_term(t, 192)
            k, x, s4 = new["K4_FLOOR"], new["EXCESS"], new["S4_FLOOR"]
            self.assertGreaterEqual(4 * k, x)
            if k:
                self.assertLess(4 * (k - 1), x)
            q, rem = divmod(4 * s4, 7)
            self.assertTrue(0 <= rem < 7)
            self.assertEqual(q, 372228640 - 63838600 + new["S3"] - new["BOUND"])
            # Seven times the conservative bound is >= exact rational RHS by rem.
            self.assertEqual(7 * new["BOUND"] -
                             (7 * (372228640 - 63838600 + new["S3"]) - 4 * s4), rem)
            self.assertGreaterEqual(new["S4_FLOOR"], old["S4_FLOOR"])
            self.assertLessEqual(new["BOUND"], old["BOUND"])
            self.assertEqual(new["S3"], 2800 * 832 + 11872 * (t - 22) - 30800)
            if prior is not None:
                self.assertGreater(new["BOUND"], prior)
            prior = new["BOUND"]
        self.assertEqual(c.envelope_term(264, 200)["BOUND"], 313398532)
        last = c.envelope_term(264, 192)
        self.assertEqual((last["K4_FLOOR"], last["S4_FLOOR"], last["S3"], last["BOUND"]),
                         (489, 287679, 5171824, 313397476))
        for t, a in ((21, 192), (265, 192), (264.0, 192), (264, 192.5)):
            with self.assertRaises(ValueError):
                c.envelope_term(t, a)

    def test_frozen_sha_and_realization_incidence(self):
        blob = (c.ROOT / c.INPUT_PATH).read_bytes()
        authority = c.frozen_input(blob)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            c.frozen_input(blob + b" ")
        realization = authority["NEW_OWNER_ROWS"][c.PROFILE_ID]["realization"]
        seen = c.recount(realization)
        self.assertEqual(seen["EDGES"], 93)
        self.assertLessEqual(seen["A"], seen["MIN_DEGREE_SUM"])
        self.assertEqual(sum(seen["COMMON_NEIGHBORS_BY_SUPPORT"]), seen["A"])
        reused = copy.deepcopy(realization)
        reused[1][0] = reused[1][1]
        with self.assertRaisesRegex(ValueError, "pair reuse"):
            c.recount(reused)
        wrong = copy.deepcopy(realization)
        wrong[0][0][-1] = 12  # unused pairs, but degree/capacity constraints fail
        with self.assertRaisesRegex(ValueError, "wrong profile"):
            c.recount(wrong)

    def test_s4_direction_for_all_quartet_counts(self):
        prior = -1
        for k in range(c.comb(20, 4) + 1):
            light = min(k, 192)
            s4 = 448 * light + 679 * (k - light)
            self.assertEqual(s4, 679 * k - 231 * light)
            self.assertGreater(s4, prior)
            prior = s4

    def test_frozen_cap_and_family_effect(self):
        self.assertEqual(c.T_CAP, 264)
        result = c.compute_result()
        self.assertEqual(result["PROOF_SCOPE"], "FULL_PROFILE")
        self.assertEqual(result["BOUND_DELTA"], 1056)
        self.assertEqual(result["FAMILY_BOUND_AFTER"], 313398248)
        self.assertEqual(result["NEXT_OWNER_AFTER"],
                         ["66555555555531000000", "66655555554441000000", "66655555555422000000"])
        self.assertEqual(result["NEW_STRICT_WINNING_OUTCOMES"], 0)
        self.assertEqual(result["GLOBAL_OPTIMUM_PROVED"], "NO")
        self.assertEqual(result["FROZEN_LEDGER_MUTATED"], "NO")


if __name__ == "__main__":
    unittest.main()
