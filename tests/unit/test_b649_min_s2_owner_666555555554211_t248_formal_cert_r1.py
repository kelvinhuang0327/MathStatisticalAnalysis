"""Focused universality, independent-domain and tamper checks; no solver."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import pytest

from lottolab.research import b649_min_s2_owner_666555555554211_t248_formal_cert_r1 as cert


@pytest.fixture(scope="module")
def result() -> cert.Document:
    return cert.compute_result()


def test_model_and_universal_identities() -> None:
    facts = cert.model_facts()
    assert (facts["EDGES"], facts["W"], facts["GOODMAN"], facts["CHOOSE3"], facts["A_MAX"]) == (
        93,
        828,
        294,
        2326,
        198,
    )
    # Construct a simple graph only, by degree reduction. Identity verification
    # applies independently of support attainability; it is NOT a witness.
    sigma = (0,) * 13 + (5, 5)
    remaining = [(6 + d - s, v) for v, (d, s) in enumerate(zip(cert.D[:15], sigma, strict=True))]
    edges: set[cert.Pair] = set(combinations(range(15, 20), 2))
    edges.update((x, z) for x in (13, 14) for z in range(15, 20))
    while remaining:
        remaining.sort(reverse=True)
        degree, v = remaining.pop(0)
        assert 0 <= degree <= len(remaining)
        for i in range(degree):
            old, w = remaining[i]
            assert old > 0
            remaining[i] = (old - 1, w)
            edges.add((min(v, w), max(v, w)))
    seen = cert.audit_graph(edges)
    assert min(cert.integer(v) for v in cert.inherited.items(seen["P_TERMS"])) >= 0
    assert seen["SUPPORT_ATTAINMENT"] == "NOT_ASSERTED"
    with pytest.raises(ValueError, match="sign"):
        cert.audit_graph(edges, sigma_sign=1)


def test_shadow_shared_companion_scope() -> None:
    assert cert.shadow_audit()["DISTINCT_CASES"] == 132
    assert not cert.shared_companion_allowed(12)
    assert all(cert.shared_companion_allowed(c) for c in range(12))
    # Only the shared degree-two companion is excluded: singly present d=2
    # candidates contribute to the retained distinct domain.
    s = (0,) * 11 + (0, 0, 5, 5)
    _, counts = cert.corrections(s)
    assert counts["DIFFERENT_D2"] == 132
    assert counts["DIFFERENT_RETAINED"] > 0


def test_overlap_and_common_multiplicity() -> None:
    assert cert.overlap_audit()["EDGE_BASIS_CHECKS"] == 152
    # The same base edge produces two DIFFERENT triangles with two low apices.
    a, b, edge = {0, 1}, {1, 2}, {3, 4}
    tau1, tau2, tau12 = (int(not edge.intersection(p)) for p in (a, b, a | b))
    assert tau1 + tau2 == 2 and tau1 + tau2 - tau12 == 1
    s = (0,) * 11 + (0, 0, 5, 5)
    assert cert.corrections(s)[0] == 8


def test_full_domain_and_independent_canonical_bytes(result: cert.Document) -> None:
    first, counts = cert.enumerate_records()
    second, other = cert.enumerate_records(True)
    assert first == second and counts == other
    assert len(first) == 1087 and len(cert.canonical_sigmas()) == 2835
    assert cert.canonical_sigmas() == cert.canonical_sigmas(True)
    assert cert.zero_maxima() == cert.zero_maxima(True)
    assert cert.records_bytes(first) == cert.records_bytes(second)
    enum = cert.obj(result["ENUMERATION"])
    assert enum["R_MAXIMA"] == [246, 248, 248, 246, 246, 244, 246, 228]
    assert enum["RECORDS_SHA256"] == cert.sha(cert.records_bytes(second))
    assert enum["LEGACY_DIGEST_MATCH"] == "NOT_VERIFIED"


def test_every_zero_graph_split_polynomial() -> None:
    # All labelled zero graphs, with cross totals inside the allowed interval.
    sigma_by_sum = {sum(s): s for s in cert.canonical_sigmas() if sum(s) in cert.R_VALUES}
    pairs = list(combinations(range(5), 2))
    for mask in range(1024):
        zeta = tuple(
            6 - sum(bool(mask & (1 << i)) for i, e in enumerate(pairs) if v in e) for v in range(5)
        )
        r = sum(zeta)
        if r in sigma_by_sum:
            assert type(cert.split_f(sigma_by_sum[r], zeta)) is int


def test_all_route_terms_and_fraction_rounding(result: cert.Document) -> None:
    old, new = cert.route_terms(cert.TARGET, 265), cert.route_terms(cert.TARGET, 248)
    assert len(old) == 244 and len(new) == 227 and new == old[:227]
    assert new[-1] == (248, 313242512, 372, 198, 206850, 4970672)
    for _, bound, _, _, floor, s3 in old:
        exact = Fraction(308390040 + s3) - Fraction(4 * floor, 7)
        assert bound - 1 < exact <= bound
    assert result["FULL_PROFILE_BOUND"] == 313242512
    assert result["PROFILE_DELTA"] == 152548
    assert result["STRICT_GAIN_EXCLUDED"] == "YES"
    assert result["SINGLE_ROW_FAMILY_BOUND"] == 313395060
    assert result["SINGLE_ROW_FAMILY_DELTA"] == 0


@pytest.mark.parametrize("constant", [5956, 5953])
def test_wrong_profile_k4_constant_rejected(constant: int) -> None:
    with pytest.raises(ValueError, match="5954"):
        cert.route_terms(cert.TARGET, 248, constant=constant)


def test_wrong_model_profile_and_cross_degree_rejected() -> None:
    with pytest.raises(ValueError, match="profile"):
        cert.model_facts("66655555555332000000")
    with pytest.raises(ValueError, match="profile/model"):
        cert.model_facts(model={**cert.MODEL, "PAIR_LINEARITY": False})
    with pytest.raises(ValueError, match="capacity"):
        cert.split_f((1,) + (0,) * 14, (2,) * 5)


def test_omitted_domain_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    frozen = cert.canonical_sigmas()
    monkeypatch.setattr(cert, "canonical_sigmas", lambda independent=False: frozen[:-1])
    with pytest.raises(ValueError, match="raw domain"):
        cert.enumerate_records()


def test_wrong_companion_exclusion_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def changed(c: int) -> bool:
        return c >= 0

    monkeypatch.setattr(cert, "shared_companion_allowed", changed)
    with pytest.raises(ValueError, match="exclusion counts"):
        cert.enumeration()


@pytest.mark.parametrize("mutation", ["omit", "sign"])
def test_omitted_branch_and_wrong_penalty_sign_rejected(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    original = cert.corrections

    def changed(s: cert.Degrees, independent: bool = False) -> tuple[int, cert.Counter[str]]:
        penalty, counts = original(s, independent)
        if s[14] == 5:
            return (0 if mutation == "omit" else -penalty), counts
        return penalty, counts

    monkeypatch.setattr(cert, "corrections", changed)
    with pytest.raises(ValueError, match="maxima"):
        cert.enumeration()


@pytest.mark.parametrize("which", ["base", "r2", "t223"])
def test_cursor_change_rejected(which: str) -> None:
    inputs = list(deepcopy(cert.load_inputs()))
    selected = inputs[["base", "r2", "t223"].index(which)]
    cursor = cert.obj(selected["CURSOR"])
    cursor["BOUND"] = cert.integer(cursor["BOUND"]) + 1
    with pytest.raises(ValueError, match="tampered"):
        cert.comparison(*inputs)


def test_tampered_reused_source_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.read_bytes
    target = cert.ROOT / cert.inherited.SOURCE

    def changed(path: Path) -> bytes:
        return original(path) + (b"# tampered\n" if path == target else b"")

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError, match="tampered reused source"):
        cert.source_pins()


@pytest.mark.parametrize("field", ["NEW_T_TERMS", "ENUMERATION", "TARGET_PROFILE"])
def test_incomplete_tampered_sealed_result_rejected(result: cert.Document, field: str) -> None:
    altered = deepcopy(result)
    del altered[field]
    with pytest.raises(ValueError, match="tampered result"):
        cert.verify_result(altered)
