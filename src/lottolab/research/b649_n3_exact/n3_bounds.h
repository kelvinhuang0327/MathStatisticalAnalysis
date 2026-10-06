#ifndef N3_BOUNDS_H
#define N3_BOUNDS_H
#include <stdint.h>

/* Submodularity: res(B)\res(A) and res(C)\res(A) may overlap,
   so their two exact marginals give an admissible remaining-slot bound. */
static inline int64_t n3_two_slot_bound(int64_t rA, int64_t gB, int64_t gC) {
#ifdef MUTANT_CONDITIONAL_BOUND
    return rA + gB + gC - 1;
#else
    return rA + gB + gC;
#endif
}

/* iABC <= min(iAB, iAC, iBC); retains all equal optima. */
static inline int64_t n3_pair_bound(int64_t base, int64_t gC,
                                    int64_t iAB, int64_t iAC, int64_t iBC) {
    int64_t mn = iAB < iAC ? iAB : iAC;
    if (iBC < mn) mn = iBC;
    return base + gC - iBC + mn;
}

/* A lower bound L<=iBC implies iBC-iABC >= max(0,L-min(iAB,iAC)). */
static inline int64_t n3_lower_pair_bound(int64_t base, int64_t gC,
                                         int64_t iAB, int64_t iAC, int64_t lower) {
    int64_t cap = iAB < iAC ? iAB : iAC;
    return base + gC - (lower > cap ? lower - cap : 0);
}

static inline int n3_strict_prune(int64_t bound, int64_t target) {
#ifdef MUTANT_PRUNE_EQUAL
    return bound <= target;
#else
    return bound < target;
#endif
}
#endif
