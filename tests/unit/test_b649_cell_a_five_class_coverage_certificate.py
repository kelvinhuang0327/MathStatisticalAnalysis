"""Focused bridge verification only: no original rigidity suite, solve, or exact scoring.

Small invalid fixtures make completeness, scope and full-support checks falsifiable. Actual
pinned source topology, all 26 deletion keys, all ten U partitions, and both preserved STSs
are exercised. Solver and scorer guards apply before any coverage fixture is built.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from importlib import import_module
from itertools import combinations
from pathlib import Path
from typing import NoReturn, cast

import pytest

from lottolab.research import b649_cell_a_five_class_coverage_certificate as cert
from lottolab.research import b649_cell_a_overlap_rigidity_certificate as rigidity
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_two_open_cells_targeted_solver as engine

ROOT = Path(__file__).resolve().parents[2]
KEYS = tuple((name, p) for name in ("CYCLIC", "NONCYCLIC") for p in range(13))


@pytest.fixture(scope="module", autouse=True)
def refuse_solving_and_scoring() -> Iterator[list[str]]:
    calls: list[str] = []

    def refuse(*_: object, **__: object) -> NoReturn:
        calls.append("forbidden solve/scoring")
        raise AssertionError("CP-SAT or exact scoring was called")

    cp = import_module("ortools.sat.python.cp_model")
    official = import_module("lottolab.research.b649_official_any_prize_exact")
    with pytest.MonkeyPatch.context() as patch:
        solver = cp.CpSolver
        for name in ("Solve", "solve", "SearchForAllSolutions", "SolveWithSolutionCallback"):
            if hasattr(solver, name):
                patch.setattr(solver, name, refuse)
        for module, names in (
            (census, ("cp_sat_solve", "official_evaluator", "support_model", "k20_model")),
            (engine, ("cp_sat_solve", "exact_evaluator", "configured_solver")),
            (official, ("evaluate_portfolio", "all_main_draw_masks")),
        ):
            for name in names:
                patch.setattr(module, name, refuse)
        yield calls
    assert calls == []


@pytest.fixture(scope="module")
def coverage() -> cert.Coverage:
    return cert.build_coverage(ROOT)


@pytest.fixture(scope="module")
def record(coverage: cert.Coverage) -> dict[str, object]:
    return cert.certificate(coverage)


def test_sources_and_rigidity_bind_exactly(coverage: cert.Coverage) -> None:
    blobs = cert.read_sources(ROOT)
    cert.verify_source_bytes(blobs)
    assert len(blobs) == 5
    assert coverage.rigidity_record == rigidity.certificate()
    assert coverage.rigidity_record["CERTIFICATE_SHA256"] == cert.RIGIDITY_SHA256
    assert cert.RIGIDITY_SHA256 == (
        "db91bb0689e978de16e33776fe975515c899c31396107b5908daed35d07d6c96"
    )
    assert engine.engine_sha256() == cert.SOURCES[1].sha256
    assert coverage.sts.STS13_SOURCE["BLOB"] == cert.SOURCES[3].blob
    assert cert.SOURCES[1].commit == "03b5691fac02c3a125c91cf4120b6219c3143b5e"


@pytest.mark.parametrize("name", [pin.name for pin in cert.SOURCES])
def test_missing_and_changed_sources_fail(name: str) -> None:
    blobs = cert.read_sources(ROOT)
    del blobs[name]
    with pytest.raises(cert.CoverageError, match="source missing"):
        cert.load_donors(blobs)
    blobs = cert.read_sources(ROOT)
    blobs[name] += b"\n# identity change\n"
    with pytest.raises(cert.CoverageError, match="source SHA256 mismatch"):
        cert.load_donors(blobs)


def test_no_historical_results_or_fresh_recount_are_source_inputs() -> None:
    assert all(pin.path.startswith("src/lottolab/research/") for pin in cert.SOURCES)
    assert all("recount" not in pin.path and "result" not in pin.path for pin in cert.SOURCES)
    assert not {"evaluate_portfolio", "run_family", "score_family_candidates", "seal_result"} & (
        cert.CONSTRUCTOR_SYMBOLS | cert.STS_SYMBOLS
    )


@pytest.mark.parametrize("index", range(10))
def test_every_u_partition_has_explicit_full_support_map(index: int) -> None:
    part = cert.u_partitions()[index]
    pairs = cert.u_pairs(part)
    mapping = cert.u_mapping(part, pairs)
    assert len(pairs) == 21
    assert sorted(mapping) == list(range(20))
    assert mapping[:12] == tuple(range(12))
    assert all(cert.PROFILE[v] == cert.PROFILE[w] for v, w in enumerate(mapping))
    assert {tuple(sorted(mapping[v] for v in t)) for t in part} == {(12, 13, 14), (15, 16, 17)}
    assert {tuple(sorted(mapping[v] for v in p)) for p in pairs} == set(
        cert.u_pairs(((12, 13, 14), (15, 16, 17)))
    )


def test_u_partition_enumeration_is_exhaustive() -> None:
    # Independently choose all 20 triples, then quotient the interchange of their complements.
    parts = {
        tuple(sorted((block, tuple(v for v in cert.POSITIVE_U if v not in block))))
        for block in combinations(cert.POSITIVE_U, 3)
    }
    assert len(parts) == 10 and set(cert.u_partitions()) == parts


def test_exact_26_keys_25_byte_hashes_and_five_support_classes(
    coverage: cert.Coverage, record: dict[str, object]
) -> None:
    assert tuple(c.key for c in coverage.candidates) == KEYS
    cert.verify_complete_keys(c.key for c in coverage.candidates)
    assert (
        record["RAW_KEYS"],
        record["NORMALIZED_SHA_COUNT"],
        record["ISOMORPHISM_CLASS_COUNT"],
    ) == (26, 25, 5)
    assert coverage.point_orbits == {
        "CYCLIC": (tuple(range(13)),),
        "NONCYCLIC": ((0, 1, 4, 8, 11, 12), (2, 7, 9), (3, 5, 10), (6,)),
    }
    assert len({c.canonical.witness_id for c in coverage.candidates}) == 5
    assert len({cert.normalized_sha(c.tickets) for c in coverage.candidates}) == 25


def test_one_missing_key_is_detected(coverage: cert.Coverage) -> None:
    damaged = replace(coverage, candidates=coverage.candidates[:-1])
    with pytest.raises(cert.CoverageError, match=r"pointed completeness: missing=.*12"):
        cert.certificate(damaged)
    with pytest.raises(cert.CoverageError, match="pointed completeness"):
        cert.cover_solution(coverage.candidates[0].tickets, damaged)


@pytest.mark.parametrize("keys", [(*KEYS[:-1], KEYS[0]), (*KEYS, ("FOREIGN", 0))])
def test_duplicate_and_foreign_keys_are_detected(keys: tuple[cert.Key, ...]) -> None:
    with pytest.raises(cert.CoverageError, match="pointed completeness"):
        cert.verify_complete_keys(keys)


@pytest.mark.parametrize("key", KEYS)
def test_original_constructor_extension_deletion_round_trip_and_chain(
    key: cert.Key, coverage: cert.Coverage
) -> None:
    raw = next(c for c in coverage.candidates if c.key == key)
    extension = cert.extend_h(raw.structure, coverage.constructor)
    # Deletion of the added point recovers all H supports, using the original constructor.
    round_trip = cert.delete_h(extension, 12, coverage.constructor)
    assert cert.supports(round_trip) == raw.structure
    assert len(extension) == 26 and coverage.constructor.is_valid_sts13(extension)
    remaining = [p for p in range(13) if p != key[1]]
    known_point_map = (*remaining, key[1])
    assert {tuple(sorted(known_point_map[v] for v in block)) for block in extension} == set(
        coverage.sts.STS13_DESIGNS[key[0]]
    )
    chain = cert.cover_solution(raw.tickets, coverage)
    representative = next(r for r in coverage.representatives if r.class_id == chain.class_id)
    cert.verify_support_map(raw.tickets, representative.candidate.tickets, chain.composed)
    # Both complete labelled bijections are checked, rather than overlap adjacency alone.
    assert sorted(chain.composed.tickets) == list(range(20))
    assert sorted(chain.composed.numbers) == list(range(1, 50))


def shuffled(raw: cert.Candidate) -> cert.Portfolio:
    sigma = (*reversed(range(12)), *reversed(range(12, 18)), 19, 18)
    changed: list[tuple[int, ...]] = [()] * 20
    for v, ticket in enumerate(raw.tickets):
        changed[sigma[v]] = tuple(50 - n for n in ticket)
    return tuple(changed)


@pytest.mark.parametrize("key", KEYS)
def test_arbitrary_degree_preserving_ticket_and_number_labels(
    key: cert.Key, coverage: cert.Coverage
) -> None:
    raw = next(c for c in coverage.candidates if c.key == key)
    source = shuffled(raw)
    chain = cert.cover_solution(source, coverage)
    assert chain.class_id == coverage.representative(raw).class_id
    rep = next(r for r in coverage.representatives if r.class_id == chain.class_id)
    cert.verify_support_map(source, rep.candidate.tickets, chain.composed)
    cert.verify_support_map(
        source, next(c for c in coverage.candidates if c.key == chain.key).tickets, chain.to_raw_key
    )


@pytest.mark.parametrize("partition", cert.u_partitions())
def test_entire_model_chain_with_each_u_decomposition(
    partition: tuple[cert.Block, cert.Block], coverage: cert.Coverage
) -> None:
    raw = coverage.candidates[0]
    structure = census.Structure(
        tuple(sorted((*[t for t in raw.structure.triples if set(t) <= cert.H], *partition))),
        tuple(
            sorted(
                (*[p for p in raw.structure.pairs if set(p) <= cert.H], *cert.u_pairs(partition))
            )
        ),
    )
    tickets = census.portfolio(structure)
    chain = cert.cover_solution(tickets, coverage)
    assert chain.class_id == coverage.representative(raw).class_id


def test_c2_and_c4_have_distinct_complete_support_classes(coverage: cert.Coverage) -> None:
    c2 = next(r.candidate for r in coverage.representatives if r.class_id == "C2")
    c4 = next(r.candidate for r in coverage.representatives if r.class_id == "C4")
    assert census.edges(c2.structure) == census.edges(c4.structure)
    assert c2.canonical.structure != c4.canonical.structure
    assert c2.canonical.witness_id != c4.canonical.witness_id
    with pytest.raises(engine.CanonicalFormError, match="only equal canonical forms"):
        engine.isomorphism(c2.canonical, c2.structure, c4.canonical, c4.structure)


@pytest.mark.parametrize("profile,t", [("66665555555322000000", 270), (cert.PROFILE_ID, 269)])
def test_other_profile_or_target_is_rejected(profile: str, t: int) -> None:
    with pytest.raises(cert.CoverageError, match="scope"):
        cert.build_coverage(ROOT, profile_id=profile, t=t)


@pytest.mark.parametrize(
    "classification",
    [
        None,
        replace(cert.CLASSIFICATION, doi="other"),
        replace(cert.CLASSIFICATION, unpointed_classes=3),
        replace(cert.CLASSIFICATION, locally_proved=True),
    ],
)
def test_classification_identity_is_required(
    classification: cert.ExternalClassification | None,
) -> None:
    with pytest.raises(cert.CoverageError, match="classification identity"):
        cert.build_coverage(ROOT, classification=classification)


def test_cross_component_support_is_rejected(coverage: cert.Coverage) -> None:
    raw = coverage.candidates[0].structure
    changed = replace(raw, pairs=tuple(sorted((*raw.pairs[1:], (0, 12)))))
    with pytest.raises(cert.CoverageError, match="cross-component support"):
        cert.extend_h(changed, coverage.constructor)


@pytest.mark.parametrize("triples", [((12, 13, 14), (12, 15, 16)), ((12, 13, 14), (15, 16, 18))])
def test_wrong_u_triple_degrees_are_rejected(triples: tuple[cert.Block, cert.Block]) -> None:
    with pytest.raises(cert.CoverageError, match="U triple degree"):
        cert.u_mapping(triples, cert.u_pairs(triples))


def test_wrong_u_pair_decomposition_is_rejected() -> None:
    part = cert.u_partitions()[0]
    with pytest.raises(cert.CoverageError, match="remaining 21 edges"):
        cert.u_mapping(part, cert.u_pairs(part)[:-1])


def test_overlap_only_bijection_is_rejected(coverage: cert.Coverage) -> None:
    source = coverage.candidates[0].tickets
    # Swapping any two number labels preserves overlap, but identity numbers cease to map supports.
    target = tuple(tuple(2 if n == 1 else 1 if n == 2 else n for n in t) for t in source)
    assert census.edges(cert.supports(source)) == census.edges(cert.supports(target))
    identity = cert.SupportMap(tuple(range(20)), tuple(range(1, 50)))
    with pytest.raises(cert.CoverageError, match="complete number supports"):
        cert.verify_support_map(source, target, identity)
    correct = cert.support_map(source, target, identity.tickets)
    assert correct.numbers[:2] == (2, 1)
    with pytest.raises(cert.CoverageError, match="both be bijections"):
        cert.verify_support_map(source, target, replace(correct, numbers=(1,) * 49))


def test_wrong_ticket_profile_and_support_model_are_rejected(coverage: cert.Coverage) -> None:
    source = list(coverage.candidates[0].tickets)
    source[0], source[12] = source[12], source[0]
    with pytest.raises(cert.CoverageError):
        cert.cover_solution(tuple(source), coverage)
    with pytest.raises(cert.CoverageError, match="six distinct numbers"):
        cert.cover_solution(((1, 1, 2, 3, 4, 5), *tuple(source)[1:]), coverage)
    with pytest.raises(cert.CoverageError, match="two or three tickets"):
        cert.cover_solution(tuple((1, 2, 3, 4, 5, 6) for _ in range(20)), coverage)


def test_certificate_replay_and_tamper_detection(
    record: dict[str, object],
    coverage: cert.Coverage,
) -> None:
    # JSON round trip tests the actual serialized artifact's shape and hash convention.
    cert.verify_certificate(cast(dict[str, object], json.loads(json.dumps(record))), coverage)
    with pytest.raises(cert.CoverageError, match="differs from replayed evidence"):
        cert.verify_certificate({**record, "RAW_KEYS": 25}, coverage)
    assert record["CELL_A_SCORE_CLOSURE"] == "NOT_CLAIMED_BY_THIS_TASK"
    assert record["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
    assert record["EXTERNAL_CLASSIFICATION_DEPENDENCY"] == cert.asdict(cert.CLASSIFICATION)
    assert cert.CLASSIFICATION.locally_proved is False
    assert "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT" not in json.dumps(record)
    print(
        "\nCERTIFICATE_HANDOFF="
        + json.dumps(
            {
                "CERTIFICATE_SHA256": record["CERTIFICATE_SHA256"],
                "RAW_KEYS": record["RAW_KEYS"],
                "NORMALIZED_SHA_COUNT": record["NORMALIZED_SHA_COUNT"],
                "ISOMORPHISM_CLASS_COUNT": record["ISOMORPHISM_CLASS_COUNT"],
                "REPRESENTATIVES": [
                    {
                        "CLASS_ID": r.class_id,
                        "KEY": r.candidate.key,
                        "CANONICAL_ID": r.candidate.canonical.witness_id,
                    }
                    for r in coverage.representatives
                ],
            },
            sort_keys=True,
        )
    )


def test_mapping_chain_refuses_tampered_rigidity_record(coverage: cert.Coverage) -> None:
    altered = replace(coverage, rigidity_record={**coverage.rigidity_record, "CROSS_EDGES": 1})
    with pytest.raises(rigidity.CertificateError, match="differs from its derivation"):
        cert.cover_solution(coverage.candidates[0].tickets, altered)


def test_canonicalizer_is_independent_of_scoring_and_guards_are_installed(
    coverage: cert.Coverage,
    refuse_solving_and_scoring: list[str],
) -> None:
    assert refuse_solving_and_scoring == []
    assert (
        len(
            {
                engine.canonicalize(cert.PROFILE, r.candidate.structure).witness_id
                for r in coverage.representatives
            }
        )
        == 5
    )
    assert refuse_solving_and_scoring == []
