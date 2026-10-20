"""Compose two accepted exact-profile envelopes; never rerun donor theorems.

All 4647 immutable resolved rows and all 197 cursor profiles are replayed.
Only the two intended rows change. Complete old/new Route-B terms use exact
integer and rational arithmetic and the pinned evaluator. Original results,
source dispositions and independent acceptance records remain distinct.
"""

from __future__ import annotations

import argparse
import ast
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from fractions import Fraction
from math import comb
from pathlib import Path

from . import b649_min_s2_three_max_owners_exact_authority_r1 as frozen

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_T248_T228_EXACT_FAMILY_COMPOSITION_R1"
OWNER_CONVERSATION_ID = "01a1390c-32fd-7952-93dd-9d7be2549df6"
SOURCE = "src/lottolab/research/b649_min_s2_t248_t228_exact_family_composition_r1.py"
TEST = "tests/unit/test_b649_min_s2_t248_t228_exact_family_composition_r1.py"
RESULT = f"{frozen.DIRECTORY}/b649-min-s2-t248-t228-exact-family-composition-r1-result.json"
PROFILES = ("66655555555421100000", "66655555555332000000")
CAPS = (248, 228)
require = frozen.require
obj = frozen.obj
items = frozen.items
integer = frozen.integer
string = frozen.string
sha = frozen.sha
render = frozen.render
decode = frozen.decode
git = frozen.git
checked_blob = frozen.checked_blob
projection = frozen.projection
profile = frozen.profile
family = frozen.family
Pin = frozen.Pin
Authority = frozen.Authority
type Document = dict[str, object]
type Term = tuple[int, int, int, int, int, int]
type Inputs = tuple[Authority, Authority, Authority]

BASE = Pin(
    "BASE",
    "64c4c6b66640616c44c6cab14d359ba81aacad22",
    "f406bf732ebcd7c962162e27d4f6a4b6c1c9c961",
    f"{frozen.DIRECTORY}/b649-min-s2-three-max-owners-exact-authority-r1-result-"
    "ab4711dc900e529dddfbf27606155c267075d6d854360a28682cc70b947adb7c.json",
    "ab4711dc900e529dddfbf27606155c267075d6d854360a28682cc70b947adb7c",
    frozen.SOURCE,
    "115dd17bf731a2092faf41bbcc874b4b4a4c1e46ab7193841934d14f1e1b9b00",
    frozen.TEST,
    "6c866e9c7acf84526915a1e52887704b22a2092ffa8b7d02b7055adfaf3b4bcd",
)
T248 = Pin(
    "T248",
    "b019943076d40aa87b2f9ad386b85a229d85ad1c",
    "625756f7498740992df66aaedf3a7778ebcdf53a",
    f"{frozen.DIRECTORY}/b649-min-s2-t248-exact-formal-handoff-r2-result.json",
    "ae6ecca0ec9d2b2c0e44d296165cd3f3bb3357cc43ec67068b9c99ffdefeb18b",
    "src/lottolab/research/b649_min_s2_t248_exact_formal_handoff_r2.py",
    "4122a0c6b721baad5e001f62ca3d5a2496f8363323e8002709c473cc7bd200d2",
    "tests/unit/test_b649_min_s2_t248_exact_formal_handoff_r2.py",
    "a354ad4cd5c9f6ae86bbe659ee53f5ae7136171012abc7bca168438d00ce38e3",
)
T228 = Pin(
    "T228",
    "d618e18320316e501ae98ad86e6ca6643b40753d",
    "9a0931008feb48d0bb986e5375f7b1dc49f82793",
    f"{frozen.DIRECTORY}/b649-min-s2-t228-exact-formal-handoff-r2-result.json",
    "7427872b3a56a49a72746e61f16b440eae6b5bc7b18e6df0057a4f64a2f1bce2",
    "src/lottolab/research/b649_min_s2_t228_exact_formal_handoff_r2.py",
    "515a98a0e3c0b6eec54a6acb7461b5d5a40775d4bbfb0dd4b6c0be4d8b4f42f6",
    "tests/unit/test_b649_min_s2_t228_exact_formal_handoff_r2.py",
    "1cca7a43c6564679abbffb14f14e45699e1ec825921990dff676a06e5f6b343d",
)
REPORT_SHA256 = {
    "BASE": "9cf151ef41231c8db040ad750781ceb8570cdcc16507b9daafd5f10df891d865",
    "T248": "d10a25bfef9811c6655b197bce7b703499f67c6b5514b9b6400d6eaa15d3948e",
    "T228": "4c37cfed462f309ac3562ed94d3d2c245d48aab993c8756139892c7664d64f62",
}
T228_REPORT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_MIN_S2_T228_EXACT_FORMAL_HANDOFF_R2/.task-data/t228-r2/fresh-judge-report.md"
)


def acceptance(pin: Pin, message: str, report: str) -> Document:
    accepted = frozen.inherited.acceptance(pin, message)
    declared = re.findall(r"(?m)^Judge-report-SHA256: ([0-9a-f]{64})$", message)
    require(declared == [REPORT_SHA256[pin.tag]], "wrong terminal Judge report identity")
    require(
        sha(report.encode()) == REPORT_SHA256[pin.tag]
        and "VERIFIED_WITH_CAVEATS" in report
        and "JUDGE_MODE: FRESH_CONTEXT" in report
        and pin.tree in report
        and pin.result_sha256 in report,
        "wrong Fresh Judge report/tree/result binding",
    )
    if pin != BASE:
        require("Scientific-acceptance: YES\n" in message, "missing scientific acceptance")
    return {
        **accepted,
        "JUDGE_MODE": "FRESH_CONTEXT",
        "REPORT_SHA256": declared[0],
        "REPORT_VERBATIM": report,
        "DISPOSITION": "Formal acceptance; original seal-time source status remains unchanged",
    }


def load_report(pin: Pin, message: str) -> str:
    if pin != T228:
        return (
            message.split("FRESH_JUDGE_REPORT_VERBATIM_BEGIN\n", 1)[1].split(
                "\nFRESH_JUDGE_REPORT_VERBATIM_END", 1
            )[0]
            + "\n"
        )
    if T228_REPORT.exists():
        require(stat.S_ISREG(T228_REPORT.lstat().st_mode), "unsafe donor Judge report")
        return T228_REPORT.read_text()
    # Portable replay uses the separately hash-pinned report carried by this result.
    path = ROOT / RESULT
    require(path.exists() and stat.S_ISREG(path.lstat().st_mode), "missing T228 Judge report")
    sealed = decode(path.read_bytes())
    return string(obj(obj(obj(sealed["PROVENANCE"])["T228"])["ACCEPTANCE"])["REPORT_VERBATIM"])


def load_inputs() -> Inputs:
    loaded: list[Authority] = []
    for pin in (BASE, T248, T228):
        frozen.identity(pin.head, pin.tree)
        raw = checked_blob(pin.head, pin.result, pin.result_sha256)
        result = decode(raw)
        require(render(result) == raw, "noncanonical immutable result")
        source = checked_blob(pin.head, pin.source, pin.source_sha256)
        checked_blob(pin.head, pin.test, pin.test_sha256)
        key = "SOURCE_SHA256" if pin == T228 else "IMPLEMENTATION_SHA256"
        require(
            result[key] == pin.source_sha256 and result["TEST_SHA256"] == pin.test_sha256,
            "source/result identity differs",
        )
        message = git("cat-file", "commit", pin.head).split(b"\n\n", 1)[1].decode()
        accepted = acceptance(pin, message, load_report(pin, message))
        for path, digest in obj(result.get("SOURCE_PINS", {})).items():
            expected = string(digest)
            checked_blob(pin.head, path, expected)
            raw_source = checked_blob(BASE.head, path, expected)
            local = ROOT / path
            require(
                stat.S_ISREG(local.lstat().st_mode) and local.read_bytes() == raw_source,
                f"frozen evaluator drift: {path}",
            )
        if pin == BASE:
            for path, digest in (
                (pin.result, pin.result_sha256),
                (pin.source, pin.source_sha256),
                (pin.test, pin.test_sha256),
            ):
                local = ROOT / path
                require(
                    stat.S_ISREG(local.lstat().st_mode)
                    and local.read_bytes() == checked_blob(pin.head, path, digest),
                    "Base drift",
                )
        loaded.append(Authority(pin, result, source, message, accepted))
    require(not any(n.startswith("ortools") for n in sys.modules), "solver loaded")
    return loaded[0], loaded[1], loaded[2]


def validate_inputs(inputs: Inputs) -> None:
    require(tuple(a.pin for a in inputs) == (BASE, T248, T228), "wrong source identity")
    for a in inputs:
        require(sha(render(a.result)) == a.pin.result_sha256, "altered immutable result")
        require(sha(a.source) == a.pin.source_sha256, "altered immutable source")
        require(
            a.acceptance == acceptance(a.pin, a.message, string(a.acceptance["REPORT_VERBATIM"])),
            "altered acceptance record",
        )
        if a.pin != BASE:
            require(
                ast.get_docstring(ast.parse(a.source), clean=False) == a.result["PROOF"],
                "certificate proof/source differs",
            )


def replay_base(base: Document) -> tuple[dict[str, int], Document]:
    require(sha(render(base)) == BASE.result_sha256, "altered Base authority")
    rows = {p: integer(v) for p, v in obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(base["CURSOR"])
    coarse, ids = obj(cursor["COARSE_BOUND_PROJECTION"]), items(cursor["PROFILE_IDS"])
    require(len(rows) == integer(base["ROWS_TOTAL"]) == 4647, "missing resolved rows")
    require(
        len(coarse) == len(ids) == integer(cursor["PROFILE_COUNT"]) == 197
        and set(coarse) == set(ids)
        and not set(rows).intersection(coarse),
        "cursor coverage",
    )
    for pid in [*rows, *coarse]:
        profile(pid)
    require(sha(projection(rows)) == base["BOUNDS_SHA256_AFTER"], "row projection differs")
    require(sha(render(cursor)) == base["CURSOR_SHA256"], "cursor digest differs")
    for pid, bound in coarse.items():
        require(
            frozen.route.r28.coarse_profile_envelope(profile(pid)).family_upper_bound
            == integer(bound),
            "cursor bound differs",
        )
    require(max(integer(v) for v in coarse.values()) == cursor["BOUND"], "cursor max differs")
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


def envelope(pid: str, cap: int, constant: int | None = None) -> list[Term]:
    require(pid in PROFILES, "wrong envelope profile")
    require(type(cap) is int and cap in (265, CAPS[PROFILES.index(pid)]), "wrong envelope cap")
    d = profile(pid)
    g = [6 + x for x in d]
    w, third = sum(comb(x, 2) for x in g), sum(comb(x, 3) for x in g)
    a_max = sum(x * (4 + x) for x in d) // 3
    derived = (max(g) - 2) * w - third
    require((w, a_max) == (828, 198), "wrong envelope model")
    require(
        constant is None or (type(constant) is int and constant == derived), "wrong K4 constant"
    )
    require(frozen.route.r28.profile_s4_floor(d) == 112, "wrong inherited S4 floor")
    terms: list[Term] = []
    for t in range(22, cap + 1):
        q = max(0, -(-((max(g) - 2) * 3 * t - derived) // 4))
        contained = min(q, a_max)
        s4 = max(112, 679 * q - 231 * contained)
        s3 = 2800 * (w - 3 * t) + 20272 * (t - 22) + 7000 * 22
        total = 372228640 - 63838600 + s3
        exact = Fraction(total) - Fraction(4 * s4, 7)
        bound = -(-exact.numerator // exact.denominator)
        require(bound == (7 * total - 4 * s4 + 6) // 7, "integer/rational ceiling differs")
        terms.append((t, bound, q, contained, s4, s3))
    require(terms == frozen.route.route_b_envelope(d, cap, 112), "frozen Route-B terms differ")
    return terms


def certificates(inputs: Inputs) -> dict[str, Document]:
    validate_inputs(inputs)
    base = inputs[0].result
    certs: dict[str, Document] = {}
    for a, pid, cap in zip(inputs[1:], PROFILES, CAPS, strict=True):
        r, facts = a.result, obj(a.result["MODEL_FACTS"])
        require(
            r["BASE_HEAD"] == BASE.head
            and r["BASE_TREE"] == BASE.tree
            and r["BASE_RESULT_SHA256"] == BASE.result_sha256,
            "donor Base identity differs",
        )
        require(r["TARGET_PROFILE"] == pid and facts["D"] == list(profile(pid)), "wrong profile")
        model = obj(facts["MODEL"])
        expected: Document = (
            {
                "TICKETS": 20,
                "DISTINCT_LABELS_PER_TICKET": 6,
                "TRIPLES": 22,
                "PAIRS": 27,
                "SUPPORT_SIZES": [2, 3],
                "PAIR_LINEARITY": True,
            }
            if a.pin == T248
            else frozen.R2_MODEL
        )
        require(render(model) == render(expected), "wrong frozen support model")
        require(facts["W"] == 828 and facts["A_MAX"] == 198, "wrong model constants")
        if a.pin == T248:
            require(r["INHERITED_BASE_RESULT_VERBATIM"] == base, "donor inherited Base differs")
            require(
                r["NEW_PROVEN_T_CAP"] == cap == obj(r["ENUMERATION"])["NEW_PROVEN_T_CAP"]
                and r["OLD_T_CAP"] == 265
                and r["K4_CONSTANT"] == 5954,
                "wrong T248 cap/constants",
            )
            old_stored, new_stored = r["OLD_TERMS"], r["NEW_TERMS"]
            old_count, new_count = r["OLD_TERM_COUNT"], r["NEW_TERM_COUNT"]
            require(
                obj(r["ENUMERATION"])["LEGACY_DIGEST_MATCH"] == "NOT_VERIFIED", "legacy upgrade"
            )
        else:
            require(
                r["NEW_PROVEN_CAP"] == cap == obj(r["ENUMERATION"])["UNIVERSAL_T_CAP"]
                and r["CURRENT_CAP"] == 265
                and facts["K4_CONSTANT"] == 5956,
                "wrong T228 cap/constants",
            )
            e = obj(r["ENVELOPE"])
            old_stored, new_stored = e["OLD_TERMS"], e["NEW_TERMS"]
            old_count, new_count = e["OLD_T_TERMS"], e["NEW_T_TERMS"]
            require(obj(r["FAMILY"])["S5_ADOPTED_FOR_TARGET"] is False, "target S5 adoption")
        old, new = envelope(pid, 265), envelope(pid, cap)
        require(
            old_stored == [list(t) for t in old]
            and new_stored == [list(t) for t in new]
            and (old_count, new_count) == (len(old), len(new))
            and old[: len(new)] == new,
            "incomplete old/new envelope",
        )
        before, after = max(t[1] for t in old), max(t[1] for t in new)
        require(
            before == obj(base["RESOLVED_ROW_BOUNDS"])[pid]
            and after == r["FULL_PROFILE_BOUND"]
            and r["INCUMBENT"] == base["INCUMBENT"]
            and after <= integer(base["INCUMBENT"]),
            "wrong full-profile envelope bound",
        )
        certs[pid] = {
            "PROFILE_ID": pid,
            "T_CAP": cap,
            "OLD_T_CAP": 265,
            "S4_FLOOR": 112,
            "S5_ADOPTED": False,
            "K4_CONSTANT": 5954 if a.pin == T248 else 5956,
            "FULL_PROFILE_BOUND": after,
            "PRE_UPDATE_BOUND": before,
            "OLD_TERM_COUNT": len(old),
            "NEW_TERM_COUNT": len(new),
            "OLD_TERMS": [list(t) for t in old],
            "NEW_TERMS": [list(t) for t in new],
            "MAXIMIZING_TERMS": [list(t) for t in new if t[1] == after],
            "STRICT_GAIN_EXCLUDED": True,
            "LEGAL_ATTAINMENT": "UNKNOWN",
            "SOURCE_HEAD": a.pin.head,
            "SOURCE_TREE": a.pin.tree,
        }
    return certs


def compose(
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    inputs: Inputs,
    updates: Sequence[tuple[str, int, int]],
) -> dict[str, int]:
    certs = certificates(inputs)
    frozen_rows, frozen_cursor = replay_base(inputs[0].result)
    before = dict(rows)
    require(
        len(rows) == len(before) == len(frozen_rows)
        and before == frozen_rows
        and all(type(b) is int for _, b in rows),
        "missing, duplicate or altered row",
    )
    require(render(cursor) == render(frozen_cursor), "cursor mutation")
    require(
        len(updates) == len({p for p, _, _ in updates}) == 2
        and {p for p, _, _ in updates} == set(PROFILES),
        "missing, duplicate or wrong-profile update",
    )
    after = dict(before)
    for pid, cap, bound in updates:
        require(type(cap) is int and cap == certs[pid]["T_CAP"], "wrong update cap")
        require(
            type(bound) is int and bound == integer(certs[pid]["FULL_PROFILE_BOUND"]) < before[pid],
            "wrong update bound",
        )
        after[pid] = bound
    require(
        {p for p in before if before[p] != after[p]} == set(PROFILES), "not exactly two updates"
    )
    require(
        projection({p: b for p, b in before.items() if p not in PROFILES})
        == projection({p: b for p, b in after.items() if p not in PROFILES}),
        "other rows changed",
    )
    return after


def compute_result(inputs: Inputs | None = None) -> Document:
    sources = load_inputs() if inputs is None else inputs
    certs = certificates(sources)
    before, cursor = replay_base(sources[0].result)
    updates = [
        (p, integer(certs[p]["T_CAP"]), integer(certs[p]["FULL_PROFILE_BOUND"])) for p in PROFILES
    ]
    after = compose(list(before.items()), cursor, sources, updates)
    first, old_owners = family(before, cursor)
    last, owners = family(after, cursor)
    incumbent = integer(sources[0].result["INCUMBENT"])
    all_rows = {
        **after,
        **{p: integer(v) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()},
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_LIFECYCLE",
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "IMPLEMENTATION_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "PROVENANCE": {
            a.pin.tag: {
                "HEAD": a.pin.head,
                "TREE": a.pin.tree,
                "RESULT": a.pin.result,
                "RESULT_SHA256": a.pin.result_sha256,
                "SOURCE_SHA256": a.pin.source_sha256,
                "TEST_SHA256": a.pin.test_sha256,
                "ACCEPTANCE": a.acceptance,
                "ORIGINAL_RESULT_VERBATIM": a.result,
            }
            for a in sources
        },
        "PROFILE_CERTIFICATES": certs,
        "ROWS_TOTAL": len(before),
        "ROWS_UPDATED": len(updates),
        "ROW_UPDATES": {p: {"BEFORE": before[p], "AFTER": after[p]} for p in PROFILES},
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "OTHER_ROWS_UNCHANGED": "PASS",
        "OTHER_4645_BOUNDS_SHA256": sha(
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
        "STILL_OPEN_PROFILE_COUNT": sum(b > incumbent for b in all_rows.values()),
        "NEWLY_STRICT_GAIN_EXCLUDED_PROFILE_IDS": sorted(
            p for p in PROFILES if before[p] > incumbent >= after[p]
        ),
        "INHERITED_CAVEATS": "PRESERVED_VERBATIM",
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "MATHEMATICAL_THEOREMS_REEXECUTED": 0,
        "GRAPHS_ENUMERATED": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "SOLVER_CALLS": 0,
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "RUN1_MUTATED": "NO",
        "EXISTING_CERTIFICATES_MUTATED": "NO",
        "HISTORICAL_SHARED_REF_DRIFT": "INHERITED; NOT_REATTRIBUTED_OR_REPAIRED",
        "TASK_OWNED_GIT_SCOPE": "New worktree/branch, index, objects and one intended local commit",
        "G01_TO_G18_AT_SEAL": {f"G{i:02}": "NOT_VERIFIED" for i in range(1, 19)},
        "GATE_STATUS_SCOPE": "Acceptance in external exact-tree Judge; lifecycle in commit/handoff",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = ROOT / RESULT
    require(not args.verify or path.exists(), "missing sealed result")
    raw = render(compute_result())
    if path.exists():
        require(
            stat.S_ISREG(path.lstat().st_mode) and path.read_bytes() == raw,
            "exact result replay differs",
        )
    else:
        with path.open("xb") as output:
            output.write(raw)
    result = decode(raw)
    print(
        render(
            {
                k: result[k]
                for k in (
                    "ROWS_TOTAL",
                    "ROWS_UPDATED",
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
