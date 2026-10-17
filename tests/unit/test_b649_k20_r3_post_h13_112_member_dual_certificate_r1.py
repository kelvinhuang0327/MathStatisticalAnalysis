"""Independent verification for 112 members / 123 vectors dual-certificate adoption."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_post_h13_112_member_dual_certificate_r1 as cert


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden predecessor readoption/rebuild, region census, or heavy solver")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as patch:
        for module, names in (
            (cert.paired, ("build_result", "core_proof", "pair_proof", "update_region")),
            (cert.hunter.r7, ("joint_residual_census", "_joint_residual_states")),
            (cert.hunter.r14, ("owner_region", "s4_child", "run_chase")),
            (cert.hunter.r6, ("iter_type_count_vectors", "candidate_type_count_vectors")),
            (cert.hunter.r8, ("support_model_status", "solver_runtime_preflight")),
        ):
            for name in names:
                if hasattr(module, name):
                    patch.setattr(module, name, forbidden)
        return cert.build_result()


def test_fixed_authority_full_closure_and_predecessor_bytes(result: dict[str, Any]) -> None:
    a = cert.verify_source_authority()
    assert a == result["SOURCE_AUTHORITY"]
    assert (a["HEAD"], a["TREE"], a["RESULT_SHA256"]) == (
        cert.BASE_HEAD,
        cert.BASE_TREE,
        cert.BASE_RESULT_SHA256,
    )
    for path, expected in {**a["upstream_sha256"], **a["implementation_sha256"]}.items():
        assert sha256((cert.REPO_ROOT / path).read_bytes()).hexdigest() == expected
    assert cert.BASE_RESULT in a["upstream_sha256"]


def test_predecessor_preservation(result: dict[str, Any]) -> None:
    p = result["PREDECESSOR_PRESERVATION"]
    assert p["base_result_sha256"] == cert.BASE_RESULT_SHA256
    assert p["readoption_count"] == 0
    assert p["rebuild_count"] == 0
    assert len(p["carried_150_certificates_sha256"]) == 64


def test_baseline_materialization_74_members_84_vectors(result: dict[str, Any]) -> None:
    assert result["BASELINE_MEMBERS"] == 74
    assert result["BASELINE_VECTORS"] == 84
    assert result["BASELINE_TERMS_DIGEST"] == cert.EXPECTED_BASELINE_DIGEST

    bdata = cert.baseline_data()
    assert bdata["total_baseline_members"] == 74
    assert bdata["total_baseline_vectors"] == 84
    assert bdata["expected_bounds"] == {
        cert.STATE_D: 354980829,
        cert.STATE_A: 355015626,
        cert.STATE_E: 354948692,
        cert.STATE_B: 354985708,
        cert.STATE_C: 354981480,
    }
    assert cert.family_digest(bdata["termsbase"]) == cert.EXPECTED_BASELINE_DIGEST


def test_novel_target_cohorts_38_members_39_vectors(result: dict[str, Any]) -> None:
    assert result["NOVEL_TARGET_MEMBERS"] == 38
    assert result["NOVEL_TARGET_VECTORS"] == 39
    assert result["TOTAL_ADOPTED_MEMBERS"] == 112
    assert result["TOTAL_ADOPTED_VECTORS"] == 123

    cohort_groups = cert.cohorts()
    assert len(cohort_groups["A1"]) == 18
    assert len(cohort_groups["A2"]) == 15
    assert len(cohort_groups["B"]) == 6

    # Verify credits
    duals = result["DUAL_CERTIFICATES"]
    assert duals["ROOTH10"]["credit"] == 4625320
    assert duals["H13_THREE_LEAVES"]["credit"] == 5812800

    for v in cohort_groups["A1"]:
        assert cert.chosen_credit(cert.STATE_A, v) == 4625320
        u = cert.uncorrected_bound(v)
        assert u - 4625320 == 354533746
    for v in cohort_groups["A2"]:
        assert cert.chosen_credit(cert.STATE_A, v) == 4625320
        u = cert.uncorrected_bound(v)
        assert u - 4625320 == 354976636
    for v in cohort_groups["B"]:
        assert cert.chosen_credit(cert.STATE_B, v) == 5812800
        u = cert.uncorrected_bound(v)
        if v[5] == 1:
            assert u - 5812800 == 354912908
        else:
            assert u - 5812800 == 354912460


def test_compressed_aliases_and_coverage(result: dict[str, Any]) -> None:
    assert result["COMPRESSED_ALIAS_COVERAGE"] == 1
    aliases = result["COMPRESSED_ALIASES"]
    assert "A2" in aliases
    alias_entry = aliases["A2"][0]
    assert alias_entry["canonical_member_id"] == "[0,12][1,1][4,3][17,2]"
    assert len(alias_entry["represented_vectors"]) == 2


def test_region_preservation_and_untouched_bounds(result: dict[str, Any]) -> None:
    regions = {r["state_id"]: r for r in result["REGIONS"]}
    assert set(regions.keys()) == {cert.STATE_A, cert.STATE_B}

    spec_a = cert.REGION_SPECS[cert.STATE_A]
    reg_a = regions[cert.STATE_A]
    assert reg_a["region_member_count"] == spec_a["total_members"]
    assert reg_a["region_vector_count"] == spec_a["total_vectors"]
    assert reg_a["target_member_count"] == spec_a["target_members"]
    assert reg_a["target_vector_count"] == spec_a["target_vectors"]
    assert reg_a["preserved_member_count"] == spec_a["total_members"] - spec_a["target_members"]
    assert reg_a["preserved_vector_count"] == spec_a["total_vectors"] - spec_a["target_vectors"]
    assert reg_a["preserved_remainder_max"] == spec_a["preserved_remainder_max"]
    assert reg_a["preserved_remainder_sha256"] == spec_a["preserved_sha256"]
    assert reg_a["target_cohort_max"] == spec_a["target_cohort_max"]
    assert reg_a["new_state_bound"] == spec_a["new_state_bound"]

    spec_b = cert.REGION_SPECS[cert.STATE_B]
    reg_b = regions[cert.STATE_B]
    assert reg_b["region_member_count"] == spec_b["total_members"]
    assert reg_b["region_vector_count"] == spec_b["total_vectors"]
    assert reg_b["target_member_count"] == spec_b["target_members"]
    assert reg_b["target_vector_count"] == spec_b["target_vectors"]
    assert reg_b["preserved_member_count"] == spec_b["total_members"] - spec_b["target_members"]
    assert reg_b["preserved_vector_count"] == spec_b["total_vectors"] - spec_b["target_vectors"]
    assert reg_b["preserved_remainder_max"] == spec_b["preserved_remainder_max"]
    assert reg_b["preserved_remainder_sha256"] == spec_b["preserved_sha256"]
    assert reg_b["target_cohort_max"] == spec_b["target_cohort_max"]
    assert reg_b["new_state_bound"] == spec_b["new_state_bound"]


def test_full_56574_family_recomputation_and_owner(result: dict[str, Any]) -> None:
    f = result["FAMILY_RECOMPUTATION"]
    assert f["term_count"] == 56574
    assert f["preserved_terms"] == 56572
    assert f["classified_count"] == 56550
    assert f["classified_max"] == 354800665
    assert f["tail"] == 354039277
    assert f["final_max"] == 354981480
    assert result["FINAL_COMPLETE_R3_UB"] == 354981480
    assert result["FINAL_OWNER"] == cert.STATE_C
    assert result["RUNNER_UP"] == {"stable_id": cert.STATE_B, "bound": 354981375}
    assert result["OWNER_RUNNER_GAP"] == 105
    assert f["new_sha256"] == cert.EXPECTED_FAMILY_DIGEST


def test_witness_soundness_for_all_39_vectors(result: dict[str, Any]) -> None:
    cohort_groups = cert.cohorts()
    for name, vs in cohort_groups.items():
        for v in vs:
            w = cert.witness_analysis(name, v)
            assert w["core_exact_weight"] >= cert.core_proof(w["core_indices"][-1] + 1)["hunter_floor"]
            assert w["applied_credit"] == cert.COHORT_SPECS[name][3]


def test_deterministic_result_replay(result: dict[str, Any]) -> None:
    status = cert.verify_result(result)
    assert status["status"] == "PASS"
    assert status["total_members"] == 112
    assert status["total_vectors"] == 123
    assert status["novel_members"] == 38
    assert status["novel_vectors"] == 39
    assert status["final_family_ub"] == 354981480
    assert status["family_digest"] == cert.EXPECTED_FAMILY_DIGEST
