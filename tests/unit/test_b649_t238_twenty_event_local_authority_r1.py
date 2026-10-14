from __future__ import annotations

import json
import unittest
from typing import Any, cast

from lottolab.research import b649_t238_twenty_event_local_authority_r1 as authority


class TwentyEventCandidateTests(unittest.TestCase):
    result: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        result_path = authority.ROOT / authority.RESULT_PATH
        cls.result = cast(dict[str, Any], json.loads(result_path.read_text(encoding="utf-8")))

    def test_pinned_authorities_and_proof_locators_match(self) -> None:
        gates = self.result["AUTHORITY_GATES"]
        self.assertEqual(
            gates,
            {
                "FROZEN_HEAD_TREE": "MATCH",
                "BASE_19_HEAD_TREE": "MATCH",
                "BASE_19_RESULT_SHA256": "MATCH",
                "T238_DONOR_HEAD_TREE": "MATCH",
                "T238_RESULT_SHA256": "MATCH",
                "T238_JUDGE_IDENTITY": "MATCH",
                "ALL_PROOF_LOCATORS_RESOLVE": "YES",
            },
        )
        donor = self.result["T238_DONOR_IDENTITY"]
        self.assertEqual(donor["JUDGE_SESSION_ID"], authority.T238_JUDGE_SESSION_ID)
        self.assertEqual(donor["PARENT"], authority.FROZEN_HEAD)
        self.assertEqual(
            donor["CAP_SOURCE_LOCATOR"],
            authority.R30_RESULT_PATH + ":GROUP_ATTEMPTS[3397]",
        )
        self.assertEqual(donor["PROOF_FRAGMENT"], "THEOREM_T238")
        self.assertEqual(len(donor["RESULT_SHA256"]), 64)
        self.assertEqual(len(donor["PROOF_SHA256"]), 64)

    def test_twenty_event_overlay_preserves_other_rows(self) -> None:
        result = self.result
        self.assertEqual((result["ROWS_BEFORE"], result["ROWS_AFTER"]), (4_647, 4_647))
        self.assertEqual(
            (result["OLD_EVENTS"], result["NEW_EVENTS"], result["TOTAL_EVENTS"]),
            (19, 1, 20),
        )
        self.assertEqual(
            (
                result["DISTINCT_CHANGED_PROFILES_FROM_FROZEN"],
                result["UNCHANGED_ROWS_FROM_FROZEN"],
                result["CHANGED_ROWS_FROM_19_EVENT"],
                result["UNCHANGED_ROWS_FROM_19_EVENT"],
            ),
            (19, 4_628, 1, 4_646),
        )
        self.assertEqual(result["SOURCE_METADATA_REPLAY"], "MATCH")
        self.assertEqual(result["T238_NEW_CAP"], 238)
        self.assertEqual(result["T238_NEW_BOUND"], 313_150_736)
        self.assertEqual(result["OWNER_BOUND_DELTA"], -241_780)
        self.assertEqual(len(result["FULL_DIGEST"]), 64)
        self.assertEqual(len(result["BOUNDS_DIGEST"]), 64)

    def test_t238_event_uses_the_pinned_donor_source(self) -> None:
        event = self.result["EVENT_HISTORY"][-1]
        donor = self.result["T238_DONOR_IDENTITY"]
        self.assertEqual(
            (event["PROFILE_ID"], event["CAP_BEFORE"], event["CAP_AFTER"]),
            (authority.T238_PROFILE_ID, 265, 238),
        )
        self.assertEqual((event["BOUND_BEFORE"], event["BOUND_AFTER"]), (313_392_516, 313_150_736))
        self.assertEqual(event["SOURCE_AFTER"], donor["ROW_SOURCE"])
        self.assertEqual(event["DONOR"]["RESULT_SHA256"], authority.T238_RESULT_SHA256)
        self.assertEqual(event["DONOR"]["CAP_SOURCE_LOCATOR"], donor["CAP_SOURCE_LOCATOR"])

    def test_family_frontier_keeps_the_unresolved_cursor_maximum(self) -> None:
        result = self.result
        self.assertEqual(
            (result["FAMILY_BOUND_BEFORE"], result["FAMILY_BOUND_AFTER"]),
            (313_394_584, 313_394_584),
        )
        self.assertEqual(result["FAMILY_GAIN"], 0)
        self.assertEqual(result["MAX_OWNER"], authority.CURSOR_ID)
        self.assertEqual(result["MAX_OWNER_TYPE"], "UNRESOLVED_CURSOR")
        self.assertEqual(result["NEXT_DISTINCT_BOUND"], 313_392_412)
        self.assertEqual(
            result["NEXT_OWNER_IDS"],
            ["66655555555431000000", "66665555544441000000"],
        )
        self.assertEqual(result["RESOLVED_ROWS_ABOVE_INCUMBENT"], 1_366)
        self.assertEqual(result["CURSOR_COUNT"], 197)
        self.assertEqual(result["CURSOR_BOUND"], 313_394_584)
        self.assertEqual(result["CURSOR_INCLUDED"], "YES")
        self.assertEqual(result["NEW_WINNING_OUTCOMES"], 0)
        self.assertEqual(result["GLOBAL_K20_OPTIMUM"], "UNKNOWN")

    def test_required_negative_validations_reject_bad_inputs(self) -> None:
        self.assertEqual(
            self.result["NEGATIVE_VALIDATIONS"],
            {
                "WRONG_DONOR_SHA_REJECTED": "PASS",
                "WRONG_PROFILE_REJECTED": "PASS",
                "WRONG_CAP_REJECTED": "PASS",
                "WRONG_BOUND_REJECTED": "PASS",
                "WRONG_PROOF_LOCATOR_REJECTED": "PASS",
                "UNRELATED_ROW_MUTATION_REJECTED": "PASS",
                "CURSOR_OMISSION_REJECTED": "PASS",
                "INCORRECT_FAMILY_MAX_REJECTED": "PASS",
            },
        )


if __name__ == "__main__":
    unittest.main()
