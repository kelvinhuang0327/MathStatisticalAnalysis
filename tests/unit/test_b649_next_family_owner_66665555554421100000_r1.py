"""Focused acceptance and adversarial checks for the full-profile T<=261 relaxation."""

from __future__ import annotations

import sys
import unittest
from collections import Counter
from fractions import Fraction
from itertools import combinations, product
from math import comb
from unittest.mock import patch

from lottolab.research import b649_next_family_owner_66665555554421100000_r1 as c


class OwnerCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = c.compute_result()
        cls.authority = c.frozen_authority()
        cls.rows, cls.report = c.relaxation()

    def test_frozen_row_and_target_only_authority(self) -> None:
        c.check_source_row(self.authority["ROW"], 112)
        self.assertEqual(self.result["FROZEN_HEAD"], c.FROZEN_HEAD)
        self.assertEqual(self.result["FROZEN_TREE"], c.FROZEN_TREE)
        self.assertEqual(self.authority["SCOPE"], "TARGET_ONLY_LOOKUP_NO_4647_ROW_REPLAY")
        for path, blob in self.authority["BLOBS"].items():
            self.assertEqual(c.digest(blob), c.FROZEN_HASHES[path])
        self.assertEqual(c.nb_recount(), (829, 34, 265))

    def test_degree_distribution_and_goodman_independently(self) -> None:
        degrees = [6] * 4 + [5] * 6 + [4] * 2 + [2] + [1] * 2 + [0] * 5
        self.assertEqual("".join(map(str, degrees)), c.PROFILE_ID)
        self.assertEqual((sum(degrees), sum(v * v for v in degrees)), (66, 332))
        mixed = sum(78 + 7 * d - d * d for d in degrees)
        self.assertEqual((mixed, comb(20, 3) - mixed // 2), (1690, 295))
        self.assertEqual(self.result["COMPLEMENT_CHOOSE2_SUM"], 901)
        self.assertEqual(self.result["F_CONSTANT"], 235)
        self.assertEqual(self.result["DEGREE_COUNTS"], {6: 4, 5: 6, 4: 2, 2: 1, 1: 2, 0: 5})

    def test_all_labelled_core_vectors_reduce_to_exact_symmetry_set(self) -> None:
        # A different enumeration: labelled product first, symmetry quotient second.
        reduced = set()
        count = 0
        for raw in product(*[range(7 - d) for d in c.CORE[4:]]):
            count += 1
            reduced.add((0, 0, 0, 0, *sorted(raw[:6]), *sorted(raw[6:8]), raw[8], *sorted(raw[9:])))
        self.assertEqual(count, 103680)
        self.assertEqual(reduced, set(c.sigma_vectors()))
        self.assertEqual(len(reduced), 4410)

    def test_zero_table_by_independent_edge_subset_enumeration(self) -> None:
        expected = {}
        counts = Counter()
        for edge_count in range(11):
            for edges in combinations(c.ZERO_EDGES, edge_count):
                adjacency = [set() for _ in range(5)]
                for u, v in edges:
                    adjacency[u].add(v)
                    adjacency[v].add(u)
                z = tuple(len(neighbours) + 2 for neighbours in adjacency)
                shape = tuple(sorted(z))
                counts[shape] += 1
                # Each triangle has three incident edges, and one common neighbour per edge.
                triangles = sum(len(adjacency[u] & adjacency[v]) for u, v in edges) // 3
                mask = sum(1 << c.ZERO_EDGES.index(edge) for edge in edges)
                for q in range(12):
                    cost = triangles + sum(max(0, z[u] + z[v] - q) for u, v in edges)
                    key = shape, q
                    expected[key] = min(expected.get(key, (cost, mask)), (cost, mask))
        observed, observed_counts = c.zero_table()
        self.assertEqual(observed, expected)
        self.assertEqual(observed_counts, counts)
        self.assertEqual((sum(counts.values()), len(counts)), (1024, 31))

    def test_all_balanced_pairs_and_exact_split_objectives(self) -> None:
        table, _ = c.zero_table()
        shapes = {key[0] for key in table}
        expected = {(s, z) for s in c.sigma_vectors() for z in shapes if sum(s) == sum(z)}
        self.assertEqual({(row.sigma, row.zeta) for row in self.rows}, expected)
        self.assertEqual(len(expected), 3779)
        for row in self.rows:
            r = sum(row.sigma)
            h = [8 - d + s for d, s in zip(c.CORE, row.sigma, strict=True)]
            a = [z - 2 for z in row.zeta]
            mixed_constant = Fraction(5 * sum(h) + 15 * sum(a), 2)
            self.assertEqual(mixed_constant, 60 + 10 * r)
            exact_f = (
                295
                - mixed_constant
                + sum(s * v for s, v in zip(row.sigma, h, strict=True))
                + sum(z * v for z, v in zip(row.zeta, a, strict=True))
            )
            self.assertEqual(exact_f, row.f)
            self.assertEqual(row.bound, row.f - row.core_floor - row.zero_floor)
            self.assertEqual(row.q, sum(s != 0 for s in row.sigma))

    def test_core_floor_is_minimum_over_every_neighbour_subset(self) -> None:
        maximizing = [row for row in self.rows if row.bound == 261]
        for row in maximizing:
            total = 0
            for i, (s, d) in enumerate(zip(row.sigma, c.CORE, strict=True)):
                candidates = [j for j in range(15) if j != i]
                h = 8 - d + s
                minimum = min(
                    sum(max(0, s + row.sigma[j] - 5) for j in neighbours)
                    for neighbours in combinations(candidates, h)
                )
                total += minimum
            self.assertEqual(total, row.directed_weight_sum)
            self.assertEqual(Fraction(total, 2).__ceil__(), row.core_floor)
        odd = next(row for row in self.rows if row.directed_weight_sum % 2)
        self.assertEqual(odd.core_floor, odd.directed_weight_sum // 2 + 1)

    def test_common_neighbour_cardinality_floor_and_wrong_universe(self) -> None:
        subsets = [{i for i in range(5) if mask & (1 << i)} for mask in range(32)]
        for left in subsets:
            for right in subsets:
                self.assertLessEqual(max(0, len(left) + len(right) - 5), len(left & right))
        left, right = {0, 1, 2}, {3, 4, 5}
        self.assertEqual(max(0, len(left) + len(right) - 6), len(left & right))
        # Assuming only five active core vertices here would overstate the P term.
        self.assertGreater(max(0, len(left) + len(right) - 5), len(left & right))

    def test_exact_remainder_identity_by_direct_triangle_counts(self) -> None:
        # Supplemental checks of the universal counting identity; these are not cap proofs.
        k, z = set(range(15)), set(range(15, 20))
        all_edges = set(combinations(range(20), 2))
        for shift in range(4):
            g = {e for e in all_edges if ((e[0] + 1) * (e[1] + 3) + shift) % 7 < 3}
            h = all_edges - g
            ng = {i: {j for j in range(20) if tuple(sorted((i, j))) in g} for i in range(20)}
            em = {e for e in h if set(e) <= k}
            eq = {e for e in h if set(e) <= z}
            sigma = {i: len(ng[i] & z) for i in k}
            zeta = {i: len(ng[i] & k) for i in z}
            hm = {i: sum(i in e for e in em) for i in k}
            aq = {i: sum(i in e for e in eq) for i in z}

            def triangles(vertices: set[int], edges: set[tuple[int, int]]) -> int:
                return sum(
                    all(e in edges for e in combinations(tri, 2))
                    for tri in combinations(sorted(vertices), 3)
                )

            p = (
                triangles(k, em)
                + triangles(z, eq)
                + sum(len(ng[u] & ng[v] & z) for u, v in em)
                + sum(len(ng[u] & ng[v] & k) for u, v in eq)
            )
            mixed = (
                5 * len(em)
                + 15 * len(eq)
                - sum(sigma[i] * hm[i] for i in k)
                - sum(zeta[i] * aq[i] for i in z)
            )
            self.assertEqual(mixed + p, triangles(k | z, h))
            self.assertGreaterEqual(p, 0)

    def test_proved_cap_and_both_load_bearing_remainder_floors(self) -> None:
        self.assertEqual(max(row.bound for row in self.rows), 261)
        self.assertEqual(sum(row.bound == 261 for row in self.rows), 5)
        self.assertEqual(max(row.f for row in self.rows), 275)
        self.assertGreater(max(row.f - row.core_floor for row in self.rows), 264)
        self.assertGreater(max(row.f - row.zero_floor for row in self.rows), 264)
        c.check_cap_claim(261, self.rows)
        with self.assertRaisesRegex(AssertionError, "below a relaxation"):
            c.check_cap_claim(260, self.rows)

    def test_omitted_graphs_and_domain_endpoints_are_rejected(self) -> None:
        with self.assertRaisesRegex(AssertionError, "all 1024 masks"):
            c.zero_table(range(1023))
        with self.assertRaisesRegex(AssertionError, "all 1024 masks"):
            c.zero_table([*range(1023), 0])
        good = {d: range(7 - d) for d in set(c.CORE)}
        for bad in ({**good, 1: range(5)}, {**good, 6: range(2)}):
            with self.assertRaisesRegex(AssertionError, "full-profile domains"):
                c.check_domains(bad, range(2, 7))
        with self.assertRaisesRegex(AssertionError, "full-profile domains"):
            c.check_domains(good, range(1, 7))

    def test_wrong_support_and_profile_premises_are_rejected(self) -> None:
        for kwargs in (
            {"capacity": 7},
            {"triple_count": 21},
            {"pair_count": 28},
            {"linear": False},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(AssertionError):
                c.premises(**kwargs)
        wrong = list(c.PROFILE)
        wrong[0], wrong[-1] = 5, 1  # Same degree sum, different distribution/square sum.
        with self.assertRaisesRegex(AssertionError, "degree profile"):
            c.premises(wrong)

    def test_wrong_frozen_source_and_row_metadata_are_rejected(self) -> None:
        for key, value in (
            ("TRIANGLE_CAP", 266),
            ("BOUND", c.OLD_BOUND - 1),
            ("SOURCE", c.ROW_SOURCE.replace("883", "882")),
            ("PROFILE_ID", "66665555554422000000"),
        ):
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "source mismatch"):
                c.check_source_row({**self.authority["ROW"], key: value}, 112)
        with self.assertRaises(AssertionError):
            c.check_source_row(self.authority["ROW"], 1680)
        with self.assertRaisesRegex(AssertionError, "wrong frozen source"):
            c.check_frozen_bytes(c.SEVEN, self.authority["BLOBS"][c.SEVEN] + b" ")
        with self.assertRaisesRegex(AssertionError, "wrong frozen source"):
            c.check_frozen_bytes(
                c.SPLIT, self.authority["BLOBS"][c.SPLIT].replace(b"679", b"678", 1)
            )

    def test_all_T_terms_integer_rational_and_frozen(self) -> None:
        actual = [c.route_term(t) for t in range(22, 266)]
        exact = [c.rational_term(t) for t in range(22, 266)]
        self.assertEqual(actual, exact)
        self.assertEqual(actual, c.frozen_route_terms(self.authority["BLOBS"]))
        self.assertEqual(len(actual), 244)
        self.assertEqual(actual[:240], self.result["ALL_T_TERMS"])
        self.assertTrue(all(term[4] % 7 == 0 for term in actual))

    def test_peak_gain_and_incumbent_scope(self) -> None:
        self.assertEqual(c.route_term(265), (265, 313397860, 499, 198, 293083, 5175296))
        self.assertEqual(c.route_term(261), (261, 313362012, 469, 198, 272713, 5127808))
        self.assertEqual(self.result["ARGMAX_T"], [261])
        self.assertEqual(self.result["OWNER_BOUND_REDUCTION"], 35848)
        self.assertEqual(self.result["GAP_ABOVE_INCUMBENT"], 98124)
        self.assertFalse(self.result["OWNER_EXCLUSION_PROVED"])
        self.assertEqual(self.result["PROOF_SCOPE"], "FULL_PROFILE")
        self.assertEqual(self.result["FAMILY_BOUND_GAIN_CLAIMED"], 0)
        self.assertEqual(self.result["NEW_WINNING_OUTCOMES"], 0)
        self.assertEqual(self.result["GLOBAL_K20_OPTIMUM"], "UNKNOWN")
        c.check_result_bytes(c.canonical(self.result), self.result)
        with self.assertRaisesRegex(AssertionError, "stored scientific result differs"):
            c.check_result_bytes(c.canonical({**self.result, "PROVED_T_CAP": 260}), self.result)

    def test_thresholds_from_all_prefix_maxima(self) -> None:
        terms = self.result["ORIGINAL_ALL_T_TERMS"]
        by_cap = {cap: max(row[1] for row in terms[: cap - 21]) for cap in range(22, 266)}
        strict = max(cap for cap, bound in by_cap.items() if bound < c.OLD_BOUND)
        closure = max(cap for cap, bound in by_cap.items() if bound < c.INCUMBENT)
        self.assertEqual((strict, closure), (264, 250))
        self.assertEqual(c.thresholds(terms), (strict, closure))
        self.assertLess(by_cap[250], c.INCUMBENT)
        self.assertGreaterEqual(by_cap[251], c.INCUMBENT)
        self.assertLess(by_cap[264], c.OLD_BOUND)
        self.assertEqual(by_cap[265], c.OLD_BOUND)
        with self.assertRaisesRegex(AssertionError, "missing T term"):
            c.thresholds(terms[1:])

    def test_actual_K4_floor_mutant_fails_the_same_crosscheck(self) -> None:
        t = 200
        k4 = max(0, (30 * t - 5954) // 4)  # Deliberately replace the required ceiling by a floor.
        contained = min(k4, 198)
        s4 = max(112, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * 829 + 11872 * (t - 22) - 30800
        bad = (t, 372228640 - 63838600 + s3 - 4 * s4 // 7, k4, contained, s4, s3)
        with self.assertRaisesRegex(AssertionError, "rounding/arithmetic"):
            c.check_route_term(bad)
        c.check_route_term(c.route_term(t))

    def test_Amax_ceiling_and_bound_off_by_one_are_rejected(self) -> None:
        t, _, k4, _, _, s3 = c.route_term(261)
        wrong_a = Fraction(596, 3).__ceil__()
        s4 = max(112, 448 * wrong_a + 679 * (k4 - wrong_a))
        bad = (t, 372228640 - 63838600 + s3 - 4 * s4 // 7, k4, wrong_a, s4, s3)
        with self.assertRaisesRegex(AssertionError, "rounding/arithmetic"):
            c.check_route_term(bad)
        good = c.route_term(261)
        with self.assertRaisesRegex(AssertionError, "rounding/arithmetic"):
            c.check_route_term((261, good[1] - 1, *good[2:]))
        c.check_route_term(good)

    def test_disabling_new_core_floor_falsifies_certificate_then_restores(self) -> None:
        c.relaxation.cache_clear()
        try:
            with (
                patch.object(c, "core_floor", return_value=(0, 0)),
                self.assertRaisesRegex(AssertionError, "relaxation maximum changed"),
            ):
                c.relaxation()
        finally:
            c.relaxation.cache_clear()
        restored_rows, restored_report = c.relaxation()
        self.assertEqual(restored_report["CAP"], 261)
        self.assertEqual(
            restored_report["ALL_CONFIGURATION_SHA256"], self.report["ALL_CONFIGURATION_SHA256"]
        )
        self.assertEqual(restored_rows, self.rows)

    def test_negative_case_results_and_no_pipeline_import(self) -> None:
        self.assertEqual(len(self.result["NEGATIVE_CASE_RESULTS"]), 13)
        self.assertTrue(
            all(
                value.startswith("PASS_REJECTED:")
                for value in self.result["NEGATIVE_CASE_RESULTS"].values()
            )
        )
        self.assertFalse(any(name.startswith("ortools") for name in sys.modules))
        self.assertFalse(any(name.startswith("lottolab.research.b649_k20") for name in sys.modules))
        self.assertEqual(self.result["FULL_4647_ROW_PIPELINE"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
