"""Adopt a ten-event Hunter certificate for fifteen sealed Classified R12 vectors.

R_i = E_i minus (E_A union E_B). Select nine type-0 events and one type-1
(type-4 if type-1 is absent). Their outside incidences total 59 on 40 labels.
Smoothing d_a >= d_b+2 lowers sum C(d_x,2), so its universal minimum is 19.
Since every selected pair contains type-0, its intersection lies wholly outside
the anchors. Thus Q=e1+e2+e3, with 45>=e1>=e2>=e3>=0 and Q>=19.

A graph whose components have ranks r_i has e<=sum C(r_i+1,2)
<=C(sum r_i+1,2), so rank>=rho(e). Descending Kruskal keeps a spanning
forest in every nested threshold graph. Its ten-event tree therefore weighs
at least 9*phi0+sum_j (phi_j-phi_(j-1))*rho(e_j). Exhaust only this small
17,022-case integer relaxation. Pointwise, a tree induces at most k-1 edges
on k present residual events, proving Hunter's union bound. Attach each of
the eight omitted events as a leaf: residual intersections are nonnegative,
so the resulting eighteen-event, seventeen-edge tree retains the floor.

The sealed nine-event ledger supplies complete coverage and legal witnesses;
parameterized vectors only check identities, never establish census coverage.
Adopt TS153 and all predecessor certificates as immutable bytes. MAX existing
credits with the new floor, subtract once, MAX all three vectors per level,
and remaximize every Family term. No predecessor threshold rebuild or solver.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from functools import cache
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import (
    b649_k20_r3_classified_r12_five_level_nine_event_certificate_r1 as nine,
)
from lottolab.research import b649_k20_r3_ts153_four_state_wall_adoption_r2 as ts153

hunter, catalog, six, r24 = nine.hunter, nine.catalog, nine.six, nine.r24
r12, r6, r5 = nine.r12, nine.r6, nine.r5
dense, sparse, digest = nine.dense, nine.sparse, nine.digest
type CountVector = tuple[int, ...]
type Cells = tuple[int, int, int, int]
type Terms = tuple[tuple[str, int], ...]
Level = nine.ClassifiedLevel
TASK_ID = "B649_K20_R3_CLASSIFIED_R12_FIVE_LEVEL_TEN_EVENT_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-classified-r12-five-level-ten-event-certificate-r1"
BASE_HEAD = "b25f5b17440b8eb3e344f6c2567473081995646c"
BASE_TREE = "7ef64b1c6071c53e6612872009f07134aff4af9a"
BASE_RESULT_SHA256 = "800641b391ee23961ddbe12a1806670322063a6ee759465720d7cabe36a4f159"
AGGREGATE_DIGEST = "4cb42408f0b805ea9d7cfab99df2bf44b733ea43d5fc01612d0e246c962f1801"
TARGET_SIGNATURE_DIGEST = "8a342aa566133a49891871a7e8b8cc75e1f52297e221aeaf6cdc0d4a92a10e32"
CLASSIFIED_DIGEST = "c5e05f33c98da7ec83bd5cef319a23929600be16df7cbaad36d7a032126acbeb"
TARGET_ORDINALS = (25, 26, 27, 30, 32)
EXPECTED_BOUNDS = (354588304, 354587856, 354587408, 354586960, 354586512)
EVENT_COUNT = 10
RESIDUAL_EVENT_DEFINITION = "R_i = E_i \\ (E_A \u222a E_B)"
CORRECTION_COMBINATION = "MAX(ALL_EXISTING_VALID_CREDITS, TEN_EVENT_HUNTER); SUBTRACT_ONCE"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-classified-r12-five-level-ten-event-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE


def source_paths() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *ts153.source_paths(),
                *nine.UPSTREAM_SHA256,
                ts153.RESULT_RELATIVE,
                nine.RESULT_RELATIVE,
                str(Path(ts153.__file__).resolve().relative_to(REPO_ROOT)),
                str(Path(nine.__file__).resolve().relative_to(REPO_ROOT)),
            }
        )
    )


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


@cache
def frozen_blob(head: str, relative: str) -> bytes:
    return git_bytes("show", f"{head}:{relative}")


def verify_source_authority() -> dict[str, Any]:
    """Recheck live donor bytes, immutable object identity and checkout lineage."""
    if (
        git_bytes("show", "-s", "--format=%H %T", BASE_HEAD).decode().strip()
        != f"{BASE_HEAD} {BASE_TREE}"
        or sha256(frozen_blob(BASE_HEAD, ts153.RESULT_RELATIVE)).hexdigest() != BASE_RESULT_SHA256
    ):
        raise AssertionError("immutable BASE HEAD/TREE/result SHA authority failed")
    if subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"],
        check=False,
    ).returncode:
        raise AssertionError("checkout must descend from immutable BASE_HEAD")
    fingerprints: dict[str, str] = {}
    for relative in source_paths():
        frozen = frozen_blob(BASE_HEAD, relative)
        if (REPO_ROOT / relative).read_bytes() != frozen:
            raise AssertionError(f"immutable donor bytes changed: {relative}")
        fingerprints[relative] = sha256(frozen).hexdigest()
    return {
        "HEAD": BASE_HEAD,
        "TREE": BASE_TREE,
        "RESULT_SHA256": BASE_RESULT_SHA256,
        "donor_sha256": fingerprints,
    }


@cache
def sealed(relative: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(frozen_blob(BASE_HEAD, relative)))


def source_results() -> tuple[dict[str, Any], dict[str, Any]]:
    source, ledger = sealed(ts153.RESULT_RELATIVE), sealed(nine.RESULT_RELATIVE)
    if (
        source["TASK_ID"] != ts153.TASK_ID
        or source["TASK_STATUS"] != "SUCCESS"
        or source["FINAL_COMPLETE_R3_UB"] != 355145504
        or source["FINAL_OWNER_IDS"] != [r24.AGGREGATE_ID]
        or ledger["TASK_ID"] != nine.TASK_ID
        or ledger["TASK_STATUS"] != "SUCCESS"
        or ledger["FINAL_CLASSIFIED_TERMS_SHA256"] != source["CLASSIFIED_TERMS_SHA256"]
        or ledger["AGGREGATE_VECTORS_SHA256"] != AGGREGATE_DIGEST
    ):
        raise AssertionError("sealed TS153/Classified authority identity failed")
    return source, ledger


def aggregate_levels() -> tuple[Level, ...]:
    """Restore all 183 actual vectors from the sealed complete ledger, without census."""
    _, ledger = source_results()
    original = sealed(r24.R12_RESULT_RELATIVE)["LOSS_LEVEL_ROWS"]
    rows = ledger["COMPLETE_AGGREGATE_LEVELS"]
    levels: list[Level] = []
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    baseline = nine.canonical_baseline()
    if len(original) != 32 or [r["ordinal"] for r in original] != list(range(1, 33)):
        raise AssertionError("sealed R12 level coverage failed")
    for row in rows:
        ordinal, loss = int(row["ordinal"]), int(row["exact_loss"])
        vectors = tuple(dense(v) for v in row["represented_vectors"])
        envelopes = tuple(r6.type_count_envelope(v) for v in vectors)
        raw_bounds = tuple(baseline - loss - e.combined_pair_penalty for e in envelopes)
        credits = tuple(e.combined_pair_penalty for e in envelopes)
        final_bound = int(row["level_final_bound"])
        if (
            not 1 <= ordinal <= 32
            or row["source_level_row"] != original[ordinal - 1]
            or loss != original[ordinal - 1]["local_loss"]
            or not vectors
            or vectors != tuple(sorted(set(vectors)))
            or len(vectors) != row["represented_vector_count"]
            or len(vectors) != original[ordinal - 1]["vector_count"]
            or list(raw_bounds) != row["vector_prior_bounds"]
            or list(credits) != row["vector_prior_corrections"]
            or any(
                e.local_loss != loss or r12.local_loss(v, losses) != loss
                for v, e in zip(vectors, envelopes, strict=True)
            )
            or any(
                e.combined_pair_penalty != max(e.pair_union_penalty, e.prior_forest_penalty)
                for e in envelopes
            )
            or max(raw_bounds) != row["level_prior_bound"]
            or final_bound > max(raw_bounds)
            or (ordinal not in TARGET_ORDINALS and final_bound != max(raw_bounds))
        ):
            raise AssertionError("complete aggregate vector coverage/loss/credit failed")
        bounds = tuple(min(b, final_bound) for b in raw_bounds)
        levels.append(
            Level(ordinal, loss, vectors, bounds, tuple(baseline - loss - b for b in bounds), row)
        )
    flat = [v for level in levels for v in level.vectors]
    if (
        tuple(r.ordinal for r in levels) != tuple(i for i in range(1, 33) if i not in (1, 2, 24))
        or len(levels) != 29
        or len(flat) != len(set(flat))
        or len(flat) != 183
        or digest(tuple((r.ordinal, r.vectors) for r in levels)) != AGGREGATE_DIGEST
        or max(r.prior_bound for r in levels) != ledger["FINAL_R12_AGGREGATE_MAX"]
    ):
        raise AssertionError("complete 29-level/183-vector aggregate digest failed")
    return tuple(levels)


def vector_signature(vector: CountVector) -> tuple[object, ...]:
    envelope = r6.type_count_envelope(vector)
    raw = nine.canonical_baseline() - envelope.local_loss - envelope.combined_pair_penalty
    member = catalog.LedgerMember(vector, 1, raw, raw)
    return hunter.eleven.compression_signature(catalog.rebuild_member(member))


def target_levels(levels: tuple[Level, ...]) -> tuple[Level, ...]:
    targets = tuple(r for r in levels if r.ordinal in TARGET_ORDINALS)
    if tuple(r.ordinal for r in targets) != TARGET_ORDINALS:
        raise AssertionError("complete five target levels required")
    for k, level in enumerate(targets):
        expected: set[CountVector] = set()
        for a in range(3):
            expected.add(
                tuple({0: 9, 1: a, 4: 2 - a, 5: 7 - k, 16: k}.get(i, 0) for i in range(30))
            )
        if (
            len(level.vectors) != 3
            or set(level.vectors) != expected
            or level.loss != 6709724 + 448 * k
            or set(level.prior_corrections) != {3193400}
        ):
            raise AssertionError(
                "all fifteen target vectors and existing nine-event credit required"
            )
    actual = tuple((r.ordinal, v, vector_signature(v)) for r in targets for v in r.vectors)
    if digest(actual) != TARGET_SIGNATURE_DIGEST:
        raise AssertionError("all fifteen actual target signatures failed")
    return targets


def select_subset(v: CountVector) -> CountVector:
    if len(v) != 30 or sum(v) != 18 or min(v) < 0 or v[0] < 9 or not (v[1] or v[4]):
        raise AssertionError("ten-event submultiset applicability failed")
    mixed = 1 if v[1] else 4
    u = tuple(9 if i == 0 else int(i == mixed) for i in range(30))
    if sum(u) != EVENT_COUNT or any(a > b for a, b in zip(u, v, strict=True)):
        raise AssertionError("selected submultiset must satisfy u<=v")
    return u


def ten_event_proof() -> dict[str, Any]:
    """Independent pair recount and the complete nested threshold domain."""
    if (
        hunter.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.family_pair_overlap_ceiling() != 3
        or tuple(hunter.type_cells(i) for i in (0, 1, 4))
        != ((0, 0, 0, 6), (0, 0, 1, 5), (0, 1, 0, 5))
    ):
        raise AssertionError("Classified residual-event contract failed")
    pairs = ((0, 0), (0, 1), (0, 4))
    rows = hunter.exact_pair_rows(pairs)
    if tuple(r[:6] for r in rows) != tuple((a, b, 0, 0, 0, k) for a, b in pairs for k in range(4)):
        raise AssertionError("all twelve exact pair rows required")
    for a, b, s, x, y, z, value in rows:
        cells = (s, x, y, z)
        tickets = hunter.realize_pair(hunter.type_cells(a), hunter.type_cells(b), cells)
        if (
            six.residual_pair_intersection(a, b, cells) != value
            or hunter.outcome_count(tickets, (hunter.ANCHOR_A, hunter.ANCHOR_B)) != value
        ):
            raise AssertionError("independent exact residual pair count failed")
    phi = hunter.pair_floors(rows)
    hunter.require_safe_pair_floors(phi, rows)
    if phi != (107800, 571200, 1679692, 3428908):
        raise AssertionError("mixed pairs require their own safe common floors")
    outside = set(range(49)) - set(hunter.ANCHOR_A | hunter.ANCHOR_B)
    incidences = 9 * hunter.type_cells(0)[3] + hunter.type_cells(1)[3]
    quotient, remainder = divmod(incidences, len(outside))
    mass = (len(outside) - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)
    if (
        outside != set(hunter.CELL_LABELS[3])
        or len(outside) != 40
        or incidences != 59
        or mass != 19
        or mass != hunter.balanced_collision_mass(incidences, len(outside))
    ):
        raise AssertionError("universal balanced collision Q=19 failed")
    capacity = comb(EVENT_COUNT, 2)
    ranks = tuple(
        next(r for r in range(EVENT_COUNT) if comb(r + 1, 2) >= e) for e in range(capacity + 1)
    )
    if hunter.verify_rank_floor_algebra(EVENT_COUNT) != 46 or any(
        hunter.rank_floor(e) != r for e, r in enumerate(ranks)
    ):
        raise AssertionError("nested threshold forest-rank floor failed")
    cases: list[tuple[int, tuple[int, int, int]]] = []
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 >= mass:
                    rho = (ranks[e1], ranks[e2], ranks[e3])
                    weight = 9 * phi[0] + sum((phi[k + 1] - phi[k]) * rho[k] for k in range(3))
                    if weight != hunter.tree_weight_floor(phi, rho, EVENT_COUNT):
                        raise AssertionError("nested threshold weight identity failed")
                    cases.append((weight, (e1, e2, e3)))
    floor, edges = min(cases)
    minimum = hunter.minimum_tree_correction(phi, mass, EVENT_COUNT)
    if (
        len(cases) != 17022
        or (floor, edges) != (3750600, (19, 0, 0))
        or (minimum.correction, minimum.edge_counts, minimum.rank_floors, minimum.census_size)
        != (floor, edges, (6, 0, 0), len(cases))
    ):
        raise AssertionError("complete ten-event threshold minimum failed")
    return catalog.normalized(
        {
            "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
            "event_count": EVENT_COUNT,
            "pair_rows": rows,
            "pair_floors": phi,
            "outside_labels": sorted(outside),
            "outside_incidences": incidences,
            "balanced_frequencies": ((1, 21), (2, 19)),
            "collision_mass_floor": mass,
            "rank_floor_table": ranks,
            "all_admissible_threshold_cases": len(cases),
            "hunter_floor": floor,
            "integer_minimizer": {"edge_counts": edges, "rank_floors": minimum.rank_floors},
            "universal_argument": (
                "SMOOTHING; NESTED_GRAPH_RANK; DESCENDING_KRUSKAL; POINTWISE_HUNTER"
            ),
            "tree_extension": "8 omitted events attached as leaves with nonnegative intersections",
        }
    )


def tree_extension_proof(v: CountVector, u: CountVector) -> dict[str, Any]:
    if u != select_subset(v):
        raise AssertionError("tree extension requires the applicable ten-event subset")
    omitted = tuple(i for i in range(30) for _ in range(v[i] - u[i]))
    attachments: list[dict[str, int]] = []
    for t in omitted:
        rows = ts153.prior.verified_pair_rows((0, t))
        if not rows or min(r[6] for r in rows) < 0:
            raise AssertionError("universal attachment must have nonnegative exact intersections")
        attachments.append(
            {
                "omitted_type": t,
                "minimum_intersection": min(r[6] for r in rows),
                "legal_pair_rows": len(rows),
            }
        )
    if len(omitted) != 8 or sum(u) - 1 + len(omitted) != 17:
        raise AssertionError("ten-event tree must extend to eighteen events and seventeen edges")
    return {"subset_tree_edges": 9, "attachment_edges": attachments, "extended_tree_edges": 17}


def witness_analysis(
    v: CountVector, u: CountVector, support: tuple[tuple[int, ...], ...], proof: dict[str, Any]
) -> dict[str, Any]:
    if not hunter.r8.validate_support_assignment(v, support):
        raise AssertionError("illegal sealed support witness")
    types = tuple(i for i, n in enumerate(v) for _ in range(n))
    indices = tuple(
        j for i in range(30) for j in [k for k, t in enumerate(types) if t == i][: u[i]]
    )
    selected = tuple(support[j] for j in indices)
    phi = cast(Cells, tuple(proof["pair_floors"]))
    values = {(r[0], r[1], tuple(r[2:6])): r[6] for r in proof["pair_rows"]}
    observed = hunter.witness_analysis(u, selected, phi, values)
    tickets = tuple(frozenset(t) for t in selected)
    overlaps = {(a, b): len(tickets[a] & tickets[b]) for a, b in combinations(range(10), 2)}
    tree = cast(tuple[tuple[int, int], ...], hunter.threshold_tree(10, overlaps))
    extended = (
        *((indices[a], indices[b]) for a, b in tree),
        *((indices[0], j) for j in range(18) if j not in indices),
    )
    weight = 0
    for a, b in extended:
        cells = cast(
            Cells,
            tuple(len(set(support[a]) & set(support[b]) & set(c)) for c in hunter.CELL_LABELS),
        )
        cost = six.residual_pair_intersection(*sorted((types[a], types[b])), cells)
        if cost < 0:
            raise AssertionError("negative residual edge prevents tree extension")
        weight += cost
    outside_mass = sum(comb(sum(x in t for t in tickets), 2) for x in hunter.CELL_LABELS[3])
    if (
        len(indices) != 10
        or len(set(indices)) != 10
        or outside_mass != observed["collision_mass"]
        or outside_mass < 19
        or observed["phi_tree_weight"] < proof["hunter_floor"]
        or weight < observed["phi_tree_weight"]
        or len(extended) != 17
        or hunter.graph_rank(18, extended) != 17
    ):
        raise AssertionError("witness collision or ten-to-eighteen tree extension failed")
    return catalog.normalized(
        {
            **observed,
            "selected_event_indices": indices,
            "selected_event_types": [types[j] for j in indices],
            "subset_tree": tree,
            "extended_tree": extended,
            "extended_tree_exact_weight": weight,
        }
    )


def certify_vector(level: Level, v: CountVector, proof: dict[str, Any]) -> dict[str, Any]:
    targets = target_levels(aggregate_levels())
    if level not in targets or v not in level.vectors or proof != ten_event_proof():
        raise AssertionError("target vector or proof applicability failed")
    _, ledger = source_results()
    old_rows = [
        row
        for r in ledger["LEVEL_CERTIFICATES"]
        for row in r["vector_certificates"]
        if dense(row["counts"]) == v and row["ordinal"] == level.ordinal
    ]
    if len(old_rows) != 1:
        raise AssertionError("exact existing per-vector certificate required")
    old = old_rows[0]
    u = select_subset(v)
    envelope = r6.type_count_envelope(v)
    uncorrected = nine.canonical_baseline() - level.loss
    residual = sum(c * hunter.residual_event_size(i) for i, c in enumerate(v) if c)
    earlier = ts153.sealed_vector_bounds().get(v, ())
    prior_bound = min(
        level.prior_bounds[level.vectors.index(v)],
        int(old["vector_new_bound"]),
        *(b for _, b in earlier),
    )
    credits = {str(k): int(c) for k, c in old["corrections"].items()}
    credits["SEALED_VECTOR"] = uncorrected - prior_bound
    existing = hunter.combine_corrections(credits)
    credits["TEN_EVENT_HUNTER"] = int(proof["hunter_floor"])
    combined = hunter.combine_corrections(credits)
    bound = min(prior_bound, uncorrected - combined)
    if (
        uncorrected != hunter.anchor_union_size() + residual
        or envelope.local_loss != level.loss
        or credits["R6_PAIR"] != envelope.pair_union_penalty
        or credits["FOREST"] != envelope.prior_forest_penalty
        or credits["NINE_EVENT_HUNTER"] != 3193400
        or existing != uncorrected - prior_bound
        or combined != max(credits.values())
        or bound != uncorrected - combined
        or bound >= prior_bound
    ):
        raise AssertionError("existing credit preservation or MAX single replacement failed")
    support = tuple(tuple(int(x) for x in t) for t in old["support_witness"])
    if digest(support) != old["support_sha256"]:
        raise AssertionError("sealed support hash failed")
    return catalog.normalized(
        {
            "ordinal": level.ordinal,
            "counts": sparse(v),
            "actual_signature": vector_signature(v),
            "selected_subset_counts": sparse(u),
            "exact_loss": level.loss,
            "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
            "uncorrected_anchor_bound": uncorrected,
            "residual_event_sum": residual,
            "sealed_vector_bounds": earlier,
            "corrections": credits,
            "prior_applied_correction": existing,
            "combined_correction": combined,
            "vector_prior_bound": prior_bound,
            "vector_new_bound": bound,
            "support_witness": support,
            "support_sha256": digest(support),
            "tree_extension": tree_extension_proof(v, u),
            "witness_analysis": witness_analysis(v, u, support, proof),
        }
    )


def certify_level(
    level: Level, vectors: tuple[CountVector, ...], proof: dict[str, Any]
) -> dict[str, Any]:
    if vectors != level.vectors or len(set(vectors)) != 3 or len(vectors) != 3:
        raise AssertionError("complete three represented-vector coverage required")
    records = [certify_vector(level, v, proof) for v in vectors]
    return {
        "ordinal": level.ordinal,
        "exact_loss": level.loss,
        "represented_vector_count": len(records),
        "vector_certificates": records,
        "level_prior_bound": level.prior_bound,
        "level_new_bound": max(int(r["vector_new_bound"]) for r in records),
    }


def family_inputs() -> tuple[Terms, Terms, int]:
    source, _ = source_results()
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in source["FINAL_STATE_TERMS"])
    classified = ts153.classified_terms()
    tail = six.sealed_tail_bound()
    return states, classified, tail


def recompute_family(aggregate_bound: int) -> dict[str, Any]:
    source, _ = source_results()
    states, classified, tail = family_inputs()
    if (
        len(states) != 23
        or len(dict(states)) != 23
        or len(classified) != 56550
        or len(dict(classified)) != 56550
        or digest(classified) != source["CLASSIFIED_TERMS_SHA256"]
        or states != tuple((r["stable_id"], r["bound"]) for r in source["FINAL_STATE_TERMS"])
        or tail != source["TAIL_BOUND"]
    ):
        raise AssertionError("complete Family term coverage/identity failed")
    start = six.tail.family_maximum(tail, states, classified)
    if start != source["FINAL_FAMILY_MAX_RECOMPUTATION"]:
        raise AssertionError("source Family maximum replay failed")
    updated = nine.replace_aggregate(classified, aggregate_bound)
    explicit = tuple((k, b) for k, b in classified if k != r24.AGGREGATE_ID)
    if explicit != tuple((k, b) for k, b in updated if k != r24.AGGREGATE_ID):
        raise AssertionError("all 56549 explicit Classified terms must remain identical")
    terms = (*states, *updated, (r24.TAIL_ID, tail))
    maximum = max(b for _, b in terms)
    runner = max(b for _, b in terms if b < maximum)
    final = six.tail.family_maximum(tail, states, updated)
    if (
        len(terms) != 56574
        or len(dict(terms)) != 56574
        or final["R3_BOUND"] != maximum
        or final["OWNER_IDS"] != sorted(k for k, b in terms if b == maximum)
    ):
        raise AssertionError("independent complete Family maximum/owner recount failed")
    return {
        "states": states,
        "classified": updated,
        "tail": tail,
        "start": start,
        "final": final,
        "term_count": len(terms),
        "terms_sha256": digest(terms),
        "classified_sha256": digest(updated),
        "explicit_count": len(explicit),
        "explicit_sha256": digest(explicit),
        "explicit_max": max(b for _, b in explicit),
        "runner_up": {"bound": runner, "owner_ids": sorted(k for k, b in terms if b == runner)},
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    source, ledger = source_results()
    levels = aggregate_levels()
    targets, proof = target_levels(levels), ten_event_proof()
    certificates = [certify_level(r, r.vectors, proof) for r in targets]
    changed = {int(r["ordinal"]): int(r["level_new_bound"]) for r in certificates}
    bounds = {r.ordinal: changed.get(r.ordinal, r.prior_bound) for r in levels}
    remainder = tuple(r for r in levels if r.ordinal not in changed)
    aggregate = max(bounds.values())
    family = recompute_family(aggregate)
    if (
        tuple(changed.values()) != EXPECTED_BOUNDS
        or {r.ordinal for r in levels if bounds[r.ordinal] != r.prior_bound} != set(TARGET_ORDINALS)
        or len(remainder) != 24
        or sum(len(r.vectors) for r in remainder) != 168
        or max(r.prior_bound for r in remainder) != 354333735
        or aggregate != 354588304
        or family["explicit_count"] != 56549
        or family["explicit_max"] != 354800665
        or family["classified_sha256"] != CLASSIFIED_DIGEST
        or family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] != 354800665
        or family["tail"] != 354039277
        or family["final"]["R3_BOUND"] != 355142998
        or family["final"]["OWNER_IDS"] != [ts153.STATE_13169800]
        or family["runner_up"] != {"bound": 355141066, "owner_ids": [ts153.STATE_12695020]}
    ):
        raise AssertionError("five-level adoption/preservation/complete Family acceptance failed")
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "TASK_BRANCH": TASK_BRANCH,
            "MODEL": "最強模型",
            "REMAINING_TASK_MODEL": "最強模型",
            "MODEL_LABEL_SOURCE": "OWNER_REQUEST; NOT_A_RUNTIME_MODEL_ATTESTATION",
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "SOURCE_AUTHORITY": authority,
            "SOURCE_AUTHORITY_STATUS": "PASS_IMMUTABLE_OBJECTS_AND_DONOR_BYTES",
            "AGGREGATE_LEVEL_COVERAGE": 29,
            "AGGREGATE_VECTOR_COVERAGE": 183,
            "AGGREGATE_VECTORS_SHA256": AGGREGATE_DIGEST,
            "TARGET_LEVEL_COVERAGE": len(targets),
            "TARGET_VECTOR_COVERAGE": 15,
            "TARGET_SIGNATURE_DIGEST": digest(
                tuple((r.ordinal, v, vector_signature(v)) for r in targets for v in r.vectors)
            ),
            "SIGNATURE_DIGEST_ENCODING": (
                "sha256(repr(tuple((ordinal,dense_vector,actual_signature),...)).encode('ascii'))"
            ),
            "TEN_EVENT_PROOF": proof,
            "EXACT_PAIR_ROW_STATUS": "PASS_12_ROWS_TWO_EXACT_COUNTERS",
            "COLLISION_FLOOR_STATUS": "PASS_UNIVERSAL_BALANCED_59_INCIDENCES_40_LABELS_Q19",
            "HUNTER_THRESHOLD_STATUS": "PASS_17022_CASES_FLOOR_3750600",
            "TREE_EXTENSION_STATUS": "PASS_10_EVENT_9_EDGES_TO_18_EVENT_17_EDGES_NONNEGATIVE",
            "LEVEL_CERTIFICATES": certificates,
            "NEW_FIVE_LEVEL_BOUNDS": list(changed.values()),
            "COMPLETE_AGGREGATE_LEVELS": [
                {
                    **r.source_row,
                    "adopted_prior_bound": r.prior_bound,
                    "level_final_bound": bounds[r.ordinal],
                }
                for r in levels
            ],
            "START_AGGREGATE_MAX": ledger["FINAL_R12_AGGREGATE_MAX"],
            "NEW_AGGREGATE_MAX": aggregate,
            "PRESERVED_CLASSIFIED_REMAINDER": {
                "levels": len(remainder),
                "vectors": 168,
                "maximum": max(r.prior_bound for r in remainder),
                "sha256": digest(
                    tuple((r.ordinal, r.loss, r.vectors, r.prior_bounds) for r in remainder)
                ),
            },
            "PRESERVED_EXPLICIT_CLASSIFIED": {
                "count": family["explicit_count"],
                "maximum": family["explicit_max"],
                "sha256": family["explicit_sha256"],
            },
            "NEW_CLASSIFIED_MAX": family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
            "NEW_CLASSIFIED_DIGEST": family["classified_sha256"],
            "FINAL_CLASSIFIED_TERMS": [
                {"stable_id": k, "bound": b} for k, b in family["classified"]
            ],
            "FINAL_STATE_TERMS": source["FINAL_STATE_TERMS"],
            "TAIL_BOUND": family["tail"],
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_ONLY_SINGLE_REPLACEMENT",
            "PREDECESSOR_PRESERVATION": (
                "PASS_ALL_23_STATES_TAIL_56549_EXPLICIT_24_LEVELS_AND_EXISTING_CREDITS"
            ),
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER": family["final"]["OWNER_IDS"][0],
            "RUNNER_UP": family["runner_up"],
            "STRICT_GAIN": family["start"]["R3_BOUND"] - family["final"]["R3_BOUND"],
            "REMAINING_GAP": family["final"]["R3_BOUND"] - r24.INCUMBENT,
            "FULL_FAMILY_RECOMPUTATION": {
                "term_count": family["term_count"],
                "terms_sha256": family["terms_sha256"],
                "maximum": family["final"],
            },
            "WITNESS_SOUNDNESS_STATUS": "PASS_ALL_15_SEALED_LEGAL_SUPPORTS_AND_TREE_EXTENSIONS",
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "OUTCOME_ENUMERATION_USED": False,
            "PREDECESSOR_THRESHOLD_REBUILD_CALLS": 0,
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    if result != build_result():
        raise AssertionError("stored certificate differs from complete deterministic replay")
    return {"status": "PASS", "levels": 5, "vectors": 15, "family_terms": 56574}


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    rebuilt = build_result()
    if json.loads(stored) != rebuilt or stored != encode(rebuilt).encode():
        raise AssertionError("stored result differs from byte-for-byte replay")
    return {"status": "PASS", "levels": 5, "vectors": 15, "family_terms": 56574}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument("--write", action="store_true")
    options.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if args.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "NEW_FIVE_LEVEL_BOUNDS",
                    "FINAL_COMPLETE_R3_UB",
                    "FINAL_OWNER",
                    "STRICT_GAIN",
                    "REMAINING_GAP",
                )
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
