from __future__ import annotations

from lottolab.application.biglotto_l2_pairwise_prospective_shadow_runtime import (
    BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_IDS,
    BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
    build_biglotto_l2_pairwise_prospective_candidate_runtimes,
)


def test_nine_candidate_runtime_registry_has_exact_frozen_identity_and_order() -> None:
    runtimes = build_biglotto_l2_pairwise_prospective_candidate_runtimes(
        target_draw="115000082"
    )

    assert tuple(runtime.candidate_id for runtime in runtimes) == (
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "C6",
        "C8",
        "C9",
        "C10",
    )
    assert tuple(runtime.candidate_id for runtime in runtimes) == (
        BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_IDS
    )
    assert tuple(runtime.method_id for runtime in runtimes) == (
        "BMSGV1_L2_PAIRWISE_378b7fc29066cbc8",
        "BMSGV1_L2_PAIRWISE_8abbaed2ea78e47f",
        "BMSGV1_L2_PAIRWISE_a9bf271fe5419f15",
        "BMSGV1_L2_PAIRWISE_950aa3b890915ed7",
        "BMSGV1_L2_PAIRWISE_96368234e833a391",
        "BMSGV1_L2_PAIRWISE_2e8fb1bb6d0648fa",
        "BMSGV1_L2_PAIRWISE_NF01_LAG_BLOCK_HSIC_V1",
        "BMSGV1_L2_PAIRWISE_NF02_TRANSFER_ENTROPY_V1",
        "BMSGV1_L2_PAIRWISE_NF05_CHECKERBOARD_RECURRENCE_COPULA_V1",
    )
    assert tuple(runtime.semantic_signature for runtime in runtimes) == (
        "259e140c70571b37e15f326688ddf5f4a0e18ba0d1982f8098565232ee375508",
        "a299e56636b9a90a5a2e0caa8fa5c89a251b1523a9c11e87630eda390cb70d58",
        "77a875147dc4f0520dcfb4e1929df20aa3bfde638cd01d9860764ed53fb4cc1b",
        "8f2a36e3f33629455f0a08d13737eac21726ac04d999daa3cf0c93a39034c683",
        "96368234e833a391f98ebe9d4deaf5adea2b12335a341e80be87cf9a7c4a3ba2",
        "2e8fb1bb6d0648fa1e226bc78d35b3677833855e3e8d5e2a1ea51acd2504ce4f",
        "1ce87b2abf6fb55c812d4d09476ba050bab8e8165d08da9b8bf46e19a5a8af6f",
        "339a4a3e3e3df04db4b6a02461ecd433089ad54b3edd56628d5ded568aea4234",
        "949ab011357554942d530666465765446a782526decaee900a00254f801ec96f",
    )
    assert all(
        runtime.strategy_version == BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION
        for runtime in runtimes
    )


def test_runtime_registry_excludes_c7_and_c11() -> None:
    candidate_ids = set(BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_IDS)

    assert "C7" not in candidate_ids
    assert "C11" not in candidate_ids
