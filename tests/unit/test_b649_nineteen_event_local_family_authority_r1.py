from __future__ import annotations

import json
import unittest
from dataclasses import replace
from typing import Any, cast

from lottolab.research import b649_nineteen_event_local_family_authority_r1 as authority


class NineteenEventCandidateTests(unittest.TestCase):
    result: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        result_path = authority.ROOT / authority.RESULT_PATH
        cls.result = cast(dict[str, Any], json.loads(result_path.read_text(encoding="utf-8")))

    def test_ledger_counts_digests_and_family_frontier(self) -> None:
        result = self.result
        overlay = result["LEDGER_OVERLAY"]

        self.assertEqual(result["UPDATE_EVENTS"], 19)
        self.assertEqual(result["PREVIOUS_EVENTS"], 16)
        self.assertEqual(result["NEW_EVENTS"], 3)
        self.assertEqual(result["DISTINCT_CHANGED_PROFILES"], 18)
        self.assertEqual(result["UNCHANGED_ROWS_FROM_FROZEN"], 4_629)
        self.assertEqual(result["UNCHANGED_ROWS_FROM_SIXTEEN_EVENT"], 4_644)
        self.assertEqual(overlay["ROWS_BEFORE"], 4_647)
        self.assertEqual(overlay["ROWS_AFTER"], 4_647)
        self.assertEqual(overlay["SOURCE_METADATA_BINDINGS"], "VERIFIED")
        self.assertEqual(overlay["UNRELATED_ROW_MUTATION"], "NONE")
        self.assertEqual(overlay["FULL_DIGEST_AFTER"], result["NEW_FULL_DIGEST"])
        self.assertEqual(overlay["BOUNDS_DIGEST_AFTER"], result["NEW_BOUNDS_DIGEST"])

        family = result["FAMILY_AFTER"]
        self.assertEqual(family["FAMILY_BOUND"], 313_394_584)
        self.assertEqual(family["TIED_OWNERS"], [authority.CURSOR_ID])
        self.assertEqual(family["NEXT_COMPETING_BOUND"], 313_392_516)
        self.assertEqual(family["NEXT_COMPETING_OWNERS"], ["65555555555541000000"])
        self.assertEqual(family["CURSOR"], {"ID": authority.CURSOR_ID, "BOUND": 313_394_584})
        self.assertEqual(result["MAX_OWNER_TYPE"], "UNRESOLVED_CURSOR")
        self.assertEqual(result["NEXT_DISTINCT_BOUND"], 313_392_516)
        self.assertEqual(result["NEXT_RESOLVED_OWNER"], ["65555555555541000000"])
        self.assertEqual(result["FAMILY_DELTA_FROM_SIXTEEN_EVENT"], 476)
        self.assertEqual(result["FAMILY_DELTA_FROM_FROZEN"], 3_948)
        self.assertEqual(result["RESOLVED_ROWS_ABOVE_INCUMBENT"], 1_367)

    def test_three_event_transitions_match_the_donor_records(self) -> None:
        expected = [
            ("T228_A187", "66655555555332000000", 313_395_060, 313_062_208, 265, 228),
            ("T248", "66655555555421100000", 313_395_060, 313_242_512, 265, 248),
            ("T255_NEW_OWNER", "66555555555431100000", 313_394_776, 313_296_388, 266, 255),
        ]
        events = self.result["EVENT_HISTORY"][-3:]
        self.assertEqual(len(events), 3)
        for event, (event_id, profile, before, after, cap_before, cap_after) in zip(
            events, expected, strict=True
        ):
            self.assertEqual(event["EVENT_ID"], event_id)
            self.assertEqual(event["PROFILE_ID"], profile)
            self.assertEqual(event["BOUND_BEFORE"], before)
            self.assertEqual(event["BOUND_AFTER"], after)
            self.assertEqual(event["CAP_BEFORE"], cap_before)
            self.assertEqual(event["CAP_AFTER"], cap_after)
            self.assertEqual(event["S4_BASE_BEFORE"], 112)
            self.assertEqual(event["S4_BASE_AFTER"], 112)
            self.assertTrue(event["SOURCE_AFTER"].startswith("git:"))

        self.assertEqual(
            [item["FAMILY_BOUND_AFTER"] for item in self.result["EVENT_FAMILY_TRANSITIONS"]],
            [313_395_060, 313_394_776, 313_394_584],
        )

    def test_frozen_and_donor_authority_caveats_are_preserved(self) -> None:
        result = self.result
        gates = result["AUTHORITY_GATES"]
        self.assertEqual(gates["FROZEN_HEAD_TREE"], "MATCH")
        self.assertEqual(gates["SIXTEEN_EVENT_HEAD_TREE"], "MATCH")
        self.assertEqual(gates["SIXTEEN_EVENT_RESULT_SHA256"], "MATCH")
        self.assertEqual(gates["T228_DONOR_IDENTITY"], "MATCH")
        self.assertEqual(gates["T248_SEALED_DONOR_IDENTITY"], "MATCH")
        self.assertEqual(gates["T255_DONOR_IDENTITY"], "MATCH")
        self.assertEqual(gates["T248_FROZEN_ROW_EXISTS"], "YES")
        self.assertEqual(gates["T248_FROZEN_ROW_BOUND"], 313_395_060)
        self.assertEqual(gates["T248_FROZEN_CAP_AND_SOURCE"], "VERIFIED")
        self.assertEqual(gates["ALL_NEW_PROOF_LOCATORS_RESOLVE"], "YES")

        t248 = result["FROZEN_TARGET_ROWS"]["66655555555421100000"]
        self.assertEqual(t248["bound"], 313_395_060)
        self.assertEqual(t248["cap"], 265)
        self.assertEqual(t248["s4_base"], 112)
        self.assertTrue(t248["source"])
        self.assertEqual(
            result["NEW_DONOR_REVIEW_CAVEATS"]["T248_R14_SHARED_REFERENCES"],
            "NOT_VERIFIED",
        )
        self.assertEqual(
            result["NEW_DONOR_REVIEW_CAVEATS"]["T255_NEW_OWNER_SCIENTIFIC_REVIEW"],
            "SELF_CHECK_ONLY",
        )
        self.assertEqual(
            result["HISTORICAL_AUTHORITY_CAVEATS"]["NB_CERTIFICATES_1444"]["STATUS"],
            "UNRESOLVED_LOCATOR_PRESERVED",
        )
        self.assertEqual(
            result["HISTORICAL_AUTHORITY_CAVEATS"]["MUTATION_RAW_LOGS"]["STATUS"],
            "NOT_OBTAINED",
        )
        self.assertEqual(result["PR378_CI"], "FAIL")
        self.assertEqual(result["FORMAL_AUTHORITY_ACCEPTANCE"], "NOT_CLAIMED")
        self.assertEqual(result["NEW_WINNING_OUTCOMES"], 0)
        self.assertEqual(result["GLOBAL_K20_OPTIMUM"], "UNKNOWN")

    def test_all_required_negative_validations_rejected(self) -> None:
        validations = self.result["NEGATIVE_VALIDATIONS"]
        self.assertEqual(
            set(validations),
            {
                "WRONG_PROFILE_REJECTED",
                "WRONG_SOURCE_SHA_REJECTED",
                "WRONG_CAP_REJECTED",
                "WRONG_BOUND_REJECTED",
                "WRONG_PROOF_LOCATOR_REJECTED",
                "UNRELATED_ROW_MUTATION_REJECTED",
                "CURSOR_OMISSION_REJECTED",
            },
        )
        self.assertEqual(set(validations.values()), {"PASS"})


def t255_claim_fixture() -> dict[str, Any]:
    spec = authority.DONORS[2]
    return {
        "TASK_ID": spec.task_id,
        "PROFILE_ID": spec.profile_id,
        "SOURCE_OLD_BOUND": spec.before_bound,
        "SOURCE_T_CAP": spec.before_cap,
        "SOURCE_S4_BASE": spec.s4_base,
        "PROVED_T_CAP": spec.after_cap,
        "NEW_ADMISSIBLE_BOUND": spec.after_bound,
    }


class DonorValidationTests(unittest.TestCase):
    def test_wrong_profile_is_rejected(self) -> None:
        spec = authority.DONORS[2]
        with self.assertRaises(ValueError):
            authority.validate_donor_claim(t255_claim_fixture(), replace(spec, profile_id="0" * 20))

    def test_wrong_cap_is_rejected(self) -> None:
        spec = authority.DONORS[2]
        with self.assertRaises(ValueError):
            authority.validate_donor_claim(
                t255_claim_fixture(), replace(spec, after_cap=spec.after_cap - 1)
            )

    def test_wrong_bound_is_rejected(self) -> None:
        spec = authority.DONORS[2]
        with self.assertRaises(ValueError):
            authority.validate_donor_claim(
                t255_claim_fixture(), replace(spec, after_bound=spec.after_bound + 1)
            )

    def test_wrong_proof_locator_is_rejected(self) -> None:
        certificate = {"PROFILE_ID": "profile", "CAP": 255, "PROOF_SCOPE": "FULL_PROFILE"}
        spec = authority.DONORS[2]
        proof_hash = authority.canonical_json_sha256(certificate)
        test_spec = replace(spec, proof_sha256=proof_hash)
        locator = authority.proof_source(test_spec)
        with self.assertRaises(ValueError):
            authority.verify_proof_locator(
                {"ANALYTIC_CERTIFICATE": certificate}, test_spec, locator + "/wrong"
            )

    def test_wrong_source_hash_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            authority.require_hash(b"pinned donor source", "0" * 64, "donor source")


if __name__ == "__main__":
    unittest.main()
