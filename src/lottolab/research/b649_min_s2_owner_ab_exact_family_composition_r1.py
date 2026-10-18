"""Reuse two accepted exact-profile certificates and replay the frozen family.

Only immutable Git sources supply authority. The A/B triangle theorems are
never executed or re-proved: this verifier checks their exact scope and
replays the complete rational Route-B envelopes, then replaces two rows in
memory. Every other resolved row and the entire cursor remain inherited.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import stat
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_OWNER_AB_EXACT_FAMILY_COMPOSITION_R1"
OWNER_CONVERSATION_ID = "01a13318-d46a-7f12-a1d6-dda0c9678d2b"
DIRECTORY = "docs/research/matrix-native-results"
SOURCE = "src/lottolab/research/b649_min_s2_owner_ab_exact_family_composition_r1.py"
TEST = "tests/unit/test_b649_min_s2_owner_ab_exact_family_composition_r1.py"
RESULT_PREFIX = "b649-min-s2-owner-ab-exact-family-composition-r1-result-"
PROFILES = ("66655555555511100000", "66665555554431000000")
MODEL: dict[str, object] = {
    "TICKETS": 20,
    "LABELS_PER_TICKET": 6,
    "TRIPLES": 22,
    "PAIRS": 27,
    "PAIR_LINEARITY": True,
}
type Document = dict[str, object]
type Term = tuple[int, int, int, int, int, int]


@dataclass(frozen=True)
class Pin:
    tag: str
    head: str
    tree: str
    result: str
    result_sha256: str
    source: str
    source_sha256: str
    test: str
    test_sha256: str


BASE = Pin(
    "BASE",
    "8d08e843b30300e8379f63e7dc9db401581e2e5e",
    "231494ec0995981d2324cc5ef697ba4b1975b2f0",
    f"{DIRECTORY}/b649-min-s2-two-bonf5-owners-exact-composition-r1-result-"
    "42f6a5ea0e0a5c31bcd67c179ceb40d7599740daf511b57ab29e39bdd1bb4632.json",
    "42f6a5ea0e0a5c31bcd67c179ceb40d7599740daf511b57ab29e39bdd1bb4632",
    "src/lottolab/research/b649_min_s2_two_bonf5_owners_exact_composition_r1.py",
    "ee8ce0b641571e89b8e03f592f9b71009df6bdc92c5d451aa104036c1bb7d8f1",
    "tests/unit/test_b649_min_s2_two_bonf5_owners_exact_composition_r1.py",
    "a39c641c7cdde72163f4ce55ff997848595cfcf513f01caed0f3a189f9e105c7",
)
A = Pin(
    "A",
    "a7a7efb1280156ab3fbab97abac0a2e8cc3cd6ec",
    "fb49c11fcfadfa28618e4a043b240c31c36fc0e3",
    f"{DIRECTORY}/b649-min-s2-owner-a-exact-bound-r1-result.json",
    "1e248e752622645685447e4b2c382f12aab36d5c25d1c42fb7771e16dceabab0",
    "src/lottolab/research/b649_min_s2_owner_a_exact_bound_r1.py",
    "f8e3493fddaf150999db5259be055b84521612476f1edc39acc3351b870a08cd",
    "tests/unit/test_b649_min_s2_owner_a_exact_bound_r1.py",
    "a53df6b4138b1b3f23766be37e73ecc2929fdceb6cb8b97a237ed62124c1986c",
)
B = Pin(
    "B",
    "97dcfa9a2cfec1ef30097d808ecb6f87e9c6241f",
    "83fbdfece095ec5f88ac411a9d2db7a9aaf833f3",
    f"{DIRECTORY}/b649-min-s2-owner-b-exact-bound-r1-result-"
    "9e8bc62cf36eab69a6714237841316609907b9da5a8e7026ffb7955950902a0b.json",
    "9e8bc62cf36eab69a6714237841316609907b9da5a8e7026ffb7955950902a0b",
    "src/lottolab/research/b649_min_s2_owner_b_exact_bound_r1.py",
    "2a176205ceb6b96b929e459c44270d9e4f4fc04389d9507efe75806a5c885290",
    "tests/unit/test_b649_min_s2_owner_b_exact_bound_r1.py",
    "404639ae889f9509e4e9930597b4d1df86373fe5f6842f27b863057e11a2c5c8",
)


@dataclass(frozen=True)
class Authority:
    pin: Pin
    result: Document
    source: bytes
    message: str
    acceptance: Document


type Inputs = tuple[Authority, Authority, Authority]


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def obj(value: object) -> Document:
    require(isinstance(value, dict), "expected object")
    result = cast(dict[object, object], value)
    require(all(isinstance(k, str) for k in result), "non-string object key")
    return cast(Document, result)


def items(value: object) -> list[object]:
    require(isinstance(value, list), "expected list")
    return cast(list[object], value)


def integer(value: object) -> int:
    require(type(value) is int, "expected exact integer")
    return cast(int, value)


def string(value: object) -> str:
    require(isinstance(value, str), "expected string")
    return cast(str, value)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def projection(rows: Mapping[str, int]) -> bytes:
    # The frozen Base uses this serialization for its bound projection digest.
    return json.dumps(
        [{"PROFILE_ID": p, "CURRENT_BOUND": rows[p]} for p in sorted(rows)], sort_keys=True
    ).encode()


def decode(raw: bytes) -> Document:
    def unique(pairs: list[tuple[str, object]]) -> Document:
        require(len(pairs) == len(dict(pairs)), "duplicate JSON key")
        return dict(pairs)

    return obj(json.loads(raw, object_pairs_hook=unique))


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=ROOT)


def checked_blob(head: str, path: str, digest: str) -> bytes:
    require(not Path(path).is_absolute() and ".." not in Path(path).parts, "unsafe source path")
    meta = git("ls-tree", head, "--", path).decode().strip().split("\t")
    require(
        len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path,
        "missing or unsafe immutable blob",
    )
    raw = git("cat-file", "blob", f"{head}:{path}")
    require(sha(raw) == digest, "source SHA256 mismatch")
    return raw


def acceptance(pin: Pin, message: str) -> Document:
    verdicts = re.findall(r"(?im)^Fresh-context Judge: (VERIFIED_WITH_CAVEATS)\.?\s*$", message)
    trees = re.findall(r"(?im)^Judged[- ]tree:\s*([0-9a-f]{40})\s*$", message)
    require(verdicts == ["VERIFIED_WITH_CAVEATS"] and trees == [pin.tree], "Judge binding differs")
    require(pin.result_sha256 in message, "Judge result binding differs")
    result: Document = {
        "VERDICT": verdicts[0],
        "JUDGED_TREE": trees[0],
        "ACCEPTED_COMMIT": pin.head,
        "COMMIT_MESSAGE_SHA256": sha(message.encode()),
        "COMMIT_MESSAGE_VERBATIM": message,
        "LOCATOR": f"git cat-file commit {pin.head}: commit message",
    }
    if pin == A:
        report = message.split("FRESH_JUDGE_REPORT_VERBATIM_BEGIN\n", 1)[1].split(
            "\nFRESH_JUDGE_REPORT_VERBATIM_END", 1
        )[0]
        require(
            "JUDGE_MODE: FRESH_CONTEXT" in report
            and pin.tree in report
            and pin.result_sha256 in report,
            "embedded A Judge identity differs",
        )
        declared = re.findall(r"(?m)^Judge-report-SHA256: ([0-9a-f]{64})$", message)
        require(len(declared) == 1, "missing A historical report hash")
        result.update(
            REPORT_DECLARED_SHA256=declared[0],
            REPORT_COMMITTED_TEXT_SHA256=sha(report.encode()),
            REPORT_VERBATIM=report,
            REPORT_HASH_DISPOSITION=(
                "Historical trailing-whitespace normalization discrepancy retained; "
                "formal accepted verdict and exact committed tree remain authority."
            ),
        )
    if pin == B:
        require(
            "historical catalog label" in message
            and "Legal-support attainment" in message
            and "global K20 optimum remain unknown" in message,
            "B accepted caveats missing",
        )
        declared = re.findall(r"(?m)^Judge report SHA256:([0-9a-f]{64})$", message)
        require(len(declared) == 1, "missing B report identity")
        result.update(
            REPORT_DECLARED_SHA256=declared[0],
            REPORT_HASH_DISPOSITION="Original report hash recorded in exact accepted commit.",
        )
    return result


def load_inputs() -> Inputs:
    loaded: list[Authority] = []
    for pin in (BASE, A, B):
        require(git("cat-file", "-t", pin.head).strip() == b"commit", "wrong commit identity")
        require(
            git("rev-parse", f"{pin.head}^{{tree}}").decode().strip() == pin.tree,
            "wrong tree identity",
        )
        document = decode(checked_blob(pin.head, pin.result, pin.result_sha256))
        require(sha(render(document)) == pin.result_sha256, "noncanonical authority bytes")
        source = checked_blob(pin.head, pin.source, pin.source_sha256)
        checked_blob(pin.head, pin.test, pin.test_sha256)
        require(
            document["IMPLEMENTATION_SHA256"] == pin.source_sha256
            and document["TEST_SHA256"] == pin.test_sha256,
            "result source binding differs",
        )
        message = git("cat-file", "commit", pin.head).split(b"\n\n", 1)[1].decode()
        for path in (pin.result, pin.source, pin.test) if pin == BASE else ():
            local = ROOT / path
            require(stat.S_ISREG(local.lstat().st_mode), "unsafe inherited working file")
            require(
                local.read_bytes() == git("cat-file", "blob", f"{pin.head}:{path}"), "Base drift"
            )
        for path, digest in obj(document.get("SOURCE_PINS", {})).items():
            checked_blob(pin.head, path, string(digest))
        loaded.append(Authority(pin, document, source, message, acceptance(pin, message)))
    return loaded[0], loaded[1], loaded[2]


def profile(pid: str) -> tuple[int, ...]:
    require(len(pid) == 20 and all(c in "0123456" for c in pid), "wrong profile encoding")
    d = tuple(int(c) for c in pid)
    require(sum(d) == 66 and d == tuple(sorted(d, reverse=True)), "wrong profile domain")
    return d


def validate_model(pid: str, model: Mapping[str, object]) -> tuple[int, ...]:
    require(pid in PROFILES, "wrong certificate profile")
    require(
        dict(model) == MODEL
        and model["PAIR_LINEARITY"] is True
        and all(type(model[k]) is int for k in MODEL if k != "PAIR_LINEARITY"),
        "weakened mathematical assumptions",
    )
    return profile(pid)


def rounded_bound(s3: int, s4: int) -> int:
    return (7 * (372_228_640 - 63_838_600 + s3) - 4 * s4 + 6) // 7


def envelope(pid: str, cap: int, s4_floor: int) -> list[Term]:
    d = profile(pid)
    require(type(cap) is int and 22 <= cap <= 264 and s4_floor == 112, "wrong envelope domain")
    g = [6 + v for v in d]
    wedges, third_degrees = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    amax = sum(v * (4 + v) for v in d) // 3
    terms: list[Term] = []
    for t in range(22, cap + 1):
        open_wedges = wedges - 3 * t
        require(open_wedges >= 0, "invalid triangle/wedge range")
        k4 = max(0, -(-(third_degrees - (max(g) - 2) * open_wedges) // 4))
        contained = min(k4, amax)
        s4 = max(s4_floor, 679 * k4 - 231 * contained)
        s3 = 2800 * wedges + 11872 * (t - 22) - 30800
        bound = rounded_bound(s3, s4)
        rational = Fraction(372_228_640 - 63_838_600 + s3) - Fraction(4 * s4, 7)
        require(bound == -(-rational.numerator // rational.denominator), "wrong ceiling or sign")
        terms.append((t, bound, k4, contained, s4, s3))
    return terms


def adopt_certificate(authority: Authority, base: Document) -> Document:
    pin, donor = authority.pin, authority.result
    require(pin in (A, B), "wrong donor authority")
    require(sha(render(donor)) == pin.result_sha256, "altered donor authority")
    require(authority.acceptance == acceptance(pin, authority.message), "altered Judge acceptance")
    require(sha(authority.source) == pin.source_sha256, "altered donor source")
    require(
        ast.get_docstring(ast.parse(authority.source), clean=False) == donor["PROOF"], "proof drift"
    )
    pid = PROFILES[0 if pin == A else 1]
    require(donor["TARGET_PROFILE"] == pid, "wrong target profile")
    model = obj(donor["MODEL"] if pin == A else obj(donor["MODEL_FACTS"])["MODEL"])
    d = validate_model(pid, model)
    require(
        donor["BASE_HEAD"] == BASE.head
        and donor["BASE_TREE"] == BASE.tree
        and donor["BASE_RESULT_SHA256"] == BASE.result_sha256,
        "donor Base identity differs",
    )
    cap = integer(donor["NEW_PROVEN_T_CAP"])
    require(cap == (249 if pin == A else 243), "wrong accepted cap")
    require(
        donor["CURRENT_S4_FLOOR"] == donor["NEW_PROVEN_S4_FLOOR"] == 112
        and donor["CURRENT_T_CAP"] == 264
        and donor["GLOBAL_K20_OPTIMUM"] == "UNKNOWN",
        "wrong inherited mathematical scope",
    )
    if pin == A:
        premises = obj(donor["PREMISES"])
        require(premises["D"] == list(d) and premises["Z"] == 5, "A profile premises differ")
        theorem = obj(donor["CERTIFICATE"])
        require(
            theorem["NEW_T_CAP"] == cap
            and theorem["ATTAINABILITY"] == "NOT_ASSERTED"
            and donor["NEW_PROVEN_S5_CAP"] == "NOT_ADOPTED",
            "A certificate scope weakened",
        )
        old_key, new_key = "CURRENT_ROUTE_BOUND_TERMS", "NEW_ROUTE_BOUND_TERMS"
        reference = obj(donor["INHERITED_CAVEATS_REFERENCE"])
        require(
            reference["HEAD"] == BASE.head
            and reference["PATH"] == BASE.result
            and reference["KEY"] == "INHERITED_CAVEATS_AND_STATUS_VERBATIM"
            and reference["VALUE_SHA256"] == sha(render(base[string(reference["KEY"])])),
            "A inherited caveat reference differs",
        )
    else:
        facts, theorem = obj(donor["MODEL_FACTS"]), obj(donor["THEOREM"])
        require(facts["D"] == list(d) and facts["ZEROS"] == 6, "B profile premises differ")
        require(
            theorem["PROFILE_ID"] == pid
            and theorem["T_CAP"] == cap
            and theorem["LEGAL_SUPPORT_ATTAINMENT"] == "UNKNOWN"
            and theorem["RELAXATION"]
            == "NECESSARY_ONLY; simultaneous graph or support realizability not asserted"
            and obj(donor["GRAPH_COUNTEREXAMPLE_CHECK"])["SUPPORT_REALIZATION"] == "NOT_ASSERTED"
            and donor["S5_USED"] is False
            and donor["NEW_PROVEN_S5_CAP"] is None
            and donor["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
            == base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
            "B relaxation or inherited caveats weakened",
        )
        old_key, new_key = "OLD_FULL_T_ENVELOPE", "NEW_FULL_T_ENVELOPE"
    old, new = envelope(pid, 264, 112), envelope(pid, cap, 112)
    require(
        donor[old_key] == [list(t) for t in old]
        and donor[new_key] == [list(t) for t in new]
        and old[: len(new)] == new,
        "complete profile envelope differs",
    )
    bound, before = max(t[1] for t in new), max(t[1] for t in old)
    require(
        bound == donor["NEW_FULL_PROFILE_BOUND"]
        and before == donor["CURRENT_PROFILE_BOUND"] == obj(base["RESOLVED_ROW_BOUNDS"])[pid]
        and bound <= integer(base["INCUMBENT"])
        and donor["STRICT_GAIN_EXCLUDED"] == ("YES" if pin == A else True),
        "wrong full-profile bound or strict-gain disposition",
    )
    return {
        "PROFILE_ID": pid,
        "FULL_PROFILE_BOUND": bound,
        "PRE_UPDATE_BOUND": before,
        "T_CAP": cap,
        "S4_FLOOR": 112,
        "S5_ADOPTED": False,
        "COMPLETE_T_RANGE": [22, cap],
        "TERM_COUNT": len(new),
        "ALL_T_TERMS": [list(t) for t in new],
        "MAXIMIZING_TERMS": [list(t) for t in new if t[1] == bound],
        "STRICT_GAIN_EXCLUDED": "YES",
        "PROOF_VERBATIM": donor["PROOF"],
        "SOURCE_HEAD": pin.head,
        "SOURCE_TREE": pin.tree,
        "RESULT_SHA256": pin.result_sha256,
        "ATTAINMENT": "NOT_ASSERTED",
    }


def family(rows: Mapping[str, int], cursor: Mapping[str, object]) -> tuple[int, list[str]]:
    coarse = {p: integer(v) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    require(not set(rows).intersection(coarse), "ledger/cursor overlap")
    ranked = sorted((b, p) for p, b in [*rows.items(), *coarse.items()])
    maximum = max([*rows.values(), *coarse.values()])
    owners = sorted(p for p, b in {**rows, **coarse}.items() if b == maximum)
    require(
        (maximum, owners) == (ranked[-1][0], sorted(p for b, p in ranked if b == ranked[-1][0])),
        "independent family maximum differs",
    )
    return maximum, owners


def replay_base(base: Document) -> tuple[dict[str, int], Document]:
    require(sha(render(base)) == BASE.result_sha256, "altered Base authority")
    rows = {p: integer(v) for p, v in obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(base["CURSOR"])
    coarse = obj(cursor["COARSE_BOUND_PROJECTION"])
    require(len(rows) == integer(base["ROWS_TOTAL"]) == 4647, "omitted ledger rows")
    require(
        len(coarse) == len(items(cursor["PROFILE_IDS"])) == integer(cursor["PROFILE_COUNT"]) == 197
        and set(coarse) == set(items(cursor["PROFILE_IDS"]))
        and not set(rows).intersection(coarse),
        "wrong cursor coverage",
    )
    for pid in [*rows, *coarse]:
        profile(pid)
    require(sha(projection(rows)) == base["BOUNDS_SHA256_AFTER"], "ledger projection differs")
    require(
        sha(render(cursor)) == base["CURSOR_SHA256"]
        and max(integer(b) for b in coarse.values()) == cursor["BOUND"],
        "cursor projection differs",
    )
    maximum, owners = family(rows, cursor)
    incumbent = integer(base["INCUMBENT"])
    require(
        maximum == base["FAMILY_BOUND_AFTER"]
        and owners == base["FAMILY_OWNER_IDS"]
        and maximum - incumbent == base["GAP_TO_INCUMBENT"]
        and sum(b > incumbent for b in [*rows.values(), *(integer(v) for v in coarse.values())])
        == base["STILL_OPEN_PROFILE_COUNT"],
        "Base complete-family replay differs",
    )
    return rows, cursor


def compose(
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    inputs: Inputs,
    updates: Sequence[tuple[str, int]],
) -> dict[str, int]:
    require(tuple(a.pin for a in inputs) == (BASE, A, B), "source identity mismatch")
    base, owner_a, owner_b = inputs
    frozen, frozen_cursor = replay_base(base.result)
    before = dict(rows)
    require(
        len(rows) == len(before) == len(frozen)
        and all(type(b) is int for _, b in rows)
        and before == frozen,
        "wrong, duplicate, omitted or modified ledger row",
    )
    require(render(cursor) == render(frozen_cursor), "cursor modification")
    require(
        len(updates) == len({p for p, _ in updates}) == 2
        and {p for p, _ in updates} == set(PROFILES),
        "duplicate, omitted or wrong-profile updates",
    )
    certificates = {
        p: adopt_certificate(a, base.result)
        for p, a in zip(PROFILES, (owner_a, owner_b), strict=True)
    }
    after = dict(before)
    for pid, bound in updates:
        require(
            type(bound) is int
            and bound == integer(certificates[pid]["FULL_PROFILE_BOUND"]) < before[pid],
            "wrong full-profile update bound",
        )
        after[pid] = bound
    require(
        {p for p in before if before[p] != after[p]} == set(PROFILES), "not exactly two changes"
    )
    require(
        projection({p: b for p, b in before.items() if p not in PROFILES})
        == projection({p: b for p, b in after.items() if p not in PROFILES}),
        "other rows changed",
    )
    return after


def status_snapshot(document: Document) -> Document:
    return {
        k: v
        for k, v in document.items()
        if (
            any(t in k for t in ("STATUS", "CAVEAT", "PRIOR", "GATE", "JUDGE"))
            or k == "BOUND_SOURCE"
            or k.endswith("_AT_SEAL")
        )
        and k != "INHERITED_CAVEATS_AND_STATUS_VERBATIM"
    }


def compute_result(inputs: Inputs | None = None) -> Document:
    sources = load_inputs() if inputs is None else inputs
    require(tuple(a.pin for a in sources) == (BASE, A, B), "source identity mismatch")
    base = sources[0]
    before, cursor = replay_base(base.result)
    certs = {
        p: adopt_certificate(a, base.result) for p, a in zip(PROFILES, sources[1:], strict=True)
    }
    updates = [(p, integer(certs[p]["FULL_PROFILE_BOUND"])) for p in PROFILES]
    after = compose(list(before.items()), cursor, sources, updates)
    before_max, before_owners = family(before, cursor)
    maximum, owners = family(after, cursor)
    singles = {p: family({**before, p: b}, cursor)[0] for p, b in updates}
    incumbent = integer(base.result["INCUMBENT"])
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_LIFECYCLE",
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "PROVENANCE": {
            a.pin.tag: {
                "HEAD": a.pin.head,
                "TREE": a.pin.tree,
                "RESULT": a.pin.result,
                "RESULT_SHA256": sha(render(a.result)),
                "SOURCE_SHA256": sha(a.source),
                "TEST_SHA256": a.pin.test_sha256,
                "ACCEPTANCE": a.acceptance,
            }
            for a in sources
        },
        "IMPLEMENTATION_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "PROFILE_CERTIFICATES": certs,
        "ROWS_TOTAL": len(before),
        "ROWS_CHANGED": sum(before[p] != after[p] for p in before),
        "ROW_UPDATES": {p: {"BEFORE": before[p], "AFTER": b} for p, b in updates},
        "OTHER_ROWS_UNCHANGED": "PASS",
        "OTHER_4645_BOUNDS_SHA256": sha(
            projection({p: b for p, b in before.items() if p not in PROFILES})
        ),
        "BOUNDS_SHA256_BEFORE": sha(projection(before)),
        "BOUNDS_SHA256_AFTER": sha(projection(after)),
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "CURSOR": cursor,
        "CURSOR_SHA256": sha(render(cursor)),
        "CURSOR_PRESERVED": "PASS",
        "CURSOR_PROFILE_COUNT": cursor["PROFILE_COUNT"],
        "FAMILY_BOUND_BEFORE": before_max,
        "FAMILY_AFTER_SINGLE_UPDATE": singles,
        "FAMILY_BOUND_AFTER": maximum,
        "EXACT_FAMILY_DELTA": before_max - maximum,
        "FAMILY_OWNER_IDS_BEFORE": before_owners,
        "FAMILY_OWNER_IDS": owners,
        "INCUMBENT": incumbent,
        "GAP_TO_INCUMBENT": maximum - incumbent,
        "STILL_OPEN_PROFILE_COUNT": sum(
            b > incumbent
            for b in [
                *after.values(),
                *(integer(v) for v in obj(cursor["COARSE_BOUND_PROJECTION"]).values()),
            ]
        ),
        "CERTIFICATES_ADOPTED_UNCHANGED": base.result["CERTIFICATES_ADOPTED"],
        "INHERITED_TARGET_BONFERRONI_5_UNCHANGED": base.result["INHERITED_TARGET_BONFERRONI_5"],
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": base.result[
            "INHERITED_CAVEATS_AND_STATUS_VERBATIM"
        ],
        "BASE_PROVENANCE_VERBATIM": base.result["PROVENANCE"],
        "SOURCE_STATUS_VERBATIM": {a.pin.tag: status_snapshot(a.result) for a in sources},
        "DONOR_B_BOUND_SOURCE_DISPOSITION": (
            "Historical catalog label; no new JSON pointer asserted."
        ),
        "DONOR_B_ATTAINMENT": (
            "T243 necessary-condition relaxation does not assert legal support attainment."
        ),
        "G01_TO_G16_AT_SEAL": {f"G{i:02}": "NOT_VERIFIED" for i in range(1, 17)},
        "GATE_STATUS_SCOPE": (
            "External exact-tree Fresh Judge and subsequent single-commit/clean/release lifecycle."
        ),
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "MATHEMATICAL_THEOREMS_REEXECUTED": 0,
        "SOLVER_CALLS": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "EXISTING_CERTIFICATES_MUTATED": "NO",
        "CURSOR_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
    }


def result_path() -> Path | None:
    paths = sorted((ROOT / DIRECTORY).glob(f"{RESULT_PREFIX}*.json"))
    require(len(paths) <= 1, "duplicate composition results")
    if not paths:
        return None
    path = paths[0]
    require(stat.S_ISREG(path.lstat().st_mode), "unsafe result file")
    require(
        path.name == f"{RESULT_PREFIX}{sha(path.read_bytes())}.json", "result identity mismatch"
    )
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
        json.dumps(
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
    )


if __name__ == "__main__":
    main()
