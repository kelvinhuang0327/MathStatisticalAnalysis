"""Compose three exact-profile certificates without executing their theorems.

The immutable b114 family supplies all 4647 resolved rows and 197 cursor
profiles. The original R2 analytic caps apply only to its exact profiles;
the independently accepted T223 certificate supersedes R2's weaker T227.
Only complete Route-B envelopes and family arithmetic are executed here.
Source dispositions, independent reviews and unknown attainment stay distinct.
"""

from __future__ import annotations

import argparse
import ast
import stat
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route
from . import b649_min_s2_owner_ab_exact_family_composition_r1 as inherited

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_THREE_MAX_OWNERS_EXACT_AUTHORITY_R1"
OWNER_CONVERSATION_ID = "01a13884-b852-7dc3-a58b-068e4b12c0d4-47befd38-8f72-4512-aa2b-4afaf492f9ec"
DIRECTORY = inherited.DIRECTORY
SOURCE = "src/lottolab/research/b649_min_s2_three_max_owners_exact_authority_r1.py"
TEST = "tests/unit/test_b649_min_s2_three_max_owners_exact_authority_r1.py"
RESULT_PREFIX = "b649-min-s2-three-max-owners-exact-authority-r1-result-"
PROFILES = ("65555555555532000000", "66555555555333000000", "66555555554442000000")
CAPS = (230, 228, 223)
MODEL = inherited.MODEL
R2_MODEL: dict[str, object] = {
    "tickets": 20,
    "labels_per_ticket": 6,
    "labels": 49,
    "triples": 22,
    "pairs": 27,
    "support_sizes": [2, 3],
    "pair_linearity": True,
}
PR_HEAD = "693e750e8fdf62382b5be056cffe3b688608ab6d"
PR_TREE = "484b4df1b44fc2fb0405c6b470aff58579f0617e"
REVIEW_LOCATOR = (
    "/Users/kelvin/.codex/task-results/B649_THREE_PROFILE_R2_EXACT_ACCEPTANCE_PUBLICATION_R1/"
    "01a135c0-2db5-7572-b136-726f7709bf1c/fresh-judge-report.md"
)
REVIEW_SHA256 = "eb64ebce07e8c417de030d520c13962e39e088ee11a3ef9bc32a42f33c262b7d"
type Document = dict[str, object]
type Term = tuple[int, int, int, int, int, int]
Pin = inherited.Pin
require = inherited.require
obj = inherited.obj
items = inherited.items
integer = inherited.integer
string = inherited.string
sha = inherited.sha
render = inherited.render
git = inherited.git
checked_blob = inherited.checked_blob
decode = inherited.decode
projection = inherited.projection
profile = inherited.profile
family = inherited.family

BASE = Pin(
    "BASE",
    "b1145036c33230d09de0f9c29f831ab1053188a2",
    "12490e36b382081b7ec07be84676644cd0897a3d",
    f"{DIRECTORY}/b649-min-s2-owner-ab-exact-family-composition-r1-result-"
    "f86b27c0481dda62ef25ff390ba2f4b58987faf7aa2d8b4c4a8302cb83ddb643.json",
    "f86b27c0481dda62ef25ff390ba2f4b58987faf7aa2d8b4c4a8302cb83ddb643",
    inherited.SOURCE,
    "6529fcf7b678c33b9a06250ab8037cb068cb6d22e51fc8eca0e9c372e423902b",
    inherited.TEST,
    "1c6702afed06b419f36b4d39d93082fbda7d979246c9c672bd4162e3969d10ad",
)
T223 = Pin(
    "T223",
    "e3c650d1b298f3df7f2ecaeccca63305653b3bba",
    "fe1d00b3b842cdd9494af7e6a4082f0dcf580f91",
    f"{DIRECTORY}/b649-min-s2-owner-t223-formal-cert-r1-result.json",
    "7425b8826e8eddb3d4b930a9f8b1579fc96dbfbdd9c2014a0a34aaf2ef69c48d",
    "src/lottolab/research/b649_min_s2_owner_t223_formal_cert_r1.py",
    "77f07f550b684601c699b8879f4fb5d224b9aef07cb061d0013ace1e8f0ab701",
    "tests/unit/test_b649_min_s2_owner_t223_formal_cert_r1.py",
    "939778df0ebbc36593c7e50f109d1cc441e9d090e1dd4af3aa8a900b5fa31577",
)
R2 = Pin(
    "R2",
    "ef69e3fb4a2fdb171c4bc6944a3672706506beac",
    "bb8615cfe4af6d78bf55756b37a3f8530b05a304",
    f"{DIRECTORY}/b649-three-max-profiles-shared-certificate-r2-result.json",
    "dc28b0f4e3bfb14be8a39a3d3148f1d27aadf3e060c89a8e6e695dfea55babcc",
    "src/lottolab/research/b649_three_max_profiles_shared_certificate_r2.py",
    "ac4890aba8f8524fb705fead03d4e36608c3ab299cd02f870db06f1a3848ba9d",
    "tests/unit/test_b649_three_max_profiles_shared_certificate_r2.py",
    "d5d0d23543721fe918fd551d6756921d19e6c6cb89d4cec363edb7acd1973fac",
)


@dataclass(frozen=True)
class Authority:
    pin: Pin
    result: Document
    source: bytes
    message: str
    acceptance: Document


type Inputs = tuple[Authority, Authority, Authority]


def identity(head: str, tree: str) -> None:
    require(git("cat-file", "-t", head).strip() == b"commit", "wrong commit identity")
    require(git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "wrong tree identity")


def review_record(raw: bytes) -> Document:
    require(sha(raw) == REVIEW_SHA256, "R2 independent review SHA256 mismatch")
    text = raw.decode()
    require(
        text.startswith("VERIFIED_WITH_CAVEATS\n")
        and "JUDGE_MODE: FRESH_CONTEXT; JUDGE_DEPTH: BOUNDED" in text
        and f"EXACT_CANDIDATE_HEAD: {R2.head}\n" in text
        and f"EXACT_CANDIDATE_TREE: {R2.tree}\n" in text
        and all(h in text for h in (R2.source_sha256, R2.test_sha256, R2.result_sha256)),
        "R2 independent review binding differs",
    )
    return {
        "VERDICT": "VERIFIED_WITH_CAVEATS",
        "JUDGE_MODE": "FRESH_CONTEXT",
        "REVIEWED_HEAD": R2.head,
        "JUDGED_TREE": R2.tree,
        "REPORT_SHA256": REVIEW_SHA256,
        "LOCATOR": REVIEW_LOCATOR,
        "REPORT_VERBATIM": text,
        "DISPOSITION": "Independent exact-original-tree review; original result status unchanged",
    }


def load_review() -> bytes:
    path = Path(REVIEW_LOCATOR)
    if path.exists():
        require(stat.S_ISREG(path.lstat().st_mode), "unsafe R2 review file")
        return path.read_bytes()
    # A sealed result carries the exact externally pinned report for portable replay.
    sealed = result_path()
    if sealed is None:
        raise ValueError("missing pinned R2 independent review")
    document = decode(sealed.read_bytes())
    return string(obj(obj(document["PROVENANCE"])["R2"])["ACCEPTANCE_REPORT_VERBATIM"]).encode()


def load_inputs() -> Inputs:
    loaded: list[Authority] = []
    for pin in (BASE, T223, R2):
        identity(pin.head, pin.tree)
        raw = checked_blob(pin.head, pin.result, pin.result_sha256)
        result = decode(raw)
        require(render(result) == raw, "noncanonical immutable result")
        source = checked_blob(pin.head, pin.source, pin.source_sha256)
        checked_blob(pin.head, pin.test, pin.test_sha256)
        source_key = "SOURCE_SHA256" if pin == R2 else "IMPLEMENTATION_SHA256"
        require(
            result[source_key] == pin.source_sha256 and result["TEST_SHA256"] == pin.test_sha256,
            "result source binding differs",
        )
        message = git("cat-file", "commit", pin.head).split(b"\n\n", 1)[1].decode()
        accepted = review_record(load_review()) if pin == R2 else inherited.acceptance(pin, message)
        for path, digest in obj(result.get("SOURCE_PINS", {})).items():
            checked_blob(pin.head, path, string(digest))
            # Every reused evaluator source must also be the exact Science Base/local blob.
            frozen = checked_blob(BASE.head, path, string(digest))
            local = ROOT / path
            require(
                stat.S_ISREG(local.lstat().st_mode) and local.read_bytes() == frozen,
                f"reused evaluator source drift: {path}",
            )
        if pin == BASE:
            for path, digest in (
                (pin.source, pin.source_sha256),
                (pin.test, pin.test_sha256),
                (pin.result, pin.result_sha256),
            ):
                local = ROOT / path
                require(
                    stat.S_ISREG(local.lstat().st_mode)
                    and local.read_bytes() == checked_blob(pin.head, path, digest),
                    "Base drift",
                )
        loaded.append(Authority(pin, result, source, message, accepted))
    identity(PR_HEAD, PR_TREE)
    require(R2.tree != PR_TREE, "current PR tree conflated with original reviewed tree")
    for path, digest in (
        (R2.source, R2.source_sha256),
        (R2.test, R2.test_sha256),
        (R2.result, R2.result_sha256),
    ):
        checked_blob(PR_HEAD, path, digest)
    require(not any(name.startswith("ortools") for name in sys.modules), "solver loaded")
    return loaded[0], loaded[1], loaded[2]


def validate_inputs(inputs: Inputs) -> None:
    require(tuple(a.pin for a in inputs) == (BASE, T223, R2), "source identity mismatch")
    for a in inputs:
        require(sha(render(a.result)) == a.pin.result_sha256, "altered source result")
        require(sha(a.source) == a.pin.source_sha256, "altered source SHA256")
        accepted = (
            review_record(string(a.acceptance["REPORT_VERBATIM"]).encode())
            if a.pin == R2
            else inherited.acceptance(a.pin, a.message)
        )
        require(a.acceptance == accepted, "altered source acceptance")
        if a.pin != BASE:
            require(
                ast.get_docstring(ast.parse(a.source), clean=False) == a.result["PROOF"],
                "donor proof/source mismatch",
            )


def replay_base(base: Document) -> tuple[dict[str, int], Document]:
    require(sha(render(base)) == BASE.result_sha256, "altered Base authority")
    rows = {p: integer(v) for p, v in obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(base["CURSOR"])
    coarse = obj(cursor["COARSE_BOUND_PROJECTION"])
    ids = items(cursor["PROFILE_IDS"])
    require(len(rows) == integer(base["ROWS_TOTAL"]) == 4647, "omitted ledger rows")
    require(
        len(coarse) == len(ids) == integer(cursor["PROFILE_COUNT"]) == 197
        and set(coarse) == set(ids)
        and not set(rows).intersection(coarse),
        "cursor coverage",
    )
    for pid in [*rows, *coarse]:
        profile(pid)
    require(sha(projection(rows)) == base["BOUNDS_SHA256_AFTER"], "ledger digest differs")
    require(sha(render(cursor)) == base["CURSOR_SHA256"], "cursor digest differs")
    for pid, bound in coarse.items():
        require(
            route.r28.coarse_profile_envelope(profile(pid)).family_upper_bound == integer(bound),
            "cursor exact-profile evaluator differs",
        )
    require(max(integer(b) for b in coarse.values()) == cursor["BOUND"], "cursor maximum differs")
    maximum, owners = family(rows, cursor)
    incumbent = integer(base["INCUMBENT"])
    require(
        maximum == base["FAMILY_BOUND_AFTER"]
        and owners == base["FAMILY_OWNER_IDS"]
        and maximum - incumbent == base["GAP_TO_INCUMBENT"]
        and sum(b > incumbent for b in [*rows.values(), *(integer(v) for v in coarse.values())])
        == base["STILL_OPEN_PROFILE_COUNT"],
        "Base family replay differs",
    )
    return rows, cursor


def envelope(pid: str, cap: int) -> list[Term]:
    require(pid in PROFILES and type(cap) is int and 22 <= cap <= 266, "wrong exact profile/cap")
    d = profile(pid)
    g = [6 + v for v in d]
    wedges, third = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    contained_cap = sum(v * (4 + v) for v in d) // 3
    require((wedges, contained_cap) == (825, 196), "wrong envelope model")
    require(route.r28.profile_s4_floor(d) == 112, "wrong inherited exact-profile S4 floor")
    terms: list[Term] = []
    for t in range(22, cap + 1):
        open_wedges = wedges - 3 * t
        k4 = max(0, -(-(third - (max(g) - 2) * open_wedges) // 4))
        contained = min(k4, contained_cap)
        s4 = max(112, 679 * k4 - 231 * contained)
        s3 = 2800 * open_wedges + 20272 * (t - 22) + 7000 * 22
        total = 372_228_640 - 63_838_600 + s3
        bound = (7 * total - 4 * s4 + 6) // 7
        exact = Fraction(total) - Fraction(4 * s4, 7)
        require(bound == -(-exact.numerator // exact.denominator), "final rational ceiling differs")
        terms.append((t, bound, k4, contained, s4, s3))
    require(
        terms == route.route_b_envelope(d, cap, 112), "pinned complete Route-B envelope differs"
    )
    return terms


def certificates(inputs: Inputs) -> dict[str, Document]:
    validate_inputs(inputs)
    base, t223, r2 = (a.result for a in inputs)
    require(
        obj(r2["RESOLVED_ROW_BOUNDS_BEFORE"]) == obj(base["RESOLVED_ROW_BOUNDS"])
        and r2["CURSOR"] == base["CURSOR"],
        "R2 mathematical Base projection differs",
    )
    require(
        t223["BASE_HEAD"] == BASE.head
        and t223["BASE_TREE"] == BASE.tree
        and t223["BASE_RESULT_SHA256"] == BASE.result_sha256
        and t223["INHERITED_BASE_RESULT_VERBATIM"] == base,
        "T223 Base identity differs",
    )
    facts = obj(t223["MODEL_FACTS"])
    require(
        facts["MODEL"] == MODEL
        and facts["D"] == list(profile(PROFILES[2]))
        and t223["TARGET_PROFILE"] == PROFILES[2]
        and integer(t223["NEW_PROVEN_T_CAP"]) == 223
        and obj(t223["ENUMERATION"])["MAX_F"] == 223
        and t223["LEGAL_SUPPORT_T223_ATTAINMENT"] == "UNKNOWN",
        "wrong T223 model/cap",
    )
    adopted = set(obj(base["PROFILE_CERTIFICATES"])) | {
        string(obj(base["INHERITED_TARGET_BONFERRONI_5_UNCHANGED"])["PROFILE_ID"])
    }
    require(not adopted.intersection(PROFILES), "target has adopted S5")
    sources = [obj(c) for c in items(r2["CERTIFICATES"])]
    require(
        len(sources) == 3 and {c["PROFILE_ID"] for c in sources} == set(PROFILES),
        "wrong R2 certificate identities",
    )
    result: dict[str, Document] = {}
    for pid, cap in zip(PROFILES, CAPS, strict=True):
        donor = next(c for c in sources if c["PROFILE_ID"] == pid)
        theorem = obj(donor["THEOREM"])
        d = profile(pid)
        require(
            theorem["PROFILE_ID"] == pid
            and theorem["D"] == list(d)
            and theorem["ASSUMPTIONS"] == R2_MODEL
            and render(theorem["ASSUMPTIONS"]) == render(R2_MODEL)
            and theorem["ATTAINABILITY"] == "NOT_ASSERTED",
            "wrong exact-profile model",
        )
        analytic = 237 + sum(max(0, (6 - v) * (9 - 2 * v)) for v in d if v) - 6 * d.count(0)
        r2_cap = integer(donor["NEW_T_CAP"])
        require(
            analytic == r2_cap == integer(theorem["ANALYTIC_CAP"])
            and r2_cap == (227 if pid == PROFILES[2] else cap),
            "wrong R2 accepted cap",
        )
        s4, s5 = obj(donor["S4_AUTHORITY"]), obj(donor["S5_AUTHORITY"])
        require(
            s4["EXACT_PROFILE"] == pid
            and s4["INHERITED_FLOOR"] == 112
            and s5["USED"] is False
            and s5["VALUE"] is None,
            "wrong S4/S5 adoption scope",
        )
        old, r2_terms, new = envelope(pid, 266), envelope(pid, r2_cap), envelope(pid, cap)
        require(
            integer(donor["OLD_T_CAP"]) == 266
            and donor["OLD_ALL_T_TERMS"] == [list(t) for t in old]
            and donor["NEW_ALL_T_TERMS"] == [list(t) for t in r2_terms]
            and old[: len(new)] == new,
            "incomplete donor envelope",
        )
        bound, before = max(t[1] for t in new), max(t[1] for t in old)
        require(
            before == donor["OLD_BOUND"] == obj(base["RESOLVED_ROW_BOUNDS"])[pid]
            and max(t[1] for t in r2_terms) == donor["NEW_BOUND"],
            "donor profile bound differs",
        )
        if pid == PROFILES[2]:
            require(
                cap < r2_cap and bound < integer(donor["NEW_BOUND"]), "weaker T227 substitution"
            )
            require(
                t223["ROUTE_B_TERMS"] == [list(t) for t in new]
                and t223["FULL_PROFILE_BOUND_AFTER"] == bound,
                "T223 envelope differs",
            )
        else:
            require(bound == donor["NEW_BOUND"], "R2 bound differs")
        result[pid] = {
            "PROFILE_ID": pid,
            "T_CAP": cap,
            "S4_FLOOR": 112,
            "S5_ADOPTED": False,
            "FULL_PROFILE_BOUND": bound,
            "PRE_UPDATE_BOUND": before,
            "COMPLETE_T_RANGE": [22, cap],
            "TERM_COUNT": len(new),
            "ALL_T_TERMS": [list(t) for t in new],
            "MAXIMIZING_TERMS": [list(t) for t in new if t[1] == bound],
            "SOURCE_HEAD": T223.head if pid == PROFILES[2] else R2.head,
            "SOURCE_TREE": T223.tree if pid == PROFILES[2] else R2.tree,
            "R2_CAP_RETAINED_AS_HISTORY": r2_cap,
            "R2_BOUND_RETAINED_AS_HISTORY": donor["NEW_BOUND"],
            "ATTAINMENT": "UNKNOWN",
        }
    expected = dict(obj(base["RESOLVED_ROW_BOUNDS"]))
    expected[PROFILES[2]] = result[PROFILES[2]]["FULL_PROFILE_BOUND"]
    require(
        t223["RESOLVED_ROW_BOUNDS"] == expected and t223["CURSOR"] == base["CURSOR"],
        "T223 donor changed other rows/cursor",
    )
    return result


def compose(
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    inputs: Inputs,
    updates: Sequence[tuple[str, int, int]],
) -> dict[str, int]:
    certs = certificates(inputs)
    frozen, frozen_cursor = replay_base(inputs[0].result)
    before = dict(rows)
    require(
        len(rows) == len(before) == len(frozen)
        and before == frozen
        and all(type(b) is int for _, b in rows),
        "wrong, duplicate, missing or altered ledger row",
    )
    require(render(cursor) == render(frozen_cursor), "altered cursor")
    require(
        len(updates) == len({p for p, _, _ in updates}) == 3
        and {p for p, _, _ in updates} == set(PROFILES),
        "duplicate, missing or wrong-profile update",
    )
    after = dict(before)
    for pid, cap, bound in updates:
        require(
            type(cap) is int and cap == certs[pid]["T_CAP"], "wrong T cap or weaker substitution"
        )
        require(
            type(bound) is int and bound == integer(certs[pid]["FULL_PROFILE_BOUND"]) < before[pid],
            "wrong full-profile bound",
        )
        after[pid] = bound
    require(
        {p for p in before if before[p] != after[p]} == set(PROFILES), "not exactly three changes"
    )
    require(
        projection({p: b for p, b in before.items() if p not in PROFILES})
        == projection({p: b for p, b in after.items() if p not in PROFILES}),
        "other 4644 rows changed",
    )
    return after


def compute_result(inputs: Inputs | None = None) -> Document:
    sources = load_inputs() if inputs is None else inputs
    certs = certificates(sources)
    base = sources[0].result
    before, cursor = replay_base(base)
    updates = [
        (p, integer(certs[p]["T_CAP"]), integer(certs[p]["FULL_PROFILE_BOUND"])) for p in PROFILES
    ]
    after = compose(list(before.items()), cursor, sources, updates)
    first, old_owners = family(before, cursor)
    last, owners = family(after, cursor)
    incumbent = integer(base["INCUMBENT"])
    all_before = {
        **before,
        **{p: integer(b) for p, b in obj(cursor["COARSE_BOUND_PROJECTION"]).items()},
    }
    all_after = {**all_before, **after}
    provenance: Document = {}
    for a in sources:
        record: Document = {
            "HEAD": a.pin.head,
            "TREE": a.pin.tree,
            "RESULT": a.pin.result,
            "RESULT_SHA256": a.pin.result_sha256,
            "SOURCE_SHA256": a.pin.source_sha256,
            "TEST_SHA256": a.pin.test_sha256,
            "ACCEPTANCE": a.acceptance,
            "ORIGINAL_STATUS_VERBATIM": inherited.status_snapshot(a.result),
            "COMMIT_MESSAGE_VERBATIM": a.message,
        }
        if a.pin == R2:
            record["ACCEPTANCE_REPORT_VERBATIM"] = a.acceptance["REPORT_VERBATIM"]
        provenance[a.pin.tag] = record
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_LIFECYCLE",
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "IMPLEMENTATION_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "PROVENANCE": provenance,
        "R2_CURRENT_PR": {
            "HEAD": PR_HEAD,
            "TREE": PR_TREE,
            "ORIGINAL_REVIEWED_TREE": R2.tree,
            "TREE_IDENTICAL": False,
            "THREE_R2_SCIENCE_BLOBS_UNCHANGED": True,
            "CHANGED_PATHS": git("diff", "--name-status", R2.head, PR_HEAD).decode().splitlines(),
            "DISPOSITION": "Merge-main head differs; publication is not final family acceptance",
        },
        "PROFILE_CERTIFICATES": certs,
        "ROWS_TOTAL": len(before),
        "ROWS_CHANGED": 3,
        "ROW_UPDATES": {p: {"BEFORE": before[p], "AFTER": after[p]} for p in PROFILES},
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "OTHER_ROWS_UNCHANGED": "PASS",
        "OTHER_4644_BOUNDS_SHA256": sha(
            projection({p: b for p, b in before.items() if p not in PROFILES})
        ),
        "BOUNDS_SHA256_BEFORE": sha(projection(before)),
        "BOUNDS_SHA256_AFTER": sha(projection(after)),
        "CURSOR": cursor,
        "CURSOR_SHA256": sha(render(cursor)),
        "CURSOR_PRESERVED": "PASS",
        "CURSOR_PROFILE_COUNT": len(obj(cursor["COARSE_BOUND_PROJECTION"])),
        "FAMILY_BOUND_BEFORE": first,
        "FAMILY_BOUND_AFTER": last,
        "EXACT_FAMILY_DELTA": first - last,
        "FAMILY_OWNER_IDS_BEFORE": old_owners,
        "FAMILY_OWNER_IDS": owners,
        "FAMILY_AFTER_SINGLE_UPDATE": {
            p: family({**before, p: after[p]}, cursor)[0] for p in PROFILES
        },
        "INCUMBENT": incumbent,
        "GAP_TO_INCUMBENT": last - incumbent,
        "STILL_OPEN_PROFILE_COUNT_BEFORE": sum(b > incumbent for b in all_before.values()),
        "STILL_OPEN_PROFILE_COUNT": sum(b > incumbent for b in all_after.values()),
        "STRICT_GAIN_EXCLUDED_PROFILE_COUNT": sum(b <= incumbent for b in all_after.values()),
        "NEWLY_STRICT_GAIN_EXCLUDED_PROFILE_IDS": sorted(
            p for p in PROFILES if before[p] > incumbent >= after[p]
        ),
        "BASE_INHERITED_CAVEATS_AND_STATUS_VERBATIM": base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
        "BASE_SOURCE_STATUS_VERBATIM": base["SOURCE_STATUS_VERBATIM"],
        "BASE_PROVENANCE_VERBATIM": base["PROVENANCE"],
        "OWNER_A_HISTORICAL_REPORT_DIGEST_CAVEAT": obj(obj(base["PROVENANCE"])["A"])["ACCEPTANCE"],
        "INHERITED_CERTIFICATES_ADOPTED_UNCHANGED": base["CERTIFICATES_ADOPTED_UNCHANGED"],
        "INHERITED_TARGET_BONFERRONI_5_UNCHANGED": base["INHERITED_TARGET_BONFERRONI_5_UNCHANGED"],
        "INHERITED_CAVEATS": "PRESERVED",
        "ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "G01_TO_G18_AT_SEAL": {f"G{i:02}": "NOT_VERIFIED" for i in range(1, 19)},
        "GATE_STATUS_SCOPE": (
            "External exact-tree Judge and subsequent single-commit/clean/release lifecycle"
        ),
        "MATHEMATICAL_THEOREMS_REEXECUTED": 0,
        "GRAPHS_ENUMERATED": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "SOLVER_CALLS": 0,
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "EXISTING_CERTIFICATES_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
    }


def result_path() -> Path | None:
    paths = sorted((ROOT / DIRECTORY).glob(f"{RESULT_PREFIX}*.json"))
    require(len(paths) <= 1, "duplicate sealed results")
    if not paths:
        return None
    path = paths[0]
    require(stat.S_ISREG(path.lstat().st_mode), "unsafe result file")
    require(path.name == f"{RESULT_PREFIX}{sha(path.read_bytes())}.json", "invalid result identity")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    existing = result_path()
    require(not args.verify or existing is not None, "missing sealed result")
    result = compute_result()
    raw = render(result)
    if existing:
        require(existing.read_bytes() == raw, "exact result replay differs")
    else:
        with (ROOT / DIRECTORY / f"{RESULT_PREFIX}{sha(raw)}.json").open("xb") as output:
            output.write(raw)
    print(
        render(
            {
                k: result[k]
                for k in (
                    "ROWS_TOTAL",
                    "ROWS_CHANGED",
                    "FAMILY_BOUND_BEFORE",
                    "FAMILY_BOUND_AFTER",
                    "EXACT_FAMILY_DELTA",
                    "FAMILY_OWNER_IDS",
                    "GAP_TO_INCUMBENT",
                    "STILL_OPEN_PROFILE_COUNT",
                )
            }
        )
        .decode()
        .strip()
    )


if __name__ == "__main__":
    main()
