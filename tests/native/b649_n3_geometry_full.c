/* Verify actual pool-49 geometry tables against the preserved exact overlap
   kernels over the complete unconditional universe (U = all C(49,7)). */
#include "n3.h"
int main(void) {
    n3_init_binom(); n3_init_kappa();
    Ctx c={0}; c.residual_matches_kept=1;
    c.U=malloc((NT7+7)/8); memset(c.U,255,(NT7+7)/8);
    c.N3=malloc(NT3*sizeof *c.N3); c.N4=malloc(NT4*sizeof *c.N4);
    c.N5=malloc(NT5*sizeof *c.N5); c.N6=malloc(NT6*sizeof *c.N6);
    for (unsigned i=0;i<NT3;i++) c.N3[i]=BIN[46][4];
    for (unsigned i=0;i<NT4;i++) c.N4[i]=BIN[45][3];
    for (unsigned i=0;i<NT5;i++) c.N5[i]=BIN[44][2];
    memset(c.N6,43,NT6);
    uint64_t random=0x649abcdef;
    for (unsigned trial=0;trial<40;trial++) {
        unsigned s=trial%4;
        uint64_t B=63,C=((1ull<<s)-1)|(((1ull<<(6-s))-1)<<6),R=0;
        unsigned pool=trial<32 ? 12-s : 49;
        while (__builtin_popcountll(R)<6) { random=splitmix64(random); R|=1ull<<(random%pool); }
        int64_t pair=n3_pair_overlap(&c,B,C), lower=n3_pair_overlap_lower_bound(&c,B,C);
        int64_t triple=n3_triple_overlap(&c,B,C,R), table=n3_geometry_triple_overlap(B,C,R);
        if (pair!=lower || triple!=table) {
            fprintf(stderr,"GEOMETRY_FULL_MISMATCH s=%u pair=%lld lower=%lld triple=%lld table=%lld\n",
                s,(long long)pair,(long long)lower,(long long)triple,(long long)table); return 1;
        }
    }
    printf("{\"POOL49_GEOMETRY_CHECKS\":80,\"MISMATCHES\":0}\n");
    free(c.U); free(c.N3); free(c.N4); free(c.N5); free(c.N6);
    return 0;
}
