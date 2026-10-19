"""Compose exactly two accepted cap-term certificates into the immutable family.

Reuse the certified Bonferroni-5 theorem; never reconstruct its 2544 patterns.
Replay the accepted Base ledger, all 244 integer T terms per donor profile,
and all 197 cursor members. S4 lower bounds are subtracted, S5 upper bounds
added, and official Route-B ceiling semantics retained. Bonferroni-5 replaces
only T265, while the complete envelope supplies each row's upper bound.
No solver, attainment, strict-gain exclusion, or global optimum is asserted.
"""

from __future__ import annotations

import argparse
import ast
import json
import stat
import sys
from collections.abc import Mapping, Sequence
from fractions import Fraction
from math import comb
from pathlib import Path

from . import b649_min_s2_t249_bonf5_single_row_composition_r1 as prior

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_TWO_BONF5_OWNERS_EXACT_FAMILY_COMPOSITION_R1"
OWNER_CONVERSATION_ID = "01a13096-b609-78a2-85fe-66b0604c19a8"
BASE_HEAD = "5aece9bd6d29070deb8583bceba5cfb6af749db1"
BASE_TREE = "08ad7923905facf4a69370453cb9de9338ebbfbe"
DONOR_HEAD = "2e27a2c77934c7352b792ab867eb5be20b095372"
DONOR_TREE = "2d3bf1e263ee13e9c55d49a70a05128a5362dbd3"
BASE_RESULT = prior.RESULT_PATH.relative_to(ROOT).as_posix()
BASE_SHA = "53730d723d701735cca917d624b60d57f2ac242dae358882701b2a7341996cd7"
DONOR_RESULT = f"{prior.DIRECTORY}/b649-min-s2-bonf5-tied-owners-cert-r1-result.json"
DONOR_SHA = "6c26b95cbacb0a6802b5cd8df4d1b98f2867dfd10422b973b1b9108cede0259d"
DONOR_SOURCE = "src/lottolab/research/b649_min_s2_bonf5_tied_owners_cert_r1.py"
DONOR_SOURCE_SHA = "53657a6426e1d0d51cc4cfb98476f4e2343cecc01e5115dfbc4839df0dffe24c"
SOURCE = "src/lottolab/research/b649_min_s2_two_bonf5_owners_exact_composition_r1.py"
TEST_SOURCE = "tests/unit/test_b649_min_s2_two_bonf5_owners_exact_composition_r1.py"
RESULT_PREFIX = "b649-min-s2-two-bonf5-owners-exact-composition-r1-result-"
PROFILES = ("66555555555441000000", "66555555555522000000")
ORIGINAL_HEAD = "e3a9843db4339167bffcdc92fb782ff6bb663ed8"
ORIGINAL_TREE = "f63545acbc883f13ec9c50eea0b3a7e6a2190d3b"
REPORT_ROOT = ROOT.parent
REPORT_PINS = {
    "BASE": (
        "B649_MIN_S2_T249_BONF5_SINGLE_ROW_COMPOSITION_R1/"
        ".task-data/B649_MIN_S2_T249_BONF5_SINGLE_ROW_COMPOSITION_R1/fresh-judge-report.md",
        "ff7506bf775e2171089e6b32f8b8d614bb2a425e22ac27f6be6ad9307c9d397d",
    ),
    "DONOR": (
        "B649_MIN_S2_BONF5_TIED_OWNERS_CERT_R1/"
        ".task-data/B649_MIN_S2_BONF5_TIED_OWNERS_FORMAL_CERT_R1/fresh-judge-report.md",
        "6e84387d07f61081edb55fe1ff162348aa065c6216c590e37ef9aeb964510b1b",
    ),
}
require, obj, items, integer, string = (
    prior.require,
    prior.obj,
    prior.items,
    prior.integer,
    prior.string,
)
sha, render, projection, git, blob, decode = (
    prior.sha,
    prior.render,
    prior.projection,
    prior.git,
    prior.blob,
    prior.decode,
)
type Inputs = tuple[dict[str, object], dict[str, object], dict[str, object]]
type Term = prior.Term


def result_path() -> Path | None:
    paths = sorted((ROOT / prior.DIRECTORY).glob(f"{RESULT_PREFIX}*.json"))
    require(len(paths) <= 1, "duplicate composition result")
    if not paths:
        return None
    path = paths[0]
    require(stat.S_ISREG(path.lstat().st_mode), "unsafe result")
    require(path.name == f"{RESULT_PREFIX}{sha(path.read_bytes())}.json", "result SHA differs")
    return path


def validate_reports(reports: Mapping[str, object]) -> None:
    require(set(reports) == set(REPORT_PINS), "missing Judge report")
    for tag, head, tree, digest in (
        ("BASE", BASE_HEAD, BASE_TREE, BASE_SHA),
        ("DONOR", DONOR_HEAD, DONOR_TREE, DONOR_SHA),
    ):
        report = string(reports[tag])
        require(sha(report.encode()) == REPORT_PINS[tag][1], "Judge report SHA differs")
        require(
            "VERIFIED_WITH_CAVEATS" in report
            and "JUDGE_MODE: FRESH_CONTEXT" in report
            and tree in report
            and digest in report,
            "Judge identity binding differs",
        )
        require(head in report or tag == "BASE", "Judge commit binding differs")


def load_inputs() -> Inputs:
    for head, tree in (
        (BASE_HEAD, BASE_TREE),
        (DONOR_HEAD, DONOR_TREE),
        (ORIGINAL_HEAD, ORIGINAL_TREE),
    ):
        require(git("cat-file", "-t", head).strip() == b"commit", "wrong commit identity")
        require(
            git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "wrong tree identity"
        )
    sealed = decode(blob(BASE_HEAD, BASE_RESULT, BASE_SHA))
    donor = decode(blob(DONOR_HEAD, DONOR_RESULT, DONOR_SHA))
    source = blob(DONOR_HEAD, DONOR_SOURCE, DONOR_SOURCE_SHA)
    require(
        donor["SOURCE_SHA256"] == DONOR_SOURCE_SHA
        and ast.get_docstring(ast.parse(source), clean=False) == donor["PROOF"],
        "donor source/proof binding differs",
    )
    require(
        render(prior.compute_result()) == render(sealed) == blob(BASE_HEAD, BASE_RESULT, BASE_SHA),
        "full Base replay differs",
    )
    require(
        sha((ROOT / prior.SOURCE).read_bytes()) == sealed["IMPLEMENTATION_SHA256"], "Base drift"
    )
    path = result_path()
    reports = (
        obj(obj(decode(path.read_bytes())["PROVENANCE"])["JUDGE_REPORTS_VERBATIM"])
        if path
        else {tag: (REPORT_ROOT / p).read_text() for tag, (p, _) in REPORT_PINS.items()}
    )
    validate_reports(reports)
    require(not any(n.startswith("ortools") for n in sys.modules), "solver imported")
    provenance: dict[str, object] = {
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT": BASE_RESULT,
        "BASE_RESULT_SHA256": BASE_SHA,
        "DONOR_HEAD": DONOR_HEAD,
        "DONOR_TREE": DONOR_TREE,
        "DONOR_RESULT": DONOR_RESULT,
        "DONOR_RESULT_SHA256": DONOR_SHA,
        "DONOR_SOURCE_SHA256": DONOR_SOURCE_SHA,
        "JUDGE_REPORTS_VERBATIM": reports,
        "JUDGE_REPORT_SHA256": {tag: pin[1] for tag, pin in REPORT_PINS.items()},
        "BASE_FRESH_JUDGE": "VERIFIED_WITH_CAVEATS",
        "DONOR_FRESH_JUDGE": "VERIFIED_WITH_CAVEATS",
        "ORIGINAL_BONF5_STATUS": "SELF_CHECK_ONLY",
        "BASE_COMMIT_MESSAGE_VERBATIM": git("show", "-s", "--format=%B", BASE_HEAD).decode(),
        "DONOR_COMMIT_MESSAGE_VERBATIM": git("show", "-s", "--format=%B", DONOR_HEAD).decode(),
    }
    return sealed, donor, provenance


def donor_blob(donor: Mapping[str, object], path: str) -> dict[str, object]:
    pin = obj(obj(donor["BLOB_PINS"])[path])
    head = string(pin["HEAD"])
    require(git("rev-parse", f"{head}:{path}").decode().strip() == pin["BLOB"], "blob ID differs")
    return decode(blob(head, path, string(pin["SHA256"])))


def moment_bounds(s3: int, s4: int, s5: int) -> tuple[int, int]:
    numerator = 7 * (372228640 - 63838600 + s3) - 4 * s4
    return (numerator + 6) // 7, 372228640 - 63838600 + s3 - s4 + s5


def validate_donor(donor: Mapping[str, object]) -> dict[str, object]:
    # These profiles' S4 values divide by seven exactly. A fractional arithmetic
    # probe distinguishes ceiling from floor without extending theorem scope.
    constant = 372228640 - 63838600
    require(moment_bounds(0, 1, 1) == (constant, constant), "wrong bound-term sign or rounding")
    require(
        donor["DONOR_HEAD"] == ORIGINAL_HEAD
        and donor["DONOR_TREE"] == ORIGINAL_TREE
        and donor["ORIGINAL_DONOR_STATUS"]
        == {"JUDGE_MODE": "SELF_CHECK_ONLY", "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY"},
        "original authority status differs",
    )
    require(
        donor["MODEL"]
        == {
            "POOL": 49,
            "TICKETS": 20,
            "LABELS_PER_TICKET": 6,
            "TRIPLES": 22,
            "PAIRS": 27,
            "PAIR_LINEARITY": True,
        },
        "model applicability differs",
    )
    original = donor_blob(
        donor,
        f"{prior.DIRECTORY}/b649-k20-min-s2-three-competing-profiles-bonferroni5-r1-result.json",
    )
    target = donor_blob(donor, prior.DONOR_RESULT)
    r30 = donor_blob(donor, f"{prior.DIRECTORY}/{prior.base.inherited.official.CAP_SOURCE_RESULT}")
    require(original["JUDGE_MODE"] == "SELF_CHECK_ONLY", "original status upgraded")
    for key in ("BONFERRONI_PROOF", "S123", "S4_WEIGHTS"):
        require(donor[key] == target[key], "accepted moment proof differs")
    proof = obj(donor["BONFERRONI_PROOF"])
    require(
        proof["SIGNS"] == [1, -1, 1, -1, 1]
        and proof["S4_DIRECTION"] == "LOWER_BOUND_SUBTRACTED"
        and proof["S5_DIRECTION"] == "UPPER_BOUND_ADDED"
        and proof["R_CAP"] == 7,
        "wrong moment sign or domain",
    )
    require(
        donor["S5_LOCAL_IDENTITY"]
        == {k: obj(target["S5_PROOF"])[k] for k in obj(donor["S5_LOCAL_IDENTITY"])},
        "accepted S5 theorem differs",
    )
    certs, caps, proofs = (
        obj(donor[k]) for k in ("PROFILE_CERTIFICATES", "CAP_AUTHORITIES", "DEGREE_S5_PROOFS")
    )
    require(set(certs) == set(caps) == set(proofs) == set(PROFILES), "wrong certificate set")
    checked: dict[str, object] = {}
    for pid in PROFILES:
        cert, cap_proof, s5_proof = obj(certs[pid]), obj(caps[pid]), obj(proofs[pid])
        d = prior.base.inherited.split.profile_values(pid)
        require(len(d) == 20 and sum(d) == 66 and d.count(0) == 6, "profile applicability differs")
        cap = integer(cert["T_CAP"])
        require(
            cap == 265 and cert["PROFILE_ID"] == s5_proof["PROFILE_ID"] == pid,
            "wrong profile identity or cap",
        )
        require(
            cap_proof == obj(items(r30["GROUP_ATTEMPTS"])[integer(cap_proof["ATTEMPT_INDEX"])]),
            "cap proof drift",
        )
        require(
            cap_proof["PROFILE_IDS"] == [pid]
            and prior.base.inherited.official.r28.r26.accepted_cap(cap_proof, (d,), cap) == cap,
            "wrong certified cap",
        )
        thresholds: list[list[int]] = []
        for k in range(1, 7):
            high, low = [v for v in d if v >= k], [v for v in d if 0 < v < k]
            incidence = sum(high) // 3 if len(high) >= 3 else 0
            low_cap = 22 - max(low, default=0)
            thresholds.append(
                [k, len(high), sum(high), incidence, low_cap, min(incidence, low_cap)]
            )
        common = 22 * comb(5, 2) + sum(thresholds[k - 1][5] * (k + 3) for k in range(2, 7))
        n2 = sum(comb(v, 2) for v in d)
        s5 = 7 * (common + 2 * n2)
        require(
            s5_proof
            == {
                "PROFILE_ID": pid,
                "D": list(d),
                "G": [6 + v for v in d],
                "THRESHOLD_CAPS": thresholds,
                "COMMON_PAIR_SUM_CAP": common,
                "N_2T_CAP": n2,
                "S5_CAP": s5,
                "BOUND_DIRECTION": "UPPER_BOUND_ADDED",
                "ATTAINABILITY": "NOT_ASSERTED",
            }
            and cert["S5_CAP"] == s5,
            "wrong S5 cap or proof",
        )
        floor = prior.base.inherited.official.r28.profile_s4_floor(d)
        old = prior.base.inherited.split.route_b_terms(d, cap, floor)
        require(
            old == prior.base.inherited.official.route_b_envelope(d, cap, floor),
            "official T terms differ",
        )
        terms: list[Term] = []
        for t, bound, k4, contained, s4, s3 in old:
            fourth, fifth = moment_bounds(s3, s4, s5)
            rational = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
            require(
                fourth == bound == -(-rational.numerator // rational.denominator)
                and fifth == 372228640 - 63838600 + s3 - s4 + s5,
                "wrong bound-term sign or rounding",
            )
            terms.append((t, min(fourth, fifth) if t == cap else bound, k4, contained, s4, s3))
        maximum = max(t[1] for t in terms)
        original_cert = obj(obj(original["PROFILE_CERTIFICATES"])[pid])
        require(
            original_cert["PROFILE_ID"] == pid
            and original_cert["TRIANGLE_CAP"] == cap
            and original_cert["CAP_SOURCE_IDENTITY"] == cap_proof
            and original_cert["S4_BASE"] == floor
            and cert["COMPLETE_T_RANGE"] == [22, cap]
            and cert["TERM_COUNT"] == len(terms) == 244
            and [t[0] for t in terms] == list(range(22, cap + 1))
            and cert["OLD_TERMS"] == [list(t) for t in old]
            and cert["ALL_T_TERMS"] == original_cert["ALL_T_TERMS"] == [list(t) for t in terms]
            and cert["FULL_PROFILE_BOUND"] == original_cert["CERTIFIED_PROFILE_BOUND"] == maximum
            and cert["MAX_T"] == max(t[0] for t in terms if t[1] == maximum)
            and cert["PRE_UPDATE_BOUND"] == max(t[1] for t in old)
            and cert["T265_TERM_BOUND"] == terms[-1][1]
            and cert["LOWER_T_SHA256"]
            == original_cert["RETAINED_TERMS_SHA256"]
            == sha(json.dumps(old[:-1], sort_keys=True).encode())
            and cert["CHANGED_FIELDS"] == [[cap, "BOUND"]]
            and cert["TERM_COLUMNS"] == ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"]
            and cert["INCUMBENT"] == prior.base.inherited.INCUMBENT
            and cert["STRICT_GAIN_EXCLUDED"] == "NO"
            and maximum > integer(cert["INCUMBENT"])
            and cert["PROFILE_DELTA"] == max(t[1] for t in old) - maximum
            and cert["BOUND_MINUS_INCUMBENT"] == maximum - integer(cert["INCUMBENT"]),
            "complete profile envelope differs",
        )
        checked[pid] = cert
    return checked


def compose(
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    sealed: Mapping[str, object],
    certificates: Mapping[str, object],
    updates: Sequence[tuple[str, int]],
) -> dict[str, int]:
    before = dict(rows)
    require(
        len(rows) == len(before) == 4647 and all(type(v) is int for _, v in rows),
        "wrong or duplicate ledger rows",
    )
    require(
        before == obj(sealed["RESOLVED_ROW_BOUNDS"])
        and sha(projection(before)) == sealed["BOUNDS_SHA256_AFTER"],
        "Base projection drift",
    )
    prior.base.validate_cursor(cursor, obj(sealed["CURSOR"]))
    require(
        len(updates) == len({p for p, _ in updates}) == 2
        and {p for p, _ in updates} == set(PROFILES),
        "missing/duplicate/wrong updates",
    )
    require(set(certificates) == set(PROFILES), "wrong certificate scope")
    after = dict(before)
    for pid, bound in updates:
        cert = obj(certificates[pid])
        require(
            type(bound) is int
            and bound == integer(cert["FULL_PROFILE_BOUND"]) < before[pid]
            and before[pid] == cert["PRE_UPDATE_BOUND"],
            "wrong full-profile update bound",
        )
        after[pid] = bound
    require({p for p in before if before[p] != after[p]} == set(PROFILES), "not exactly two rows")
    require(
        projection({p: v for p, v in before.items() if p not in PROFILES})
        == projection({p: v for p, v in after.items() if p not in PROFILES}),
        "other rows changed",
    )
    require(not set(after).intersection(obj(cursor["COARSE_BOUND_PROJECTION"])), "cursor overlap")
    return after


def compute_result() -> dict[str, object]:
    sealed, donor, provenance = load_inputs()
    before = {p: integer(v) for p, v in obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(sealed["CURSOR"])
    certs = validate_donor(donor)
    updates = [(pid, integer(obj(certs[pid])["FULL_PROFILE_BOUND"])) for pid in PROFILES]
    after = compose(list(before.items()), cursor, sealed, certs, updates)
    before_max, before_owners = prior.base.family(before, cursor)
    after_max, owners = prior.base.family(after, cursor)
    all_rows = [
        *after.items(),
        *[(p, integer(v)) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()],
    ]
    ranked = sorted((bound, pid) for pid, bound in all_rows)
    require(
        (before_max, before_owners) == (sealed["FAMILY_BOUND_AFTER"], sealed["FAMILY_OWNER_IDS"])
        and (after_max, owners)
        == (ranked[-1][0], sorted(p for b, p in ranked if b == ranked[-1][0])),
        "independent maximum differs",
    )
    singles = {pid: prior.base.family({**before, pid: bound}, cursor)[0] for pid, bound in updates}
    require(all(v == before_max for v in singles.values()), "single update unexpectedly lowers max")
    incumbent = integer(sealed["INCUMBENT"])
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_LIFECYCLE",
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "PROVENANCE": provenance,
        "IMPLEMENTATION_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST_SOURCE).read_bytes()),
        "ROWS_TOTAL": len(before),
        "ROWS_UPDATED": sum(before[p] != after[p] for p in before),
        "ROW_UPDATES": {p: {"BEFORE_BOUND": before[p], "AFTER_BOUND": b} for p, b in updates},
        "OTHER_ROWS_UNCHANGED": "PASS",
        "OTHER_4645_BOUNDS_SHA256": sha(
            projection({p: v for p, v in before.items() if p not in PROFILES})
        ),
        "BOUNDS_SHA256_BEFORE": sha(projection(before)),
        "BOUNDS_SHA256_AFTER": sha(projection(after)),
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "CURSOR": cursor,
        "CURSOR_PRESERVED": "PASS",
        "CURSOR_SHA256": sha(render(cursor)),
        "CERTIFICATES_ADOPTED": sealed["CERTIFICATES_ADOPTED"],
        "INHERITED_TARGET_BONFERRONI_5": sealed["BONFERRONI_5_ADOPTED"],
        "PROFILE_CERTIFICATES": certs,
        "NEW_BONFERRONI_5_SCOPE": "T265_BOUND_ONLY",
        "FULL_PROFILE_SCOPE": "T22_T265_ENVELOPE",
        "ALL_T_BONFERRONI_5_ADOPTION": "NOT_VERIFIED",
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": {
            k: v for k, v in sealed.items() if k.startswith("INHERITED_") or "STATUS" in k
        },
        "DONOR_ORIGINAL_STATUS_VERBATIM": donor["ORIGINAL_DONOR_STATUS"],
        "DONOR_PRE_JUDGE_STATUS_VERBATIM": donor["TASK_STATUS"],
        "DONOR_PROOF_VERBATIM": donor["PROOF"],
        "FAMILY_BOUND_BEFORE": before_max,
        "FAMILY_AFTER_SINGLE_UPDATE": singles,
        "FAMILY_BOUND_AFTER": after_max,
        "EXACT_DELTA": before_max - after_max,
        "FAMILY_OWNER_IDS_BEFORE": before_owners,
        "FAMILY_OWNER_IDS": owners,
        "INCUMBENT": incumbent,
        "GAP_TO_INCUMBENT": after_max - incumbent,
        "STILL_OPEN_PROFILE_COUNT": sum(b > incumbent for _, b in all_rows),
        "CURSOR_PROFILE_COUNT": cursor["PROFILE_COUNT"],
        "G01_TO_G15_AT_SEAL": {f"G{i:02}": "NOT_VERIFIED" for i in range(1, 16)},
        "GATE_STATUS_SCOPE": "External exact-tree scientific Judge and subsequent local lifecycle.",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "MATHEMATICAL_THEOREMS_REEXECUTED": 0,
        "BONFERRONI_METHOD_REBUILT": "NO",
        "SOLVER_CALLS": 0,
        "EXISTING_CERTIFICATES_MUTATED": "NO",
        "CURSOR_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    existing = result_path()
    require(not args.verify or existing is not None, "missing sealed result")
    result = compute_result()
    raw = render(result)
    if existing:
        require(existing.read_bytes() == raw, "sealed result differs")
    else:
        with (ROOT / prior.DIRECTORY / f"{RESULT_PREFIX}{sha(raw)}.json").open("xb") as output:
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
