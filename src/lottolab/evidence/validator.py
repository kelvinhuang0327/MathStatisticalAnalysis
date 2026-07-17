"""Semantic validation for LottoLab evidence-contract documents.

Contract Part 10, layer 3: canonicalization, hash recomputation, causality
arithmetic, hit recomputation, dataset cross-checks, definition-path
lookup, and trust classification. Layer 2 (``lottolab.evidence.models``)
only enforces structural shape; everything here assumes a document already
parsed successfully as a Pydantic model.

Definition-path containment is fail-closed and staged so that a lexically
invalid, protected-by-name, or wrong-root-by-name path is rejected with
*zero* filesystem access (no open/stat/hash/read) — see
``resolve_definition_path``. Only a path that survives every string-only
check is ever resolved against disk, and even then resolution never reads
the target file's content (that happens separately, only after containment
succeeds).
"""

from __future__ import annotations

import os
import stat
import subprocess
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from lottolab.domain.lottery_rules import LOTTERY_RULE_CONTRACTS, resolve_lottery_rule_contract
from lottolab.evidence import canonical_json
from lottolab.evidence.canonical_json import CanonicalizationError
from lottolab.evidence.models import (
    DatasetProvenanceKind,
    DatasetSnapshot,
    DrawEntry,
    DrawRef,
    EvaluationProtocol,
    EvidenceStatus,
    EvidenceTrustClass,
    FindingCategory,
    FormulaStatus,
    HashVerificationState,
    MetricDefinition,
    MetricValueStatus,
    ParameterSelectionMode,
    PolicyStatus,
    PolicyTrustClass,
    RankingPolicy,
    RuleParameters,
    SampleUnit,
    StrategyEvaluationEvidence,
)

#: Repository-relative locations the validator must never open, stat, hash, or
#: read, regardless of what an input document declares.
PROTECTED_RELATIVE_PATHS: tuple[str, ...] = ("docs/ownerinit.md", ".local")

#: Allowed definition-path roots. SYNTHETIC_TEST_ONLY evidence may additionally
#: reference SYNTHETIC_ADDITIONAL_ROOTS.
CANONICAL_DRAFT_ALLOWED_ROOTS: tuple[str, ...] = ("contracts/evidence",)
SYNTHETIC_ADDITIONAL_ROOTS: tuple[str, ...] = ("tests/fixtures/evidence",)

#: The provenance boundary admits only these read-only local Git operations.
#: ``_run_read_only_git`` also disables lazy object fetching and optional locks.
_READ_ONLY_GIT_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "cat-file",
        "merge-base",
        "rev-parse",
    }
)

_GIT_OID_HEX_DIGITS = frozenset("0123456789abcdef")
_MAX_ALTERNATES_FILE_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class Finding:
    category: FindingCategory
    code: str
    pointer: str
    message: str


@dataclass(frozen=True, slots=True)
class HashCheck:
    pointer: str
    state: HashVerificationState


@dataclass(frozen=True, slots=True)
class ValidationReport:
    schema_valid: bool
    findings: tuple[Finding, ...]
    hash_checks: tuple[HashCheck, ...]
    trust_classification: EvidenceTrustClass | PolicyTrustClass | None
    structurally_valid: bool
    canonical_gate_passed: bool


class DefinitionPathRejected(Exception):
    """Raised by resolve_definition_path; carries the rejection Finding."""

    def __init__(self, finding: Finding) -> None:
        self.finding = finding
        super().__init__(finding.message)


# --------------------------------------------------------------------------
# Definition-path containment (fail-closed, staged; see module docstring)
# --------------------------------------------------------------------------


def _lexical_check(raw_path: str) -> str | None:
    if not raw_path:
        return "definition path must not be empty"
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in raw_path):
        return "definition path must not contain control characters"
    if raw_path.startswith("/"):
        return "definition path must not be absolute"
    if "\\" in raw_path:
        return "definition path must not contain a backslash"
    if len(raw_path) >= 2 and raw_path[1] == ":" and raw_path[0].isalpha():
        return "definition path must not contain a drive prefix"
    segments = raw_path.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        return "definition path must not contain empty, '.', or '..' segments"
    return None


def _is_protected(relative_posix: str) -> bool:
    for protected in PROTECTED_RELATIVE_PATHS:
        if relative_posix == protected or relative_posix.startswith(protected + "/"):
            return True
    return False


def _allowed_roots_for(evidence_status: EvidenceStatus) -> tuple[str, ...]:
    if evidence_status is EvidenceStatus.SYNTHETIC_TEST_ONLY:
        return CANONICAL_DRAFT_ALLOWED_ROOTS + SYNTHETIC_ADDITIONAL_ROOTS
    return CANONICAL_DRAFT_ALLOWED_ROOTS


def _is_within_allowed_roots(relative_posix: str, allowed_roots: tuple[str, ...]) -> bool:
    return any(
        relative_posix == root or relative_posix.startswith(root + "/") for root in allowed_roots
    )


def _resolution_failure(pointer: str) -> DefinitionPathRejected:
    return DefinitionPathRejected(
        Finding(
            FindingCategory.SEMANTIC_FAILURE,
            "DEFINITION_PATH_RESOLUTION_FAILED",
            pointer,
            "definition path could not be resolved safely",
        )
    )


def resolve_definition_path(
    raw_path: str,
    *,
    repo_root: Path,
    evidence_status: EvidenceStatus,
    pointer: str,
) -> Path:
    """Resolve a declared ``*_definition_path`` under fail-closed containment.

    Order: (1) lexical/path-form checks, (2) protected-path and allowed-root
    checks by name, (3) only then a filesystem resolve() to catch symlink
    escapes, re-checked against the same protected/allowed-root rules. Steps
    1-2 touch no filesystem path at all. Step 3 necessarily stats the path's
    own components to resolve symlinks (that is what "after symlink
    resolution" requires) but never opens/reads/hashes the target's content.
    """

    lexical_error = _lexical_check(raw_path)
    if lexical_error is not None:
        raise DefinitionPathRejected(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DEFINITION_PATH_LEXICALLY_INVALID",
                pointer,
                lexical_error,
            )
        )

    if _is_protected(raw_path):
        raise DefinitionPathRejected(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DEFINITION_PATH_PROTECTED",
                pointer,
                "definition path names a protected repository location",
            )
        )

    allowed_roots = _allowed_roots_for(evidence_status)
    if not _is_within_allowed_roots(raw_path, allowed_roots):
        raise DefinitionPathRejected(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DEFINITION_PATH_OUTSIDE_ALLOWED_ROOT",
                pointer,
                "definition path is outside the allowed root for this evidence status",
            )
        )

    try:
        resolved_repo_root = repo_root.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise _resolution_failure(pointer) from exc
    unresolved_candidate = resolved_repo_root / raw_path
    try:
        candidate = unresolved_candidate.resolve(strict=True)
    except FileNotFoundError:
        try:
            candidate = unresolved_candidate.resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            raise _resolution_failure(pointer) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise _resolution_failure(pointer) from exc
    if candidate != resolved_repo_root and resolved_repo_root not in candidate.parents:
        raise DefinitionPathRejected(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DEFINITION_PATH_ESCAPES_REPO",
                pointer,
                "definition path escapes the repository root after symlink resolution",
            )
        )

    try:
        post_relative = candidate.relative_to(resolved_repo_root).as_posix()
    except (OSError, RuntimeError, ValueError) as exc:
        raise _resolution_failure(pointer) from exc
    if _is_protected(post_relative) or not _is_within_allowed_roots(post_relative, allowed_roots):
        raise DefinitionPathRejected(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DEFINITION_PATH_ESCAPES_ALLOWED_ROOT",
                pointer,
                "definition path resolves outside its allowed root or into a protected location",
            )
        )

    return candidate


def hash_referenced_file(resolved_path: Path) -> str | None:
    """SHA-256 of committed file bytes, or None if unreadable (NOT_VERIFIABLE)."""

    try:
        data = resolved_path.read_bytes()
    except OSError:
        return None
    return canonical_json.sha256_hex(data)


def _is_full_git_oid(value: str) -> bool:
    return len(value) == 40 and all(character in _GIT_OID_HEX_DIGITS for character in value)


def _is_validated_blob_spec(value: str) -> bool:
    oid, separator, raw_path = value.partition(":")
    if separator != ":" or not _is_full_git_oid(oid) or _lexical_check(raw_path) is not None:
        return False
    if _is_protected(raw_path):
        return False
    return _is_within_allowed_roots(
        raw_path,
        CANONICAL_DRAFT_ALLOWED_ROOTS + SYNTHETIC_ADDITIONAL_ROOTS,
    )


def _is_exact_read_only_git_argv(args: tuple[str, ...]) -> bool:
    if args in {
        ("rev-parse", "--show-toplevel"),
        ("rev-parse", "--git-common-dir"),
    }:
        return True
    if len(args) == 3 and args[:2] == ("cat-file", "-t"):
        return _is_full_git_oid(args[2]) or _is_validated_blob_spec(args[2])
    if len(args) == 3 and args[:2] == ("cat-file", "blob"):
        return _is_validated_blob_spec(args[2])
    return (
        len(args) == 4
        and args[:2] == ("merge-base", "--is-ancestor")
        and _is_full_git_oid(args[2])
        and args[3] == "HEAD"
    )


def _run_read_only_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes] | None:
    """Run one allowlisted, local-only Git query without shell or repository mutation."""

    if not _is_exact_read_only_git_argv(args):
        raise ValueError("Git provenance query is outside the exact read-only allowlist")

    env = dict(os.environ)
    repository_redirecting_variables = {
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_CEILING_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_NAMESPACE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_REPLACE_REF_BASE",
        "GIT_SHALLOW_FILE",
        "GIT_WORK_TREE",
    }
    for name in tuple(env):
        if (
            name in repository_redirecting_variables
            or name.startswith("GIT_TRACE")
            or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
        ):
            env.pop(name)
    env.pop("GIT_CONFIG_COUNT", None)
    env.update(
        {
            "GIT_GRAFT_FILE": os.devnull,
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            shell=False,
            env=env,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _alternate_configuration_file_is_unsafe(path: Path) -> bool:
    try:
        path_status = os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError:
        return True

    if not stat.S_ISREG(path_status.st_mode) or path_status.st_size > _MAX_ALTERNATES_FILE_BYTES:
        return True

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return True

    try:
        opened_status = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_status.st_mode)
            or opened_status.st_dev != path_status.st_dev
            or opened_status.st_ino != path_status.st_ino
        ):
            return True

        content = bytearray()
        while True:
            chunk = os.read(descriptor, 8192)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > _MAX_ALTERNATES_FILE_BYTES:
                return True

        final_status = os.fstat(descriptor)
        if (
            final_status.st_dev != opened_status.st_dev
            or final_status.st_ino != opened_status.st_ino
            or final_status.st_size != len(content)
            or final_status.st_mtime_ns != opened_status.st_mtime_ns
        ):
            return True
    except OSError:
        return True
    finally:
        with suppress(OSError):
            os.close(descriptor)

    try:
        text = bytes(content).decode("utf-8")
    except UnicodeDecodeError:
        return True
    return any(character not in " \t\n" for character in text)


def _repository_has_unsafe_alternate_object_database(repo_root: Path) -> bool:
    common_dir_query = _run_read_only_git(repo_root, "rev-parse", "--git-common-dir")
    if common_dir_query is None or common_dir_query.returncode != 0:
        return True
    try:
        common_dir_output = common_dir_query.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return True
    if not common_dir_output.endswith("\n") or common_dir_output.count("\n") != 1:
        return True

    raw_common_dir = common_dir_output[:-1]
    if not raw_common_dir or any(
        ord(character) < 0x20 or ord(character) == 0x7F for character in raw_common_dir
    ):
        return True

    unresolved_common_dir = Path(raw_common_dir)
    if not unresolved_common_dir.is_absolute():
        unresolved_common_dir = repo_root / unresolved_common_dir
    try:
        common_dir = unresolved_common_dir.resolve(strict=True)
        common_dir_status = os.stat(common_dir)
    except (OSError, RuntimeError, ValueError):
        return True
    if not stat.S_ISDIR(common_dir_status.st_mode):
        return True

    alternates_info = common_dir / "objects" / "info"
    return any(
        _alternate_configuration_file_is_unsafe(alternates_info / filename)
        for filename in ("alternates", "http-alternates")
    )


# --------------------------------------------------------------------------
# Hashing helpers
# --------------------------------------------------------------------------


def recompute_self_hash(model: BaseModel, *, excluded_key: str) -> str:
    dumped = model.model_dump(mode="json", exclude_none=True)
    return canonical_json.self_key_removed_sha256(dumped, excluded_key)


def verify_hash(declared: str, recomputed: str | None) -> HashVerificationState:
    if recomputed is None:
        return HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT
    if declared == recomputed:
        return HashVerificationState.VERIFIED_MATCH
    return HashVerificationState.VERIFIED_MISMATCH


def _decimal_matches_scale(value: str, scale: int) -> bool:
    if scale == 0:
        return "." not in value
    if "." not in value:
        return False
    fractional = value.split(".", 1)[1]
    return len(fractional) == scale


def _pydantic_errors_to_findings(exc: ValidationError) -> list[Finding]:
    findings: list[Finding] = []
    for error in exc.errors():
        pointer = "/" + "/".join(str(part) for part in error["loc"])
        findings.append(
            Finding(
                FindingCategory.SCHEMA_FAILURE, "SCHEMA_VALIDATION_ERROR", pointer, error["msg"]
            )
        )
    return findings


# --------------------------------------------------------------------------
# Number-set validation shared by dataset draws, actual outcomes, and tickets
# --------------------------------------------------------------------------


def _check_numbers_against_rule(
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
    rule: RuleParameters,
    *,
    pointer_prefix: str,
) -> list[Finding]:
    findings: list[Finding] = []

    if len(main_numbers) != rule.main_number_count:
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "MAIN_NUMBER_COUNT_MISMATCH",
                f"{pointer_prefix}/main_numbers",
                f"expected {rule.main_number_count} main numbers, got {len(main_numbers)}",
            )
        )
    else:
        if list(main_numbers) != sorted(main_numbers):
            findings.append(
                Finding(
                    FindingCategory.SEMANTIC_FAILURE,
                    "MAIN_NUMBERS_NOT_ASCENDING",
                    f"{pointer_prefix}/main_numbers",
                    "main_numbers must be canonical ascending order",
                )
            )
        if rule.main_numbers_unique and len(set(main_numbers)) != len(main_numbers):
            findings.append(
                Finding(
                    FindingCategory.SEMANTIC_FAILURE,
                    "MAIN_NUMBERS_NOT_UNIQUE",
                    f"{pointer_prefix}/main_numbers",
                    "main_numbers must be unique under this rule contract",
                )
            )
        if any(n < rule.main_number_min or n > rule.main_number_max for n in main_numbers):
            findings.append(
                Finding(
                    FindingCategory.SEMANTIC_FAILURE,
                    "MAIN_NUMBERS_OUT_OF_RANGE",
                    f"{pointer_prefix}/main_numbers",
                    f"main_numbers must lie within [{rule.main_number_min}, "
                    f"{rule.main_number_max}]",
                )
            )

    if len(special_numbers) != rule.special_number_count:
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "SPECIAL_NUMBER_COUNT_MISMATCH",
                f"{pointer_prefix}/special_numbers",
                f"expected {rule.special_number_count} special numbers, got {len(special_numbers)}",
            )
        )
    else:
        if list(special_numbers) != sorted(special_numbers):
            findings.append(
                Finding(
                    FindingCategory.SEMANTIC_FAILURE,
                    "SPECIAL_NUMBERS_NOT_ASCENDING",
                    f"{pointer_prefix}/special_numbers",
                    "special_numbers must be canonical ascending order",
                )
            )
        if rule.special_numbers_unique and len(set(special_numbers)) != len(special_numbers):
            findings.append(
                Finding(
                    FindingCategory.SEMANTIC_FAILURE,
                    "SPECIAL_NUMBERS_NOT_UNIQUE",
                    f"{pointer_prefix}/special_numbers",
                    "special_numbers must be unique under this rule contract",
                )
            )
        if any(n < rule.special_number_min or n > rule.special_number_max for n in special_numbers):
            findings.append(
                Finding(
                    FindingCategory.SEMANTIC_FAILURE,
                    "SPECIAL_NUMBERS_OUT_OF_RANGE",
                    f"{pointer_prefix}/special_numbers",
                    f"special_numbers must lie within [{rule.special_number_min}, "
                    f"{rule.special_number_max}]",
                )
            )

    if not rule.main_special_overlap_allowed and set(main_numbers) & set(special_numbers):
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "MAIN_SPECIAL_OVERLAP_NOT_ALLOWED",
                pointer_prefix,
                "main and special numbers must not overlap under this rule contract",
            )
        )

    return findings


# --------------------------------------------------------------------------
# Dataset snapshot validation
# --------------------------------------------------------------------------


def load_dataset_snapshot(path: Path) -> tuple[DatasetSnapshot | None, list[Finding]]:
    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return None, [
            Finding(
                FindingCategory.SCHEMA_FAILURE,
                "DATASET_FILE_UNREADABLE",
                "/",
                "dataset snapshot file could not be read",
            )
        ]
    try:
        raw_value = canonical_json.loads_canonical(raw_bytes)
    except CanonicalizationError as exc:
        return None, [Finding(FindingCategory.SCHEMA_FAILURE, "DATASET_NOT_LCJ1", "/", str(exc))]
    try:
        snapshot = DatasetSnapshot.model_validate(raw_value)
    except ValidationError as exc:
        return None, _pydantic_errors_to_findings(exc)
    return snapshot, []


def validate_dataset_snapshot(snapshot: DatasetSnapshot) -> tuple[list[Finding], list[HashCheck]]:
    findings: list[Finding] = []
    hash_checks: list[HashCheck] = []

    recomputed = recompute_self_hash(snapshot, excluded_key="dataset_sha256")
    state = verify_hash(snapshot.dataset_sha256, recomputed)
    hash_checks.append(HashCheck("/dataset_sha256", state))
    if state is HashVerificationState.VERIFIED_MISMATCH:
        findings.append(
            Finding(
                FindingCategory.HASH_MISMATCH,
                "DATASET_HASH_MISMATCH",
                "/dataset_sha256",
                "declared dataset_sha256 does not match recomputed content hash",
            )
        )

    rb_recomputed = recompute_self_hash(
        snapshot.rule_binding, excluded_key="rule_parameters_sha256"
    )
    rb_state = verify_hash(snapshot.rule_binding.rule_parameters_sha256, rb_recomputed)
    hash_checks.append(HashCheck("/rule_binding/rule_parameters_sha256", rb_state))
    if rb_state is HashVerificationState.VERIFIED_MISMATCH:
        findings.append(
            Finding(
                FindingCategory.HASH_MISMATCH,
                "RULE_PARAMETERS_HASH_MISMATCH",
                "/rule_binding/rule_parameters_sha256",
                "declared rule_parameters_sha256 does not match recomputed content hash",
            )
        )

    for index, draw in enumerate(snapshot.draws):
        if draw.draw_sequence != index:
            findings.append(
                Finding(
                    FindingCategory.SEMANTIC_FAILURE,
                    "DRAW_SEQUENCE_NOT_CONTIGUOUS",
                    f"/draws/{index}/draw_sequence",
                    "draw_sequence must be contiguous starting at zero",
                )
            )
            break

    draw_ids = [draw.draw_id for draw in snapshot.draws]
    duplicate_ids = sorted({draw_id for draw_id, count in Counter(draw_ids).items() if count > 1})
    if duplicate_ids:
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DUPLICATE_DRAW_ID",
                "/draws",
                f"duplicate draw_id(s): {duplicate_ids}",
            )
        )

    for index in range(1, len(snapshot.draws)):
        if snapshot.draws[index].draw_date < snapshot.draws[index - 1].draw_date:
            findings.append(
                Finding(
                    FindingCategory.SEMANTIC_FAILURE,
                    "DRAW_DATE_DECREASING",
                    f"/draws/{index}/draw_date",
                    "draw_date must be non-decreasing across draws",
                )
            )
            break

    for index, draw in enumerate(snapshot.draws):
        findings.extend(
            _check_numbers_against_rule(
                draw.main_numbers,
                draw.special_numbers,
                snapshot.rule_binding,
                pointer_prefix=f"/draws/{index}",
            )
        )

    return findings, hash_checks


def _dataset_snapshot_pointer(pointer: str) -> str:
    return "/dataset_snapshot" if pointer == "/" else f"/dataset_snapshot{pointer}"


def _prefix_dataset_findings(findings: list[Finding]) -> list[Finding]:
    return [
        Finding(
            finding.category,
            finding.code,
            _dataset_snapshot_pointer(finding.pointer),
            finding.message,
        )
        for finding in findings
    ]


_DATASET_PROVENANCE_KIND_POINTER = "/dataset_snapshot/source_provenance/kind"
_DATASET_SOURCE_PATH_POINTER = "/dataset_snapshot/source_provenance/source_definition_path"
_DATASET_SOURCE_OID_POINTER = "/dataset_snapshot/source_provenance/source_git_oid"
_DATASET_SOURCE_HASH_POINTER = "/dataset_snapshot/source_provenance/source_file_sha256"


def _dataset_source_not_verifiable(
    code: str, *, pointer: str, message: str
) -> tuple[list[Finding], list[HashCheck], bool]:
    return (
        [Finding(FindingCategory.UNVERIFIED_PROVENANCE, code, pointer, message)],
        [
            HashCheck(
                _DATASET_SOURCE_HASH_POINTER,
                HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT,
            )
        ],
        True,
    )


def verify_dataset_provenance(
    dataset: DatasetSnapshot,
    *,
    repo_root: Path,
    evidence_status: EvidenceStatus,
) -> tuple[list[Finding], list[HashCheck], bool]:
    """Verify dataset provenance and return findings, hash checks, and unverified state.

    ``LOCAL_COMMITTED_FILE`` proves only that the declared path at the exact
    reachable commit has the declared raw-byte SHA-256. It deliberately does
    not claim that those bytes were normalized into the snapshot correctly.
    """

    provenance = dataset.source_provenance
    if provenance.kind is DatasetProvenanceKind.SYNTHETIC:
        if evidence_status is EvidenceStatus.SYNTHETIC_TEST_ONLY:
            return [], [], False
        return (
            [
                Finding(
                    FindingCategory.AUTHORITY_FAILURE,
                    "SYNTHETIC_DATASET_REQUIRES_SYNTHETIC_EVIDENCE",
                    _DATASET_PROVENANCE_KIND_POINTER,
                    "a synthetic dataset may support only SYNTHETIC_TEST_ONLY evidence",
                )
            ],
            [],
            True,
        )

    if provenance.kind is DatasetProvenanceKind.EXTERNAL_DECLARED:
        return (
            [
                Finding(
                    FindingCategory.UNVERIFIED_PROVENANCE,
                    "DATASET_EXTERNAL_DECLARED_UNVERIFIED",
                    _DATASET_PROVENANCE_KIND_POINTER,
                    "externally declared dataset provenance is not independently verifiable",
                )
            ],
            [],
            True,
        )

    raw_path = provenance.source_definition_path
    source_git_oid = provenance.source_git_oid
    declared_source_hash = provenance.source_file_sha256
    if raw_path is None or source_git_oid is None or declared_source_hash is None:
        return _dataset_source_not_verifiable(
            "DATASET_SOURCE_BLOB_UNAVAILABLE",
            pointer=_DATASET_SOURCE_PATH_POINTER,
            message="the declared historical source blob is unavailable",
        )

    # Reuse the definition-path containment system before any Git object bytes
    # are requested. The resolved working-tree path is intentionally not read.
    try:
        resolve_definition_path(
            raw_path,
            repo_root=repo_root,
            evidence_status=evidence_status,
            pointer=_DATASET_SOURCE_PATH_POINTER,
        )
    except DefinitionPathRejected as exc:
        return (
            [exc.finding],
            [
                HashCheck(
                    _DATASET_SOURCE_HASH_POINTER,
                    HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT,
                )
            ],
            True,
        )

    top_level = _run_read_only_git(repo_root, "rev-parse", "--show-toplevel")
    if top_level is None or top_level.returncode != 0:
        return _dataset_source_not_verifiable(
            "DATASET_SOURCE_GIT_REPOSITORY_UNAVAILABLE",
            pointer=_DATASET_SOURCE_OID_POINTER,
            message="the supplied repository is unavailable for local provenance verification",
        )
    try:
        top_level_text = top_level.stdout.decode("utf-8").strip()
        resolved_top_level = Path(top_level_text).resolve() if top_level_text else None
        resolved_supplied_root = repo_root.resolve()
    except (OSError, RuntimeError, UnicodeDecodeError, ValueError):
        resolved_top_level = None
        resolved_supplied_root = None
    if resolved_top_level is None or resolved_top_level != resolved_supplied_root:
        return _dataset_source_not_verifiable(
            "DATASET_SOURCE_GIT_REPOSITORY_UNAVAILABLE",
            pointer=_DATASET_SOURCE_OID_POINTER,
            message="the supplied repository is unavailable for local provenance verification",
        )

    if _repository_has_unsafe_alternate_object_database(repo_root):
        return _dataset_source_not_verifiable(
            "DATASET_SOURCE_ALTERNATE_OBJECT_DATABASE_UNSAFE",
            pointer=_DATASET_SOURCE_OID_POINTER,
            message="repository alternate object database configuration is unsafe",
        )

    object_type = _run_read_only_git(repo_root, "cat-file", "-t", source_git_oid)
    if (
        object_type is None
        or object_type.returncode != 0
        or object_type.stdout.strip() != b"commit"
    ):
        return _dataset_source_not_verifiable(
            "DATASET_SOURCE_GIT_OID_UNVERIFIED",
            pointer=_DATASET_SOURCE_OID_POINTER,
            message="the declared source Git object is not a verifiable commit",
        )

    ancestry = _run_read_only_git(
        repo_root, "merge-base", "--is-ancestor", source_git_oid, "HEAD"
    )
    if ancestry is None or ancestry.returncode not in (0, 1):
        return _dataset_source_not_verifiable(
            "DATASET_SOURCE_GIT_OID_UNVERIFIED",
            pointer=_DATASET_SOURCE_OID_POINTER,
            message="the declared source Git commit cannot be verified against HEAD",
        )
    if ancestry.returncode == 1:
        return _dataset_source_not_verifiable(
            "DATASET_SOURCE_GIT_OID_NOT_ANCESTOR",
            pointer=_DATASET_SOURCE_OID_POINTER,
            message="the declared source Git commit is not an ancestor of HEAD",
        )

    blob_spec = f"{source_git_oid}:{raw_path}"
    blob_type = _run_read_only_git(repo_root, "cat-file", "-t", blob_spec)
    if blob_type is None or blob_type.returncode != 0 or blob_type.stdout.strip() != b"blob":
        return _dataset_source_not_verifiable(
            "DATASET_SOURCE_BLOB_UNAVAILABLE",
            pointer=_DATASET_SOURCE_PATH_POINTER,
            message="the declared historical source blob is unavailable",
        )

    blob = _run_read_only_git(repo_root, "cat-file", "blob", blob_spec)
    if blob is None or blob.returncode != 0:
        return _dataset_source_not_verifiable(
            "DATASET_SOURCE_BLOB_UNAVAILABLE",
            pointer=_DATASET_SOURCE_PATH_POINTER,
            message="the declared historical source bytes are unavailable",
        )

    recomputed_source_hash = canonical_json.sha256_hex(blob.stdout)
    state = verify_hash(declared_source_hash, recomputed_source_hash)
    hash_checks = [HashCheck(_DATASET_SOURCE_HASH_POINTER, state)]
    if state is HashVerificationState.VERIFIED_MISMATCH:
        return (
            [
                Finding(
                    FindingCategory.HASH_MISMATCH,
                    "DATASET_SOURCE_FILE_HASH_MISMATCH",
                    _DATASET_SOURCE_HASH_POINTER,
                    "declared source_file_sha256 does not match the historical Git blob bytes",
                )
            ],
            hash_checks,
            True,
        )
    return [], hash_checks, False


# --------------------------------------------------------------------------
# Evidence artifact validation
# --------------------------------------------------------------------------


def load_evidence(path: Path) -> tuple[StrategyEvaluationEvidence | None, list[Finding]]:
    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return None, [
            Finding(
                FindingCategory.SCHEMA_FAILURE,
                "EVIDENCE_FILE_UNREADABLE",
                "/",
                "evidence file could not be read",
            )
        ]
    try:
        raw_value = canonical_json.loads_canonical(raw_bytes)
    except CanonicalizationError as exc:
        return None, [Finding(FindingCategory.SCHEMA_FAILURE, "EVIDENCE_NOT_LCJ1", "/", str(exc))]
    try:
        evidence = StrategyEvaluationEvidence.model_validate(raw_value)
    except ValidationError as exc:
        return None, _pydantic_errors_to_findings(exc)
    return evidence, []


def _check_rule_binding_against_domain_contract(
    evidence: StrategyEvaluationEvidence, findings: list[Finding]
) -> bool:
    """Returns True if rule-binding provenance is unverified."""

    lottery_type = evidence.dataset_reference.lottery_type
    contract = resolve_lottery_rule_contract(lottery_type, LOTTERY_RULE_CONTRACTS)
    if contract is None:
        findings.append(
            Finding(
                FindingCategory.UNVERIFIED_PROVENANCE,
                "RULE_CONTRACT_NOT_AUTHORITATIVE",
                "/rule_parameters",
                f"no authoritative committed rule contract for {lottery_type.value}; "
                "rule binding cannot be verified",
            )
        )
        return True

    rp = evidence.rule_parameters
    mismatches = [
        name
        for name, declared, authoritative in (
            ("main_number_count", rp.main_number_count, contract.main_number_count),
            ("main_number_min", rp.main_number_min, contract.main_number_min),
            ("main_number_max", rp.main_number_max, contract.main_number_max),
            ("main_numbers_unique", rp.main_numbers_unique, contract.main_numbers_unique),
            ("special_number_count", rp.special_number_count, contract.special_number_count),
            ("special_number_min", rp.special_number_min, contract.special_number_min),
            ("special_number_max", rp.special_number_max, contract.special_number_max),
            ("special_numbers_unique", rp.special_numbers_unique, contract.special_numbers_unique),
            (
                "main_special_overlap_allowed",
                rp.main_special_overlap_allowed,
                contract.main_special_overlap_allowed,
            ),
        )
        if declared != authoritative
    ]
    if mismatches:
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "RULE_BINDING_MISMATCH",
                "/rule_parameters",
                f"embedded rule parameters do not match the committed domain rule "
                f"contract for {lottery_type.value}: {mismatches}",
            )
        )
    return False


def _check_causality(evidence: StrategyEvaluationEvidence, findings: list[Finding]) -> None:
    windows = evidence.evaluation_windows
    protocol = evidence.evaluation_protocol
    cutoff_sequences: list[int] = []

    for r_index, record in enumerate(evidence.records):
        pointer_prefix = f"/records/{r_index}"
        cutoff_sequences.append(record.cutoff.draw_sequence)

        if record.cutoff.draw_sequence >= record.target.draw_sequence:
            findings.append(
                Finding(
                    FindingCategory.CAUSAL_VIOLATION,
                    "CUTOFF_NOT_BEFORE_TARGET",
                    f"{pointer_prefix}/cutoff",
                    "cutoff sequence must be strictly less than target sequence",
                )
            )

        window = windows.evaluation_window
        if not (window.start_sequence <= record.target.draw_sequence <= window.end_sequence):
            findings.append(
                Finding(
                    FindingCategory.CAUSAL_VIOLATION,
                    "TARGET_OUTSIDE_EVALUATION_WINDOW",
                    f"{pointer_prefix}/target",
                    "target does not lie inside the evaluation window",
                )
            )

        if protocol is EvaluationProtocol.WALK_FORWARD:
            lag = windows.walk_forward_cutoff_lag
            actual_lag = record.target.draw_sequence - record.cutoff.draw_sequence
            if lag is not None and actual_lag != lag:
                findings.append(
                    Finding(
                        FindingCategory.CAUSAL_VIOLATION,
                        "WALK_FORWARD_LAG_MISMATCH",
                        pointer_prefix,
                        f"expected cutoff lag {lag}, got {actual_lag}",
                    )
                )
        else:
            shared = windows.one_shot_cutoff
            if shared is not None:
                if (
                    record.cutoff.draw_id != shared.draw_id
                    or record.cutoff.draw_sequence != shared.draw_sequence
                ):
                    findings.append(
                        Finding(
                            FindingCategory.CAUSAL_VIOLATION,
                            "ONE_SHOT_CUTOFF_NOT_SHARED",
                            f"{pointer_prefix}/cutoff",
                            "every record must share the same one_shot_cutoff",
                        )
                    )
                if record.target.draw_sequence <= shared.draw_sequence:
                    findings.append(
                        Finding(
                            FindingCategory.CAUSAL_VIOLATION,
                            "ONE_SHOT_TARGET_BEFORE_CUTOFF",
                            f"{pointer_prefix}/target",
                            "target must be strictly after the shared one-shot cutoff",
                        )
                    )

    if not cutoff_sequences:
        return

    minimum_cutoff_sequence = min(cutoff_sequences)
    maximum_cutoff_sequence = max(cutoff_sequences)

    if windows.training_window.end_sequence > minimum_cutoff_sequence:
        findings.append(
            Finding(
                FindingCategory.CAUSAL_VIOLATION,
                "TRAINING_WINDOW_AFTER_MINIMUM_CUTOFF",
                "/evaluation_windows/training_window",
                "training window end must not be after the minimum record cutoff",
            )
        )

    if (
        windows.parameter_selection_mode is ParameterSelectionMode.FIXED
        and windows.parameter_selection_window is not None
    ):
        psw = windows.parameter_selection_window
        if psw.end_sequence >= windows.evaluation_window.start_sequence:
            findings.append(
                Finding(
                    FindingCategory.CAUSAL_VIOLATION,
                    "PARAMETER_SELECTION_OVERLAPS_EVALUATION",
                    "/evaluation_windows/parameter_selection_window",
                    "fixed parameter-selection window must end before the evaluation window",
                )
            )
        if psw.end_sequence > minimum_cutoff_sequence:
            findings.append(
                Finding(
                    FindingCategory.CAUSAL_VIOLATION,
                    "PARAMETER_SELECTION_AFTER_MINIMUM_CUTOFF",
                    "/evaluation_windows/parameter_selection_window",
                    "fixed parameter-selection window must end no later than the "
                    "minimum record cutoff",
                )
            )

    declared_max = windows.maximum_data_cutoff
    if declared_max.draw_sequence != maximum_cutoff_sequence:
        findings.append(
            Finding(
                FindingCategory.CAUSAL_VIOLATION,
                "MAXIMUM_CUTOFF_MISMATCH",
                "/evaluation_windows/maximum_data_cutoff",
                f"declared maximum cutoff sequence {declared_max.draw_sequence} does not "
                f"match recomputed maximum {maximum_cutoff_sequence}",
            )
        )


def _check_records(
    evidence: StrategyEvaluationEvidence, findings: list[Finding], hash_checks: list[HashCheck]
) -> None:
    rule = evidence.rule_parameters
    seen_ticket_ids: set[str] = set()

    for r_index, record in enumerate(evidence.records):
        pointer_prefix = f"/records/{r_index}"

        recomputed = recompute_self_hash(record, excluded_key="record_sha256")
        state = verify_hash(record.record_sha256, recomputed)
        hash_checks.append(HashCheck(f"{pointer_prefix}/record_sha256", state))
        if state is HashVerificationState.VERIFIED_MISMATCH:
            findings.append(
                Finding(
                    FindingCategory.HASH_MISMATCH,
                    "RECORD_HASH_MISMATCH",
                    f"{pointer_prefix}/record_sha256",
                    "declared record_sha256 does not match recomputed content hash",
                )
            )

        findings.extend(
            _check_numbers_against_rule(
                record.actual_main_numbers,
                record.actual_special_numbers,
                rule,
                pointer_prefix=f"{pointer_prefix}/actual",
            )
        )

        combos_seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
        previous_sort_key: tuple[tuple[int, ...], tuple[int, ...], str] | None = None
        for t_index, ticket in enumerate(record.tickets):
            t_pointer = f"{pointer_prefix}/tickets/{t_index}"

            if ticket.ticket_id in seen_ticket_ids:
                findings.append(
                    Finding(
                        FindingCategory.SEMANTIC_FAILURE,
                        "DUPLICATE_TICKET_ID",
                        t_pointer,
                        f"duplicate ticket_id {ticket.ticket_id!r}",
                    )
                )
            seen_ticket_ids.add(ticket.ticket_id)

            combo = (ticket.main_numbers, ticket.special_numbers)
            if combo in combos_seen:
                findings.append(
                    Finding(
                        FindingCategory.SEMANTIC_FAILURE,
                        "DUPLICATE_TICKET_COMBINATION",
                        t_pointer,
                        "duplicate ticket number combination within one record",
                    )
                )
            combos_seen.add(combo)

            findings.extend(
                _check_numbers_against_rule(
                    ticket.main_numbers, ticket.special_numbers, rule, pointer_prefix=t_pointer
                )
            )

            sort_key = (ticket.main_numbers, ticket.special_numbers, ticket.ticket_id)
            if previous_sort_key is not None and sort_key < previous_sort_key:
                findings.append(
                    Finding(
                        FindingCategory.SEMANTIC_FAILURE,
                        "TICKET_ORDER_NOT_DETERMINISTIC",
                        t_pointer,
                        "tickets must be ordered by (main_numbers, special_numbers, ticket_id)",
                    )
                )
            previous_sort_key = sort_key

            recomputed_main_hits = len(set(ticket.main_numbers) & set(record.actual_main_numbers))
            if ticket.main_hit_count != recomputed_main_hits:
                findings.append(
                    Finding(
                        FindingCategory.SEMANTIC_FAILURE,
                        "MAIN_HIT_COUNT_MISMATCH",
                        f"{t_pointer}/main_hit_count",
                        f"declared main_hit_count {ticket.main_hit_count} does not match "
                        f"recomputed {recomputed_main_hits}",
                    )
                )

            recomputed_special_overlap = len(
                set(ticket.special_numbers) & set(record.actual_special_numbers)
            )
            expected_special: bool | int = (
                recomputed_special_overlap > 0
                if rule.special_number_count <= 1
                else recomputed_special_overlap
            )
            if (
                type(ticket.special_hit) is not type(expected_special)
                or ticket.special_hit != expected_special
            ):
                findings.append(
                    Finding(
                        FindingCategory.SEMANTIC_FAILURE,
                        "SPECIAL_HIT_MISMATCH",
                        f"{t_pointer}/special_hit",
                        f"declared special_hit {ticket.special_hit!r} does not match "
                        f"recomputed {expected_special!r}",
                    )
                )


def _check_definition_path_and_hash(
    raw_path: str,
    declared_hash: str,
    *,
    evidence_status: EvidenceStatus,
    repo_root: Path,
    pointer: str,
    findings: list[Finding],
    hash_checks: list[HashCheck],
) -> tuple[bytes | None, bool]:
    """Resolve+hash one referenced-file definition path. Returns (raw_bytes, unverified)."""

    try:
        resolved = resolve_definition_path(
            raw_path, repo_root=repo_root, evidence_status=evidence_status, pointer=pointer
        )
    except DefinitionPathRejected as exc:
        findings.append(exc.finding)
        hash_checks.append(HashCheck(pointer, HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT))
        return None, True

    raw_bytes: bytes | None
    try:
        raw_bytes = resolved.read_bytes()
    except OSError:
        raw_bytes = None

    recomputed = canonical_json.sha256_hex(raw_bytes) if raw_bytes is not None else None
    state = verify_hash(declared_hash, recomputed)
    hash_checks.append(HashCheck(pointer, state))
    if state is HashVerificationState.VERIFIED_MISMATCH:
        findings.append(
            Finding(
                FindingCategory.HASH_MISMATCH,
                "REFERENCED_FILE_HASH_MISMATCH",
                pointer,
                "declared hash does not match the committed file bytes",
            )
        )
        return raw_bytes, False
    if state is HashVerificationState.NOT_VERIFIABLE_INPUT_ABSENT:
        return None, True
    return raw_bytes, False


def _check_metric_results(
    evidence: StrategyEvaluationEvidence,
    findings: list[Finding],
    hash_checks: list[HashCheck],
    *,
    repo_root: Path,
) -> bool:
    unverified_any = False
    sample_size_by_unit = {
        SampleUnit.DRAWS: len(evidence.records),
        SampleUnit.TICKETS: sum(len(record.tickets) for record in evidence.records),
    }

    for m_index, result in enumerate(evidence.metric_results):
        pointer_prefix = f"/metric_results/{m_index}"
        raw_bytes, unverified = _check_definition_path_and_hash(
            result.metric_definition_path,
            result.metric_definition_sha256,
            evidence_status=evidence.evidence_status,
            repo_root=repo_root,
            pointer=f"{pointer_prefix}/metric_definition_sha256",
            findings=findings,
            hash_checks=hash_checks,
        )
        unverified_any = unverified_any or unverified
        if raw_bytes is None:
            continue

        try:
            raw_value = canonical_json.loads_canonical(raw_bytes)
            definition = MetricDefinition.model_validate(raw_value)
        except (CanonicalizationError, ValidationError):
            findings.append(
                Finding(
                    FindingCategory.METRIC_DEFINITION_FAILURE,
                    "METRIC_DEFINITION_UNREADABLE",
                    f"{pointer_prefix}/metric_definition_path",
                    "referenced metric definition could not be parsed",
                )
            )
            continue

        if (
            result.metric_id != definition.metric_id
            or result.metric_version != definition.metric_version
        ):
            findings.append(
                Finding(
                    FindingCategory.METRIC_DEFINITION_FAILURE,
                    "METRIC_IDENTITY_MISMATCH",
                    pointer_prefix,
                    "metric_id/metric_version do not match the referenced definition",
                )
            )

        if (
            definition.formula_status is FormulaStatus.RESERVED_UNAVAILABLE
            and result.value_status is MetricValueStatus.VALUE_PRESENT
        ):
            findings.append(
                Finding(
                    FindingCategory.METRIC_DEFINITION_FAILURE,
                    "RESERVED_METRIC_VALUE_PRESENT",
                    pointer_prefix,
                    f"metric {definition.metric_id} is RESERVED_UNAVAILABLE; no result "
                    "may declare VALUE_PRESENT",
                )
            )

        value_scale_ok = result.value is None or _decimal_matches_scale(
            result.value, definition.decimal_scale
        )
        if result.value_status is MetricValueStatus.VALUE_PRESENT and not value_scale_ok:
            findings.append(
                Finding(
                    FindingCategory.METRIC_DEFINITION_FAILURE,
                    "METRIC_VALUE_SCALE_MISMATCH",
                    f"{pointer_prefix}/value",
                    f"value does not match declared decimal_scale {definition.decimal_scale}",
                )
            )

        if result.sample_unit is not definition.sample_unit:
            findings.append(
                Finding(
                    FindingCategory.METRIC_DEFINITION_FAILURE,
                    "METRIC_SAMPLE_UNIT_MISMATCH",
                    f"{pointer_prefix}/sample_unit",
                    "result sample_unit does not match the referenced metric definition",
                )
            )

        if result.aggregation != definition.aggregation:
            findings.append(
                Finding(
                    FindingCategory.METRIC_DEFINITION_FAILURE,
                    "METRIC_AGGREGATION_MISMATCH",
                    f"{pointer_prefix}/aggregation",
                    "result aggregation does not match the referenced metric definition",
                )
            )

        expected_sample_size = sample_size_by_unit[definition.sample_unit]
        if result.sample_size != expected_sample_size:
            findings.append(
                Finding(
                    FindingCategory.METRIC_DEFINITION_FAILURE,
                    "SAMPLE_SIZE_MISMATCH",
                    f"{pointer_prefix}/sample_size",
                    f"sample_size {result.sample_size} does not match recomputed "
                    f"{expected_sample_size}",
                )
            )

    return unverified_any


def _reconcile_draw_ref_with_snapshot(
    reference: DrawRef,
    snapshot_draw: DrawEntry | None,
    *,
    pointer: str,
    missing_code: str,
    inconsistent_code: str,
    reference_name: str,
    findings: list[Finding],
) -> None:
    if snapshot_draw is None:
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                missing_code,
                pointer,
                f"{reference_name} draw_id is not present in the supplied dataset snapshot",
            )
        )
        return

    if (
        reference.draw_sequence != snapshot_draw.draw_sequence
        or reference.draw_date != snapshot_draw.draw_date
    ):
        findings.append(
            Finding(
                FindingCategory.CAUSAL_VIOLATION,
                inconsistent_code,
                pointer,
                f"{reference_name} draw_sequence/draw_date contradict the supplied "
                "dataset snapshot",
            )
        )


def _check_dataset_cross_reference(
    evidence: StrategyEvaluationEvidence, dataset: DatasetSnapshot, findings: list[Finding]
) -> None:
    ref = evidence.dataset_reference

    if ref.dataset_id != dataset.dataset_id or ref.dataset_version != dataset.dataset_version:
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DATASET_IDENTITY_MISMATCH",
                "/dataset_reference",
                "dataset_id/dataset_version do not match the supplied snapshot",
            )
        )
    if ref.dataset_sha256 != dataset.dataset_sha256:
        findings.append(
            Finding(
                FindingCategory.HASH_MISMATCH,
                "DATASET_REFERENCE_HASH_MISMATCH",
                "/dataset_reference/dataset_sha256",
                "declared dataset_sha256 does not match the supplied snapshot",
            )
        )
    if ref.lottery_type != dataset.lottery_type:
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DATASET_LOTTERY_TYPE_MISMATCH",
                "/dataset_reference/lottery_type",
                "lottery_type does not match the supplied snapshot",
            )
        )
    if ref.draw_count != len(dataset.draws):
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DATASET_DRAW_COUNT_MISMATCH",
                "/dataset_reference/draw_count",
                "draw_count does not match the supplied snapshot",
            )
        )

    first, last = dataset.draws[0], dataset.draws[-1]
    if (
        ref.first_draw.draw_id != first.draw_id
        or ref.first_draw.draw_sequence != first.draw_sequence
        or ref.first_draw.draw_date != first.draw_date
    ):
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DATASET_FIRST_DRAW_MISMATCH",
                "/dataset_reference/first_draw",
                "first_draw does not match the supplied snapshot",
            )
        )
    if (
        ref.last_draw.draw_id != last.draw_id
        or ref.last_draw.draw_sequence != last.draw_sequence
        or ref.last_draw.draw_date != last.draw_date
    ):
        findings.append(
            Finding(
                FindingCategory.SEMANTIC_FAILURE,
                "DATASET_LAST_DRAW_MISMATCH",
                "/dataset_reference/last_draw",
                "last_draw does not match the supplied snapshot",
            )
        )

    draws_by_id = {draw.draw_id: draw for draw in dataset.draws}

    maximum_cutoff = evidence.evaluation_windows.maximum_data_cutoff
    _reconcile_draw_ref_with_snapshot(
        maximum_cutoff,
        draws_by_id.get(maximum_cutoff.draw_id),
        pointer="/evaluation_windows/maximum_data_cutoff",
        missing_code="CUTOFF_DRAW_NOT_IN_DATASET",
        inconsistent_code="CUTOFF_REF_INCONSISTENT_WITH_SNAPSHOT",
        reference_name="maximum_data_cutoff",
        findings=findings,
    )

    one_shot_cutoff = evidence.evaluation_windows.one_shot_cutoff
    if one_shot_cutoff is not None:
        _reconcile_draw_ref_with_snapshot(
            one_shot_cutoff,
            draws_by_id.get(one_shot_cutoff.draw_id),
            pointer="/evaluation_windows/one_shot_cutoff",
            missing_code="CUTOFF_DRAW_NOT_IN_DATASET",
            inconsistent_code="CUTOFF_REF_INCONSISTENT_WITH_SNAPSHOT",
            reference_name="one_shot_cutoff",
            findings=findings,
        )

    for r_index, record in enumerate(evidence.records):
        target_draw = draws_by_id.get(record.target.draw_id)
        _reconcile_draw_ref_with_snapshot(
            record.target,
            target_draw,
            pointer=f"/records/{r_index}/target",
            missing_code="TARGET_DRAW_NOT_IN_DATASET",
            inconsistent_code="TARGET_REF_INCONSISTENT_WITH_SNAPSHOT",
            reference_name="target",
            findings=findings,
        )

        cutoff_draw = draws_by_id.get(record.cutoff.draw_id)
        _reconcile_draw_ref_with_snapshot(
            record.cutoff,
            cutoff_draw,
            pointer=f"/records/{r_index}/cutoff",
            missing_code="CUTOFF_DRAW_NOT_IN_DATASET",
            inconsistent_code="CUTOFF_REF_INCONSISTENT_WITH_SNAPSHOT",
            reference_name="cutoff",
            findings=findings,
        )

        if target_draw is not None and (
            tuple(record.actual_main_numbers) != target_draw.main_numbers
            or tuple(record.actual_special_numbers) != target_draw.special_numbers
        ):
            findings.append(
                Finding(
                    FindingCategory.SEMANTIC_FAILURE,
                    "ACTUAL_OUTCOME_INCONSISTENT_WITH_SNAPSHOT",
                    f"/records/{r_index}",
                    "declared actual outcome does not match the supplied dataset snapshot",
                )
            )


def classify_evidence_trust(
    evidence: StrategyEvaluationEvidence,
    *,
    structurally_valid: bool,
    hash_checks: list[HashCheck],
    canonical_registry: frozenset[str],
    unverified_provenance: bool,
    authority_failure: bool,
) -> EvidenceTrustClass:
    if evidence.evidence_status is EvidenceStatus.SYNTHETIC_TEST_ONLY:
        return EvidenceTrustClass.SYNTHETIC
    required_hashes_verified = all(
        hc.state is HashVerificationState.VERIFIED_MATCH for hc in hash_checks
    )
    if (
        evidence.evidence_status is EvidenceStatus.CANONICAL
        and structurally_valid
        and evidence.artifact_content_sha256 in canonical_registry
        and required_hashes_verified
        and not unverified_provenance
        and not authority_failure
    ):
        return EvidenceTrustClass.REGISTERED_CANONICAL
    return EvidenceTrustClass.UNTRUSTED_DECLARED


def validate_evidence_artifact(
    evidence: StrategyEvaluationEvidence,
    *,
    repo_root: Path,
    dataset: DatasetSnapshot | None,
    canonical_registry: frozenset[str] = frozenset(),
) -> ValidationReport:
    findings: list[Finding] = []
    hash_checks: list[HashCheck] = []

    art_recomputed = recompute_self_hash(evidence, excluded_key="artifact_content_sha256")
    art_state = verify_hash(evidence.artifact_content_sha256, art_recomputed)
    hash_checks.append(HashCheck("/artifact_content_sha256", art_state))
    if art_state is HashVerificationState.VERIFIED_MISMATCH:
        findings.append(
            Finding(
                FindingCategory.HASH_MISMATCH,
                "ARTIFACT_CONTENT_HASH_MISMATCH",
                "/artifact_content_sha256",
                "declared artifact_content_sha256 does not match recomputed content hash",
            )
        )

    params_recomputed = canonical_json.sha256_hex(
        canonical_json.canonical_bytes(evidence.parameters)
    )
    params_state = verify_hash(evidence.parameters_sha256, params_recomputed)
    hash_checks.append(HashCheck("/parameters_sha256", params_state))
    if params_state is HashVerificationState.VERIFIED_MISMATCH:
        findings.append(
            Finding(
                FindingCategory.HASH_MISMATCH,
                "PARAMETERS_HASH_MISMATCH",
                "/parameters_sha256",
                "declared parameters_sha256 does not match recomputed content hash",
            )
        )

    rule_recomputed = recompute_self_hash(
        evidence.rule_parameters, excluded_key="rule_parameters_sha256"
    )
    rule_state = verify_hash(evidence.rule_parameters.rule_parameters_sha256, rule_recomputed)
    hash_checks.append(HashCheck("/rule_parameters/rule_parameters_sha256", rule_state))
    if rule_state is HashVerificationState.VERIFIED_MISMATCH:
        findings.append(
            Finding(
                FindingCategory.HASH_MISMATCH,
                "RULE_PARAMETERS_HASH_MISMATCH",
                "/rule_parameters/rule_parameters_sha256",
                "declared rule_parameters_sha256 does not match recomputed content hash",
            )
        )

    rule_unverified = _check_rule_binding_against_domain_contract(evidence, findings)
    _check_records(evidence, findings, hash_checks)
    _check_causality(evidence, findings)

    feature_bytes, feature_unverified = _check_definition_path_and_hash(
        evidence.feature_definition_path,
        evidence.feature_definition_sha256,
        evidence_status=evidence.evidence_status,
        repo_root=repo_root,
        pointer="/feature_definition_sha256",
        findings=findings,
        hash_checks=hash_checks,
    )
    del feature_bytes  # foundation task does not interpret feature-definition content

    metric_unverified = _check_metric_results(evidence, findings, hash_checks, repo_root=repo_root)

    dataset_unverified = dataset is None
    if dataset is not None:
        dataset_findings, dataset_hash_checks = validate_dataset_snapshot(dataset)
        findings.extend(_prefix_dataset_findings(dataset_findings))
        hash_checks.extend(
            HashCheck(_dataset_snapshot_pointer(check.pointer), check.state)
            for check in dataset_hash_checks
        )

        provenance_findings, provenance_hash_checks, dataset_unverified = (
            verify_dataset_provenance(
                dataset,
                repo_root=repo_root,
                evidence_status=evidence.evidence_status,
            )
        )
        findings.extend(provenance_findings)
        hash_checks.extend(provenance_hash_checks)
        _check_dataset_cross_reference(evidence, dataset, findings)

    unverified_provenance = (
        rule_unverified or feature_unverified or metric_unverified or dataset_unverified
    )

    blocking_categories = (
        FindingCategory.SCHEMA_FAILURE,
        FindingCategory.SEMANTIC_FAILURE,
        FindingCategory.HASH_MISMATCH,
        FindingCategory.CAUSAL_VIOLATION,
        FindingCategory.METRIC_DEFINITION_FAILURE,
    )
    structurally_valid = not any(finding.category in blocking_categories for finding in findings)
    authority_finding = any(
        finding.category is FindingCategory.AUTHORITY_FAILURE for finding in findings
    )

    trust = classify_evidence_trust(
        evidence,
        structurally_valid=structurally_valid,
        hash_checks=hash_checks,
        canonical_registry=canonical_registry,
        unverified_provenance=unverified_provenance,
        authority_failure=authority_finding,
    )

    all_required_hashes_verified = all(
        hc.state is HashVerificationState.VERIFIED_MATCH for hc in hash_checks
    )
    canonical_gate_passed = (
        structurally_valid
        and trust is EvidenceTrustClass.REGISTERED_CANONICAL
        and all_required_hashes_verified
        and not unverified_provenance
        and not authority_finding
    )

    return ValidationReport(
        schema_valid=True,
        findings=tuple(findings),
        hash_checks=tuple(hash_checks),
        trust_classification=trust,
        structurally_valid=structurally_valid,
        canonical_gate_passed=canonical_gate_passed,
    )


def validate_evidence_file(
    evidence_path: Path,
    *,
    repo_root: Path,
    dataset_path: Path | None = None,
    canonical_registry: frozenset[str] = frozenset(),
) -> ValidationReport:
    evidence, load_findings = load_evidence(evidence_path)
    if evidence is None:
        return ValidationReport(
            schema_valid=False,
            findings=tuple(load_findings),
            hash_checks=(),
            trust_classification=None,
            structurally_valid=False,
            canonical_gate_passed=False,
        )

    dataset: DatasetSnapshot | None = None
    if dataset_path is not None:
        dataset, dataset_findings = load_dataset_snapshot(dataset_path)
        load_findings = load_findings + _prefix_dataset_findings(dataset_findings)

    report = validate_evidence_artifact(
        evidence, repo_root=repo_root, dataset=dataset, canonical_registry=canonical_registry
    )
    if load_findings:
        return ValidationReport(
            schema_valid=report.schema_valid
            and not any(
                finding.category is FindingCategory.SCHEMA_FAILURE
                for finding in load_findings
            ),
            findings=tuple(load_findings) + report.findings,
            hash_checks=report.hash_checks,
            trust_classification=report.trust_classification,
            structurally_valid=False,
            canonical_gate_passed=False,
        )
    return report


# --------------------------------------------------------------------------
# Ranking policy loading and trust classification
# --------------------------------------------------------------------------


def load_ranking_policy(path: Path) -> tuple[RankingPolicy | None, list[Finding]]:
    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return None, [
            Finding(
                FindingCategory.SCHEMA_FAILURE,
                "POLICY_FILE_UNREADABLE",
                "/",
                "ranking policy file could not be read",
            )
        ]
    try:
        raw_value = canonical_json.loads_canonical(raw_bytes)
    except CanonicalizationError as exc:
        return None, [Finding(FindingCategory.SCHEMA_FAILURE, "POLICY_NOT_LCJ1", "/", str(exc))]
    try:
        policy = RankingPolicy.model_validate(raw_value)
    except ValidationError as exc:
        return None, _pydantic_errors_to_findings(exc)
    return policy, []


def classify_policy_trust(
    policy: RankingPolicy,
    *,
    raw_file_sha256: str,
    approved_registry: frozenset[str],
) -> PolicyTrustClass:
    if policy.declared_status is PolicyStatus.APPROVED and raw_file_sha256 in approved_registry:
        return PolicyTrustClass.REGISTERED_APPROVED
    return PolicyTrustClass.UNTRUSTED_DECLARED


# --------------------------------------------------------------------------
# Owner-gated registries (always empty in this task)
# --------------------------------------------------------------------------


def load_canonical_evidence_registry(path: Path) -> frozenset[str]:
    raw_value = canonical_json.loads_canonical(path.read_bytes())
    return frozenset(entry["artifact_content_sha256"] for entry in raw_value.get("entries", []))


def load_approved_ranking_policy_registry(path: Path) -> frozenset[str]:
    raw_value = canonical_json.loads_canonical(path.read_bytes())
    return frozenset(entry["policy_definition_sha256"] for entry in raw_value.get("entries", []))
