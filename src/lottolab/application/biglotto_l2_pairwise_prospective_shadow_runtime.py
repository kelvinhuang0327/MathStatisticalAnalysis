"""Exact nine-candidate runtime adapters for prospective Big Lotto shadow capture.

The frozen research modules remain the sole owners of candidate construction.
This adapter calls each published entrypoint against the same immutable causal
history and exposes only its legal ticket through the existing ordered-emission
contract used by the common capture layer.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from lottolab.application.biglotto_l2_pairwise_prospective_shadow_capture import (
    ProspectiveCandidateRuntime,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.research import (
    biglotto_l2_pairwise_causal_dyadic_haar_pair_coherence_exact6_candidate_batch_r1 as c5,
)
from lottolab.research import (
    biglotto_l2_pairwise_checkerboard_recurrence_copula as c10,
)
from lottolab.research import (
    biglotto_l2_pairwise_cooccurrence_spectral_weighted_score_candidate_batch_r1 as c2,
)
from lottolab.research import biglotto_l2_pairwise_eighth as c8
from lottolab.research import (
    biglotto_l2_pairwise_entropy_bayesian_weighted_score_candidate_batch_r1 as c1,
)
from lottolab.research import biglotto_l2_pairwise_marked_matrix_profile as c6
from lottolab.research import (
    biglotto_l2_pairwise_profile_cluster_renyi2_regime_candidate_batch_r1 as c4,
)
from lottolab.research import biglotto_l2_pairwise_transfer_entropy as c9
from lottolab.research import (
    biglotto_l2_pairwise_transition_markov_graph_pagerank_traversal_candidate_batch_r1 as c3,
)

BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_IDS = (
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C8",
    "C9",
    "C10",
)
BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION = "V1"

_C1_METHOD_ID = "BMSGV1_L2_PAIRWISE_378b7fc29066cbc8"
_C1_SEMANTIC_SIGNATURE = (
    "259e140c70571b37e15f326688ddf5f4a0e18ba0d1982f8098565232ee375508"
)

type Draw = Sequence[int]
type CausalHistory = Sequence[Draw]


def _causal_history(history: tuple[object, ...]) -> CausalHistory:
    """Narrow the injected opaque history; every frozen producer validates its rows."""

    return cast(CausalHistory, history)


def _emission(
    *,
    target_draw: str,
    history_cutoff: str,
    method_id: str,
    ticket: tuple[int, ...],
) -> OrderedCandidateEmission:
    return OrderedCandidateEmission(
        schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id=method_id,
        strategy_version=BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
        replicate=1,
        target_draw=target_draw,
        history_cutoff=history_cutoff,
        emitted_main_numbers=ticket,
        auxiliary_operand_kind=AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
        auxiliary_operand_availability=(
            AuxiliaryOperandAvailability.EXPLICITLY_MISSING
        ),
        auxiliary_operand_value=None,
    )


def build_biglotto_l2_pairwise_prospective_candidate_runtimes(
    *,
    target_draw: str,
) -> tuple[ProspectiveCandidateRuntime, ...]:
    """Bind all and only the frozen C1-C6/C8-C10 prediction entrypoints."""

    def produce_c1(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        prediction = (
            c1.predict_biglotto_l2_pairwise_null_z2_bayes_changepoint_weighted_score_50(
                _causal_history(history)
            )
        )
        if prediction is None:
            raise ValueError("C1 requires its frozen minimum causal history")
        return _emission(
            target_draw=target_draw,
            history_cutoff=history_cutoff,
            method_id=_C1_METHOD_ID,
            ticket=prediction.ticket,
        )

    def produce_c2(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        prediction = c2.predict_biglotto_l2_pairwise_conditional_cooccurrence_spectral_ipr_weighted_score_300(  # noqa: E501
            _causal_history(history)
        )
        if prediction is None:
            raise ValueError("C2 requires its frozen minimum causal history")
        return _emission(
            target_draw=target_draw,
            history_cutoff=history_cutoff,
            method_id=c2.METHOD_ID,
            ticket=prediction.ticket,
        )

    def produce_c3(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        prediction = c3.predict_biglotto_l2_pairwise_transition_markov_graph_pagerank_traversal_weighted_score_100(  # noqa: E501
            history
        )
        if prediction is None:
            raise ValueError("C3 requires its frozen minimum causal history")
        return _emission(
            target_draw=target_draw,
            history_cutoff=history_cutoff,
            method_id=c3.METHOD_ID,
            ticket=prediction.ticket,
        )

    def produce_c4(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        prediction = c4.predict_biglotto_l2_pairwise_profile_cluster_renyi2_regime_cluster_selection_weighted_score_100(  # noqa: E501
            history
        )
        if prediction is None:
            raise ValueError("C4 requires its frozen minimum causal history")
        return _emission(
            target_draw=target_draw,
            history_cutoff=history_cutoff,
            method_id=c4.METHOD_ID,
            ticket=prediction.ticket,
        )

    def produce_c5(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        prediction = c5.run_design(history, len(history))
        return _emission(
            target_draw=target_draw,
            history_cutoff=history_cutoff,
            method_id=c5.METHOD_ID,
            ticket=prediction.ticket,
        )

    def produce_c6(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        prediction = c6.analyze(history, len(history))
        return _emission(
            target_draw=target_draw,
            history_cutoff=history_cutoff,
            method_id=c6.METHOD_ID,
            ticket=prediction.ticket,
        )

    def produce_c8(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        prediction = c8.analyze(history, len(history))
        return _emission(
            target_draw=target_draw,
            history_cutoff=history_cutoff,
            method_id=c8.METHOD_ID,
            ticket=prediction.ticket,
        )

    def produce_c9(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        prediction = c9.analyze(history, len(history))
        return _emission(
            target_draw=target_draw,
            history_cutoff=history_cutoff,
            method_id=c9.METHOD_ID,
            ticket=prediction.ticket,
        )

    def produce_c10(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        prediction = c10.analyze(history, len(history))
        return _emission(
            target_draw=target_draw,
            history_cutoff=history_cutoff,
            method_id=c10.METHOD_ID,
            ticket=prediction.ticket,
        )

    return (
        ProspectiveCandidateRuntime(
            candidate_id="C1",
            method_id=_C1_METHOD_ID,
            semantic_signature=_C1_SEMANTIC_SIGNATURE,
            strategy_version=BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
            producer=produce_c1,
        ),
        ProspectiveCandidateRuntime(
            candidate_id="C2",
            method_id=c2.METHOD_ID,
            semantic_signature=c2.SEMANTIC_SIGNATURE,
            strategy_version=BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
            producer=produce_c2,
        ),
        ProspectiveCandidateRuntime(
            candidate_id="C3",
            method_id=c3.METHOD_ID,
            semantic_signature=c3.SEMANTIC_SIGNATURE,
            strategy_version=BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
            producer=produce_c3,
        ),
        ProspectiveCandidateRuntime(
            candidate_id="C4",
            method_id=c4.METHOD_ID,
            semantic_signature=c4.SEMANTIC_SIGNATURE,
            strategy_version=BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
            producer=produce_c4,
        ),
        ProspectiveCandidateRuntime(
            candidate_id="C5",
            method_id=c5.METHOD_ID,
            semantic_signature=c5.SEMANTIC_SIGNATURE,
            strategy_version=BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
            producer=produce_c5,
        ),
        ProspectiveCandidateRuntime(
            candidate_id="C6",
            method_id=c6.METHOD_ID,
            semantic_signature=c6.SEMANTIC_SIGNATURE,
            strategy_version=BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
            producer=produce_c6,
        ),
        ProspectiveCandidateRuntime(
            candidate_id="C8",
            method_id=c8.METHOD_ID,
            semantic_signature=c8.SEMANTIC_SIGNATURE,
            strategy_version=BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
            producer=produce_c8,
        ),
        ProspectiveCandidateRuntime(
            candidate_id="C9",
            method_id=c9.METHOD_ID,
            semantic_signature=c9.SEMANTIC_SIGNATURE,
            strategy_version=BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
            producer=produce_c9,
        ),
        ProspectiveCandidateRuntime(
            candidate_id="C10",
            method_id=c10.METHOD_ID,
            semantic_signature=c10.SEMANTIC_SIGNATURE,
            strategy_version=BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION,
            producer=produce_c10,
        ),
    )


__all__ = [
    "BIGLOTTO_L2_PAIRWISE_EXPECTED_CANDIDATE_IDS",
    "BIGLOTTO_L2_PAIRWISE_FROZEN_STRATEGY_VERSION",
    "build_biglotto_l2_pairwise_prospective_candidate_runtimes",
]
