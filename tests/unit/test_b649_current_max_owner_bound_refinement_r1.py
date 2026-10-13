"""Focused proof checks, adversarial inputs, and two independent finite recounts."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product

from lottolab.research import b649_current_max_owner_bound_refinement_r1 as research


class OwnerBoundRefinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = research.compute_result()
        cls.weights = cls.result["LOCAL_INTERSECTION_RECOUNT"]

    def test_full_profile_and_two_goodman_counts(self) -> None:
        result = self.result
        self.assertEqual(result["PROOF_SCOPE"], "FULL_PROFILE")
        self.assertEqual(result["DEGREE_DISTRIBUTION"], {"0": 6, "1": 1, "2": 1, "5": 9, "6": 3})
        self.assertEqual((result["CORE"], result["ZERO"], result["DEGREE_SUM"]), (14, 6, 66))
        self.assertEqual((result["G_EDGES"], result["H_EDGES"]), (93, 97))
        self.assertEqual((result["GOODMAN_PHI"], result["H_IE_PHI"]), (298, 298))
        self.assertEqual(result["H_DEGREE_CHOOSE_2_SUM"], 904)
        self.assertEqual(result["WEDGE_COUNT"], 832)

    def test_all_symmetric_relaxed_states_and_maximum(self) -> None:
        proof = self.result["RELAXATION_COMPLETENESS"]
        self.assertEqual((proof["STATE_COUNT"], proof["CAP"]), (874, 258))
        self.assertEqual(
            proof["ARGMAX_STATES"],
            [{"a": 1, "q": 4, "p": 5, "r": 10, "zeta": [1, 1, 1, 1, 1, 5], "T_UPPER": 258}],
        )
        for row in research.relaxed_states():
            self.assertEqual(sum(row["zeta"]), row["r"])
            self.assertEqual(row["r"] % 2, 0)
            self.assertLessEqual(row["T_UPPER"], 258)

    def test_independent_labelled_coordinate_relaxation(self) -> None:
        # Enumerate all 6^6 labelled zero degree tuples and all 2^9 labelled
        # binary core tuples. Compress only by sum after observing all tuples.
        max_squares = {}
        for zeta in product(range(1, 7), repeat=6):
            total = sum(zeta)
            max_squares[total] = max(max_squares.get(total, -1), sum(x * x for x in zeta))
        best = -1
        for binary_sigma in product((0, 1), repeat=9):
            for q, p in product(range(5), range(6)):
                sigma = (0, 0, 0, *binary_sigma, q, p)
                degrees = (6, 6, 6, *([5] * 9), 2, 1)
                r = sum(sigma)
                if r % 2 or r not in max_squares:
                    continue
                # Unreduced general mixed-triangle expression, independent of
                # the production 244-8a-6q+q^2-5p+p^2 polynomial.
                m_edges, l_edges = (32 + r) // 2, (r - 6) // 2
                core_loss = sum(s * (7 - d + s) for s, d in zip(sigma, degrees, strict=True))
                zero_loss = max_squares[r] - r
                value = 298 - 6 * m_edges - 14 * l_edges + core_loss + zero_loss
                best = max(best, value)
        self.assertEqual(best, self.result["NEW_T_CAP"])

    def test_decomposition_on_every_five_vertex_simple_graph(self) -> None:
        # Every labelled graph on five vertices, with a 3/2 split. This tests
        # the exact identity and four remainder counts; it is not the proof
        # of the 20-vertex cap, whose complete mapping is stated in the module.
        edges = list(combinations(range(5), 2))
        checked = 0
        for mask in range(1 << len(edges)):
            graph = [set() for _ in range(5)]
            for bit, (x, y) in enumerate(edges):
                if mask & (1 << bit):
                    graph[x].add(y)
                    graph[y].add(x)
            row = research.decomposition_check(graph, {0, 1, 2})
            self.assertTrue(all(x >= 0 for x in row["REMAINDER_PARTS"]))
            self.assertEqual(row["P"], sum(row["REMAINDER_PARTS"]))
            checked += 1
        self.assertEqual(checked, 1024)

    def test_pinned_realization_is_only_a_sanity_check(self) -> None:
        row = self.result["PINNED_REALIZATION_CHECK"]
        self.assertEqual(row["CHECK_SCOPE"], "ONE_REALIZATION_SANITY_ONLY")
        self.assertEqual(row["T"] + row["H_TRIANGLES"], 298)
        self.assertLessEqual(row["T"], 258)
        self.assertTrue(all(1 <= z <= 6 for z in row["ZETA"].values()))
        self.assertEqual(sum(row["SIGMA"].values()), sum(row["ZETA"].values()))
        self.assertGreaterEqual(row["P"], 0)

    def test_each_missing_or_false_necessary_premise_is_rejected(self) -> None:
        for key in research.REQUIRED_PREMISES:
            with self.subTest(key=key):
                premises = deepcopy(research.REQUIRED_PREMISES)
                del premises[key]
                with self.assertRaisesRegex(ValueError, "necessary premise"):
                    research.prove_cap(premises=premises)
                premises = deepcopy(research.REQUIRED_PREMISES)
                premises[key] = False
                with self.assertRaisesRegex(ValueError, "necessary premise"):
                    research.prove_cap(premises=premises)

    def test_zero_lower_bound_is_load_bearing(self) -> None:
        rows = list(research.relaxed_states(zero_min=0))
        best = max(rows, key=lambda row: row["T_UPPER"])
        self.assertGreater(best["T_UPPER"], 258)
        self.assertIn(0, best["zeta"])

    def test_cross_edge_balance_is_load_bearing(self) -> None:
        # One concrete point of the larger domain suffices to disprove 258
        # when this necessary equality is omitted.
        a, q, p, zeta = 0, 0, 0, [6] * 6
        self.assertNotEqual(a + q + p, sum(zeta))
        value = 244 - 8 * a - 6 * q + q * q - 5 * p + p * p + sum(x * x for x in zeta)
        self.assertGreater(value, 258)

    def test_wrong_cap_and_profile_are_rejected(self) -> None:
        for cap in (257, 0, -1, 258.0, True):
            with self.subTest(cap=cap), self.assertRaisesRegex(ValueError, "cap"):
                research.prove_cap(claimed_cap=cap)
        for profile in ("66555555555540000000", "66655555555521000001", research.PROFILE[::-1]):
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, "profile"):
                research.prove_cap(profile=profile)
        self.assertEqual(research.prove_cap(claimed_cap=258)["CAP"], 258)

    def test_wrong_K4_rounding_is_rejected(self) -> None:
        row = research.route_term(205, self.weights)
        self.assertEqual(Fraction(2356 - 10 * row["OPEN_WEDGES"], 4), Fraction(93, 2))
        row["K4_LOWER_BOUND"] -= 1
        with self.assertRaisesRegex(ValueError, "K4 rounding"):
            research.validate_rounding(row)

    def test_wrong_final_rounding_on_nonintegral_credit_is_rejected(self) -> None:
        # Actual weights are multiples of seven. Perturb a weight only in
        # this arithmetic test to force a nonintegral final credit.
        weights = dict(self.weights)
        weights["K4_PAIR_ONLY"] += 1
        row = research.route_term(263, weights)
        exact = Fraction(row["EXACT_BOUND_NUMERATOR"], row["EXACT_BOUND_DENOMINATOR"])
        self.assertNotEqual(exact.denominator, 1)
        self.assertEqual(row["BOUND"], research.ceil_fraction(exact))
        row["BOUND"] = exact.numerator // exact.denominator
        with self.assertRaisesRegex(ValueError, "final rounding"):
            research.validate_rounding(row)

    def test_modified_certificate_sources_are_rejected(self) -> None:
        frozen = research.git(
            research.ROOT, "show", f"{research.FROZEN_HEAD}:{research.FROZEN_RESULT}"
        )
        donor = research.git(
            research.ROOT, "show", f"{research.DONOR_HEAD}:{research.DONOR_RESULT}"
        )
        for f, d in ((frozen + b" ", donor), (frozen, donor + b" ")):
            with self.assertRaisesRegex(ValueError, "modified .*certificate source"):
                research.validate_source_bytes(f, d)
        mutated = json.loads(donor)
        mutated["A_PROOF"]["PROOF"] = "claim without a proof"
        with self.assertRaisesRegex(ValueError, "modified .*certificate source"):
            research.validate_source_bytes(frozen, json.dumps(mutated).encode())

    def test_modified_Route_B_source_bytes_are_rejected(self) -> None:
        path = "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py"
        blob = (research.ROOT / path).read_bytes()
        self.assertEqual(research.verify_source_file(path, blob), research.sha256(blob))
        with self.assertRaisesRegex(ValueError, "modified Route-B source"):
            research.verify_source_file(path, blob + b"\n# changed\n")

    def test_all_envelope_terms_and_competitor_threshold(self) -> None:
        result = self.result
        terms = result["NEW_ENVELOPE_TERMS"]
        self.assertEqual([row["T"] for row in terms], list(range(22, 259)))
        self.assertEqual((len(terms), result["OLD_T_TERM_COUNT"]), (237, 243))
        for row in terms:
            research.validate_rounding(row)
        self.assertEqual(result["MAX_SUFFICIENT_T_CAP"], 263)
        self.assertLessEqual(result["SUFFICIENT_CAP_BOUND"], 313396120)
        self.assertGreater(result["NEXT_CAP_BOUND"], 313396120)
        self.assertEqual(
            (result["OLD_BOUND"], result["NEW_ADMISSIBLE_BOUND"]), (313397476, 313343704)
        )
        self.assertEqual(result["OWNER_BOUND_DELTA"], 53772)
        self.assertEqual(result["ARGMAX_TERM"]["T"], 258)
        self.assertEqual(result["ARGMAX_TERM"]["K4_LOWER_BOUND"], 444)
        self.assertEqual(result["ARGMAX_TERM"]["S4_FLOOR"], 257124)
        self.assertEqual(result["ARGMAX_TERM"]["S3"], 5100592)

    def test_frozen_A_proof_full_scope_and_caveat_preserved(self) -> None:
        result = self.result
        a_proof = result["EXISTING_A_LE_192_APPLICABILITY"]
        self.assertEqual(a_proof["PROOF_SCOPE"], "FULL_PROFILE")
        self.assertTrue(a_proof["A_LE_192"])
        self.assertEqual(result["SOURCE_JUDGE_CAVEAT"], "BLOCKED_UNVERIFIABLE")
        self.assertEqual(result["JUDGE_MODE"], "SELF_CHECK_ONLY")
        self.assertEqual(result["JUDGE_UPGRADE"], "NONE")
        self.assertEqual(result["FAMILY_BOUND_GAIN_CLAIMED"], 0)
        self.assertEqual(result["NEW_WINNING_OUTCOMES"], 0)
        self.assertEqual(result["GLOBAL_K20_OPTIMUM"], "UNKNOWN")
        self.assertEqual(result["HEAVY_SOLVER_STARTED"], "NO")

    def test_result_replay_checks_all_scientific_claims(self) -> None:
        saved = json.loads(json.dumps(self.result))
        saved["CPU_SECONDS"] = 123
        research.validate_result_replay(saved, self.result)
        for field in ("NEW_T_CAP", "NEW_ADMISSIBLE_BOUND", "PROOF_SCOPE", "ARGMAX_TERM"):
            altered = deepcopy(saved)
            altered[field] = "tampered"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "scientific claims"):
                research.validate_result_replay(altered, self.result)


if __name__ == "__main__":
    unittest.main()
