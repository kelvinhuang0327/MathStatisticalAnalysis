from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from copy import deepcopy
from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from lottolab.research import b649_eight_row_family_authority_r1 as authority  # noqa: E402


class EightRowFamilyAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.frozen_blob, cls.donor_blob, cls.identity = authority.load_live_sources()
        cls.before = authority.load_seven_row_ledger(json.loads(cls.frozen_blob))
        with patch.object(authority, "load_seven_row_ledger", return_value=cls.before) as loader:
            cls.result = authority.build_authority(
                cls.frozen_blob, cls.donor_blob, cls.identity
            )
        loader.assert_called_once()

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
        self.assertTrue(all(a["BOUND"] < b["BOUND"] for a, b in pairwise(terms)))
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

    def test_compute_result_calls_the_complete_ledger_loader(self) -> None:
        with patch.object(authority, "load_seven_row_ledger", return_value=self.before) as loader:
            result = authority.compute_result()
        loader.assert_called_once()
        self.assertEqual(result["LEDGER_OVERLAY"]["ROWS_BEFORE"], 4647)
        self.assertEqual(result["LEDGER_OVERLAY"]["ROWS_AFTER"], 4647)
        self.assertEqual(result["LEDGER_OVERLAY"]["CHANGED_ROW_COUNT"], 1)
        self.assertEqual(result["LEDGER_OVERLAY"]["UNCHANGED_ROW_COMPARISONS"], 4646)

    def test_complete_overlay_compares_all_rows_and_recomputes_digests(self) -> None:
        before = self.before
        source = f"{authority.RESULT_PATH}:EIGHTH_PROFILE_CERTIFICATE"
        after, summary = authority.apply_eighth_overlay(before, 313397476, source)

        self.assertEqual(len(before), 4647)
        self.assertEqual(len(after), 4647)
        self.assertEqual(set(before), set(after))
        self.assertEqual(summary["UNCHANGED_ROW_COMPARISONS"], 4646)
        self.assertEqual(summary["CHANGED_PROFILE_IDS"], [authority.PROFILE_ID])
        self.assertEqual(summary["FULL_DIGEST_BEFORE"], authority.SEVEN_ROW_FULL_DIGEST)
        self.assertEqual(summary["BOUNDS_DIGEST_BEFORE"], authority.SEVEN_ROW_BOUNDS_DIGEST)
        self.assertEqual(summary["FULL_DIGEST_AFTER"], authority.seven.two.full_digest(after))
        self.assertEqual(summary["BOUNDS_DIGEST_AFTER"], authority.seven.two.bounds_digest(after))
        for profile_id in before:
            if profile_id == authority.PROFILE_ID:
                self.assertEqual(after[profile_id], replace(before[profile_id], bound=313397476,
                                                             source=source))
            else:
                self.assertEqual(after[profile_id], before[profile_id])
        self.assertEqual(authority.seven.two.full_digest(before), authority.SEVEN_ROW_FULL_DIGEST)

    def test_ledger_loader_rejects_missing_extra_and_duplicate_rows(self) -> None:
        before = self.before
        records = list(before.items())

        with self.assertRaisesRegex(ValueError, "ledger row count mismatch"):
            authority.index_ledger_rows(records[:-1])
        with self.assertRaisesRegex(ValueError, "ledger row count mismatch"):
            authority.index_ledger_rows([*records, ("0" * 20, records[0][1])])
        duplicated = list(records)
        duplicated[0] = (duplicated[1][0], duplicated[0][1])
        with self.assertRaisesRegex(ValueError, "duplicate ledger profile ID"):
            authority.index_ledger_rows(duplicated)

    def test_overlay_rejects_other_profile_changes_and_bad_frozen_digest(self) -> None:
        before = self.before
        source = f"{authority.RESULT_PATH}:EIGHTH_PROFILE_CERTIFICATE"
        after, _summary = authority.apply_eighth_overlay(before, 313397476, source)
        other = next(profile_id for profile_id in before if profile_id != authority.PROFILE_ID)

        changed_other = dict(after)
        changed_other[other] = replace(changed_other[other], bound=changed_other[other].bound + 1)
        with self.assertRaisesRegex(ValueError, "outside the designated owner"):
            authority.verify_ledger_overlay(before, changed_other, 313397476, source)

        changed_before = dict(before)
        changed_before[other] = replace(
            changed_before[other], bound=changed_before[other].bound + 1
        )
        with self.assertRaisesRegex(ValueError, "frozen seven-row before digest mismatch"):
            authority.apply_eighth_overlay(changed_before, 313397476, source)

    def test_overlay_is_copy_only_and_second_application_is_rejected(self) -> None:
        before = self.before
        original = dict(before)
        source = f"{authority.RESULT_PATH}:EIGHTH_PROFILE_CERTIFICATE"
        after, _summary = authority.apply_eighth_overlay(before, 313397476, source)

        self.assertEqual(before, original)
        self.assertEqual(len(after), 4647)
        with self.assertRaisesRegex(ValueError, "frozen seven-row before digest mismatch"):
            authority.apply_eighth_overlay(after, 313397476, source)
        profile_ids = self.result["CERTIFICATE_PROFILE_IDS_AFTER"]
        self.assertEqual(len(profile_ids), 8)
        self.assertEqual(len(set(profile_ids)), 8)

    def test_donor_certificate_pointer_fails_closed(self) -> None:
        donor = json.loads(self.donor_blob)
        mutations = (
            ("PROFILE_ID", "0" * 20),
            ("APPLICABILITY", "ONE_REALIZATION"),
            ("RESULT_FIELD", "OWNER_CERTIFICATE"),
            ("RESULT_SHA256", "0" * 64),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                candidate = deepcopy(self.result)
                if field in {"RESULT_FIELD", "RESULT_SHA256"}:
                    candidate["EIGHTH_PROFILE_CERTIFICATE"]["PROOF_REFERENCE"][field] = value
                else:
                    candidate["EIGHTH_PROFILE_CERTIFICATE"][field] = value
                with self.assertRaisesRegex(
                    ValueError, "proof pointer, identity, or applicability"
                ):
                    authority.validate_certificate_pointer(candidate, donor)

    def test_missing_or_invalid_donor_proof_identity_is_rejected(self) -> None:
        donor = json.loads(self.donor_blob)
        for field in ("PROOF", "TASK_ID", "PROFILE_ID", "NEW_INEQUALITY"):
            with self.subTest(field=field):
                invalid = dict(donor)
                invalid.pop(field)
                with self.assertRaisesRegex(ValueError, "donor proof"):
                    authority.validate_donor_proof(invalid)

    def test_wrong_emitted_bound_cap_and_family_maximum_are_rejected(self) -> None:
        donor = json.loads(self.donor_blob)
        frozen = json.loads(self.frozen_blob)
        before = self.before
        mutations = (
            ("NEW_OWNER_BOUND", 313397475, "owner bound"),
            ("T_CAP", 263, "owner bound"),
            ("FAMILY_BOUND_AFTER", 313397477, "family maximum"),
        )
        for field, value, message in mutations:
            with self.subTest(field=field):
                candidate = deepcopy(self.result)
                candidate[field] = value
                with self.assertRaisesRegex(ValueError, message):
                    authority.validate_authority_result(candidate, donor, frozen, before)

    def test_frozen_seven_row_and_certificate_f_bytes_are_unchanged(self) -> None:
        source_path = Path(authority.seven.__file__).resolve().relative_to(authority.ROOT)
        paths = (
            authority.FROZEN_INPUT,
            source_path.as_posix(),
            authority.seven.SIX_RESULT_PATH,
        )
        for relative in paths:
            with self.subTest(path=relative):
                committed = subprocess.run(
                    ["git", "-C", str(authority.ROOT), "show",
                     f"{authority.FROZEN_HEAD}:{relative}"],
                    check=True,
                    capture_output=True,
                ).stdout
                self.assertEqual((authority.ROOT / relative).read_bytes(), committed)
        six_result = json.loads((authority.ROOT / authority.seven.SIX_RESULT_PATH).read_bytes())
        self.assertIn("CERTIFICATE_F", six_result)

    def test_original_refuted_integration_blob_remains_in_parent_history(self) -> None:
        original = subprocess.run(
            ["git", "-C", str(authority.ROOT), "show",
             f"{authority.PRIOR_INTEGRATION_HEAD}:{authority.RESULT_PATH}"],
            check=True,
            capture_output=True,
        ).stdout
        self.assertEqual(
            hashlib.sha256(original).hexdigest(), authority.PRIOR_INTEGRATION_RESULT_SHA256
        )
        self.assertEqual(
            authority.PRIOR_INTEGRATION_TREE,
            authority.run_git(authority.ROOT, "rev-parse",
                              f"{authority.PRIOR_INTEGRATION_HEAD}^{{tree}}"),
        )

    def test_all_inherited_caveats_and_self_check_status_are_preserved(self) -> None:
        inherited = json.loads(self.frozen_blob)["PRESERVED_SIX_ROW_STATUS"]
        self.assertEqual(self.result["PRESERVED_SIX_ROW_STATUS"], inherited)
        self.assertEqual(self.result["INHERITED_JUDGE_STATUS"], "SELF_CHECK_ONLY")
        self.assertEqual(self.result["NEW_CERTIFICATE_JUDGE_STATUS"], "SELF_CHECK_ONLY")
        self.assertEqual(
            self.result["EIGHTH_PROFILE_CERTIFICATE"]["SOURCE_JUDGE_STATUS"],
            "SELF_CHECK_ONLY",
        )


if __name__ == "__main__":
    unittest.main()
