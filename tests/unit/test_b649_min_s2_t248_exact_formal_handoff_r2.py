"""Focused exact-domain, rational-envelope and falsifiable certificate checks."""

from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import replace
from fractions import Fraction

import pytest

from lottolab.research import b649_min_s2_t248_exact_formal_handoff_r2 as cert


@pytest.fixture(scope="module")
def primary() -> tuple[list[cert.Record], dict[str, int], str]:
    return cert.enumerate_records()


@pytest.fixture(scope="module")
def independent() -> tuple[list[cert.Record], dict[str, int], str]:
    return cert.enumerate_records(True)


@pytest.fixture(scope="module")
def authority() -> cert.Document:
    return cert.load_authority()[0]


def test_model_and_goodman() -> None:
    facts = cert.model_facts()
    assert (facts["G_EDGES"], facts["W"], facts["GOODMAN_SUM"]) == (93, 828, 294)
    assert (facts["CORE"], facts["ZEROS"], facts["SPLIT_CONSTANT"]) == (15, 5, 234)
    assert (facts["SUM_CHOOSE3_DEGREES"], facts["A_MAX"]) == (2326, 198)
    # Independently use inclusion-exclusion in the complement.
    complement_degrees = [13 - int(d) for d in cert.TARGET]
    assert 1140 - 18 * 97 + sum(d * (d - 1) // 2 for d in complement_degrees) == 294


def test_raw_domains_complete() -> None:
    product_domain, recursive_domain = cert.primary_sigmas(), cert.independent_sigmas()
    assert product_domain == recursive_domain
    assert len(set(product_domain)) == 9 * 3 * 5 * 21 == 2835
    assert product_domain[0] == (0,) * 15
    assert product_domain[-1] == (0,) * 3 + (1,) * 8 + (2, 4, 5, 5)


def test_independent_records_counts_and_maxima(
    primary: tuple[list[cert.Record], dict[str, int], str],
    independent: tuple[list[cert.Record], dict[str, int], str],
) -> None:
    records, counts, zero_hash = primary
    other, other_counts, other_zero_hash = independent
    assert records == other and counts == other_counts == cert.EXPECTED_COUNTS
    assert zero_hash == other_zero_hash
    assert len(records) == 1087
    assert Counter(v.branch for v in records) == {"A": 705, "B": 314, "C": 68}
    assert {r: max(v.bound for v in records if v.r == r) for r in range(10, 25, 2)} == {
        10: 246,
        12: 248,
        14: 248,
        16: 246,
        18: 246,
        20: 244,
        22: 246,
        24: 228,
    }
    cert.validate_records(records, other)
    assert counts["DISTINCT_CANDIDATES"] == sum(
        counts[k]
        for k in (
            "DISTINCT_EQUAL_EXCLUDED",
            "DISTINCT_D2_EXCLUDED",
            "DISTINCT_TAU_EXCLUDED",
            "DISTINCT_RETAINED",
        )
    )
    assert counts["SAME_CANDIDATES"] == sum(
        counts[k]
        for k in (
            "SAME_D2_EXCLUDED",
            "SAME_ER_EXCLUDED",
            "SAME_RETAINED",
        )
    )


def test_record_schema_and_independent_encoding(
    primary: tuple[list[cert.Record], dict[str, int], str],
    independent: tuple[list[cert.Record], dict[str, int], str],
) -> None:
    raw = cert.records_bytes(primary[0])
    assert raw == cert.records_bytes(independent[0], True)
    assert raw.endswith(b"\n") and len(raw.splitlines()) == 1087
    for line, record in zip(raw.decode("utf-8").splitlines(), primary[0], strict=True):
        fields = line.split("|")
        assert len(fields) == 8 and fields[0] == "v1"
        assert tuple(map(int, fields[1].split(","))) == record.sigma
        assert fields[3] in ("A", "B", "C")
        assert list(map(int, (fields[2], *fields[4:]))) == [
            record.r,
            record.core,
            record.zero,
            record.correction,
            record.bound,
        ]


def test_cross_split_identity_for_whole_domain(
    primary: tuple[list[cert.Record], dict[str, int], str],
) -> None:
    # General mixed-triangle formula vs expanded polynomial at every retained state.
    for record in primary[0]:
        s, r = record.sigma, record.r
        h = [8 - d + v for d, v in zip(cert.D, s, strict=True)]
        constant = 294 - (5 * (54 + r) + 15 * (r - 10)) // 2
        constant += sum(v * degree for v, degree in zip(s, h, strict=True)) - 2 * r
        assert constant == record.core
        assert record.correction >= 0


@pytest.mark.parametrize("defect", ["branch", "sign", "correction", "omission", "duplicate"])
def test_record_mutations_rejected(
    defect: str,
    primary: tuple[list[cert.Record], dict[str, int], str],
    independent: tuple[list[cert.Record], dict[str, int], str],
) -> None:
    records = list(primary[0])
    pos = next(i for i, v in enumerate(records) if v.branch == "C" and v.correction > 0)
    value = records[pos]
    if defect == "branch":
        records[pos] = replace(value, branch="A")
    elif defect == "sign":
        records[pos] = replace(value, bound=value.core + value.zero + value.correction)
    elif defect == "correction":
        records[pos] = replace(value, correction=value.correction + 1, bound=value.bound - 1)
    elif defect == "omission":
        records.pop()
    else:
        records[-1] = records[0]
    with pytest.raises(ValueError):
        cert.validate_records(records, independent[0])


def test_distinct_degree_two_is_excluded_only_when_common(
    primary: tuple[list[cert.Record], dict[str, int], str],
) -> None:
    # Excluding *any* d=2 companion changes these independently fixed counts.
    counts = primary[1]
    assert counts["DISTINCT_EQUAL_EXCLUDED"] == 68 * 78
    assert counts["DISTINCT_D2_EXCLUDED"] == 68 * 12 * 11
    assert counts["DISTINCT_RETAINED"] == 397980
    assert counts["SAME_D2_EXCLUDED"] == 314 + 68


@pytest.mark.parametrize("pid", ["66555555554442000000", "66655555555332000000", ""])
def test_wrong_profile_rejected(pid: str) -> None:
    with pytest.raises(ValueError, match="profile"):
        cert.model_facts(pid)


@pytest.mark.parametrize(
    "key,value",
    [
        ("PAIR_LINEARITY", False),
        ("DISTINCT_LABELS_PER_TICKET", 5),
        ("TRIPLES", 21),
        ("PAIRS", 28),
        ("SUPPORT_SIZES", [1, 2, 3]),
    ],
)
def test_weakened_model_rejected(key: str, value: object) -> None:
    model = {**cert.MODEL, key: value}
    with pytest.raises(ValueError, match="model"):
        cert.model_facts(model=model)


def test_complete_old_new_route_b() -> None:
    old, new = cert.envelope(cert.TARGET, 265), cert.envelope(cert.TARGET, 248)
    assert len(old) == 244 and len(new) == 227 and new == old[:227]
    assert max(t[1] for t in old) == 313395060
    assert max(t[1] for t in new) == 313242512
    assert new[-1] == (248, 313242512, 372, 198, 206850, 4970672)
    assert 313395060 - 313242512 == 152548
    for term in [*old, *new]:
        t, bound, q, _, s4, s3 = term
        assert q * 4 >= 30 * t - 5954
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        assert 0 <= bound - exact < 1


@pytest.mark.parametrize("cap", [223, 247, 249, 266, True])
def test_wrong_cap_rejected(cap: int) -> None:
    with pytest.raises(ValueError, match="cap"):
        cert.envelope(cert.TARGET, cap)


def test_other_profile_5956_constant_rejected() -> None:
    with pytest.raises(ValueError, match="K4 constant"):
        cert.envelope(cert.TARGET, 248, 5956)


@pytest.mark.parametrize("field", [1, 2, 4, 5])
def test_route_b_rounding_and_credit_mutations_rejected(field: int) -> None:
    terms = cert.envelope(cert.TARGET, 248)
    row = list(terms[-1])
    row[field] -= 1
    terms[-1] = (row[0], row[1], row[2], row[3], row[4], row[5])
    with pytest.raises(ValueError):
        cert.validate_terms(cert.TARGET, 248, terms)


def test_source_hash_negative() -> None:
    with pytest.raises(ValueError, match="hash"):
        cert.checked_blob(cert.BASE_HEAD, cert.BASE_RESULT, "0" * 64)


def test_duplicate_json_key_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        json.loads('{"value": 1, "value": 2}', object_pairs_hook=cert.unique_object)


def test_family_read_only_replay_and_cursor_negative(authority: cert.Document) -> None:
    before = cert.render(authority)
    cursor = cert.obj(authority["CURSOR"])
    projected = cert.project_one(authority, cursor, cert.TARGET, 248, 313242512)
    assert projected["RESOLVED_ROWS"] == 4647 and projected["CURSOR_ROWS"] == 197
    assert projected["FAMILY_AFTER_SINGLE_ROW"] == 313395060
    assert projected["SINGLE_ROW_FAMILY_DELTA"] == 0
    assert projected["FAMILY_OWNERS_AFTER"] == ["66655555555332000000"]
    assert cert.render(authority) == before
    mutated_cursor = copy.deepcopy(cursor)
    mutated_cursor["BOUND"] = -1
    with pytest.raises(ValueError, match="cursor mutation"):
        cert.project_one(authority, mutated_cursor, cert.TARGET, 248, 313242512)
    altered_base = copy.deepcopy(authority)
    cert.obj(altered_base["RESOLVED_ROW_BOUNDS"])[cert.TARGET] = 313242512
    with pytest.raises(ValueError, match="Base"):
        cert.project_one(
            altered_base, cert.obj(altered_base["CURSOR"]), cert.TARGET, 248, 313242512
        )


def test_exact_result_replay_and_caveats(authority: cert.Document) -> None:
    result = cert.compute_result()
    assert cert.render(result) == (cert.ROOT / cert.RESULT).read_bytes()
    assert result["INHERITED_BASE_RESULT_VERBATIM"] == authority
    enumeration = cert.obj(result["ENUMERATION"])
    assert enumeration["LEGACY_RESEARCH_DIGEST"] == cert.LEGACY_RESEARCH_DIGEST
    assert enumeration["LEGACY_DIGEST_MATCH"] == "NOT_VERIFIED"
    assert result["HISTORICAL_R14"] == cert.HISTORICAL_R14
    assert result["STRICT_GAIN_EXCLUDED"] == "YES"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
