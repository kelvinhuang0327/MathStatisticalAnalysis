"""Join immutable TS53 and a universal 89-member residual pair-moment certificate.

Recover targets by parameters and sealed compression identities, including the
five already corrected H11 members. Recount all legal occupied pair rows using
the seven-set cell counter and independently check inclusion-exclusion. Each
pair has its own minimum and rational outside slope. For a vector, sum its pair
minima and use the least applicable slope times the balanced outside collision
mass. Smoothing integer frequencies proves that mass floor for every support.

There are eighteen residual events, so pointwise C(m,2) <= 9*(m-1)_+ for
0<=m<=18. Summing gives an integer correction ceil(S2/9). Adopt the common
minimum over the complete 99-vector cohort. Combine credits by MAX once and
maximize bounds over all represented vectors, regions and sealed Family terms.
Concrete supports check applicability; they do not prove universal floors.
No predecessor implementation, census, solver or official outcome enumeration
is rebuilt. The three imported TS53 files remain byte-exact Git donor blobs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from fractions import Fraction
from functools import cache
from hashlib import sha256
from itertools import product
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_state_13548976_fifty_three_subset_hunter_r1 as ts53

h11, prior, hunter, catalog, six, r24 = (
    ts53.h11,
    ts53.prior,
    ts53.hunter,
    ts53.catalog,
    ts53.six,
    ts53.r24,
)
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
type Pair = tuple[int, int]
type PairRow = tuple[int, int, int, int, int, int, int]
dense, sparse, digest, member_id = ts53.dense, ts53.sparse, ts53.digest, ts53.member_id
TASK_ID = "B649_K20_R3_R14_89_TS53_JOINT_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-r14-89-ts53-joint-certificate-r1"
BASE_HEAD, BASE_TREE, BASE_RESULT_SHA256 = (ts53.BASE_HEAD, ts53.BASE_TREE, ts53.BASE_RESULT_SHA256)
DONOR_HEAD = "3212e448cbe0a9a150d9705ae95dc68669a3106a"
DONOR_TREE = "ac60557c255a88e933502c8ed2ded6d84062752e"
DONOR_RESULT_SHA256 = "3c9583835d5e9f72c21d1ecf09065b1e89bda0e4bd5e18e798b9eb7645d20e31"
RESEARCH_HEAD, RESEARCH_TREE, RESEARCH_RESULT_SHA256 = (
    h11.BASE_HEAD,
    h11.BASE_TREE,
    h11.BASE_RESULT_SHA256,
)
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = six.RESULTS + "b649-k20-r3-r14-89-ts53-joint-certificate-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
DONOR_PATHS = (
    "src/lottolab/research/b649_k20_r3_state_13548976_fifty_three_subset_hunter_r1.py",
    "tests/unit/test_b649_k20_r3_state_13548976_fifty_three_subset_hunter_r1.py",
    ts53.RESULT_RELATIVE,
)
STATE_A = h11.TARGET_STATE_ID
STATE_B = prior.primary.TARGET_STATE_ID
REGION_SPECS = {STATE_A: (582, 633, 25, 30), STATE_B: (989, 1072, 64, 69)}
RESIDUAL_EVENT_DEFINITION = ts53.RESIDUAL_EVENT_DEFINITION
CORRECTION_COMBINATION = "MAX(ALL_EXISTING_VALID_CREDITS, COMMON_R14); SUBTRACT_ONCE"


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


def verify_source_authority() -> dict[str, Any]:
    """Uncached object, lineage, executing-byte and donor-blob checks."""
    ts53.verify_source_authority()
    objects: dict[str, Any] = {}
    for label, head, tree, relative, expected in (
        ("PRIMARY", BASE_HEAD, BASE_TREE, h11.RESULT_RELATIVE, BASE_RESULT_SHA256),
        ("TS53_DONOR", DONOR_HEAD, DONOR_TREE, ts53.RESULT_RELATIVE, DONOR_RESULT_SHA256),
        (
            "R14_RESEARCH",
            RESEARCH_HEAD,
            RESEARCH_TREE,
            prior.RESULT_RELATIVE,
            RESEARCH_RESULT_SHA256,
        ),
    ):
        if git_bytes("show", "-s", "--format=%H %T", head).decode().strip() != f"{head} {tree}":
            raise AssertionError("immutable HEAD/TREE authority failed")
        blob = git_bytes("show", f"{head}:{relative}")
        if sha256(blob).hexdigest() != expected:
            raise AssertionError("immutable result SHA authority failed")
        objects[label] = {"HEAD": head, "TREE": tree, "RESULT_SHA256": expected}
    for ancestor, descendant in (
        (RESEARCH_HEAD, BASE_HEAD),
        (BASE_HEAD, DONOR_HEAD),
        (BASE_HEAD, "HEAD"),
    ):
        if subprocess.run(
            ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", ancestor, descendant],
            check=False,
        ).returncode:
            raise AssertionError("incompatible immutable certificate lineage")
    if set(git_bytes("diff", "--name-only", BASE_HEAD, DONOR_HEAD).decode().splitlines()) != set(
        DONOR_PATHS
    ):
        raise AssertionError("donor must add exactly the three TS53 paths")
    blobs: dict[str, str] = {}
    for relative in DONOR_PATHS:
        frozen = git_bytes("show", f"{DONOR_HEAD}:{relative}")
        if (REPO_ROOT / relative).read_bytes() != frozen:
            raise AssertionError(f"byte-exact TS53 donor tampering: {relative}")
        blobs[relative] = git_bytes("rev-parse", f"{DONOR_HEAD}:{relative}").decode().strip()
    return {
        "objects": objects,
        "donor_blob_ids": blobs,
        "upstream_sha256": ts53.verify_source_authority()["upstream_sha256"],
    }


@cache
def source_results() -> dict[str, dict[str, Any]]:
    verify_source_authority()
    ts53.verify_stored_result()
    result = {
        name: cast(dict[str, Any], json.loads(module.RESULT_PATH.read_bytes()))
        for name, module in (("TS53", ts53), ("H11", h11), ("TS106", prior))
    }
    if result["TS53"]["FINAL_STANDALONE_COMPLETE_R3_UB"] != 355274472:
        raise AssertionError("standalone donor complete Family replay failed")
    return result


def parameter_vector(counts: dict[int, int]) -> CountVector:
    return tuple(counts.get(i, 0) for i in range(30))


def target_parameters(state_id: str) -> tuple[CountVector, ...]:
    """Complete research parameter sets, independent of current bound cutoffs."""
    if state_id == STATE_A:
        patterns = (
            {4: 2, 8: 1},
            {2: 1, 4: 2},
            {1: 1, 4: 1, 8: 1},
            {1: 1, 2: 1, 4: 1},
            {1: 2, 2: 1},
            {1: 2, 8: 1},
        )
        vectors = tuple(
            parameter_vector({0: 11, 5: 4 - k, 16: k, **p}) for k in range(5) for p in patterns
        )
    elif state_id == STATE_B:
        vectors = (
            *(
                parameter_vector({0: 9, 1: j, 4: 5 - j, 5: 3 - k, 16: k, e: 1})
                for k in range(4)
                for j in range(6)
                for e in (6, 9)
            ),
            *(
                parameter_vector({0: 10, 1: j, 4: 6 - j, 17: a, 19: 2 - a})
                for j in range(7)
                for a in range(3)
            ),
        )
    else:
        raise AssertionError("unknown R14 target State")
    if len(vectors) != len(set(vectors)) or any(sum(v) != 18 or min(v) < 0 for v in vectors):
        raise AssertionError("complete target parameter identity failed")
    return tuple(sorted(vectors))


def expected_aliases(state_id: str) -> tuple[tuple[CountVector, CountVector], ...]:
    if state_id == STATE_A:
        pairs = (
            (
                parameter_vector({0: 11, 5: 4 - k, 16: k, 2: 1, 4: 2}),
                parameter_vector({0: 11, 5: 4 - k, 16: k, 1: 2, 8: 1}),
            )
            for k in range(5)
        )
    elif state_id == STATE_B:
        pairs = (
            *(
                (
                    parameter_vector({0: 9, 1: 2, 4: 3, 5: 3 - k, 16: k, 6: 1}),
                    parameter_vector({0: 9, 1: 3, 4: 2, 5: 3 - k, 16: k, 9: 1}),
                )
                for k in range(4)
            ),
            (
                parameter_vector({0: 10, 1: 2, 4: 4, 17: 2}),
                parameter_vector({0: 10, 1: 4, 4: 2, 19: 2}),
            ),
        )
    else:
        raise AssertionError("unknown alias State")
    return tuple(sorted((min(a, b), max(a, b)) for a, b in pairs))


def region_rows(state_id: str) -> list[dict[str, Any]]:
    if state_id == STATE_A:
        return cast(list[dict[str, Any]], source_results()["H11"]["COMPLETE_REGION_MEMBERS"])
    if state_id == STATE_B:
        return cast(
            list[dict[str, Any]],
            next(
                r["complete_region_members"]
                for r in source_results()["TS106"]["REGIONS"]
                if r["state_id"] == state_id
            ),
        )
    raise AssertionError("unknown complete region")


@cache
def region_members(state_id: str) -> tuple[LedgerMember, ...]:
    rows = region_rows(state_id)
    members = tuple(
        LedgerMember(
            dense(r["witness_counts"]),
            int(r["represented_vector_count"]),
            int(r["raw_bound"]),
            int(r["final_bound"]),
        )
        for r in rows
    )
    mc, vc, _, _ = REGION_SPECS[state_id]
    terms = {r["stable_id"]: r["bound"] for r in source_results()["TS53"]["FINAL_STATE_TERMS"]}
    if (
        len(members) != mc
        or len({m.counts for m in members}) != mc
        or sum(m.represented_vector_count for m in members) != vc
        or max(m.final_bound for m in members) != terms[state_id]
        or any(m.final_bound > m.raw_bound or m.represented_vector_count < 1 for m in members)
    ):
        raise AssertionError("complete latest region identity failed")
    return members


@cache
def represented_vectors(state_id: str) -> dict[CountVector, tuple[CountVector, ...]]:
    members = region_members(state_id)
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in members))
    flat = [v for vs in recovered.values() for v in vs]
    if (
        set(recovered) != {m.counts for m in members}
        or len(flat) != len(set(flat))
        or len(flat) != REGION_SPECS[state_id][1]
    ):
        raise AssertionError("complete represented-vector region coverage failed")
    for m, row in zip(members, region_rows(state_id), strict=True):
        vs = recovered[m.counts]
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(m))
        if (
            len(vs) != m.represented_vector_count
            or vs != tuple(sorted(vs))
            or min(vs) != m.counts
            or row["member_id"] != member_id(m.counts)
            or row["represented_vectors"] != [sparse(v) for v in vs]
            or (
                state_id == STATE_B
                and row["compression_signature"] != catalog.normalized(signature)
            )
        ):
            raise AssertionError("sealed canonical/compression identity failed")
        for v in vs:
            state = catalog.rebuild_member(replace(m, counts=v, represented_vector_count=1))
            if (
                len(v) != 30
                or sum(v) != 18
                or min(v) < 0
                or hunter.eleven.compression_signature(state) != signature
                or hunter.r14.raw_bound(state) != m.raw_bound
            ):
                raise AssertionError("represented-vector compression signature failed")
    # H11 seals all canonical/represented identities as a whole-list digest;
    # TS106 additionally carries individual normalized signature rows.
    if (
        state_id == STATE_A
        and digest(tuple((m.counts, recovered[m.counts]) for m in members))
        != source_results()["H11"]["ALL_REPRESENTED_VECTORS_SHA256"]
    ):
        raise AssertionError("sealed complete compression identities failed")
    return recovered


def target_members(state_id: str) -> tuple[LedgerMember, ...]:
    members, vectors = region_members(state_id), represented_vectors(state_id)
    parameters = set(target_parameters(state_id))
    targets = tuple(m for m in members if parameters.intersection(vectors[m.counts]))
    actual = {v for m in targets for v in vectors[m.counts]}
    aliases = tuple(sorted(vectors[m.counts] for m in targets if len(vectors[m.counts]) > 1))
    if (
        actual != parameters
        or (len(targets), len(actual)) != REGION_SPECS[state_id][2:]
        or aliases != expected_aliases(state_id)
    ):
        raise AssertionError("exact R14 target/alias coverage failed")
    if state_id == STATE_A:
        adopted = {
            dense(r["witness_counts"]) for r in source_results()["H11"]["MEMBER_CERTIFICATES"]
        }
        if len(adopted) != 5 or not adopted <= {m.counts for m in targets}:
            raise AssertionError("all five adopted H11 members must be R14 targets")
    return targets


@cache
def exact_pair_rows() -> tuple[PairRow, ...]:
    vectors = tuple(v for sid in REGION_SPECS for v in target_parameters(sid))
    pairs = hunter.occupied_type_pairs(vectors)
    rows: list[PairRow] = []
    for pair in pairs:
        left, right = (hunter.type_cells(i) for i in pair)
        overlaps = tuple(
            c
            for c in product(
                *(
                    range(max(0, a + b - len(labels)), min(a, b) + 1)
                    for a, b, labels in zip(left, right, hunter.CELL_LABELS, strict=True)
                )
            )
            if sum(c) <= hunter.family_pair_overlap_ceiling()
        )
        for overlap in overlaps:
            cells = (int(overlap[0]), int(overlap[1]), int(overlap[2]), int(overlap[3]))
            tickets = hunter.realize_pair(left, right, cells)
            value = hunter.outcome_count(tickets, (hunter.ANCHOR_A, hunter.ANCHOR_B))
            if value != six.residual_pair_intersection(*pair, cells) or value < 0:
                raise AssertionError("exact residual intersection recount failed")
            rows.append((*pair, *cells, value))
    if len(pairs) != 44 or len(rows) != 264 or len(set(rows)) != 264:
        raise AssertionError("44 occupied pairs / 264 legal rows required")
    if tuple(rows) != hunter.exact_pair_rows(pairs):
        raise AssertionError("complete independent residual pair rows differ")
    return tuple(rows)


def require_safe_pair_floor(
    pair: Pair, floor: int, slope: Fraction, rows: tuple[PairRow, ...]
) -> None:
    relevant = tuple(r for r in rows if r[:2] == pair)
    if not relevant or floor < 0 or slope < 0 or any(r[6] < floor + slope * r[5] for r in relevant):
        raise AssertionError("unsafe type-specific pair floor/outside slope")


@cache
def pair_floors() -> dict[Pair, tuple[int, Fraction]]:
    rows = exact_pair_rows()
    floors: dict[Pair, tuple[int, Fraction]] = {}
    for pair in sorted({r[:2] for r in rows}):
        relevant = tuple(r for r in rows if r[:2] == pair)
        floor = min(r[6] for r in relevant)
        slope = min(Fraction(r[6] - floor, r[5]) for r in relevant if r[5])
        require_safe_pair_floor(pair, floor, slope, rows)
        floors[pair] = floor, slope
    return floors


def ceiling(numerator: int, denominator: int) -> int:
    if numerator < 0 or denominator <= 0:
        raise ValueError("ceiling requires nonnegative numerator and positive denominator")
    return -(-numerator // denominator)


def vector_moment(v: CountVector) -> dict[str, Any]:
    if len(v) != 30 or sum(v) != 18 or any(type(c) is not int or c < 0 for c in v):
        raise AssertionError("eighteen residual events required")
    pairs: tuple[Pair, ...] = six.occupied_type_pairs(v)
    floors = pair_floors()
    minimum = sum((comb(v[a], 2) if a == b else v[a] * v[b]) * floors[a, b][0] for a, b in pairs)
    slope = min(floors[p][1] for p in pairs)
    incidences = sum(c * hunter.type_cells(i)[3] for i, c in enumerate(v))
    labels = len(hunter.CELL_LABELS[3])
    q, r = divmod(incidences, labels)
    mass = (labels - r) * comb(q, 2) + r * comb(q + 1, 2)
    floor = minimum + ceiling(slope.numerator * mass, slope.denominator)
    independent = hunter.r14.moment_certificate(v)
    if (
        floor != independent["residual_s2_lower_bound"]
        or minimum != independent["pair_minimum_sum"]
        or mass != independent["outside_pair_mass_floor"]
        or [slope.numerator, slope.denominator] != independent["outside_slope"]
    ):
        raise AssertionError("independent exact vector pair-moment replay failed")
    return {
        "counts": sparse(v),
        "pair_minimum_sum": minimum,
        "outside_slope": [slope.numerator, slope.denominator],
        "outside_incidence_total": incidences,
        "outside_label_count": labels,
        "outside_collision_floor": mass,
        "residual_s2_floor": floor,
    }


def multiplicity_proof(cap: int = 18) -> dict[str, Any]:
    # Cap18 follows from the number of events alone. A smaller cap requires
    # an additional theorem; its proposed dual fails on the allowed m=18 bin.
    if cap != hunter.RESIDUAL_EVENT_COUNT or cap != 18:
        raise AssertionError("cap17 rejected: m=18 gives 306 > 17*17=289")
    rows = [[m, comb(m, 2), 9 * max(m - 1, 0)] for m in range(19)]
    if any(a > b for _, a, b in rows):
        raise AssertionError("universal multiplicity dual failed")
    return {
        "cap": cap,
        "event_count": hunter.RESIDUAL_EVENT_COUNT,
        "dual": [1, 9],
        "bin_checks": rows,
        "cap17_counterexample": {"m": 18, "lhs": 306, "rhs": 289},
    }


@cache
def universal_proof() -> dict[str, Any]:
    for sid in REGION_SPECS:
        target_members(sid)
    moments = [vector_moment(v) for sid in REGION_SPECS for v in target_parameters(sid)]
    common = min(r["residual_s2_floor"] for r in moments)
    correction = ceiling(common, 9)
    if len(moments) != 99 or common != 44130478 or correction != 4903387:
        raise AssertionError("recomputed common S2/correction floor failed")
    return {
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "pair_rows": catalog.normalized(exact_pair_rows()),
        "occupied_type_pairs": [list(p) for p in pair_floors()],
        "pair_floors": [
            {"types": list(p), "minimum": f, "outside_slope": [s.numerator, s.denominator]}
            for p, (f, s) in pair_floors().items()
        ],
        "vector_moments": moments,
        "common_s2_floor": common,
        "multiplicity": multiplicity_proof(),
        "correction_floor": correction,
    }


@cache
def carried_supports() -> dict[CountVector, tuple[tuple[tuple[int, ...], ...], ...]]:
    found: dict[CountVector, list[tuple[tuple[int, ...], ...]]] = {}

    def is_sparse_pair(value: Any) -> bool:
        if not isinstance(value, list):
            return False
        pair = cast(list[Any], value)
        return (
            len(pair) == 2
            and type(pair[0]) is int
            and 0 <= pair[0] < 30
            and type(pair[1]) is int
            and pair[1] >= 0
        )

    def decode_counts(value: Any) -> CountVector | None:
        # Earlier schemas contain both dense vectors and unrelated count
        # arrays. Only a complete eighteen-event vector establishes context.
        if not isinstance(value, list):
            return None
        values = cast(list[Any], value)
        if len(values) == 30 and all(type(c) is int and c >= 0 for c in values):
            decoded = tuple(int(c) for c in values)
        elif values and all(is_sparse_pair(p) for p in values):
            decoded = dense(values)
        else:
            return None
        return decoded if sum(decoded) == 18 else None

    def visit(value: Any, vector: CountVector | None = None) -> None:
        if isinstance(value, dict):
            row = cast(dict[str, Any], value)
            if "counts" in row:
                vector = decode_counts(row["counts"])
            elif "witness_counts" in row:
                vector = decode_counts(row["witness_counts"])
            if vector is not None and "support_witness" in row:
                support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
                if support not in found.setdefault(vector, []):
                    found[vector].append(support)
            for child in row.values():
                visit(child, vector)
        elif isinstance(value, list):
            for child in cast(list[Any], value):
                visit(child, vector)

    for p in ts53.source_paths():
        if p.endswith(".json"):
            visit(json.loads((REPO_ROOT / p).read_bytes()))
    return {v: tuple(s) for v, s in found.items()}


def certify_vector(member: LedgerMember, v: CountVector) -> dict[str, Any]:
    state = catalog.rebuild_member(replace(member, counts=v, represented_vector_count=1))
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual = sum(c * hunter.residual_event_size(i) for i, c in enumerate(v))
    prior_bound = min((member.final_bound, *ts53.sealed_vector_bounds().get(v, ())))
    credits = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "SEALED_MEMBER": uncorrected - member.final_bound,
        "SEALED_VECTOR": uncorrected - prior_bound,
    }
    current = hunter.combine_corrections(credits)
    credits["COMMON_R14"] = int(universal_proof()["correction_floor"])
    new = hunter.combine_corrections(credits)
    bound = min(prior_bound, uncorrected - new)
    if (
        uncorrected != hunter.anchor_union_size() + residual
        or min(credits.values()) < 0
        or current != uncorrected - prior_bound
        or new != max(credits.values())
        or bound > member.final_bound
    ):
        raise AssertionError("MAX-only credit replacement/preservation failed")
    supports = carried_supports().get(v, ())
    for support in supports:
        if not hunter.r8.validate_support_assignment(v, support):
            raise AssertionError("applicable carried legal witness is unsound")
    support = prior.legal_support(v)
    return {
        "counts": sparse(v),
        "vector_id": member_id(v),
        "uncorrected_bound": uncorrected,
        "residual_event_sum": residual,
        "vector_prior_bound": prior_bound,
        "corrections": credits,
        "current_credit": current,
        "new_credit": new,
        "vector_new_bound": bound,
        "support_witness": catalog.normalized(support),
        "support_sha256": digest(support),
        "preserved_support_sha256": [digest(s) for s in supports],
    }


def certify_member(
    state_id: str, member: LedgerMember, vectors: tuple[CountVector, ...]
) -> dict[str, Any]:
    if (
        member not in target_members(state_id)
        or vectors != represented_vectors(state_id)[member.counts]
    ):
        raise AssertionError("complete target represented-vector coverage failed")
    rows = [certify_vector(member, v) for v in vectors]
    return {
        "member_id": member_id(member.counts),
        "witness_counts": sparse(member.counts),
        "represented_vectors": [sparse(v) for v in vectors],
        "represented_vector_count": len(vectors),
        "member_prior_bound": member.final_bound,
        "member_new_bound": max(r["vector_new_bound"] for r in rows),
        "member_raw_bound": member.raw_bound,
        "vector_certificates": rows,
    }


def region_certificate(state_id: str) -> dict[str, Any]:
    members, vectors = region_members(state_id), represented_vectors(state_id)
    targets = target_members(state_id)
    records = [certify_member(state_id, m, vectors[m.counts]) for m in targets]
    updates = {dense(r["witness_counts"]): r["member_new_bound"] for r in records}
    bounds = {m.counts: updates.get(m.counts, m.final_bound) for m in members}
    remainder = tuple(m for m in members if m.counts not in updates)
    if any(bounds[m.counts] != m.final_bound for m in remainder):
        raise AssertionError("untouched non-target bounds changed")
    return {
        "state_id": state_id,
        "region_member_count": len(members),
        "region_vector_count": sum(len(v) for v in vectors.values()),
        "prior_region_sha256": catalog.region_fingerprint(members),
        "target_member_count": len(records),
        "target_vector_count": sum(r["represented_vector_count"] for r in records),
        "compression_aliases": [[sparse(v) for v in pair] for pair in expected_aliases(state_id)],
        "member_certificates": records,
        "preserved_member_count": len(remainder),
        "preserved_vector_count": sum(len(vectors[m.counts]) for m in remainder),
        "preserved_bounds_sha256": digest(tuple((m.counts, bounds[m.counts]) for m in remainder)),
        "complete_region_members": [
            {**row, "prior_bound": m.final_bound, "final_bound": bounds[m.counts]}
            for m, row in zip(members, region_rows(state_id), strict=True)
        ],
        "new_state_bound": max(bounds.values()),
    }


def recompute_family(regions: list[dict[str, Any]]) -> dict[str, Any]:
    source = source_results()["TS53"]
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in source["FINAL_STATE_TERMS"])
    classified = tuple(
        (str(r["stable_id"]), int(r["bound"]))
        for r in prior.source_results()["JOINT"]["FINAL_CLASSIFIED_TERMS"]
    )
    tail = six.sealed_tail_bound()
    start = six.tail.family_maximum(tail, states, classified)
    replacements = {str(r["state_id"]): int(r["new_state_bound"]) for r in regions}
    if (
        len(states) != 23
        or len(dict(states)) != 23
        or not set(REGION_SPECS) <= dict(states).keys()
        or set(replacements) != set(REGION_SPECS)
        or len(regions) != 2
        or len(classified) != 56550
        or len(dict(classified)) != 56550
        or digest(classified) != source["CLASSIFIED_TERMS_SHA256"]
        or max(b for _, b in classified) != 355145504
        or tail != 354039277
        or start != source["FINAL_FAMILY_MAX_RECOMPUTATION"]
        or start["R3_BOUND"] != 355274472
    ):
        raise AssertionError("complete 23-State/Classified/Tail recomputation failed")
    updated = tuple((k, replacements.get(k, b)) for k, b in states)
    final = six.tail.family_maximum(tail, updated, classified)
    terms = (*updated, *classified, (r24.TAIL_ID, tail))
    maximum = max(b for _, b in terms)
    runner = max(b for _, b in terms if b < maximum)
    return {
        "start": start,
        "final": final,
        "start_states": states,
        "states": updated,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
        "classified_max": max(b for _, b in classified),
        "tail": tail,
        "runner_up": {"bound": runner, "owner_ids": [k for k, b in terms if b == runner]},
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    proof = universal_proof()
    regions = [region_certificate(sid) for sid in REGION_SPECS]
    family = recompute_family(regions)
    states = dict(family["states"])
    if (
        states[STATE_A] != 355235139
        or states[STATE_B] != 355243700
        or states[ts53.TARGET_STATE_ID] != 355116818
        or states[prior.h0.joint.TARGET_STATE_ID] != 355243049
        or family["final"]["R3_BOUND"] != 355243700
        or family["final"]["OWNER_IDS"] != [STATE_B]
        or family["runner_up"] != {"bound": 355243049, "owner_ids": ["state:s2-12695020-s3-735532"]}
    ):
        raise AssertionError("recomputed State/Family owner/runner-up acceptance failed")
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "TASK_BRANCH": TASK_BRANCH,
            "MODEL": "最強模型",
            "REMAINING_TASK_MODEL": "最強模型",
            "MODEL_LABEL_SOURCE": "OWNER_REQUEST; NOT_A_RUNTIME_MODEL_ATTESTATION",
            "PRIMARY_BASE_HEAD": BASE_HEAD,
            "PRIMARY_BASE_TREE": BASE_TREE,
            "DONOR_HEAD": DONOR_HEAD,
            "SOURCE_AUTHORITY": authority,
            "SOURCE_AUTHORITY_STATUS": "PASS_OBJECTS_LINEAGE_AND_EXECUTING_BYTES",
            "DONOR_BYTE_IDENTITY_STATUS": "PASS_ALL_THREE_GIT_BLOBS",
            "TS53_PRESERVATION_STATUS": "PASS_BYTE_EXACT_CERTIFICATE_AND_COMPLETE_REPLAY",
            "TS53_CERTIFICATE_SHA256": sha256(ts53.RESULT_PATH.read_bytes()).hexdigest(),
            "TS53_UPDATED_REGION_SHA256": source_results()["TS53"][
                "COMPLETE_UPDATED_BOUNDS_SHA256"
            ],
            "TS53_TARGET_MEMBER_IDS": [
                r["member_id"] for r in source_results()["TS53"]["MEMBER_CERTIFICATES"]
            ],
            "R14_PROOF": proof,
            "REGIONS": regions,
            "R14_89_MEMBER_COVERAGE": sum(r["target_member_count"] for r in regions),
            "R14_99_VECTOR_COVERAGE": sum(r["target_vector_count"] for r in regions),
            "R14_COMPRESSION_ALIAS_STATUS": "PASS_ALL_TEN_PARAMETERS_AND_SEALED_SIGNATURES",
            "EXACT_PAIR_ROW_STATUS": "PASS_44_OCCUPIED_PAIRS_264_RECOUNTED_LEGAL_ROWS",
            "COMMON_S2_FLOOR_STATUS": proof["common_s2_floor"],
            "MULTIPLICITY_CAP_STATUS": "PASS_CAP18_ALL_19_BINS_CAP17_REJECTED",
            "R14_CORRECTION_FLOOR": proof["correction_floor"],
            "H11_CREDIT_PRESERVATION": "PASS_ALL_FIVE_MEMBERS_SIX_VECTORS_INCLUDED_MAX_ONLY",
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SUBTRACT_ONCE_MEMBER_MAX",
            "UNTOUCHED_BOUNDS_STATUS": "PASS_ALL_NON_TARGET_REGION_BOUNDS_AND_OTHER_STATES",
            "NEW_STATE_12692531_UB": states[STATE_A],
            "NEW_STATE_13169800_UB": states[STATE_B],
            "NEW_STATE_13548976_UB": states[ts53.TARGET_STATE_ID],
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_states"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["states"]],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "RUNNER_UP": family["runner_up"],
            "STRICT_GAIN": family["start"]["R3_BOUND"] - family["final"]["R3_BOUND"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": family["final"]["R3_BOUND"] - r24.INCUMBENT,
            "FULL_23_STATE_RECOMPUTATION": "PASS_ALL_23_UNIQUE_TERMS",
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "CLASSIFIED_MAX": family["classified_max"],
            "TAIL_BOUND": family["tail"],
            "CLASSIFIED_RECOMPUTATION": "PASS_ALL_56550_TERMS",
            "TAIL_RECOMPUTATION": "PASS_SEALED_FORMULA_SINGLE_CORRECTION",
            "WITNESS_SOUNDNESS_STATUS": (
                "PASS_99_LEGAL_SUPPORTS_ALL_APPLICABLE_CARRIED_SUPPORTS_AND_TS53"
            ),
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "R14_RESEARCH_AUTHORITY_KIND": "TS106_CONTEXT; NO_COMMITTED_89_MEMBER_R14_DONOR",
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_source_authority()
    if encode(result) != encode(build_result()):
        raise AssertionError("stored result differs from complete exact joint certificate replay")
    return {
        "status": "PASS",
        "members": 89,
        "vectors": 99,
        "aliases": 10,
        "occupied_pairs": 44,
        "pair_rows": 264,
        "state_terms": 23,
        "classified_terms": 56550,
        "complete_r3": result["FINAL_COMPLETE_R3_UB"],
    }


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    status = verify_result(cast(dict[str, Any], json.loads(stored)))
    if stored != encode(build_result()).encode():
        raise AssertionError("stored joint result bytes differ from deterministic replay")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    if options.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if options.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "R14_89_MEMBER_COVERAGE",
        "R14_99_VECTOR_COVERAGE",
        "R14_CORRECTION_FLOOR",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "STRICT_GAIN",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
