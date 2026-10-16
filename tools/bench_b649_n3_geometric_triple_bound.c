/* Fixed, bounded MICROBENCHMARK, not a solver/runner. No solver is linked.
 * Build (compilation is outside all reported candidate timings):
 * clang -std=c11 -O3 -Wall -Wextra -Werror \
 *   -Isrc/lottolab/research/b649_n3_exact \
 *   tools/bench_b649_n3_geometric_triple_bound.c \
 *   src/lottolab/research/b649_n3_exact/{n3_core,n3_lower,n3_overlap}.c \
 *   -o /tmp/g-bench
 * /usr/bin/time -l /tmp/g-bench
 *
 * Fixed 512 legal, mutually distinct triples on 1..49, four equal strata:
 * uniform; disjoint; high intersection; one-swap neighbors of removed tickets.
 * U is a FIXED SAMPLE of 4096 distinct residual 7-sets against the pinned 17 R,
 * NOT the full C2 residual. D is the exact removed-ticket union on THIS SAMPLE.
 * These rejection counts must never be described as full C2 search savings.
 * Pipelines call the ORIGINAL lower/pair/triple kernels, without pair caching,
 * solver auditing, sorting or setup. The lower-only alternative is measured
 * separately and is NOT the integration in n3_solve.c. No source/binary I/O or
 * context construction is timed as single-candidate runtime.
 * Pipeline seconds are normalized per 512-candidate pass after 64 repetitions;
 * the reported three measurements rotate order. Counts are per unique sample.
 * Direct arithmetic uses 64 passes; cheap arithmetic uses 4096. LUT setup CPU
 * and wall time are reported separately. --dump-input PATH writes the exact
 * canonical inputs outside all timed regions for external SHA256 verification.
 */
#include "n3_bounds.h"
#include <inttypes.h>
#include <time.h>

#define NS 512
#define NE 4096
#define NRUN 3
#define REPEAT 64
#define OLD_REPEAT 4096
#define PIPELINE_REPEAT 64
#define NARITH 9
#define NPIPE 4
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr,"benchmark FAIL line=%d: %s\n",__LINE__,#x); exit(1); } } while (0)

typedef struct {
    uint64_t t[3];
    int64_t g[3], ab, ac, bc, q, F, G, lower;
    N3TripleShape shape;
} Sample;
typedef struct { uint64_t rejects, lower_rejects, pairs, triples, g_calls; int64_t checksum; } Counts;
static Ctx ctx;
static const N3TripleGeometryTable *geometry;
static Sample samples[NS];
static uint64_t events[NE], random_state=0x649b64920261016ull, sample_fingerprint;
static int64_t target;
static volatile int64_t sink;
static uint64_t next_random(void) { random_state=splitmix64(random_state); return random_state; }
static int hit(uint64_t e,uint64_t t) { return __builtin_popcountll(e&t)>=3; }
static uint64_t ticket(void) {
    uint64_t t=0;
    while (__builtin_popcountll(t)<6) t|=1ull<<(next_random()%49);
    return t;
}
static uint64_t from_numbers(const int v[6]) {
    uint64_t t=0;
    for (unsigned j=0;j<6;j++) t|=1ull<<(v[j]-1);
    return t;
}
static int allowed(uint64_t t) {
    if (__builtin_popcountll(t)!=6 || t>>49) return 0;
    for (int j=0;j<ctx.nR;j++) if (t==ctx.Rmask[j]) return 0;
    return 1;
}
static uint64_t one_swap(uint64_t t) {
    unsigned drop=next_random()%6, j=0; uint64_t bit=0;
    for (unsigned p=0;p<49;p++) if ((t>>p)&1) { if (j++==drop) { bit=1ull<<p; break; } }
    uint64_t add;
    do { add=1ull<<(next_random()%49); } while (t&add);
    return (t^bit)|add;
}

static void setup(void) {
    const int kept[17][6]={
        {1,2,3,4,5,21},{1,6,7,8,9,22},{2,6,10,11,12,23},{3,10,13,14,15,22},
        {1,11,13,16,17,24},{4,6,14,16,18,25},{7,10,17,18,19,21},{2,8,13,19,20,25},
        {3,7,12,16,20,26},{5,8,11,15,18,26},{5,9,12,14,19,24},{4,9,15,17,20,23},
        {27,34,35,36,37,38},{27,39,40,41,42,43},{28,30,35,40,46,47},
        {28,31,36,41,48,49},{33,38,43,45,47,49}};
    const int removed[3][6]={{27,29,30,31,32,33},{28,29,34,39,44,45},{32,37,42,44,46,48}};
    ctx.nR=17;
    for (int j=0;j<17;j++) ctx.Rmask[j]=from_numbers(kept[j]);
    for (int j=0;j<3;j++) ctx.Xmask[j]=from_numbers(removed[j]);
    /* Arbitrary residual subset: keep geometry-lower's stronger precondition OFF. */
    ctx.residual_matches_kept=0;
    ctx.U=calloc((NT7+7)/8,1);
    ctx.N3=calloc(NT3,sizeof *ctx.N3); ctx.N4=calloc(NT4,sizeof *ctx.N4);
    ctx.N5=calloc(NT5,sizeof *ctx.N5); ctx.N6=calloc(NT6,sizeof *ctx.N6);
    REQUIRE(ctx.U && ctx.N3 && ctx.N4 && ctx.N5 && ctx.N6);
    unsigned ne=0;
    while (ne<NE) {
        uint64_t e=0;
        while (__builtin_popcountll(e)<7) e|=1ull<<(next_random()%49);
        int keep=1;
        for (int j=0;j<17;j++) if (hit(e,ctx.Rmask[j])) { keep=0; break; }
        uint32_t rank=rank_mask(e);
        if (!keep || u_get(ctx.U,rank)) continue;
        ctx.U[rank>>3]|=1u<<(rank&7); events[ne++]=e;
        sample_fingerprint=splitmix64(sample_fingerprint^e);
        target+=hit(e,ctx.Xmask[0]) || hit(e,ctx.Xmask[1]) || hit(e,ctx.Xmask[2]);
        for (uint64_t s=e;s;s=(s-1)&e) {
            unsigned k=__builtin_popcountll(s); uint32_t r=rank_mask(s);
            if (k==3) ctx.N3[r]++; if (k==4) ctx.N4[r]++;
            if (k==5) ctx.N5[r]++; if (k==6) ctx.N6[r]++;
        }
    }
    for (unsigned i=0;i<NS;i++) {
        Sample *s=samples+i;
        do {
            if (i<128) { for (unsigned j=0;j<3;j++) s->t[j]=ticket(); }
            else if (i<256) {
                uint64_t used=0;
                for (unsigned j=0;j<3;j++) {
                    s->t[j]=0;
                    while (__builtin_popcountll(s->t[j])<6) {
                        uint64_t bit=1ull<<(next_random()%49);
                        if (!(used&bit)) s->t[j]|=bit;
                    }
                    used|=s->t[j];
                }
            } else if (i<384) {
                s->t[0]=ticket(); s->t[1]=one_swap(s->t[0]); s->t[2]=one_swap(s->t[0]);
            } else for (unsigned j=0;j<3;j++) s->t[j]=one_swap(ctx.Xmask[j]);
        } while (!allowed(s->t[0]) || !allowed(s->t[1]) || !allowed(s->t[2]) ||
                 s->t[0]==s->t[1] || s->t[0]==s->t[2] || s->t[1]==s->t[2]);
        for (unsigned j=0;j<3;j++) sample_fingerprint=splitmix64(sample_fingerprint^s->t[j]);
        for (unsigned j=0;j<NE;j++) {
            int a=hit(events[j],s->t[0]),b=hit(events[j],s->t[1]),c=hit(events[j],s->t[2]);
            s->g[0]+=a; s->g[1]+=b; s->g[2]+=c;
            s->ab+=a&&b; s->ac+=a&&c; s->bc+=b&&c; s->q+=a&&b&&c; s->F+=a||b||c;
        }
        s->G=n3_full_triple_geometry(s->t[0],s->t[1],s->t[2]);
        s->shape=n3_triple_shape(s->t[0],s->t[1],s->t[2],
                                (unsigned)__builtin_popcountll(s->t[1]&s->t[2]));
        REQUIRE(s->G==n3_triple_geometry_lookup(geometry,s->shape));
        s->lower=n3_pair_overlap_lower_bound(&ctx,s->t[1],s->t[2]);
        REQUIRE(s->q<=s->G && s->lower>=0 && s->lower<=s->bc);
    }
    REQUIRE(target>0);
}

/* One complete pass remains observable; callers time repeated passes. */
static __attribute__((noinline)) int64_t arithmetic_pass(unsigned mode) {
    int64_t sum=0;
    for (unsigned i=0;i<NS;i++) {
        const Sample *s=samples+i;
        int64_t base=s->g[0]+s->g[1]-s->ab, gc=s->g[2]-s->ac;
        if (mode==0) sum+=n3_pair_bound(base,gc,s->ab,s->ac,s->bc);
        else if (mode<4) {
            int64_t G=n3_full_triple_geometry(s->t[0],s->t[1],s->t[2]);
            if (mode==1) sum+=G;
            if (mode==2) sum+=n3_geometric_pair_bound(base,gc,s->ab,s->ac,s->bc,G);
            if (mode==3) sum+=n3_geometric_lower_pair_bound(base,gc,s->ab,s->ac,s->lower,G);
        } else if (mode==4) {
            /* The solver already has bc from its lower gate. */
            N3TripleShape shape=n3_triple_shape(s->t[0],s->t[1],s->t[2],s->shape.bc);
            sum+=((shape.ab*7+shape.ac)*7+shape.bc)*7+shape.abc;
        } else {
            N3TripleShape shape=mode==5 ? s->shape :
                n3_triple_shape(s->t[0],s->t[1],s->t[2],s->shape.bc);
            int64_t G=n3_triple_geometry_lookup(geometry,shape);
            if (mode==5 || mode==6) sum+=G;
            if (mode==7) sum+=n3_geometric_pair_bound(base,gc,s->ab,s->ac,s->bc,G);
            if (mode==8) sum+=n3_geometric_lower_pair_bound(base,gc,s->ab,s->ac,s->lower,G);
        }
    }
    return sum;
}

/* 0=original; 1=previous direct-G prototype (unchanged gate order);
 * 2=installed LUT exact-pair gate; 3=lower-gate LUT alternative.
 * LUT modes short-circuit original safe rejects before shape/lookup work.
 * No mode caches residual pairs or calls a solver/evaluator. */
static __attribute__((noinline)) Counts pipeline(unsigned mode) {
    Counts count={0};
    for (unsigned i=0;i<NS;i++) {
        const Sample *s=samples+i;
        int64_t base=s->g[0]+s->g[1]-s->ab, gc=s->g[2]-s->ac;
        int64_t L=n3_pair_overlap_lower_bound(&ctx,s->t[1],s->t[2]);
        int64_t quick=n3_lower_pair_bound(base,gc,s->ab,s->ac,L);
        if (mode==3 && !n3_strict_prune(quick,target)) {
            N3TripleShape shape=n3_triple_shape(s->t[0],s->t[1],s->t[2],
                                 (unsigned)__builtin_popcountll(s->t[1]&s->t[2]));
            int64_t G=n3_triple_geometry_lookup(geometry,shape); count.g_calls++;
            quick=n3_geometric_lower_pair_bound(base,gc,s->ab,s->ac,L,G);
        }
        if (n3_strict_prune(quick,target)) {
            REQUIRE(s->F<target); count.rejects++; count.lower_rejects++; continue;
        }
        int64_t bc=n3_pair_overlap(&ctx,s->t[1],s->t[2]); count.pairs++;
        REQUIRE(bc==s->bc);
        int64_t bound=n3_pair_bound(base,gc,s->ab,s->ac,bc);
        if (mode==1) {
            int64_t G=n3_full_triple_geometry(s->t[0],s->t[1],s->t[2]); count.g_calls++;
            bound=n3_geometric_pair_bound(base,gc,s->ab,s->ac,bc,G);
        } else if (mode==2 && !n3_strict_prune(bound,target)) {
            N3TripleShape shape=n3_triple_shape(s->t[0],s->t[1],s->t[2],
                                 (unsigned)__builtin_popcountll(s->t[1]&s->t[2]));
            int64_t G=n3_triple_geometry_lookup(geometry,shape); count.g_calls++;
            bound=n3_geometric_pair_bound(base,gc,s->ab,s->ac,bc,G);
        }
        if (n3_strict_prune(bound,target)) { REQUIRE(s->F<target); count.rejects++; continue; }
        int64_t q=n3_triple_overlap(&ctx,s->t[0],s->t[1],s->t[2]); count.triples++;
        REQUIRE(q==s->q && base+gc-bc+q==s->F);
        count.checksum+=s->F;
    }
    sink+=count.checksum;
    return count;
}

static double median(double *v) {
    double a=v[0],b=v[1],c=v[2],t;
    if (a>b) { t=a; a=b; b=t; } if (b>c) { t=b; b=c; c=t; } if (a>b) b=a;
    return b;
}

/* Canonical binary input stream, explicit little-endian uint64 values:
 * nR, R masks, X masks, NE, events in generation order, NS, three masks/sample.
 * No struct padding, derived results, timings or addresses enter its SHA256. */
static void write_u64(FILE *f, uint64_t value) {
    for (unsigned j=0;j<8;j++) REQUIRE(fputc((int)((value>>(8*j))&255),f)!=EOF);
}
static void dump_input(const char *path) {
    FILE *f=fopen(path,"wb"); REQUIRE(f);
    write_u64(f,ctx.nR);
    for (int j=0;j<ctx.nR;j++) write_u64(f,ctx.Rmask[j]);
    for (unsigned j=0;j<3;j++) write_u64(f,ctx.Xmask[j]);
    write_u64(f,NE);
    for (unsigned j=0;j<NE;j++) write_u64(f,events[j]);
    write_u64(f,NS);
    for (unsigned j=0;j<NS;j++) for (unsigned k=0;k<3;k++) write_u64(f,samples[j].t[k]);
    REQUIRE(fclose(f)==0);
}

int main(int argc, char **argv) {
    n3_init_binom(); n3_init_kappa();
    clock_t cpu_start=clock(); double init_start=n3_now();
    geometry=n3_init_triple_geometry_table();
    double init_seconds=n3_now()-init_start;
    double init_cpu_seconds=(double)(clock()-cpu_start)/CLOCKS_PER_SEC;
    REQUIRE(geometry==n3_init_triple_geometry_table());
    setup();
    REQUIRE(sample_fingerprint==0x4e0b53247c1fa922ull && target==532);
    if (argc==3 && !strcmp(argv[1],"--dump-input")) dump_input(argv[2]);
    else REQUIRE(argc==1);
    double arithmetic[NARITH][NRUN],runtime[NPIPE][NRUN]; Counts results[NPIPE]={{0}};
    /* Warm each real kernel; no timed compile/setup and no background work. */
    for (unsigned j=0;j<NARITH;j++) sink+=arithmetic_pass(j);
    for (unsigned j=0;j<NPIPE;j++) results[j]=pipeline(j);
    for (unsigned run=0;run<NRUN;run++) {
        /* Rotate order to reduce fixed order bias. */
        for (unsigned j=0;j<NARITH;j++) {
            unsigned mode=(j+run)%NARITH; double start=n3_now();
            for (unsigned rep=0;rep<((mode==0 || mode>=4) ? OLD_REPEAT : REPEAT);rep++) {
                __asm__ volatile("" ::: "memory");
                sink+=arithmetic_pass(mode);
            }
            arithmetic[mode][run]=n3_now()-start;
        }
        for (unsigned j=0;j<NPIPE;j++) {
            unsigned mode=(j+run)%NPIPE; double start=n3_now();
            for (unsigned rep=0;rep<PIPELINE_REPEAT;rep++) {
                __asm__ volatile("" ::: "memory");
                Counts c=pipeline(mode);
                REQUIRE(c.rejects==results[mode].rejects && c.triples==results[mode].triples);
            }
            runtime[mode][run]=(n3_now()-start)/PIPELINE_REPEAT;
        }
    }
    for (unsigned j=1;j<NPIPE;j++) REQUIRE(results[j].rejects>=results[0].rejects);
    REQUIRE(results[1].rejects==results[2].rejects && results[1].checksum==results[2].checksum);
    const char *anames[NARITH]={"OLD_BOUND","G_ONLY","NEW_BOUND_INCLUDING_G","LOWER_BOUND_INCLUDING_G",
        "SHAPE_INDEX_REUSING_BC","LOOKUP_ONLY","LUT_G_INCLUDING_INDEX","NEW_BOUND_LUT","LOWER_BOUND_LUT"};
    const char *pnames[NPIPE]={"PROTOTYPE_OFF","EXACT_PAIR_DIRECT_G","EXACT_PAIR_LUT","LOWER_GATE_LUT"};
    printf("{\"SAMPLE_COUNT\":%d,\"RESIDUAL_EVENT_SAMPLE_COUNT\":%d,\"STRATUM_SIZE\":128,"
           "\"MEASUREMENTS\":%d,\"G_REPETITIONS\":%d,\"OLD_REPETITIONS\":%d,"
           "\"PIPELINE_REPETITIONS\":%d,\"D_SAMPLE\":%" PRId64
           ",\"SEED_HEX\":\"649b64920261016\",\"FINGERPRINT_HEX\":\"%016" PRIx64 "\","
           "\"DOMAIN\":\"1..49\",\"FULL_C2_RESIDUAL\":false,"
           "\"LUT_BYTES\":%zu,\"LUT_INITIALIZATION_SECONDS\":%.9f,"
           "\"LUT_INITIALIZATION_CPU_SECONDS\":%.9f,\"ARITHMETIC\":{",
           NS,NE,NRUN,REPEAT,OLD_REPEAT,PIPELINE_REPEAT,target,sample_fingerprint,
           sizeof *geometry,init_seconds,init_cpu_seconds);
    for (unsigned j=0;j<NARITH;j++) {
        printf("%s\"%s\":{\"SECONDS\":[%.9f,%.9f,%.9f],\"MEDIAN_NS_PER_CANDIDATE\":%.3f}",
            j?",":"",anames[j],arithmetic[j][0],arithmetic[j][1],arithmetic[j][2],
            median(arithmetic[j])*1e9/(NS*((j==0 || j>=4) ? OLD_REPEAT : REPEAT)));
    }
    printf("},\"PIPELINES\":{");
    for (unsigned j=0;j<NPIPE;j++)
        printf("%s\"%s\":{\"SECONDS\":[%.9f,%.9f,%.9f],\"MEDIAN_SECONDS\":%.9f,"
               "\"SAFE_REJECTS\":%" PRIu64 ",\"LOWER_REJECTS\":%" PRIu64
               ",\"PAIR_CALLS\":%" PRIu64 ",\"TRIPLE_CALLS\":%" PRIu64
               ",\"G_CALLS_PER_PASS\":%" PRIu64
               ",\"G_CALLS_TIMED\":%" PRIu64 ",\"G_CALLS_WITH_WARMUP\":%" PRIu64 "}",
            j?",":"",pnames[j],runtime[j][0],runtime[j][1],runtime[j][2],median(runtime[j]),
            results[j].rejects,results[j].lower_rejects,results[j].pairs,results[j].triples,
            results[j].g_calls,results[j].g_calls*NRUN*PIPELINE_REPEAT,
            results[j].g_calls*(1+NRUN*PIPELINE_REPEAT));
    printf("},\"ADDITIONAL_SAFE_REJECTS\":%" PRIu64 ",\"NET_SECONDS_SAVED\":%.9f,"
           "\"PEAK_RSS_BYTES\":%zu,\"MISMATCHES\":0,\"FORMAL_N3_SOLVER_CALLS\":0,"
           "\"CANONICAL_SCORING_CALLS\":0}\n",results[2].rejects-results[0].rejects,
           median(runtime[0])-median(runtime[2]),n3_peak_rss());
    free(ctx.U); free(ctx.N3); free(ctx.N4); free(ctx.N5); free(ctx.N6);
    return sink==-1;
}
