"""LCJ-1: LottoLab Canonical JSON, revision 1.

A pinned, deterministic byte serialization for evidence-contract documents.
Every embedded and referenced-file hash in ``lottolab.evidence`` is computed
over LCJ-1 canonical bytes so that hashing is reproducible across producers,
platforms, and Python versions.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from typing import Any, cast

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

#: Largest magnitude integer LCJ-1 allows (JavaScript's safe-integer bound).
MAX_SAFE_INTEGER = 9007199254740991


class CanonicalizationError(ValueError):
    """A value, or object key, violates the LCJ-1 canonical value domain."""


def _check_key(key: object, *, path: str) -> str:
    if not isinstance(key, str):
        raise CanonicalizationError(
            f"{path}: object key must be a string, got {type(key).__name__}"
        )
    if not key.isascii():
        raise CanonicalizationError(f"{path}: object key {key!r} must be ASCII")
    if _KEY_PATTERN.fullmatch(key) is None:
        raise CanonicalizationError(f"{path}: object key {key!r} violates ^[a-z][a-z0-9_]*$")
    return key


def _check_value(value: Any, *, path: str) -> None:
    # bool is an int subclass in Python; check it first so booleans are never
    # mistaken for LCJ-1 integers.
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise CanonicalizationError(
                f"{path}: integer {value} exceeds the LCJ-1 magnitude bound"
            )
        return
    if isinstance(value, str):
        return
    if isinstance(value, list | tuple):
        items = cast(Sequence[Any], value)
        for index, item in enumerate(items):
            _check_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        mapping = cast(dict[Any, Any], value)
        seen: set[str] = set()
        for raw_key, item in mapping.items():
            key = _check_key(raw_key, path=path)
            if key in seen:
                raise CanonicalizationError(f"{path}: duplicate object key {key!r}")
            seen.add(key)
            _check_value(item, path=f"{path}.{key}")
        return
    if value is None:
        raise CanonicalizationError(f"{path}: JSON null is forbidden in LCJ-1")
    if isinstance(value, float):
        raise CanonicalizationError(
            f"{path}: binary floats (including NaN/Infinity) are forbidden in LCJ-1"
        )
    raise CanonicalizationError(f"{path}: unsupported LCJ-1 value type {type(value).__name__}")


def validate_value_domain(value: Any) -> None:
    """Raise ``CanonicalizationError`` if any part of ``value`` is outside LCJ-1's domain.

    Accepts Python tuples in addition to lists (both canonicalize to JSON
    arrays) so producers may pass immutable model data directly.
    """

    _check_value(value, path="$")


def canonical_bytes(value: Any) -> bytes:
    """Return the LCJ-1 canonical UTF-8 byte serialization of ``value``.

    Raises ``CanonicalizationError`` first if ``value`` leaves the allowed
    domain (object/array/string/integer/boolean only).
    """

    validate_value_domain(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_file_bytes(value: Any) -> bytes:
    """Canonical bytes for a *committed* file: canonical bytes plus one trailing LF."""

    return canonical_bytes(value) + b"\n"


def canonical_bytes_excluding_keys(value: dict[str, Any], *excluded_keys: str) -> bytes:
    """Canonical bytes of a top-level mapping with the given keys removed.

    Used for self-key-removed tree hashing: a document embeds a hash of its
    own canonical bytes computed with the hash field itself excluded.
    """

    missing = [key for key in excluded_keys if key not in value]
    if missing:
        raise CanonicalizationError(f"expected top-level key(s) {missing!r} to self-hash-exclude")
    reduced = {key: item for key, item in value.items() if key not in excluded_keys}
    return canonical_bytes(reduced)


def sha256_hex(data: bytes) -> str:
    """Lowercase hex SHA-256 digest of raw bytes."""

    return hashlib.sha256(data).hexdigest()


def self_key_removed_sha256(value: dict[str, Any], *excluded_keys: str) -> str:
    """SHA-256 of ``value``'s canonical bytes with ``excluded_keys`` removed."""

    return sha256_hex(canonical_bytes_excluding_keys(value, *excluded_keys))


def loads_canonical(raw: bytes | str) -> Any:
    """Parse JSON text/bytes, rejecting duplicate object keys, and check the LCJ-1 domain.

    Standard ``json.loads`` silently keeps the *last* value for a duplicate
    object key and, by default, accepts the non-standard ``NaN``/``Infinity``
    constants as ``float``. Both are rejected here: duplicates at parse time,
    non-domain values (including those floats) via :func:`validate_value_domain`.
    """

    def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise CanonicalizationError(f"$: duplicate object key {key!r} in parsed JSON")
            result[key] = item
        return result

    value = json.loads(raw, object_pairs_hook=_reject_duplicates)
    validate_value_domain(value)
    return value
