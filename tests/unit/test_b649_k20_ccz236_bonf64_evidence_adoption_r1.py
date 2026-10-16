"""Focused acceptance tests for the pinned CCZ236 / Bonf64 evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from lottolab.research.b649_k20_ccz236_bonf64_evidence_adoption_r1 import (
    BONF64_SOURCE_PATH,
    BONF64_SOURCE_SHA256,
    BONF64_SUPPORT_SOURCE_PATH,
    BONF64_SUPPORT_SOURCE_SHA256,
    FROZEN_FAMILY_RESULT_PATH,
    FROZEN_HEAD,
    FROZEN_RESULT_SHA256,
    FROZEN_TREE,
    b3_bound,
    bonf64_bound,
    expected_certificate,
    integer_ccz_cases,
    phi93,
    t_range_summary,
    t_range_values,
    validate_certificate,
)


RESULT_PATH = Path(
    "docs/research/matrix-native-results/"
    "b649-k20-ccz236-bonf64-evidence-adoption-r1-result.json"
)


class Bonf64EvidenceAdoptionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[2]
        with (cls.repo_root / RESULT_PATH).open("r", encoding="utf-8") as stream:
            cls.result = json.load(stream)

    def assert_rejected(self, name, mutate):
        candidate = copy.deepcopy(self.result)
        mutate(candidate)
        with self.subTest(case=name):
            self.assertTrue(validate_certificate(candidate), name)

    def test_correct_result_passes_public_validator(self):
        self.assertEqual(validate_certificate(self.result), ())

    def test_pinned_endpoint_values_and_margin(self):
        self.assertEqual(b3_bound(236), 313212648)
        self.assertEqual(phi93(3 * 236 - 66), 1899)
        self.assertEqual(bonf64_bound(236), 313091112)
        self.assertEqual(313263888 - bonf64_bound(236), 172776)

    def test_all_seven_integer_capacity_cases(self):
        self.assertEqual(
            integer_ccz_cases(),
            [
                {"M": 0, "A_MAX": 94, "I_CCZ_FLOOR": 56},
                {"M": 1, "A_MAX": 88, "I_CCZ_FLOOR": 56},
                {"M": 2, "A_MAX": 82, "I_CCZ_FLOOR": 56},
                {"M": 3, "A_MAX": 76, "I_CCZ_FLOOR": 56},
                {"M": 4, "A_MAX": 70, "I_CCZ_FLOOR": 56},
                {"M": 5, "A_MAX": 64, "I_CCZ_FLOOR": 56},
                {"M": 6, "A_MAX": 58, "I_CCZ_FLOOR": 56},
            ],
        )

    def test_all_215_legal_t_values_are_strictly_increasing(self):
        values = t_range_values()
        self.assertEqual(len(values), 215)
        self.assertEqual([total for total, _ in values], list(range(22, 237)))
        bounds = [bound for _, bound in values]
        steps = [right - left for left, right in zip(bounds, bounds[1:])]
        self.assertTrue(all(step > 0 for step in steps))
        self.assertEqual(min(steps), 10720)
        self.assertEqual(values[0], (22, 310672040))
        self.assertEqual(values[-1], (236, 313091112))
        self.assertEqual(
            t_range_summary(),
            {
                "FIRST_T": 22,
                "LAST_T": 236,
                "COUNT": 215,
                "STRICTLY_INCREASING": True,
                "MINIMUM_STEP": 10720,
                "FIRST_UPPER_BOUND": 310672040,
                "ENDPOINT_UPPER_BOUND": 313091112,
                "MAXIMUM_AT_ENDPOINT": True,
            },
        )

    def test_frozen_authority_bytes_and_base_tree_match(self):
        pinned_files = (
            (BONF64_SOURCE_PATH, BONF64_SOURCE_SHA256),
            (BONF64_SUPPORT_SOURCE_PATH, BONF64_SUPPORT_SOURCE_SHA256),
            (FROZEN_FAMILY_RESULT_PATH, FROZEN_RESULT_SHA256),
        )
        for relative_path, expected_sha256 in pinned_files:
            content = (self.repo_root / relative_path).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), expected_sha256)

        tree = subprocess.run(
            ["git", "rev-parse", FROZEN_HEAD + "^{tree}"],
            cwd=str(self.repo_root),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        self.assertEqual(tree, FROZEN_TREE)

    def test_correct_source_roles_are_independently_pinned(self):
        expected_roles = {
            "BONF64_SOURCE_PATH": (
                "src/lottolab/research/"
                "b649_k20_min_s2_higher_order_closure_r2.py"
            ),
            "BONF64_SOURCE_SHA256": (
                "6897c974fe9679f2ec567602522bb4c38c996275368b714c6a7fadedd66d6e45"
            ),
            "BONF64_SUPPORT_SOURCE_PATH": (
                "src/lottolab/research/"
                "b649_k20_min_s2_realizable_core_class_bound_r4.py"
            ),
            "BONF64_SUPPORT_SOURCE_SHA256": (
                "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec"
            ),
        }
        for source in (expected_certificate(), self.result):
            with self.subTest(source="validator" if source is not self.result else "result"):
                self.assertEqual(
                    {key: source[key] for key in expected_roles},
                    expected_roles,
                )
        self.assertEqual(validate_certificate(self.result), ())

    def test_source_role_tampering_is_rejected(self):
        support_path = (
            "src/lottolab/research/"
            "b649_k20_min_s2_realizable_core_class_bound_r4.py"
        )
        support_sha256 = (
            "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec"
        )
        bonf64_path = (
            "src/lottolab/research/"
            "b649_k20_min_s2_higher_order_closure_r2.py"
        )
        bonf64_sha256 = (
            "6897c974fe9679f2ec567602522bb4c38c996275368b714c6a7fadedd66d6e45"
        )

        def swap_both_roles(item):
            for left, right in (
                ("BONF64_SOURCE_PATH", "BONF64_SUPPORT_SOURCE_PATH"),
                ("BONF64_SOURCE_SHA256", "BONF64_SUPPORT_SOURCE_SHA256"),
            ):
                item[left], item[right] = item[right], item[left]

        def coupled_bonf64_tampering(item):
            item["BONF64_SOURCE_PATH"] = support_path
            item["BONF64_SOURCE_SHA256"] = support_sha256

        cases = (
            ("REVERSED_SOURCE_ROLE", swap_both_roles),
            ("BONF64_PATH_ONLY_TAMPER", lambda item: item.update(BONF64_SOURCE_PATH=support_path)),
            ("BONF64_SHA_ONLY_TAMPER", lambda item: item.update(BONF64_SOURCE_SHA256=support_sha256)),
            (
                "SUPPORT_PATH_ONLY_TAMPER",
                lambda item: item.update(BONF64_SUPPORT_SOURCE_PATH=bonf64_path),
            ),
            (
                "SUPPORT_SHA_ONLY_TAMPER",
                lambda item: item.update(BONF64_SUPPORT_SOURCE_SHA256=bonf64_sha256),
            ),
            ("BOTH_ROLES_SWAPPED", swap_both_roles),
            ("COUPLED_SOURCE_TAMPERING", coupled_bonf64_tampering),
        )
        for name, mutate in cases:
            self.assert_rejected(name, mutate)

    def test_required_fail_closed_mutations(self):
        cases = (
            ("WRONG_PROFILE", lambda item: item.update(PROFILE_ID="55555555555551100000")),
            ("WRONG_FROZEN_HEAD", lambda item: item.update(FROZEN_HEAD="0" * 40)),
            ("WRONG_FROZEN_TREE", lambda item: item.update(FROZEN_TREE="0" * 40)),
            (
                "WRONG_FROZEN_RESULT_SHA",
                lambda item: item.update(FROZEN_RESULT_SHA256="0" * 64),
            ),
            (
                "WRONG_BONF64_SOURCE_SHA",
                lambda item: item.update(BONF64_SOURCE_SHA256="0" * 64),
            ),
            ("WRONG_SOURCE_METHOD", lambda item: item.update(SOURCE_METHOD="FAMILY_ROW")),
            ("WRONG_PROOF_SCOPE", lambda item: item.update(PROOF_SCOPE="GLOBAL")),
            ("WRONG_I_FLOOR", lambda item: item.update(I_FLOOR=55)),
            ("WRONG_T_CAP", lambda item: item.update(T_CAP=237)),
            ("WRONG_B3", lambda item: item.update(B3_AT_236=313212647)),
            ("WRONG_P_MIN", lambda item: item.update(P_MIN_AT_236=1898)),
            ("WRONG_U64", lambda item: item.update(BONF64_UPPER_BOUND=313091113)),
            (
                "WRONG_INCUMBENT_MARGIN",
                lambda item: item.update(MARGIN_BELOW_INCUMBENT=172775),
            ),
            ("WRONG_HISTORICAL_R30_CAP", lambda item: item.update(HISTORICAL_R30_CAP=264)),
        )
        for name, mutate in cases:
            self.assert_rejected(name, mutate)

    def test_resource_fail_cannot_be_promoted_to_pass(self):
        self.assert_rejected(
            "RESOURCE_FAIL_TO_PASS_NEW",
            lambda item: item.update(NEW_RESOURCE_VERDICT="PASS"),
        )
        self.assert_rejected(
            "RESOURCE_FAIL_TO_PASS_HISTORICAL",
            lambda item: item.update(HISTORICAL_RESOURCE="PASS"),
        )

    def test_false_family_closure_and_maximum_claims_are_rejected(self):
        self.assert_rejected(
            "FALSE_FAMILY_CLOSURE",
            lambda item: item.update(FULL_FAMILY_CLOSURE="CLAIMED"),
        )
        self.assert_rejected(
            "FALSE_FAMILY_MAXIMUM_REDUCTION",
            lambda item: item.update(FAMILY_MAXIMUM_REDUCED=True),
        )

    def test_missing_wrongly_typed_and_synchronized_source_fields_rejected(self):
        self.assert_rejected(
            "MISSING_REQUIRED_FIELD",
            lambda item: item.pop("BONF64_SOURCE_SHA256"),
        )
        self.assert_rejected(
            "WRONG_REQUIRED_TYPE",
            lambda item: item.update(I_FLOOR="56"),
        )

        def synchronize_source_digests(item):
            item["BONF64_SOURCE_SHA256"] = "a" * 64
            item["BONF64_SUPPORT_SOURCE_SHA256"] = "a" * 64

        self.assert_rejected("SYNCHRONIZED_SOURCE_FIELDS_CHANGED", synchronize_source_digests)


if __name__ == "__main__":
    unittest.main()
