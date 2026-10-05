"""Focused, falsifiable tests for exact scoring, primary ordering and durable resume."""
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("conditional_beam", ROOT / "src/lottolab/research/b649_k20_v7_conditional_destroy3_beam_r1.py")
beam = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(beam)


class ConditionalBeamTests(unittest.TestCase):
    def test_native_all_toy_marginals_and_conditional_contexts(self):
        native = beam.Native(n=12, workers=2)
        tickets = list(itertools.combinations(range(1, 13), 6))
        outcomes = list(itertools.combinations(range(1, 13), 7))
        try:
            self.assertEqual(native.total, math.comb(12, 6))
            self.assertEqual({native.ticket(i) for i in range(native.total)}, set(tickets))
            previous = None
            for frozen in [[], [(1, 2, 3, 4, 5, 6)], [(1, 2, 3, 4, 5, 6), (1, 3, 6, 8, 9, 12)]]:
                values, stats = native.score(frozen)
                residual = [set(e) for e in outcomes if all(len(set(t).intersection(e)) < 3 for t in frozen)]
                expected = np.array([sum(len(set(native.ticket(i)).intersection(e)) >= 3 for e in residual)
                                     for i in range(native.total)], dtype=np.int32)
                np.testing.assert_array_equal(values, expected)
                self.assertEqual(stats["SUM_TOP_COUNTS"], 7 * len(residual))
                self.assertEqual(stats["SUM_MARGINALS"], int(expected.sum()))
                if previous is not None:
                    self.assertTrue(np.all(values <= previous))
                    self.assertTrue(np.any(values < previous))
                previous = values
                # The equality gate demonstrably rejects a one-unit scoring defect.
                mutated = values.copy()
                mutated[0] += 1
                with self.assertRaises(AssertionError):
                    np.testing.assert_array_equal(mutated, expected)
        finally:
            native.close()

    def test_state_sha_and_signature_permutation_invariance(self):
        sample = beam.signature_sample()[:100]
        a = (1, 2, 3, 4, 5, 6)
        b = (4, 5, 6, 7, 8, 9)
        self.assertEqual(beam.state([], [a, b], 12, sample), beam.state([], [b, a], 12, sample))
        self.assertEqual(beam.ticket_distance([a, b], [b, a]), 0)
        self.assertEqual(beam.ticket_distance([a], [b]), 3)

    def test_coverage_primary_then_residual_then_ticket_then_sha(self):
        def s(sha, count, sig, ticket):
            return {"SHA256": sha, "COVERAGE7": count, "SIGNATURE": hex(sig), "TICKETS": [ticket]}
        a = s("a", 10, 0, [1, 2, 3, 4, 5, 6])
        b = s("b", 10, 1, [1, 2, 3, 4, 5, 7])
        c = s("c", 10, 15, [1, 2, 3, 4, 5, 8])
        d = s("d", 9, 65535, [20, 21, 22, 23, 24, 25])
        picked, stats = beam.choose([d, b, c, a], 2)
        self.assertEqual([x["SHA256"] for x in picked], ["a", "c"])
        self.assertEqual(stats["DIVERSITY_SAVES"], 1)
        e = s("e", 10, 15, [20, 21, 22, 23, 24, 25])
        picked, _ = beam.choose([a, c, e], 2)
        self.assertEqual([x["SHA256"] for x in picked], ["a", "e"])
        picked, _ = beam.choose([e, dict(e, SHA256="f"), a], 2)
        self.assertEqual([x["SHA256"] for x in picked], ["a", "e"])
        # Primary-order mutation must change this observed result.
        picked, _ = beam.choose([a, b, c, dict(d, COVERAGE7=11)], 2)
        self.assertEqual(picked[0]["SHA256"], "d")

    def test_deduplication_roundtrip_and_conflict(self):
        s = beam.state([], [(1, 2, 3, 4, 5, 6)], 10, np.array([127], dtype=np.uint64))
        reloaded = json.loads(beam.compact(s))
        picked, _ = beam.choose([s, reloaded], 32)
        self.assertEqual(len(picked), 1)
        with self.assertRaisesRegex(RuntimeError, "CANONICAL_STATE_CONFLICT"):
            beam.choose([s, dict(s, COVERAGE7=11)], 32)

    def test_selection_source_priority_and_pre_scoring_freeze(self):
        source, _ = beam.source_document()
        first = beam.selection_document(source)
        second = beam.selection_document(json.loads(json.dumps(source)))
        self.assertEqual(first, second)
        self.assertTrue(first["SOURCE_FIELDS_SUFFICIENT"])
        self.assertEqual(len(first["DESTROY_TRIPLES"]), 32)
        ranking = first["RANKED_SOURCE_EVIDENCE"]
        self.assertTrue(all(x["BEST_COUNT_TIE_MULTIPLICITY"] == 16 for x in ranking[:32]))
        keys = [(-x["BEST_COUNT_TIE_MULTIPLICITY"], -x["STRUCTURAL_DISTANCE_PAIR_SUM"], tuple(x["POSITIONS"])) for x in ranking]
        self.assertEqual(keys, sorted(keys))
        fallback = beam.selection_document({})
        self.assertFalse(fallback["SOURCE_FIELDS_SUFFICIENT"])
        self.assertEqual(fallback, beam.selection_document({}))

    def test_atomic_immutable_and_resume_reuses_no_scorer(self):
        with tempfile.TemporaryDirectory() as td, patch.object(beam, "RUN", Path(td)):
            p = Path(td) / "frozen.json"
            beam.atomic_json(p, {"a": 1}, immutable=True)
            beam.atomic_json(p, {"a": 1}, immutable=True)
            with self.assertRaisesRegex(RuntimeError, "IMMUTABLE_IDENTITY_CONFLICT"):
                beam.atomic_json(p, {"a": 2}, immutable=True)
            coverage = beam.OUTCOMES7 - 7
            stats = {"TICKETS_SCORED": beam.TOTAL, "SUM_TOP_COUNTS": 49,
                     "SUM_MARGINALS": 7 * sum(math.comb(7, j) * math.comb(42, 6-j) for j in range(3, 7))}
            row = {"PARENT_SHA256": "parent", "CONTRACT_SHA256": "contract", "DEPTH": 2, "ENUMERATION": stats}
            row["PAYLOAD_SHA256"] = beam.digest(row)
            path = Path(td) / "enumerations/01-1-2-3/2-parent.json"
            beam.atomic_json(path, row)
            # An object without score() proves no enumeration is called on resume.
            resumed = beam.expansion(object(), [], {"SHA256": "parent", "COVERAGE7": coverage}, None, "01-1-2-3", 2, "contract")
            self.assertEqual(resumed, row)
            row["ENUMERATION"]["SUM_TOP_COUNTS"] += 1
            beam.atomic_json(path, row)
            with self.assertRaisesRegex(RuntimeError, "ENUMERATION_CHECKSUM_MISMATCH"):
                beam.expansion(object(), [], {"SHA256": "parent", "COVERAGE7": coverage}, None, "01-1-2-3", 2, "contract")

    def test_global_identity_detects_wrong_coverage_or_missing_ticket(self):
        coverage = beam.OUTCOMES7 - 7
        stats = {"TICKETS_SCORED": beam.TOTAL, "SUM_TOP_COUNTS": 49,
                 "SUM_MARGINALS": 7 * sum(math.comb(7, j) * math.comb(42, 6-j) for j in range(3, 7))}
        beam.verify_identities(stats, coverage)
        for changed in [dict(stats, TICKETS_SCORED=beam.TOTAL-1), dict(stats, SUM_TOP_COUNTS=50), dict(stats, SUM_MARGINALS=stats["SUM_MARGINALS"]+1)]:
            with self.assertRaisesRegex(RuntimeError, "EXACT_GLOBAL_SCORE_IDENTITY_MISMATCH"):
                beam.verify_identities(changed, coverage)

    def test_incomplete_summary_keeps_incumbent_and_precise_accounting(self):
        source, start = beam.source_document()
        parity = {"CHECKS": 210, "PARITY_MISMATCHES": 0, "CONDITIONAL_ENUMERATIONS": 3, "GLOBAL_TICKETS_SCORED": 3*beam.TOTAL}
        best = {"TICKETS": [], "COVERAGE7": beam.START_COUNT//7-1, "SHA256": "a", "PORTFOLIO": start, "POSITIONS": [0, 1, 2]}
        row = {"BEST": best, "CONDITIONAL_ENUMERATIONS": 57, "BEAM_STATES_GENERATED": 1368,
               "BEAM_STATES_RETAINED": 88, "TIE_GROUPS": 3, "DIVERSITY_SAVES": 2}
        result = beam.summary([row], start, parity)
        self.assertEqual(result["SCIENTIFIC_RESULT"], "IN_PROGRESS")
        self.assertEqual(result["BEST_SHA256"], beam.START_SHA)
        self.assertEqual(result["BEST_COUNT"], beam.START_COUNT)
        self.assertEqual(result["GLOBAL_TICKETS_SCORED"], 57*beam.TOTAL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
