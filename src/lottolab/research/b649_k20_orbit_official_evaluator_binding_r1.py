"""Bind terminal recounts to the byte-pinned official evaluator, never a callback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from types import CodeType, FunctionType, ModuleType
from typing import Any

from lottolab.research import b649_k20_four_ticket_orbit_source_binding_r1 as source

OFFICIAL_CALLABLE = source.OFFICIAL_IMPORT_NAME + ".evaluate_portfolio"


class OfficialEvaluatorBindingError(ValueError):
    """The terminal evaluator does not have the required executable identity."""


def _verified_evaluate(module: ModuleType, data: bytes) -> FunctionType:
    # Reuse the unchanged, pinned source loader rather than duplicating its gates.
    source._module_file(  # pyright: ignore[reportPrivateUsage]
        module, source.OFFICIAL_SOURCE_PATH, "TERMINAL_OFFICIAL_EVALUATOR"
    )
    source._verify_sha256(  # pyright: ignore[reportPrivateUsage]
        data, source.OFFICIAL_SOURCE_SHA256, "TERMINAL_OFFICIAL_EVALUATOR"
    )
    # Hashing the backing file alone cannot detect an in-memory fixed-count swap.
    compiled = compile(data, str(source.OFFICIAL_SOURCE_PATH), "exec", dont_inherit=True)
    expected = next(
        item
        for item in compiled.co_consts
        if isinstance(item, CodeType) and item.co_name == "evaluate_portfolio"
    )
    evaluate = getattr(module, "evaluate_portfolio", None)
    if (
        not isinstance(evaluate, FunctionType)
        or evaluate.__module__ != source.OFFICIAL_IMPORT_NAME
        or evaluate.__globals__ is not vars(module)
        or evaluate.__code__ != expected
        or evaluate.__code__.co_filename != str(source.OFFICIAL_SOURCE_PATH)
        or evaluate.__defaults__ is not None
        or evaluate.__kwdefaults__
        != {
            "pool_size": 49,
            "draw_size": 6,
            "outright_matches": 3,
            "draws": None,
            "chunk_size": 1 << 21,
        }
    ):
        raise OfficialEvaluatorBindingError("OFFICIAL_EVALUATOR_CALLABLE_IDENTITY_MISMATCH")
    return evaluate


@dataclass(frozen=True)
class OfficialRecountBinding:
    """Verified evaluator capability. Production callers accept this exact type."""

    module: ModuleType = field(repr=False, compare=False)
    evaluator_bytes: bytes = field(repr=False)
    _evaluate: Callable[..., Any] = field(repr=False, compare=False)

    def validate(self) -> None:
        current = source._stable_bytes(  # pyright: ignore[reportPrivateUsage]
            source.OFFICIAL_SOURCE_PATH, "TERMINAL_OFFICIAL_EVALUATOR"
        )
        if (
            current != self.evaluator_bytes
            or _verified_evaluate(self.module, current) is not self._evaluate
        ):
            raise OfficialEvaluatorBindingError("OFFICIAL_RECOUNT_BINDING_CHANGED")

    def __call__(self, portfolio: Sequence[Sequence[int]]) -> int:
        self.validate()
        result = self._evaluate(portfolio, pool_size=49, draw_size=6, outright_matches=3)
        count = result.official_any_prize_outcome_count
        if (
            type(count) is not int
            or result.main_draw_count != 13_983_816
            or result.special_count != 43
            or not 0 <= count <= 601_304_088
        ):
            raise OfficialEvaluatorBindingError("OFFICIAL_RECOUNT_OUTCOME_SPACE_MISMATCH")
        self.validate()
        return count

    def result_identity(self) -> dict[str, Any]:
        self.validate()
        return {
            "interface": "pinned_official_evaluator",
            "official_evaluator_module": source.OFFICIAL_IMPORT_NAME,
            "official_evaluator_source_path": str(source.OFFICIAL_SOURCE_PATH),
            "official_evaluator_callable": OFFICIAL_CALLABLE,
            "official_evaluator_executed": True,
            "official_universe_enumerated": True,
            "real_canonical_recount": "COMPLETED",
        }


_BINDING_CALL = OfficialRecountBinding.__call__
_BINDING_VALIDATE = OfficialRecountBinding.validate


def require_official_binding(value: object) -> OfficialRecountBinding:
    if (
        type(value) is not OfficialRecountBinding
        or OfficialRecountBinding.__call__ is not _BINDING_CALL
        or OfficialRecountBinding.validate is not _BINDING_VALIDATE
    ):
        raise OfficialEvaluatorBindingError("ARBITRARY_TERMINAL_RECOUNT_REJECTED")
    value.validate()
    return value


def load_official_recount() -> OfficialRecountBinding:
    """Import verified definitions only; constructing this binding runs no recount."""

    data = source._stable_bytes(  # pyright: ignore[reportPrivateUsage]
        source.OFFICIAL_SOURCE_PATH, "TERMINAL_OFFICIAL_EVALUATOR"
    )
    module, _path, _digest, _created = source._load_verified_module(  # pyright: ignore[reportPrivateUsage]
        source.OFFICIAL_IMPORT_NAME,
        source.OFFICIAL_SOURCE_PATH,
        source.OFFICIAL_SOURCE_PATH,
        source.OFFICIAL_SOURCE_SHA256,
        "TERMINAL_OFFICIAL_EVALUATOR",
    )
    return require_official_binding(
        OfficialRecountBinding(module, data, _verified_evaluate(module, data))
    )
