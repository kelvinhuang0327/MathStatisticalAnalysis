"""Next two exact R14 owners, surgical preservation, semantic mutations and byte replay."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from math import comb
from pathlib import Path
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_state_13548976_next_two_r14_certificate_r1 as cert

EXACT_MOMENT_DIGESTS = [
    "c38050a9a796fcff5d18dd3cc9095e0856dd116d5249a4f124e39a1a44d3e38b",
    "eaf14b7980a6af1ef1114f667c7b0b73db71c669e2f997a8ed01e7e86bff7c42",
]
SUPPORT_DIGESTS = [
    "373c8f6ad926032326e24bd2078d6cf0605e0c40ea5059d4776fafef72103a3e",
    "a3bbbc9906ab8fe23e8603ae3b166ad7a5e686fe9cd93da1e61a4d15df881d3a",
]
PRESERVED_MEMBER_BOUNDS_DIGEST = "ea12eb6a4d98475a495caa53f815555e0c8bb78a08f0aa71cab408e39f1d537a"


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def test_exact_source_and_region_identity(result: dict[str, Any]) -> None:
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    assert result["BASE_HEAD"] == "2935eeba8ffd476575820a3be69f1c42a0132798"
    assert result["BASE_TREE"] == "00fd9da1e20e419e7f3e589ef992d0267ed7993b"
    assert result["BASE_RESULT_SHA256"] == cert.BASE_RESULT_SHA256
    assert result["BASE_MODULE_SHA256"] == cert.BASE_MODULE_SHA256
    for relative, pinned in (
        (
            cert.prior.RESULT_RELATIVE,
            "d34f27530cda179d6b1461cbdffcf2539ccee2eb21dd8f2a4c6745f7df92b70b",
        ),
        (
            "src/lottolab/research/b649_k20_r3_current_state_two_member_r14_refinement_r1.py",
            "2f2709213026e6aa80f4cccd4f19e9d1bdd39e693e103ab812dd4145e6ec6f99",
        ),
    ):
        assert sha256((cert.REPO_ROOT / relative).read_bytes()).hexdigest() == pinned
    assert result["TWO_MEMBER_IDS"] == list(cert.TARGET_IDS)
    assert result["REPRESENTED_VECTOR_COVERAGE"] == [1, 1]
    assert (
        result["REGION_SHA256"]
        == cert.REGION_SHA256
        == "1eed0fb9bc975d825d42413dd07ebfad5296d00185118850a38512c8a94e1f63"
    )
    assert result["REGION_COMPRESSED_MEMBER_COUNT"] == 1427
    assert result["REGION_REPRESENTED_VECTOR_COUNT"] == 1543
    assert result["PRESERVED_MEMBER_COUNT"] == 1425
    assert cert.prior_authority()["FINAL_OWNER_IDS"] == [cert.TARGET_STATE_ID]


def test_every_tied_owner_is_read_from_the_complete_catalog(result: dict[str, Any]) -> None:
    members = cert.six.region_members()
    bounds = cert.current_member_bounds(members)
    top = max(bounds.values())
    tied = [m for m in members if bounds[m.counts] == top]
    assert top == result["START_STATE_BOUND"] == 355_595_338
    assert [cert.member_id(m.counts) for m in tied] == list(cert.TARGET_IDS)
    assert [m.represented_vector_count for m in tied] == [1, 1]
    assert all(m.raw_bound == top for m in tied)
    # The stored predecessor ledger names the same owners without any module logic.
    stored = cert.prior_authority()["COMPLETE_REGION_MEMBERS"]
    assert [r["member_id"] for r in stored if r["final_bound"] == top] == list(cert.TARGET_IDS)
    assert max(r["final_bound"] for r in stored) == top
    # Each represented vector is the member's own witness: no hidden extra vector.
    recovered = cert.represented_vectors()
    assert recovered == {m.counts: (m.counts,) for m in tied}
    assert sum(len(v) for v in recovered.values()) == 2


def test_each_own_exact_residual_pair_arithmetic(result: dict[str, Any]) -> None:
    occupied_sets: list[set[tuple[int, int]]] = []
    for member in result["MEMBER_CERTIFICATES"]:
        vector = cert.dense(member["witness_counts"])
        row = member["vector_certificates"][0]
        moment = row["moment_certificate"]
        assert cert.prior.exact_moment_certificate(vector) == moment
        assert row["residual_event_definition"] == cert.hunter.RESIDUAL_EVENT_DEFINITION
        occupied = cert.six.occupied_type_pairs(vector)
        occupied_sets.append(set(occupied))
        assert {tuple(p["types"]) for p in moment["pair_table_rows"]} == set(occupied)
        minima = 0
        exact_rows = 0
        slopes: list[Fraction] = []
        for pair in moment["pair_table_rows"]:
            left, right = pair["types"]
            multiplicity = comb(vector[left], 2) if left == right else vector[left] * vector[right]
            assert pair["pair_count"] == multiplicity
            rows = pair["exact_residual_rows"]
            exact_rows += len(rows)
            overlaps = cert.hunter.feasible_cell_overlaps(
                cert.hunter.type_cells(left), cert.hunter.type_cells(right)
            )
            assert {tuple(r[2:6]) for r in rows} == set(overlaps)
            for r in rows:
                overlap = tuple(r[2:6])
                direct = cert.hunter.outcome_count(
                    cert.hunter.realize_pair(
                        cert.hunter.type_cells(left), cert.hunter.type_cells(right), overlap
                    ),
                    (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B),
                )
                assert direct == r[6] == cert.six.residual_pair_intersection(left, right, overlap)
            minimum = min(r[6] for r in rows)
            slope = min(Fraction(r[6] - minimum, r[5]) for r in rows if r[5])
            assert pair["pair_minimum"] == minimum
            assert pair["outside_slope"] == [slope.numerator, slope.denominator]
            assert all(r[6] >= minimum + slope * r[5] for r in rows)
            minima += multiplicity * minimum
            slopes.append(slope)
        assert exact_rows == 43
        assert moment["pair_count_total"] == 153
        assert minima == moment["pair_minimum_sum"] == 16_398_760
        outside = sum(n * cert.hunter.type_cells(i)[3] for i, n in enumerate(vector))
        assert outside == moment["outside_incidence_total"] == 96
        q, r = divmod(outside, 40)
        mass = (40 - r) * comb(q, 2) + r * comb(q + 1, 2)
        assert mass == moment["outside_pair_mass_floor"] == 72
        slope = min(slopes)
        assert slope == Fraction(433_006)
        assert (
            minima + cert.prior.ceil_fraction(slope * mass)
            == row["residual_pair_moment"]
            == 47_575_192
        )
        assert row["r14_correction"] == cert.prior.ceil_fraction(Fraction(47_575_192, 9))
        assert row["r14_correction"] == (47_575_192 + 8) // 9 == 5_286_133
        assert row["r14_correction"] != 47_575_192 // 9
        assert moment["multiplicity_dual"] == [1, 9]
        assert moment["multiplicity_cap"] == 18
        assert all(Fraction(comb(m, 2), 9) <= max(0, m - 1) for m in range(19))
    # The A-only and B-only events require distinct tables even when their floors coincide.
    assert occupied_sets[0] != occupied_sets[1]


def test_exact_integer_ceiling_above_float_precision() -> None:
    for n in (0, 9, 10, 47_575_192, 9 * 2**70 + 1):
        assert cert.prior.ceil_fraction(Fraction(n, 9)) == (n + 8) // 9
    with pytest.raises(ValueError, match="nonnegative"):
        cert.prior.ceil_fraction(Fraction(-1))


def test_certificate_and_support_identities(result: dict[str, Any]) -> None:
    records = result["MEMBER_CERTIFICATES"]
    vectors = [cert.dense(r["witness_counts"]) for r in records]
    moments = [cert.prior.exact_moment_certificate(v) for v in vectors]
    supports = [cert.hunter.r12.construct_support_witness(v) for v in vectors]
    assert [cert.digest(m) for m in moments] == EXACT_MOMENT_DIGESTS
    assert [cert.digest(s) for s in supports] == SUPPORT_DIGESTS
    assert result["EXACT_MOMENT_DIGESTS"] == EXACT_MOMENT_DIGESTS
    assert result["SUPPORT_DIGESTS"] == SUPPORT_DIGESTS
    for record, moment, support in zip(records, moments, supports, strict=True):
        row = record["vector_certificates"][0]
        assert row["moment_certificate"] == moment
        assert row["support_witness"] == [list(t) for t in support]
        assert row["moment_sha256"] == cert.digest(moment)
        assert row["support_sha256"] == cert.digest(support)
    assert len(set(EXACT_MOMENT_DIGESTS)) == len(set(SUPPORT_DIGESTS)) == 2


def test_max_single_credit_and_exact_witnesses(result: dict[str, Any]) -> None:
    for member in result["MEMBER_CERTIFICATES"]:
        vector = cert.dense(member["witness_counts"])
        row = member["vector_certificates"][0]
        corrections = row["corrections"]
        assert corrections == {
            "R6_PAIR": 1_829_688,
            "FOREST": 4_018_000,
            "R14": 5_286_133,
            "NINE_EVENT_HUNTER": 3_193_400,
            "ELEVEN_EVENT_HUNTER": 4_341_400,
        }
        assert row["prior_applied_correction"] == 4_018_000
        assert row["combined_correction"] == max(corrections.values()) != sum(corrections.values())
        assert row["uncorrected_anchor_bound"] == row["anchor_union"] + row["residual_event_sum"]
        assert row["uncorrected_anchor_bound"] == 359_613_338
        assert row["uncorrected_anchor_bound"] - row["prior_applied_correction"] == 355_595_338
        assert row["uncorrected_anchor_bound"] - row["combined_correction"] == 354_327_205
        assert member["member_new_bound"] == 354_327_205
        assert member["member_certified_correction"] == min(
            v["combined_correction"] for v in member["vector_certificates"]
        )
        support = tuple(tuple(t) for t in row["support_witness"])
        assert cert.r8.validate_support_assignment(vector, support)
        assert cert.digest(support) == row["support_sha256"]
        residual, s4 = cert.r8.witness_costs(vector, support)
        assert residual == row["support_residual_pair_moment"] >= row["residual_pair_moment"]
        assert (
            s4
            == row["support_s4_pair_moment"]
            >= row["moment_certificate"]["s4_pairwise_lower_bound"]
        )
        for key, n, floor in (
            ("nine_event_witness_analysis", 9, 3_193_400),
            ("eleven_event_witness_analysis", 11, 4_341_400),
        ):
            analysis = row[key]
            assert len(analysis["subset_tree"]) == n - 1
            assert len(analysis["extended_tree"]) == 17
            assert analysis["exact_tree_weight"] >= analysis["phi_tree_weight"] >= floor
    assert result["DUPLICATE_CORRECTIONS"] == 0
    assert result["NO_DOUBLE_COUNT_STATUS"] == "PASS_MAX_SINGLE_REPLACEMENT"


def test_all_other_members_and_previous_certificates_preserved(result: dict[str, Any]) -> None:
    source = cert.prior_authority()
    before = {r["member_id"]: r for r in source["COMPLETE_REGION_MEMBERS"]}
    after = result["COMPLETE_REGION_MEMBERS"]
    assert len(after) == len({r["member_id"] for r in after}) == 1427
    assert sum(r["represented_vector_count"] for r in after) == 1543
    changed: set[str] = set()
    for row in after:
        old = before[row["member_id"]]
        assert row["prior_bound"] == old["final_bound"]
        for key in ("member_id", "witness_counts", "raw_bound", "represented_vector_count"):
            assert row[key] == old[key]
        if row["final_bound"] != old["final_bound"]:
            changed.add(row["member_id"])
    assert changed == set(cert.TARGET_IDS)
    # The preserved-bounds digest is re-derived here from the stored predecessor rows.
    preserved = tuple(
        (cert.dense(r["witness_counts"]), r["final_bound"])
        for r in source["COMPLETE_REGION_MEMBERS"]
        if r["member_id"] not in cert.TARGET_IDS
    )
    assert len(preserved) == 1425 == result["PRESERVED_MEMBER_COUNT"]
    assert cert.digest(preserved) == result["PRESERVED_MEMBER_BOUNDS_SHA256"]
    assert result["PRESERVED_MEMBER_BOUNDS_SHA256"] == PRESERVED_MEMBER_BOUNDS_DIGEST
    assert result["PRESERVED_MEMBER_BOUNDS_STATUS"] == "PASS_1425_MEMBER_BOUNDS_UNCHANGED"
    # Earlier certificates, including both Hunter certificates, are carried unchanged.
    assert result["PREVIOUS_TWO_MEMBER_CERTIFICATES_SHA256"] == cert.json_digest(
        source["MEMBER_CERTIFICATES"]
    )
    assert result["PREVIOUS_REGION_CERTIFICATES_SHA256"] == cert.json_digest(
        source["PREVIOUS_REGION_CERTIFICATES"]
    )
    assert result["PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256"] == cert.digest(
        cert.prior.source_authority()["MEMBER_CERTIFICATES"]
    )
    assert (
        result["PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256"]
        == source["PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256"]
    )
    donors = result["DONOR_SOURCE_IDENTITIES"]
    assert donors["NINE_EVENT"]["proof"] == cert.prior.source_authority()["NINE_EVENT_PROOF"]
    assert donors["ELEVEN_EVENT"]["proof"] == cert.base.prior.eleven_event_proof()
    assert donors["TWO_MEMBER_REFINEMENT"]["result_sha256"] == cert.BASE_RESULT_SHA256
    # The superseded two-member certificates stay readable and unmodified in their source.
    assert [r["member_new_bound"] for r in source["MEMBER_CERTIFICATES"]] == [354_424_001] * 2


def test_complete_23_state_maximum_and_regression_targets(result: dict[str, Any]) -> None:
    start = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    final = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(start) == len(final) == result["STATE_TERM_COUNT"] == 23
    assert {k for k in start if start[k] != final[k]} == {cert.TARGET_STATE_ID}
    assert result["START_STATE_TERMS"] == cert.prior_authority()["FINAL_STATE_TERMS"]
    assert result["START_STATE_BOUND"] == result["START_COMPLETE_R3_UB"] == 355_595_338
    assert result["FINAL_STATE_BOUND"] == max(
        r["final_bound"] for r in result["COMPLETE_REGION_MEMBERS"]
    )
    assert result["FINAL_STATE_BOUND"] == result["FINAL_COMPLETE_R3_UB"] == 355_594_890
    assert result["FINAL_COMPLETE_R3_UB"] == max(
        max(final.values()), result["TAIL_BOUND"], result["CLASSIFIED_MAX"]
    )
    assert result["FINAL_OWNER_IDS"] == ["state:s2-13548976-s3-951748"]
    assert result["FINAL_STATE_MEMBER_IDS"] == ["[0,11][4,1][5,4][16,2]", "[0,11][1,1][5,4][16,2]"]
    assert result["REMAINING_GAP"] == result["FINAL_COMPLETE_R3_UB"] - 313_263_888 == 42_331_002
    assert result["TAIL_BOUND"] == 354_039_277
    assert result["CLASSIFIED_MAX"] == 355_468_904
    for key in ("TAIL_BOUND", "CLASSIFIED_AGGREGATE", "CLASSIFIED_MAX", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == cert.prior_authority()[key]
    assert result["CLASSIFIED_TERM_COUNT"] == 56_550
    assert (
        cert.recompute_family(result["FINAL_STATE_BOUND"])["final"]
        == result["FINAL_FAMILY_MAX_RECOMPUTATION"]
    )
    assert (
        result["START_FAMILY_MAX_RECOMPUTATION"]
        == (cert.prior_authority()["FINAL_FAMILY_MAX_RECOMPUTATION"])
    )


def test_byte_for_byte_result_replay(result: dict[str, Any]) -> None:
    assert cert.RESULT_PATH.read_bytes() == cert.encode(result).encode()
    assert cert.verify_result(result) == {
        "status": "PASS",
        "members": 2,
        "vectors": 2,
        "region_members": 1427,
    }
    assert cert.verify_stored_result()["status"] == "PASS"


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("source", "source identity"),
        ("base_module", "source identity"),
        ("missing_member", "two member"),
        ("duplicate_member", "two member"),
        ("missing_vector", "represented-vector"),
        ("foreign_vector", "identity or compression"),
        ("signature", "identity or compression"),
        ("pair_event", "residual moment"),
        ("pair_minimum", "residual moment"),
        ("slope", "residual moment"),
        ("mass", "residual moment"),
        ("moment", "residual moment"),
        ("moment_digest", "residual moment"),
        ("ceiling", "integer ceiling"),
        ("multiplicity", "residual moment"),
        ("sum_credit", "max single"),
        ("double_subtraction", "max single"),
        ("hunter_credit", "max single"),
        ("witness", "support witness is invalid"),
        ("witness_digest", "fingerprint"),
        ("preserved_member", "region preservation"),
        ("preserved_digest", "region preservation"),
        ("region_coverage", "region preservation"),
        ("state_term", "23-State"),
        ("owner", "23-State"),
        ("tied_owner", "23-State"),
        ("r3_bound", "23-State"),
        ("tail", "23-State"),
        ("aggregate", "23-State"),
        ("member_bound", "witness arithmetic differs"),
        ("vectors_list", "represented-vector"),
        ("meta", "differs from complete exact replay"),
    ],
)
def test_semantic_mutations_rejected(result: dict[str, Any], mutation: str, reason: str) -> None:
    bad = copy.deepcopy(result)
    member = bad["MEMBER_CERTIFICATES"][0]
    row = member["vector_certificates"][0]
    moment = row["moment_certificate"]
    if mutation == "source":
        bad["BASE_HEAD"] = "0" * 40
    elif mutation == "base_module":
        bad["BASE_MODULE_SHA256"] = "0" * 64
    elif mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(member))
    elif mutation == "missing_vector":
        member["vector_certificates"].pop()
    elif mutation == "foreign_vector":
        row["counts"] = bad["MEMBER_CERTIFICATES"][1]["witness_counts"]
    elif mutation == "signature":
        row["compression_signature"][0] += 1
    elif mutation == "pair_event":
        moment["pair_table_rows"][0]["exact_residual_rows"][0][6] += 1
    elif mutation == "pair_minimum":
        moment["pair_table_rows"][0]["pair_minimum"] += 1
    elif mutation == "slope":
        moment["outside_slope"][0] += 1
    elif mutation == "mass":
        moment["outside_pair_mass_floor"] -= 1
    elif mutation == "moment":
        row["residual_pair_moment"] += 1
    elif mutation == "moment_digest":
        row["moment_sha256"] = "0" * 64
    elif mutation == "ceiling":
        row["r14_correction"] -= 1
    elif mutation == "multiplicity":
        moment["multiplicity_cap"] = 17
    elif mutation == "sum_credit":
        row["combined_correction"] = sum(row["corrections"].values())
    elif mutation == "double_subtraction":
        row["vector_new_bound"] -= row["prior_applied_correction"]
    elif mutation == "hunter_credit":
        row["corrections"]["ELEVEN_EVENT_HUNTER"] += 1
    elif mutation == "witness":
        row["support_witness"][0][0] = 99
        # Recompute the digest: a hash-only rejection cannot pass this test.
        row["support_sha256"] = cert.digest(tuple(tuple(t) for t in row["support_witness"]))
    elif mutation == "witness_digest":
        row["support_sha256"] = "0" * 64
    elif mutation == "preserved_member":
        bad["COMPLETE_REGION_MEMBERS"][0]["final_bound"] -= 1
    elif mutation == "preserved_digest":
        bad["PRESERVED_MEMBER_BOUNDS_SHA256"] = "0" * 64
    elif mutation == "region_coverage":
        bad["COMPLETE_REGION_MEMBERS"].pop()
    elif mutation == "state_term":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = ["state:s2-10833008-s3-427140"]
    elif mutation == "tied_owner":
        bad["FINAL_STATE_MEMBER_IDS"] = [cert.TARGET_IDS[0]]
    elif mutation == "r3_bound":
        bad["FINAL_COMPLETE_R3_UB"] -= 1
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    elif mutation == "member_bound":
        member["member_new_bound"] -= 1
    elif mutation == "vectors_list":
        member["represented_vectors"] = []
    elif mutation == "meta":
        bad["TASK_STATUS"] = "FAILED"
    else:
        bad["CLASSIFIED_AGGREGATE"][0]["bound"] -= 1
    with pytest.raises(AssertionError, match=reason):
        cert.verify_result(bad)


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("pair_counter", "inclusion/exclusion"),
        ("ceil_floor", "integer ceiling"),
        ("ceil_independent", "integer ceiling"),
        ("max_sum", "max single"),
        ("applicability", "applicability"),
        ("signature", "compression signature"),
        ("support_floor", "support witness violates"),
        ("support_floor_residual", "support witness violates"),
        ("support_floor_s4", "support witness violates"),
        ("bound_arithmetic", "max single"),
        ("bad_witness", "exact support witness"),
        ("no_witness", "exact support witness"),
        ("anchor_union", "max single"),
    ],
)
def test_implementation_mutations_killed(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch, mutation: str, reason: str
) -> None:
    member = next(
        m for m in cert.six.region_members() if cert.member_id(m.counts) == cert.TARGET_IDS[0]
    )
    if mutation == "pair_counter":
        original = cert.six.residual_pair_intersection

        def wrong_pair(left: int, right: int, overlap: tuple[int, int, int, int]) -> int:
            return original(left, right, overlap) + 1

        monkeypatch.setattr(cert.six, "residual_pair_intersection", wrong_pair)
    elif mutation == "ceil_floor":

        def wrong_ceiling(value: Fraction) -> int:
            return int(value)

        monkeypatch.setattr(cert.prior, "ceil_fraction", wrong_ceiling)
    elif mutation == "ceil_independent":
        sealed = cert.prior.exact_moment_certificate

        def lowered(vector: tuple[int, ...]) -> dict[str, Any]:
            moment = sealed(vector)
            moment["correction_lower_bound"] -= 1
            return moment

        monkeypatch.setattr(cert.prior, "exact_moment_certificate", lowered)
    elif mutation == "max_sum":

        def wrong_combine(values: Mapping[str, int]) -> int:
            return sum(values.values())

        monkeypatch.setattr(cert.hunter, "combine_corrections", wrong_combine)
    elif mutation == "applicability":
        proof = cert.base.nine_event_proof()
        monkeypatch.setattr(
            cert.base, "nine_event_proof", lambda: {**proof, "event_count": member.counts[0] + 1}
        )
    elif mutation == "signature":
        calls = iter(range(1_000))

        def drifting_signature(_state: object) -> int:
            return next(calls)

        monkeypatch.setattr(cert.hunter.eleven, "compression_signature", drifting_signature)
    elif mutation == "bad_witness":
        construct = cert.hunter.r12.construct_support_witness

        def corrupted(vector: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
            support = construct(vector)
            assert support is not None
            return ((99, *support[0][1:]), *support[1:])

        monkeypatch.setattr(cert.hunter.r12, "construct_support_witness", corrupted)
    elif mutation == "no_witness":

        def none_found(_vector: tuple[int, ...]) -> None:
            return None

        monkeypatch.setattr(cert.hunter.r12, "construct_support_witness", none_found)
    elif mutation in ("support_floor_residual", "support_floor_s4"):
        costs = cert.r8.witness_costs

        def one_free(vector: tuple[int, ...], support: Any) -> tuple[int, int]:
            residual, s4 = costs(vector, support)
            return (0, s4) if mutation == "support_floor_residual" else (residual, 0)

        monkeypatch.setattr(cert.r8, "witness_costs", one_free)
    elif mutation == "bound_arithmetic":
        member_bound = cert.hunter.member_bound

        def off_by_one_bound(uncorrected: int, correction: int) -> int:
            return int(member_bound(uncorrected, correction)) - 1

        monkeypatch.setattr(cert.hunter, "member_bound", off_by_one_bound)
    elif mutation == "anchor_union":
        anchor_union = cert.hunter.anchor_union_size

        def off_by_one() -> int:
            return int(anchor_union()) + 1

        monkeypatch.setattr(cert.hunter, "anchor_union_size", off_by_one)
    else:

        def free_support(*_args: object) -> tuple[int, int]:
            return (0, 0)

        monkeypatch.setattr(cert.r8, "witness_costs", free_support)
    with pytest.raises(AssertionError, match=reason):
        cert.certify_member(
            member, cert.represented_vectors()[member.counts], result["START_STATE_BOUND"]
        )


def test_target_selection_rejects_missing_extra_and_spent_owners() -> None:
    members = cert.six.region_members()
    bounds = cert.current_member_bounds(members)
    top = max(bounds.values())
    owners = [m for m in members if bounds[m.counts] == top]
    target = owners[0]
    with pytest.raises(AssertionError, match="coverage"):
        cert.target_members(tuple(m for m in members if m != target), bounds)
    # A third, otherwise valid member tied at the maximum would be silently ignored by a pin.
    extra = next(m for m in members if bounds[m.counts] < top and m.represented_vector_count == 1)
    third = tuple(replace(m, raw_bound=top) if m == extra else m for m in members)
    with pytest.raises(AssertionError, match="target member identities"):
        cert.target_members(third, {**bounds, extra.counts: top})
    # Losing one owner from the tie is as wrong as gaining one.
    with pytest.raises(AssertionError, match="target member identities"):
        cert.target_members(members, {**bounds, target.counts: top - 1})
    # An owner whose bound no longer equals its ledger raw bound is spent, not certifiable.
    spent = tuple(replace(m, raw_bound=top + 1) if m == target else m for m in members)
    with pytest.raises(AssertionError, match="target member identities"):
        cert.target_members(spent, bounds)
    # An owner standing for several vectors would need one certificate per vector.
    wide = tuple(replace(m, represented_vector_count=2) if m == target else m for m in members)
    with pytest.raises(AssertionError, match="target member identities"):
        cert.target_members(wide, bounds)
    assert cert.target_members(members, bounds) == tuple(owners)


def test_wrong_source_without_hash_gate(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    read = Path.read_text

    def wrong_identity(path: Path, *args: Any, **kwargs: Any) -> str:
        text = read(path, *args, **kwargs)
        if path == cert.REPO_ROOT / cert.prior.RESULT_RELATIVE:
            source = json.loads(text)
            source["TASK_ID"] = "FOREIGN_SOURCE"
            return json.dumps(source)
        return text

    monkeypatch.setattr(Path, "read_text", wrong_identity)
    cert.prior_authority.cache_clear()
    try:
        with pytest.raises(AssertionError, match="source identity"):
            cert.prior_authority()
    finally:
        monkeypatch.undo()
        cert.prior_authority.cache_clear()
    assert cert.build_result() == result


def serve(authority: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def authority_source() -> dict[str, Any]:
        return authority

    return authority_source


def target_member(index: int) -> Any:
    return next(
        m for m in cert.six.region_members() if cert.member_id(m.counts) == cert.TARGET_IDS[index]
    )


def test_certify_member_rejects_missing_foreign_and_stale_inputs(result: dict[str, Any]) -> None:
    first, second = target_member(0), target_member(1)
    vectors = cert.represented_vectors()
    prior_bound = result["START_STATE_BOUND"]
    with pytest.raises(AssertionError, match="coverage or prior bound"):
        cert.certify_member(first, (), prior_bound)
    with pytest.raises(AssertionError, match="coverage or prior bound"):
        cert.certify_member(first, vectors[second.counts], prior_bound)
    with pytest.raises(AssertionError, match="coverage or prior bound"):
        cert.certify_member(first, vectors[first.counts], prior_bound - 1)
    foreign = next(
        m for m in cert.six.region_members() if cert.member_id(m.counts) not in cert.TARGET_IDS
    )
    with pytest.raises(AssertionError, match="coverage or prior bound"):
        cert.certify_member(foreign, (foreign.counts,), foreign.raw_bound)


def test_no_strict_improvement_is_rejected(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With every new floor spent, the combined credit equals the applied one: no tightening."""

    sealed = cert.prior.exact_moment_certificate

    def spent_moment(vector: tuple[int, ...]) -> dict[str, Any]:
        moment = sealed(vector)
        moment["residual_s2_lower_bound"] = 0
        moment["correction_lower_bound"] = 0
        return moment

    nine, eleven = cert.base.nine_event_proof(), cert.base.prior.eleven_event_proof()

    def spent_nine() -> dict[str, Any]:
        return {**nine, "hunter_floor": 0}

    def spent_eleven() -> dict[str, Any]:
        return {**eleven, "hunter_floor": 0}

    monkeypatch.setattr(cert.prior, "exact_moment_certificate", spent_moment)
    monkeypatch.setattr(cert.base, "nine_event_proof", spent_nine)
    monkeypatch.setattr(cert.base.prior, "eleven_event_proof", spent_eleven)
    member = target_member(0)
    with pytest.raises(AssertionError, match="max single"):
        cert.certify_member(
            member, cert.represented_vectors()[member.counts], result["START_STATE_BOUND"]
        )


def test_represented_vector_recovery_must_match_exactly(monkeypatch: pytest.MonkeyPatch) -> None:
    recover = cert.catalog.r17.represented_vectors

    def with_extra_vector(states: Any) -> dict[tuple[int, ...], tuple[tuple[int, ...], ...]]:
        recovered = dict(recover(states))
        counts = next(iter(recovered))
        recovered[counts] = (*recovered[counts], counts)
        return recovered

    monkeypatch.setattr(cert.catalog.r17, "represented_vectors", with_extra_vector)
    cert.represented_vectors.cache_clear()
    try:
        with pytest.raises(AssertionError, match="represented-vector coverage"):
            cert.represented_vectors()
    finally:
        monkeypatch.undo()
        cert.represented_vectors.cache_clear()
    assert set(cert.represented_vectors()) == {m.counts for m in map(target_member, (0, 1))}


def test_predecessor_replay_failure_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A predecessor file whose identity is intact but whose numbers fail replay is refused."""

    read = Path.read_text

    def tampered(path: Path, *args: Any, **kwargs: Any) -> str:
        text = read(path, *args, **kwargs)
        if path == cert.REPO_ROOT / cert.prior.RESULT_RELATIVE:
            source = json.loads(text)
            source["NEW_MEMBER_BOUNDS"][0] += 1
            return json.dumps(source)
        return text

    monkeypatch.setattr(Path, "read_text", tampered)
    cert.prior_authority.cache_clear()
    try:
        with pytest.raises(AssertionError, match="exact replay"):
            cert.prior_authority()
    finally:
        monkeypatch.undo()
        cert.prior_authority.cache_clear()


@pytest.mark.parametrize(
    "field,reason",
    [
        ("tail", "classified aggregate or Tail"),
        ("classified_sha", "classified aggregate or Tail"),
        ("classified_count", "classified aggregate or Tail"),
        ("aggregate", "classified aggregate or Tail"),
        ("family", "starting complete family"),
        ("state_terms", "23-State identity"),
        ("duplicate_term", "23-State identity"),
        ("extra_term", "23-State identity"),
        ("target_term", "23-State identity"),
    ],
)
def test_family_recompute_rejects_tampered_source(
    monkeypatch: pytest.MonkeyPatch, field: str, reason: str
) -> None:
    authority = copy.deepcopy(cert.prior_authority())
    terms = authority["FINAL_STATE_TERMS"]
    if field == "tail":
        authority["TAIL_BOUND"] -= 1
    elif field == "classified_sha":
        authority["CLASSIFIED_TERMS_SHA256"] = "0" * 64
    elif field == "classified_count":
        authority["CLASSIFIED_TERM_COUNT"] -= 1
    elif field == "aggregate":
        authority["CLASSIFIED_AGGREGATE"][0]["bound"] -= 1
    elif field == "family":
        authority["FINAL_FAMILY_MAX_RECOMPUTATION"]["R3_BOUND"] -= 1
    elif field == "state_terms":
        terms.pop()
    elif field == "duplicate_term":
        terms[0]["stable_id"] = terms[1]["stable_id"]
    elif field == "extra_term":
        terms.append(copy.deepcopy(terms[0]))
    else:
        for term in terms:
            if term["stable_id"] == cert.TARGET_STATE_ID:
                term["stable_id"] = "state:foreign"
    monkeypatch.setattr(cert, "prior_authority", serve(authority))
    with pytest.raises(AssertionError, match=reason):
        cert.recompute_family(355_594_890)


def test_region_bounds_reject_a_tampered_predecessor_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = copy.deepcopy(cert.prior_authority())
    authority["COMPLETE_REGION_MEMBERS"][0]["final_bound"] -= 1
    monkeypatch.setattr(cert, "prior_authority", serve(authority))
    with pytest.raises(AssertionError, match="source bounds"):
        cert.current_member_bounds(cert.six.region_members())


@pytest.mark.parametrize("field", ["vector_total", "fingerprint"])
def test_region_coverage_terms_stand_alone(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    """With the catalog replay neutralized, each coverage identity must still reject alone."""

    members = cert.six.region_members()
    earlier = cert.prior.current_member_bounds(members)
    rows = cert.prior_authority()["COMPLETE_REGION_MEMBERS"]
    first = members[0]
    if field == "vector_total":
        first = replace(first, represented_vector_count=first.represented_vector_count + 1)
    else:
        first = replace(first, raw_bound=first.raw_bound + 1)

    def earlier_bounds(_members: tuple[Any, ...]) -> dict[tuple[int, ...], int]:
        return earlier

    def stored_rows(_payload: object) -> Any:
        return rows

    monkeypatch.setattr(cert.prior, "current_member_bounds", earlier_bounds)
    monkeypatch.setattr(cert.catalog, "normalized", stored_rows)
    with pytest.raises(AssertionError, match="region coverage"):
        cert.current_member_bounds((first, *members[1:]))


def test_applied_penalty_must_match_the_state(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    rebuild = cert.catalog.rebuild_member

    def drifted(member: Any) -> Any:
        state = rebuild(member)
        return replace(
            state, applied_residual_union_penalty=state.applied_residual_union_penalty + 1
        )

    monkeypatch.setattr(cert.catalog, "rebuild_member", drifted)
    member = target_member(0)
    with pytest.raises(AssertionError, match="max single"):
        cert.certify_member(
            member, cert.represented_vectors()[member.counts], result["START_STATE_BOUND"]
        )


def test_target_state_term_must_equal_the_region_maximum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A self-consistent family whose target term is below the region maximum is refused."""

    authority = copy.deepcopy(cert.prior_authority())
    for term in authority["FINAL_STATE_TERMS"]:
        if term["stable_id"] == cert.TARGET_STATE_ID:
            term["bound"] -= 1
    terms = tuple((t["stable_id"], t["bound"]) for t in authority["FINAL_STATE_TERMS"])
    authority["FINAL_FAMILY_MAX_RECOMPUTATION"] = cert.six.tail.family_maximum(
        cert.six.sealed_tail_bound(), terms, cert.six.classified_terms()
    )
    monkeypatch.setattr(cert, "prior_authority", serve(authority))
    with pytest.raises(AssertionError, match="target State bound differs"):
        cert.build_result()


def test_stored_bytes_must_equal_the_canonical_encoding(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Semantically identical JSON with different bytes is not the stored result."""

    reformatted = tmp_path / "result.json"
    reformatted.write_text(json.dumps(result, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    assert json.loads(reformatted.read_bytes()) == json.loads(cert.RESULT_PATH.read_bytes())
    monkeypatch.setattr(cert, "RESULT_PATH", reformatted)
    with pytest.raises(AssertionError, match="bytes differ"):
        cert.verify_stored_result()


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver, portfolio search or outcome enumeration")


def test_cold_replay_without_solver_census_or_search(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(cert.r14, "owner_region", forbidden)
    monkeypatch.setattr(cert.r14, "s4_child", forbidden)
    monkeypatch.setattr(cert.r8, "support_model_status", forbidden)
    monkeypatch.setattr(cert.r8, "solver_runtime_preflight", forbidden)
    monkeypatch.setattr(cert.catalog.r24, "run_chase", forbidden)
    for module in (cert.prior, cert.base, cert.base.prior, cert.region):
        module.source_authority.cache_clear()
    cert.prior.region_authority.cache_clear()
    cert.prior.represented_vectors.cache_clear()
    cert.prior_authority.cache_clear()
    cert.represented_vectors.cache_clear()
    cert.base.region_members.cache_clear()
    cert.base.region_vectors.cache_clear()
    assert cert.build_result() == result
    assert result["R7_CENSUS_REBUILD_CALLS"] == 0
    assert result["OUTCOME_ENUMERATION_USED"] is False
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"
