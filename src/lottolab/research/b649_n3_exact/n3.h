/* B649_K20_V7_FULL_N3_SIGNATURE_COMPRESSION_FEASIBILITY_R1 exact kernel.
 *
 * Objective (7-subset form, identical to b649_official_any_prize_exact):
 * a ticket t wins outcome (D, s) iff |t & (D | {s})| >= 3, so every 7-subset E of
 * 1..49 stands for 7 outcomes and the canonical count of a portfolio is
 * 7 * #{E : some ticket t has |t & E| >= 3}.
 *
 * For a destroy triple, R is the 17 kept tickets, U the 7-subsets R does not win,
 * res(t) = {E in U : |t & E| >= 3} the residual-coverage signature of ticket t and
 * r(t) = |res(t)|.  The repair objective is F(A,B,C) = |res(A) u res(B) u res(C)|
 * and the repaired canonical count is 7 * (C(49,7) - |U| + F).
 *
 * Numbers are 0-based (0..48) inside the kernel; subsets are colex ranked:
 * rank(e_0 < ... < e_{k-1}) = sum_i C(e_i, i + 1).
 */
#ifndef N3_H
#define N3_H

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef NPOOL
#define NPOOL 49
#endif
#define NT3 18424u
#define NT4 211876u
#define NT5 1906884u
#ifndef NT6
#define NT6 13983816u
#endif
#define NT7 85900584u
#define HITS_PER_7SET 432824ull     /* tickets t with |t & E| >= 3 for one fixed 7-set E */
#define COVER_PER_TICKET 2658776ull /* 7-sets E with |t & E| >= 3 for one fixed ticket t */

extern uint32_t BIN[64][9];

void n3_init_binom(void);

static inline uint32_t rank_mask(uint64_t m) {
    uint32_t r = 0;
    int i = 0;
    while (m) {
        int b = __builtin_ctzll(m);
        r += BIN[b][++i];
        m &= m - 1;
    }
    return r;
}

static inline int u_get(const uint8_t *bits, uint32_t idx) { return (bits[idx >> 3] >> (idx & 7)) & 1; }

static inline uint64_t splitmix64(uint64_t x) {
    uint64_t z = x + 0x9e3779b97f4a7c15ull;
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
    return z ^ (z >> 31);
}

typedef struct {
    int nR;
    uint64_t Rmask[20];
    uint64_t Xmask[3]; /* removed (destroyed) tickets */
    uint8_t *U;        /* bitset over 7-set colex ranks: 1 = residual (not won by R) */
    uint64_t Usize;
    int residual_matches_kept; /* true only for U = complement of kept coverage */
    uint8_t *N6;  /* #{E in U : E >= t}, t a 6-set    (<= 43)     */
    uint16_t *N5; /* #{E in U : E >= Y}, |Y| = 5      (<= 946)    */
    uint16_t *N4; /* |Y| = 4                          (<= 14190)  */
    uint32_t *N3; /* |Y| = 3                          (<= 163185) */
    int32_t *r;   /* r(t) for every ticket rank */
    uint64_t *g3a, *g3b, *g4a, *g4b; /* XOR fingerprint tables (two independent hashes) */
    uint64_t seed1, seed2;
} Ctx;

/* core passes */
void n3_build_residual(Ctx *c, int with_fingerprints);
void n3_build_n6(Ctx *c);
void n3_lift(Ctx *c);
void n3_score_all(Ctx *c, uint64_t *sum_r, uint64_t *sum_n6);
void n3_fingerprints(const Ctx *c, uint64_t *f1, uint64_t *f2);

/* helpers */
uint64_t n3_unrank6(uint32_t rank);
int n3_mask_to_sorted(uint64_t m, int *out);
uint64_t n3_count_N(const Ctx *c, uint64_t w); /* #{E in U : E >= w}, 3 <= |w| <= 7 */

/* direct (brute-force) checks */
uint64_t n3_direct_res(const Ctx *c, uint64_t t, uint64_t *xor1, uint64_t *xor2);
uint64_t n3_direct_union(const Ctx *c, const uint64_t *tickets, int n);
uint32_t *n3_res_list(const Ctx *c, uint64_t t, uint64_t *count);

/* exact overlaps */
void n3_init_kappa(void);
int64_t n3_pair_overlap(const Ctx *c, uint64_t b, uint64_t cc);
int64_t n3_triple_overlap(const Ctx *c, uint64_t a, uint64_t b, uint64_t cc);
int64_t n3_pair_overlap_direct(const Ctx *c, uint64_t b, uint64_t cc);
int64_t n3_pair_overlap_lower_bound(const Ctx *c, uint64_t b, uint64_t cc);
/* Unconditional geometric table, supported for |B&C|<=3. */
int64_t n3_geometry_triple_overlap(uint64_t b, uint64_t cc, uint64_t r);

double n3_now(void);
size_t n3_peak_rss(void);

#endif
