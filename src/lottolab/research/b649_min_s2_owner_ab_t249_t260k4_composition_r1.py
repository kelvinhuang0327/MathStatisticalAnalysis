"""Exact composition of two accepted certificates into one Family authority.

The immutable Owner A/B proofs, including their 1661/73-state coverage, are
reused, never re-enumerated. Every adopted integer T term is reconstructed
with both integer and Fraction arithmetic. For g=6+d, W=sum C(g,2) and
J=sum C(g,3), q=max(0,ceil((J-10*(W-3T))/4)) is the K4 lower floor.
The contained-triple K4 allowance is 197 for A and the proved 185 for B.
Thus S4>=max(112,679*q-231*min(q,allowance)), with exact S3 from the
sealed evaluator. UB(T)=ceil(S1-S2+S3-4*S4/7). The entire T domain,
including its profile-specific S4 floor at every T, must match the donor.
There is no S5 authority. Endpoint attainability is not asserted.

Each of S0/A-only/B-only/both starts afresh from all 4647 immutable resolved
rows and the unchanged 197-profile cursor, including its coverage metadata.
The Family maximum is computed over all 4844 profiles, never assigned from
the acceptance comparison. Historical pending/self-check dispositions and
all inherited caveats retain their original meaning under immutable pins.
Only this isolated result becomes the new joint Family authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
from math import ceil, comb
from pathlib import Path
from typing import cast

type Document = dict[str, object]
ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_OWNER_AB_T249_T260K4_EXACT_COMPOSITION_R1"
OWNER_CONVERSATION_ID = "01a13e4e-6992-7b82-bc90-b2eac888e962"
STEM = "b649_min_s2_owner_ab_t249_t260k4_composition_r1"
SOURCE = f"src/lottolab/research/{STEM}.py"
TEST = f"tests/unit/test_{STEM}.py"
DIRECTORY = "docs/research/matrix-native-results/"
RESULT = DIRECTORY + STEM.replace("_", "-") + "-result.json"
BASE_HEAD = "bee6acaaf9d2781e2aae560138d8be99fb4789ed"
BASE_TREE = "7b382a405d8d734763b477aa88efafeba2e1ed9b"
BASE_RESULT = DIRECTORY + "b649-min-s2-w784-39-goodman-exact-authority-r1-result.json"
BASE_SHA = "bca4ad19aebb9808c952259d677a4a07381aa43392c38715c8265427960fe6f6"
A = "66655555555331100000"
B = "66655555555411110000"
INCUMBENT = 313263888
OLD_BOUND = 313391740
MODEL = {"TICKETS": 20, "LABELS_PER_TICKET": 6, "TRIPLES": 22, "PAIRS": 27, "PAIR_LINEARITY": True}


@dataclass(frozen=True)
class Donor:
    profile: str
    head: str
    tree: str
    stem: str
    result_sha: str
    source_sha: str
    test_sha: str
    sealed_report_sha: str
    final_report_sha: str
    cap: int
    k4_cap: int
    bound: int


DONORS = (
    Donor(
        A,
        "c4c83e6bfed718db133b69aaec4431e9dcd690ce",
        "b1339e0a35fb3cf40b06ffc4053ba502fc4c76c4",
        "b649_min_s2_owner_666555555553311_exact_cert_r1",
        "7709b51fb56bafb90f6370b7e9add76bee29f558f422764a273f3afe1ce6a5ad",
        "2952bffa5d54b9df9ac3364bf90604e1df7cdbef326e12ccb790659197b77128",
        "4204cdd52baa8c941db0e5ba144ecc4b8cd2fb0157e8b7854def97524543b21b",
        "1dc62174c62db0cd805517fdf286ffbdf4a80499999eb3cf1fd006ad976eb3c3",
        "4a65c8d7562177468343ec7394c54c5358c0d26332b4603b53b48c2ae9d0da3f",
        249,
        197,
        313248348,
    ),
    Donor(
        B,
        "aa8b5f4f53d28b90c0c0072bb723205240c0ba86",
        "1840c5231286302fe6bbffcb6d9add2c14bf8c96",
        "b649_min_s2_owner_6665555555541111_exact_cert_r1",
        "75edb5824b1e108847c9dbfb7468d5c4ea674795ff245c5817216ce4f3cbb598",
        "2207c1827e4342fa31646cef34422350f5fe5a30963eb03024491ef294668e71",
        "3db4e2634ef4d4e6553226bd22043be5acf513b98356d7f0348b55b5a792d57a",
        "8cd32ebed26fccbf95d3943193dda3171705c73f3eb16d8d4e7421fcc4d3bb32",
        "8cd32ebed26fccbf95d3943193dda3171705c73f3eb16d8d4e7421fcc4d3bb32",
        260,
        185,
        313345152,
    ),
)


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def obj(value: object) -> Document:
    require(isinstance(value, dict), "expected object")
    return cast(Document, value)


def integer(value: object) -> int:
    require(type(value) is int, "expected integer")
    return cast(int, value)


def ledger(value: object) -> dict[str, int]:
    return {k: integer(v) for k, v in obj(value).items()}


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", *args],
        cwd=ROOT,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def working(path: str) -> bytes:
    target = ROOT / path
    require(target.is_file() and not target.is_symlink(), "unsafe working file")
    return target.read_bytes()


def frozen(head: str, path: str, digest: str) -> bytes:
    meta = git("ls-tree", head, "--", path).decode().strip().split("\t")
    require(
        len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path,
        "unsafe immutable blob",
    )
    raw = git("cat-file", "blob", f"{head}:{path}")
    require(sha(raw) == digest, "immutable SHA256 mismatch")
    return raw


def load_base() -> Document:
    require(git("rev-parse", BASE_HEAD + "^{tree}").decode().strip() == BASE_TREE, "Base tree")
    raw = frozen(BASE_HEAD, BASE_RESULT, BASE_SHA)
    require(working(BASE_RESULT) == raw, "Base working bytes")
    base = obj(json.loads(raw))
    require(base["MODEL"] == MODEL and base["INCUMBENT"] == INCUMBENT, "Base model")
    return base


def load_donor(pin: Donor) -> Document:
    require(git("rev-parse", pin.head + "^{tree}").decode().strip() == pin.tree, "donor tree")
    source = f"src/lottolab/research/{pin.stem}.py"
    test = f"tests/unit/test_{pin.stem}.py"
    frozen(pin.head, source, pin.source_sha)
    frozen(pin.head, test, pin.test_sha)
    result = DIRECTORY + pin.stem.replace("_", "-") + "-result.json"
    doc = obj(json.loads(frozen(pin.head, result, pin.result_sha)))
    require(
        doc["SOURCE_SHA256"] == pin.source_sha and doc["TEST_SHA256"] == pin.test_sha,
        "donor source/result binding",
    )
    require(
        doc["BASE_HEAD"] == BASE_HEAD
        and doc["BASE_TREE"] == BASE_TREE
        and doc["BASE_RESULT_SHA256"] == BASE_SHA,
        "donor Base binding",
    )
    message = git("show", "-s", "--format=%B", pin.head).decode()
    require(
        pin.tree in message
        and pin.sealed_report_sha in message
        and "Fresh-context" in message
        and "G01-G17 PASS" in message,
        "donor Judge seal",
    )
    for path, digest in obj(doc["EVALUATOR_SOURCE_PINS"]).items():
        relative = path if path.startswith("src/") else "src/lottolab/research/" + path
        require(isinstance(digest, str), "evaluator digest")
        raw = frozen(pin.head, relative, cast(str, digest))
        require(
            frozen(BASE_HEAD, relative, cast(str, digest)) == raw and working(relative) == raw,
            "evaluator source closure",
        )
    return doc


def terms(profile: str, cap: int, k4_cap: int) -> list[Document]:
    require(profile in (A, B) and type(cap) is int and 22 <= cap <= 265, "profile/T domain")
    require(type(k4_cap) is int and k4_cap in (185, 197), "contained K4 scope")
    ds = tuple(map(int, profile))
    g = tuple(6 + d for d in ds)
    w, j = sum(comb(x, 2) for x in g), sum(comb(x, 3) for x in g)
    require(w == 827 and j == (2318 if profile == A else 2320), "profile degree identity")
    result: list[Document] = []
    for t in range(22, cap + 1):
        wedges = w - 3 * t
        q = max(0, -(-(j - 10 * wedges) // 4))
        contained = min(q, k4_cap)
        s4 = max(112, 679 * q - 231 * contained)
        s3 = 2800 * wedges + 20272 * (t - 22) + 7000 * 22
        bound = 372228640 - 63838600 + s3 - 4 * s4 // 7
        q_ref = max(0, ceil(Fraction(j - (max(g) - 2) * wedges, 4)))
        s4_ref = max(112, 448 * min(q_ref, k4_cap) + 679 * max(0, q_ref - k4_cap))
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4_ref, 7)
        require(q == q_ref and s4 == s4_ref and bound == ceil(exact), "exact arithmetic")
        result.append(
            {
                "T": t,
                "BOUND": bound,
                "K4_FLOOR": q,
                "CONTAINED_K4": contained,
                "S4": s4,
                "S3": s3,
                "OPEN_WEDGES": wedges,
            }
        )
    return result


def maximum(envelope: list[Document]) -> int:
    return max(integer(t["BOUND"]) for t in envelope)


def a_format(envelope: list[Document]) -> list[list[int]]:
    columns = ("T", "BOUND", "K4_FLOOR", "CONTAINED_K4", "S4", "S3")
    return [[integer(term[k]) for k in columns] for term in envelope]


def verify_certificate(pin: Donor, doc: Document) -> Document:
    require(doc["MODEL"] == MODEL, "donor model")
    profile = obj(doc["FACTS"])["PROFILE"] if pin.profile == A else doc["TARGET_PROFILE"]
    require(profile == pin.profile, "wrong profile identity")
    require(
        doc["NEW_PROVEN_T_CAP"] == pin.cap and doc["NEW_PROVEN_S5"] == "NOT_USED",
        "adopted T cap or S5 authority",
    )
    require(
        doc["NEW_FULL_PROFILE_BOUND"] == pin.bound
        and doc["STRICT_GAIN_EXCLUDED"] is (pin.bound <= INCUMBENT),
        "full-profile bound",
    )
    envelope = terms(pin.profile, pin.cap, pin.k4_cap)
    if pin.profile == A:
        domain = obj(doc["ENUMERATION"])
        require(
            domain["RETAINED_STATES"] == 1661
            and domain["CAP"] == pin.cap
            and sha(render(domain["STATES"])) == domain["STATES_SHA256"],
            "A coverage seal",
        )
        require(
            doc["NEW_T_TERMS"] == a_format(envelope) and doc["NEW_TERM_COUNT"] == 228,
            "A complete adopted T terms or S4 scope",
        )
        old = terms(A, 265, 197)
        require(
            doc["OLD_T_TERMS"] == a_format(old)
            and doc["OLD_TERM_COUNT"] == 244
            and maximum(old) == OLD_BOUND,
            "A complete old envelope",
        )
    else:
        k4 = obj(doc["K4_CERTIFICATE"])
        states = cast(list[Document], k4["STATES"])
        require(
            k4["CAP"] == 185
            and k4["STATE_COUNT"] == len(states) == 73
            and max(integer(s["CAP"]) for s in states) == 185,
            "B K4 cap/coverage scope",
        )
        require(
            doc["NEW_PROVEN_S4"] == "MAX(112, 679*q(T)-231*MIN(q(T),185))"
            and doc["T_TERMS"] == envelope,
            "B complete adopted T terms or S4 scope",
        )
        preserved = obj(doc["PRESERVED_T260_CERTIFICATE"])
        require(
            preserved["T_TERMS"] == terms(B, 260, 197)
            and preserved["NEW_FULL_PROFILE_BOUND"] == maximum(terms(B, 260, 197)) == 313346736,
            "B preserved weaker comparison",
        )
        comparison = obj(doc["T265_K4_ONLY_PROJECTION"])
        require(
            comparison["T_CAP"] == 265
            and comparison["NEW_TERMS"] == terms(B, 265, 185)
            and comparison["BOUND"] == maximum(terms(B, 265, 185)) == 313390156,
            "B T265 comparison scope",
        )
        require(doc["JOINT_T260_K4_BOUND"] == pin.bound, "B joint authority")
    require(maximum(envelope) == pin.bound, "false full-envelope maximum")
    return {
        "IDENTITY": asdict(pin),
        "T_RANGE": [22, pin.cap],
        "TERM_COUNT": len(envelope),
        "TERMS": envelope,
        "FULL_BOUND": maximum(envelope),
        "STRICT_GAIN_EXCLUDED": pin.bound <= INCUMBENT,
        "FRESH_JUDGE": "VERIFIED_WITH_CAVEATS",
        "JUDGE_BINDING": "Immutable commit seals scientific report SHA and exact judged tree; "
        "hash-verified original reports retained in task evidence",
    }


def family(rows: Mapping[str, int], cursor: Mapping[str, int]) -> Document:
    require(
        len(rows) == 4647 and len(cursor) == 197 and not set(rows) & set(cursor),
        "complete Family coverage",
    )
    entries = [*rows.items(), *cursor.items()]
    bound = max(b for _, b in entries)
    ordered = sorted(entries, key=lambda pair: (-pair[1], pair[0]))
    require(bound == ordered[0][1], "independent Family maximum")
    owners = sorted(p for p, b in entries if b == bound)
    require(owners == [p for p, b in ordered if b == bound], "independent Family owners")
    return {
        "FAMILY_BOUND": bound,
        "OWNER_IDS": owners,
        "GAP_TO_INCUMBENT": bound - INCUMBENT,
        "STILL_OPEN_PROFILE_COUNT": sum(b > INCUMBENT for _, b in entries),
        "RESOLVED_MAXIMUM": max(rows.values()),
        "CURSOR_MAXIMUM": max(cursor.values()),
    }


def replay(base: Document, updates: Sequence[tuple[str, int]]) -> tuple[dict[str, int], Document]:
    # This guard is in the production path; malformed input cannot borrow a trusted SHA label.
    require(base == load_base(), "immutable Base rows/cursor/coverage mismatch")
    rows = ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = obj(base["CURSOR"])
    projection = ledger(cursor["COARSE_BOUND_PROJECTION"])
    require(
        cursor["PROFILE_COUNT"] == 197
        and len(cast(list[str], cursor["PROFILE_IDS"])) == 197
        and set(cast(list[str], cursor["PROFILE_IDS"])) == set(projection),
        "cursor membership",
    )
    require(len(updates) == len({p for p, _ in updates}), "duplicate update")
    allowed = {pin.profile: pin.bound for pin in DONORS}
    revised = dict(rows)
    for pid, bound in updates:
        require(
            pid in allowed and type(bound) is int and bound == allowed[pid],
            "update profile/bound authority",
        )
        require(rows[pid] == OLD_BOUND, "old owner bound")
        revised[pid] = bound
    changed = sorted(p for p in rows if revised[p] != rows[p])
    require(changed == sorted(p for p, _ in updates), "exact changed rows")
    other = {p: b for p, b in rows.items() if p not in changed}
    require(other == {p: b for p, b in revised.items() if p not in changed}, "other rows changed")
    return revised, {
        **family(revised, projection),
        "UPDATED_IDS": changed,
        "OTHER_ROWS_UNCHANGED": len(other),
        "OTHER_ROWS_SHA256": sha(render(other)),
        "CURSOR_SHA256": sha(render(cursor)),
    }


def dispositions(doc: Document) -> Document:
    # Whole matching subtrees are kept verbatim; remaining content stays bound by result SHA.
    keys = (
        "INHERITED",
        "CAVEAT",
        "PRIOR",
        "STATUS",
        "AUTHORITY",
        "S5",
        "LEGAL",
        "GLOBAL",
        "HISTORICAL",
        "EXTERNAL",
        "G01_TO_G18",
        "PRESERVED_T260_CERTIFICATE",
    )
    return {k: v for k, v in doc.items() if any(word in k for word in keys)}


def compose(base: Document, donors: Sequence[Document]) -> Document:
    require(len(donors) == 2, "two sealed donors required")
    certificates = [verify_certificate(pin, doc) for pin, doc in zip(DONORS, donors, strict=True)]
    selections = (
        (),
        ((A, DONORS[0].bound),),
        ((B, DONORS[1].bound),),
        ((A, DONORS[0].bound), (B, DONORS[1].bound)),
    )
    labels = ("S0_BASE", "S1_OWNER_A_ONLY", "S2_OWNER_B_ONLY", "S3_BOTH")
    scenarios: Document = {}
    final_rows: dict[str, int] = {}
    for label, updates in zip(labels, selections, strict=True):
        final_rows, snapshot = replay(base, updates)
        scenarios[label] = snapshot
    final = obj(scenarios["S3_BOTH"])
    require(
        [obj(scenarios[label])["FAMILY_BOUND"] for label in labels]
        == [313391740, 313391740, 313391740, 313391636],
        "Family acceptance comparison",
    )
    require(
        final["OWNER_IDS"] == ["66665555555321100000"]
        and final["GAP_TO_INCUMBENT"] == 127748
        and final["STILL_OPEN_PROFILE_COUNT"] == 1515,
        "owner/gap/open acceptance",
    )
    return {
        "PROFILE_CERTIFICATES": certificates,
        "SCENARIOS": scenarios,
        "RESOLVED_ROW_BOUNDS": final_rows,
        "CURSOR": base["CURSOR"],
        "FAMILY_AFTER": final,
        "FAMILY_DELTA": integer(obj(scenarios["S0_BASE"])["FAMILY_BOUND"])
        - integer(final["FAMILY_BOUND"]),
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": {
            "BASE": dispositions(base),
            "OWNER_A": dispositions(donors[0]),
            "OWNER_B": dispositions(donors[1]),
            "REFERENCE_POLICY": "Full original objects remain SHA-pinned; no disposition upgraded",
        },
    }


def compute_result() -> Document:
    base = load_base()
    donors = [load_donor(pin) for pin in DONORS]
    composed = compose(base, donors)
    return {
        "TASK_ID": TASK_ID,
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "TASK_STATUS": "JOINT_SCIENTIFIC_AUTHORITY_SEALED; FINAL_JUDGE_AND_LIFECYCLE_EXTERNAL",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_SHA,
        "MODEL": MODEL,
        "INCUMBENT": INCUMBENT,
        "RESOLVED_ROWS": 4647,
        "ROWS_UPDATED": 2,
        "OTHER_ROWS_UNCHANGED": 4645,
        "CURSOR_PROFILES": 197,
        "CURSOR_PRESERVED": True,
        "S5_AUTHORITY": "NONE; NOT_USED",
        "PROOF_SCOPE": __doc__,
        "SOURCE_SHA256": sha(working(SOURCE)),
        "TEST_SHA256": sha(working(TEST)),
        "HISTORICAL_R15": "NOT_VERIFIED",
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        **composed,
    }


def verify_result(candidate: Document) -> None:
    require(
        candidate == compute_result(), "sealed result / maximum / inherited disposition mismatch"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    payload = render(result)
    if args.write_result:
        require(not (ROOT / RESULT).exists(), "result exists; read before replacement")
        (ROOT / RESULT).write_bytes(payload)
    else:
        require(working(RESULT) == payload, "sealed result bytes mismatch")
    print(
        json.dumps(
            {
                "RESULT_SHA256": sha(payload),
                "FAMILY_AFTER": result["FAMILY_AFTER"],
                "FAMILY_DELTA": result["FAMILY_DELTA"],
            }
        )
    )


if __name__ == "__main__":
    main()
