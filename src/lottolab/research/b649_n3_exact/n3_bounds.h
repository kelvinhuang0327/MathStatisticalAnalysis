#ifndef N3_BOUNDS_H
#define N3_BOUNDS_H
#include <stdint.h>
#include "n3.h"

/* Experimental, compile-time opt-in only; production/default code is unchanged. */
#ifndef N3_GEOMETRIC_TRIPLE_BOUND
#define N3_GEOMETRIC_TRIPLE_BOUND 0
#endif
#if N3_GEOMETRIC_TRIPLE_BOUND != 0 && N3_GEOMETRIC_TRIPLE_BOUND != 1
#error "N3_GEOMETRIC_TRIPLE_BOUND must be 0 or 1"
#endif

/* Cell index is membership in A (bit 0), B (bit 1), C (bit 2).
 * Cell 0 includes EVERY number outside the union, including zero-support ones.
 * Inputs are legal six-number masks in the kernel's 0..NPOOL-1 convention.
 * Return failure for invalid inputs rather than manufacture an unsafe bound. */
static inline int n3_triple_venn_cells(uint64_t A, uint64_t B, uint64_t C,
                                      int cells[8]) {
    uint64_t universe = (1ull << NPOOL) - 1;
    if (((A | B | C) & ~universe) || __builtin_popcountll(A) != 6 ||
        __builtin_popcountll(B) != 6 || __builtin_popcountll(C) != 6) return 0;
    cells[7] = __builtin_popcountll(A & B & C);
    cells[3] = __builtin_popcountll(A & B & ~C);
    cells[5] = __builtin_popcountll(A & C & ~B);
    cells[6] = __builtin_popcountll(B & C & ~A);
    cells[1] = 6 - cells[7] - cells[3] - cells[5];
    cells[2] = 6 - cells[7] - cells[3] - cells[6];
    cells[4] = 6 - cells[7] - cells[5] - cells[6];
    cells[0] = NPOOL - __builtin_popcountll(A | B | C);
    return 1;
}

/* Select k_j from each of seven inside cells, completing the 7-set from cell 0.
 * Each admissible vector contributes product_j C(cells[j],k_j), exactly once.
 * Requires n3_init_binom(), nonnegative cells with sum <=49, and need<=7.
 * Every partial product counts subsets of <=7 numbers, so is <=C(49,7)
 * =85,900,584. All terms are nonnegative and the final sum is also <=C(49,7):
 * int64_t (including each multiplication and partial sum) cannot overflow. */
static inline int64_t n3_triple_cell_count(const int cells[8], unsigned pos,
                                          unsigned need, unsigned a, unsigned b,
                                          unsigned c, int64_t weight) {
    if (pos == 8)
        return a >= 3 && b >= 3 && c >= 3 ? weight * BIN[cells[0]][need] : 0;
    int64_t total = 0;
    for (unsigned k = 0; k <= need && k <= (unsigned)cells[pos]; k++)
        total += n3_triple_cell_count(cells, pos + 1, need - k,
                    a + ((pos & 1) ? k : 0), b + ((pos & 2) ? k : 0),
                    c + ((pos & 4) ? k : 0), weight * BIN[cells[pos]][k]);
    return total;
}

static inline int64_t n3_full_triple_geometry(uint64_t A, uint64_t B, uint64_t C) {
    int cells[8];
    if (!n3_triple_venn_cells(A, B, C, cells)) {
        fprintf(stderr, "invalid geometric triple ticket\n");
        exit(2);
    }
    return n3_triple_cell_count(cells, 1, 7, 0, 0, 0, 1);
}

typedef struct { unsigned ab, ac, bc, abc; } N3TripleShape;
typedef struct { uint32_t G_TABLE[7][7][7][7]; } N3TripleGeometryTable;

/* Complete intersection shape on 1..49, including coincident tickets. These
 * integer cells are sufficient: assign disjoint labels to each inside cell,
 * then the remaining labels to cell 0. Nonnegativity is also necessary. */
static inline int n3_triple_shape_cells(N3TripleShape s, int cells[8]) {
    if (s.ab > 6 || s.ac > 6 || s.bc > 6 || s.abc > 6) return 0;
    int ab=(int)s.ab, ac=(int)s.ac, bc=(int)s.bc, abc=(int)s.abc;
    int z[8]={31+ab+ac+bc-abc, 6-ab-ac+abc, 6-ab-bc+abc,
              ab-abc, 6-ac-bc+abc, ac-abc, bc-abc, abc};
    int sum=0;
    for (unsigned j=0;j<8;j++) {
        if (z[j]<0) return 0;
        sum+=z[j];
    }
    if (sum!=49) return 0;
    memcpy(cells,z,sizeof z);
    return 1;
}

/* Single-threaded kernel, one table in its consuming translation unit.
 * Call once before the candidate loop, AFTER n3_init_binom(). Repeated calls
 * return the same immutable table without rebuilding. No residual/support
 * mask is involved. UINT32_MAX marks invalid slots, never a zero G.
 * Every G <= C(49,7)=85,900,584 < 2^32-1; in fact G<=2,658,776 since
 * the triple coverage is contained in one ticket's coverage. The original
 * exact int64_t recursion above is used unchanged before the checked cast. */
static inline const N3TripleGeometryTable *n3_init_triple_geometry_table(void) {
    static N3TripleGeometryTable table;
    static int ready;
    if (ready) return &table;
    if (NPOOL!=49 || BIN[49][7]!=NT7) {
        fprintf(stderr,"geometric LUT requires pool 49 and initialized binomials\n");
        exit(2);
    }
    memset(&table,0xff,sizeof table);
    for (unsigned ab=0;ab<7;ab++) for (unsigned ac=0;ac<7;ac++)
        for (unsigned bc=0;bc<7;bc++) for (unsigned abc=0;abc<7;abc++) {
            int cells[8];
            if (!n3_triple_shape_cells((N3TripleShape){ab,ac,bc,abc},cells)) continue;
            int64_t G=n3_triple_cell_count(cells,1,7,0,0,0,1);
            if (G<0 || G>(int64_t)COVER_PER_TICKET || G>=UINT32_MAX) {
                fprintf(stderr,"geometric LUT value out of range\n"); exit(2);
            }
            table.G_TABLE[ab][ac][bc][abc]=(uint32_t)G;
        }
    ready=1;
    return &table;
}

/* Legal six-number tickets are guaranteed by the caller's candidate domain.
 * bc is the already computed |B&C| (NOT residual overlap iBC). */
static inline N3TripleShape n3_triple_shape(uint64_t A, uint64_t B, uint64_t C,
                                           unsigned bc) {
    return (N3TripleShape){(unsigned)__builtin_popcountll(A&B),
                           (unsigned)__builtin_popcountll(A&C),bc,
                           (unsigned)__builtin_popcountll(A&B&C)};
}

static inline int n3_triple_geometry_try_lookup(const N3TripleGeometryTable *table,
                                                N3TripleShape s, uint32_t *G) {
    if (s.ab>6 || s.ac>6 || s.bc>6 || s.abc>6) return 0;
    uint32_t value=table->G_TABLE[s.ab][s.ac][s.bc][s.abc];
    if (value==UINT32_MAX) return 0;
    *G=value;
    return 1;
}

static inline int64_t n3_triple_geometry_lookup(const N3TripleGeometryTable *table,
                                                N3TripleShape s) {
    uint32_t G;
    if (!n3_triple_geometry_try_lookup(table,s,&G)) {
        fprintf(stderr,"invalid geometric triple shape (%u,%u,%u,%u)\n",
                s.ab,s.ac,s.bc,s.abc); exit(2);
    }
    return G;
}

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

/* res(A)&res(B)&res(C) is contained in full(A)&full(B)&full(C), and
 * in each residual pair intersection: q<=G and q<=iAB,iAC,iBC. Thus
 * F<=base+gC-iBC+min(iAB,iAC,iBC,G)<=the original pair bound.
 * base+gC = rA+rB+rC-iAB-iAC (conditional marginals in the solver).
 * This bound is for ONE candidate; G need not be monotone in suffix order. */
static inline int64_t n3_geometric_pair_bound(int64_t base, int64_t gC,
                                             int64_t iAB, int64_t iAC,
                                             int64_t iBC, int64_t G) {
    int64_t cap = iAB < iAC ? iAB : iAC;
    if (iBC < cap) cap = iBC;
    if (G < cap) cap = G;
    return base + gC - iBC + cap;
}

/* Optional earlier-gate formula, tested/benchmarked but NOT wired into solver.
 * Given 0<=lower<=iBC and K=min(iAB,iAC,G), iBC-q>=max(0,lower-K). */
static inline int64_t n3_geometric_lower_pair_bound(int64_t base, int64_t gC,
                                                   int64_t iAB, int64_t iAC,
                                                   int64_t lower, int64_t G) {
    int64_t cap = iAB < iAC ? iAB : iAC;
    if (G < cap) cap = G;
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
