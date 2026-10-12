from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from lottolab.research import b649_eight_row_family_authority_r1 as authority


class EightRowFamilyAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.frozen_blob, cls.donor_blob, cls.identity = authority.load_live_sources()
        cls.result = authority.build_authority(cls.frozen_blob, cls.donor_blob, cls.identity)

    def test_full_profile_proof_and_exact_owner_bound(self) -> None:
        proof = self.result["A_PROOF"]
        self.assertEqual(self.result["PROOF_SCOPE"], "FULL_PROFILE")
        self.assertEqual(proof["PROFILE_DEGREE_DISTRIBUTION"],
                         {"6": 3, "5": 9, "2": 1, "1": 1, "0": 6})
        self.assertTrue(proof["A_LE_188_PLUS_M_PLUS_3E"])
        self.assertTrue(proof["M_PLUS_3E_LE_4"])
        self.assertTrue(proof["A_LE_192"])
        self.assertEqual(self.result["OLD_A_CAP"], 200)
        self.assertEqual(self.result["NEW_A_CAP"], 192)
        self.assertEqual(self.result["OLD_OWNER_BOUND"], 313398532)
        self.assertEqual(self.result["NEW_OWNER_BOUND"], 313397476)
        self.assertEqual(self.result["OWNER_DELTA"], 1056)

    def test_complete_frozen_triangle_domain_and_integer_rounding(self) -> None:
        terms = self.result["NEW_ENVELOPE_TERMS"]
        self.assertEqual(len(terms), 243)
        self.assertEqual([terms[0]["T"], terms[-1]["T"]], [22, 264])
        self.assertTrue(all(a["BOUND"] < b["BOUND"] for a, b in zip(terms, terms[1:])))
        self.assertEqual(self.result["NEW_ENVELOPE_PEAK"]["T"], 264)
        self.assertEqual(self.result["NEW_ENVELOPE_PEAK"]["K4_LOWER_BOUND"], 489)
        self.assertEqual(self.result["NEW_ENVELOPE_PEAK"]["S4_FLOOR"], 287679)
        self.assertEqual(self.result["NEW_ENVELOPE_PEAK"]["S3"], 5171824)
        self.assertEqual(self.result["NEW_ENVELOPE_PEAK"]["BOUND"], 313397476)
        self.assertEqual(self.result["T_CAP"], 264)
        self.assertEqual(self.result["T_CAP_STATUS"], "UNCHANGED_FROZEN_ACCEPTED_PREMISE")

    def test_local_exact_counts_match_frozen_route(self) -> None:
        self.assertEqual(
            authority.local_intersection_weights(),
            authority.EXPECTED_LOCAL_WEIGHTS,
        )
        self.assertEqual((self.result["S1"], self.result["S2"]),
                         (372228640, 63838600))
        self.assertEqual(self.result["BONFERRONI_MULTIPLICITY_CHECK"][-1],
                         {"WINNERS": 7, "NUMERATOR_OVER_7": 7})

    def test_eight_certificate_family_overlay_preserves_other_authority(self) -> None:
        self.assertEqual(self.result["LEDGER_ROWS"], 4647)
        self.assertEqual(self.result["CERTIFICATES_BEFORE"], 7)
        self.assertEqual(self.result["CERTIFICATES_AFTER"], 8)
        self.assertEqual(self.result["CHANGED_PROFILE_COUNT"], 1)
        self.assertEqual(self.result["CHANGED_PROFILE_ID"], authority.PROFILE_ID)
        self.assertEqual(self.result["FAMILY_BOUND_AFTER"], 313398248)
        self.assertEqual(self.result["FAMILY_BOUND_DELTA"], 284)
        self.assertEqual(self.result["NEXT_TIED_OWNERS"], authority.NEXT_TIED_OWNERS)
        self.assertEqual(self.result["EXPECTED_REMAINING_GAP"], 134360)
        self.assertEqual(self.result["CERTIFICATE_PROFILE_IDS_AFTER"][:-1],
                         self.result["CERTIFICATE_PROFILE_IDS_BEFORE"])
        self.assertEqual(self.result["PRESERVED_SIX_ROW_STATUS"],
                         json.loads(self.frozen_blob)["PRESERVED_SIX_ROW_STATUS"])
        self.assertEqual(self.result["GLOBAL_K20_OPTIMUM"], "UNKNOWN")
        self.assertEqual(self.result["NEW_STRICT_WINNING_OUTCOMES"], 0)

    def test_frozen_realization_is_only_a_sanity_check(self) -> None:
        witness = self.result["FROZEN_REALIZATION_CHECK"]
        self.assertEqual(witness["CHECK_SCOPE"], "ONE_PINNED_REALIZATION_ONLY")
        self.assertEqual(witness["TRIPLE_SUPPORTS"], 22)
        self.assertEqual(witness["PAIR_SUPPORTS"], 27)
        self.assertEqual(witness["SIMPLE_OVERLAP_GRAPH_EDGES"], 93)

    def test_wrong_profile_and_out_of_scope_T_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported profile"):
            authority.prove_a_cap("66655555555521000001")
        with self.assertRaisesRegex(ValueError, "T outside frozen proof range"):
            authority.envelope_terms(265, 192, 112, authority.EXPECTED_LOCAL_WEIGHTS)
        with self.assertRaisesRegex(ValueError, "T outside frozen proof range"):
            authority.envelope_terms(21, 192, 112, authority.EXPECTED_LOCAL_WEIGHTS)

    def test_tampered_bound_and_source_identity_are_rejected(self) -> None:
        changed = json.loads(self.frozen_blob)
        changed["NEW_OWNER_ROWS"][authority.PROFILE_ID]["bound"] += 1
        changed_blob = json.dumps(changed).encode()
        with self.assertRaisesRegex(ValueError, "frozen input SHA256 mismatch"):
            authority.build_authority(changed_blob, self.donor_blob, self.identity)

        bad_identity = dict(self.identity)
        bad_identity["donor_head"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "source identity mismatch"):
            authority.build_authority(self.frozen_blob, self.donor_blob, bad_identity)

    def test_saved_result_matches_deterministic_recount(self) -> None:
        saved = authority.ROOT / authority.RESULT_PATH
        if saved.exists():
            self.assertEqual(saved.read_bytes(), authority.serialize_result(self.result))


if __name__ == "__main__":
    unittest.main()
