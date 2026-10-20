/* Proof-preserving cheap overlap lower bounds, valid for ANY residual U.
 * If B and C share >=3 numbers, outcomes hitting >=3 of the common numbers
 * are a subset of res(B) intersect res(C). Count this subset exactly by the
 * same threshold-3 Moebius identity (coefficients 1,-3,6,-10).
 * If they share exactly two numbers, choose two exclusive numbers from each
 * ticket. Outcomes containing the two common numbers and >=1 of each chosen
 * exclusive pair are also in both coverages. Inclusion-exclusion counts this
 * subset in 9 superset-table lookups (4 N4 - 4 N5 + N6).
 * No conclusion is drawn from an inconclusive lower bound.
 */
#include "n3.h"

/* H[s][a][b][z] is the unconditional triple overlap for B,C,R, where
 * s=|B&C|, a=|R&B&C|, b=|R&(B\C)|, z=|R&(C\B)|. All eight Venn atoms
 * determine the count, so the table enumerates category counts exactly.
 * With U the complement of kept coverage, union bound gives
 * i_U(B,C) >= i_full(B,C) - sum_R H(B,C,R).
 */
static int64_t H[4][4][7][7], full_pair[4];
static int geometry_ready;
static const unsigned hitB[7] = {1,1,1,1,0,0,0};
static const unsigned hitC[7] = {1,1,0,0,1,1,0};
static const unsigned hitR[7] = {1,0,1,0,1,0,1};

static int64_t geometry_count(const int *sizes, unsigned pos, unsigned need,
                              unsigned b, unsigned z, unsigned r, int64_t weight) {
    if (pos==7) return b>=3 && z>=3 && r>=3 ? weight*BIN[sizes[7]][need] : 0;
    int64_t total=0;
    for (unsigned k=0; k<=need && k<=(unsigned)sizes[pos]; k++)
        total += geometry_count(sizes,pos+1,need-k,b+k*hitB[pos],z+k*hitC[pos],
                                r+k*hitR[pos],weight*BIN[sizes[pos]][k]);
    return total;
}

static void init_geometry(void) {
    if (geometry_ready) return;
    for (int s=0;s<4;s++) for (int a=0;a<=s;a++)
        for (int b=0;b<=6-s;b++) for (int z=0;z<=6-s;z++) {
            if (a+b+z>6) continue;
            int sizes[8] = {a,s-a,b,6-s-b,z,6-s-z,6-a-b-z,
                            NPOOL-(18-s-a-b-z)};
            if (sizes[7]<0) continue;
            H[s][a][b][z]=geometry_count(sizes,0,7,0,0,0,1);
        }
    for (int s=0;s<4;s++) full_pair[s]=H[s][s][6-s][0]; /* R=B */
    geometry_ready=1;
}

static int64_t geometry_lower(const Ctx *c, uint64_t B, uint64_t C, unsigned s) {
    init_geometry();
    uint64_t common=B&C, bx=B&~C, cx=C&~B;
    int64_t lower=full_pair[s];
    int start=0;
#ifdef MUTANT_GEOMETRIC_LOWER_BOUND
    start=1; /* invalid: ignores excluded outcomes of the first kept ticket */
#endif
    for (int i=start;i<c->nR;i++) {
        uint64_t r=c->Rmask[i];
        lower -= H[s][__builtin_popcountll(r&common)]
                       [__builtin_popcountll(r&bx)][__builtin_popcountll(r&cx)];
    }
    return lower>0 ? lower : 0;
}

int64_t n3_geometry_triple_overlap(uint64_t B, uint64_t C, uint64_t R) {
    unsigned s=__builtin_popcountll(B&C);
    if (s>3) { fprintf(stderr,"unsupported geometry table intersection\n"); exit(2); }
    init_geometry();
    return H[s][__builtin_popcountll(R&B&C)]
               [__builtin_popcountll(R&B&~C)][__builtin_popcountll(R&C&~B)];
}

int64_t n3_pair_overlap_lower_bound(const Ctx *c, uint64_t B, uint64_t C) {
    uint64_t shared = B & C;
    unsigned size = __builtin_popcountll(shared);
    int64_t lower = 0;
    if (size >= 3) {
        static const int coefficient[7] = {0,0,0,1,-3,6,-10};
        for (uint64_t sub = shared; sub; sub = (sub - 1) & shared) {
            unsigned k = __builtin_popcountll(sub);
            if (k >= 3) lower += coefficient[k] * (int64_t)n3_count_N(c, sub);
        }
    } else if (size == 2) {
        uint64_t b = B & ~C, z = C & ~B;
        uint64_t b1 = b & -b; b &= b - 1;
        uint64_t b2 = b & -b;
        uint64_t z1 = z & -z; z &= z - 1;
        uint64_t z2 = z & -z;
        uint64_t bp[3] = {b1,b2,b1|b2}, zp[3] = {z1,z2,z1|z2};
        for (unsigned i = 0; i < 3; i++) for (unsigned j = 0; j < 3; j++) {
            int sign = ((i == 2) ^ (j == 2)) ? -1 : 1;
            lower += sign * (int64_t)n3_count_N(c, shared | bp[i] | zp[j]);
        }
    }
    if (size<=3 && c->residual_matches_kept) {
        int64_t geometric=geometry_lower(c,B,C,size);
        if (geometric>lower) lower=geometric;
    }
#ifdef MUTANT_SHARED_LOWER_BOUND
    lower++;
#endif
    return lower;
}
