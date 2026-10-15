"""Focused scientific, full-domain, provenance and production-path negative checks."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from itertools import combinations
from typing import cast

import pytest

from lottolab.research import b649_min_s2_owner_666555555553311_exact_cert_r1 as a


@pytest.fixture(scope="module")
def reference() -> a.Document:
    return a.compute_result()


def test_complete_certificate_and_sealed_bytes(reference: a.Document) -> None:
    assert reference["NEW_PROVEN_T_CAP"] == 249
    assert reference["NEW_FULL_PROFILE_BOUND"] == 313248348
    assert reference["PROFILE_DELTA"] == 143392
    assert reference["OLD_TERM_COUNT"] == 244
    assert reference["NEW_TERM_COUNT"] == 228
    assert a.working_bytes(a.RESULT) == a.render(reference)
    domain = a.obj(reference["ENUMERATION"])
    assert domain["RETAINED_STATES"] == 1661
    assert domain["WITHOUT_PAIR_CAP"] == 253
    assert len(cast(list[object], domain["ARGMAX"])) == 2
    assert a.obj(a.obj(reference["FAMILY"])["AFTER"]) == {
        "BOUND": 313391740,
        "OWNER_IDS": ["66655555555411110000"],
        "GAP_TO_INCUMBENT": 127852,
        "OPEN_COUNT": 1515,
        "RESOLVED_MAXIMUM": 313391740,
        "CURSOR_MAXIMUM": 313388984,
    }
    assert reference["LEGAL_ATTAINMENT"] == reference["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


def test_all_small_graphs_validate_triangle_floors() -> None:
    """Bounded corroboration of the proved inequalities, not universal-proof sampling."""
    edges = list(combinations(range(5), 2))
    triples = list(combinations(range(5), 3))
    for mask in range(1024):
        es = {edge for bit, edge in enumerate(edges) if mask & (1 << bit)}
        degrees = tuple(sum(v in e for e in es) for v in range(5))
        triangles = sum(all(e in es for e in combinations(t, 2)) for t in triples)
        assert a.graphical_eg(degrees) and a.graphical_hh(degrees)
        assert a.floors_a(degrees) == a.floors_b(degrees)
        assert max(a.floors_a(degrees)) <= triangles


def test_pair_correction_improves_old_split_argmax() -> None:
    degrees = (2, 2, 2) + (3,) * 8 + (5, 5, 12, 12)
    assert a.floors_a(degrees) == a.floors_b(degrees) == (0, 0, 6)


def test_graphical_algorithms_reject_impossible_sequences() -> None:
    for sequence in ((2, 2, 0), (3, 1, 1, 1, 0), (-1, 1), (4, 2, 2, 0)):
        # (3,1,1,1,0) is graphical; include a positive control.
        expected = sequence == (3, 1, 1, 1, 0)
        assert a.graphical_eg(sequence) == a.graphical_hh(sequence) == expected


@pytest.mark.parametrize(
    ("defect", "match"),
    [
        ("wrong_profile", "wrong profile"),
        ("missing_states", "missing states"),
        ("invalid_assumption", "invalid theorem assumption"),
        ("incorrect_sign", "remainder disagreement"),
        ("wrong_cap", "wrong T cap"),
        ("incomplete_envelope", "incomplete envelope"),
        ("rounding_error", "nonintegral rational ceiling"),
        ("tampered_source", "working source mismatch"),
        ("cursor_mutation", "cursor/source mutation"),
    ],
)
def test_production_entry_rejects_defects(
    monkeypatch: pytest.MonkeyPatch, reference: a.Document, defect: str, match: str
) -> None:
    # Unrelated expensive recomputation can reuse this exact mathematical snapshot;
    # each injected defect still enters compute_result and its real guard.
    domain = deepcopy(a.obj(reference["ENUMERATION"]))
    if defect not in ("missing_states", "incorrect_sign"):
        monkeypatch.setattr(a, "domain_certificate", lambda: domain)
    if defect == "wrong_profile":
        original_facts = a.facts
        monkeypatch.setattr(a, "facts", lambda: original_facts("66655555555411110000"))
    elif defect == "missing_states":
        original_enumeration = a.enumerate_a
        monkeypatch.setattr(a, "enumerate_a", lambda: original_enumeration()[1:])
    elif defect == "invalid_assumption":
        original_load = a.load_base

        def bad_model() -> a.Document:
            doc = original_load()
            a.obj(doc["MODEL"])["PAIR_LINEARITY"] = False
            return doc

        monkeypatch.setattr(a, "load_base", bad_model)
    elif defect == "incorrect_sign":
        original_record = a.record_a

        def bad_sign(state: a.State) -> a.Document:
            doc = original_record(state)
            doc["UPPER"] = a.integer(doc["RAW"]) + a.integer(doc["C_K"]) + a.integer(doc["C_Z"])
            return doc

        monkeypatch.setattr(a, "record_a", bad_sign)
    elif defect == "wrong_cap":
        domain["CAP"] = 250
    elif defect == "incomplete_envelope":
        original_envelope = a.route.route_b_envelope

        def incomplete(profile: a.Degrees, cap: int, base: int) -> list[a.Term]:
            return list(original_envelope(profile, cap, base))[1:]

        monkeypatch.setattr(a.route, "route_b_envelope", incomplete)
    elif defect == "rounding_error":

        def rounded_down(value: Fraction) -> int:
            return value.numerator // value.denominator

        monkeypatch.setattr(a, "ceil", rounded_down)
    elif defect == "tampered_source":
        original_bytes = a.working_bytes

        def tampered(path: str) -> bytes:
            raw = original_bytes(path)
            return raw + b"\n# mutation" if path.endswith("refinement_r32.py") else raw

        monkeypatch.setattr(a, "working_bytes", tampered)
    elif defect == "cursor_mutation":
        original_authority = a.current_authority

        def mutate_cursor(base: a.Document) -> a.Document:
            authority = original_authority(base)
            a.obj(base["CURSOR"])["PROFILE_COUNT"] = 196
            return authority

        monkeypatch.setattr(a, "current_authority", mutate_cursor)
    with pytest.raises(ValueError, match=match):
        a.compute_result()


def test_bad_pair_theorem_assumption_rejected() -> None:
    with pytest.raises(ValueError, match="invalid theorem assumption"):
        a.floors_a((8, 8, -1))


def test_family_does_not_adopt_cursor_change(reference: a.Document) -> None:
    base = a.load_base()
    a.obj(a.obj(base["CURSOR"])["COARSE_BOUND_PROJECTION"])["65444444444444441100"] = 0
    with pytest.raises(ValueError, match="cursor/source mutation"):
        a.replay(base, a.integer(reference["NEW_FULL_PROFILE_BOUND"]))


def test_genuine_fraction_ceiling() -> None:
    # Explicitly inspect values where floor and ceiling differ.
    terms = a.fraction_terms(265, floor=113)
    assert any(t[4] % 7 for t in terms)
    for _, bound, _, _, s4, s3 in terms:
        numerator = 7 * (372228640 - 63838600 + s3) - 4 * s4
        assert 7 * (bound - 1) < numerator <= 7 * bound


def test_no_endpoint_only_envelope(reference: a.Document) -> None:
    new = cast(list[list[int]], reference["NEW_T_TERMS"])
    assert [t[0] for t in new] == list(range(22, 250))
    assert all(t[1] <= 313248348 for t in new)
    assert new[-1] == [249, 313248348, 380, 197, 212513, 4979744]


def test_production_guard_is_falsifiable(
    monkeypatch: pytest.MonkeyPatch, reference: a.Document
) -> None:
    # This same mutation is also used in the external red/green falsifiability probe.
    domain = deepcopy(a.obj(reference["ENUMERATION"]))
    domain["CAP"] = 250
    monkeypatch.setattr(a, "domain_certificate", lambda: domain)
    with pytest.raises(ValueError, match="wrong T cap"):
        a.compute_result()
