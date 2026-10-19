"""Compose the two accepted B649 donor envelopes on their pinned Base rows.

This adapter reuses the accepted A/B envelopes and the Base's existing family
aggregation contract. It does not rerun either donor proof or adopt S5.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

TASK_ID = "B649_ACCEPTED_AB_PAIR_COMPOSITION_R1"
ACCEPTANCE_TASK_ID = "B649_DONOR_PAIR_FOCUSED_ACCEPTANCE_R1"
ACCEPTANCE_SHA256 = "41161c94b0e39bc68600b151f721c0387c5159496497b2474c1bb108b595ea71"
IMPLEMENTATION_BASE_HEAD = "a895e02f0f3a71c29c33bee6612a73ff0bd9fac8"
IMPLEMENTATION_BASE_TREE = "790c6b05c652a4f0b4b1f0e9ad45b55831b385fb"
MATHEMATICAL_BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
MATHEMATICAL_BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-two-bonf5-owners-exact-composition-r1-result-"
    "42f6a5ea0e0a5c31bcd67c179ceb40d7599740daf511b57ab29e39bdd1bb4632.json"
)
BASE_RESULT_SHA256 = "42f6a5ea0e0a5c31bcd67c179ceb40d7599740daf511b57ab29e39bdd1bb4632"
RESULT_PATH = Path(
    "docs/research/matrix-native-results/b649-accepted-ab-pair-composition-r1-result.json"
)
TERM_COLUMNS = ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"]

DONOR_SPECS: dict[str, dict[str, Any]] = {
    "A": {
        "commit": "a7a7efb1280156ab3fbab97abac0a2e8cc3cd6ec",
        "tree": "fb49c11fcfadfa28618e4a043b240c31c36fc0e3",
        "profile": "66655555555511100000",
        "source_path": "src/lottolab/research/b649_min_s2_owner_a_exact_bound_r1.py",
        "source_sha256": "f8e3493fddaf150999db5259be055b84521612476f1edc39acc3351b870a08cd",
        "source_blob": "1aea323bf87c383e2804e422849633161d3204a6",
        "result_path": "docs/research/matrix-native-results/"
        "b649-min-s2-owner-a-exact-bound-r1-result.json",
        "result_sha256": "1e248e752622645685447e4b2c382f12aab36d5c25d1c42fb7771e16dceabab0",
        "result_blob": "46cec234dc35e9885567e87c092fb3072de34b5d",
        "envelope_key": "NEW_ROUTE_BOUND_TERMS",
        "current_bound": 313395344,
        "current_cap": 264,
        "cap": 249,
        "bound": 313260720,
        "term_count": 228,
        "argmax_t": [249],
        "envelope_sha256": "952452c6010670d62f762ffefe4715b9c688c031bd6f90df5877ce561ec04075",
        "accepted_terms_sha256": "71068f573f8834217784ded22d3b7a58e1960887a398e22aa1ba9a3b034ca095",
        "s4_floor": 112,
        "s5_used": False,
        "s5_artifact_value": "NOT_ADOPTED",
        "latest_lifecycle_acceptance": "A01-A16 ALL_PASS",
        "latest_judge_turn": "01a1330d-479f-7100-a27b-922bdb59fe1b",
        "original_report_sha256": (
            "62b7e6aef7d7b918b8c80cefdfdc48ec516e22f7e4628b14374abd2aa3422471"
        ),
        "committed_report_sha256": (
            "022fe99ad9d4f8b35c6a5cb8c98144b6445d3433ee546dbdf7bb72c650247480"
        ),
        "caveat": (
            "The original terminal report digest and actual committed-report digest differ. "
            "The accepted review attributes this to removal of 24 trailing spaces across "
            "12 lines; only the byte-verbatim preservation claim was invalidated."
        ),
    },
    "B": {
        "commit": "97dcfa9a2cfec1ef30097d808ecb6f87e9c6241f",
        "tree": "83fbdfece095ec5f88ac411a9d2db7a9aaf833f3",
        "profile": "66665555554431000000",
        "source_path": "src/lottolab/research/b649_min_s2_owner_b_exact_bound_r1.py",
        "source_sha256": "2a176205ceb6b96b929e459c44270d9e4f4fc04389d9507efe75806a5c885290",
        "source_blob": "47a49675d14acfc5c9dfafdaf6e03ed0e71453bf",
        "result_path": "docs/research/matrix-native-results/"
        "b649-min-s2-owner-b-exact-bound-r1-result-"
        "9e8bc62cf36eab69a6714237841316609907b9da5a8e7026ffb7955950902a0b.json",
        "result_sha256": "9e8bc62cf36eab69a6714237841316609907b9da5a8e7026ffb7955950902a0b",
        "result_blob": "d950e7a96edeed0f950b8d2f42c5773708d3763a",
        "envelope_key": "NEW_FULL_T_ENVELOPE",
        "current_bound": 313395344,
        "current_cap": 264,
        "cap": 243,
        "bound": 313206948,
        "term_count": 222,
        "argmax_t": [243],
        "envelope_sha256": "341b67bf7ddeccfb484ead6eeb63a5b6b2c0eabeaaa8a43839245b35cc213e1e",
        "accepted_terms_sha256": "bdc5df618644d3e85c3bc9c5752ace64108c6196b29be1a86c30769915dce560",
        "s4_floor": 112,
        "s5_used": False,
        "s5_artifact_value": None,
        "latest_lifecycle_acceptance": "B01-B16 ALL_PASS",
        "latest_judge_turn": "01a1330f-cb9a-7a63-be05-4451d775155d",
        "original_report_sha256": (
            "b24a70e0b1e569eb96524b79822833248fc4c13b940f15838dc4d8517b86f811"
        ),
        "lifecycle_addendum_sha256": (
            "3f375a24fcd1cebfb07099c0eb051d04e395ead36a8fe664276c3043a0212c05"
        ),
        "caveat": (
            "The inherited NB_CERTIFICATES[881] label is not a result pointer. The actual "
            "historical cap authority is R30 GROUP_ATTEMPTS[3414], recorded below."
        ),
    },
}

BASE_SOURCE_PINS: tuple[tuple[str, str], ...] = (
    (
        "src/lottolab/research/b649_k20_min_s2_current_cursor_class_owner_chase_r28.py",
        "72d7462a4cf32ed6932e81c6e62819e351e4b289246fd0644e5696b70b832fb0",
    ),
    (
        "src/lottolab/research/b649_k20_min_s2_current_cursor_dynamic_family_max_r30.py",
        "230cb455bb162f6c8ab428afbbc8e7d9cbc7ee3c88575ef247e8d57ae925acb5",
    ),
    (
        "src/lottolab/research/b649_k20_min_s2_realizable_core_class_bound_r4.py",
        "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec",
    ),
    (
        "src/lottolab/research/b649_k20_min_s2_resolved_above_cursor_owner_chase_r20.py",
        "b63081af598a6366ab9989f00f3e269052e8edbc41956a0771941dc03891b74e",
    ),
    (
        "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
        "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d",
    ),
    (
        "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py",
        "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784",
    ),
    (
        "src/lottolab/research/b649_min_s2_two_bonf5_owners_exact_composition_r1.py",
        "ee8ce0b641571e89b8e03f592f9b71009df6bdc92c5d451aa104036c1bb7d8f1",
    ),
)

AGGREGATION_SOURCE = "src/lottolab/research/b649_min_s2_t249_dual_profile_composition_r1.py"
AGGREGATION_SOURCE_SHA256 = "08dcc4b07e97710d7755e9cbdbbd452965c281300cc16e40535af89e5c9d4941"
RELATED_CONSUMER = "src/lottolab/research/b649_min_s2_two_bonf5_owners_exact_composition_r1.py"
RELATED_CONSUMER_SHA256 = "ee8ce0b641571e89b8e03f592f9b71009df6bdc92c5d451aa104036c1bb7d8f1"
RELATED_CONSUMER_PROFILES = ["66555555555441000000", "66555555555522000000"]
IMPLEMENTATION_BASE_CONSUMER = (
    "src/lottolab/research/b649_min_s2_two_certified_row_combined_authority_r1.py"
)
IMPLEMENTATION_BASE_CONSUMER_SHA256 = (
    "d4e66d1515d9d9c1d1206d7d5cee8769d9fb12bc2f39d11b471f5689ae2ffa5f"
)
IMPLEMENTATION_BASE_CONSUMER_PROFILES = [
    "66666555555311100000",
    "55555555555511111100",
]

R30_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
)
R30_RESULT_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
R30_ATTEMPT_INDEX = 3414
R30_PROOF_SHA256 = "eaca04bb815f5f59eab06d29a07140a1e9042fd21666fbda7a4064fa7cc02205"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return _sha256(raw)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON for {label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object for {label}")
    return cast(dict[str, Any], value)


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an exact integer")
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    typed_value = cast(dict[Any, Any], value)
    if not all(isinstance(key, str) for key in typed_value):
        raise ValueError(f"{label} keys must be strings")
    return cast(dict[str, Any], typed_value)


def _rows(value: Any, label: str) -> list[tuple[str, int]]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be pairs")
    result: list[tuple[str, int]] = []
    typed_rows = cast(Sequence[Any], value)
    for index, item in enumerate(typed_rows):
        if not isinstance(item, (list, tuple)):
            raise ValueError(f"{label}[{index}] must be an ID/bound pair")
        typed_item = cast(Sequence[Any], cast(Any, item))
        if len(typed_item) != 2:
            raise ValueError(f"{label}[{index}] must be an ID/bound pair")
        profile, bound = typed_item
        if (
            not isinstance(profile, str)
            or len(profile) != 20
            or not profile.isascii()
            or not profile.isdigit()
        ):
            raise ValueError(f"{label}[{index}] has an invalid profile ID")
        result.append((profile, _integer(bound, f"{label}[{index}] bound")))
    _require(len({profile for profile, _ in result}) == len(result), f"duplicate {label} profile")
    return result


def _aggregate(resolved: Mapping[str, int], cursor: Mapping[str, int]) -> tuple[int, list[str]]:
    terms = [*resolved.items(), *cursor.items()]
    _require(len({profile for profile, _ in terms}) == len(terms), "family cursor overlap")
    maximum = max(bound for _, bound in terms)
    return maximum, sorted(profile for profile, bound in terms if bound == maximum)


def compose(
    base: Mapping[str, Any],
    donors: Mapping[str, Mapping[str, Any]],
    acceptance: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    """Purely validate and compose supplied rows/envelopes; performs no I/O."""
    expected_acceptance = _mapping(expected["acceptance"], "expected acceptance")
    _require(
        acceptance.get("task_id") == expected_acceptance.get("task_id")
        and acceptance.get("sha256") == expected_acceptance.get("sha256"),
        "acceptance identity differs",
    )
    _require(set(donors) == {"A", "B"}, "exactly donors A and B are required")

    expected_base = _mapping(expected["base"], "expected Base")
    actual_base = _mapping(base.get("identity"), "Base identity")
    for key in ("commit", "tree", "result_sha256"):
        _require(actual_base.get(key) == expected_base.get(key), f"Base {key} pin differs")

    resolved_pairs = _rows(base.get("resolved_rows"), "resolved rows")
    cursor_pairs = _rows(base.get("cursor_rows"), "cursor rows")
    resolved = dict(resolved_pairs)
    cursor = dict(cursor_pairs)
    _require(
        len(resolved_pairs) == expected_base.get("resolved_count"), "resolved row count differs"
    )
    _require(len(cursor_pairs) == expected_base.get("cursor_count"), "cursor profile count differs")
    _require(not set(resolved).intersection(cursor), "resolved/cursor profiles overlap")

    incumbent = _integer(base.get("incumbent"), "incumbent")
    before_max, before_owners = _aggregate(resolved, cursor)
    if "recorded_family_bound" in base:
        _require(base["recorded_family_bound"] == before_max, "Base family maximum differs")
    if "recorded_family_owners" in base:
        _require(base["recorded_family_owners"] == before_owners, "Base family owners differ")

    expected_donors = _mapping(expected["donors"], "expected donors")
    after = dict(resolved)
    donor_rows: dict[str, dict[str, Any]] = {}
    for label in ("A", "B"):
        donor = _mapping(donors[label], f"donor {label}")
        pin = _mapping(expected_donors[label], f"expected donor {label}")
        identity = _mapping(donor.get("identity"), f"donor {label} identity")
        expected_identity = _mapping(pin.get("identity"), f"expected donor {label} identity pin")
        for key in ("commit", "tree", "source_sha256", "result_sha256"):
            _require(
                identity.get(key) == expected_identity.get(key), f"donor {label} {key} pin differs"
            )

        profile = donor.get("profile")
        if not isinstance(profile, str):
            raise ValueError(f"donor {label} profile must be a string")
        cap = _integer(donor.get("cap"), f"donor {label} cap")
        current_cap = _integer(donor.get("current_cap"), f"donor {label} current cap")
        bound = _integer(donor.get("bound"), f"donor {label} bound")
        term_count = _integer(donor.get("term_count"), f"donor {label} term count")
        pin_profile = pin.get("profile")
        if not isinstance(pin_profile, str):
            raise ValueError(f"expected donor {label} profile must be a string")
        pin_cap = _integer(pin.get("cap"), f"expected donor {label} cap")
        pin_current_cap = _integer(pin.get("current_cap"), f"expected donor {label} current cap")
        pin_bound = _integer(pin.get("bound"), f"expected donor {label} bound")
        pin_term_count = _integer(pin.get("term_count"), f"expected donor {label} term count")
        before_bound = _integer(pin.get("before_bound"), f"expected donor {label} old bound")
        s4_floor = _integer(pin.get("s4_floor"), f"expected donor {label} S4 floor")
        expected_status = pin.get("acceptance_status")
        _require(profile == pin_profile, f"donor {label} profile differs")
        _require(current_cap == pin_current_cap, f"donor {label} current cap differs")
        _require(cap == pin_cap, f"donor {label} cap differs")
        _require(term_count == pin_term_count, f"donor {label} term count differs")
        _require(donor.get("before_bound") == before_bound, f"donor {label} old bound differs")
        _require(donor.get("s4_floor") == s4_floor, f"donor {label} S4 floor differs")
        _require(
            donor.get("s5_used") is False and pin.get("s5_used") is False, f"donor {label} uses S5"
        )
        _require(
            donor.get("s5_artifact_value") == pin.get("s5_artifact_value"),
            f"donor {label} S5 artifact disposition differs",
        )
        _require(
            donor.get("acceptance_status") == expected_status == "VERIFIED_WITH_CAVEATS",
            f"donor {label} acceptance status differs",
        )
        _require(donor.get("term_columns") == TERM_COLUMNS, f"donor {label} term columns differ")

        terms = donor.get("terms")
        if not isinstance(terms, (list, tuple)):
            raise ValueError(f"donor {label} terms missing")
        typed_terms = cast(Sequence[Any], cast(Any, terms))
        _require(
            len(typed_terms) == term_count,
            f"donor {label} term count does not match its envelope",
        )
        term_rows: list[list[int]] = []
        for index, term in enumerate(typed_terms):
            if not isinstance(term, (list, tuple)):
                raise ValueError(f"donor {label} term {index} has the wrong shape")
            term_values = cast(Sequence[Any], cast(Any, term))
            if len(term_values) != 6:
                raise ValueError(f"donor {label} term {index} has the wrong shape")
            term_rows.append(
                [_integer(value, f"donor {label} term {index}") for value in term_values]
            )
        _require(
            [term[0] for term in term_rows] == list(range(22, cap + 1)),
            f"donor {label} T range differs",
        )
        envelope_sha256 = _json_digest(term_rows)
        _require(
            envelope_sha256 == pin.get("envelope_sha256"), f"donor {label} envelope digest differs"
        )
        maximum = max(term[1] for term in term_rows)
        argmax_t = sorted(term[0] for term in term_rows if term[1] == maximum)
        _require(bound == pin_bound == maximum, f"donor {label} bound differs from its envelope")
        _require(argmax_t == pin.get("argmax_t"), f"donor {label} argmax differs")
        _require(
            all(term[4] >= s4_floor for term in term_rows),
            f"donor {label} S4 term is below its floor",
        )
        _require(profile in resolved, f"donor {label} profile is not a resolved Base row")
        _require(resolved[profile] == before_bound, f"donor {label} Base row differs")
        _require(bound < resolved[profile], f"donor {label} update does not tighten")
        after[profile] = bound
        donor_rows[label] = {
            "PROFILE_ID": profile,
            "BEFORE_BOUND": resolved[profile],
            "AFTER_BOUND": bound,
            "T_CAP": cap,
            "T_RANGE": [22, cap],
            "TERM_COUNT": len(term_rows),
            "ALL_ARGMAX_T": argmax_t,
            "ENVELOPE_SHA256": envelope_sha256,
            "ACCEPTANCE_TERMS_SHA256": pin.get("envelope_sha256"),
            "NUMERIC_REPRODUCTION_TERMS_SHA256": pin.get("accepted_terms_sha256"),
            "TERM_COLUMNS": TERM_COLUMNS,
            "S4_FLOOR": pin.get("s4_floor"),
            "S5_USED": False,
            "ACCEPTANCE_STATUS": donor.get("acceptance_status"),
            "DONOR_COMMIT": identity.get("commit"),
            "DONOR_TREE": identity.get("tree"),
            "SOURCE_LOCATOR": f"{identity.get('commit')}:{pin.get('source_path')}",
            "RESULT_LOCATOR": f"{identity.get('commit')}:{pin.get('result_path')}",
            "SOURCE_SHA256": identity.get("source_sha256"),
            "RESULT_SHA256": identity.get("result_sha256"),
            "TERMS": term_rows,
            "CAVEAT": pin.get("caveat"),
        }

    changed = sorted(profile for profile in resolved if resolved[profile] != after[profile])
    target_profiles = sorted(str(expected_donors[label]["profile"]) for label in ("A", "B"))
    _require(changed == target_profiles, "composition changed rows outside A/B")
    unchanged_before = {p: resolved[p] for p in resolved if p not in target_profiles}
    unchanged_after = {p: after[p] for p in after if p not in target_profiles}
    _require(unchanged_before == unchanged_after, "an unowned resolved row changed")
    _require(len(unchanged_after) == len(resolved) - 2, "unchanged row count differs")

    after_max, owners = _aggregate(after, cursor)
    cursor_max = max(cursor.values())
    cursor_after = dict(cursor)
    _require(cursor_after == cursor, "cursor projection changed")

    base_identity = dict(actual_base)
    after_sorted = dict(sorted(after.items()))
    cursor_sorted = dict(sorted(cursor.items()))
    unchanged_sorted = dict(sorted(unchanged_after.items()))
    artifact_digests = _mapping(expected.get("bound_artifact_digests"), "bound artifact digests")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPOSED_BASE_SPECIFIC",
        "CERTIFICATE_SCOPE": "BASE_SPECIFIC",
        "CURRENT_GLOBAL_LATEST_AUTHORITY": "NOT_CLAIMED",
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "CANONICAL_SELECTOR_OR_LEDGER_CHANGED": "NO",
        "THREE_ROW_JOINT_CERTIFICATE_INCLUDED": "NO",
        "NEW_COVERAGE_CLAIM": "NO",
        "MATHEMATICAL_THEOREMS_REEXECUTED": 0,
        "ACCEPTANCE": {
            "TASK_ID": acceptance.get("task_id"),
            "JSON_SHA256": acceptance.get("sha256"),
            "DONOR_VERDICTS": expected_acceptance.get("donor_verdicts", {}),
            "LATEST_JUDGE_TURNS": expected_acceptance.get("latest_judge_turns", {}),
            "REPORT_EVIDENCE": expected_acceptance.get("report_evidence", {}),
        },
        "BASE": {
            **base_identity,
            "RESOLVED_ROW_COUNT": len(resolved),
            "CURSOR_PROFILE_COUNT": len(cursor),
            "INCUMBENT": incumbent,
        },
        "BOUND_ARTIFACT_DIGESTS": dict(artifact_digests),
        "RELATED_CONSUMER_CHECK": {
            "PATH": RELATED_CONSUMER,
            "SHA256": RELATED_CONSUMER_SHA256,
            "STATUS": "NOT_EQUIVALENT_TARGET_PROFILES_DIFFER",
            "EXISTING_PROFILES": RELATED_CONSUMER_PROFILES,
            "COMPOSED_PROFILES": target_profiles,
        },
        "IMPLEMENTATION_BASE_CONSUMER_CHECK": {
            "PATH": IMPLEMENTATION_BASE_CONSUMER,
            "SHA256": IMPLEMENTATION_BASE_CONSUMER_SHA256,
            "STATUS": "NOT_EQUIVALENT_TARGET_PROFILES_DIFFER",
            "EXISTING_PROFILES": IMPLEMENTATION_BASE_CONSUMER_PROFILES,
            "COMPOSED_PROFILES": target_profiles,
        },
        "AGGREGATION_CONTRACT": {
            "SOURCE": AGGREGATION_SOURCE,
            "SOURCE_SHA256": AGGREGATION_SOURCE_SHA256,
            "RULE": "max over resolved bounds and the Base cursor projection; sorted IDs own ties",
            "FORMULA_OR_ROUNDING_CHANGED": "NO",
        },
        "DONORS": donor_rows,
        "RESOLVED_ROW_COUNT": len(resolved),
        "UPDATED_ROW_COUNT": len(changed),
        "UNCHANGED_ROW_COUNT": len(unchanged_after),
        "TOTAL_DONOR_TERM_COUNT": sum(int(donor_rows[label]["TERM_COUNT"]) for label in ("A", "B")),
        "ROW_UPDATES": {
            label: {
                "PROFILE_ID": donor_rows[label]["PROFILE_ID"],
                "BEFORE_BOUND": donor_rows[label]["BEFORE_BOUND"],
                "AFTER_BOUND": donor_rows[label]["AFTER_BOUND"],
            }
            for label in ("A", "B")
        },
        "RESOLVED_ROW_BOUNDS_AFTER": after_sorted,
        "RESOLVED_ROW_BOUNDS_AFTER_SHA256": _json_digest(after_sorted),
        "UNCHANGED_RESOLVED_ROW_BOUNDS_SHA256": _json_digest(unchanged_sorted),
        "UNCHANGED_ROWS_PRESERVED": "PASS",
        "CURSOR_PROFILE_BOUNDS": cursor_sorted,
        "CURSOR_PROFILE_BOUNDS_SHA256": _json_digest(cursor_sorted),
        "CURSOR_PROFILE_COUNT": len(cursor),
        "CURSOR_MAXIMUM": cursor_max,
        "CURSOR_UNCHANGED": "PASS",
        "FAMILY_BOUND_BEFORE": before_max,
        "FAMILY_OWNER_IDS_BEFORE": before_owners,
        "FAMILY_MAXIMUM": after_max,
        "ALL_OWNERS": owners,
        "GAP_TO_INCUMBENT": after_max - incumbent,
        "GAP_ABOVE_CURSOR": after_max - cursor_max,
    }


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def _tree(root: Path, commit: str) -> str:
    return _git(root, "rev-parse", f"{commit}^{{tree}}").decode().strip()


def _committed_blob(root: Path, commit: str, path: str, expected: Mapping[str, Any]) -> bytes:
    entry = _git(root, "ls-tree", commit, "--", path).decode().strip()
    _require("\t" in entry, f"missing committed path: {path}")
    mode_type_blob, actual_path = entry.split("\t", 1)
    mode, kind, blob_id = mode_type_blob.split()
    _require(
        actual_path == path and mode == "100644" and kind == "blob",
        f"unsafe committed path: {path}",
    )
    if "blob" in expected:
        _require(blob_id == expected["blob"], f"Git blob pin differs: {path}")
    raw = _git(root, "show", f"{commit}:{path}")
    if "sha256" in expected:
        _require(_sha256(raw) == expected["sha256"], f"SHA256 pin differs: {path}")
    return raw


def load_pinned_inputs(
    root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Read immutable Base/donor Git blobs; never reads acceptance.json or temp paths."""
    repo = root or _root()
    _require(
        _tree(repo, IMPLEMENTATION_BASE_HEAD) == IMPLEMENTATION_BASE_TREE,
        "implementation base tree differs",
    )
    current_head = _git(repo, "rev-parse", "HEAD").decode().strip()
    if current_head != IMPLEMENTATION_BASE_HEAD:
        _require(
            _git(repo, "rev-parse", "HEAD^").decode().strip() == IMPLEMENTATION_BASE_HEAD,
            "worktree HEAD is not the authorized one-commit descendant",
        )
    _require(
        _tree(repo, MATHEMATICAL_BASE_HEAD) == MATHEMATICAL_BASE_TREE,
        "mathematical Base tree differs",
    )
    base_raw = _committed_blob(
        repo,
        MATHEMATICAL_BASE_HEAD,
        BASE_RESULT_PATH,
        {"sha256": BASE_RESULT_SHA256},
    )
    base_result = _decode_json(base_raw, "Base result")
    resolved_map = _mapping(base_result.get("RESOLVED_ROW_BOUNDS"), "Base resolved rows")
    cursor_object = _mapping(base_result.get("CURSOR"), "Base cursor")
    cursor_map = _mapping(cursor_object.get("COARSE_BOUND_PROJECTION"), "Base cursor projection")
    base = {
        "identity": {
            "commit": MATHEMATICAL_BASE_HEAD,
            "tree": MATHEMATICAL_BASE_TREE,
            "result_sha256": _sha256(base_raw),
        },
        "resolved_rows": list(resolved_map.items()),
        "cursor_rows": list(cursor_map.items()),
        "incumbent": base_result["INCUMBENT"],
        "recorded_family_bound": base_result["FAMILY_BOUND_AFTER"],
        "recorded_family_owners": base_result["FAMILY_OWNER_IDS"],
    }

    _require(len(cursor_map) == 197, "Base cursor projection does not contain 197 profiles")
    _require(
        cursor_object.get("PROFILE_COUNT") == len(cursor_map), "Base cursor profile count differs"
    )
    for path, digest in BASE_SOURCE_PINS:
        _committed_blob(repo, MATHEMATICAL_BASE_HEAD, path, {"sha256": digest})
    aggregation_source = _committed_blob(
        repo,
        MATHEMATICAL_BASE_HEAD,
        AGGREGATION_SOURCE,
        {"sha256": AGGREGATION_SOURCE_SHA256},
    )
    del aggregation_source
    _committed_blob(
        repo,
        MATHEMATICAL_BASE_HEAD,
        RELATED_CONSUMER,
        {"sha256": RELATED_CONSUMER_SHA256},
    )
    _committed_blob(
        repo,
        IMPLEMENTATION_BASE_HEAD,
        IMPLEMENTATION_BASE_CONSUMER,
        {"sha256": IMPLEMENTATION_BASE_CONSUMER_SHA256},
    )

    donor_inputs: dict[str, dict[str, Any]] = {}
    for label, spec in DONOR_SPECS.items():
        commit = str(spec["commit"])
        _require(_tree(repo, commit) == spec["tree"], f"donor {label} tree differs")
        _require(
            _git(repo, "rev-parse", f"{commit}^").decode().strip() == MATHEMATICAL_BASE_HEAD,
            f"donor {label} is not a direct child of the mathematical Base",
        )
        source_raw = _committed_blob(
            repo,
            commit,
            str(spec["source_path"]),
            {"blob": spec["source_blob"], "sha256": spec["source_sha256"]},
        )
        result_raw = _committed_blob(
            repo,
            commit,
            str(spec["result_path"]),
            {"blob": spec["result_blob"], "sha256": spec["result_sha256"]},
        )
        donor_result = _decode_json(result_raw, f"donor {label} result")
        terms = donor_result.get(str(spec["envelope_key"]))
        typed_terms = cast(list[Any], terms) if isinstance(terms, list) else []
        donor_inputs[label] = {
            "identity": {
                "commit": commit,
                "tree": spec["tree"],
                "source_sha256": _sha256(source_raw),
                "result_sha256": _sha256(result_raw),
            },
            "profile": donor_result.get("TARGET_PROFILE"),
            "before_bound": donor_result.get("CURRENT_PROFILE_BOUND"),
            "cap": donor_result.get("NEW_PROVEN_T_CAP"),
            "current_cap": donor_result.get("CURRENT_T_CAP"),
            "bound": donor_result.get("NEW_FULL_PROFILE_BOUND"),
            "term_count": len(typed_terms) if isinstance(terms, list) else None,
            "terms": typed_terms,
            "term_columns": list(TERM_COLUMNS),
            "terms_sha256": _json_digest(typed_terms),
            "s4_floor": donor_result.get("NEW_PROVEN_S4_FLOOR"),
            "s5_used": donor_result.get("S5_USED", False),
            "s5_artifact_value": donor_result.get("NEW_PROVEN_S5_CAP"),
            "acceptance_status": "VERIFIED_WITH_CAVEATS",
        }
        _require(
            donor_inputs[label]["current_cap"] == spec["current_cap"],
            f"donor {label} current cap differs",
        )
        _require(
            donor_inputs[label]["s5_artifact_value"] == spec["s5_artifact_value"],
            f"donor {label} S5 disposition differs",
        )

    r30_raw = _committed_blob(
        repo,
        MATHEMATICAL_BASE_HEAD,
        R30_RESULT_PATH,
        {"sha256": R30_RESULT_SHA256},
    )
    r30 = _decode_json(r30_raw, "R30 authority")
    attempts = r30.get("GROUP_ATTEMPTS")
    if not isinstance(attempts, list):
        raise ValueError("R30 attempt missing")
    typed_attempts = cast(list[Any], attempts)
    if len(typed_attempts) <= R30_ATTEMPT_INDEX:
        raise ValueError("R30 attempt missing")
    proof_row = typed_attempts[R30_ATTEMPT_INDEX]
    proof_row = _mapping(proof_row, "R30 B authority proof row")
    _require(
        _sha256(json.dumps(proof_row, sort_keys=True).encode()) == R30_PROOF_SHA256,
        "R30 proof digest differs",
    )
    _require(
        proof_row.get("ATTEMPT_INDEX") == R30_ATTEMPT_INDEX
        and proof_row.get("PROFILE_IDS") == [DONOR_SPECS["B"]["profile"]]
        and proof_row.get("STATUS") == "INFEASIBLE"
        and proof_row.get("TARGET_TRIANGLE_CAP") == 264,
        "R30 B authority identity differs",
    )

    acceptance = {"task_id": ACCEPTANCE_TASK_ID, "sha256": ACCEPTANCE_SHA256}
    expected = {
        "acceptance": {
            "task_id": ACCEPTANCE_TASK_ID,
            "sha256": ACCEPTANCE_SHA256,
            "donor_verdicts": {"A": "VERIFIED_WITH_CAVEATS", "B": "VERIFIED_WITH_CAVEATS"},
            "latest_judge_turns": {
                label: spec["latest_judge_turn"] for label, spec in DONOR_SPECS.items()
            },
            "report_evidence": {
                "A": {
                    "ORIGINAL_REPORT_SHA256": DONOR_SPECS["A"]["original_report_sha256"],
                    "COMMITTED_REPORT_SHA256": DONOR_SPECS["A"]["committed_report_sha256"],
                    "CAVEAT": DONOR_SPECS["A"]["caveat"],
                },
                "B": {
                    "ORIGINAL_REPORT_SHA256": DONOR_SPECS["B"]["original_report_sha256"],
                    "LIFECYCLE_ADDENDUM_SHA256": DONOR_SPECS["B"]["lifecycle_addendum_sha256"],
                    "CAVEAT": DONOR_SPECS["B"]["caveat"],
                },
            },
        },
        "base": {
            "commit": MATHEMATICAL_BASE_HEAD,
            "tree": MATHEMATICAL_BASE_TREE,
            "result_sha256": BASE_RESULT_SHA256,
            "result_path": BASE_RESULT_PATH,
            "resolved_count": 4647,
            "cursor_count": 197,
        },
        "donors": {
            label: {
                "identity": {
                    "commit": spec["commit"],
                    "tree": spec["tree"],
                    "source_sha256": spec["source_sha256"],
                    "result_sha256": spec["result_sha256"],
                },
                "profile": spec["profile"],
                "before_bound": spec["current_bound"],
                "current_cap": spec["current_cap"],
                "cap": spec["cap"],
                "bound": spec["bound"],
                "term_count": spec["term_count"],
                "argmax_t": spec["argmax_t"],
                "envelope_sha256": spec["envelope_sha256"],
                "accepted_terms_sha256": spec["accepted_terms_sha256"],
                "s4_floor": spec["s4_floor"],
                "s5_used": spec["s5_used"],
                "s5_artifact_value": spec["s5_artifact_value"],
                "acceptance_status": "VERIFIED_WITH_CAVEATS",
                "caveat": spec["caveat"],
                "source_path": spec["source_path"],
                "result_path": spec["result_path"],
            }
            for label, spec in DONOR_SPECS.items()
        },
        "bound_artifact_digests": {
            "ACCEPTANCE_JSON_SHA256": ACCEPTANCE_SHA256,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "DONOR_A_SOURCE_SHA256": DONOR_SPECS["A"]["source_sha256"],
            "DONOR_A_RESULT_SHA256": DONOR_SPECS["A"]["result_sha256"],
            "DONOR_B_SOURCE_SHA256": DONOR_SPECS["B"]["source_sha256"],
            "DONOR_B_RESULT_SHA256": DONOR_SPECS["B"]["result_sha256"],
            "BASE_SOURCE_PINS": [
                {"path": path, "sha256": digest} for path, digest in BASE_SOURCE_PINS
            ],
            "R30_RESULT_SHA256": R30_RESULT_SHA256,
            "R30_GROUP_ATTEMPT_3414_SHA256": R30_PROOF_SHA256,
            "AGGREGATION_SOURCE_SHA256": AGGREGATION_SOURCE_SHA256,
            "MATHEMATICAL_BASE_RELATED_CONSUMER_SHA256": RELATED_CONSUMER_SHA256,
            "IMPLEMENTATION_BASE_RELATED_CONSUMER_SHA256": IMPLEMENTATION_BASE_CONSUMER_SHA256,
        },
    }
    return base, donor_inputs, acceptance, expected


def build_result(root: Path | None = None) -> dict[str, Any]:
    base, donors, acceptance, expected = load_pinned_inputs(root)
    result = compose(base, donors, acceptance, expected)
    repo = root or _root()
    result["IMPLEMENTATION_BASE"] = {
        "HEAD": IMPLEMENTATION_BASE_HEAD,
        "TREE": IMPLEMENTATION_BASE_TREE,
    }
    result["IMPLEMENTATION_SOURCE_SHA256"] = _sha256(
        (repo / "src/lottolab/research/b649_accepted_ab_pair_composition_r1.py").read_bytes()
    )
    result["FOCUSED_TEST_SHA256"] = _sha256(
        (repo / "tests/unit/test_b649_accepted_ab_pair_composition_r1.py").read_bytes()
    )
    result["BOUND_ARTIFACT_DIGESTS"] = expected["bound_artifact_digests"]
    cursor_rows = _rows(base["cursor_rows"], "cursor rows")
    _require(
        _json_digest(dict(cursor_rows)) == result["CURSOR_PROFILE_BOUNDS_SHA256"],
        "cursor projection digest differs",
    )
    result["B_R30_AUTHORITY"] = {
        "RESULT_PATH": R30_RESULT_PATH,
        "RESULT_SHA256": R30_RESULT_SHA256,
        "GROUP_ATTEMPT_INDEX": R30_ATTEMPT_INDEX,
        "PROFILE_ID": DONOR_SPECS["B"]["profile"],
        "STATUS": "INFEASIBLE",
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 264,
        "PROOF_OBJECT_SHA256": R30_PROOF_SHA256,
    }
    result["PER_DONOR_ACCEPTED_CAPS"] = {
        label: {
            "CURRENT_T_CAP": spec["current_cap"],
            "ACCEPTED_T_CAP": spec["cap"],
            "BOUND": spec["bound"],
            "TERM_COUNT": spec["term_count"],
        }
        for label, spec in DONOR_SPECS.items()
    }
    return result


def render(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--build", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    root = _root()
    output = root / RESULT_PATH
    expected_raw = render(build_result(root))
    if args.build:
        _require(not output.exists(), "result already exists; refusing to overwrite")
        with output.open("xb") as stream:
            stream.write(expected_raw)
    else:
        _require(output.is_file(), "result is missing")
        _require(
            output.read_bytes() == expected_raw, "saved result differs from deterministic replay"
        )
    result = json.loads(expected_raw)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "RESOLVED_ROW_COUNT",
                    "UPDATED_ROW_COUNT",
                    "UNCHANGED_ROW_COUNT",
                    "CURSOR_PROFILE_COUNT",
                    "CURSOR_MAXIMUM",
                    "FAMILY_MAXIMUM",
                    "ALL_OWNERS",
                    "GAP_TO_INCUMBENT",
                    "GAP_ABOVE_CURSOR",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
