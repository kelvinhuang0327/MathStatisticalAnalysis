"""Focused scientific falsification; one sequential stdlib-only verification process."""

from __future__ import annotations

import hashlib
import json
import random
import resource
import sys
import unittest
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from time import process_time
from typing import Any, ClassVar

from lottolab.research import b649_new_frontier_owner_b_bounded_r1 as c

ARGMAX = c.State(0, (4, 4), (0, 0, 0, 0, 1, 1))


def triangles(edges: set[tuple[int, int]], vertices: set[int]) -> int:
    return sum(
        all(e in edges for e in combinations(t, 2)) for t in combinations(sorted(vertices), 3)
    )


class CertificateTests(unittest.TestCase):
    negative_count: ClassVar[int] = 0
    result: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.result = c.compute_result()

    def rejects(self, call: Callable[[], object], message: str) -> None:
        with self.assertRaisesRegex(AssertionError, message):
            call()
        type(self).negative_count += 1

    def test_source_and_full_profile(self) -> None:
        source = self.result["SOURCE"]
        self.assertEqual((source["HEAD"], source["TREE"]), (c.FROZEN_HEAD, c.FROZEN_TREE))
        self.assertEqual(source["RESULT_SHA256"], c.FROZEN_SHA256)
        self.assertEqual((source["SOURCE_T_CAP"], source["SOURCE_S4_BASE"]), (265, 112))
        self.assertEqual(source["SOURCE_ROW_BOUND"], 313395448)
        self.assertTrue(source["SOURCE_LOCATOR"].endswith("NB_CERTIFICATES[1444]"))
        self.assertEqual(source["SOURCE_CAP_COMPONENTS"], {"NB": 271, "R18": 274, "CATALOG": 265})
        self.assertIn("GROUP_ATTEMPTS[3073]", source["CATALOG_CAP_LOCATOR"])
        self.assertEqual(source["PRE_NB_BOUND"], 313562472)
        self.assertEqual(source["CURSOR"], {"BOUND": 313394584, "ID": "66544333333333332222"})
        self.assertEqual(source["NEXT_COMPETITOR_BOUND"], 313395344)
        self.assertEqual(source["OLD_ENVELOPE"], (265, 313395448, 498, 198, 292404, 5172496))
        self.assertEqual((sum(c.PROFILE), sum(d * d for d in c.PROFILE)), (66, 330))
        self.assertEqual((self.result["CORE_VERTICES"], self.result["ZERO_VERTICES"]), (14, 6))
        self.assertEqual((self.result["GRAPH_EDGES"], self.result["COMPLEMENT_EDGES"]), (93, 97))
        self.assertEqual(self.result["GOODMAN_CONSTANT"], 294)
        self.assertEqual(self.result["DEGREE_PROFILE"], "6^2,5^10,2^2,0^6")

    def test_negative_source_pins(self) -> None:
        raw = (c.ROOT / c.RESULT_DIR / c.FROZEN_RESULT).read_bytes()
        c.validate_pin(c.FROZEN_HEAD, c.FROZEN_TREE, raw)
        self.rejects(lambda: c.validate_pin("0" * 40, c.FROZEN_TREE, raw), "HEAD")
        self.rejects(lambda: c.validate_pin(c.FROZEN_HEAD, c.FROZEN_TREE[:-1] + "0", raw), "tree")
        self.rejects(lambda: c.validate_pin(c.FROZEN_HEAD, c.FROZEN_TREE, raw + b"\n"), "SHA256")
        self.rejects(lambda: c.frozen_json(c.NB_RESULT, "0" * 64), "supporting source pin")
        self.rejects(lambda: c.frozen_json(c.SIX_ROW_RESULT, c.NB_SHA256), "supporting source pin")

    def test_negative_profile_and_illegal_sequences(self) -> None:
        for wrong in ("66665555555411100000", "66555555555441000000", "66555555555521100000"):
            profile = tuple(map(int, wrong))
            self.assertEqual(sum(profile), 66)
            self.rejects(lambda p=profile: c.profile_check(p), "wrong full profile")
        illegal = [
            (c.PROFILE[:-1], "twenty integer"),
            ((7, *c.PROFILE[1:-1], 0), "twenty integer"),
            ((*c.PROFILE[:-1], -1), "twenty integer"),
            ((6.0, *c.PROFILE[1:]), "twenty integer"),
            ((True, *c.PROFILE[1:]), "twenty integer"),
            ((*c.PROFILE[:13], 1, *c.PROFILE[14:]), "sum d must be 66"),
            (tuple(reversed(c.PROFILE)), "order"),
        ]
        for profile, message in illegal:
            self.rejects(lambda p=profile: c.profile_check(p), message)  # type: ignore[arg-type]
        self.rejects(lambda: c.route_terms(c.PROFILE[:-1], 236, 112), "profile range")

    def test_three_forms_of_the_triangle_identity(self) -> None:
        g = [6 + d for d in c.PROFILE]
        self.assertEqual(2 * 1140 - sum(v * (19 - v) for v in g), 2 * 294)
        self.assertEqual(1140 - 18 * 97 + sum((13 - d) * (12 - d) // 2 for d in c.PROFILE), 294)
        domain = sorted(c.zero_domain())
        checked = 0
        for a in range(11):
            for s1 in range(5):
                for s2 in range(s1, 5):
                    for q in domain:
                        if a + s1 + s2 != 6 + sum(q):
                            continue
                        s = c.State(a, (s1, s2), q)
                        r = a + s1 + s2
                        sigma = [0, 0] + [1] * a + [0] * (10 - a) + [s1, s2]
                        raw = (
                            240
                            - 11 * r
                            + sum(
                                x * (7 - d + x) for d, x in zip(c.PROFILE[:14], sigma, strict=True)
                            )
                            + sum((x + 1) ** 2 for x in q)
                        )
                        self.assertEqual(raw, c.objective(s))
                        self.assertEqual(raw, c.generic_objective(s))
                        checked += 1
        self.assertEqual(checked, self.result["RELAXATION"]["STATE_COUNT"])

    def test_complete_relaxation(self) -> None:
        r = self.result["RELAXATION"]
        self.assertEqual((r["STATE_COUNT"], r["EXACT_MAXIMUM"]), (238, 236))
        self.assertEqual((r["ZERO_LABELLED_GRAPHS"], r["ZERO_DEGREE_SIGNATURES"]), (32768, 102))
        self.assertEqual(r["ARGMAX"], [vars(ARGMAX)])
        self.assertEqual(sum(r["HISTOGRAM"].values()), 238)
        self.assertEqual(max(r["HISTOGRAM"]), 236)
        self.assertEqual(r["HISTOGRAM"][236], 1)
        self.assertEqual(c.objective(ARGMAX), 236)
        self.assertEqual(self.result["PROOF_SCOPE"], "FULL_PROFILE")
        self.assertEqual(self.result["PROVED_T_CAP"], 236)
        self.assertEqual(self.result["UNPROVED_ASSUMPTIONS"], [])

    def test_zero_domain_has_independent_complement_recount(self) -> None:
        # Build from every G[Z] (zero-zero G edges), independently of deg_Q.
        domain: set[tuple[int, ...]] = set()
        for mask in range(1 << 15):
            edges = [e for i, e in enumerate(c.EDGES_6) if mask >> i & 1]
            domain.add(tuple(sorted(5 - sum(v in e for e in edges) for v in range(6))))
        self.assertEqual(domain, set(c.zero_domain()))
        self.assertIn((5, 5, 5, 5, 5, 5), domain)
        self.assertIn((0, 0, 0, 0, 1, 1), domain)
        self.assertNotIn((0, 0, 0, 0, 0, 2), domain)
        self.assertNotIn((0, 0, 0, 0, 2, 4), domain)

    def test_analytic_chain_and_edge_sum_lemma(self) -> None:
        a = self.result["ANALYTIC_CERTIFICATE"]
        self.assertEqual((a["MAXIMUM"], a["ARGMAX_A"]), (236, 0))
        self.assertEqual([row[2] for row in a["PER_A_BOUND"]][:3], [236, 230, 228])
        self.assertEqual(a["DEGREE_SQUARE_LEMMA"]["GRAPHS_CHECKED"], 32768)
        rng = random.Random(649236)
        for n in range(1, 11):
            for _ in range(40):
                edges = [e for e in combinations(range(n), 2) if rng.random() < rng.random()]
                degrees = [sum(v in e for e in edges) for v in range(n)]
                self.assertLessEqual(sum(d * d for d in degrees), len(edges) * (len(edges) + 1))
        # Without graphicality the lemma fails, so the analytic chain needs it.
        nongraph = (0, 0, 0, 0, 0, 2)
        edges = sum(nongraph) // 2
        self.assertGreater(sum(x * x for x in nongraph), edges * (edges + 1))
        self.assertEqual(c.analytic_bound(0), 236)
        self.rejects(lambda: c.validate_state(c.State(0, (4, 4), (0, 0, 0, 0, 0, 2))), "graphical")

    def test_mixed_identity_and_nonnegative_remainder(self) -> None:
        rng = random.Random(649522)
        all_edges = set(combinations(range(20), 2))
        core, zero = set(range(14)), set(range(14, 20))
        positive = 0
        for density in (0, 0.2, 0.5, 0.8, 1):
            g = {e for e in sorted(all_edges) if rng.random() < density}
            h = all_edges - g
            m = {e for e in h if set(e) <= core}
            q = {e for e in h if set(e) <= zero}
            ng = {i: {j for j in range(20) if tuple(sorted((i, j))) in g} for i in range(20)}
            sigma = {i: len(ng[i] & zero) for i in core}
            zeta = {i: len(ng[i] & core) for i in zero}
            hd = {i: sum(i in e for e in m) for i in core}
            qd = {i: sum(i in e for e in q) for i in zero}
            p = (
                triangles(m, core)
                + triangles(q, zero)
                + sum(len(ng[i] & ng[j] & zero) for i, j in m)
                + sum(len(ng[i] & ng[j] & core) for i, j in q)
            )
            bare = (
                6 * len(m)
                + 14 * len(q)
                - sum(sigma[i] * hd[i] for i in core)
                - sum(zeta[i] * qd[i] for i in zero)
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

    def test_realization_fixtures_and_tampering(self) -> None:
        rows = self.result["REALIZATION_IDENTITY_CHECKS"]
        self.assertEqual([(r["T"], r["F"]) for r in rows], [(173, 194), (206, 219)])
        self.assertEqual([r["P_TERMS"] for r in rows], [(9, 1, 7, 4), (6, 0, 5, 2)])
        for r in rows:
            self.assertEqual(r["T"], r["F"] - sum(r["P_TERMS"]))
            self.assertLessEqual(r["T"], c.NEW_CAP)
        triples, pairs = c.REALIZATIONS[0]
        self.rejects(
            lambda: c.realization_check((triples, pairs.replace("5.15", "15.18"))), "linearity"
        )
        self.rejects(
            lambda: c.realization_check((triples, pairs.rsplit(" ", 1)[0])), "support counts"
        )
        self.rejects(
            lambda: c.realization_check((triples.replace("0.2.9", "0.2.13"), pairs)), "profile"
        )

    def test_load_bearing_negatives(self) -> None:
        n = self.result["NEGATIVE_CASES"]
        self.assertEqual(n["OMIT_LOW_PAIR_LABEL_CAP"]["BOUND"], 270)
        self.assertGreater(n["OMIT_LOW_PAIR_LABEL_CAP"]["BOUND"], 264)
        self.assertEqual(n["OMIT_ZERO_GRAPHICALITY"]["BOUND"], 238)
        self.assertEqual(n["WRONG_GOODMAN_298"]["BOUND"], 240)
        for key in ("OMIT_LOW_PAIR_LABEL_CAP", "OMIT_ZERO_GRAPHICALITY", "WRONG_GOODMAN_298"):
            self.assertGreater(n[key]["BOUND"], c.NEW_CAP)
            type(self).negative_count += 1
        wide = c.State(0, (6, 6), (0, 0, 0, 2, 2, 2))
        c.validate_state(wide, low_cap=6)
        self.assertEqual(c.objective(wide), 270)
        self.assertEqual(c.generic_objective(wide), 270)
        self.rejects(lambda: c.validate_state(wide), "low cross range")
        self.assertEqual(c.objective(ARGMAX, c.IDENTITY_CONSTANT + 4), 240)
        # Tied relaxation maximizers are all reported, in enumeration order.
        self.assertEqual(
            n["OMIT_LOW_PAIR_LABEL_CAP"]["ARGMAX"],
            [vars(wide), vars(c.State(0, (6, 6), (0, 0, 1, 1, 1, 3)))],
        )
        self.assertEqual(
            n["OMIT_ZERO_GRAPHICALITY"]["ARGMAX"],
            [
                vars(c.State(0, (4, 4), (0, 0, 0, 0, 0, 2))),
                vars(c.State(2, (4, 4), (0, 0, 0, 0, 0, 4))),
            ],
        )

    def test_negative_state_ranges_and_equal_sums(self) -> None:
        cases = [
            (replace(ARGMAX, a=-1), "d5"),
            (replace(ARGMAX, a=11), "d5"),
            (replace(ARGMAX, a=True), "d5"),
            (replace(ARGMAX, low=(-1, 4)), "low cross"),
            (replace(ARGMAX, low=(4, 5)), "low cross"),
            (replace(ARGMAX, low=(4, 3)), "symmetry"),
            (replace(ARGMAX, low=(4,)), "low cross"),
            (replace(ARGMAX, q=(0, 0, 0, 0, 1, 6)), "zero degree"),
            (replace(ARGMAX, q=(0, 0, 0, 1, 1, 0)), "symmetry"),
            (replace(ARGMAX, q=(0, 0, 0, 0, 0, 1)), "parity"),
            (replace(ARGMAX, a=2), "unequal"),
        ]
        for state, message in cases:
            self.rejects(lambda s=state: c.validate_state(s), message)
        self.rejects(lambda: c.graph_degrees(1 << 15), "mask")
        self.rejects(lambda: c.graph_degrees(-1), "mask")

    def test_route_b_all_integer_terms(self) -> None:
        new = c.route_terms(c.PROFILE, 236, 112)
        old = c.route_terms(c.PROFILE, 265, 112)
        c.check_terms(new, 236)
        c.check_terms(old, 265)
        self.assertEqual((len(new), len(old)), (215, 244))
        self.assertEqual(new[-1], (236, 313135356, 281, 198, 145061, 4828208))
        self.assertEqual(old[-1], (265, 313395448, 498, 198, 292404, 5172496))
        self.assertEqual(old[-2], (264, 313386292, 491, 198, 287651, 5160624))
        self.assertEqual(new, old[:215])
        self.assertEqual(max(new, key=lambda t: t[1]), new[-1])
        self.assertEqual(self.result["ARGMAX_TERM"], new[-1])
        self.assertEqual(self.result["NEW_ADMISSIBLE_BOUND"], 313135356)
        self.assertEqual(self.result["OWNER_BOUND_DELTA"], -260092)
        self.assertTrue(self.result["BELOW_NEXT_COMPETITOR_313395344"])
        self.assertTrue(self.result["ROW_BOUND_AT_OR_BELOW_INCUMBENT"])
        thresholds = [
            self.result[k]
            for k in (
                "STRICT_REDUCTION_THRESHOLD",
                "NEXT_COMPETITOR_THRESHOLD",
                "CURSOR_THRESHOLD",
                "INCUMBENT_CLOSURE_THRESHOLD",
            )
        ]
        self.assertEqual(thresholds, [264, 264, 264, 250])
        self.assertLess(old[-2][1], c.CURSOR_BOUND)
        self.assertLessEqual(c.route_terms(c.PROFILE, 250, 112)[-1][1], c.INCUMBENT)
        self.assertGreater(c.route_terms(c.PROFILE, 251, 112)[-1][1], c.INCUMBENT)
        self.assertEqual(self.result["FAMILY_BOUND_GAIN_CLAIMED"], 0)
        rational = Fraction(372228640 - 63838600 + 4828208) - Fraction(4 * 145061, 7)
        self.assertEqual(rational, 313135356)

    def test_negative_route_rounding_cap_and_threshold(self) -> None:
        good = c.route_terms(c.PROFILE, 236, 112)
        for index in (1, 2, 3, 4, 5):
            bad = list(good)
            term = list(bad[-1])
            term[index] += 1
            bad[-1] = (term[0], term[1], term[2], term[3], term[4], term[5])
            self.rejects(lambda bad=bad: c.check_terms(bad, 236), "arithmetic")
        self.rejects(lambda: c.check_terms(good[:-1], 236), "domain")
        self.rejects(lambda: c.check_terms(good[1:], 236), "domain")
        self.rejects(lambda: c.check_terms(good, 237), "domain")
        self.rejects(lambda: c.check_terms([*good, good[-1]], 236), "domain")
        # K4 floor instead of ceiling at T=236 (excess 1122 is not a multiple of 4).
        t, _, k4, contained, _, s3 = good[-1]
        self.assertEqual((2322 - 10 * (828 - 3 * t)) % 4, 2)
        floor_s4 = 679 * (k4 - 1) - 231 * contained
        floor_term = (t, 308390040 + s3 - 4 * floor_s4 // 7, k4 - 1, contained, floor_s4, s3)
        self.rejects(lambda: c.check_terms([*good[:-1], floor_term], 236), "arithmetic")
        # The S4 credit is exact here (7 | 112, 679, 231), so K4 is the live rounding.
        self.assertTrue(all(4 * x[4] % 7 == 0 for x in c.route_terms(c.PROFILE, 265, 112)))
        rounding = self.result["ROUNDING_CHECK"]
        self.assertEqual(rounding["K4_CEILING_STRICT_T_COUNT"], 33)
        self.assertEqual(rounding["K4_CEILING_STRICT_T_RANGE"], [200, 264])
        half = c.route_terms(c.PROFILE, 236, 112)
        index = next(i for i, x in enumerate(half) if x[2] > 0 and (30 * x[0] - 5958) % 4)
        self.assertEqual(half[index][0], 200)
        t, _, k4, _, _, s3 = half[index]
        low_s4 = max(112, 679 * (k4 - 1) - 231 * min(k4 - 1, 198))
        low_term = (t, 308390040 + s3 - 4 * low_s4 // 7, k4 - 1, min(k4 - 1, 198), low_s4, s3)
        self.assertNotEqual(low_term, half[index])
        half[index] = low_term
        self.rejects(lambda: c.check_terms(half, 236), "arithmetic")
        for cap in (21, 277, True):
            self.rejects(lambda cap=cap: c.route_terms(c.PROFILE, cap, 112), "cap range")
        self.rejects(lambda: c.route_terms(c.PROFILE, 236, -1), "base range")
        # Wrong cap: the inherited 265 reproduces the old bound, not an improvement.
        self.assertEqual(max(t[1] for t in c.route_terms(c.PROFILE, 265, 112)), c.OLD_BOUND)
        old = c.route_terms(c.PROFILE, 265, 112)
        self.assertEqual(c.largest_cap(old, c.OLD_BOUND, strict=False), 265)
        self.assertEqual(c.largest_cap(old, c.OLD_BOUND, strict=True), 264)
        self.assertEqual(c.largest_cap(old, 0, strict=True), 21)


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
