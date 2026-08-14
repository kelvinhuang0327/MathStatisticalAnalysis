"""A deterministic, pairwise-low-overlap ticket family for POWER_LOTTO Zone-1
(6/38), via a Sidon-type set in Z_38. Structurally the same idea as
`cyclic_sidon_shift.py` (BIG_LOTTO, 6/49) and `cyclic_sidon_shift_t539.py`
(DAILY_539, 5/39) -- see the former's docstring for the full mathematical
argument for cyclic shifts of a Sidon set. This is a separate, explicit
module rather than a generalization of either, matching how each locked
preregistration hardcodes its own verified, lottery-native constant rather
than sharing a mutable parameterization. Zone-2 (1-of-8) is out of scope for
this constructor entirely; it is a separate, unresolved design dimension.

Unlike BIG_LOTTO (49) and DAILY_539 (39), POWER_LOTTO Zone-1's pool size,
38, is EVEN. This matters and is disclosed in detail, not glossed over:

The plain greedy search used verbatim for the other two lotteries (start
from `{0}`; repeatedly try the smallest not-yet-included residue and keep it
only if it introduces no duplicate pairwise difference with the current
set; stop once `target_size` elements are collected) was tried first here,
run independently for modulus 38. It reproduces `{0, 1, 3, 7, 12}` for the
first five elements (identical to T539's full base set, for the same reason
T539's own docstring already discloses -- neither search has yet needed to
differ from the other while every difference involved stays well under the
smaller modulus), but then EXHAUSTS all remaining residues (13..37) without
finding a valid sixth element. This is not a search-quality accident: `19 =
38 / 2` is its own negation mod 38 (`-19 mod 38 == 19`), so ANY pair of base
elements differing by exactly 19 produces the SAME signed difference from
both of its two orderings, where a genuine Sidon set needs two *distinct*
values there -- and, independent of that difference-counting framing, such
a pair provably forces a pairwise cyclic-shift intersection of exactly 2 at
shift-distance 19 (both `a` and `b` of that pair map onto each other's
positions simultaneously whenever the shift gap is exactly half the
modulus). Odd moduli (49, 39) have no nonzero element equal to its own
negation, so this case never arose for B649 or T539 -- it is a genuinely new
structural wrinkle specific to POWER_LOTTO Zone-1's even pool size, not
something carried over from either prior replication.

The fix applied is the minimal one the same criterion already implies, not
a different or weaker rule: reject any candidate whose difference from an
existing element equals `pool_size / 2`. Confirming plain greedy alone is
insufficient, and that greedy's OWN acceptance rule (rather than a weaker
one) is still what is being enforced, this module's base set was found by
depth-first backtracking search -- same "try the smallest untried residue
next" order as greedy, but backtracking on a dead end instead of discarding
a rejected candidate permanently, plus the one added rejection rule above.
This is a completion of the same deterministic, pre-result criterion, not a
switch to a heuristic, randomized, or outcome-tuned method: it never
inspects winning-space coverage, and it reproduces the *exact same* B649 and
T539 base sets when run against pool sizes 49 and 39 (verified in this
module's test suite), where plain greedy already happened to succeed
without ever needing to backtrack.

The result is the lexicographically smallest base set containing 0 under
this search order: `{0, 1, 3, 7, 17, 30}`. It differs from B649/T539's
shared `{0, 1, 3, 7, 12, ...}` prefix starting at its fifth element (12 is
excluded here only because some valid continuation from a `{0,1,3,7,12}`
prefix does not exist mod 38 under this rule -- verified by exhaustion, not
assumed) -- disclosed as a real divergence, not a coincidence to preserve.
"""

from __future__ import annotations

POOL_SIZE = 38

#: 0-based base set in Z_38: all 6*5=30 ordered pairwise differences are
#: distinct, AND no pair differs by exactly 19 (= POOL_SIZE / 2) -- both
#: verified in tests, both via direct computation and via exhaustive
#: overlap-size checking across every one of the 38 possible shifts.
SIDON_BASE_SET_0_INDEXED: tuple[int, ...] = (0, 1, 3, 7, 17, 30)


def sidon_shift_ticket(shift: int) -> tuple[int, ...]:
    """The 1-based, ascending-sorted 6-number Zone-1 ticket for shift `shift`

    (`shift` may be any integer; only its value mod 38 matters).
    """

    return tuple(sorted((x + shift) % POOL_SIZE + 1 for x in SIDON_BASE_SET_0_INDEXED))


def sidon_shift_portfolio(ticket_count: int) -> tuple[tuple[int, ...], ...]:
    """The first `ticket_count` tickets, `T_0, T_1, ..., T_{ticket_count-1}`.

    A strict prefix relationship holds by construction, identical in kind to
    the BIG_LOTTO and DAILY_539 modules: the portfolio for `ticket_count=k`
    is always the portfolio for `ticket_count=k-1` with exactly one ticket
    appended -- nothing is ever reordered or rebuilt.
    """

    if not 0 <= ticket_count <= POOL_SIZE:
        raise ValueError("ticket_count must lie in [0, 38] -- only 38 distinct shifts exist")
    return tuple(sidon_shift_ticket(shift) for shift in range(ticket_count))


# --- Reproducible derivation (not needed at runtime; kept so the claims in
# the module docstring above are independently re-checkable rather than
# merely asserted -- see the test suite for the checks that actually matter).


def greedy_sidon_base(pool_size: int, target_size: int) -> tuple[int, ...]:
    """The plain greedy search shared with `cyclic_sidon_shift.py` /
    `cyclic_sidon_shift_t539.py`: start from `{0}`, keep the smallest
    not-yet-included residue whenever it introduces no duplicate ordered
    pairwise difference with the current set, stop at `target_size`.

    Raises `RuntimeError` if it runs out of residues first -- which is
    exactly what happens for `(38, 6)`, not a defect in this function.
    """

    base = [0]
    diffs: set[int] = set()
    candidate = 1
    while len(base) < target_size:
        if candidate >= pool_size:
            raise RuntimeError(
                f"greedy search exhausted all residues mod {pool_size} with only "
                f"{len(base)}/{target_size} elements found: {base}"
            )
        new_diffs: set[int] = set()
        ok = True
        for b in base:
            d1 = (candidate - b) % pool_size
            d2 = (b - candidate) % pool_size
            if d1 == d2 or d1 in diffs or d2 in diffs or d1 in new_diffs or d2 in new_diffs:
                ok = False
                break
            new_diffs.add(d1)
            new_diffs.add(d2)
        if ok:
            base.append(candidate)
            diffs |= new_diffs
        candidate += 1
    return tuple(base)


def derive_base_set_by_backtracking_search(pool_size: int, target_size: int) -> tuple[int, ...]:
    """The complete deterministic search actually used for this module's
    `SIDON_BASE_SET_0_INDEXED`: depth-first, trying the smallest untried
    residue first at every position like `greedy_sidon_base`, but
    backtracking on a dead end instead of discarding a rejected candidate
    permanently. Finds the lexicographically smallest valid base set
    containing 0. Never inspects winning-space coverage -- the acceptance
    rule is the Sidon-distinct-difference criterion only (with the
    even-modulus self-paired-distance case correctly excluded, matching
    `greedy_sidon_base`'s own rule, not a weaker one).

    Reproduces `greedy_sidon_base`'s output whenever that already succeeds
    (verified for `(49, 6)` and `(39, 5)` in the test suite), because greedy
    is exactly this same search with backtracking disabled -- so whenever
    greedy's own smallest-first path never dead-ends, DFS finds that
    identical path immediately and never needs to explore an alternative.
    """

    self_paired_distance = pool_size // 2 if pool_size % 2 == 0 else None

    def distance_class(a: int, b: int) -> int:
        d = abs(a - b) % pool_size
        return min(d, pool_size - d)

    base = [0]
    used_classes: set[int] = set()

    def backtrack(start_candidate: int) -> bool:
        if len(base) == target_size:
            return True
        for candidate in range(start_candidate, pool_size):
            new_classes: list[int] = []
            ok = True
            for b in base:
                dc = distance_class(candidate, b)
                if dc == self_paired_distance or dc in used_classes or dc in new_classes:
                    ok = False
                    break
                new_classes.append(dc)
            if not ok:
                continue
            base.append(candidate)
            used_classes.update(new_classes)
            if backtrack(candidate + 1):
                return True
            base.pop()
            for dc in new_classes:
                used_classes.discard(dc)
        return False

    if not backtrack(1):
        raise RuntimeError(
            f"no valid {target_size}-element constructor exists in Z_{pool_size} "
            "containing 0 under the Sidon-distinct-distance-class criterion"
        )
    return tuple(base)
