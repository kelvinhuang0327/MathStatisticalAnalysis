"""Exact composition and fail-closed tests against genuine committed donor bytes."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from typing import cast

import pytest

from lottolab.research import b649_min_s2_three_tied_owner_combined_authority_r1 as c

type Authority = tuple[
    dict[str, int], dict[str, dict[str, object]], dict[str, object], dict[str, dict[str, object]]
]
type Donors = tuple[dict[str, object], dict[str, object]]


@pytest.fixture(scope="module")
def authority() -> Authority:
    return c.frozen_authority()


@pytest.fixture(scope="module")
def donors() -> Donors:
    return c.donor(c.A)[0], c.donor(c.BC)[0]


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


def test_result_bytes_reproduced(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.render(result)


def test_all_three_git_identities() -> None:
    for head, tree in ((c.BASE_HEAD, c.BASE_TREE), (c.A.head, c.A.tree), (c.BC.head, c.BC.tree)):
        assert tree in c.commit_identity(head, tree)


def test_wrong_commit_tree_rejected() -> None:
    with pytest.raises(AssertionError, match="commit tree mismatch"):
        c.donor(replace(c.BC, tree="0" * 40))


def test_source_hash_mismatch_rejected() -> None:
    with pytest.raises(AssertionError, match="source-hash mismatch"):
        c.blob(c.A.head, f"src/lottolab/research/{c.A.module}.py", "0" * 64)


def test_missing_donor_rejected() -> None:
    with pytest.raises(AssertionError, match="missing/unsafe donor blob"):
        c.donor(replace(c.BC, filename="missing-donor-result.json"))


def test_target_profiles_occur_once(authority: Authority) -> None:
    bounds, owners, cursor, _ = authority
    assert len(bounds) == 4647
    assert set(owners) == set(c.TARGETS)
    assert c.family(bounds, cursor) == (c.FAMILY_BEFORE, sorted(c.TARGETS))
    assert all(sum(p == target for p in bounds) == 1 for target in c.TARGETS)


def test_duplicate_row_rejected(authority: Authority) -> None:
    original = list(authority[0].items())
    duplicate = [*original[:-1], original[0]]
    with pytest.raises(AssertionError, match="duplicate ledger row"):
        c.row_map(duplicate)


def test_missing_target_rejected(authority: Authority) -> None:
    rows = [(p if p != c.TARGETS[0] else "0" * 20, v) for p, v in authority[0].items()]
    with pytest.raises(AssertionError, match="missing target row"):
        c.row_map(rows)


def test_duplicate_json_key_rejected() -> None:
    with pytest.raises(AssertionError, match="duplicate JSON key/row"):
        c.decode(b'{"RESOLVED_ROW_BOUNDS":{"profile":1,"profile":2}}')


@pytest.mark.parametrize("which", [0, 1])
def test_wrong_profile_rejected(authority: Authority, donors: Donors, which: int) -> None:
    a, bc = copy.deepcopy(donors)
    if which == 0:
        a["TARGET_PROFILE"] = c.TARGETS[1]
    else:
        c.obj(c.items(bc["PROFILES"])[0])["PROFILE_ID"] = c.TARGETS[0]
    with pytest.raises(AssertionError, match="wrong-profile"):
        c.certificates(a, bc, authority[1])


def test_duplicate_donor_profile_rejected(authority: Authority, donors: Donors) -> None:
    a, bc = copy.deepcopy(donors)
    records = c.items(bc["PROFILES"])
    records[1] = copy.deepcopy(records[0])
    with pytest.raises(AssertionError, match="duplicate BC donor"):
        c.certificates(a, bc, authority[1])


def test_missing_update_rejected(authority: Authority, donors: Donors) -> None:
    bounds, owners, cursor, _ = authority
    updates = c.certificates(*donors, owners)
    del updates[c.TARGETS[2]]
    with pytest.raises(AssertionError, match="missing/wrong donor"):
        c.compose(bounds, owners, cursor, updates, cursor)


@pytest.mark.parametrize(
    "field,value", [("BOUND", 313394583), ("ID", c.TARGETS[0]), ("PROFILE_COUNT", 196)]
)
def test_cursor_tamper_rejected(
    authority: Authority, donors: Donors, field: str, value: object
) -> None:
    bounds, owners, cursor, _ = authority
    tampered = {**cursor, field: value}
    with pytest.raises(AssertionError, match="cursor-tamper"):
        c.compose(bounds, owners, tampered, c.certificates(*donors, owners), cursor)


def test_sealed_cursor_digest_tamper_rejected(authority: Authority) -> None:
    sealed = copy.deepcopy(authority[3])
    partition = c.obj(sealed[c.SIX]["CURSOR_PARTITION_AUTHORITY"])
    c.obj(partition["UNRESOLVED_FRONTIER_UNDER_W785_CURSOR"])["IDS_SHA256"] = "0" * 64
    with pytest.raises(AssertionError, match="cursor partition tamper"):
        c.cursor_authority(sealed[c.SIX], sealed[c.COVERAGE])


@pytest.mark.parametrize("target", c.TARGETS)
def test_exact_full_envelope(authority: Authority, donors: Donors, target: str) -> None:
    updates = c.certificates(*donors, authority[1])
    route = c.obj(updates[target]["ROUTE_B"])
    terms = c.route_b(target, c.CAPS[target], 112)
    assert [t[0] for t in terms] == list(range(22, c.CAPS[target] + 1))
    assert [list(t) for t in terms] == route["ALL_T_TERMS"]
    assert max(t[1] for t in terms) == c.PACKET_BOUNDS[target] < c.INCUMBENT


def test_truncated_envelope_rejected(authority: Authority, donors: Donors) -> None:
    a, bc = copy.deepcopy(donors)
    c.items(c.obj(a["ROUTE_B"])["ALL_T_TERMS"]).pop(0)
    with pytest.raises(AssertionError, match="full Route-B envelope"):
        c.certificates(a, bc, authority[1])


def test_wrong_cap_rejected(authority: Authority, donors: Donors) -> None:
    a, bc = copy.deepcopy(donors)
    a["CERTIFIED_T_CAP"] = 242
    with pytest.raises(AssertionError, match="certificate cap/status"):
        c.certificates(a, bc, authority[1])


def test_three_replacements_and_other_projection_independent(
    authority: Authority, result: dict[str, object]
) -> None:
    before = authority[0]
    after = {p: c.integer(v) for p, v in c.obj(result["RESOLVED_ROW_BOUNDS"]).items()}
    assert len(after) == 4647 and set(after) == set(before)
    assert sorted(p for p in before if before[p] != after[p]) == sorted(c.TARGETS)
    # Independent canonical serializer, separate from the verifier's projection function.
    unchanged = sorted(set(before) - set(c.TARGETS))
    raw_before = json.dumps([[p, before[p]] for p in unchanged]).encode()
    raw_after = json.dumps([[p, after[p]] for p in unchanged]).encode()
    assert len(unchanged) == 4644 and raw_before == raw_after
    for p in c.items(result["PRIOR_CERTIFICATE_IDS"]):
        pid = c.string(p)
        assert before[pid] == after[pid]


def test_family_recomputed_independently(authority: Authority, result: dict[str, object]) -> None:
    terms = [(c.integer(v), p) for p, v in c.obj(result["RESOLVED_ROW_BOUNDS"]).items()]
    terms.append((c.integer(authority[2]["BOUND"]), c.string(authority[2]["ID"])))
    actual = sorted(terms, reverse=True)[0][0]
    assert actual == result["FAMILY_BOUND_AFTER"]
    assert actual < c.FAMILY_BEFORE
    assert sorted(p for bound, p in terms if bound == actual) == result["NEW_FAMILY_OWNER_IDS"]
    assert c.FAMILY_BEFORE - actual == result["EXACT_DELTA"]
    assert actual - c.INCUMBENT == result["GAP_TO_INCUMBENT"]
    resolved = sum(bound > c.INCUMBENT for bound, _ in terms[:-1])
    assert resolved == result["RESOLVED_ROWS_ABOVE_INCUMBENT"]
    assert (
        resolved + c.integer(authority[2]["PROFILE_COUNT"])
        == result["REMAINING_OPEN_PROFILE_COUNT"]
    )


def test_cursor_identities_and_bounds_preserved(
    authority: Authority, result: dict[str, object]
) -> None:
    cursor = c.obj(result["CURSOR"])
    assert cursor == authority[2]
    ids = cast(list[str], cursor["PROFILE_IDS"])
    assert len(ids) == len(set(ids)) == cursor["PROFILE_COUNT"]
    band = c.obj(c.obj(cursor["PARTITION"])["UNRESOLVED_FRONTIER_UNDER_W785_CURSOR"])
    assert hashlib.sha256(json.dumps(ids).encode()).hexdigest() == band["IDS_SHA256"]
    assert result["CURSOR_AUTHORITY_SHA256_BEFORE"] == result["CURSOR_AUTHORITY_SHA256_AFTER"]


def test_inherited_caveats_verbatim(
    authority: Authority, donors: Donors, result: dict[str, object]
) -> None:
    caveats = c.obj(result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])
    assert caveats["SIX_ROW_AUTHORITY_VERBATIM"] == authority[3][c.SIX]
    assert (
        caveats["T248_PRESERVED_STATUS_VERBATIM"] == authority[3][c.T248]["PRESERVED_T256_STATUS"]
    )
    a, bc = donors
    assert (
        c.obj(caveats["A_STATUS_VERBATIM"])["HISTORICAL_THEOREM_SOURCE"]
        == a["HISTORICAL_THEOREM_SOURCE"]
    )
    assert c.obj(caveats["BC_STATUS_VERBATIM"])["HISTORICAL_SOURCE"] == bc["HISTORICAL_SOURCE"]
    assert c.obj(caveats["SIX_ROW_AUTHORITY_VERBATIM"])["DONOR_JUDGE_STATUS"] == "SELF_CHECK_ONLY"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["CAP_PROOFS_REEXECUTED"] == 0


def test_composition_leaves_inputs_unchanged(authority: Authority, donors: Donors) -> None:
    before = c.render(authority)
    bounds, owners, cursor, _ = authority
    c.compose(bounds, owners, cursor, c.certificates(*donors, owners), cursor)
    assert c.render(authority) == before
