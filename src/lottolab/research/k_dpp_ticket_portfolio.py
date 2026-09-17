"""Bounded research-only exact fixed-size k-DPP selector over a generic item set.

Clean-room behavioral reimplementation of the frozen donor characterization of
guilgautier/DPPy, commit 0d34dd67deedfed1d66f555636067f8fb2b0aab7 (MIT
License, Copyright (c) 2017 CRIStAL-PADR). No donor source is copied; the two
donor functions this module reproduces the semantics of --
``dppy.exact_sampling.elementary_symmetric_polynomials`` and
``dppy.exact_sampling.k_dpp_eig_vecs_selector`` (Phase 1, eigenvector
selection), plus the default ``'GS'`` mode of
``dppy.exact_sampling.proj_dpp_sampler_eig`` (Phase 2, sequential conditional
sampling) -- were read directly from the pinned commit to confirm the exact
recursion and selection formulas, which follow Kulesza & Taskar's
"Determinantal Point Processes for Machine Learning" (2012), Algorithm 8.

Given an L-ensemble kernel L (n x n, symmetric PSD) and a target size k, the
donor draws a k-subset of ``{1, ..., n}`` with probability proportional to
``det(L_S)`` restricted to ``|S| = k``, via two phases:

* Phase 1 selects exactly k eigenvectors of L, drawn without replacement with
  probability weighted by the corresponding eigenvalues, using elementary
  symmetric polynomials of the eigenvalues so the selection has the correct
  fixed-size marginal (this is the donor-cited Algorithm 8 of Kulesza-Taskar).
* Phase 2 samples k items sequentially from the rank-k projection kernel
  spanned by the Phase 1 eigenvectors, using a Gram-Schmidt-style residual
  update (the donor's default ``mode='GS'``) so each item is drawn
  proportional to the current residual squared norm and the basis is
  deflated after every draw.

Three deliberate deviations from the donor, each documented at its use site
below:

* ``dppy.utils.is_symmetric`` is a *cheap* check: it only compares a leading
  20x20 corner of the matrix. This module checks the full matrix instead,
  because "reject materially non-symmetric kernels" is a hard requirement
  here and a corner-only check would silently pass an asymmetric kernel
  whose asymmetry lies outside that corner.
* The donor's ``k_dpp_eig_vecs_selector`` has no guard for ``size=0``: its
  ``ind_selected`` array has length 0, and the loop's acceptance branch
  indexes ``ind_selected[k - 1]`` with ``k=0``, i.e. ``ind_selected[-1]`` on
  an empty array, which raises ``IndexError`` as soon as any eigenvalue
  triggers acceptance (near-certain for any positive eigenvalue). This
  module special-cases ``k=0`` to return an empty selection directly,
  before Phase 1 ever runs.
* Phase 2 renormalizes the categorical draw distribution by summing the
  current residual squared norms at each step, rather than the donor's
  ``rank - it`` shortcut. Both are mathematically identical under exact
  arithmetic (the selected eigenvectors are orthonormal, so the sum of
  residual squared norms after ``it`` deflations equals ``rank - it``
  exactly), but summing avoids compounding floating-point drift over a long
  sequential draw.

Reproducibility (which k-subset is returned) is for THIS implementation,
this NumPy version and this seed, using one ``numpy.random.Generator``
threaded through every stochastic draw. Exact trajectory parity with the
donor's Python/NumPy execution is not claimed.

Scope boundary
--------------

Standalone research selector only: no SQLite, no network access, no B649
wiring, no Matrix/replay/ranking candidate registration, and no
lottery-specific quality scoring, similarity features, hot/cold logic,
ranking weights, or prediction features. The caller supplies the L-ensemble
kernel; this module only implements the generic fixed-size k-DPP draw.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence

import numpy as np

_SYMMETRY_RTOL = 1e-5
_SYMMETRY_ATOL = 1e-8
_PSD_EIGENVALUE_ATOL = 1e-8


def select_k_dpp[ItemId: Hashable](
    item_ids: Sequence[ItemId],
    *,
    l_kernel: Sequence[Sequence[float]] | np.ndarray,
    k: int,
    seed: int | np.random.Generator,
) -> tuple[ItemId, ...]:
    """Draw one exact fixed-size k-DPP sample from an L-ensemble kernel.

    :param item_ids: Distinct labels for the ground set, length n.
    :param l_kernel: n x n symmetric PSD likelihood kernel, aligned by
        position with ``item_ids``.
    :param k: Requested sample size, ``0 <= k <= n``.
    :param seed: Seed or ``numpy.random.Generator`` for
        ``numpy.random.default_rng``; the same kernel, k and seed always
        return the same selection.
    :return: A tuple of exactly ``k`` distinct entries of ``item_ids``.
    :raises ValueError: If ``item_ids`` has duplicates, ``l_kernel`` is not a
        finite square symmetric PSD matrix matching ``len(item_ids)``, ``k``
        is out of ``[0, n]``, or ``k`` exceeds the numerical rank of
        ``l_kernel``.
    """
    n = len(item_ids)
    if len(set(item_ids)) != n:
        raise ValueError("item_ids must be distinct")

    kernel = _validate_kernel(l_kernel, n)

    if k < 0:
        raise ValueError(f"k must be >= 0, got {k}")
    if k > n:
        raise ValueError(f"k={k} exceeds ground set size n={n}")

    eigenvalues, eigenvectors = np.linalg.eigh(kernel)
    if eigenvalues.size and eigenvalues.min() < -_PSD_EIGENVALUE_ATOL:
        raise ValueError(
            f"l_kernel is not positive semi-definite within tolerance "
            f"{_PSD_EIGENVALUE_ATOL}: smallest eigenvalue={eigenvalues.min()!r}"
        )

    if k == 0:
        return ()

    rank_tolerance = eigenvalues.max() * n * np.finfo(np.float64).eps
    rank = int(np.count_nonzero(eigenvalues > rank_tolerance))
    if k > rank:
        raise ValueError(f"k={k} exceeds numerical rank={rank} of l_kernel")

    rng = np.random.default_rng(seed)
    e_poly = _elementary_symmetric_polynomials(eigenvalues, k)
    selected_eigenvectors = _select_eigenvectors(eigenvalues, eigenvectors, k, e_poly, rng)
    selected_indices = _sample_projection_indices(selected_eigenvectors, rng)

    return tuple(item_ids[int(index)] for index in selected_indices.tolist())


def _validate_kernel(l_kernel: Sequence[Sequence[float]] | np.ndarray, n: int) -> np.ndarray:
    try:
        kernel = np.asarray(l_kernel, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"l_kernel is not a valid numeric matrix: {exc}") from exc

    if kernel.ndim != 2 or kernel.shape[0] != kernel.shape[1]:
        raise ValueError(f"l_kernel must be square, got shape {kernel.shape}")
    if kernel.shape[0] != n:
        raise ValueError(f"l_kernel shape {kernel.shape} does not match len(item_ids)={n}")
    if not np.isfinite(kernel).all():
        raise ValueError("l_kernel contains non-finite values")
    if not np.allclose(kernel, kernel.T, rtol=_SYMMETRY_RTOL, atol=_SYMMETRY_ATOL):
        raise ValueError("l_kernel is not symmetric within tolerance")

    return kernel


def _elementary_symmetric_polynomials(eigenvalues: np.ndarray, k: int) -> np.ndarray:
    """``e_poly[d, m]``: degree-``d`` elementary symmetric polynomial of ``eigenvalues[:m]``."""
    n = eigenvalues.shape[0]
    e_poly = np.zeros((k + 1, n + 1))
    e_poly[0, :] = 1.0
    for degree in range(1, k + 1):
        for prefix_len in range(1, n + 1):
            e_poly[degree, prefix_len] = (
                e_poly[degree, prefix_len - 1]
                + eigenvalues[prefix_len - 1] * e_poly[degree - 1, prefix_len - 1]
            )
    return e_poly


def _select_eigenvectors(
    eigenvalues: np.ndarray,
    eigenvectors: np.ndarray,
    k: int,
    e_poly: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Phase 1: pick k of n eigenvectors, weighted by eigenvalue via elementary symmetric polys."""
    n = eigenvalues.shape[0]
    selected_columns = np.zeros(k, dtype=np.int64)
    remaining = k
    for index in range(n, 0, -1):
        acceptance = (
            eigenvalues[index - 1] * e_poly[remaining - 1, index - 1] / e_poly[remaining, index]
        )
        if rng.random() < acceptance:
            remaining -= 1
            selected_columns[remaining] = index - 1
            if remaining == 0:
                break
    return eigenvectors[:, selected_columns]


def _sample_projection_indices(eigenvectors: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Phase 2: sequentially draw k items from the projection kernel spanned by eigenvectors."""
    n, k = eigenvectors.shape
    basis = eigenvectors.copy()
    selected = np.zeros(k, dtype=np.int64)
    available = np.ones(n, dtype=bool)
    residual_sq_norm = np.einsum("ij,ij->i", basis, basis)
    orthogonal_contrib = np.zeros((n, k))

    for step in range(k):
        candidates = np.flatnonzero(available)
        weights = np.abs(residual_sq_norm[candidates])
        chosen = rng.choice(candidates, p=weights / weights.sum())
        selected[step] = chosen
        if step == k - 1:
            break

        available[chosen] = False
        remaining = np.flatnonzero(available)
        raw_overlap = basis[remaining, :].dot(basis[chosen, :])
        prior_overlap = orthogonal_contrib[remaining, :step].dot(orthogonal_contrib[chosen, :step])
        projection = raw_overlap - prior_overlap
        orthogonal_contrib[remaining, step] = projection / np.sqrt(residual_sq_norm[chosen])
        residual_sq_norm[remaining] -= orthogonal_contrib[remaining, step] ** 2

    return selected
