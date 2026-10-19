"""Formal, separate cap-term Bonferroni-5 certificates for exactly two profiles.

MODEL/APPLICABILITY. In the pair-linear Minimum-S2 class twenty six-label
tickets use 22 triple and 27 pair supports on 49 labels. Each profile d has
sum d=66, residual pair degrees 6-d, and graph degrees g=6+d. The two
profiles are checked separately; neither supplies the other's authority.
The pinned R30 records refute T>=266 and the accepted-cap predicate gives
T<=265. These are historical solver certificates, not new solver execution.

MOMENTS. Reuse the pinned formal target's independently counted S1--S5
helpers, including its 2544 local five-ticket patterns and multiplicity
inequalities. Pair-linearity gives r<=7 winning tickets per outcome.
U<=S1-S2+S3-(4/7)S4 and U<=S1-S2+S3-S4+S5. S4 LOWER bounds are
subtracted; S5 UPPER bounds are added. Take the minimum of upper bounds.
S3=2800W+11872(T-22)-30800. J<=4K4+(max(g)-2)(W-3T), and the
contained-K4 cap is floor(sum d(4+d)/3). Thus the K4 S4 floor is
679K4-231*min(K4,contained_cap), combined with the inherited S4 floor.

S5. The proven identity is S5=7*(sum_tau C(m_tau,2)+2*N_2T), with
m_tau<=4+min(d_v). H_k counts triples with all three degrees >=k:
3H_k<=sum_{d>=k}d; H_k<=22-max_{0<d<k}d; H_k=0 if fewer than three
vertices are high. Threshold telescoping and N_2T<=sum C(d_v,2) give
(common,n2,S5)=(742,132,7042) and (750,132,7098), independently.

SCOPE. Only the T265 BOUND is replaced. Independently check all 244 terms
T22--T265 for each profile, preserve all lower-T fields, and maximize the
complete envelopes at T264. Neither bound excludes strict gain over the
incumbent. No attainment or global optimum is asserted. The donor remains
SELF_CHECK_ONLY. Replay the pinned T249 bound ledger read-only, explicitly
project the previously certified target's cap-term update, then project
both new rows and all 197 cursor profiles. This PROJECTED_COMPOSITION is
not A's separate combined authority and installs no shared ledger update.
Inherited status/caveat snapshots remain verbatim. The new immutable result
requires an external Fresh Judge tied to its exact scientific tree.
"""

from __future__ import annotations

import argparse
import ast
import json
import stat
import sys
from collections.abc import Mapping
from math import comb
from pathlib import Path

from . import b649_min_s2_bonferroni5_target_cert_r1 as proven

require, obj, items, integer = proven.require, proven.obj, proven.items, proven.integer
sha, render, git, decode = proven.sha, proven.render, proven.git, proven.decode
projection = proven.prior.projection
ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = proven.DIRECTORY
TASK_ID = "B649_MIN_S2_BONF5_TIED_OWNERS_FORMAL_CERT_R1"
BASE_HEAD = "8fac3d41b2d519d92b06d6ceb933fe31072c6409"
BASE_TREE = "62f80eecf3f1045c905d345a3e68fb2ad078eaec"
T249_HEAD = "7ae9c7c332119926ee2282da7dd205bdcef6afdf"
T249_TREE = "9f32fcfcf63cf93e78014b3f5a33155673d4b1b6"
PROFILE_1, PROFILE_2 = "66555555555441000000", "66555555555522000000"
PROFILES = (PROFILE_1, PROFILE_2)
CAP, S4_BASE, INCUMBENT = 265, 112, 313263888
ATTEMPTS = {PROFILE_1: 3074, PROFILE_2: 3073}
NB_INDICES = {PROFILE_1: 1447, PROFILE_2: 1444}
S5_CAPS = {PROFILE_1: 7042, PROFILE_2: 7098}
EXPECTED_BOUNDS = {PROFILE_1: 313386680, PROFILE_2: 313386292}
CAP_TERM_BOUNDS = {PROFILE_1: 313277174, PROFILE_2: 313277230}
NEXT_OWNERS = ["66655555555511100000", "66665555554431000000"]
SOURCE = "src/lottolab/research/b649_min_s2_bonf5_tied_owners_cert_r1.py"
TARGET_RESULT = proven.RESULT_PATH.relative_to(ROOT).as_posix()
T249_MODULE = "b649_min_s2_t249_dual_profile_composition_r1"
T249_SOURCE = f"src/lottolab/research/{T249_MODULE}.py"
T249_RESULT = f"{DIRECTORY}/b649-min-s2-t249-dual-profile-composition-r1-result.json"
T249_SOURCES = f"{DIRECTORY}/b649-min-s2-t249-dual-profile-composition-r1-sources"
RESULT_PATH = ROOT / DIRECTORY / "b649-min-s2-bonf5-tied-owners-cert-r1-result.json"
PINS = {
    **proven.PINS,
    TARGET_RESULT: (
        BASE_HEAD,
        "2ee215a1f355bab37021d387b3ddf52fc62f3c09",
        "dc0ffab7c48e5a651375f7773e495d869d4211273ff3ff3b1423c5b10c1f7d9b",
    ),
    f"src/lottolab/research/{proven.__name__.split('.')[-1]}.py": (
        BASE_HEAD,
        "45bcd1d2b8769de508e8fb97abb41b13e0895617",
        "037e4629e681dbb695b920fa5f06fffccff5b8aa12121e3433f5b48f354c9cdd",
    ),
    f"tests/unit/test_{proven.__name__.split('.')[-1]}.py": (
        BASE_HEAD,
        "65b71e5191135789ff84559774cc4fb90d41ed2a",
        "d6770d2feeabf990edf3b5b2ffd7f8656a0ffbb2b8a17f6d9ff537709902d95b",
    ),
    T249_RESULT: (
        T249_HEAD,
        "471d31eeadc8087b9e5017cf3e7ea18debe01a7e",
        "5c0aca19ec5e703e3de35abca804380aabdb82dfaaec40f36d0a3e760938e493",
    ),
    T249_SOURCE: (
        T249_HEAD,
        "370dddc45a02ec0f409c57e0cb8b0d2dda582c15",
        "08dcc4b07e97710d7755e9cbdbbd452965c281300cc16e40535af89e5c9d4941",
    ),
    f"tests/unit/test_{T249_MODULE}.py": (
        T249_HEAD,
        "c4945354f6b627af3b24d5a351067c11ae5e7d96",
        "cd71602009dde445f0576ea2a285011a34b3e1043ab4f9e4fc69743588fd50d9",
    ),
    f"{T249_SOURCES}/base-judge.txt": (
        T249_HEAD,
        "466f0e3524bc51650e7d504ae42a5f29dab9542e",
        "94e6640b7362f6e709e3322706ad54e85ed475c4916e15fc6371e0993c954dd7",
    ),
    f"{T249_SOURCES}/donor-judge.json": (
        T249_HEAD,
        "72747544832a95fd3de87d59f271eed1f9783acd",
        "d2d6490c6b40b8751e31f65b050ec14ac4702f983579a0176672e507f02186b9",
    ),
    f"{T249_SOURCES}/donor-result.json": (
        T249_HEAD,
        "3622801fa07ce3ca83eb0035b5c16ffa5a46863c",
        "2e019bd686cd49e7ed8539a8d56f66c7aa2835eb087538cd99e5fc8b4e03d694",
    ),
}
type Term = proven.Term


def pinned_bytes(path: str) -> bytes:
    head, blob, digest = PINS[path]
    metadata = git("ls-tree", head, "--", path).decode().split()
    require(len(metadata) == 4 and metadata[:2] == ["100644", "blob"], "unsafe pinned blob")
    require(not blob or metadata[2] == blob, "pinned blob mismatch")
    raw = git("show", f"{head}:{path}")
    require(sha(raw) == digest, "tampered source bytes")
    if head in (BASE_HEAD, proven.BASE_HEAD):
        local = ROOT / path
        require(stat.S_ISREG(local.lstat().st_mode), "unsafe local source")
        require(local.read_bytes() == raw, "local source bytes changed")
    return raw


def helper_identity() -> dict[str, str]:
    pins: dict[str, str] = {}
    for name, module in sorted(sys.modules.copy().items()):
        if name.startswith("lottolab.research.") and name != __name__:
            require(module.__file__ is not None, "helper lacks source")
            path = Path(proven.base.string(module.__file__)).resolve()
            require(path.is_relative_to(ROOT), "helper outside isolated worktree")
            relative = path.relative_to(ROOT).as_posix()
            meta = git("ls-tree", BASE_HEAD, "--", relative).decode().split()
            require(len(meta) == 4 and meta[:2] == ["100644", "blob"], "unsafe helper")
            raw = git("show", f"{BASE_HEAD}:{relative}")
            require(raw == path.read_bytes(), "helper differs from pinned base")
            pins[relative] = sha(raw)
    require(not any(n.startswith("ortools") for n in sys.modules), "solver imported")
    return pins


def authority() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    for head, tree in (
        (BASE_HEAD, BASE_TREE),
        (T249_HEAD, T249_TREE),
        (proven.DONOR_HEAD, proven.DONOR_TREE),
    ):
        require(git("cat-file", "-t", head).strip() == b"commit", "wrong commit identity")
        require(
            git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "wrong tree identity"
        )
    raw = {p: pinned_bytes(p) for p in PINS}
    donor, sealed, r30 = proven.authority()
    require(
        ast.get_docstring(
            ast.parse(raw[f"src/lottolab/research/{proven.DONOR_MODULE}.py"]), clean=False
        )
        == donor["PROOF"],
        "donor model/proof mismatch",
    )
    target = decode(raw[TARGET_RESULT])
    target_proof = obj(items(r30["GROUP_ATTEMPTS"])[3627])
    proven.cap_authority(target_proof)
    target_s5 = proven.s5_proof(donor)
    target_env = proven.envelope(donor, integer(target_s5["S5_CAP"]))
    expected: dict[str, object] = {
        "PROFILE_ID": proven.TARGET,
        "TRIANGLE_CAP": proven.CAP,
        "SOURCE_SHA256": sha(raw[f"src/lottolab/research/{proven.__name__.split('.')[-1]}.py"]),
        "PROOF": proven.__doc__,
        "CAP_AUTHORITY": target_proof,
        "BONFERRONI_PROOF": proven.multiplicity_proof(),
        "S123": proven.s123_proof(),
        "S4_WEIGHTS": proven.s4_weights(),
        "S5_PROOF": target_s5,
        "ENVELOPE": target_env,
        "FAMILY_EFFECT": proven.family_effect(sealed, integer(target_env["FULL_PROFILE_BOUND"])),
    }
    require(
        all(render(target.get(k)) == render(v) for k, v in expected.items()),
        "formal target replay differs",
    )
    ledger = decode(raw[T249_RESULT])
    require(
        ledger["IMPLEMENTATION_SHA256"] == sha(raw[T249_SOURCE]),
        "composition source/result mismatch",
    )
    message = git("show", "-s", "--format=%B", T249_HEAD).decode()
    require(
        "Fresh-context Judge: VERIFIED_WITH_CAVEATS" in message
        and f"Judged-tree: {T249_TREE}" in message
        and PINS[T249_RESULT][2] in message,
        "T249 Judge binding differs",
    )
    reports = decode(raw[f"{T249_SOURCES}/donor-judge.json"])
    recorded = obj(obj(ledger["PROVENANCE"])["EXTERNAL_JUDGES"])
    require(
        obj(recorded["DONOR"])["REPORTS_VERBATIM"] == reports["reports_newest_first"],
        "T249 donor Judge archive differs",
    )
    return donor, ledger, r30


def profile_degrees(pid: str) -> tuple[int, ...]:
    require(pid in PROFILES, "wrong profile identity")
    d = proven.split.profile_values(pid)
    model = proven.split.prior.r5
    require(
        (
            model.K20_TICKET_COUNT,
            model.K20_TICKET_CAPACITY,
            model.K20_LABEL_COUNT,
            model.K20_TRIPLE_SUPPORT_COUNT,
            model.K20_DOUBLE_SUPPORT_COUNT,
        )
        == (20, 6, 49, 22, 27),
        "support model mismatch",
    )
    require(
        len(d) == 20
        and "".join(map(str, d)) == pid
        and sum(d) == 66
        and all(0 <= v <= 6 for v in d)
        and d.count(0) == 6
        and sum(6 - v for v in d) == 54
        and sum(6 + v for v in d) == 186,
        "profile applicability mismatch",
    )
    require(proven.official.r28.profile_s4_floor(d) == S4_BASE, "wrong inherited S4 floor")
    return d


def cap_authority(pid: str, proof: Mapping[str, object], cap: int = CAP) -> None:
    d = profile_degrees(pid)
    require(type(cap) is int and cap == 265, "wrong T cap")
    w = sum(comb(6 + v, 2) for v in d)
    expected: dict[str, object] = {
        "ATTEMPT_INDEX": ATTEMPTS[pid],
        "PROFILE_IDS": [pid],
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "ROUTE": proven.official.CAP_SOURCE_ROUTE,
        "WEDGE_COUNT": w,
        "TARGET_TRIANGLE_CAP": cap,
        "REFUTED_GRAPH_TRIANGLE_COUNT": cap + 1,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cap,
        "OPEN_WEDGE_CEILING_REFUTED": w - 3 * (cap + 1),
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": w - 3 * (cap + 1) + 1,
        "EXTERNAL_TIMEOUT_EXIT_CODE": 0,
    }
    require(
        all(type(proof.get(k)) is type(v) and proof.get(k) == v for k, v in expected.items()),
        "profile cap authority mismatch",
    )
    require(proven.official.r28.r26.accepted_cap(proof, (d,), cap) == cap, "cap not accepted")


def degree_s5_proof(pid: str, published: Mapping[str, object]) -> dict[str, object]:
    d = profile_degrees(pid)
    thresholds: list[list[int]] = []
    for k in range(1, 7):
        high, low = [v for v in d if v >= k], [v for v in d if 0 < v < k]
        incidence = sum(high) // 3 if len(high) >= 3 else 0
        low_cap = 22 - max(low, default=0)
        thresholds.append([k, len(high), sum(high), incidence, low_cap, min(incidence, low_cap)])
    common = 22 * comb(5, 2) + sum(
        thresholds[k - 1][5] * (comb(4 + k, 2) - comb(3 + k, 2)) for k in range(2, 7)
    )
    n2 = sum(comb(v, 2) for v in d)
    cap = 7 * (common + 2 * n2)
    require(cap == S5_CAPS[pid], "wrong derived S5 cap")
    expected: dict[str, object] = {
        "D": list(d),
        "G": [6 + v for v in d],
        "THRESHOLD_CAPS": thresholds,
        "COMMON_PAIR_SUM_CAP": common,
        "N_2T_CAP": n2,
        "S5_CAP": cap,
    }
    require(
        all(render(published.get(k)) == render(v) for k, v in expected.items()),
        "profile-specific S5 proof mismatch",
    )
    return {
        "PROFILE_ID": pid,
        **expected,
        "BOUND_DIRECTION": "UPPER_BOUND_ADDED",
        "ATTAINABILITY": "NOT_ASSERTED",
    }


def original_terms(pid: str, cap: int = CAP, t_min: int = 22) -> list[Term]:
    d = profile_degrees(pid)
    require(type(cap) is int and cap == 265 and type(t_min) is int and t_min == 22, "wrong T range")
    g = tuple(6 + v for v in d)
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    amax = sum(v * (4 + v) for v in d) // 3
    out: list[Term] = []
    for t in range(t_min, cap + 1):
        k4 = max(0, (j - (max(g) - 2) * (w - 3 * t) + 3) // 4)
        contained = min(k4, amax)
        s4 = max(S4_BASE, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        fourth, _ = proven.moment_bounds(s3, s4, 0)
        out.append((t, fourth, k4, contained, s4, s3))
    require(
        out
        == proven.split.route_b_terms(d, cap, S4_BASE)
        == proven.official.route_b_envelope(d, cap, S4_BASE),
        "Route-B terms differ",
    )
    return out


def envelope(pid: str, published: Mapping[str, object], s5_cap: int) -> dict[str, object]:
    require(
        published["PROFILE_ID"] == pid and published["TRIANGLE_CAP"] == CAP,
        "cross-profile certificate mismatch",
    )
    require(type(s5_cap) is int and s5_cap == S5_CAPS[pid], "wrong S5 cap")
    old = original_terms(pid)
    t, before, k4, contained, s4, s3 = old[-1]
    fourth, fifth = proven.moment_bounds(s3, s4, s5_cap)
    require(fourth == before == 313395448, "pre-update cap bound differs")
    terms = [*old[:-1], (t, min(fourth, fifth), k4, contained, s4, s3)]
    require(
        [list(row) for row in terms] == published["ALL_T_TERMS"]
        and sha(json.dumps(old[:-1], sort_keys=True).encode())
        == published["RETAINED_TERMS_SHA256"],
        "published T envelope mismatch",
    )
    best = max(terms, key=lambda row: (row[1], row[0]))
    require(
        (len(terms), best[0], best[1], fifth)
        == (244, 264, EXPECTED_BOUNDS[pid], CAP_TERM_BOUNDS[pid])
        and published["CERTIFIED_PROFILE_BOUND"] == best[1],
        "full envelope mismatch",
    )
    return {
        "PROFILE_ID": pid,
        "T_CAP": CAP,
        "S5_CAP": s5_cap,
        "COMPLETE_T_RANGE": [22, CAP],
        "TERM_COUNT": len(terms),
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"],
        "OLD_TERMS": [list(row) for row in old],
        "ALL_T_TERMS": [list(row) for row in terms],
        "LOWER_T_SHA256": published["RETAINED_TERMS_SHA256"],
        "CHANGED_FIELDS": [[CAP, "BOUND"]],
        "MAX_T": best[0],
        "PRE_UPDATE_BOUND": max(row[1] for row in old),
        "FULL_PROFILE_BOUND": best[1],
        "T265_TERM_BOUND": fifth,
        "PROFILE_DELTA": 313395448 - best[1],
        "INCUMBENT": INCUMBENT,
        "BOUND_MINUS_INCUMBENT": best[1] - INCUMBENT,
        "STRICT_GAIN_EXCLUDED": "YES" if best[1] <= INCUMBENT else "NO",
    }


def replay_t249(ledger: Mapping[str, object]) -> dict[str, int]:
    sealed = decode(pinned_bytes(proven.BASE_RESULT))
    before = {p: integer(v) for p, v in obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    after = {p: integer(v) for p, v in obj(ledger["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(ledger["CURSOR"])
    proven.base.validate_cursor(cursor, obj(sealed["CURSOR"]))
    require(
        sha(render(cursor)) == ledger["CURSOR_SHA256_BEFORE"] == ledger["CURSOR_SHA256_AFTER"],
        "T249 cursor hash differs",
    )
    require(
        len(before) == len(after) == 4647
        and set(before) == set(after)
        and sha(projection(before)) == ledger["BOUNDS_SHA256_BEFORE"]
        and sha(projection(after)) == ledger["BOUNDS_SHA256_AFTER"],
        "T249 ledger mismatch",
    )
    pid = "66665555554421100000"
    terms = proven.split.route_b_terms(proven.split.profile_values(pid), 249, 112)
    require(
        [list(t) for t in terms] == obj(ledger["ROUTE_B"])["ALL_T_TERMS"]
        and len(terms) == 228
        and max(t[1] for t in terms) == after[pid] == 313254468
        and [p for p in before if before[p] != after[p]] == [pid],
        "T249 replay differs",
    )
    for profile in proven.base.TARGETS:
        update = obj(obj(ledger["INHERITED_TWO_PROFILE_ROW_UPDATES_VERBATIM"])[profile])
        inherited = proven.split.route_b_terms(
            proven.split.profile_values(profile), integer(update["T_CAP"]), 112
        )
        require(
            after[profile] == max(t[1] for t in inherited) == update["AFTER_BOUND"],
            "inherited envelope differs",
        )
    require(
        proven.prior.family(after, cursor)
        == (ledger["FAMILY_BOUND_AFTER"], ledger["FAMILY_OWNER_IDS"]),
        "T249 family differs",
    )
    return after


def family_effect(ledger: Mapping[str, object], certs: Mapping[str, object]) -> dict[str, object]:
    bounds = replay_t249(ledger)
    source_digest = sha(projection(bounds))
    cursor = obj(ledger["CURSOR"])
    cursor_before = render(cursor)
    target = decode(pinned_bytes(TARGET_RESULT))
    target_bound = integer(obj(target["ENVELOPE"])["FULL_PROFILE_BOUND"])
    require(
        bounds[proven.TARGET] == 313396120 and target_bound == 313387352,
        "target projected replacement differs",
    )
    projected = {**bounds, proven.TARGET: target_bound}
    require(set(certs) == set(PROFILES), "wrong composition certificate scope")
    updates: dict[str, int] = {}
    for pid in PROFILES:
        cert = obj(certs[pid])
        require(
            cert["PROFILE_ID"] == pid
            and cert["T_CAP"] == CAP
            and cert["S5_CAP"] == S5_CAPS[pid]
            and cert["FULL_PROFILE_BOUND"] == EXPECTED_BOUNDS[pid]
            and projected[pid] == 313395448,
            "wrong profile row replacement",
        )
        updates[pid] = integer(cert["FULL_PROFILE_BOUND"])
    scenarios = {
        "T249_SOURCE": bounds,
        "AFTER_TARGET_BONF5": projected,
        "AFTER_ONLY_PROFILE_1": {**projected, PROFILE_1: updates[PROFILE_1]},
        "AFTER_ONLY_PROFILE_2": {**projected, PROFILE_2: updates[PROFILE_2]},
        "AFTER_BOTH_PROFILES": {**projected, **updates},
    }
    views: dict[str, object] = {}
    for name, rows in scenarios.items():
        complete = {
            **rows,
            **{p: integer(v) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()},
        }
        require(len(complete) == 4844, "row/cursor coverage overlap")
        maximum = max(complete.values())
        owners = sorted(p for p, b in complete.items() if b == maximum)
        require((maximum, owners) == proven.prior.family(rows, cursor), "family maximum differs")
        views[name] = {"BOUND": maximum, "OWNERS": owners, "BOUNDS_SHA256": sha(projection(rows))}
    require(
        [obj(views[n])["BOUND"] for n in scenarios]
        == [313396120, 313395448, 313395448, 313395448, 313395344]
        and obj(views["AFTER_BOTH_PROFILES"])["OWNERS"] == NEXT_OWNERS,
        "projected family effect differs",
    )
    final = scenarios["AFTER_BOTH_PROFILES"]
    changed = sorted(p for p in bounds if bounds[p] != final[p])
    require(changed == sorted([proven.TARGET, *PROFILES]), "projection scope leak")
    others = {p: v for p, v in bounds.items() if p not in changed}
    require(
        projection(others) == projection({p: v for p, v in final.items() if p not in changed})
        and sha(projection(bounds)) == source_digest
        and render(cursor) == cursor_before,
        "source ledger or cursor mutated",
    )
    return {
        "STATUS": "PROJECTED_COMPOSITION",
        "VIEWS": views,
        "EXPLICIT_TARGET_ROW_REPLACEMENT": {
            "PROFILE_ID": proven.TARGET,
            "BOUND": target_bound,
            "SOURCE": TARGET_RESULT,
        },
        "PROJECTED_ROW_UPDATES": updates,
        "PROJECTED_FAMILY_BEFORE_BOTH": 313395448,
        "PROJECTED_FAMILY_AFTER_BOTH": 313395344,
        "PROJECTED_FAMILY_DELTA": 104,
        "NEXT_OWNER_IDS": NEXT_OWNERS,
        "GAP_TO_INCUMBENT": 313395344 - INCUMBENT,
        "SOURCE_LEDGER_SHA256_BEFORE": source_digest,
        "SOURCE_LEDGER_SHA256_AFTER": sha(projection(bounds)),
        "OTHER_4644_BOUNDS_SHA256": sha(projection(others)),
        "CURSOR": cursor,
        "CURSOR_PRESERVED": "PASS",
        "CURSOR_SHA256_BEFORE": sha(cursor_before),
        "CURSOR_SHA256_AFTER": sha(render(cursor)),
        "RESOLVED_ROWS": 4647,
        "CURSOR_PROFILES": 197,
        "TOTAL_PROFILES": 4844,
        "SHARED_LEDGER_ADOPTION": "NONE",
        "REPLACES_A_COMBINED_AUTHORITY": "NO",
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": ledger["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
        "T249_ORIGINAL_TASK_STATUS": ledger["TASK_STATUS"],
        "TARGET_ORIGINAL_TASK_STATUS": target["TASK_STATUS"],
    }


def compute_result() -> dict[str, object]:
    helpers = helper_identity()
    donor, ledger, r30 = authority()
    local_s5 = proven.s5_proof(donor)
    certs: dict[str, object] = {}
    caps: dict[str, object] = {}
    degrees: dict[str, object] = {}
    for pid in PROFILES:
        published = obj(obj(donor["PROFILE_CERTIFICATES"])[pid])
        proof = obj(items(r30["GROUP_ATTEMPTS"])[ATTEMPTS[pid]])
        cap_authority(pid, proof)
        require(
            proof == published["CAP_SOURCE_IDENTITY"]
            and published["CAP_SOURCE"]
            == f"b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES"
            f"[{NB_INDICES[pid]}]"
            and published["S4_BASE"] == S4_BASE,
            "original profile source mismatch",
        )
        degree = degree_s5_proof(pid, obj(published["DEGREE_S5_PROOF"]))
        degrees[pid], caps[pid] = degree, proof
        certs[pid] = envelope(pid, published, integer(degree["S5_CAP"]))
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "MATHEMATICAL_CERTIFICATE_REQUIRES_EXACT_TREE_FRESH_JUDGE",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "T249_HEAD": T249_HEAD,
        "T249_TREE": T249_TREE,
        "DONOR_HEAD": proven.DONOR_HEAD,
        "DONOR_TREE": proven.DONOR_TREE,
        "ORIGINAL_DONOR_STATUS": {
            "JUDGE_MODE": donor["JUDGE_MODE"],
            "TASK_STATUS": donor["TASK_STATUS"],
        },
        "SOURCE_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "PROOF": __doc__,
        "BLOB_PINS": {
            p: {"HEAD": h, "BLOB": git("rev-parse", f"{h}:{p}").decode().strip(), "SHA256": s}
            for p, (h, _, s) in PINS.items()
        },
        "HELPER_SHA256": helpers,
        "MODEL": {
            "TICKETS": 20,
            "LABELS_PER_TICKET": 6,
            "POOL": 49,
            "TRIPLES": 22,
            "PAIRS": 27,
            "PAIR_LINEARITY": True,
        },
        "BONFERRONI_PROOF": proven.multiplicity_proof(),
        "S123": proven.s123_proof(),
        "S4_WEIGHTS": proven.s4_weights(),
        "S5_LOCAL_IDENTITY": {
            k: local_s5[k]
            for k in (
                "IDENTITY",
                "LOCAL_CASE_COUNT",
                "LOCAL_COUNTS",
                "LOCAL_HISTOGRAM",
                "LOCAL_TABLE_SHA256",
                "TWO_TRIPLE_K5_WEIGHT",
            )
        },
        "CAP_AUTHORITIES": caps,
        "DEGREE_S5_PROOFS": degrees,
        "PROFILE_CERTIFICATES": certs,
        "FAMILY_EFFECT": family_effect(ledger, certs),
        "B01_TO_B15_AT_COMPUTATION": {
            f"B{i:02}": "PASS" if i <= 11 else "NOT_VERIFIED" for i in range(1, 16)
        },
        "GATE_STATUS_SCOPE": "B12--B15 require external tests/checks, exact-tree Judge and "
        "commit/ownership lifecycle; see final handoff and commit message.",
        "SOLVER_CALLS": 0,
        "PORTFOLIO_ENUMERATIONS": 0,
        "SHARED_LEDGER_WRITES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
    }


def verify_result(value: Mapping[str, object]) -> None:
    require(render(value) == render(compute_result()), "tampered formal dual-profile certificate")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    raw = render(result)
    if args.verify:
        require(RESULT_PATH.read_bytes() == raw, "sealed result bytes differ")
    else:
        require(not RESULT_PATH.exists(), "result already exists")
        with RESULT_PATH.open("xb") as output:
            output.write(raw)
    print(
        json.dumps(
            {
                "STATUS": "PASS",
                "PROFILES": {
                    p: {
                        k: obj(obj(result["PROFILE_CERTIFICATES"])[p])[k]
                        for k in (
                            "FULL_PROFILE_BOUND",
                            "MAX_T",
                            "T265_TERM_BOUND",
                            "STRICT_GAIN_EXCLUDED",
                        )
                    }
                    for p in PROFILES
                },
                "PROJECTED_FAMILY_BOUND": 313395344,
            }
        )
    )


if __name__ == "__main__":
    main()
