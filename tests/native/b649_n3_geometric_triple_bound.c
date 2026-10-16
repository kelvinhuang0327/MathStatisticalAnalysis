/* Bounded helper tests only: NEVER links/calls either N3 solver or evaluator.
 * clang -std=c11 -O2 -Wall -Wextra -Isrc/lottolab/research/b649_n3_exact \
 *   tests/native/b649_n3_geometric_triple_bound.c \
 *   src/lottolab/research/b649_n3_exact/{n3_core,n3_lower}.c -o /tmp/g-test
 * /tmp/g-test
 */
#include "n3_bounds.h"
#include <inttypes.h>

#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr, "FAIL line=%d: %s\n", __LINE__, #x); exit(1); } } while (0)

static unsigned hits(uint64_t e, uint64_t t) { return __builtin_popcountll(e & t) >= 3; }
static uint64_t mask(const int *v, unsigned n) {
    uint64_t m = 0;
    for (unsigned i = 0; i < n; i++) { CHECK(v[i] >= 1 && v[i] <= 49); m |= 1ull << (v[i]-1); }
    CHECK((unsigned)__builtin_popcountll(m) == n);
    return m;
}

/* Independent element-subset oracle, without category recursion. Each W in the
 * ticket union is unique; choose the remaining numbers from its full complement. */
static int64_t geometric_oracle(uint64_t a, uint64_t b, uint64_t c) {
    uint64_t u = a | b | c, w = u;
    unsigned outside = 49 - __builtin_popcountll(u);
    int64_t total = 0;
    for (;;) {
        unsigned k = __builtin_popcountll(w);
        if (k <= 7 && hits(w,a) && hits(w,b) && hits(w,c)) total += BIN[outside][7-k];
        if (!w) return total;
        w = (w-1) & u;
    }
}

static const N3TripleGeometryTable *geometry;
static uint64_t shape_checks, distinct_shapes, invalid_shapes, toy_triples, classifications, lower_checks;
static uint64_t toy_old_reject, toy_new_reject, production_new_reject, varied_overlap;
static int64_t maximum_G;

static int64_t lut_G(uint64_t a, uint64_t b, uint64_t c) {
    return n3_triple_geometry_lookup(geometry,
            n3_triple_shape(a,b,c,(unsigned)__builtin_popcountll(b&c)));
}

static void all_shapes(void) {
    for (int ab=0; ab<=6; ab++) for (int ac=0; ac<=6; ac++)
        for (int bc=0; bc<=6; bc++) for (int abc=0; abc<=6; abc++) {
            int z[8] = {49-18+ab+ac+bc-abc, 6-ab-ac+abc, 6-ab-bc+abc,
                        ab-abc, 6-ac-bc+abc, ac-abc, bc-abc, abc};
            int valid=1;
            for (int j=0; j<8; j++) if (z[j]<0) valid=0;
            N3TripleShape shape={(unsigned)ab,(unsigned)ac,(unsigned)bc,(unsigned)abc};
            int from_shape[8];
            uint32_t value=123;
            CHECK(n3_triple_shape_cells(shape,from_shape)==valid);
            CHECK(n3_triple_geometry_try_lookup(geometry,shape,&value)==valid);
            if (!valid) {
                CHECK(value==123); /* failure must not manufacture G=0 */
                CHECK(geometry->G_TABLE[ab][ac][bc][abc]==UINT32_MAX);
                invalid_shapes++; continue;
            }
            for (int j=0;j<8;j++) CHECK(from_shape[j]==z[j]);
            uint64_t a=0,b=0,c=0;
            unsigned next=0;
            for (unsigned j=1; j<8; j++) for (int k=0; k<z[j]; k++,next++) {
                if (j&1) a |= 1ull<<next;
                if (j&2) b |= 1ull<<next;
                if (j&4) c |= 1ull<<next;
            }
            int cells[8], sum=0;
            CHECK(n3_triple_venn_cells(a,b,c,cells));
            for (int j=0; j<8; j++) { CHECK(cells[j]==z[j]); CHECK(cells[j]>=0); sum+=cells[j]; }
            CHECK(sum==49);
            CHECK(__builtin_popcountll(a&b)==ab && __builtin_popcountll(a&c)==ac);
            CHECK(__builtin_popcountll(b&c)==bc && __builtin_popcountll(a&b&c)==abc);
            int64_t G=n3_full_triple_geometry(a,b,c);
            CHECK(value==G && lut_G(a,b,c)==G);
            if (G>maximum_G) maximum_G=G;
            CHECK(G==geometric_oracle(a,b,c));
            CHECK(G>=0 && G<=(int64_t)COVER_PER_TICKET && G<=85900584);
            CHECK(G==n3_full_triple_geometry(c,a,b));
            CHECK(G==lut_G(c,a,b) && G==lut_G(b,a,c));
            shape_checks++;
            distinct_shapes += a!=b && a!=c && b!=c;
        }
    int cells[8];
    for (unsigned j=0;j<4;j++) {
        N3TripleShape bad={0,0,0,0};
        if (j==0) bad.ab=7; if (j==1) bad.ac=7;
        if (j==2) bad.bc=7; if (j==3) bad.abc=UINT32_MAX;
        uint32_t value=123;
        CHECK(!n3_triple_shape_cells(bad,cells));
        CHECK(!n3_triple_geometry_try_lookup(geometry,bad,&value) && value==123);
    }
    CHECK(shape_checks==256 && distinct_shapes==237 && invalid_shapes==2145);
    CHECK(maximum_G==COVER_PER_TICKET && maximum_G<UINT32_MAX);
    uint32_t saved=BIN[49][7];
    BIN[49][7]=0; /* a rebuild would fail its binomial precondition */
    CHECK(geometry==n3_init_triple_geometry_table());
    BIN[49][7]=saved;
    CHECK(!n3_triple_venn_cells(31,63,126,cells));
    CHECK(!n3_triple_venn_cells(63^(1ull<<5)^(1ull<<49),63,126,cells));
    /* Full label invariance moves every number, including 29,32,44,49, through
     * the tickets and the outside cell. No support mask enters the helper. */
    int64_t expected=n3_full_triple_geometry(63,95,159);
    for (unsigned shift=0; shift<49; shift++) {
        uint64_t in[3]={63,95,159}, out[3]={0};
        for (unsigned t=0;t<3;t++) for (unsigned j=0;j<49;j++)
            if (in[t]&(1ull<<j)) out[t] |= 1ull<<((j+shift)%49);
        CHECK(n3_full_triple_geometry(out[0],out[1],out[2])==expected);
        CHECK(lut_G(out[0],out[1],out[2])==expected);
    }
    CHECK(expected>0);
}

static void fixed_witnesses(void) {
    const int tickets[3][6]={{1,2,27,29,32,44},{3,4,28,30,34,39},{5,6,31,35,40,46}};
    const int events[3][7]={{3,4,28,29,32,44,49},{5,6,29,31,32,44,49},{3,4,6,28,29,31,46}};
    const int kept[17][6]={
        {1,2,3,4,5,21},{1,6,7,8,9,22},{2,6,10,11,12,23},{3,10,13,14,15,22},
        {1,11,13,16,17,24},{4,6,14,16,18,25},{7,10,17,18,19,21},{2,8,13,19,20,25},
        {3,7,12,16,20,26},{5,8,11,15,18,26},{5,9,12,14,19,24},{4,9,15,17,20,23},
        {27,34,35,36,37,38},{27,39,40,41,42,43},{28,30,35,40,46,47},
        {28,31,36,41,48,49},{33,38,43,45,47,49}};
    uint64_t t[3], g[3]={0}, h[3]={0};
    for (unsigned j=0;j<3;j++) t[j]=mask(tickets[j],6);
    CHECK(!(t[0]&t[1]) && !(t[0]&t[2]) && !(t[1]&t[2]));
    CHECK(lut_G(t[0],t[1],t[2])==0);
    for (unsigned j=0;j<3;j++) {
        uint64_t e=mask(events[j],7);
        for (unsigned r=0;r<17;r++) CHECK(!hits(e,mask(kept[r],6)));
        unsigned a=hits(e,t[0]), b=hits(e,t[1]), c=hits(e,t[2]);
        g[0]+=a; g[1]+=b; g[2]+=c;
        h[0]+=a&&b; h[1]+=a&&c; h[2]+=b&&c;
        CHECK(!(a&&b&&c));
    }
    CHECK(h[0]==1 && h[1]==1 && h[2]==1);
    int64_t base=g[0]+g[1]-h[0], conditional=g[2]-h[1];
    int64_t old=n3_pair_bound(base,conditional,h[0],h[1],h[2]);
    int64_t now=n3_geometric_pair_bound(base,conditional,h[0],h[1],h[2],0);
    CHECK(old==4 && now==3 && now<old);
    CHECK(!n3_strict_prune(old,4) && n3_strict_prune(now,4));
    CHECK(!n3_strict_prune(now,3)); /* preserve equality */

    /* Explicit nonmonotone suffix: add a fourth residual event and a later
     * ticket. With b as anchor and a as second ticket, c and later both have
     * conditional marginal 1, ordered by increasing colex rank. Current UB=3
     * but later F=UB=4. Breaking the tail at target 4 would lose a tied optimum. */
    const int extra[7]={7,11,20,33,37,42,49}, later_numbers[6]={7,11,20,33,37,49};
    uint64_t extra_event=mask(extra,7),later=mask(later_numbers,6);
    for (unsigned r=0;r<17;r++) CHECK(!hits(extra_event,mask(kept[r],6)));
    for (unsigned j=0;j<3;j++) {
        CHECK(!hits(extra_event,t[j]));
        CHECK(!hits(mask(events[j],7),later));
    }
    CHECK(hits(extra_event,later) && rank_mask(t[2])<rank_mask(later));
    CHECK((int64_t)g[2]-(int64_t)h[2]==1); /* conditional c relative to b */
    int64_t later_bound=n3_geometric_pair_bound(3,1,1,0,0,
                            lut_G(t[1],t[0],later));
    CHECK(now==3 && later_bound==4);
    CHECK(n3_strict_prune(now,4) && !n3_strict_prune(later_bound,4));

    /* Two residual events hit a common triple. A blanket q=0 would give UB=0,
     * falsely reject F=2>D=1. The same source-level zero-G mutant must fail. */
    const int hi[3][6]={{1,2,3,4,5,6},{1,2,3,4,5,7},{1,2,3,4,5,8}};
    const int he[2][7]={{1,2,3,9,10,11,49},{1,2,3,12,13,14,48}};
    for (unsigned j=0;j<3;j++) t[j]=mask(hi[j],6);
    for (unsigned j=0;j<2;j++) for (unsigned k=0;k<3;k++) CHECK(hits(mask(he[j],7),t[k]));
    int64_t G=lut_G(t[0],t[1],t[2]);
    CHECK(G>0);
    CHECK(n3_geometric_pair_bound(2,0,2,2,2,G)==2);
    CHECK(n3_strict_prune(n3_geometric_pair_bound(2,0,2,2,2,0),1));
    CHECK(!n3_strict_prune(n3_geometric_pair_bound(2,0,2,2,2,G),1));
}

/* Exhaust the COMPLETE legal six-ticket domain on eleven labels:
 * C(462,3)=16,328,620 triples per residual, ALL C(11,7)=330 outcomes.
 * Unlike pools <=10, tickets can MISS seven-outcomes, so overlaps vary.
 * Two residual subsets (full, deterministic sparse) have independent direct
 * signatures. Actual production lower-bound code reads exact colex counts.
 * Toy G changes ONLY cell 0 to the toy universe; production G stays pool-49.
 * No solver/evaluator is linked or called. */
#define TOY_NT 462
#define TOY_NE 330
#define TOY_WORDS 6
static uint64_t toy_full[TOY_NT][TOY_WORDS], toy_sig[TOY_NT][TOY_WORDS];
static int64_t toy_lower[TOY_NT][TOY_NT], toy_pair[TOY_NT][TOY_NT];

static void exhaustive_toy(void) {
    uint64_t t[TOY_NT],e[TOY_NE]; unsigned nt=0,ne=0;
    for (uint64_t m=0;m<(1u<<11);m++) {
        if (__builtin_popcountll(m)==6) t[nt++]=m;
        if (__builtin_popcountll(m)==7) e[ne++]=m;
    }
    CHECK(nt==TOY_NT && ne==TOY_NE);
    for (unsigned i=0;i<nt;i++) for (unsigned j=0;j<ne;j++)
        if (hits(e[j],t[i])) toy_full[i][j/64]|=1ull<<(j%64);
    Ctx ctx={0};
    ctx.N3=calloc(NT3,sizeof *ctx.N3); ctx.N4=calloc(NT4,sizeof *ctx.N4);
    ctx.N5=calloc(NT5,sizeof *ctx.N5); ctx.N6=calloc(NT6,sizeof *ctx.N6);
    CHECK(ctx.N3 && ctx.N4 && ctx.N5 && ctx.N6);
    int64_t geom[7][7][7][7],geom49[7][7][7][7];
    memset(geom,-1,sizeof geom); memset(geom49,-1,sizeof geom49);
    for (unsigned trial=0;trial<2;trial++) {
        uint64_t residual[TOY_WORDS]={0}; int64_t marginal[TOY_NT]={0},D=0;
        memset(ctx.N3,0,NT3*sizeof *ctx.N3); memset(ctx.N4,0,NT4*sizeof *ctx.N4);
        memset(ctx.N5,0,NT5*sizeof *ctx.N5); memset(ctx.N6,0,NT6*sizeof *ctx.N6);
        for (unsigned j=0;j<ne;j++) {
            if (trial && (splitmix64(j+649)&3)) continue;
            residual[j/64]|=1ull<<(j%64);
            D+=hits(e[j],t[0]) || hits(e[j],t[nt/2]) || hits(e[j],t[nt-1]);
            for (uint64_t sub=e[j];sub;sub=(sub-1)&e[j]) {
                unsigned k=__builtin_popcountll(sub); uint32_t r=rank_mask(sub);
                if (k==3) ctx.N3[r]++; if (k==4) ctx.N4[r]++;
                if (k==5) ctx.N5[r]++; if (k==6) ctx.N6[r]++;
            }
        }
        for (unsigned i=0;i<nt;i++) for (unsigned w=0;w<TOY_WORDS;w++) {
            toy_sig[i][w]=toy_full[i][w]&residual[w];
            marginal[i]+=__builtin_popcountll(toy_sig[i][w]);
        }
        for (unsigned i=0;i<nt;i++) for (unsigned j=i+1;j<nt;j++) {
            int64_t exact=0;
            for (unsigned w=0;w<TOY_WORDS;w++) exact+=__builtin_popcountll(toy_sig[i][w]&toy_sig[j][w]);
            toy_pair[i][j]=exact;
            toy_lower[i][j]=n3_pair_overlap_lower_bound(&ctx,t[i],t[j]);
            CHECK(toy_lower[i][j]>=0 && toy_lower[i][j]<=exact);
            varied_overlap+=exact<marginal[i] && exact<marginal[j];
            lower_checks++;
        }
        for (unsigned i=0;i<nt;i++) for (unsigned j=i+1;j<nt;j++) for (unsigned k=j+1;k<nt;k++) {
            unsigned ab=__builtin_popcountll(t[i]&t[j]),ac=__builtin_popcountll(t[i]&t[k]);
            unsigned bc=__builtin_popcountll(t[j]&t[k]),abc=__builtin_popcountll(t[i]&t[j]&t[k]);
            int64_t *G=&geom[ab][ac][bc][abc],*G49=&geom49[ab][ac][bc][abc];
            if (*G<0) {
                int cells[8]; CHECK(n3_triple_venn_cells(t[i],t[j],t[k],cells)); cells[0]-=38;
                CHECK(cells[0]>=0);
                *G=n3_triple_cell_count(cells,1,7,0,0,0,1);
                *G49=n3_full_triple_geometry(t[i],t[j],t[k]);
            }
            int64_t fullq=0,q=0,F=0;
            for (unsigned w=0;w<TOY_WORDS;w++) {
                fullq+=__builtin_popcountll(toy_full[i][w]&toy_full[j][w]&toy_full[k][w]);
                q+=__builtin_popcountll(toy_sig[i][w]&toy_sig[j][w]&toy_sig[k][w]);
                F+=__builtin_popcountll(toy_sig[i][w]|toy_sig[j][w]|toy_sig[k][w]);
            }
            CHECK(*G==fullq);
            int64_t a=marginal[i],b=marginal[j],c=marginal[k];
            int64_t hab=toy_pair[i][j],hac=toy_pair[i][k],hbc=toy_pair[j][k];
            int64_t base=a+b-hab,gc=c-hac;
            CHECK(q<=*G && q<=*G49 && q<=hab && q<=hac && q<=hbc);
            CHECK(F==a+b+c-hab-hac-hbc+q);
            int64_t old=n3_pair_bound(base,gc,hab,hac,hbc);
            int64_t now=n3_geometric_pair_bound(base,gc,hab,hac,hbc,*G);
            int64_t production=n3_geometric_pair_bound(base,gc,hab,hac,hbc,*G49);
            int64_t lookup=lut_G(t[i],t[j],t[k]);
            CHECK(lookup==*G49);
            CHECK(production==n3_geometric_pair_bound(base,gc,hab,hac,hbc,lookup));
            int64_t early=n3_geometric_lower_pair_bound(base,gc,hab,hac,toy_lower[j][k],*G);
            int64_t early49=n3_geometric_lower_pair_bound(base,gc,hab,hac,toy_lower[j][k],lookup);
            CHECK(F<=early49 && early49<=n3_lower_pair_bound(base,gc,hab,hac,toy_lower[j][k]));
            CHECK(F<=now && now<=production && production<=old);
            CHECK(F<=early && early<=n3_lower_pair_bound(base,gc,hab,hac,toy_lower[j][k]));
            int64_t targets[5]={0,D,F,F+1,old};
            for (unsigned v=0;v<5;v++) {
                int old_reject=n3_strict_prune(old,targets[v]),new_reject=n3_strict_prune(now,targets[v]);
                int production_reject=n3_strict_prune(production,targets[v]);
                CHECK(!old_reject || production_reject);
                CHECK(!production_reject || new_reject);
                CHECK(!new_reject || F<targets[v]);
                CHECK(F<=targets[v] || !new_reject); /* no positive delta lost */
                CHECK(F!=targets[v] || !new_reject); /* no tied optimum lost */
                CHECK(!n3_strict_prune(early,targets[v]) || F<targets[v]);
                CHECK(!n3_strict_prune(early49,targets[v]) || F<targets[v]);
                toy_old_reject+=old_reject; toy_new_reject+=new_reject;
                production_new_reject+=production_reject; classifications++;
            }
            toy_triples++;
        }
    }
    CHECK(varied_overlap>0 && toy_new_reject>toy_old_reject);
    free(ctx.N3); free(ctx.N4); free(ctx.N5); free(ctx.N6);
}

int main(int argc, char **argv) {
    if (argc==2 && !strcmp(argv[1],"--uninitialized-table")) {
        (void)n3_init_triple_geometry_table(); return 1;
    }
    n3_init_binom();
    geometry=n3_init_triple_geometry_table();
    if (argc==2 && !strcmp(argv[1],"--invalid-shape")) {
        (void)n3_triple_geometry_lookup(geometry,(N3TripleShape){0,0,0,1}); return 1;
    }
    all_shapes(); fixed_witnesses(); exhaustive_toy();
    CHECK(!n3_strict_prune(10,10) && n3_strict_prune(9,10));
    printf("{\"SHAPE_CHECKS\":%" PRIu64 ",\"DISTINCT_TICKET_SHAPES\":%" PRIu64
           ",\"INVALID_SHAPES_REJECTED\":%" PRIu64 ",\"MAXIMUM_G\":%" PRId64
           ",\"LUT_BYTES\":%zu,\"LABEL_PERMUTATIONS\":49,\"TOY_TRIPLES\":%" PRIu64 ",\"CLASSIFICATIONS\":%" PRIu64
           ",\"PRODUCTION_LOWER_CHECKS\":%" PRIu64 ",\"TOY_OLD_REJECTS\":%" PRIu64
           ",\"TOY_NEW_REJECTS\":%" PRIu64 ",\"PRODUCTION_NEW_REJECTS\":%" PRIu64
           ",\"VARIED_PAIR_OVERLAPS\":%" PRIu64 ",\"FIXED_WITNESS_ADDITIONAL_REJECTS\":1,"
           "\"ZERO_Q_COUNTEREXAMPLE\":true,\"SUFFIX_COUNTEREXAMPLE\":true,"
           "\"MISMATCHES\":0,\"PEAK_RSS_BYTES\":%zu}\n",
           shape_checks,distinct_shapes,invalid_shapes,maximum_G,sizeof *geometry,toy_triples,classifications,lower_checks,
           toy_old_reject,toy_new_reject,production_new_reject,varied_overlap,n3_peak_rss());
    return 0;
}
