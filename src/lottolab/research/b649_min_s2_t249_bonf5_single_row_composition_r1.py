"""Compose one accepted Bonferroni-5 cap-term certificate into T249 authority.

Replay the inherited bound projection, without re-executing any theorem or
solver. Rebuild all integer T terms using the accepted Route-B semantics,
apply min(B4, B5) only at the donor's certified cap, and maximize the complete
envelope. Replace exactly one resolved row in memory. The other 4646 rows and
the complete 197-member cursor remain immutable. Original SELF_CHECK_ONLY and
subsequent VERIFIED dispositions are separate; inherited caveats are retained.
Family maxima, all ties, deltas and open-profile counts are derived, with no
expected family result or owner set used as an acceptance constant.
"""

from __future__ import annotations

import argparse
import ast
import json
import stat
import sys
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path

from . import b649_min_s2_t249_dual_profile_composition_r1 as base

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_T249_BONF5_SINGLE_ROW_COMPOSITION_R1"
OWNER_CONVERSATION_ID = "01a13056-4de1-7d81-8cd7-f6540662f9d4"
BASE_HEAD = "7ae9c7c332119926ee2282da7dd205bdcef6afdf"
BASE_TREE = "9f32fcfcf63cf93e78014b3f5a33155673d4b1b6"
DONOR_HEAD = "8fac3d41b2d519d92b06d6ceb933fe31072c6409"
DONOR_TREE = "62f80eecf3f1045c905d345a3e68fb2ad078eaec"
DIRECTORY = base.DIRECTORY
BASE_RESULT = f"{DIRECTORY}/b649-min-s2-t249-dual-profile-composition-r1-result.json"
BASE_SHA = "5c0aca19ec5e703e3de35abca804380aabdb82dfaaec40f36d0a3e760938e493"
DONOR_RESULT = f"{DIRECTORY}/b649-min-s2-bonferroni5-target-cert-r1-result.json"
DONOR_SHA = "dc0ffab7c48e5a651375f7773e495d869d4211273ff3ff3b1423c5b10c1f7d9b"
DONOR_SOURCE = "src/lottolab/research/b649_min_s2_bonferroni5_target_cert_r1.py"
DONOR_SOURCE_SHA = "037e4629e681dbb695b920fa5f06fffccff5b8aa12121e3433f5b48f354c9cdd"
BASE_SOURCE = "src/lottolab/research/b649_min_s2_t249_dual_profile_composition_r1.py"
BASE_SOURCE_SHA = "08dcc4b07e97710d7755e9cbdbbd452965c281300cc16e40535af89e5c9d4941"
SOURCE = "src/lottolab/research/b649_min_s2_t249_bonf5_single_row_composition_r1.py"
SOURCES = f"{DIRECTORY}/b649-min-s2-t249-bonf5-single-row-composition-r1-sources"
REPORT_PINS = {
    "base-judge.md": "95f5231dbbccbe04d758353e27789adb604a9357440090a83208644414025991",
    "donor-judge.json": "8e1427db9e7d48552fd993c21a9bfc7ee1e44b6b10443630c40a08bab4944200",
}
RESULT_PATH = ROOT / DIRECTORY / "b649-min-s2-t249-bonf5-single-row-composition-r1-result.json"
TARGET = "65555555555550000000"
ORIGINAL_DONOR = "e3a9843db4339167bffcdc92fb782ff6bb663ed8"
require, obj, items, integer, string = base.require, base.obj, base.items, base.integer, base.string
sha, render, projection, git, blob, decode = (
    base.sha,
    base.render,
    base.projection,
    base.git,
    base.blob,
    base.decode,
)
type Inputs = tuple[dict[str, object], dict[str, object], dict[str, object]]
type Term = tuple[int, int, int, int, int, int]


def local_blob(path: str, digest: str) -> bytes:
    file = ROOT / path
    require(stat.S_ISREG(file.lstat().st_mode), "unsafe local input")
    raw = file.read_bytes()
    require(sha(raw) == digest, f"source-hash mismatch: {path}")
    return raw


def judges() -> dict[str, object]:
    raw = {p: local_blob(f"{SOURCES}/{p}", h) for p, h in REPORT_PINS.items()}
    prior = raw["base-judge.md"].decode()
    require(
        prior.startswith("VERDICT: VERIFIED_WITH_CAVEATS\n")
        and f"EXACT_JUDGED_STAGED_TREE {BASE_TREE}" in prior
        and BASE_SHA in prior
        and prior.rstrip().endswith("TERMINAL_VERDICT: VERIFIED_WITH_CAVEATS"),
        "base Judge binding differs",
    )
    donor = decode(raw["donor-judge.json"])
    require(donor["judge_thread_id"] == "01a13027-9801-7720-840d-74cd4a10bd3b", "wrong Judge")
    reports = [string(v) for v in items(donor["reports"])]
    require(len(reports) == 1, "missing donor Judge report")
    report = reports[0]
    require(
        report.startswith("VERIFIED — B01\u2013B15 PASS.")
        and "JUDGE_MODE: FRESH_CONTEXT" in report
        and f"JUDGED_HEAD: {DONOR_HEAD}" in report
        and f"JUDGED_TREE: {DONOR_TREE}" in report
        and f"RESULT_SHA256: {DONOR_SHA}" in report,
        "donor Judge binding differs",
    )
    return {
        "BASE": {"STATUS": "VERIFIED_WITH_CAVEATS", "REPORT": f"{SOURCES}/base-judge.md"},
        "DONOR": {"STATUS": "VERIFIED", "REPORT": f"{SOURCES}/donor-judge.json"},
        "REPORT_SHA256": REPORT_PINS,
    }


def load_inputs() -> Inputs:
    for head, tree in ((BASE_HEAD, BASE_TREE), (DONOR_HEAD, DONOR_TREE)):
        require(git("cat-file", "-t", head).strip() == b"commit", "wrong commit identity")
        require(git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "wrong tree")
    sealed = decode(blob(BASE_HEAD, BASE_RESULT, BASE_SHA))
    require(
        local_blob(BASE_RESULT, BASE_SHA) == blob(BASE_HEAD, BASE_RESULT, BASE_SHA), "base drift"
    )
    donor = decode(blob(DONOR_HEAD, DONOR_RESULT, DONOR_SHA))
    source = blob(DONOR_HEAD, DONOR_SOURCE, DONOR_SOURCE_SHA)
    require(
        donor["SOURCE_SHA256"] == DONOR_SOURCE_SHA
        and ast.get_docstring(ast.parse(source), clean=False) == donor["PROOF"],
        "donor source/result binding differs",
    )
    pins = {p: string(h) for p, h in obj(obj(sealed["PROVENANCE"])["SOURCE_PINS"]).items()}
    pins[BASE_SOURCE] = BASE_SOURCE_SHA
    for path, digest in pins.items():
        require(local_blob(path, digest) == blob(BASE_HEAD, path, digest), "helper drift")
    require(not any(n.startswith("ortools") for n in sys.modules), "solver loaded")
    provenance: dict[str, object] = {
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "DONOR_HEAD": DONOR_HEAD,
        "DONOR_TREE": DONOR_TREE,
        "BASE_RESULT": BASE_RESULT,
        "SOURCE_RESULT_SHA256": BASE_SHA,
        "DONOR_RESULT": DONOR_RESULT,
        "DONOR_RESULT_SHA256": DONOR_SHA,
        "SOURCE_PINS": pins,
        "DONOR_SOURCE_SHA256": DONOR_SOURCE_SHA,
        "EXTERNAL_JUDGES": judges(),
        "BASE_COMMIT_MESSAGE_VERBATIM": git("show", "-s", "--format=%B", BASE_HEAD).decode(),
        "DONOR_COMMIT_MESSAGE_VERBATIM": git("show", "-s", "--format=%B", DONOR_HEAD).decode(),
    }
    return sealed, donor, provenance


def validate_rows(rows: Sequence[tuple[str, int]], sealed: Mapping[str, object]) -> dict[str, int]:
    require(len(rows) == len({p for p, _ in rows}) == 4647, "wrong/duplicate row count")
    require(all(type(v) is int for _, v in rows), "noninteger bound")
    bounds = dict(rows)
    require(TARGET in bounds, "missing target")
    require(sha(projection(bounds)) == sealed["BOUNDS_SHA256_AFTER"], "base projection differs")
    return bounds


def replay_base(sealed: Mapping[str, object]) -> dict[str, int]:
    bounds, _ = base.inherited.frozen_authority()
    for pid in base.inherited.TARGETS:
        record = obj(obj(sealed["INHERITED_TWO_PROFILE_ROW_UPDATES_VERBATIM"])[pid])
        terms = base.route_b(pid, integer(record["T_CAP"]), integer(record["S4_BASE"]))
        require(bounds[pid] == record["BEFORE_BOUND"], "inherited old row differs")
        require(max(t[1] for t in terms) == record["AFTER_BOUND"], "inherited envelope differs")
        bounds[pid] = integer(record["AFTER_BOUND"])
    accepted = decode(blob(BASE_HEAD, f"{base.SOURCES}/donor-result.json", base.DONOR_RESULT_SHA))
    bound, _ = base.validate_donor(accepted)
    before = obj(obj(accepted["ROW_UPDATE"])["BEFORE"])
    require(bounds[base.TARGET] == before["bound"], "T249 prior row differs")
    bounds[base.TARGET] = bound
    recorded = {p: integer(v) for p, v in obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    require(bounds == recorded, "complete base replay differs")
    return validate_rows(list(bounds.items()), sealed)


def validate_donor(donor: Mapping[str, object]) -> tuple[int, dict[str, object]]:
    require(donor["PROFILE_ID"] == TARGET, "wrong donor profile")
    require(donor["DONOR_HEAD"] == ORIGINAL_DONOR, "wrong original donor")
    status = obj(donor["DONOR_ORIGINAL_STATUS"])
    require(
        status == {"JUDGE_MODE": "SELF_CHECK_ONLY", "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY"},
        "original donor status changed",
    )
    d = base.inherited.split.profile_values(TARGET)
    cap = integer(donor["TRIANGLE_CAP"])
    proof = obj(donor["CAP_AUTHORITY"])
    r30_path = f"{DIRECTORY}/{base.inherited.official.CAP_SOURCE_RESULT}"
    pin = obj(obj(donor["BLOB_PINS"])[r30_path])
    r30 = decode(blob(string(pin["HEAD"]), r30_path, string(pin["SHA256"])))
    require(
        proof == obj(items(r30["GROUP_ATTEMPTS"])[integer(proof["ATTEMPT_INDEX"])]), "cap drift"
    )
    require(
        proof["PROFILE_IDS"] == [TARGET]
        and proof["TARGET_TRIANGLE_CAP"] == cap
        and base.inherited.official.r28.r26.accepted_cap(proof, (d,), cap) == cap,
        "wrong certified cap/profile",
    )
    original_path = (
        f"{DIRECTORY}/b649-k20-min-s2-three-competing-profiles-bonferroni5-r1-result.json"
    )
    original_pin = obj(obj(donor["BLOB_PINS"])[original_path])
    original = decode(blob(ORIGINAL_DONOR, original_path, string(original_pin["SHA256"])))
    require(original["JUDGE_MODE"] == status["JUDGE_MODE"], "original status differs")
    cert = obj(obj(original["PROFILE_CERTIFICATES"])[TARGET])
    s5 = integer(obj(donor["S5_PROOF"])["S5_CAP"])
    require(s5 == obj(cert["DEGREE_S5_PROOF"])["S5_CAP"], "certified S5 cap differs")
    floor = base.inherited.official.r28.profile_s4_floor(d)
    old = base.inherited.official.route_b_envelope(d, cap, floor)
    require(old == base.inherited.split.route_b_terms(d, cap, floor), "official terms differ")
    terms: list[Term] = []
    fifth = 0
    for t, bound, k4, contained, s4, s3 in old:
        rational = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        require(bound == -(-rational.numerator // rational.denominator), "rational ceiling differs")
        if t == cap:
            fifth = 372228640 - 63838600 + s3 - s4 + s5
            bound = min(bound, fifth)
        terms.append((t, bound, k4, contained, s4, s3))
    envelope = obj(donor["ENVELOPE"])
    best = max(t[1] for t in terms)
    lower_sha = sha(json.dumps(old[:-1], sort_keys=True).encode())
    require(
        envelope["OLD_TERMS"] == [list(t) for t in old]
        and envelope["ALL_T_TERMS"] == cert["ALL_T_TERMS"] == [list(t) for t in terms]
        and envelope["COMPLETE_T_RANGE"] == [old[0][0], cap]
        and len(terms) == envelope["TERM_COUNT"] == cap - old[0][0] + 1
        and envelope["FULL_PROFILE_BOUND"] == best
        and envelope["MAX_T"] == max(t[0] for t in terms if t[1] == best)
        and envelope["T264_TERM_BOUND"] == fifth
        and envelope["OLD_PROFILE_BOUND"] == max(t[1] for t in old)
        and envelope["LOWER_T_SHA256"] == cert["RETAINED_TERMS_SHA256"] == lower_sha
        and envelope["CHANGED_FIELDS"] == [[cap, "BOUND"]]
        and envelope["ALL_T_BONFERRONI5_ADOPTION"] == "OUT_OF_SCOPE_NOT_VERIFIED",
        "donor complete envelope differs",
    )
    require(terms[:-1] == old[:-1] and terms[-1][2:] == old[-1][2:], "other T fields changed")
    return best, dict(envelope)


def compose(
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    sealed: Mapping[str, object],
    donor: Mapping[str, object],
    pid: str,
    bound: int,
) -> dict[str, int]:
    before = validate_rows(rows, sealed)
    base.validate_cursor(cursor, obj(sealed["CURSOR"]))
    certified, _ = validate_donor(donor)
    require(pid == TARGET, "wrong update profile")
    require(type(bound) is int and bound == certified < before[pid], "wrong update bound")
    after = {**before, pid: bound}
    require([p for p in before if before[p] != after[p]] == [pid], "not one row")
    require(
        projection({p: v for p, v in before.items() if p != pid})
        == projection({p: v for p, v in after.items() if p != pid}),
        "other rows changed",
    )
    require(not set(after).intersection(obj(cursor["COARSE_BOUND_PROJECTION"])), "cursor overlap")
    return after


def compute_result() -> dict[str, object]:
    sealed, donor, provenance = load_inputs()
    before = replay_base(sealed)
    cursor = obj(sealed["CURSOR"])
    bound, envelope = validate_donor(donor)
    require(before[TARGET] == envelope["OLD_PROFILE_BOUND"], "target old bound differs")
    after = compose(list(before.items()), cursor, sealed, donor, TARGET, bound)
    before_max, before_owners = base.family(before, cursor)
    after_max, owners = base.family(after, cursor)
    all_bounds = {
        **after,
        **{p: integer(v) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()},
    }
    ranked = sorted((v, p) for p, v in all_bounds.items())
    require(
        (before_max, before_owners) == (sealed["FAMILY_BOUND_AFTER"], sealed["FAMILY_OWNER_IDS"])
        and (after_max, owners)
        == (ranked[-1][0], sorted(p for v, p in ranked if v == ranked[-1][0])),
        "independent family maximum differs",
    )
    incumbent = integer(sealed["INCUMBENT"])
    other = {p: v for p, v in before.items() if p != TARGET}
    inherited = {
        k: v
        for k, v in sealed.items()
        if k.startswith("INHERITED_")
        or k
        in (
            "TASK_STATUS",
            "DONOR_STATUS_SNAPSHOTS_VERBATIM",
            "DONOR_THEOREM_VERBATIM",
            "PROVENANCE",
        )
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPOSITION_SEALED_PENDING_FRESH_JUDGE_AND_LIFECYCLE",
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "PROVENANCE": provenance,
        "IMPLEMENTATION_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "ROWS_TOTAL": len(before),
        "ROWS_UPDATED": len([p for p in before if before[p] != after[p]]),
        "ROW_UPDATE": {"PROFILE_ID": TARGET, "BEFORE_BOUND": before[TARGET], "AFTER_BOUND": bound},
        "OTHER_ROWS_UNCHANGED": "PASS",
        "OTHER_4646_BOUNDS_SHA256": sha(projection(other)),
        "BOUNDS_SHA256_BEFORE": sha(projection(before)),
        "BOUNDS_SHA256_AFTER": sha(projection(after)),
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "CURSOR": cursor,
        "CURSOR_PRESERVED": "PASS",
        "CURSOR_SHA256_BEFORE": sha(render(cursor)),
        "CURSOR_SHA256_AFTER": sha(render(cursor)),
        "CERTIFICATES_ADOPTED": sealed["CERTIFICATES_ADOPTED"],
        "BONFERRONI_5_ADOPTED": {
            "PROFILE_ID": TARGET,
            "SCOPE": "CAP_TERM_ONLY",
            "CAP": donor["TRIANGLE_CAP"],
        },
        "BONFERRONI_5_OTHER_PROFILES_ADOPTED": [],
        "ENVELOPE": envelope,
        "CERTIFIED_S5_CAP": obj(donor["S5_PROOF"])["S5_CAP"],
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": inherited,
        "DONOR_ORIGINAL_STATUS_VERBATIM": donor["DONOR_ORIGINAL_STATUS"],
        "DONOR_PRE_JUDGE_STATUS_VERBATIM": donor["TASK_STATUS"],
        "DONOR_FAMILY_EFFECT_SNAPSHOT_VERBATIM": donor["FAMILY_EFFECT"],
        "FAMILY_BOUND_BEFORE": before_max,
        "FAMILY_BOUND_AFTER": after_max,
        "EXACT_DELTA": before_max - after_max,
        "FAMILY_OWNER_IDS_BEFORE": before_owners,
        "FAMILY_OWNER_IDS": owners,
        "INCUMBENT": incumbent,
        "GAP_TO_INCUMBENT": after_max - incumbent,
        "RESOLVED_OPEN_PROFILE_IDS": sorted(p for p, v in after.items() if v > incumbent),
        "STILL_OPEN_PROFILE_COUNT": sum(v > incumbent for v in all_bounds.values()),
        "UNRESOLVED_CURSOR_PROFILE_COUNT": cursor["PROFILE_COUNT"],
        "G01_TO_G15_AT_SEAL": {f"G{i:02}": "NOT_VERIFIED" for i in range(1, 16)},
        "GATE_STATUS_SCOPE": "External exact-tree Judge and post-acceptance lifecycle close gates.",
        "MATHEMATICAL_THEOREMS_REEXECUTED": 0,
        "BONFERRONI_METHOD_REBUILT": "NO",
        "SOLVER_CALLS": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "SHARED_LEDGER_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "REMOTE_WRITE": "NO",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    raw = render(result)
    if args.verify or RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == raw, "sealed result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(raw)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "ROWS_TOTAL",
                    "ROWS_UPDATED",
                    "FAMILY_BOUND_AFTER",
                    "EXACT_DELTA",
                    "FAMILY_OWNER_IDS",
                    "GAP_TO_INCUMBENT",
                    "STILL_OPEN_PROFILE_COUNT",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
