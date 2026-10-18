"""Compose accepted T244/T259 and T249 certificates, without re-proving them.

The base's complete 4647-row bound projection and cursor are immutable inputs.
The sibling donor's exact result and external fresh Judge reports are pinned.
Replay every integer T in each accepted full-profile envelope, substitute only
the T249 row in a copy, and derive the family maximum, ties and open profiles.
This remains a bound projection: inherited metadata, attainability, historical
resource/source limitations and pre-Judge status snapshots are not upgraded.
Bonferroni-5 is not adopted. No theorem enumeration or solver is executed.
"""

from __future__ import annotations

import ast
import json
import stat
import sys
from collections.abc import Mapping, Sequence
from fractions import Fraction
from math import comb
from pathlib import Path

from . import b649_min_s2_two_tied_owner_exact_cert_r1 as inherited

TASK_ID = "B649_MIN_S2_T249_DUAL_PROFILE_EXACT_COMPOSITION_R1"
OWNER_CONVERSATION_ID = "01a13016-b30b-7961-aa4c-78adfb89b61a"
ROOT = Path(__file__).resolve().parents[3]
BASE_HEAD = "d0785605aefeff33d55d2763e9e8660ba298762d"
BASE_TREE = "d6e08905b87f1e8208ac7fe892f5b51278e1a9f7"
DONOR_HEAD = "42b8b74f3d4110a8ab4e51544f7756e0701c5e95"
DONOR_TREE = "4f61bfa8ce7f4afdd2800e654ed7fae89599228c"
DIRECTORY = "docs/research/matrix-native-results"
BASE_RESULT = f"{DIRECTORY}/b649-min-s2-two-tied-owner-exact-cert-r1-result.json"
BASE_RESULT_SHA = "a56c20bcabb430e9d84b177e3ad4dc27c82b25a0befa516cbbd6046030c0a7cd"
BASE_SOURCE_SHA = "cedbb029d20367fb42aa3c9be24dea7d3553ac7a930af766db1045ef5a6239a5"
BASE_BOUNDS_SHA = "0beac830bb0933d88155416839621317ebf7d6d61044c55ddf29e9cc0f923a90"
CURSOR_SHA = "e6ae5e01753b2fa2e0c4c78c5eab0cd45b3c0471e2229bb0eecf0ef4d3cefb64"
DONOR_RESULT = f"{DIRECTORY}/b649-min-s2-goodman-r2-t249-formal-cert-r1-result.json"
DONOR_RESULT_SHA = "2e019bd686cd49e7ed8539a8d56f66c7aa2835eb087538cd99e5fc8b4e03d694"
DONOR_SOURCE = "src/lottolab/research/b649_min_s2_goodman_r2_t249_formal_cert_r1.py"
DONOR_SOURCE_SHA = "38ae72a6ca8b7d8dfc7bfd93cb89ea82731c6975dc53218629a91da7ea73c643"
SOURCE = "src/lottolab/research/b649_min_s2_t249_dual_profile_composition_r1.py"
SOURCES = f"{DIRECTORY}/b649-min-s2-t249-dual-profile-composition-r1-sources"
EVIDENCE_PINS = {
    "base-judge.txt": "94e6640b7362f6e709e3322706ad54e85ed475c4916e15fc6371e0993c954dd7",
    "donor-judge.json": "d2d6490c6b40b8751e31f65b050ec14ac4702f983579a0176672e507f02186b9",
    "donor-result.json": DONOR_RESULT_SHA,
}
RESULT_PATH = ROOT / DIRECTORY / "b649-min-s2-t249-dual-profile-composition-r1-result.json"
TARGET = "66665555554421100000"
CAP = 249
TARGETS = (*inherited.TARGETS, TARGET)
require, obj, items, integer, string = (
    inherited.require,
    inherited.obj,
    inherited.items,
    inherited.integer,
    inherited.string,
)
sha, render, projection, git, blob = (
    inherited.sha,
    inherited.render,
    inherited.projection,
    inherited.git,
    inherited.blob,
)
decode = inherited.prior.decode
type Term = tuple[int, int, int, int, int, int]
type Inputs = tuple[dict[str, object], dict[str, object], dict[str, object]]


def local_blob(relative: str, expected: str) -> bytes:
    path = ROOT / relative
    require(stat.S_ISREG(path.lstat().st_mode), f"missing/unsafe local source: {relative}")
    raw = path.read_bytes()
    require(sha(raw) == expected, f"source-hash mismatch: {relative}")
    return raw


def source_pins(base: Mapping[str, object]) -> dict[str, str]:
    pins = {p: string(v) for p, v in obj(obj(base["PROVENANCE"])["MODULE_SHA256"]).items()}
    pins["src/lottolab/research/b649_min_s2_two_tied_owner_exact_cert_r1.py"] = BASE_SOURCE_SHA
    loaded: set[str] = set()
    for name, module in sys.modules.copy().items():
        if name.startswith("lottolab.research.") and name != __name__:
            require(module.__file__ is not None, "research module without source")
            path = Path(string(module.__file__)).resolve()
            require(path.is_relative_to(ROOT), "research helper outside isolated worktree")
            loaded.add(path.relative_to(ROOT).as_posix())
    require(loaded == set(pins), "loaded research source closure differs")
    for path, digest in pins.items():
        require(local_blob(path, digest) == blob(BASE_HEAD, path, digest), "helper source differs")
    require(not any(name.startswith("ortools") for name in sys.modules), "solver loaded")
    return dict(sorted(pins.items()))


def judges() -> dict[str, object]:
    raw = {name: local_blob(f"{SOURCES}/{name}", digest) for name, digest in EVIDENCE_PINS.items()}
    base_report = raw["base-judge.txt"].decode()
    require(
        base_report.startswith("VERDICT: VERIFIED_WITH_CAVEATS\n")
        and f"EXACT_JUDGED_STAGED_TREE {BASE_TREE}" in base_report
        and BASE_RESULT_SHA in base_report
        and base_report.rstrip().endswith("TERMINAL_VERDICT: VERIFIED_WITH_CAVEATS"),
        "base Judge/tree/result binding differs",
    )
    donor_report = decode(raw["donor-judge.json"])
    require(
        donor_report["judge_thread_id"] == "01a12f7e-7955-7890-85a9-981a6f780f09",
        "donor Judge identity differs",
    )
    reports = [obj(v) for v in items(donor_report["reports_newest_first"])]
    require(len(reports) == 2, "missing donor scientific/lifecycle Judge report")
    final, scientific = (string(v["report"]) for v in reports)
    require(
        final.startswith("VERIFIED_WITH_CAVEATS — G01\u2013G15 all PASS.")
        and f"Final HEAD: `{DONOR_HEAD}`" in final
        and f"Final tree / JUDGED_TREE: `{DONOR_TREE}`" in final
        and "JUDGE_MODE: FRESH_CONTEXT" in final
        and "JUDGE_MODE: FRESH_CONTEXT" in scientific
        and f"JUDGED_TREE: `{DONOR_TREE}`" in scientific,
        "donor Judge/tree binding differs",
    )
    return {
        "BASE": {"STATUS": "VERIFIED_WITH_CAVEATS", "REPORT": f"{SOURCES}/base-judge.txt"},
        "DONOR": {
            "STATUS": "VERIFIED_WITH_CAVEATS",
            "REPORT": f"{SOURCES}/donor-judge.json",
            "JUDGE_THREAD_ID": donor_report["judge_thread_id"],
            "REPORTS_VERBATIM": reports,
        },
        "SOURCE_SHA256": EVIDENCE_PINS,
    }


def load_inputs() -> Inputs:
    base_message = inherited.prior.commit_identity(BASE_HEAD, BASE_TREE)
    donor_message = inherited.prior.commit_identity(DONOR_HEAD, DONOR_TREE)
    common = git("rev-parse", f"{BASE_HEAD}^").decode().strip()
    require(git("rev-parse", f"{DONOR_HEAD}^").decode().strip() == common, "not sibling donors")
    base_raw = blob(BASE_HEAD, BASE_RESULT, BASE_RESULT_SHA)
    require(local_blob(BASE_RESULT, BASE_RESULT_SHA) == base_raw, "base authority changed")
    donor_raw = blob(DONOR_HEAD, DONOR_RESULT, DONOR_RESULT_SHA)
    require(
        local_blob(f"{SOURCES}/donor-result.json", DONOR_RESULT_SHA) == donor_raw,
        "donor snapshot differs from committed result",
    )
    base, donor = decode(base_raw), decode(donor_raw)
    source = blob(DONOR_HEAD, DONOR_SOURCE, DONOR_SOURCE_SHA)
    require(
        donor["IMPLEMENTATION_SHA256"] == DONOR_SOURCE_SHA
        and ast.get_docstring(ast.parse(source), clean=False) == donor["PROOF"],
        "donor source/proof/result binding differs",
    )
    require(
        base["BASE_HEAD"] == donor["BASE_HEAD"] == common
        and base["BASE_TREE"] == donor["BASE_TREE"]
        and base["FROZEN_RESULT"] == obj(donor["BASE_AUTHORITY"])["RESULT"]
        and base["FROZEN_RESULT_SHA256"] == obj(donor["BASE_AUTHORITY"])["SHA256"],
        "common inherited authority differs",
    )
    provenance: dict[str, object] = {
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT": BASE_RESULT,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA,
        "DONOR_HEAD": DONOR_HEAD,
        "DONOR_TREE": DONOR_TREE,
        "DONOR_RESULT": DONOR_RESULT,
        "DONOR_RESULT_SHA256": DONOR_RESULT_SHA,
        "DONOR_SOURCE": DONOR_SOURCE,
        "DONOR_SOURCE_SHA256": DONOR_SOURCE_SHA,
        "COMMON_PARENT": common,
        "BASE_COMMIT_MESSAGE_VERBATIM": base_message,
        "DONOR_COMMIT_MESSAGE_VERBATIM": donor_message,
        "SOURCE_PINS": source_pins(base),
        "EXTERNAL_JUDGES": judges(),
    }
    return base, donor, provenance


def route_b(pid: str, cap: int, s4_base: int = 112) -> list[Term]:
    require(pid in TARGETS, "wrong profile for certificate replay")
    require(type(cap) is int and 22 <= cap <= 265, "wrong T domain")
    require(type(s4_base) is int and s4_base == 112, "wrong S4 base")
    d = tuple(map(int, pid))
    g = tuple(6 + v for v in d)
    w, c3 = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    amax = sum(v * (degree - 2) for v, degree in zip(d, g, strict=True)) // 3
    out: list[Term] = []
    for t in range(22, cap + 1):
        excess = c3 - (max(g) - 2) * (w - 3 * t)
        k4 = max(0, (excess + 3) // 4)
        contained = min(k4, amax)
        s4 = max(s4_base, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        numerator = 7 * (372_228_640 - 63_838_600 + s3) - 4 * s4
        bound = (numerator + 6) // 7
        rational = Fraction(372_228_640 - 63_838_600 + s3) - Fraction(4 * s4, 7)
        require(0 <= bound - rational < 1, "integer ceiling differs")
        out.append((t, bound, k4, contained, s4, s3))
    require(
        out
        == inherited.official.route_b_envelope(d, cap, s4_base)
        == inherited.split.route_b_terms(d, cap, s4_base),
        "accepted Route-B implementations differ",
    )
    return out


def validate_donor(donor: Mapping[str, object]) -> tuple[int, list[Term]]:
    require(donor["TARGET_PROFILE"] == TARGET, "wrong donor profile")
    theorem, model = obj(donor["THEOREM"]), obj(donor["SUPPORT_MODEL"])
    cap = integer(theorem["T_CAP"])
    require(
        theorem["STATUS"] == "PROVEN"
        and cap == CAP
        and model["PROFILE"] == TARGET
        and model["T_MIN"] == 22
        and integer(model["T_PLUS_I"]) - integer(theorem["I_FLOOR"]) == cap
        and min(integer(v) for v in items(obj(theorem["ENUMERATION"])["I_FLOORS"]))
        == theorem["I_FLOOR"],
        "donor certified full T scope differs",
    )
    require(
        obj(donor["HISTORICAL_R2"])["BONFERRONI_5_USED"] == "NO"
        and obj(donor["HISTORICAL_R2"])["HISTORICAL_U64_BOUND_USED"] == "NO",
        "unadopted objective/certificate included",
    )
    after = obj(obj(donor["ROW_UPDATE"])["AFTER"])
    terms = route_b(TARGET, cap, integer(after["s4_base"]))
    recorded = obj(donor["ROUTE_B"])
    bound = max(term[1] for term in terms)
    require(
        recorded["ALL_T_TERMS"] == [list(term) for term in terms]
        and recorded["TERM_COUNT"] == len(terms)
        and recorded["MAXIMIZING_T"] in [t[0] for t in terms if t[1] == bound]
        and recorded["S4_FLOOR_AT_CAP"] == terms[-1][4]
        and after["cap"] == cap
        and type(after["bound"]) is int
        and after["bound"] == donor["PROFILE_BOUND"] == bound,
        "donor full-profile bound/domain mismatch",
    )
    return bound, terms


def validate_rows(rows: Sequence[tuple[str, int]]) -> dict[str, int]:
    require(len(rows) == 4647 and len({p for p, _ in rows}) == 4647, "wrong/duplicate row count")
    require(all(type(v) is int for _, v in rows), "noninteger bound row")
    require(all(sum(p == target for p, _ in rows) == 1 for target in TARGETS), "missing target row")
    bounds = dict(rows)
    require(sha(projection(bounds)) == BASE_BOUNDS_SHA, "base bound projection mismatch")
    return bounds


def validate_cursor(cursor: Mapping[str, object], expected: Mapping[str, object]) -> None:
    require(sha(render(expected)) == CURSOR_SHA, "expected cursor source-hash mismatch")
    inherited.validate_cursor(cursor, expected)


def compose(
    bounds: Mapping[str, int],
    cursor: Mapping[str, object],
    expected_cursor: Mapping[str, object],
    donor: Mapping[str, object],
    pid: str,
    bound: int,
) -> dict[str, int]:
    before = validate_rows(list(bounds.items()))
    validate_cursor(cursor, expected_cursor)
    require(not set(before).intersection(obj(cursor["COARSE_BOUND_PROJECTION"])), "cursor overlap")
    certified, _ = validate_donor(donor)
    require(pid == TARGET, "wrong update profile")
    require(type(bound) is int and bound == certified < before[pid], "wrong update bound")
    after = {**before, pid: bound}
    require([p for p in before if after[p] != before[p]] == [pid], "not exactly one changed row")
    others = {p: b for p, b in before.items() if p != pid}
    require(
        len(others) == 4646
        and projection(others) == projection({p: b for p, b in after.items() if p != pid})
        and projection(bounds) == projection(before),
        "other rows or input changed",
    )
    return after


def family(bounds: Mapping[str, int], cursor: Mapping[str, object]) -> tuple[int, list[str]]:
    terms = [
        *bounds.items(),
        *[(p, integer(v)) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()],
    ]
    require(len({p for p, _ in terms}) == len(terms), "family cursor overlap")
    maximum = max(b for _, b in terms)
    return maximum, sorted(p for p, b in terms if b == maximum)


def compute_result() -> dict[str, object]:
    base, donor, provenance = load_inputs()
    bounds = validate_rows([(p, integer(v)) for p, v in obj(base["RESOLVED_ROW_BOUNDS"]).items()])
    cursor = obj(base["CURSOR"])
    validate_cursor(cursor, obj(obj(donor["BASE_AUTHORITY"])["CURSOR"]))
    incumbent = integer(base["INCUMBENT"])
    inherited_updates = obj(base["ROW_UPDATES"])
    require(set(inherited_updates) == set(inherited.TARGETS), "inherited certificate set differs")
    for pid in inherited.TARGETS:
        update, theorem = obj(inherited_updates[pid]), obj(obj(base["THEOREMS"])[pid])
        cap = integer(update["T_CAP"])
        terms = route_b(pid, cap, integer(update["S4_BASE"]))
        require(
            theorem["STATUS"] == "PROVEN"
            and theorem["TRIANGLE_CAP"] == cap
            and cap == inherited.CAPS[pid]
            and obj(base["ROUTE_B_ENVELOPES"])[pid] == [list(t) for t in terms]
            and bounds[pid] == update["AFTER_BOUND"] == max(t[1] for t in terms),
            "pre-existing certified update differs",
        )
    bound, terms = validate_donor(donor)
    original = obj(obj(donor["ROW_UPDATE"])["BEFORE"])
    require(
        bounds[TARGET]
        == original["bound"]
        == max(t[1] for t in route_b(TARGET, integer(original["cap"])))
        and bound <= incumbent
        and donor["STRICT_GAIN_EXCLUDED"] == "YES",
        "donor prior row/incumbent comparison differs",
    )
    after = compose(bounds, cursor, cursor, donor, TARGET, bound)
    before_max, before_owners = family(bounds, cursor)
    after_max, owners = family(after, cursor)
    require(
        (before_max, before_owners) == (base["FAMILY_BOUND_AFTER"], base["NEW_OWNER_IDS"])
        and (after_max, owners) == inherited.prior.family(after, cursor),
        "independent family maximum/ties differ",
    )
    open_ids = sorted(p for p, b in after.items() if b > incumbent)
    cursor_open = sorted(
        p for p, b in obj(cursor["COARSE_BOUND_PROJECTION"]).items() if integer(b) > incumbent
    )
    inherited_fields = {
        k: v
        for k, v in base.items()
        if k.startswith("INHERITED_")
        or k in ("ATTAINABILITY", "FULL_METADATA_DIGEST_AFTER", "LEDGER_VIEW")
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPOSITION_COMPLETE_PENDING_EXTERNAL_VALIDATION_AND_JUDGE_LIFECYCLE",
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "PROVENANCE": provenance,
        "IMPLEMENTATION_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "SOURCE_LEDGER_ROWS": len(bounds),
        "ROWS_UPDATED": 1,
        "ROW_UPDATE": {
            "PROFILE_ID": TARGET,
            "BEFORE": original,
            "AFTER": obj(obj(donor["ROW_UPDATE"])["AFTER"]),
        },
        "OTHER_ROWS_UNCHANGED": "PASS",
        "OTHER_4646_BOUNDS_SHA256": sha(
            projection({p: b for p, b in bounds.items() if p != TARGET})
        ),
        "BOUNDS_SHA256_BEFORE": sha(projection(bounds)),
        "BOUNDS_SHA256_AFTER": sha(projection(after)),
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "INHERITED_TWO_PROFILE_ROW_UPDATES_VERBATIM": inherited_updates,
        "INHERITED_TWO_PROFILE_THEOREMS_VERBATIM": base["THEOREMS"],
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": inherited_fields,
        "DONOR_THEOREM_VERBATIM": donor["THEOREM"],
        "DONOR_STATUS_SNAPSHOTS_VERBATIM": {
            "TASK_STATUS": donor["TASK_STATUS"],
            "BASE_AUTHORITY": donor["BASE_AUTHORITY"],
            "HISTORICAL_R2": donor["HISTORICAL_R2"],
            "SCENARIO_2_STATUS": obj(obj(donor["FAMILY_SCENARIOS"])["SCENARIO_2"])["STATUS"],
        },
        "ROUTE_B": {
            "ALL_T_TERMS": [list(t) for t in terms],
            "T_DOMAIN": [terms[0][0], terms[-1][0]],
            "TERM_COUNT": len(terms),
        },
        "STRICT_GAIN_EXCLUDED": "YES",
        "DISTANCE_BELOW_INCUMBENT": incumbent - bound,
        "CURSOR": cursor,
        "CURSOR_PRESERVED": "PASS",
        "CURSOR_SHA256_BEFORE": sha(render(cursor)),
        "CURSOR_SHA256_AFTER": sha(render(cursor)),
        "FAMILY_BOUND_BEFORE": before_max,
        "FAMILY_BOUND_AFTER": after_max,
        "EXACT_FAMILY_DELTA": before_max - after_max,
        "FAMILY_OWNER_IDS_BEFORE": before_owners,
        "FAMILY_OWNER_IDS": owners,
        "INCUMBENT": incumbent,
        "GAP_TO_INCUMBENT": after_max - incumbent,
        "RESOLVED_OPEN_PROFILE_IDS": open_ids,
        "RESOLVED_OPEN_PROFILE_COUNT": len(open_ids),
        "UNRESOLVED_CURSOR_PROFILE_COUNT": cursor["PROFILE_COUNT"],
        "STILL_OPEN_PROFILE_COUNT": len(open_ids) + len(cursor_open),
        "CERTIFICATES_ADOPTED": {**inherited.CAPS, TARGET: CAP},
        "BONFERRONI_5_ADOPTED": "NO",
        "G01_TO_G15_AT_COMPOSITION": {
            f"G{i:02}": "PASS" if i <= 11 else "NOT_VERIFIED" for i in range(1, 16)
        },
        "GATE_STATUS_SCOPE": (
            "G12-G15 require external test/lint/typecheck, Fresh Judge and post-Judge "
            "commit/release evidence; see handoff and commit message."
        ),
        "MATHEMATICAL_THEOREMS_REEXECUTED": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "SCIENTIFIC_SOURCE_OUTSIDE_TASK_CHANGED": "NO",
        "RUN1_MUTATED": "NO",
        "SHARED_LEDGER_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
    }


def main() -> None:
    raw = render(compute_result())
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == raw, "sealed composition result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(raw)
    print(json.dumps({"RESULT": str(RESULT_PATH), "SHA256": sha(raw)}))


if __name__ == "__main__":
    main()
