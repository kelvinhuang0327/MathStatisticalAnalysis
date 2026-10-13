"""Focused scientific falsification; one sequential stdlib-only verification process."""

from __future__ import annotations

import hashlib
import json
import random
import resource
import sys
import unittest
from dataclasses import replace
from itertools import combinations
from time import process_time

from lottolab.research import b649_frontier_owner_b_exact_bound_r1 as c


class CertificateTests(unittest.TestCase):
    negative_count = 0

    @classmethod
    def setUpClass(cls) -> None:
        cls.result = c.compute_result()

    def rejects(self, call, message: str) -> None:
        with self.assertRaisesRegex(AssertionError, message):
            call()
        type(self).negative_count += 1

    def test_source_and_full_profile(self) -> None:
        source = self.result["SOURCE"]
        self.assertEqual((source["HEAD"], source["TREE"]), (c.FROZEN_HEAD, c.FROZEN_TREE))
        self.assertEqual((source["SOURCE_T_CAP"], source["SOURCE_S4_BASE"]), (264, 112))
        self.assertEqual(source["SOURCE_ROW_BOUND"], 313398144)
        self.assertTrue(source["SOURCE_LOCATOR"].endswith("NB_CERTIFICATES[871]"))
        self.assertEqual((sum(c.PROFILE), sum(d * d for d in c.PROFILE)), (66, 338))
        self.assertEqual((self.result["CORE_VERTICES"], self.result["ZERO_VERTICES"]), (15, 5))
        self.assertEqual((self.result["GRAPH_EDGES"], self.result["GOODMAN_CONSTANT"]), (93, 298))

    def test_negative_source_pins(self) -> None:
        raw = (c.ROOT / c.RESULT_DIR / c.FROZEN_RESULT).read_bytes()
        self.rejects(lambda: c.validate_pin("0" * 40, c.FROZEN_TREE, raw), "HEAD")
        self.rejects(
            lambda: c.validate_pin(c.FROZEN_HEAD, "986d20859c86be40295098a5d3ef", raw), "tree"
        )
        self.rejects(lambda: c.validate_pin(c.FROZEN_HEAD, c.FROZEN_TREE[:-1] + "0", raw), "tree")
        self.rejects(lambda: c.validate_pin(c.FROZEN_HEAD, c.FROZEN_TREE, raw + b"\n"), "SHA256")

    def test_negative_profile(self) -> None:
        for p in (
            c.PROFILE[:-1],
            tuple(reversed(c.PROFILE)),
            (6,) * 4 + (5,) * 8 + (1,) * 2 + (0,) * 6,
        ):
            self.rejects(lambda p=p: c.profile_check(p), "wrong full profile")

    def test_complete_relaxation(self) -> None:
        r = self.result["RELAXATION"]
        self.assertEqual((r["STATE_COUNT"], r["EXACT_MAXIMUM"]), (8810, 262))
        self.assertEqual((r["ZERO_LABELLED_GRAPHS"], r["ZERO_DEGREE_SIGNATURES"]), (1024, 31))
        self.assertEqual((r["ARGMAX_F"], r["ARGMAX_P_FLOOR"]), (290, 28))
        self.assertEqual(sum(r["HISTOGRAM"].values()), 8810)
        self.assertEqual(max(r["HISTOGRAM"]), 262)
        self.assertEqual(self.result["PROOF_SCOPE"], "FULL_PROFILE")
        self.assertEqual(self.result["UNPROVED_ASSUMPTIONS"], [])

    def test_load_bearing_premises(self) -> None:
        s = c.State(1, 2, (5, 5, 5), (3, 3, 3, 3, 6), 3)
        c.validate_state(s)
        self.assertEqual(c.objective(s), 290)
        self.assertEqual(c.remainder_floor(s), 28)
        self.assertEqual(c.objective(s) - c.remainder_floor(s), 262)
        no_zero = replace(s, zeta=(2, 2, 2, 6, 6))
        no_capacity = replace(s, mask=0)
        self.rejects(lambda: c.validate_state(no_zero), "not graphical")
        self.rejects(lambda: c.validate_state(no_capacity), "capacity")
        for row in self.result["NEGATIVE_CASES"].values():
            if isinstance(row, dict):
                self.assertGreater(row["BOUND"], 264)
                type(self).negative_count += 1
        self.assertEqual(c.objective(s) - c.remainder_floor(s, use_common_zeros=False), 272)
        self.assertEqual(c.objective(s) - c.remainder_floor(s, use_triangles=False), 280)

    def test_negative_ranges_and_equal_sums(self) -> None:
        s = c.State(1, 2, (5, 5, 5), (3, 3, 3, 3, 6), 3)
        cases = [
            (replace(s, a=-1), "d5"),
            (replace(s, a=8), "d5"),
            (replace(s, a=True), "d5"),
            (replace(s, q=-1), "d4"),
            (replace(s, q=3), "d4"),
            (replace(s, low=(5, 5, 6)), "low cross"),
            (replace(s, low=(-1, 5, 5)), "low cross"),
            (replace(s, low=(5, 4, 5)), "symmetry"),
            (replace(s, zeta=(1, 3, 3, 5, 6)), "zero cross"),
            (replace(s, zeta=(3, 3, 3, 3, 7)), "zero cross"),
            (replace(s, zeta=(3, 3, 3, 6, 3)), "symmetry"),
            (replace(s, a=2), "unequal"),
            (replace(s, mask=-1), "mask"),
            (replace(s, mask=8), "mask"),
        ]
        for state, message in cases:
            self.rejects(lambda state=state: c.validate_state(state), message)
        self.rejects(lambda: c.graph_edges(1024, c.EDGES_5), "mask")

    def test_capacity_boundary_is_inclusive(self) -> None:
        # Zero low-edges permit sum s=11, but not 12; one edge permits sum s=13.
        c.validate_state(c.State(3, 2, (3, 3, 5), (3, 3, 3, 3, 4), 0))
        over = c.State(2, 2, (3, 4, 5), (3, 3, 3, 3, 4), 0)
        self.rejects(lambda: c.validate_state(over), "capacity")
        c.validate_state(replace(over, mask=1))
        c.validate_state(c.State(1, 2, (3, 5, 5), (3, 3, 3, 3, 4), 1))

    def test_zero_domain_has_independent_complement_recount(self) -> None:
        # Build by complementing every G[Z], independently of degree_H[Z]+2.
        domain = set()
        for mask in range(1024):
            edges = {e for i, e in enumerate(c.EDGES_5) if mask & (1 << i)}
            domain.add(tuple(sorted(6 - sum(v in e for e in edges) for v in range(5))))
        self.assertEqual(domain, set(c.zero_domain()))
        self.assertIn((2, 2, 2, 2, 2), domain)
        self.assertIn((6, 6, 6, 6, 6), domain)
        self.assertNotIn((2, 2, 2, 6, 6), domain)

    def test_mixed_identity_and_nonnegative_remainder(self) -> None:
        rng = random.Random(64915)
        all_edges = set(combinations(range(20), 2))
        core, zero = set(range(15)), set(range(15, 20))
        positive = 0

        def triangles(edges: set, vertices: set) -> int:
            return sum(
                all(e in edges for e in combinations(t, 2))
                for t in combinations(sorted(vertices), 3)
            )

        for density in (0, 0.2, 0.5, 0.8, 1):
            g = {e for e in sorted(all_edges) if rng.random() < density}
            h = all_edges - g
            m = {e for e in h if set(e) <= core}
            q = {e for e in h if set(e) <= zero}
            ng = {i: {j for j in range(20) if tuple(sorted((i, j))) in g} for i in range(20)}
            sigma = {i: len(ng[i] & zero) for i in core}
            zeta = {i: len(ng[i] & core) for i in zero}
            hd = {i: sum(i in e for e in m) for i in core}
            ad = {i: sum(i in e for e in q) for i in zero}
            p = (
                triangles(m, core)
                + triangles(q, zero)
                + sum(len(ng[i] & ng[j] & zero) for i, j in m)
                + sum(len(ng[i] & ng[j] & core) for i, j in q)
            )
            bare = (
                5 * len(m)
                + 15 * len(q)
                - sum(sigma[i] * hd[i] for i in core)
                - sum(zeta[i] * ad[i] for i in zero)
            )
            self.assertEqual(triangles(h, set(range(20))), bare + p)
            degrees = [len(ng[i]) for i in range(20)]
            self.assertEqual(
                2 * (triangles(g, set(range(20))) + triangles(h, set(range(20)))),
                2 * 1140 - sum(v * (19 - v) for v in degrees),
            )
            self.assertGreaterEqual(p, 0)
            positive += p > 0
        self.assertGreater(positive, 0)

    def test_common_neighbour_cardinality_floor(self) -> None:
        for left in range(32):
            for right in range(32):
                self.assertGreaterEqual(
                    (left & right).bit_count(), max(0, left.bit_count() + right.bit_count() - 5)
                )
        for _ in range(100):
            left, right = random.Random(_).randrange(4096), random.Random(_ + 100).randrange(4096)
            self.assertGreaterEqual(
                (left & right).bit_count(), max(0, left.bit_count() + right.bit_count() - 12)
            )

    def test_route_b_all_integer_terms(self) -> None:
        new = c.route_terms(c.PROFILE, 262, 112)
        old = c.route_terms(c.PROFILE, 264, 112)
        c.check_terms(new, 262)
        c.check_terms(old, 264)
        self.assertEqual((len(new), len(old)), (241, 243))
        self.assertEqual(new[-1], (262, 313380220, 475, 200, 276325, 5148080))
        self.assertEqual(old[-1], (264, 313398144, 490, 200, 286510, 5171824))
        self.assertEqual(new, old[:241])
        self.assertEqual(max(new, key=lambda t: t[1]), new[-1])
        self.assertEqual(self.result["OWNER_BOUND_REDUCTION"], 17924)
        self.assertEqual(self.result["NEXT_COMPETITOR_SUFFICIENT_T_CAP"], 263)
        self.assertEqual(self.result["CLOSURE_T_CAP"], 249)
        self.assertFalse(self.result["OWNER_EXCLUSION_PROVED"])
        self.assertEqual(self.result["FAMILY_BOUND_REDUCTION_CLAIMED"], 0)

    def test_negative_route_rounding_and_off_by_one(self) -> None:
        good = c.route_terms(c.PROFILE, 262, 112)
        for index in (2, 3, 4, 5, 1):
            bad = list(good)
            term = list(bad[-1])
            term[index] += 1
            bad[-1] = tuple(term)
            self.rejects(lambda bad=bad: c.check_terms(bad, 262), "arithmetic")
        self.rejects(lambda: c.check_terms(good[:-1], 262), "domain")
        self.rejects(lambda: c.check_terms(good[1:], 262), "domain")
        self.rejects(lambda: c.check_terms([*good, good[-1]], 262), "domain")
        # At T=263 the K4 excess is 1930: floor 482 would under-credit S4.
        at263 = c.route_terms(c.PROFILE, 263, 112)[-1]
        self.assertEqual(at263[2], 483)
        self.assertEqual(at263[1], 313388988)
        self.assertLess(at263[1], c.NEXT_BOUND)
        wrong_floor = c.route_terms(c.PROFILE, 263, 112)
        t, _, k, contained, _, s3 = wrong_floor[-1]
        wrong_s4 = 679 * (k - 1) - 231 * contained
        wrong_bound = 372228640 - 63838600 + s3 - 4 * wrong_s4 // 7
        wrong_floor[-1] = (t, wrong_bound, k - 1, contained, wrong_s4, s3)
        self.rejects(lambda: c.check_terms(wrong_floor, 263), "arithmetic")
        self.assertLessEqual(c.route_terms(c.PROFILE, 249, 112)[-1][1], c.INCUMBENT)
        self.assertGreater(c.route_terms(c.PROFILE, 250, 112)[-1][1], c.INCUMBENT)
        for cap in (21, 278, True):
            self.rejects(lambda cap=cap: c.route_terms(c.PROFILE, cap, 112), "cap range")
        self.rejects(lambda: c.route_terms(c.PROFILE, 262, -1), "base range")


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    started = process_time()
    write = "--write-result" in sys.argv
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CertificateTests)
    run = unittest.TextTestRunner(verbosity=2).run(suite)
    if not run.wasSuccessful():
        sys.exit(1)
    result = CertificateTests.result
    result["FOCUSED_TEST_EXIT_CODE"] = 0
    result["FOCUSED_TEST_COUNT"] = run.testsRun
    result["NEGATIVE_TEST_COUNT"] = CertificateTests.negative_count
    result["CPU_SECONDS"] = process_time() - started
    result["CPU_SECONDS_MEANING"] = (
        "Measured delivery/test process CPU; excludes bounded preliminary processes"
    )
    result["DELIVERY_PROCESS_CPU_HARD_LIMIT_SECONDS"] = 60
    if write:
        digest = c.write_result(result)
    elif c.RESULT_PATH.exists():
        saved = json.loads(c.RESULT_PATH.read_bytes())
        for key in (
            "CPU_SECONDS",
            "CPU_SECONDS_MEANING",
            "FOCUSED_TEST_COUNT",
            "NEGATIVE_TEST_COUNT",
            "FOCUSED_TEST_EXIT_CODE",
            "DELIVERY_PROCESS_CPU_HARD_LIMIT_SECONDS",
        ):
            saved.pop(key, None)
            result.pop(key, None)
        if saved != json.loads(json.dumps(result)):
            raise AssertionError("saved scientific result differs from verified computation")
        digest = hashlib.sha256(c.RESULT_PATH.read_bytes()).hexdigest()
    else:
        digest = None
    print(
        json.dumps(
            {
                "TESTS": run.testsRun,
                "NEGATIVE_CASES": CertificateTests.negative_count,
                "NEW_ADMISSIBLE_BOUND": result["NEW_ADMISSIBLE_BOUND"],
                "RESULT_SHA256": digest,
                "CPU_SECONDS": process_time() - started,
            }
        )
    )
