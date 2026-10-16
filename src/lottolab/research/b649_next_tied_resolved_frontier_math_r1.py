"""Two-profile analytic certificates; no ledger installation or family adoption.

The mathematical proof is in docs/research/B649_NEXT_TIED_RESOLVED_FRONTIER_MATH_R1.md.
This module audits its arithmetic, source identities and complete Route-B domains.
The established source replay is used only to recover the two target catalog rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
from collections import Counter
from fractions import Fraction
from math import comb
from pathlib import Path
from time import monotonic

TASK_ID = "B649_NEXT_TIED_RESOLVED_FRONTIER_MATH_R1"
ROOT = Path(__file__).resolve().parents[3]
BASE_HEAD = "ee4bb2f22ff101522e73952a3f11c66c55d95098"
BASE_TREE = "876d80cb5fb524af925bd35e0d6042093248710e"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
LEDGER_PATH = (
    "docs/research/matrix-native-results/b649-t261-24-event-local-family-integration-r1-result.json"
)
LEDGER_SHA = "a1a40b170ff8e0eb7b9fcf10d33ecf56b1ceaa0a92652facea2f3e8bcfcbca7e"
RESULT_PATH = (
    ROOT
    / "docs/research/matrix-native-results/b649-next-tied-resolved-frontier-math-r1-result.json"
)
PROOF_PATH = ROOT / "docs/research/B649_NEXT_TIED_RESOLVED_FRONTIER_MATH_R1.md"
PROFILE_A = "65555555555442000000"
PROFILE_B = "66555555554433000000"
TARGETS = (PROFILE_A, PROFILE_B)
OLD_BOUND = 313_392_232
HISTOGRAMS = {
    PROFILE_A: {6: 1, 5: 10, 4: 2, 2: 1, 0: 6},
    PROFILE_B: {6: 2, 5: 8, 4: 2, 3: 2, 0: 6},
}
SOURCE_INDICES = {PROFILE_A: 1620, PROFILE_B: 1467}
SUPPORT_MODEL = {
    "TICKETS": 20,
    "TICKET_CAPACITY": 6,
    "TRIPLE_SUPPORTS": 22,
    "PAIR_SUPPORTS": 27,
    "LABELS": 49,
    "PAIR_LINEARITY": True,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def pinned(head: str, path: str, expected_sha: str | None = None) -> bytes:
    raw = git("show", f"{head}:{path}")
    if expected_sha is not None:
        require(sha(raw) == expected_sha, f"source SHA mismatch: {path}")
    require((ROOT / path).read_bytes() == raw, f"working source differs: {path}")
    return raw


def profile_premises(pid: str, degrees: tuple[int, ...], model: dict) -> dict:
    require(pid in TARGETS, "wrong profile")
    require(model == SUPPORT_MODEL, "missing or incorrect support/capacity premise")
    require(all(type(d) is int for d in degrees), "noninteger degrees")
    require(dict(Counter(degrees)) == HISTOGRAMS[pid], "wrong degree histogram")
    require(len(degrees) == 20 and sum(degrees) == 66, "degree count or sum")
    require(tuple(sorted(degrees, reverse=True)) == degrees, "degree order")
    # Profile identity is checked against the actual replayed catalog degrees.
    require("".join(map(str, degrees)) == pid, "profile/catalog mismatch")
    g = [6 + d for d in degrees]
    h = [13 - d for d in degrees]
    core = tuple(d for d in degrees if d)
    phi = comb(20, 3) - 18 * 97 + sum(comb(v, 2) for v in h)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(x * y for x, y in zip(g, h, strict=True)), 2)
    constant = phi - 3 * sum(7 - d for d in core) + 42
    require(
        (len(core), degrees.count(0), sum(g), sum(h), phi, constant) == (14, 6, 186, 194, 290, 236),
        "split constants",
    )
    require(goodman == phi, "independent Goodman recount")
    coordinate_values = {
        str(d): [s * (s + 3 - d) for s in range(7 - d)] for d in sorted(set(core), reverse=True)
    }
    cap = 200 + sum(max(coordinate_values[str(d)]) for d in core)
    return {
        "PROFILE_ID": pid,
        "DEGREES": list(degrees),
        "DEGREE_HISTOGRAM": {str(k): v for k, v in sorted(Counter(degrees).items(), reverse=True)},
        "CORE": 14,
        "ZERO": 6,
        "G_EDGES": 93,
        "H_EDGES": 97,
        "PHI": phi,
        "F_CONSTANT": constant,
        "FINAL_CONSTANT": 200,
        "CORE_COORDINATE_VALUES": coordinate_values,
        "PROVED_T_CAP": cap,
    }


def split_values(
    degrees: tuple[int, ...], sigma: tuple[int, ...], zeta: tuple[int, ...], remainder: int
) -> tuple[Fraction, int]:
    """Evaluate the exact split identity on the whole necessary degree superset.

    No graphicality/realizability assumption is made about supplied vectors.
    """
    core = tuple(d for d in degrees if d)
    require(len(core) == 14 and degrees.count(0) == 6, "split part sizes")
    require(len(sigma) == 14 and len(zeta) == 6, "cross vector lengths")
    require(
        all(type(s) is int and 0 <= s <= 6 - d for s, d in zip(sigma, core, strict=True)),
        "missing capacity constraint",
    )
    require(all(type(q) is int and 1 <= q <= 6 for q in zeta), "zero capacity")
    require(sum(sigma) == sum(zeta), "invalid cross-edge balance")
    require(type(remainder) is int and remainder >= 0, "negative remainder")
    h = [7 - d + s for d, s in zip(core, sigma, strict=True)]
    a = [q - 1 for q in zeta]
    direct = (
        Fraction(290)
        - 3 * sum(h)
        - 7 * sum(a)
        + sum(s * v for s, v in zip(sigma, h, strict=True))
        + sum(q * v for q, v in zip(zeta, a, strict=True))
        - remainder
    )
    balanced = (
        236
        + sum(s * (s + 2 - d) for s, d in zip(sigma, core, strict=True))
        + sum(q * (q - 6) for q in zeta)
        - remainder
    )
    require(direct == balanced, "split algebra mismatch")
    majorant = 200 + sum(s * (s + 3 - d) for s, d in zip(sigma, core, strict=True)) - remainder
    require(balanced <= majorant, "zero-coordinate inequality")
    return direct, majorant


def route_terms(degrees: tuple[int, ...], cap: int, s4_base: int = 112) -> list[list[int]]:
    require(22 <= cap <= 266, "unsupported Route-B domain")
    g = [6 + d for d in degrees]
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    b = sum(d * (v - 2) for d, v in zip(degrees, g, strict=True))
    amax = b // 3
    terms = []
    for t in range(22, cap + 1):
        numerator = j - (max(g) - 2) * (w - 3 * t)
        k4 = max(0, -((-numerator) // 4))
        contained = min(k4, amax)
        s4 = max(s4_base, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = 308390040 + s3 - (4 * s4) // 7
        terms.append([t, bound, k4, contained, s4, s3])
    return terms


def verify_route(degrees: tuple[int, ...], cap: int, terms: list[list[int]]) -> None:
    """Independent exact-Fraction recount; no float conversion or endpoint shortcut."""
    require([r[0] for r in terms] == list(range(22, cap + 1)), "missing Route-B term")
    g = [6 + d for d in degrees]
    w = sum(v * (v - 1) // 2 for v in g)
    j = sum(v * (v - 1) * (v - 2) // 6 for v in g)
    b = sum(d * (v - 2) for d, v in zip(degrees, g, strict=True))

    def ceil(x: Fraction) -> int:
        return -((-x.numerator) // x.denominator)

    for t, u, k, a, s4, s3 in terms:
        exact_k = max(0, ceil(Fraction(j - (max(g) - 2) * (w - 3 * t), 4)))
        exact_a = min(exact_k, b // 3)
        exact_s4 = max(112, 679 * exact_k - 231 * exact_a)
        exact_s3 = 2800 * w + 11872 * (t - 22) - 30800
        exact_u = ceil(Fraction(308390040 + exact_s3) - Fraction(4 * exact_s4, 7))
        require(
            [u, k, a, s4, s3] == [exact_u, exact_k, exact_a, exact_s4, exact_s3],
            f"incorrect ceiling/rounding at T={t}",
        )


def verify_coordinate_coverage(premises: dict) -> None:
    core = [d for d in premises["DEGREES"] if d]
    expected = {str(d): [s * (s + 3 - d) for s in range(7 - d)] for d in set(core)}
    require(premises["CORE_COORDINATE_VALUES"] == expected, "incomplete coordinate coverage")


def certify(snapshot: dict, claimed_cap: int | None = None) -> dict:
    degrees = tuple(snapshot["DEGREES"])
    p = profile_premises(snapshot["PROFILE_ID"], degrees, snapshot["SUPPORT_MODEL"])
    verify_coordinate_coverage(p)
    cap = p["PROVED_T_CAP"]
    require(claimed_cap is None or claimed_cap == cap, "unsupported T cap")
    old = route_terms(degrees, snapshot["ORIGINAL_CAP"], snapshot["S4_BASE"])
    new = route_terms(degrees, cap, snapshot["S4_BASE"])
    verify_route(degrees, 266, old)
    verify_route(degrees, cap, new)
    require(snapshot["ORIGINAL_CAP"] == 266 and snapshot["S4_BASE"] == 112, "wrong source cap/S4")
    require(max(r[1] for r in old) == snapshot["OLD_BOUND"] == OLD_BOUND, "old envelope mismatch")
    require(new == old[: cap - 21], "new envelope is not the complete old prefix")
    peak = max(new, key=lambda r: r[1])
    require(peak[1] < OLD_BOUND, "strict improvement missing")
    return {
        "SOURCE_IDENTITY": snapshot,
        "PREMISES": p,
        "PROOF_SCOPE": "FULL_PROFILE",
        "MATHEMATICAL_THEOREM": "T <= 200 + sum_core max_{0<=s<=6-d} s*(s+3-d)",
        "EXACT_INEQUALITY": "T <= 200 + sum_core sigma*(sigma+3-d) - P",
        "RELAXATION_COMPLETENESS": "ANALYTIC_ALL_REALIZATIONS_NO_FINITE_SEARCH",
        "LOAD_BEARING_PREMISES": SUPPORT_MODEL,
        "PROVED_T_CAP": cap,
        "OLD_BOUND": OLD_BOUND,
        "NEW_BOUND": peak[1],
        "OWNER_DELTA": OLD_BOUND - peak[1],
        "ARGMAX_TERM": peak,
        "OLD_ARGMAX_TERM": max(old, key=lambda r: r[1]),
        "ROUTE_B_TERMS": new,
        "ROUTE_B_TERM_COUNT": len(new),
        "OLD_ROUTE_B_TERMS": old,
        "ROUNDING_CHECK": "INTEGER_AND_FRACTION_MATCH",
        "INDEPENDENT_ARITHMETIC_RECOUNT": "EXACT_FRACTION_ALL_TERMS",
        "CAP_ATTAINMENT": "NOT_CLAIMED",
    }


def load_sources() -> tuple[list[dict], dict]:
    for head, tree in [(BASE_HEAD, BASE_TREE), (FROZEN_HEAD, FROZEN_TREE)]:
        require(
            git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree,
            "fixed head/tree mismatch",
        )
    raw = pinned(BASE_HEAD, LEDGER_PATH, LEDGER_SHA)
    ledger = json.loads(raw)
    require(
        (ledger["ROWS_AFTER"], ledger["TOTAL_EVENTS"], len(ledger["EVENT_HISTORY"]))
        == (4647, 24, 24),
        "fixed ledger count",
    )
    require(
        ledger["NEXT_DISTINCT_RESOLVED_OWNERS"] == list(TARGETS)
        and ledger["NEXT_DISTINCT_RESOLVED_BOUND"] == OLD_BOUND,
        "wrong fixed owners",
    )
    require(
        not set(TARGETS).intersection(ledger["CHANGED_PROFILE_IDS_FROM_FROZEN"]),
        "target was changed after Frozen",
    )
    require(
        not any(e["PROFILE_ID"] in TARGETS for e in ledger["EVENT_HISTORY"]),
        "target has a post-Frozen event",
    )

    # Established, digest-checked ZERO-SOLVE source replay. This replays historical
    # certificates without a new owner chase, solver or refinement search.
    # The catalog supplies actual profile tuples and caps.
    from . import b649_existing_four_owner_local_authority_r1 as f

    support = f.seven.three.r5
    observed = {
        "TICKETS": support.K20_TICKET_COUNT,
        "TICKET_CAPACITY": support.K20_TICKET_CAPACITY,
        "TRIPLE_SUPPORTS": support.K20_TRIPLE_SUPPORT_COUNT,
        "PAIR_SUPPORTS": support.K20_DOUBLE_SUPPORT_COUNT,
        "LABELS": support.K20_LABEL_COUNT,
        "PAIR_LINEARITY": True,
    }
    require(observed == SUPPORT_MODEL, "pinned support model constants differ")
    chase, _authorities, _sealed = f.seven.two.chase.prior.start_chase(monotonic() + 115)
    selected = {
        f.seven.two.chase.profile_id(c.profile): c
        for c in chase.catalog.values()
        if f.seven.two.chase.profile_id(c.profile) in TARGETS
    }
    require(set(selected) == set(TARGETS), "target source catalog rows missing")
    six_path = (
        f.seven.SIX_RESULT_PATH
        if hasattr(f.seven, "SIX_RESULT_PATH")
        else (
            "docs/research/matrix-native-results/b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
        )
    )
    six = json.loads(pinned(FROZEN_HEAD, six_path))
    snapshots = []
    for pid in TARGETS:
        c = selected[pid]
        source_row = f"NB_CERTIFICATES[{SOURCE_INDICES[pid]}]"
        require(
            (c.bound, c.triangle_cap, c.s4, c.source_result, c.source_row)
            == (
                OLD_BOUND,
                266,
                112,
                "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json",
                source_row,
            ),
            "source row identity mismatch",
        )
        require(six["RESOLVED_ROW_BOUNDS"][pid] == c.bound, "Frozen target bound mismatch")
        snapshots.append(
            {
                "PROFILE_ID": pid,
                "DEGREES": list(c.profile),
                "DEGREE_ORIGIN": (
                    "digest-checked existing replay: chase.catalog Certificate.profile"
                ),
                "SUPPORT_MODEL": dict(SUPPORT_MODEL),
                "ORIGINAL_CAP": c.triangle_cap,
                "S4_BASE": c.s4,
                "OLD_BOUND": c.bound,
                "ROW_SOURCE": f"{c.source_result}:{c.source_row}",
                "ROW_SOURCE_KIND": "VIRTUAL_REPLAY_CATALOG_ROW_NOT_JSON_MEMBER",
                "SOURCE_PROOF_LOCATOR": (
                    "src/lottolab/research/"
                    "b649_k20_min_s2_nb_degree_cap_frontier_r1.py"
                    "#module-docstring,refine_resolved"
                ),
                "SOURCE_CAP_PROOF": (
                    "NB neighbourhood-capacity inequality; cap reproduced by existing replay"
                ),
            }
        )
    paths = [
        "src/lottolab/research/b649_k20_min_s2_nb_degree_cap_frontier_r1.py",
        "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py",
        "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
        "src/lottolab/research/b649_k20_min_s2_dangerous_core_realizability_r5.py",
    ]
    hashes = {p: sha(pinned(BASE_HEAD, p)) for p in paths}
    return snapshots, {
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "LEDGER_RESULT_SHA256": sha(raw),
        "ROWS": 4647,
        "EVENTS": 24,
        "SOURCE_FILE_SHA256": hashes,
        "PROFILE_ROWS": "RESOLVED",
        "SOURCE_LOCATOR_CAVEAT": (
            "NB_CERTIFICATES indices name replay-generated catalog rows; "
            "the summary JSON contains no NB_CERTIFICATES array."
        ),
    }


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    snapshots, authority = load_sources()
    certificates = [certify(s) for s in snapshots]
    # Existing Route-B implementation is a third check, only for these profiles.
    from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32

    for cert, snapshot in zip(certificates, snapshots, strict=True):
        d = tuple(snapshot["DEGREES"])
        require(
            [list(t) for t in r32.route_b_envelope(d, cert["PROVED_T_CAP"], 112)]
            == cert["ROUTE_B_TERMS"],
            "R32 helper mismatch",
        )
        require(
            [list(t) for t in r32.route_b_envelope(d, 266, 112)] == cert["OLD_ROUTE_B_TERMS"],
            "R32 old helper mismatch",
        )
        cert["R32_RECOUNT"] = "ALL_OLD_AND_NEW_TERMS_MATCH"
    result = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "BOTH_FULL_PROFILE_BOUNDS_PROVED_SELF_CHECK_ONLY",
        "AUTHORITY": authority,
        "CERTIFICATES": certificates,
        "PROOF_SHA256": sha(PROOF_PATH.read_bytes()),
        "SCIENTIFIC_JUDGE": "SELF_CHECK_ONLY",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "FAMILY_ADOPTION": "NOT_PERFORMED",
        "NEW_WINNING_OUTCOMES": 0,
        "FRONTIER_AFTER_BOTH_UPDATES": "NOT_PROVED_EXACT_NUMERIC_VALUE",
        "HYPOTHETICAL_RESOLVED_FRONTIER_STRICT_DECREASE": "PROVED_FROM_SOLE_TIED_OWNERS",
        "SINGLE_OWNER_UPDATE_FRONTIER": OLD_BOUND,
        "FAMILY_WITH_OLD_CURSOR": 313394584,
        "FAMILY_GAIN_WITH_OLD_CURSOR": 0,
        "UNRESOLVED_CLASS_COUNT": 197,
        "COUNTEREXAMPLE_STATUS": "NONE_KNOWN; ATTAINMENT_NOT_CLAIMED",
        "UNPROVED_ASSUMPTIONS": [],
        "MISSING_EVIDENCE": [
            "fresh-context independent science Judge",
            "exact next resolved frontier aggregate",
        ],
        "FINITE_RELAXATION_SEARCH": "NOT_USED",
        "HEAVY_SOLVER": "NOT_RUN",
        "FULL_SUITE": "NOT_RUN",
    }
    result["RESULT_SHA256"] = sha(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    )
    encoded = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        require(not RESULT_PATH.exists(), "result already exists")
        with RESULT_PATH.open("xb") as out:
            out.write(encoded)
        require(RESULT_PATH.read_bytes() == encoded, "result read-after-write mismatch")
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "RESULT_SHA256": result["RESULT_SHA256"],
                "RESULT_FILE_SHA256": sha(encoded),
                "BOUNDS": {
                    c["SOURCE_IDENTITY"]["PROFILE_ID"]: c["NEW_BOUND"] for c in certificates
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
