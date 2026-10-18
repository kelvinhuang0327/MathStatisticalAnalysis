"""Exact fair-baseline prospective edge evaluator for BIG_LOTTO portfolios (Python 3.9).

Public entry point:
    evaluate_biglotto_prospective_edge(records, *, experiment_contract,
        expected_contract_sha256, experiment_id, strategy_identity,
        expected_draw_ids, ticket_count, allow_interim_prefix=False,
        certification=None)

For each fixed draw i with its own portfolio A_i (m in {2, 3, 5} tickets), the
existing K235 scorer supplies the exact MAX_HIT_WEIGHTS of A_i under a fair
6-of-49 draw, so p_i = P(MAX_HITS >= 3 | A_i) is an exact rational over
13983816. y_i = 1 when the observed MAX_HITS >= 3, else 0.

Primary statistic: the likelihood-ratio e-process with the preregistered fixed
alternative q_i = (3/2) * p_i,
    e_i = q_i / p_i                 if y_i = 1
    e_i = (1 - q_i) / (1 - p_i)     if y_i = 0
    E_0 = 1,  E_n = e_1 * ... * e_n.
Let F_{i-1} hold everything known before draw i, including the history and the
strategy's choice of A_i. Under the fair conditional null the draw is uniform
and independent of F_{i-1}, so P(y_i = 1 | F_{i-1}) = p_i exactly and
    E[e_i | F_{i-1}] = p_i * q_i / p_i + (1 - p_i) * (1 - q_i) / (1 - p_i) = 1.
q_i <= 1 makes every e_i >= 0, so E_n is a nonnegative test martingale and
Ville's inequality gives P(sup_n E_n >= 20) <= 1/20. This holds however A_i
adapts to past data, with a different p_i every draw, and under optional
stopping; the adaptive p_i vector is never treated as a fixed independent
Poisson-binomial sample. The premise is that A_i was fixed before draw i.

Evidence boundary: this module cannot itself establish that premise, that the
contract was fixed before the first prediction, or that an outcome is official.
Every accepted result is EVIDENCE_STATUS=DIAGNOSTIC_ONLY. Certification goes only
through the existing RFC 3161 portfolio verifier with
require_independent_verification=True. That verifier currently refuses without a
trusted draw-cutoff source, and no official-result authenticator exists, so a
certification request always fails closed. E_n >= 20 is only preregistered
threshold evidence against the fair conditional null, never proof of a stable,
reproducible, or profitable predictive edge. No network, filesystem writes,
prediction generation, or history replay occur.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from tools.score_biglotto_portfolio_prospective_r1 import (
        ALLOWED_TICKET_COUNTS,
        FORBIDDEN_CLAIM_VALUES,
        OUTCOME_DENOMINATOR,
        ContractError,
        _validate_single_ticket,
        portfolio_exact_baseline,
        score_biglotto_portfolio_prospective,
    )
    from tools.verify_biglotto_portfolio_predraw_r1 import (
        compute_canonical_contract_sha256,
        verify_biglotto_portfolio_predraw_boundary,
    )
except ImportError:
    from score_biglotto_portfolio_prospective_r1 import (  # type: ignore
        ALLOWED_TICKET_COUNTS,
        FORBIDDEN_CLAIM_VALUES,
        OUTCOME_DENOMINATOR,
        ContractError,
        _validate_single_ticket,
        portfolio_exact_baseline,
        score_biglotto_portfolio_prospective,
    )
    from verify_biglotto_portfolio_predraw_r1 import (  # type: ignore
        compute_canonical_contract_sha256,
        verify_biglotto_portfolio_predraw_boundary,
    )

EVALUATOR_ID = "MSA_BIGLOTTO_PROSPECTIVE_EDGE_EVALUATOR_R1"
SUCCESS_MIN_HITS = 3
ALTERNATIVE_MULTIPLIER = Fraction(3, 2)
ALPHA = Fraction(1, 20)
EVIDENCE_THRESHOLD = 20

# Fixed design of this evaluator version. The externally fixed contract must state
# every value exactly; a contract with any other value is refused, never re-tested.
PREREGISTERED_DESIGN = {
    "DRAW_MODEL": "FAIR_6_OF_49",
    "NUMBER_POOL": 49,
    "DRAW_SIZE": 6,
    "OUTCOME_DENOMINATOR": OUTCOME_DENOMINATOR,
    "PRIMARY_SUCCESS_EVENT": "MAX_HITS>=3",
    "PRIMARY_STATISTIC": "LIKELIHOOD_RATIO_E_PROCESS",
    "ALTERNATIVE_MULTIPLIER": "3/2",
    "ALPHA": "1/20",
    "EVIDENCE_THRESHOLD": 20,
}
CONTRACT_IDENTITY_FIELDS = (
    "EXPERIMENT_ID",
    "STRATEGY_IDENTITY",
    "TICKET_COUNT",
    "EXPECTED_DRAW_IDS",
)
CONTRACT_FIELDS = frozenset(PREREGISTERED_DESIGN).union(CONTRACT_IDENTITY_FIELDS)

RECORD_FIELDS = frozenset(
    {
        "EXPERIMENT_ID",
        "DRAW_ID",
        "TICKET_COUNT",
        "PREDICTED_TICKETS",
        "STRATEGY_IDENTITY",
        "INPUT_SNAPSHOT_SHA256",
        "EXPERIMENT_CONTRACT_SHA256",
        "RFC3161_EVIDENCE_REFERENCE",
        "OFFICIAL_RESULT_REFERENCE",
        "SIX_OFFICIAL_MAIN_NUMBERS",
        "INPUT_CUTOFF",
        "PREDICTION_CAPTURE_ID",
        "PREDICTION_CAPTURE_TIME",
        "DRAW_TIME",
    }
)
OPTIONAL_RECORD_FIELDS = frozenset({"INPUT_DRAW_IDS"})
PROVENANCE_FIELD_CODES = (
    ("RFC3161_EVIDENCE_REFERENCE", "UNVERIFIED_PREDRAW_EVIDENCE"),
    ("OFFICIAL_RESULT_REFERENCE", "UNAUTHENTICATED_OUTCOME"),
)
CERTIFICATION_INPUTS = frozenset(
    {
        "evidence_bundle",
        "pinned_tsa_cert_pem_path",
        "pinned_tsa_cert_sha256",
        "snapshot_files_by_sha256",
    }
)

NULL_HYPOTHESIS = (
    "Conditional on all information before each draw, including the strategy's portfolio, "
    "the six main numbers are uniform over the 13983816 six-number subsets of 1..49."
)
E_PROCESS_VALIDITY = (
    "Under the null E[e_i | F_(i-1)] = 1 for every portfolio fixed before draw i, so E_n is a "
    "nonnegative test martingale and P(sup_n E_n >= 20) <= 1/20 (Ville). Valid for adaptive "
    "portfolios, a different exact p_i per draw, and optional stopping; no fixed-vector "
    "Poisson-binomial model is used."
)
CLAIM_BOUNDARY = (
    "DIAGNOSTIC_ONLY: pre-draw portfolio fixation, contract fixation time, and official outcomes "
    "are not verified here. E_VALUE >= 20 would only be preregistered-threshold evidence against "
    "the fair conditional null, not proof of a stable, reproducible, or profitable edge."
)


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise ContractError(code, detail)


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _is_draw_id(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9]{9}", value) is not None


def _parse_time(raw: str) -> datetime:
    return datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)


def _ratio(value: Fraction, count: int) -> str | None:
    return None if count == 0 else str(value / count)


def _float(value: Fraction) -> float:
    try:
        return float(value)
    except OverflowError:
        return float("inf")


def exact_success_probability(tickets: Sequence[Sequence[int]]) -> Fraction:
    """Exact p = P(MAX_HITS >= 3 | tickets) from the existing K235 exact baseline."""
    weights = portfolio_exact_baseline(tickets)["MAX_HIT_WEIGHTS"]
    return Fraction(sum(weights[SUCCESS_MIN_HITS:]), OUTCOME_DENOMINATOR)


def e_process_factor(p_success: Fraction, success: int) -> Fraction:
    """One draw's likelihood-ratio factor under the fixed 3/2 alternative."""
    _require(
        isinstance(p_success, Fraction) and 0 < p_success < 1,
        "INVALID_SUCCESS_PROBABILITY",
        "p must be an exact Fraction strictly between 0 and 1",
    )
    _require(
        type(success) is int and success in (0, 1),
        "INVALID_SUCCESS_INDICATOR",
        "success must be the integer 0 or 1",
    )
    q = ALTERNATIVE_MULTIPLIER * p_success
    _require(q <= 1, "ALTERNATIVE_NOT_A_PROBABILITY", "(3/2) * p exceeds 1")
    return q / p_success if success else (1 - q) / (1 - p_success)


def _validate_contract(contract: Any, expected_contract_sha256: Any) -> None:
    _require(isinstance(contract, Mapping), "INVALID_CONTRACT", "contract must be a mapping")
    _require(
        isinstance(expected_contract_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", expected_contract_sha256) is not None,
        "CONTRACT_HASH_CHANGED",
        "externally pinned contract SHA-256 must be 64 lowercase hex digits",
    )
    try:
        actual = compute_canonical_contract_sha256(contract)
    except (TypeError, ValueError) as exc:
        raise ContractError("INVALID_CONTRACT", "contract is not canonical JSON") from exc
    _require(
        actual == expected_contract_sha256,
        "CONTRACT_HASH_CHANGED",
        f"contract hashes to {actual}, externally pinned {expected_contract_sha256}",
    )
    keys = set(contract)
    _require(
        keys == CONTRACT_FIELDS,
        "INVALID_CONTRACT",
        f"missing {sorted(map(str, CONTRACT_FIELDS - keys))}, "
        f"unexpected {sorted(map(str, keys - CONTRACT_FIELDS))}",
    )
    for field, fixed in PREREGISTERED_DESIGN.items():
        value = contract[field]
        _require(
            type(value) is type(fixed) and value == fixed,
            "PREREGISTERED_PARAMETER_CHANGED",
            f"{field}={value!r}; this evaluator fixes {fixed!r}",
        )
    _require(_is_text(contract["EXPERIMENT_ID"]), "INVALID_CONTRACT", "EXPERIMENT_ID")
    strategy = contract["STRATEGY_IDENTITY"]
    _require(
        _is_text(strategy) and strategy.upper() not in {"UNKNOWN", "UNVERIFIED", "NONE"},
        "INVALID_CONTRACT",
        "STRATEGY_IDENTITY must name a fixed strategy version",
    )
    ticket_count = contract["TICKET_COUNT"]
    _require(
        type(ticket_count) is int and ticket_count in ALLOWED_TICKET_COUNTS,
        "INVALID_CONTRACT",
        "TICKET_COUNT must be 2, 3, or 5",
    )
    schedule = contract["EXPECTED_DRAW_IDS"]
    _require(
        isinstance(schedule, list) and bool(schedule) and all(_is_draw_id(d) for d in schedule),
        "INVALID_CONTRACT",
        "EXPECTED_DRAW_IDS must be a nonempty list of nine-digit draw IDs",
    )
    _require(len(set(schedule)) == len(schedule), "DUPLICATE_DRAW_ID", "contract schedule")


def _bind_request(
    contract: Mapping[str, Any],
    experiment_id: Any,
    strategy_identity: Any,
    expected_draw_ids: Any,
    ticket_count: Any,
) -> None:
    _require(
        experiment_id == contract["EXPERIMENT_ID"],
        "EXPERIMENT_ID_CHANGED",
        f"request {experiment_id!r} != contract {contract['EXPERIMENT_ID']!r}",
    )
    _require(
        strategy_identity == contract["STRATEGY_IDENTITY"],
        "STRATEGY_IDENTITY_CHANGED",
        f"request {strategy_identity!r} != contract {contract['STRATEGY_IDENTITY']!r}",
    )
    _require(
        type(ticket_count) is int and ticket_count == contract["TICKET_COUNT"],
        "TICKET_COUNT_CHANGED",
        f"request {ticket_count!r} != contract {contract['TICKET_COUNT']!r}",
    )
    _require(
        isinstance(expected_draw_ids, (list, tuple))
        and list(expected_draw_ids) == contract["EXPECTED_DRAW_IDS"],
        "DRAW_SET_CHANGED",
        "requested draw IDs differ from the contract's fixed ordered schedule",
    )


def _validate_records(
    records: Any, contract: Mapping[str, Any], contract_sha256: str
) -> dict[str, Mapping[str, Any]]:
    _require(isinstance(records, (list, tuple)), "INVALID_RECORDS", "records must be a list/tuple")
    schedule = contract["EXPECTED_DRAW_IDS"]
    ticket_count = contract["TICKET_COUNT"]
    by_draw: dict[str, Mapping[str, Any]] = {}
    for record in records:
        _require(isinstance(record, Mapping), "INVALID_RECORD", "record must be a mapping")
        for field, code in PROVENANCE_FIELD_CODES:
            value = record.get(field)
            _require(
                _is_text(value) and value.upper() not in FORBIDDEN_CLAIM_VALUES,
                code,
                f"{field} must be a nonblank locator string, not a status claim",
            )
        keys = set(record)
        extra = keys - RECORD_FIELDS - OPTIONAL_RECORD_FIELDS
        _require(not extra, "UNEXPECTED_FIELD", f"{sorted(map(str, extra))}")
        missing = RECORD_FIELDS - keys
        _require(not missing, "MISSING_FIELD", f"{sorted(missing)}")
        draw = record["DRAW_ID"]
        _require(_is_draw_id(draw), "INVALID_DRAW_ID", "expected nine ASCII digits")
        _require(draw not in by_draw, "DUPLICATE_DRAW_ID", draw)
        _require(draw in schedule, "UNEXPECTED_DRAW_ID", draw)
        _require(
            record["EXPERIMENT_ID"] == contract["EXPERIMENT_ID"], "EXPERIMENT_ID_CHANGED", draw
        )
        _require(
            record["STRATEGY_IDENTITY"] == contract["STRATEGY_IDENTITY"],
            "STRATEGY_IDENTITY_CHANGED",
            draw,
        )
        _require(
            record["EXPERIMENT_CONTRACT_SHA256"] == contract_sha256, "CONTRACT_HASH_CHANGED", draw
        )
        declared = record["TICKET_COUNT"]
        _require(
            type(declared) is int and declared == ticket_count,
            "TICKET_COUNT_CHANGED",
            f"{draw}: TICKET_COUNT {declared!r} != contract {ticket_count}",
        )
        tickets = record["PREDICTED_TICKETS"]
        _require(isinstance(tickets, (list, tuple)), "MALFORMED_TICKETS", draw)
        _require(
            len(tickets) == ticket_count,
            "TICKET_COUNT_CHANGED",
            f"{draw}: {len(tickets)} tickets != contract {ticket_count}",
        )
        for ticket in tickets:
            try:
                _validate_single_ticket(ticket)
            except ContractError as err:
                raise ContractError("MALFORMED_TICKETS", f"{draw}: {err}") from err
        by_draw[draw] = record
    return by_draw


def _scorer_prediction(record: Mapping[str, Any]) -> dict[str, Any]:
    row = {
        field: record[field]
        for field in (
            "EXPERIMENT_ID",
            "DRAW_ID",
            "PREDICTED_TICKETS",
            "STRATEGY_IDENTITY",
            "INPUT_SNAPSHOT_SHA256",
            "INPUT_CUTOFF",
            "PREDICTION_CAPTURE_ID",
            "PREDICTION_CAPTURE_TIME",
        )
    }
    row["PREDRAW_EVIDENCE_LOCATOR"] = record["RFC3161_EVIDENCE_REFERENCE"]
    if "INPUT_DRAW_IDS" in record:
        row["INPUT_DRAW_IDS"] = record["INPUT_DRAW_IDS"]
    return row


def _scorer_outcome(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "DRAW_ID": record["DRAW_ID"],
        "SIX_OFFICIAL_MAIN_NUMBERS": record["SIX_OFFICIAL_MAIN_NUMBERS"],
        "DRAW_TIME": record["DRAW_TIME"],
        "OFFICIAL_RESULT_SOURCE": record["OFFICIAL_RESULT_REFERENCE"],
    }


def _refuse_or_certify(
    certification: Any,
    contract: Mapping[str, Any],
    contract_sha256: str,
    observed_ids: list[str],
    by_draw: Mapping[str, Mapping[str, Any]],
) -> None:
    """Integration boundary with the existing RFC 3161 verifier; never returns today."""
    _require(
        isinstance(certification, Mapping),
        "UNVERIFIED_PREDRAW_EVIDENCE",
        "certification needs verifier inputs; a flag or status string verifies nothing",
    )
    unknown = set(certification) - CERTIFICATION_INPUTS
    _require(
        not unknown, "UNVERIFIED_PREDRAW_EVIDENCE", f"unknown inputs {sorted(map(str, unknown))}"
    )
    # The verifier reads the pinned hash from EXPERIMENT_CONTRACT_SHA256; it was already
    # checked against the full contract, so only the observed prefix is passed as draw set.
    verifier_contract = dict(contract)
    verifier_contract["EXPECTED_DRAW_IDS"] = list(observed_ids)
    verifier_contract["EXPERIMENT_CONTRACT_SHA256"] = contract_sha256
    predictions = []
    for draw in observed_ids:
        row = _scorer_prediction(by_draw[draw])
        row["TICKET_COUNT"] = by_draw[draw]["TICKET_COUNT"]
        row["EXPERIMENT_CONTRACT_SHA256"] = contract_sha256
        predictions.append(row)
    outcomes = [_scorer_outcome(by_draw[draw]) for draw in observed_ids]
    try:
        verify_biglotto_portfolio_predraw_boundary(
            predictions,
            outcomes,
            verifier_contract,
            require_independent_verification=True,
            **dict(certification),
        )
    except Exception as exc:  # any verifier failure leaves the evidence unverified
        raise ContractError(
            "UNVERIFIED_PREDRAW_EVIDENCE", f"existing RFC 3161 portfolio verifier refused: {exc}"
        ) from exc
    raise ContractError(
        "UNAUTHENTICATED_OUTCOME",
        "no trusted official-result authenticator exists; outcome references stay unauthenticated",
    )


def evaluate_biglotto_prospective_edge(
    records: Sequence[Mapping[str, Any]],
    *,
    experiment_contract: Mapping[str, Any],
    expected_contract_sha256: str,
    experiment_id: str,
    strategy_identity: str,
    expected_draw_ids: Sequence[str],
    ticket_count: int,
    allow_interim_prefix: bool = False,
    certification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Exact fair baseline, observed hits, and e-process for one fixed experiment.

    expected_contract_sha256 must come from outside this call (e.g. the hash bound into
    the pre-draw RFC 3161 payloads); the contract must hash to it and state this
    evaluator's preregistered design. Records combine each draw's prediction and outcome.
    By default every scheduled draw is required. allow_interim_prefix=True accepts only
    the leading scheduled draws (sequential monitoring); a gap is never accepted.
    certification, when given, must hold the existing verifier's evidence inputs and
    fails closed with UNVERIFIED_PREDRAW_EVIDENCE or UNAUTHENTICATED_OUTCOME.
    """
    _validate_contract(experiment_contract, expected_contract_sha256)
    contract = experiment_contract
    _bind_request(contract, experiment_id, strategy_identity, expected_draw_ids, ticket_count)
    _require(
        type(allow_interim_prefix) is bool,
        "INVALID_ARGUMENT",
        "allow_interim_prefix must be a bool",
    )
    by_draw = _validate_records(records, contract, expected_contract_sha256)

    schedule = list(contract["EXPECTED_DRAW_IDS"])
    observed_count = len(by_draw)
    observed_ids = schedule[:observed_count]
    gaps = [draw for draw in observed_ids if draw not in by_draw]
    _require(
        not gaps,
        "MISSING_DRAW_ID",
        f"observations must be the leading scheduled draws; missing {gaps}",
    )
    _require(
        allow_interim_prefix or observed_count == len(schedule),
        "MISSING_DRAW_ID",
        f"complete evaluation requires every scheduled draw; missing {schedule[observed_count:]}",
    )

    scored_rows: list[Mapping[str, Any]] = []
    if observed_count:
        scored = score_biglotto_portfolio_prospective(
            [_scorer_prediction(by_draw[draw]) for draw in observed_ids],
            [_scorer_outcome(by_draw[draw]) for draw in observed_ids],
            experiment_id=contract["EXPERIMENT_ID"],
            strategy_identity=contract["STRATEGY_IDENTITY"],
            expected_draw_ids=observed_ids,
            ticket_count=contract["TICKET_COUNT"],
        )
        scored_rows = scored["PER_DRAW"]
        _require(
            [row["DRAW_ID"] for row in scored_rows] == observed_ids,
            "SCORER_CONTRACT_DRIFT",
            "scorer rows do not follow the fixed schedule",
        )
        draw_times = [_parse_time(by_draw[draw]["DRAW_TIME"]) for draw in observed_ids]
        _require(
            all(draw_times[i] < draw_times[i + 1] for i in range(len(draw_times) - 1)),
            "DRAW_SCHEDULE_NOT_CHRONOLOGICAL",
            "DRAW_TIME must strictly increase along the fixed schedule",
        )

    per_draw: list[dict[str, Any]] = []
    e_value = Fraction(1)
    max_e_value = e_value
    first_crossed: str | None = None
    fair_expected = Fraction(0)
    observed_successes = 0
    for row in scored_rows:
        weights = list(row["DRAW_EXACT_BASELINE"]["MAX_HIT_WEIGHTS"])
        success_weight = sum(weights[SUCCESS_MIN_HITS:])
        p_success = Fraction(success_weight, OUTCOME_DENOMINATOR)
        success = 1 if row["MAX_HITS"] >= SUCCESS_MIN_HITS else 0
        factor = e_process_factor(p_success, success)
        e_value *= factor
        max_e_value = max(max_e_value, e_value)
        if first_crossed is None and e_value >= EVIDENCE_THRESHOLD:
            first_crossed = row["DRAW_ID"]
        fair_expected += p_success
        observed_successes += success
        per_draw.append(
            {
                "DRAW_ID": row["DRAW_ID"],
                "TICKET_HITS": list(row["TICKET_HITS"]),
                "MAX_HITS": row["MAX_HITS"],
                "MAX_HIT_WEIGHTS": weights,
                "SUCCESS_WEIGHT": success_weight,
                "P_SUCCESS": str(p_success),
                "Q_ALTERNATIVE": str(ALTERNATIVE_MULTIPLIER * p_success),
                "Y": success,
                "E_FACTOR": str(factor),
                "E_VALUE": str(e_value),
                "CUMULATIVE_OBSERVED_SUCCESSES": observed_successes,
                "CUMULATIVE_FAIR_EXPECTED_SUCCESSES": str(fair_expected),
            }
        )

    if certification is not None:
        _refuse_or_certify(certification, contract, expected_contract_sha256, observed_ids, by_draw)

    return {
        "EVALUATOR_ID": EVALUATOR_ID,
        "EXPERIMENT_ID": contract["EXPERIMENT_ID"],
        "STRATEGY_IDENTITY": contract["STRATEGY_IDENTITY"],
        "TICKET_COUNT": contract["TICKET_COUNT"],
        "EXPERIMENT_CONTRACT_SHA256": expected_contract_sha256,
        "DRAW_MODEL": PREREGISTERED_DESIGN["DRAW_MODEL"],
        "OUTCOME_DENOMINATOR": OUTCOME_DENOMINATOR,
        "PRIMARY_SUCCESS_EVENT": PREREGISTERED_DESIGN["PRIMARY_SUCCESS_EVENT"],
        "SCHEDULED_DRAW_IDS": schedule,
        "OBSERVED_DRAW_IDS": list(observed_ids),
        "UNOBSERVED_SCHEDULED_DRAW_IDS": schedule[observed_count:],
        "SCHEDULE_STATUS": "COMPLETE" if observed_count == len(schedule) else "INTERIM_PREFIX",
        "OBSERVED_DRAW_COUNT": observed_count,
        "PER_DRAW": per_draw,
        "FAIR_EXPECTED_SUCCESSES": str(fair_expected),
        "FAIR_EXPECTED_RATE": _ratio(fair_expected, observed_count),
        "OBSERVED_SUCCESSES": observed_successes,
        "OBSERVED_SUCCESS_RATE": _ratio(Fraction(observed_successes), observed_count),
        "EXCESS_SUCCESS_COUNT": str(observed_successes - fair_expected),
        "ALTERNATIVE_MULTIPLIER": PREREGISTERED_DESIGN["ALTERNATIVE_MULTIPLIER"],
        "ALPHA": PREREGISTERED_DESIGN["ALPHA"],
        "EVIDENCE_THRESHOLD": EVIDENCE_THRESHOLD,
        "E_VALUE": str(e_value),
        "E_VALUE_FLOAT": _float(e_value),
        "MAX_E_VALUE": str(max_e_value),
        "THRESHOLD_FIRST_CROSSED_DRAW_ID": first_crossed,
        "STATISTICAL_SIGNAL": (
            "THRESHOLD_REACHED" if first_crossed is not None else "THRESHOLD_NOT_REACHED"
        ),
        "NULL_HYPOTHESIS": NULL_HYPOTHESIS,
        "E_PROCESS_VALIDITY": E_PROCESS_VALIDITY,
        "EVIDENCE_STATUS": "DIAGNOSTIC_ONLY",
        "PREDRAW_EVIDENCE_STATUS": "NOT_VERIFIED",
        "OFFICIAL_OUTCOME_STATUS": "NOT_AUTHENTICATED",
        "CERTIFIED_PROSPECTIVE_DRAW_COUNT": 0,
        "PREDICTIVE_SUCCESS_IMPROVEMENT": "NOT_ESTABLISHED",
        "CLAIM_BOUNDARY": CLAIM_BOUNDARY,
    }
