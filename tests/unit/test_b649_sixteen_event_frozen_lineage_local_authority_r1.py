from __future__ import annotations

import unittest
from typing import Any

from lottolab.research import (
    b649_sixteen_event_frozen_lineage_local_authority_r1 as authority,
)


class SixteenEventFrozenLineageAuthorityTests(unittest.TestCase):
    result: dict[str, Any]
    frozen: dict[str, authority.Row]
    after: dict[str, authority.Row]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.result, cls.frozen, cls.after = authority.build_candidate()

    def test_sixteen_event_overlay_and_frontier(self) -> None:
        result = self.result
        overlay = result["LEDGER_OVERLAY"]
        family = result["FAMILY_AFTER"]

        self.assertEqual(result["UPDATE_EVENTS"], 16)
        self.assertEqual(result["PREVIOUS_EVENTS"], 11)
        self.assertEqual(result["NEW_EVENTS"], 5)
        self.assertEqual(result["DISTINCT_CHANGED_PROFILES"], 15)
        self.assertEqual(overlay["ROWS_BEFORE"], 4_647)
        self.assertEqual(overlay["ROWS_AFTER"], 4_647)
        self.assertEqual(overlay["UNCHANGED_ROWS_FROM_FROZEN"], 4_632)
        self.assertEqual(overlay["UNCHANGED_ROWS_FROM_ELEVEN_EVENT"], 4_642)
        self.assertEqual(overlay["FROZEN_LEDGER_UNCHANGED"], "YES")
        self.assertEqual(overlay["UNRELATED_ROW_MUTATION"], "NONE")

        self.assertEqual(family["FAMILY_BOUND"], 313_395_060)
        self.assertEqual(
            family["TIED_OWNERS"],
            ["66655555555332000000", "66655555555421100000"],
        )
        self.assertEqual(family["NEXT_COMPETING_BOUND"], 313_394_776)
        self.assertEqual(family["NEXT_COMPETING_OWNERS"], ["66555555555431100000"])
        self.assertEqual(
            family["CURSOR"],
            {"ID": authority.CURSOR_ID, "BOUND": authority.CURSOR_BOUND},
        )
        self.assertEqual(result["FAMILY_DELTA_FROM_FROZEN"], 3_472)
        self.assertEqual(result["FAMILY_DELTA_FROM_ELEVEN_EVENT"], 284)
        self.assertEqual(result["RESOLVED_ROWS_ABOVE_INCUMBENT"], 1_369)
        self.assertEqual(result["UNRESOLVED_CURSOR"]["ID"], authority.CURSOR_ID)
        self.assertEqual(result["UNRESOLVED_CURSOR"]["BOUND"], authority.CURSOR_BOUND)
        self.assertEqual(result["NEW_WINNING_OUTCOMES"], 0)
        self.assertEqual(result["GLOBAL_K20_OPTIMUM"], "UNKNOWN")
        self.assertEqual(result["FORMAL_AUTHORITY_ACCEPTANCE"], "NOT_CLAIMED")

    def test_exact_11_event_base_and_donor_authority_are_retained(self) -> None:
        eleven = self.result["ELEVEN_EVENT_AUTHORITY"]
        self.assertEqual(eleven["HEAD"], authority.ELEVEN_HEAD)
        self.assertEqual(eleven["TREE"], authority.ELEVEN_TREE)
        self.assertEqual(eleven["RESULT_SHA256"], authority.ELEVEN_RESULT_SHA256)
        self.assertEqual(eleven["SOURCE_SHA256"], authority.ELEVEN_SOURCE_SHA256)
        self.assertEqual(eleven["TEST_SHA256"], authority.ELEVEN_TEST_SHA256)
        self.assertEqual(eleven["SOURCE_REPLAY_MATCH"], "YES")

        frozen = self.result["FROZEN_ROUTE_B_AUTHORITY"]
        self.assertEqual(frozen["FROZEN_HEAD"], authority.FROZEN_HEAD)
        self.assertEqual(frozen["FROZEN_TREE"], authority.FROZEN_TREE)
        self.assertEqual(frozen["SOURCE_PINS"], authority.FROZEN_ROUTE_B_SOURCE_PINS)

        t257 = self.result["T257_DONOR"]
        self.assertEqual(t257["HEAD"], authority.T257_HEAD)
        self.assertEqual(t257["TREE"], authority.T257_TREE)
        self.assertEqual(t257["PROOF_SCOPE"], "FULL_PROFILE")
        self.assertEqual(t257["PROOF_APPLICABILITY"], "VERIFIED")

        t243 = self.result["T243_DONOR"]
        self.assertEqual(t243["HEAD"], authority.T243_HEAD)
        self.assertEqual(t243["MATHEMATICAL_BASE_HEAD"], authority.T243_BASE_HEAD)
        self.assertEqual(t243["MATHEMATICAL_BASE_TREE"], authority.T243_BASE_TREE)
        self.assertEqual(t243["ORIGINAL_FRESH_CONTEXT_VERDICT"], "VERIFIED_WITH_CAVEATS")
        self.assertEqual(t243["ORIGINAL_JUDGE_REPORT"], "NOT_RECONSTRUCTED")
        self.assertEqual(
            t243["IMPORT_POLICY"],
            "DONOR_MODULE_NOT_IMPORTED; FROZEN_ROUTE_B_RECOMPUTED",
        )

        pr378 = self.result["PR378_AUTHORITY"]
        self.assertEqual(pr378["CROSS_LINEAGE_VERDICT"], "PARTIAL")
        self.assertEqual(pr378["ORIGINAL_CI"], "FAIL")
        self.assertEqual(pr378["EVALUATOR_CLOSURE"]["LOAD_BEARING_SOURCE_COUNT"], 22)
        self.assertEqual(pr378["EVALUATOR_CLOSURE"]["ALL_SOURCE_PINS_MATCH"], "YES")
        self.assertEqual(
            self.result["CAVEATS"]["PR378"],
            "CROSS_LINEAGE_PARTIAL",
        )
        self.assertEqual(self.result["CAVEATS"]["PR378_CI"], "FAIL")

    def test_new_profile_cap_events_match_the_pinned_proofs(self) -> None:
        actual = {
            (event["PROFILE_ID"], event["CAP_AFTER"], event["BOUND_AFTER"])
            for event in self.result["EVENT_HISTORY"][-5:]
        }
        expected = {
            ("66655555555511100000", 257, 313_332_416),
            ("66665555554431000000", 243, 313_206_948),
            ("65555555555532000000", 230, 313_072_532),
            ("66555555554442000000", 227, 313_045_840),
            ("66555555555333000000", 228, 313_054_608),
        }
        self.assertEqual(actual, expected)
        self.assertEqual(len(self.result["DONOR_IDENTITIES"]), 5)
        self.assertEqual(
            self.result["AUTHORITY_GATES"]["ALL_NEW_SOURCE_LOCATORS"],
            "REAL_AND_RESOLVABLE",
        )
        self.assertEqual(self.result["ROW_SOURCE_METADATA_VERIFIED"], "YES")

    def test_negative_validations_reject_tampered_authority_and_rows(self) -> None:
        self.assertEqual(
            set(self.result["NEGATIVE_VALIDATIONS"].values()),
            {"PASS"},
        )
        self.assertEqual(
            set(self.result["NEGATIVE_VALIDATIONS"]),
            {
                "WRONG_SOURCE_SHA_REJECTED",
                "WRONG_PROFILE_REJECTED",
                "WRONG_CAP_REJECTED",
                "WRONG_BOUND_REJECTED",
                "MISSING_PROOF_REJECTED",
                "DUPLICATE_EVENT_HANDLED",
                "UNRELATED_ROW_MUTATION_REJECTED",
                "INCORRECT_FAMILY_MAX_REJECTED",
            },
        )
        changed = set(self.result["LEDGER_OVERLAY"]["DISTINCT_CHANGED_PROFILES"])
        self.assertEqual(len(changed), 15)
        self.assertEqual(len(self.frozen), 4_647)
        self.assertEqual(len(self.after), 4_647)
        self.assertEqual(
            authority.four.seven.two.full_digest(self.frozen),
            authority.four.SEVEN_ROW_FULL_DIGEST,
        )
        self.assertEqual(
            authority.four.seven.two.bounds_digest(self.frozen),
            authority.four.SEVEN_ROW_BOUNDS_DIGEST,
        )


if __name__ == "__main__":
    unittest.main()
