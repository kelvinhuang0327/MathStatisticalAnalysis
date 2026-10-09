"""Focused checks for the T=270 structural closure; no canonical evaluator calls."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

import t270_structural_closure as closure  # noqa: E402


@pytest.fixture(scope="module")
def setup() -> dict[str, Any]:
    authority = closure.load_authority()
    generator = closure.import_generator(closure.import_evaluator())
    classification = closure.sts13_classification(generator)
    coverage = closure.family_coverage(
        generator, classification, authority["old_record"], authority["baseline_tickets"]
    )
    return {"authority": authority, "classification": classification, "coverage": coverage}


def test_phase1_arithmetic_forces_k12_plus_k8_minus_e() -> None:
    proof = closure.phase1_general_proof()
    assert proof["W"] == 816 and proof["OPEN_WEDGES_O"] == 6
    assert proof["C_FEASIBLE_AFTER_PARITY"] == [0, 2]
    assert all(proof["CHECKS"].values())


def test_classification_and_family_coverage(setup: dict[str, Any]) -> None:
    classification, coverage = setup["classification"], setup["coverage"]
    assert classification["ok"]
    record = classification["record"]["GENERATOR_REPRESENTATIVES"]
    assert record["CYCLIC"]["AUTOMORPHISM_GROUP_ORDER"] == 39
    assert record["NONCYCLIC"]["AUTOMORPHISM_GROUP_ORDER"] == 6
    assert coverage["ok"]
    assert len(coverage["class_rows"]) == 5
    assert coverage["record"]["BASELINE_ISO_CLASS"] == "NONCYCLIC/orbit3"


def test_certificates_are_not_vacuous(setup: dict[str, Any]) -> None:
    family = setup["coverage"]["family"]
    reps = setup["classification"]["reps"]
    assert closure.portfolio_isomorphism(family[("NONCYCLIC", 2)], family[("NONCYCLIC", 3)]) is None
    assert closure.portfolio_isomorphism(family[("CYCLIC", 0)], family[("NONCYCLIC", 0)]) is None
    assert closure.classify(family[("CYCLIC", 4)], reps)[0] == "CYCLIC"
    source, target = family[("NONCYCLIC", 9)], family[("NONCYCLIC", 2)]
    certificate = closure.portfolio_isomorphism(source, target)
    assert certificate is not None and closure.verify_certificate(source, target, certificate)
    tampered = {**certificate, "NUMBER_MAP": list(certificate["NUMBER_MAP"])}
    tampered["NUMBER_MAP"][0], tampered["NUMBER_MAP"][1] = (
        tampered["NUMBER_MAP"][1],
        tampered["NUMBER_MAP"][0],
    )
    assert not closure.verify_certificate(source, target, tampered)


def test_focused_checks_pass(setup: dict[str, Any]) -> None:
    focused = closure.focused_checks(
        setup["classification"],
        setup["coverage"]["family"],
        setup["authority"]["baseline_tickets"],
        trials=8,
    )
    assert focused["ok"], focused["record"]
