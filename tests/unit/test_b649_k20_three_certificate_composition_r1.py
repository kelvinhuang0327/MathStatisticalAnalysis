from __future__ import annotations

from dataclasses import replace

import pytest

from lottolab.research import (
    b649_k20_three_certificate_composition_r1 as composition,
)


def test_three_verified_certificates_keep_family_and_bonf64_methods_separate():
    evidence = composition.build_verified_evidence_set()

    assert evidence.query_certified_bound(
        composition.T249_PROFILE, composition.FAMILY_METHOD
    ) == 313121137
    assert evidence.query_certified_bound(
        composition.T251_PROFILE, composition.FAMILY_METHOD
    ) == 313142921
    assert evidence.query_certified_bound(
        composition.CCZ_PROFILE, composition.FAMILY_METHOD
    ) == 313250644
    assert evidence.query_certified_bound(
        composition.CCZ_PROFILE, composition.BONF64_METHOD
    ) == 313091112
    assert evidence.family_maximum == 313263888
    assert evidence.full_family_closure == "NOT_CLAIMED"


def test_unknown_profile_and_unauthorized_method_are_rejected():
    evidence = composition.build_verified_evidence_set()

    with pytest.raises(composition.CompositionValidationError, match="UNKNOWN_PROFILE"):
        evidence.query_certified_bound("55555555555551999999", composition.FAMILY_METHOD)
    with pytest.raises(composition.CompositionValidationError, match="UNKNOWN_METHOD"):
        evidence.query_certified_bound(composition.CCZ_PROFILE, "UNAPPROVED_METHOD")
    with pytest.raises(composition.CompositionValidationError, match="UNKNOWN_PROFILE"):
        evidence.query_certified_bound("55555555555551999999", composition.BONF64_METHOD)


def _mutate_ccz_result(monkeypatch, mutate):
    read_result = composition._read_ccz_result

    def changed(root):
        result = read_result(root)
        mutate(result)
        return result

    monkeypatch.setattr(composition, "_read_ccz_result", changed)


def test_wrong_ccz_result_sha_is_rejected_by_public_composition_entry(monkeypatch):
    monkeypatch.setattr(composition, "CCZ_RESULT_SHA256", "0" * 64)

    with pytest.raises(composition.CompositionValidationError, match="CCZ_RESULT_SHA_MISMATCH"):
        composition.build_verified_evidence_set()


def test_wrong_ccz_source_role_is_rejected_by_public_composition_entry(monkeypatch):
    _mutate_ccz_result(
        monkeypatch,
        lambda result: result.update(
            BONF64_SUPPORT_SOURCE_PATH=composition.BONF64_SOURCE_PATH
        ),
    )

    with pytest.raises(composition.CompositionValidationError, match="CCZ_PUBLIC_VALIDATOR_REJECTED"):
        composition.build_verified_evidence_set()


@pytest.mark.parametrize(
    "field,value",
    (
        ("BONF64_METHOD_IDENTITY", "UNRELATED_METHOD"),
        ("PROFILE_ID", "55555555555551999999"),
    ),
)
def test_wrong_ccz_method_or_profile_is_rejected_by_public_composition_entry(
    monkeypatch, field, value
):
    _mutate_ccz_result(monkeypatch, lambda result: result.update({field: value}))

    with pytest.raises(composition.CompositionValidationError, match="CCZ_PUBLIC_VALIDATOR_REJECTED"):
        composition.build_verified_evidence_set()


def test_bonf64_cannot_be_substituted_for_ccz_family_bound(monkeypatch):
    with monkeypatch.context() as patched:
        patched.setattr(
            composition, "CCZ_FAMILY_BOUND", composition.CCZ_BONF64_BOUND
        )
        with pytest.raises(composition.CompositionValidationError):
            composition.build_verified_evidence_set()

    # The actual public query keeps the independently certified Family row.
    evidence = composition.build_verified_evidence_set()
    assert evidence.query_certified_bound(
        composition.CCZ_PROFILE, composition.FAMILY_METHOD
    ) == 313250644


@pytest.mark.parametrize(
    "constant,wrong_value",
    (
        ("T249_NEW_BOUND", 313121138),
        ("T251_NEW_BOUND", 313142922),
    ),
)
def test_wrong_t249_or_t251_bound_is_rejected_by_public_composition_entry(
    monkeypatch, constant, wrong_value
):
    monkeypatch.setattr(composition.overlay, constant, wrong_value)

    with pytest.raises(composition.CompositionValidationError, match="T249_T251_OVERLAY_REJECTED"):
        composition.build_verified_evidence_set()


def test_third_family_override_is_rejected_by_public_composition_entry(monkeypatch):
    real_overlay = composition.overlay.build_verified_overlay()
    tampered = replace(
        real_overlay,
        _overrides=real_overlay._overrides
        + (("55555555555551000000", composition.CCZ_BONF64_BOUND),),
    )
    monkeypatch.setattr(
        composition.overlay, "build_verified_overlay", lambda: tampered
    )

    with pytest.raises(composition.CompositionValidationError, match="THIRD_FAMILY_OVERRIDE"):
        composition.build_verified_evidence_set()


def test_false_family_closure_is_rejected_by_public_composition_entry(monkeypatch):
    _mutate_ccz_result(
        monkeypatch,
        lambda result: result.update(FULL_FAMILY_CLOSURE="CLAIMED"),
    )

    with pytest.raises(composition.CompositionValidationError, match="CCZ_PUBLIC_VALIDATOR_REJECTED"):
        composition.build_verified_evidence_set()


def test_resource_history_promotion_is_rejected_by_public_composition_entry(monkeypatch):
    _mutate_ccz_result(
        monkeypatch,
        lambda result: result.update(HISTORICAL_RESOURCE="PASS"),
    )

    with pytest.raises(composition.CompositionValidationError, match="CCZ_PUBLIC_VALIDATOR_REJECTED"):
        composition.build_verified_evidence_set()
