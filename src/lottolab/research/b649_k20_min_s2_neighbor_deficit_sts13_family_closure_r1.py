"""Joint neighbor-deficit and pointed STS(13) closure of the minimum-S2 Family.

Authorities. Two sealed sibling commits share the parent a1e5dd3c and each
adds only its own three files. PRIMARY (209e7d3c) is the universal
neighbor-deficit certificate: q_v caps, the weighted S4 floor F, 11 cap
reductions, 24 impossible t terms, special S4 floors at their original t,
S5 degree caps, every sealed cap authority and witness, and the
197-profile frontier. It leaves the complete 4844-profile Family at
313263916, owned only by STS13=55555555555511111100 at its cap t=270.
DONOR (3b1f7e8b) proves for EVERY legal t=270 presentation of that profile
that the overlap graph is K12+(K8-e) whose twenty high triples are a
point-deleted STS(13) with a unique completion and converse. By the
published two-class classification and all 26 pointed deletions, the
deleted design has P>=4 Pasch six-sets (cyclic 13x7; non-cyclic 9x4, 4x5).
Inclusion-exclusion of the official events stops at seven winners with
S4=331240, S5=6860, S6=7P, S7=0: Union=313263916-7P<=313263888 at t=270.

Composition. Both siblings are replayed byte-for-byte from their pinned
sources and their STS13 base envelopes have one digest. At t=270 the
primary bound is the fifth Bonferroni sum with S4 and S5 at their exact
universal values, i.e. the donor's S1-S2+S3-S4+S5=313263916. The joint
t=270 bound is MIN(primary, donor)=313263888. The S6 credit enters once,
inside the donor's exact identity; it is never subtracted from another
bound, never used at t<270 and never used on another profile. The 248
lower t keep the primary bounds, each at most the donor's retained base
term. All other 4843 profile bounds, caps, floors, S5 caps, witnesses and
the frontier are the primary's verbatim, and coverage is rechecked by the
sealed partition. Both legal STS13 witnesses keep their exact unions
(313263867 and 313263888), so the incumbent attains the Family maximum
with gap 0. The claim is optimality relative to the sealed minimum-S2
Family authority, not global optimality of the K20 search. No solver,
R25/R30 or census runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_shared_neighbor_deficit_certificate_r1 as primary
from . import b649_k20_min_s2_sts13_pointed_pasch_certificate_r1 as donor
from .b649_k20_min_s2_split_cap_current_owner_chase_r1 import Row

integer, object_row, rows, digest = (
    primary.integer,
    primary.object_row,
    primary.rows,
    primary.digest,
)
previous, integration, chase = primary.previous, primary.integration, primary.chase
TASK_ID = "B649_K20_MIN_S2_NEIGHBOR_DEFICIT_STS13_FAMILY_CLOSURE_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-neighbor-deficit-sts13-family-closure-r1"
COMMON_PARENT = "a1e5dd3cc32a07f6f5c6e70482578aeb6c950aaf"
PRIMARY_HEAD = "209e7d3c658f9e96cdd04828c1f4d4ba14404038"
PRIMARY_TREE = "6e01b7bbca634c68f7bc175f74ffaf7ff7c3b529"
PRIMARY_RESULT_SHA256 = "4e7b8163846f6b87c561fc7a96f12a18c46636ee66c9d0dfdd0b24eb1ec08dfa"
DONOR_HEAD = "3b1f7e8b61bcbdf8d9f3436fedfa2e3d37e15225"
DONOR_TREE = "7974d7408784ca18c6ac1297305f91e183c4e7aa"
DONOR_RESULT_SHA256 = "b1a113c9cc179a9ec50761f162af3c367ec433465f3398cd5b358c9ea087c67d"
ROOT = chase.ROOT
RESULT_DIRECTORY = donor.RESULT_DIRECTORY
PRIMARY_SOURCE = "src/lottolab/research/b649_k20_min_s2_shared_neighbor_deficit_certificate_r1.py"
PRIMARY_RESULT = f"{RESULT_DIRECTORY}/{primary.RESULT_FILENAME}"
DONOR_SOURCE = "src/lottolab/research/b649_k20_min_s2_sts13_pointed_pasch_certificate_r1.py"
DONOR_RESULT = f"{RESULT_DIRECTORY}/{donor.RESULT_FILENAME}"
SIBLINGS = {
    PRIMARY_HEAD: (
        PRIMARY_TREE,
        (
            PRIMARY_SOURCE,
            "tests/unit/test_b649_k20_min_s2_shared_neighbor_deficit_certificate_r1.py",
            PRIMARY_RESULT,
        ),
    ),
    DONOR_HEAD: (
        DONOR_TREE,
        (
            DONOR_SOURCE,
            "tests/unit/test_b649_k20_min_s2_sts13_pointed_pasch_certificate_r1.py",
            DONOR_RESULT,
        ),
    ),
}
RESULT_FILENAME = "b649-k20-min-s2-neighbor-deficit-sts13-family-closure-r1-result.json"
RESULT_PATH = ROOT / RESULT_DIRECTORY / RESULT_FILENAME
PROFILE = donor.PROFILE
CAP = donor.CAP
INCUMBENT = 313263888
START_BOUND = 313263916
DONOR_LOWER_T_MAX = 313261872
CLASSES = ("CYCLIC", "NON_CYCLIC")
PASCH_DISTRIBUTION = {"CYCLIC": {7: 13}, "NON_CYCLIC": {4: 9, 5: 4}}
EXACT_S4, EXACT_S5, EXACT_S7 = 331240, 6860, 0
TERM_COLUMNS = [*primary.TERM_COLUMNS, "POINTED_PASCH_T270_BOUND", "JOINT_BOUND"]
type Blocks = tuple[tuple[int, ...], ...]
type JointTerm = tuple[
    int, int, int, int | None, int, int, int, int, int, int, int, int, int, int | None, int
]


@dataclass(frozen=True)
class Authority:
    neighbor: primary.Authority
    pasch: donor.Authority
    neighbor_result: dict[str, object]
    pasch_result: dict[str, object]
    provenance: dict[str, str]


def plain(value: object) -> object:
    """The JSON value a sealed result stores (tuples become lists)."""
    return json.loads(json.dumps(value))


def blocks(value: object) -> Blocks:
    return tuple(tuple(integer(v) for v in rows(b)) for b in rows(value))


def sibling_provenance() -> dict[str, str]:
    """Exact trees, one common parent, additive-only change sets, byte-identical files."""
    git = chase.git
    if git("merge-base", PRIMARY_HEAD, DONOR_HEAD).decode().strip() != COMMON_PARENT:
        raise AssertionError("siblings do not share the expected common authority")
    provenance: dict[str, str] = {}
    for head, (tree, files) in SIBLINGS.items():
        if git("rev-parse", f"{head}^{{tree}}").decode().strip() != tree:
            raise AssertionError("immutable sibling tree mismatch")
        if git("rev-list", "--parents", "-n", "1", head).decode().split() != [head, COMMON_PARENT]:
            raise AssertionError("sibling does not derive from the common authority")
        changed = git("diff-tree", "-r", "--name-status", COMMON_PARENT, head).decode()
        if sorted(changed.splitlines()) != sorted(f"A\t{path}" for path in files):
            raise AssertionError("sibling change set is not its three additive files")
        for relative in files:
            blob = git("show", f"{head}:{relative}")
            if (ROOT / relative).read_bytes() != blob:
                raise AssertionError(f"immutable sibling bytes differ: {relative}")
            provenance[relative] = hashlib.sha256(blob).hexdigest()
    if (provenance[PRIMARY_RESULT], provenance[DONOR_RESULT]) != (
        PRIMARY_RESULT_SHA256,
        DONOR_RESULT_SHA256,
    ):
        raise AssertionError("immutable sibling result digest mismatch")
    for module, relative in ((primary.__file__, PRIMARY_SOURCE), (donor.__file__, DONOR_SOURCE)):
        if Path(module or "").resolve() != (ROOT / relative).resolve():
            raise AssertionError("executed sibling module is not the pinned source")
    if (
        donor.ROOT.resolve() != ROOT.resolve()
        or {primary.BASE_HEAD, donor.BASE_HEAD} != {COMMON_PARENT}
        or primary.BASE_TREE != donor.BASE_TREE
        or primary.BASE_RESULT_SHA256 != donor.BASE_RESULT_SHA256
    ):
        raise AssertionError("siblings consume different base authorities")
    return dict(sorted(provenance.items()))


@cache
def load_authority() -> Authority:
    provenance = sibling_provenance()
    neighbor = primary.load_authority()
    replayed = integration.render(primary.compute_result(neighbor)).encode("utf-8")
    if replayed != (ROOT / PRIMARY_RESULT).read_bytes():
        raise AssertionError("primary neighbor-deficit executable replay differs")
    pasch = donor.load_authority()
    pointed = donor.render(donor.compute_result(pasch))
    if pointed != (ROOT / DONOR_RESULT).read_bytes():
        raise AssertionError("donor pointed STS13 executable replay differs")
    if digest(neighbor.sealed) != digest(pasch.sealed):
        raise AssertionError("siblings consume different sealed base results")
    return Authority(
        neighbor,
        pasch,
        object_row(json.loads(replayed)),
        object_row(json.loads(pointed)),
        provenance,
    )


def primary_preservation(auth: Authority) -> dict[str, object]:
    """Every primary certificate is retained verbatim; q_v proofs are re-executed."""
    result = auth.neighbor_result
    base = object_row(auth.neighbor.sealed["RESOLVED_CERTIFICATES"])
    certs = object_row(result["ACTIVE_CERTIFICATES"])
    if tuple(sorted(certs)) != auth.neighbor.active or len(certs) != 78:
        raise AssertionError("primary active certificate coverage differs")
    excluded: dict[str, list[object]] = {}
    for pid, raw in certs.items():
        cert = object_row(raw)
        proof = primary.neighbor_deficit(pid, auth.neighbor.ledger[pid].cap)
        sealed = object_row(base[pid])
        if (
            cert["NEIGHBOR_DEFICIT_PROOF"] != plain(proof.certificate())
            or cert["DEGREE_S5_PROOF"] != sealed["DEGREE_S5_PROOF"]
            or cert["CAP_AUTHORITY"] != sealed["CAP_AUTHORITY"]
            or cert["SPECIAL_CERTIFICATE_SHA256"] != sealed["SPECIAL_CERTIFICATE_SHA256"]
            or cert["T_RANGE"] != [22, proof.cap]
        ):
            raise AssertionError("primary neighbor-deficit certificate weakened")
        values = rows(cert["EXCLUDED_T_VALUES"])
        if values != list(range(proof.cap + 1, auth.neighbor.ledger[pid].cap + 1)):
            raise AssertionError("primary impossible-t exclusions differ")
        if values:
            excluded[pid] = values
    count = sum(len(v) for v in excluded.values())
    if (
        list(excluded) != result["CAP_REDUCTION_PROFILE_IDS"]
        or len(excluded) != 11
        or count != result["EXCLUDED_T_TERM_COUNT"]
        or count != 24
        or PROFILE in excluded
        or result["SPECIAL_PER_T_CERTIFICATES_SHA256"]
        != digest(auth.neighbor.sealed["SPECIAL_PER_T_CERTIFICATES"])
        or result["FRONTIER_CERTIFICATES"] != auth.neighbor.sealed["FRONTIER_CERTIFICATES"]
        or digest(result["FRONTIER_CERTIFICATES"]) != result["FRONTIER_CERTIFICATES_SHA256"]
        or result["S5_IDENTITY"] != auth.neighbor.sealed["S5_IDENTITY"]
    ):
        raise AssertionError("primary cap, special-floor, S5 or frontier authority differs")
    return {
        "STATUS": "PASS_PRIMARY_REPLAYED_AND_RETAINED_VERBATIM",
        "Q_V_THEOREM_STATUS": "PASS_REEXECUTED_ALL_78_ACTIVE_DEGREE_PROOFS",
        "ACTIVE_PROFILE_COUNT": len(certs),
        "ACTIVE_CERTIFICATES_SHA256": digest(certs),
        "RETAINED_ACTIVE_CERTIFICATES_SHA256": digest(
            {pid: cert for pid, cert in certs.items() if pid != PROFILE}
        ),
        "CAP_REDUCTION_PROFILE_IDS": list(excluded),
        "EXCLUDED_T_VALUES": excluded,
        "EXCLUDED_T_TERM_COUNT": count,
        "RETAINED_T_TERM_COUNT": result["RETAINED_T_TERM_COUNT"],
        "SPECIAL_PER_T_CERTIFICATES_SHA256": result["SPECIAL_PER_T_CERTIFICATES_SHA256"],
        "SPECIAL_S4_SCOPE_STATUS": result["SPECIAL_S4_SCOPE_STATUS"],
        "S5_DEGREE_CAPS_SHA256": digest(
            {pid: object_row(cert)["DEGREE_S5_PROOF"] for pid, cert in certs.items()}
        ),
        "S5_IDENTITY": result["S5_IDENTITY"],
        "CAP_AUTHORITIES_SHA256": digest(
            {pid: object_row(cert)["CAP_AUTHORITY"] for pid, cert in certs.items()}
        ),
        "UNCHANGED_RESOLVED_ROW_COUNT": result["UNCHANGED_RESOLVED_ROW_COUNT"],
        "UNCHANGED_RESOLVED_ROWS_SHA256": result["UNCHANGED_RESOLVED_ROWS_SHA256"],
        "FRONTIER_PROFILE_COUNT": result["FRONTIER_PROFILE_COUNT"],
        "FRONTIER_CERTIFICATES_SHA256": result["FRONTIER_CERTIFICATES_SHA256"],
        "PRIMARY_COMPLETE_BOUNDS_SHA256": result["COMPLETE_BOUNDS_SHA256"],
        "PRIMARY_FAMILY_UB": result["FINAL_COMPLETE_FAMILY_UB"],
        "PRIMARY_OWNER_IDS": result["FINAL_OWNER_IDS"],
    }


def pointed_classification(pasch_result: Mapping[str, object]) -> dict[str, object]:
    """Re-derive both classes, all pointed deletions, every P and the exact moments."""
    reps = donor.representatives()
    sealed_reps = object_row(pasch_result["REPRESENTATIVES"])
    if tuple(reps) != CLASSES or tuple(sorted(sealed_reps)) != CLASSES:
        raise AssertionError("STS13 classification classes differ")
    complete_counts: dict[str, int] = {}
    for name, design in reps.items():
        rep = object_row(sealed_reps[name])
        count = len(donor.pasches(design, tuple(range(13))))
        if blocks(rep["BLOCKS"]) != design or rep["COMPLETE_DESIGN_PASCH_COUNT"] != count:
            raise AssertionError("published STS13 representative differs")
        complete_counts[name] = count
    if len(set(complete_counts.values())) != len(CLASSES):
        raise AssertionError("STS13 classes are not certified non-isomorphic")
    structure = donor.structural_proof()
    if (
        plain(structure) != pasch_result["STRUCTURE_PROOF"]
        or structure["STATUS"] != "PROVED_UNIVERSAL_UNIQUE_COMPLETION_AND_CONVERSE"
    ):
        raise AssertionError("STS13 unique completion/converse proof differs")
    moments = donor.moment_identity_proof()
    if plain(moments) != pasch_result["MOMENT_IDENTITY_PROOF"] or (
        moments["S4"],
        moments["S5"],
        moments["S6"],
        moments["S7"],
    ) != (EXACT_S4, EXACT_S5, "7*P", EXACT_S7):
        raise AssertionError("universal S4/S5/S6/S7 identities differ")
    s1, s2, s3 = donor.first_three_moments()
    if s1 - s2 + s3 - EXACT_S4 + EXACT_S5 != START_BOUND:
        raise AssertionError("fifth partial sum differs from the primary STS13 bound")
    records = [object_row(r) for r in rows(pasch_result["POINTED_DELETIONS"])]
    keys = [(r["CLASS"], r["DELETED_POINT"]) for r in records]
    if len(keys) != 26 or set(keys) != {(c, p) for c in CLASSES for p in range(13)}:
        raise AssertionError("pointed deletion missing or duplicated")
    observed: dict[str, Counter[int]] = {name: Counter() for name in CLASSES}
    summary: list[list[object]] = []
    for record in records:
        name, point = integration.text(record["CLASS"]), integer(record["DELETED_POINT"])
        core = donor.delete_point(reps[name], point)
        complete, matching = donor.complete_deleted(core)
        if (
            blocks(record["CORE_BLOCKS"]) != core
            or record["UNCOVERED_MATCHING"] != plain(matching)
            or record["UNIQUE_COMPLETION_SHA256"] != digest(complete)
            or donor.delete_point(complete, 12) != core
        ):
            raise AssertionError("pointed deletion completion/converse differs")
        p = len(donor.pasches(core, tuple(range(12))))
        exact = donor.exact_moments(*donor.realization(core))
        expected = [s1, s2, s3, EXACT_S4, EXACT_S5, 7 * p, EXACT_S7]
        union = sum((-1) ** i * value for i, value in enumerate(expected))
        if (
            {key: record[key] for key in exact} != plain(exact)
            or record["P"] != p
            or [record[f"S{i}"] for i in range(1, 8)] != expected
            or record["EXACT_UNION"] != union
            or union != START_BOUND - 7 * p
        ):
            raise AssertionError("pointed Pasch count or exact moment identity differs")
        observed[name][p] += 1
        summary.append([name, point, p, 7 * p, union])
    distribution = {name: dict(sorted(observed[name].items())) for name in CLASSES}
    if distribution != PASCH_DISTRIBUTION:
        raise AssertionError("pointed Pasch distribution differs")
    p_min = min(integer(row[2]) for row in summary)
    if p_min != pasch_result["P_UNIVERSAL_LOWER_BOUND"] or p_min != 4:
        raise AssertionError("universal Pasch floor differs")
    return {
        "STATUS": "PASS_PUBLISHED_TWO_CLASSES_ALL_POINTED_DELETIONS_REDERIVED",
        "CLASSIFICATION_REFERENCE": pasch_result["CLASSIFICATION_REFERENCE"],
        "CLASSES": list(CLASSES),
        "COMPLETE_DESIGN_PASCH_COUNTS": complete_counts,
        "STRUCTURE_STATUS": structure["STATUS"],
        "STRUCTURE_PROOF_SHA256": digest(structure),
        "POINTED_DELETION_COUNT": len(summary),
        "POINTED_DELETIONS_SHA256": digest(records),
        "POINTED_SUMMARY_COLUMNS": ["CLASS", "DELETED_POINT", "P", "S6", "EXACT_UNION"],
        "POINTED_SUMMARY": summary,
        "PASCH_DISTRIBUTION": {
            name: {str(p): n for p, n in counts.items()} for name, counts in distribution.items()
        },
        "P_UNIVERSAL_FLOOR": p_min,
        "MOMENT_IDENTITY_PROOF_SHA256": digest(moments),
        "MOMENT_IDENTITIES": {
            "S1": s1,
            "S2": s2,
            "S3": s3,
            "S4": EXACT_S4,
            "S5": EXACT_S5,
            "S6": "7*P",
            "S7": EXACT_S7,
        },
        "UNION_IDENTITY": f"{START_BOUND}-7P",
        "EXACT_T270_BOUND": START_BOUND - 7 * p_min,
    }


def parse_term(raw: object) -> primary.Term:
    fields = rows(raw)
    if len(fields) != len(primary.TERM_COLUMNS):
        raise AssertionError("incorrect primary term shape")
    values = tuple(None if i == 3 and v is None else integer(v) for i, v in enumerate(fields))
    return cast(primary.Term, values)


def validate_scope(
    old: Sequence[primary.Term],
    new: Sequence[JointTerm],
    retained: Sequence[tuple[int, ...]],
    bound: int,
) -> None:
    if (
        [term[0] for term in new] != list(range(22, CAP + 1))
        or len(old) != len(new)
        or len(retained) != len(new)
    ):
        raise AssertionError("incomplete or duplicated joint t envelope")
    for term, joint, base in zip(old, new, retained, strict=True):
        if joint[:13] != term or base[0] != term[0]:
            raise AssertionError("primary neighbor-deficit term changed")
        if term[0] == CAP:
            if joint[13] != bound or joint[14] != min(term[12], bound):
                raise AssertionError("pointed Pasch t270 bound misapplied")
        elif joint[13] is not None or joint[14] != term[12] or joint[14] > base[1]:
            raise AssertionError("pointed Pasch credit outside the exact t=270 STS13 presentation")


def joint_terms(auth: Authority, bound: int) -> list[JointTerm]:
    cert = object_row(object_row(auth.neighbor_result["ACTIVE_CERTIFICATES"])[PROFILE])
    sts = object_row(auth.pasch_result["PROFILE_CERTIFICATE"])
    old = [parse_term(raw) for raw in rows(cert["ALL_T_TERMS"])]
    retained = [tuple(integer(v) for v in rows(raw)) for raw in rows(sts["ALL_T_TERMS"])]
    shared = [term[:6] for term in old]
    if (
        digest(old) != cert["ALL_T_TERMS_SHA256"]
        or digest(shared) != cert["AUTHORITATIVE_TERMS_SHA256"]
        or digest(shared) != sts["BASE_TERMS_SHA256"]
        or cert["T_RANGE"] != [22, CAP]
        or cert["EXCLUDED_T_VALUES"] != []
        or object_row(cert["NEIGHBOR_DEFICIT_PROOF"])["NEW_TRIANGLE_CAP"] != CAP
        or object_row(cert["CAP_AUTHORITY"])["TRIANGLE_CAP"] != CAP
        or retained[:-1] != shared[:-1]
        or retained[-1] != (CAP, bound, *shared[-1][2:])
        or sts["NEW_T270_BOUND"] != bound
    ):
        raise AssertionError("sibling STS13 envelopes do not share one sealed authority")
    top = old[-1]
    s3 = donor.first_three_moments()[2]
    # t=270: exact S3, S4_USED is the exact universal S4 (F below it), exact S5 cap.
    if (top[0], top[5], top[9], top[11], top[12]) != (CAP, s3, EXACT_S4, START_BOUND, START_BOUND):
        raise AssertionError("primary t270 bound is not the exact fifth partial sum")
    if top[8] > EXACT_S4 or object_row(cert["DEGREE_S5_PROOF"])["S5_CAP"] != EXACT_S5:
        raise AssertionError("primary t270 floor or S5 cap contradicts the exact identity")
    new: list[JointTerm] = []
    for term in old:
        credit = bound if term[0] == CAP else None
        new.append((*term, credit, term[12] if credit is None else min(term[12], credit)))
    validate_scope(old, new, retained, bound)
    return new


def primary_ledger(auth: Authority) -> dict[str, Row]:
    certs = object_row(auth.neighbor_result["ACTIVE_CERTIFICATES"])
    final = dict(auth.neighbor.ledger)
    for pid in auth.neighbor.active:
        bound = integer(object_row(certs[pid])["CERTIFIED_PROFILE_BOUND"])
        if bound != final[pid].bound:
            final[pid] = replace(
                final[pid],
                bound=bound,
                source=f"{primary.RESULT_FILENAME}:ACTIVE_CERTIFICATES[{pid}]",
            )
    return final


def complete_family(
    auth: Authority, bound: int
) -> tuple[dict[str, Row], dict[str, object], list[list[object]]]:
    frontier = object_row(auth.neighbor_result["FRONTIER_CERTIFICATES"])
    ledger = primary_ledger(auth)
    before = plain(primary.complete_bounds(ledger, frontier, auth.neighbor))
    if (
        plain(previous.family(ledger, frontier, auth.neighbor.inherited))
        != auth.neighbor_result["FINAL_FAMILY"]
        or before != auth.neighbor_result["COMPLETE_PROFILE_BOUNDS"]
    ):
        raise AssertionError("primary complete Family replay differs")
    row = ledger[PROFILE]
    if not INCUMBENT <= bound <= row.bound:
        raise AssertionError("joint STS13 bound outside the certified interval")
    joint = {
        **ledger,
        PROFILE: replace(row, bound=bound, source=f"{RESULT_FILENAME}:JOINT_STS13_CERTIFICATE"),
    }
    family = object_row(plain(previous.family(joint, frontier, auth.neighbor.inherited)))
    after = primary.complete_bounds(joint, frontier, auth.neighbor)
    old_pairs = rows(before)
    if [rows(a)[0] for a in old_pairs] != [b[0] for b in after]:
        raise AssertionError("joint Family profile coverage differs")
    changed = [b[0] for a, b in zip(old_pairs, after, strict=True) if a != b]
    if changed != [PROFILE]:
        raise AssertionError("joint Family changes a profile other than STS13")
    return joint, family, after


def witness_soundness(
    auth: Authority,
    final: Mapping[str, Row],
    terms: Sequence[JointTerm],
    p_floor: int,
) -> dict[str, object]:
    """Every sealed legal witness lies below its joint t and profile bounds."""
    base = object_row(auth.neighbor.sealed["WITNESS_SOUNDNESS"])
    witnesses = object_row(base["WITNESSES"])
    checks = object_row(object_row(auth.neighbor_result["WITNESS_SOUNDNESS"])["CHECKS"])
    certs = object_row(auth.neighbor_result["ACTIVE_CERTIFICATES"])
    exact_unions = {
        integration.text(object_row(base[key])["SUPPORTS_SHA256"]): object_row(base[key])
        for key in ("STS13_EXACT_UNION", "TRADED_STS13_EXACT_UNION")
    }
    supports = {
        "STS13": previous.split.witness_supports("STS13"),
        "TRADED_STS13": previous.identity.previous.traded_witness(),
    }
    if len(witnesses) != 77 or set(checks) != set(witnesses):
        raise AssertionError("sealed witness coverage differs")
    out: dict[str, object] = {}
    for name, raw in sorted(witnesses.items()):
        witness, check = object_row(raw), object_row(checks[name])
        pid, t = integration.text(witness["PROFILE_ID"]), integer(witness["TRIANGLES"])
        moment = integer(witness["EXACT_MOMENT_UPPER_BOUND"])
        cap = (
            integer(rows(object_row(certs[pid])["T_RANGE"])[1]) if pid in certs else final[pid].cap
        )
        if check["PROFILE_ID"] != pid or check["T"] != t or not 22 <= t <= cap:
            raise AssertionError(f"retained t range excludes a legal witness: {name}")
        if pid == PROFILE:
            sealed = exact_unions.get(integration.text(witness["SUPPORTS_SHA256"]))
            if name not in supports or sealed is None or t != CAP or terms[t - 22][0] != t:
                raise AssertionError("STS13 witness outside the pointed t=270 scope")
            triples, pairs = supports[name]
            exact = donor.exact_moments(triples, pairs)
            p = integer(exact["P"])
            value = integer(exact["EXACT_UNION"])
            if (
                digest([triples, pairs]) != witness["SUPPORTS_SHA256"]
                or plain(exact["PASCH_SIX_SETS"]) != sealed["PASCH_SIX_SETS"]
                or (exact["S4"], exact["S5"], exact["S6"], exact["S7"])
                != (witness["EXACT_S4_FROM_PINNED_LOCAL_TABLE"], sealed["S5"], 7 * p, EXACT_S7)
                or sealed["S6"] != 7 * p
                or sealed["S7"] != EXACT_S7
                or value != sealed["EXACT_ANY_PRIZE_UNION"]
                or value != moment - 7 * p + EXACT_S7
                or p < p_floor
            ):
                raise AssertionError(f"STS13 witness exact union differs: {name}")
            bound, kind = terms[t - 22][14], "EXACT_UNION"
        else:
            bound, kind, value = integer(check["T_BOUND"]), "EXACT_MOMENT_UPPER_BOUND", moment
        if value > bound or value > final[pid].bound:
            raise AssertionError(f"joint envelope excludes a legal witness: {name}")
        out[name] = {
            "PROFILE_ID": pid,
            "T": t,
            "VALUE_KIND": kind,
            "VALUE": value,
            "T_BOUND": bound,
            "PROFILE_BOUND": final[pid].bound,
        }
    return {
        "STATUS": "PASS",
        "WITNESS_COUNT": len(out),
        "PRESERVED_WITNESS_RECORDS_SHA256": digest(witnesses),
        "CHECKS": out,
    }


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    auth = load_authority() if authority is None else authority
    preserved = primary_preservation(auth)
    sts13 = pointed_classification(auth.pasch_result)
    p_floor = integer(sts13["P_UNIVERSAL_FLOOR"])
    bound = START_BOUND - 7 * p_floor
    terms = joint_terms(auth, bound)
    profile_bound = max(term[14] for term in terms)
    final, family, pairs = complete_family(auth, profile_bound)
    bounds = {integration.text(pid): integer(value) for pid, value in pairs}
    frontier = object_row(auth.neighbor_result["FRONTIER_CERTIFICATES"])
    maximum = max(bounds.values())
    owners = sorted(pid for pid, value in bounds.items() if value == maximum)
    competing = max(value for pid, value in bounds.items() if pid not in owners)
    incumbent = donor.reconstruct_incumbent(auth.pasch)
    union = integer(incumbent["EXACT_UNION"])
    if (
        len(bounds) != 4844
        or set(final) & set(frontier)
        or set(final) | set(frontier) != set(bounds)
        or (len(final), len(frontier)) != (4647, 197)
    ):
        raise AssertionError("complete 4844-profile coverage is not disjoint and exhaustive")
    if (
        plain(incumbent) != auth.pasch_result["INCUMBENT_WITNESS"]
        or union != INCUMBENT
        or maximum != family["FAMILY_UB"]
        or owners != family["OWNER_IDS"]
        or owners != [PROFILE]
        or maximum != union
    ):
        raise AssertionError("complete Family upper bound is not attained by the incumbent")
    sound = witness_soundness(auth, final, terms, p_floor)
    lower = terms[:-1]
    cert = object_row(object_row(auth.neighbor_result["ACTIVE_CERTIFICATES"])[PROFILE])
    sts = object_row(auth.pasch_result["PROFILE_CERTIFICATE"])
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "REMAINING_TASK_MODEL": "最強模型",
        "COMMON_PARENT": COMMON_PARENT,
        "PRIMARY_HEAD": PRIMARY_HEAD,
        "PRIMARY_TREE": PRIMARY_TREE,
        "PRIMARY_RESULT_SHA256": PRIMARY_RESULT_SHA256,
        "DONOR_HEAD": DONOR_HEAD,
        "DONOR_TREE": DONOR_TREE,
        "DONOR_RESULT_SHA256": DONOR_RESULT_SHA256,
        "SOURCE_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "SIBLING_FILE_SHA256": auth.provenance,
        "DONOR_BYTE_IDENTITY_STATUS": "PASS_THREE_DONOR_BLOBS_BYTE_IDENTICAL",
        "SIBLING_REPLAY_STATUS": "PASS_BOTH_SIBLINGS_EXECUTABLE_BYTE_REPLAY",
        "PROOF": __doc__,
        "PRIMARY_CERTIFICATE_PRESERVATION": preserved,
        "STS13_POINTED_PASCH_CERTIFICATE": sts13,
        "JOINT_STS13_CERTIFICATE": {
            "PROFILE_ID": PROFILE,
            "LOAD_BEARING_T": CAP,
            "CAP_AUTHORITY": cert["CAP_AUTHORITY"],
            "NEIGHBOR_DEFICIT_PROOF": cert["NEIGHBOR_DEFICIT_PROOF"],
            "PRIMARY_ALL_T_TERMS_SHA256": cert["ALL_T_TERMS_SHA256"],
            "SHARED_BASE_TERMS_SHA256": sts["BASE_TERMS_SHA256"],
            "DONOR_ALL_T_TERMS_SHA256": sts["ALL_T_TERMS_SHA256"],
            "TERM_COLUMNS": TERM_COLUMNS,
            "ALL_T_TERMS": terms,
            "ALL_T_TERMS_SHA256": digest(terms),
            "PRIMARY_T270_BOUND": terms[-1][12],
            "POINTED_PASCH_T270_BOUND": bound,
            "NEW_STS13_T270_BOUND": terms[-1][14],
            "CERTIFIED_PROFILE_BOUND": profile_bound,
            "ARGMAX_T": [term[0] for term in terms if term[14] == profile_bound],
            "LOWER_T_COUNT": len(lower),
            "LOWER_T_MAX": max(term[14] for term in lower),
            "DONOR_RETAINED_LOWER_T_MAX": DONOR_LOWER_T_MAX,
            "LOWER_T_PRIMARY_STRONGER_COUNT": sum(
                term[14] < integer(rows(raw)[1])
                for term, raw in zip(lower, rows(sts["ALL_T_TERMS"])[:-1], strict=True)
            ),
            "LOWER_T_STATUS": "PASS_PRIMARY_BOUNDS_UNCHANGED_AT_MOST_DONOR_RETAINED",
            "BOUND_RULE": "T270: MIN(PRIMARY_FIFTH_ORDER,POINTED_EXACT_UNION); OTHER T: PRIMARY",
            "S6_SCOPE": "EXACT_STS13_T270_PRESENTATION_ONLY",
        },
        "DOUBLE_COUNT_STATUS": "PASS_S6_ONCE_INSIDE_EXACT_IDENTITY_MIN_NEVER_SUBTRACTED",
        "COMPLETE_PROFILE_BOUNDS": pairs,
        "COMPLETE_BOUNDS_SHA256": digest(pairs),
        "COMPLETE_BOUNDS_ENCODING": "SHA256_CANONICAL_JSON_SORTED_PROFILE_ID_INTEGER_BOUND_PAIRS",
        "RESOLVED_PROFILE_COUNT": len(final),
        "FRONTIER_PROFILE_COUNT": len(frontier),
        "FRONTIER_MAX_BOUND": max(bounds[pid] for pid in frontier),
        "COMPLETE_4844_COVERAGE_STATUS": "PASS_DISJOINT_EXHAUSTIVE_SEALED_PARTITION",
        "CHANGED_PROFILE_IDS": [PROFILE],
        "FINAL_FAMILY": family,
        "START_COMPLETE_FAMILY_UB": START_BOUND,
        "FINAL_COMPLETE_FAMILY_UB": maximum,
        "FINAL_OWNER_IDS": owners,
        "CANONICAL_INCUMBENT": union,
        "REMAINING_GAP": maximum - union,
        "NEXT_RESOLVED_COMPETING_BOUND": competing,
        "NEXT_RESOLVED_COMPETING_IDS": sorted(
            pid for pid, value in bounds.items() if value == competing
        ),
        "INCUMBENT_WITNESS": {
            key: incumbent[key]
            for key in ("STATUS", "SUPPORTS_SHA256", "P", "PASCH_SIX_SETS", "EXACT_UNION")
        },
        "INCUMBENT_WITNESS_SHA256": digest(incumbent),
        "WITNESS_SOUNDNESS": sound,
        "WITNESS_SOUNDNESS_STATUS": "PASS_ALL_77_RECORDS_NO_LEGAL_WITNESS_EXCLUDED",
        "CLAIM_SCOPE": (
            "MINIMUM_S2_OPTIMAL_RELATIVE_TO_SEALED_STRUCTURAL_FAMILY_AUTHORITY; "
            "NOT_A_GLOBAL_K20_OPTIMALITY_CLAIM"
        ),
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PROFILE_CENSUS_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "PUSH_PR_MERGE": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def render(result: Mapping[str, object]) -> bytes:
    return integration.render(result).encode("utf-8")


def verify_result(result: Mapping[str, object], authority: Authority | None = None) -> None:
    if render(result) != render(compute_result(authority)):
        raise AssertionError("tampered joint neighbor-deficit STS13 Family closure")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify", action="store_true", help="recompute and verify exact JSON bytes"
    )
    args = parser.parse_args()
    result = compute_result()
    raw = render(result)
    if args.verify:
        if RESULT_PATH.read_bytes() != raw:
            raise AssertionError("joint Family closure byte replay differs")
    else:
        with RESULT_PATH.open("xb") as out:
            out.write(raw)
    print(
        json.dumps(
            {
                "RESULT_REPLAY_STATUS": "PASS" if args.verify else "CREATED",
                **{
                    key: result[key]
                    for key in (
                        "FINAL_COMPLETE_FAMILY_UB",
                        "FINAL_OWNER_IDS",
                        "REMAINING_GAP",
                        "NEXT_RESOLVED_COMPETING_BOUND",
                        "COMPLETE_BOUNDS_SHA256",
                    )
                },
            }
        )
    )


if __name__ == "__main__":
    main()
