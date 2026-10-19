"""Compose three already judged Goodman certificates over the sealed T248 authority.

No Goodman proof/search entrypoint is executed. Adopt the committed T caps and
independently reproduce every integer Route-B term, including rational rounding.
Replay the sealed six-row bounds snapshot and recorded T256/T248 replacements;
then change exactly three of 4647 bounds and their complete owner rows in memory.
The other 4644 rows have byte-identical canonical bound projections. This view
does not claim a new digest of their full metadata (the inherited A caveat).
The cursor's 197 identities are checked against its sealed partition digest;
their existing coarse bounds, representative, count, and partition stay fixed.
All inherited caveat/status fields and original Judge commit messages remain
verbatim, including historical resource-conformance failure and SELF_CHECK_ONLY.
The resulting family bound includes the unresolved cursor. Feasibility, cap
attainment and global K20 optimality are not asserted. Local Git objects remain
necessary for reproduction. No solver, portfolio search, DB/RUN1/shared-ledger
mutation or remote write is performed.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import cast

TASK_ID = "B649_MIN_S2_THREE_TIED_OWNERS_EXACT_COMPOSITION_R1"
BASE_HEAD = "8d2411474c721264697438428b09a2ff00ea6802"
BASE_TREE = "e7b2717e4f31d40bc213d6918a58b86a486f0375"
ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = "docs/research/matrix-native-results"
RESULT_PATH = ROOT / DIRECTORY / "b649-min-s2-three-tied-owner-combined-authority-r1-result.json"
TARGETS = ("66555555555531000000", "66655555554441000000", "66655555555422000000")
CAPS: dict[str, int] = dict(zip(TARGETS, (241, 239, 237), strict=True))
PACKET_BOUNDS: dict[str, int] = dict(
    zip(TARGETS, (313_183_160, 313_165_236, 313_147_312), strict=True)
)
INCUMBENT = 313_263_888
FAMILY_BEFORE = 313_398_248
SIX = "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
T256 = "b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
T248 = "b649-min-s2-post-t256-next-owner-cap248-cert-r1-result.json"
COVERAGE = "b649-k20-min-s2-topw12-coverage-repair-r1-result.json"
RESULT_PINS = {
    SIX: "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f",
    T256: "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743",
    T248: "28fe692403cb193ee908708c7775b45bd80a2e4cf731b4d4e015d71c5558aabe",
    COVERAGE: "b49eae19b944e3b631933b26bb9aa707e750b14ae36049dd2744d51f6357595b",
}
SOURCE_PINS = {
    "b649_min_s2_post_t256_next_owner_cap248_cert_r1": (
        "452439639d7528be3b93d85718c95699db7fa668c9d8b8b21f23047f7c851766"
    ),
    "b649_min_s2_next_owner_core_zero_t256_cert_r1": (
        "49a7364b7fbcb2ed03fdd6c3eda43067f38fdcbbda6caee7a6eedf71fa02fa04"
    ),
    "b649_min_s2_six_row_existing_s4_family_authority_r1": (
        "928eeffffa2ebf1c7d44c7e395b35740cbeb648af9dc81dd7d628a36b6d6ecac"
    ),
    "b649_k20_min_s2_route_b_current_owner_refinement_r32": (
        "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d"
    ),
    "b649_k20_min_s2_realizable_core_class_bound_r4": (
        "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec"
    ),
}
type Term = tuple[int, int, int, int, int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def obj(value: object) -> dict[str, object]:
    require(isinstance(value, dict), "expected JSON object")
    out = cast(dict[object, object], value)
    require(all(isinstance(k, str) for k in out), "non-string JSON key")
    return cast(dict[str, object], out)


def items(value: object) -> list[object]:
    require(isinstance(value, list), "expected JSON array")
    return cast(list[object], value)


def integer(value: object) -> int:
    require(type(value) is int, "expected exact integer")
    return cast(int, value)


def string(value: object) -> str:
    require(isinstance(value, str), "expected string")
    return cast(str, value)


def render(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    require(len({k for k, _ in pairs}) == len(pairs), "duplicate JSON key/row")
    return dict(pairs)


def decode(raw: bytes) -> dict[str, object]:
    return obj(json.loads(raw, object_pairs_hook=unique_object))


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-c", "core.fsmonitor=false", *args], cwd=ROOT)


def blob(head: str, path: str, digest: str) -> bytes:
    metadata = git("ls-tree", head, "--", path).decode().split()
    require(len(metadata) == 4 and metadata[:2] == ["100644", "blob"], "missing/unsafe donor blob")
    raw = git("show", f"{head}:{path}")
    require(sha(raw) == digest, f"source-hash mismatch: {head}:{path}")
    return raw


@dataclass(frozen=True)
class Pin:
    head: str
    tree: str
    module: str
    source_hash: str
    test_hash: str
    filename: str
    result_hash: str


A = Pin(
    "4093f95f4f27ea23a5dd4d74cd7c99ff1b97b92b",
    "24280b140a7445744fb11497605c2e184555e79c",
    "b649_min_s2_tied_owner_a_goodman241_cert_r1",
    "9c24470e396a151ffb006985ae5be05235abe9dd638761a31130b4a95667866c",
    "4e8e12f4257c5ab26a0fb94a2ee80c32787ceabfaf7aa1efe52a241b91a059a1",
    "b649-min-s2-tied-owner-a-goodman241-cert-r1-result.json",
    "a19fd190f8214da291903a63e4e73b15df11d21a794b194454e4ba580c0f6242",
)
BC = Pin(
    "a441c6ab8000496f4d28d3bd656c41678976e913",
    "d0a67f2734288603afe8b55699493d1fb0e21ad0",
    "b649_min_s2_tied_owners_bc_goodman_cert_r1",
    "c32c62e342b2887c7bffdea9720d2f4aefb3aea7c6863b6846119b4587ae04b3",
    "cd3def1c39cf97af2383ee77465e2137049f2b30fa632823b6fde95a2f9672ca",
    "b649-min-s2-tied-owners-bc-goodman-cert-r1-"
    "6a2425cce2c9b7f321fc9fc4f540ad72d0330a966e9cd74fda2e1377f2cef0d7.json",
    "6a2425cce2c9b7f321fc9fc4f540ad72d0330a966e9cd74fda2e1377f2cef0d7",
)


def commit_identity(head: str, tree: str) -> str:
    require(git("cat-file", "-t", head).strip() == b"commit", "not a Git commit")
    require(git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "commit tree mismatch")
    message = git("log", "-1", "--format=%B", head).decode()
    require(
        "Fresh-context Judge: VERIFIED_WITH_CAVEATS" in message and tree in message,
        "missing exact-tree Fresh Judge disposition",
    )
    return message


def donor(pin: Pin) -> tuple[dict[str, object], dict[str, object]]:
    message = commit_identity(pin.head, pin.tree)
    require(git("rev-parse", f"{pin.head}^").decode().strip() == BASE_HEAD, "donor base differs")
    source_path = f"src/lottolab/research/{pin.module}.py"
    test_path = f"tests/unit/test_{pin.module}.py"
    source = blob(pin.head, source_path, pin.source_hash)
    blob(pin.head, test_path, pin.test_hash)
    result_path = f"{DIRECTORY}/{pin.filename}"
    result = decode(blob(pin.head, result_path, pin.result_hash))
    require(
        (result["BASE_HEAD"], result["BASE_TREE"]) == (BASE_HEAD, BASE_TREE)
        and ast.get_docstring(ast.parse(source), clean=False) == result["PROOF"],
        "donor proof/base binding differs",
    )
    dependencies = obj(
        obj(result["SUPPORT_MODEL"])["PINNED_SOURCES"] if pin == A else result["MODULE_PROVENANCE"]
    )
    for path, digest in dependencies.items():
        raw = blob(pin.head, path, string(digest))
        require(raw == git("show", f"{BASE_HEAD}:{path}"), "donor shared dependency differs")
    return result, {
        "HEAD": pin.head,
        "TREE": pin.tree,
        "JUDGE": "VERIFIED_WITH_CAVEATS",
        "JUDGE_COMMIT_MESSAGE_VERBATIM": message,
        "BLOBS": {
            source_path: pin.source_hash,
            test_path: pin.test_hash,
            result_path: pin.result_hash,
        },
        "DEPENDENCY_PINS": dependencies,
        "CAP_AUTHORITY": "COMMITTED_ALREADY_JUDGED_CERTIFICATE_NOT_REPROVED",
    }


def projection(bounds: Mapping[str, int]) -> bytes:
    return json.dumps(
        [{"PROFILE_ID": p, "CURRENT_BOUND": bounds[p]} for p in sorted(bounds)], sort_keys=True
    ).encode()


def row_map(rows: Sequence[tuple[str, int]]) -> dict[str, int]:
    require(len(rows) == 4647, "ledger must contain exactly 4647 rows")
    require(len({p for p, _ in rows}) == len(rows), "duplicate ledger row")
    require(all(type(v) is int for _, v in rows), "noninteger bound row")
    require(all(sum(p == target for p, _ in rows) == 1 for target in TARGETS), "missing target row")
    return dict(rows)


def cursor_ids() -> list[str]:
    """Only the inherited W=774..785 histogram band; no support/portfolio enumeration."""
    out: list[str] = []

    def visit(prefix: str, n: int, mass: int, squares: int, ceiling: int) -> None:
        if n == 0:
            if mass == 0 and 222 <= squares <= 244:
                out.append(prefix)
            return
        if mass < 0 or mass > n * ceiling or squares + (mass * mass + n - 1) // n > 244:
            return
        for d in range(min(ceiling, mass), -1, -1):
            visit(prefix + str(d), n - 1, mass - d, squares + d * d, d)

    visit("", 20, 66, 0, 6)
    return sorted(out, reverse=True)


def cursor_authority(
    six: Mapping[str, object], coverage: Mapping[str, object]
) -> dict[str, object]:
    cursor, partition = obj(six["CURSOR"]), obj(six["CURSOR_PARTITION_AUTHORITY"])
    require(partition == coverage["PROFILE_PARTITION_BEFORE_REPAIR"], "cursor partition tamper")
    band = obj(partition["UNRESOLVED_FRONTIER_UNDER_W785_CURSOR"])
    ids = cursor_ids()
    bounds = {
        p: 372_228_640
        - 63_838_600
        + 2800 * sum(comb(6 + int(d), 2) for d in p)
        + 11872 * (sum(comb(6 + int(d), 2) for d in p) // 3 - 22)
        - 30800
        - (4 * 112) // 7
        for p in ids
    }
    require(
        len(ids)
        == band["COUNT"]
        == six["CURSOR_PROFILE_COUNT"]
        == obj(coverage["FRONTIER_COVERAGE"])["UNRESOLVED_PROFILES"]
        and sha(json.dumps(ids).encode()) == band["IDS_SHA256"]
        and cursor["ID"] in bounds
        and bounds[string(cursor["ID"])]
        == cursor["BOUND"]
        == max(bounds.values())
        == obj(coverage["FRONTIER_COVERAGE"])["COARSE_AT_W_MAX"],
        "cursor identities/count/bound tamper",
    )
    return {
        **cursor,
        "PROFILE_COUNT": len(ids),
        "PARTITION": partition,
        "PROFILE_IDS": ids,
        "COARSE_BOUND_PROJECTION": bounds,
        "STATUS": six["CURSOR_STATUS"],
    }


def frozen_authority() -> tuple[
    dict[str, int], dict[str, dict[str, object]], dict[str, object], dict[str, dict[str, object]]
]:
    commit_identity(BASE_HEAD, BASE_TREE)
    for stem, digest in SOURCE_PINS.items():
        blob(BASE_HEAD, f"src/lottolab/research/{stem}.py", digest)
    sealed = {
        name: decode(blob(BASE_HEAD, f"{DIRECTORY}/{name}", digest))
        for name, digest in RESULT_PINS.items()
    }
    six, t256, t248 = sealed[SIX], sealed[T256], sealed[T248]
    bounds = row_map([(p, integer(v)) for p, v in obj(six["RESOLVED_ROW_BOUNDS"]).items()])
    require(sha(projection(bounds)) == six["BOUNDS_SHA256_AFTER"], "six-row projection differs")
    for result in (t256, t248):
        require(sha(projection(bounds)) == result["BOUNDS_SHA256_BEFORE"], "baseline chain differs")
        update = obj(result["ROW_UPDATE"])
        p = string(update["PROFILE_ID"])
        require(p in bounds and bounds[p] == obj(update["BEFORE"])["bound"], "baseline row differs")
        bounds[p] = integer(obj(update["AFTER"])["bound"])
        require(sha(projection(bounds)) == result["BOUNDS_SHA256_AFTER"], "T248 projection differs")
    owners = {p: obj(v) for p, v in obj(t248["NEW_OWNER_ROWS"]).items()}
    require(set(owners) == set(TARGETS), "wrong T248 owner profiles")
    cursor = cursor_authority(six, sealed[COVERAGE])
    require(
        obj(obj(t248["PRESERVED_T256_STATUS"])["PRESERVED_SIX_ROW_STATUS"])["CURSOR"]
        == {k: cursor[k] for k in ("ID", "BOUND")},
        "inherited cursor differs",
    )
    require(
        family(bounds, cursor) == (FAMILY_BEFORE, sorted(TARGETS)), "previous tied owners differ"
    )
    return bounds, owners, cursor, sealed


def family(bounds: Mapping[str, int], cursor: Mapping[str, object]) -> tuple[int, list[str]]:
    terms = {**bounds, string(cursor["ID"]): integer(cursor["BOUND"])}
    require(len(terms) == len(bounds) + 1, "cursor collides with a resolved row")
    best = max(terms.values())
    return best, sorted(p for p, bound in terms.items() if bound == best)


def route_b(profile: str, cap: int, base: int) -> list[Term]:
    require(profile in TARGETS and type(cap) is int and 22 <= cap <= 265, "wrong profile/cap")
    require(type(base) is int and base == 112, "wrong inherited S4 base")
    d = tuple(map(int, profile))
    g = tuple(6 + v for v in d)
    w, c3 = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    require(len(d) == 20 and sum(d) == 66 and w == 829, "profile degree identity differs")
    amax = sum(v * (degree - 2) for v, degree in zip(d, g, strict=True)) // 3
    terms: list[Term] = []
    for t in range(22, cap + 1):
        excess = c3 - (max(g) - 2) * (w - 3 * t)
        k4 = max(0, (excess + 3) // 4)
        contained = min(k4, amax)
        s4 = max(base, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = 372_228_640 - 63_838_600 + s3 - (4 * s4) // 7
        rational = 372_228_640 - 63_838_600 + s3 - Fraction(4 * s4, 7)
        require(0 <= bound - rational < 1, "Route-B rational rounding differs")
        require(k4 == max(0, -((-excess) // 4)), "K4 ceiling differs")
        terms.append((t, bound, k4, contained, s4, s3))
    return terms


def certificates(
    a: Mapping[str, object], bc: Mapping[str, object], owners: Mapping[str, dict[str, object]]
) -> dict[str, dict[str, object]]:
    require(a["TARGET_PROFILE"] == TARGETS[0], "wrong-profile donor A")
    records = [obj(v) for v in items(bc["PROFILES"])]
    require(
        sorted(string(v["PROFILE_ID"]) for v in records) == sorted(TARGETS[1:]),
        "wrong-profile or duplicate BC donor",
    )
    normalized = {
        TARGETS[0]: {
            "CERTIFIED_T_CAP": a["CERTIFIED_T_CAP"],
            "NEW_BOUND": a["PROFILE_BOUND"],
            "THEOREM": a["THEOREM"],
            "ROUTE_B": a["ROUTE_B"],
            "UPDATE": a["ROW_UPDATE"],
        },
        **{
            string(v["PROFILE_ID"]): {
                **v,
                "UPDATE": obj(bc["ROW_UPDATES"])[string(v["PROFILE_ID"])],
            }
            for v in records
        },
    }
    for p, record in normalized.items():
        cap, bound = integer(record["CERTIFIED_T_CAP"]), integer(record["NEW_BOUND"])
        proof, route, update = obj(record["THEOREM"]), obj(record["ROUTE_B"]), obj(record["UPDATE"])
        require(
            proof["STATUS"] == "PROVEN"
            and proof["ATTAINMENT"] == "NOT_ASSERTED"
            and cap == CAPS[p]
            and bound == PACKET_BOUNDS[p],
            "certificate cap/status differs",
        )
        require(update["BEFORE"] == owners[p], "donor baseline owner row differs")
        new_row = obj(update["AFTER"])
        require(
            new_row["bound"] == bound
            and new_row["cap"] == cap
            and all(new_row[k] == owners[p][k] for k in ("s4_base", "realization")),
            "donor replacement metadata differs",
        )
        terms = route_b(p, cap, integer(owners[p]["s4_base"]))
        original = route_b(p, integer(owners[p]["cap"]), integer(owners[p]["s4_base"]))
        require(
            [list(t) for t in terms] == route["ALL_T_TERMS"]
            and len(terms) == route["TERM_COUNT"] == cap - 21
            and max(t[1] for t in terms) == bound
            and max(t[1] for t in original) == owners[p]["bound"]
            and terms == original[: len(terms)],
            "incomplete/wrong full Route-B envelope",
        )
    return normalized


def compose(
    bounds: Mapping[str, int],
    owners: Mapping[str, dict[str, object]],
    cursor: Mapping[str, object],
    updates: Mapping[str, dict[str, object]],
    expected_cursor: Mapping[str, object],
) -> tuple[dict[str, int], dict[str, dict[str, object]]]:
    require(render(cursor) == render(expected_cursor), "cursor-tamper rejected")
    require(set(updates) == set(TARGETS), "missing/wrong donor updates")
    row_map(list(bounds.items()))
    before_bytes = projection(bounds)
    after, owner_after = dict(bounds), dict(owners)
    for p in TARGETS:
        update = obj(updates[p]["UPDATE"])
        require(
            update["BEFORE"] == owners[p] and bounds[p] == owners[p]["bound"],
            "update baseline differs",
        )
        new = obj(update["AFTER"])
        require(
            new["bound"] == updates[p]["NEW_BOUND"]
            and new["cap"] == CAPS[p]
            and integer(new["bound"]) < bounds[p],
            "replacement does not match certified donor",
        )
        after[p], owner_after[p] = integer(new["bound"]), dict(new)
    require(
        sorted(p for p in bounds if after[p] != bounds[p]) == sorted(TARGETS),
        "exactly three bound rows must change",
    )
    other_before = {p: v for p, v in bounds.items() if p not in TARGETS}
    other_after = {p: v for p, v in after.items() if p not in TARGETS}
    require(
        len(other_after) == 4644 and projection(other_before) == projection(other_after),
        "other rows are not byte-identical in bound projection",
    )
    require(projection(bounds) == before_bytes, "input ledger mutated")
    return after, owner_after


def compute_result() -> dict[str, object]:
    bounds, owners, cursor, sealed = frozen_authority()
    a, aid = donor(A)
    bc, bcid = donor(BC)
    baseline_digest = sha(projection(bounds))
    require(
        a["BOUNDS_SHA256_BEFORE"] == bc["BOUNDS_SHA256_BEFORE"] == baseline_digest,
        "donor bound baseline differs",
    )
    updates = certificates(a, bc, owners)
    for result, profiles in ((a, TARGETS[:1]), (bc, TARGETS[1:])):
        single = {**bounds, **{p: integer(updates[p]["NEW_BOUND"]) for p in profiles}}
        require(
            sha(projection(single)) == result["BOUNDS_SHA256_AFTER"], "donor projection differs"
        )
    after, owner_after = compose(bounds, owners, cursor, updates, cursor)
    before, before_owners = family(bounds, cursor)
    best, next_owners = family(after, cursor)
    require(best < before, "family bound does not decrease")
    previous = [string(p) for p in items(sealed[T248]["CERTIFICATE_PROFILE_IDS"])]
    require(
        not set(previous).intersection(TARGETS) and all(bounds[p] == after[p] for p in previous),
        "prior certificate changed",
    )
    open_ids = sorted(p for p, bound in after.items() if bound > INCUMBENT)
    other_before = {p: v for p, v in bounds.items() if p not in TARGETS}
    other_after = {p: v for p, v in after.items() if p not in TARGETS}
    # Preserve the entire ancestor authority, including nested original caveats.
    inherited = {
        "SIX_ROW_AUTHORITY_VERBATIM": sealed[SIX],
        "T256_PRESERVED_STATUS_VERBATIM": sealed[T256]["PRESERVED_SIX_ROW_STATUS"],
        "T248_PRESERVED_STATUS_VERBATIM": sealed[T248]["PRESERVED_T256_STATUS"],
        "T248_PRIOR_ART_VERBATIM": sealed[T248]["PRIOR_ART"],
        "A_STATUS_VERBATIM": {
            k: a[k]
            for k in (
                "TASK_STATUS",
                "INHERITED_STATUS_PRESERVED_VERBATIM",
                "HISTORICAL_THEOREM_SOURCE",
                "LEDGER_REPLAY_VIEW",
            )
        },
        "BC_STATUS_VERBATIM": {
            k: bc[k]
            for k in (
                "TASK_STATUS",
                "PRESERVED_T248_STATUS",
                "HISTORICAL_SOURCE",
                "INHERITED_STATUS_SOURCE",
            )
        },
        "BASE_JUDGE_COMMIT_MESSAGE_VERBATIM": commit_identity(BASE_HEAD, BASE_TREE),
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "THREE_OWNER_AUTHORITY_PENDING_FRESH_JUDGE",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "DONOR_A": aid,
        "DONOR_BC": bcid,
        "SOURCE_RESULT_PINS": RESULT_PINS,
        "SOURCE_MODULE_PINS": SOURCE_PINS,
        "SOURCE_LEDGER_ROWS": len(bounds),
        "UPDATED_PROFILES": list(TARGETS),
        "ROW_UPDATES": {p: {"BEFORE": owners[p], "AFTER": owner_after[p]} for p in TARGETS},
        "ENVELOPES": {p: updates[p]["ROUTE_B"] for p in TARGETS},
        "ROWS_CHANGED": 3,
        "OTHER_ROWS_UNCHANGED": "PASS",
        "OTHER_4644_BOUNDS_SHA256_BEFORE": sha(projection(other_before)),
        "OTHER_4644_BOUNDS_SHA256_AFTER": sha(projection(other_after)),
        "BOUNDS_SHA256_BEFORE": baseline_digest,
        "BOUNDS_SHA256_AFTER": sha(projection(after)),
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "LEDGER_VIEW": "COMPLETE_BOUNDS_PROJECTION_PLUS_THREE_COMPLETE_OWNER_ROWS",
        "FULL_METADATA_DIGEST_AFTER": "NOT_CLAIMED_INHERITED_A_CAVEAT_PRESERVED",
        "CURSOR": cursor,
        "CURSOR_PRESERVED": "PASS",
        "CURSOR_AUTHORITY_SHA256_BEFORE": sha(render(cursor)),
        "CURSOR_AUTHORITY_SHA256_AFTER": sha(render(cursor)),
        "PRIOR_CERTIFICATE_IDS": previous,
        "CERTIFICATES_COMPOSED": len(previous) + len(TARGETS),
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": inherited,
        "CAVEAT_POLICY": "NOT_UPGRADED_OR_DISCARDED_PENDING_STATUSES_ARE_PRE_JUDGE_SNAPSHOTS",
        "FAMILY_BOUND_BEFORE": before,
        "FAMILY_OWNER_IDS_BEFORE": before_owners,
        "FAMILY_BOUND_AFTER": best,
        "EXACT_DELTA": before - best,
        "NEW_FAMILY_OWNER_IDS": next_owners,
        "INCUMBENT": INCUMBENT,
        "GAP_TO_INCUMBENT": best - INCUMBENT,
        "RESOLVED_ROWS_ABOVE_INCUMBENT": len(open_ids),
        "RESOLVED_OPEN_PROFILE_IDS": open_ids,
        "UNRESOLVED_OPEN_PROFILE_COUNT": cursor["PROFILE_COUNT"],
        "REMAINING_OPEN_PROFILE_COUNT": len(open_ids) + integer(cursor["PROFILE_COUNT"]),
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "CAP_PROOFS_REEXECUTED": 0,
        "SOLVER_CALLS": 0,
        "PORTFOLIO_SEARCH_STARTED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "SOURCE_MUTATED_OUTSIDE_TASK_WORKTREE": "NO",
        "RUN1_MUTATED": "NO",
        "SHARED_LEDGER_MUTATED": "NO",
        "REMOTE_WRITE": "NO",
    }


def main() -> None:
    raw = render(compute_result())
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == raw, "sealed result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(raw)
    print(json.dumps({"RESULT": str(RESULT_PATH), "SHA256": sha(raw)}))


if __name__ == "__main__":
    main()
