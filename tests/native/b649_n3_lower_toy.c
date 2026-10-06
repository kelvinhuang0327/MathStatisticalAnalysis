/* Independent exhaustive outcome oracle for the ACTUAL production lower-bound
 * implementation: arbitrary residual subsets of C(12,7), real colex N3..N6.
 * Both the 3+ common-number and the two-common-number subset counts are checked
 * for equality against direct events, then for <= exact pair coverage.
 */
#include "n3.h"

static uint64_t events[792];
static unsigned ne;
static uint64_t seed = 0x6495eed;

static uint64_t next(void) { seed = splitmix64(seed); return seed; }

int main(void) {
    n3_init_binom();
    Ctx ctx = {0};
    ctx.U = calloc((NT7+7)/8,1);
    ctx.N3 = calloc(NT3, sizeof *ctx.N3);
    ctx.N4 = calloc(NT4, sizeof *ctx.N4);
    ctx.N5 = calloc(NT5, sizeof *ctx.N5);
    ctx.N6 = calloc(NT6, sizeof *ctx.N6);
    uint64_t checks = 0, shared_counts[7] = {0};
    for (unsigned trial = 0; trial < 40; trial++) {
        ne = 0;
        memset(ctx.U,0,(NT7+7)/8);
        memset(ctx.N3,0,NT3*sizeof *ctx.N3);
        memset(ctx.N4,0,NT4*sizeof *ctx.N4);
        memset(ctx.N5,0,NT5*sizeof *ctx.N5);
        memset(ctx.N6,0,NT6*sizeof *ctx.N6);
        ctx.residual_matches_kept = trial>=20;
        ctx.nR = ctx.residual_matches_kept ? 1+(trial%2) : 0;
        if (trial==20) ctx.nR=0; /* complete small universe */
        for (int i=0;i<ctx.nR;i++) {
            ctx.Rmask[i]=0;
            while (__builtin_popcountll(ctx.Rmask[i])<6) ctx.Rmask[i]|=1ull<<(next()%12);
        }
        for (uint64_t e = 0; e < (1u<<12); e++) if (__builtin_popcountll(e)==7) {
            int residual=ctx.residual_matches_kept ? 1 : !!(next()&3);
            for (int i=0;i<ctx.nR;i++) if (__builtin_popcountll(e&ctx.Rmask[i])>=3) residual=0;
            if (!residual) continue;
            events[ne++] = e;
            uint32_t idx = rank_mask(e); ctx.U[idx>>3] |= 1u<<(idx&7);
            for (uint64_t sub=e; sub; sub=(sub-1)&e) {
                unsigned k=__builtin_popcountll(sub); uint32_t r=rank_mask(sub);
                if (k==3) ctx.N3[r]++;
                if (k==4) ctx.N4[r]++;
                if (k==5) ctx.N5[r]++;
                if (k==6) ctx.N6[r]++;
            }
        }
        for (unsigned pair = 0; pair < 2000; pair++) {
            uint64_t B=0,C=0;
            while (__builtin_popcountll(B)<6) B |= 1ull<<(next()%12);
            while (__builtin_popcountll(C)<6) C |= 1ull<<(next()%12);
            if (pair == 0) C = B;
            if (pair == 1) C = ((1ull << 12) - 1) ^ B;
            if (pair==0 && ctx.nR) {
                B=ctx.Rmask[0]; C=((1ull<<12)-1)^B;
            }
            uint64_t common=B&C;
            unsigned shared=__builtin_popcountll(common);
            uint64_t b=B&~C,z=C&~B,bp=0,zp=0;
            for (int k=0; k<2 && b; k++) { bp|=b&-b; b&=b-1; }
            for (int k=0; k<2 && z; k++) { zp|=z&-z; z&=z-1; }
            int64_t exact_pair=0,exact_subset=0;
            for (unsigned i=0; i<ne; i++) {
                uint64_t e=events[i];
                exact_pair += __builtin_popcountll(e&B)>=3 && __builtin_popcountll(e&C)>=3;
                if (shared>=3) exact_subset += __builtin_popcountll(e&common)>=3;
                if (shared==2) exact_subset += (e&common)==common && (e&bp) && (e&zp);
            }
            int64_t lower=n3_pair_overlap_lower_bound(&ctx,B,C);
            if (lower<0 || lower>exact_pair || lower<exact_subset ||
                (!ctx.residual_matches_kept && lower!=exact_subset)) {
                fprintf(stderr,"SHARED_BOUND_INADMISSIBLE shared=%u lower=%lld subset=%lld pair=%lld\n",
                    shared,(long long)lower,(long long)exact_subset,(long long)exact_pair); return 1;
            }
            checks++; shared_counts[shared]++;
        }
    }
    for (unsigned k=0;k<7;k++) if (!shared_counts[k]) return 2;
    printf("{\"LOTTERY_LOWER_BOUND_CHECKS\":%llu,\"MISMATCHES\":0}\n",(unsigned long long)checks);
    free(ctx.U); free(ctx.N3); free(ctx.N4); free(ctx.N5); free(ctx.N6);
    return 0;
}
