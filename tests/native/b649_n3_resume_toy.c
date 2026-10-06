/* Anchor-resume contract test using a 12-ticket synthetic coverage universe. */
#define _POSIX_C_SOURCE 200809L
#include "n3_solve.h"
#include "n3_checkpoint.h"
#include <time.h>

static uint64_t signatures[NT6];
static uint64_t random_state = 0x649b649u;
uint32_t BIN[64][9];

double n3_now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC,&t);
    return (double)t.tv_sec+(double)t.tv_nsec*1e-9;
}
uint64_t n3_unrank6(uint32_t rank) { return signatures[rank]; }
int64_t n3_pair_overlap(const Ctx *c,uint64_t a,uint64_t b) {
    (void)c; return __builtin_popcountll(a&b);
}
int64_t n3_pair_overlap_lower_bound(const Ctx *c,uint64_t a,uint64_t b) {
    (void)c; return __builtin_popcountll(a&b&0x5555555555555555ull);
}
int64_t n3_triple_overlap(const Ctx *c,uint64_t a,uint64_t b,uint64_t z) {
    (void)c; return __builtin_popcountll(a&b&z);
}
uint64_t n3_direct_union(const Ctx *c,const uint64_t *a,int n) {
    (void)c; uint64_t mask=0;
    for(int i=0;i<n;i++) mask|=a[i];
    return (uint64_t)__builtin_popcountll(mask);
}
static uint64_t next_random(void) { random_state=splitmix64(random_state); return random_state; }

static void init_case(Ctx *ctx,int32_t r[NT6],int prune_case) {
    if(prune_case) {
        signatures[0]=(1ull<<40)-1;
        signatures[1]=0xfull<<40;
        signatures[2]=0xfull<<44;
        for(unsigned i=3;i<NT6;i++) signatures[i]=1ull<<(i-3);
        for(unsigned i=0;i<NT6;i++) r[i]=__builtin_popcountll(signatures[i]);
        ctx->r=r;
        return;
    }
    for(unsigned i=0;i<NT6;i++) {
        signatures[i]=next_random() & 0x0000ffffffffffffull;
        if(i%4==0) signatures[i]&=0x00000000ffffffffull;
        r[i]=__builtin_popcountll(signatures[i]);
    }
    ctx->r=r;
}

static SolverResumeConfig config_for(const char *path,int drift,int prune_case) {
    SolverResumeConfig cfg={
        .path=path,
        .destroy_set="0000000000000001,0000000000000002,0000000000000004",
        .input_sha256=drift?"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd":
            prune_case?"1111111111111111111111111111111111111111111111111111111111111111":
                       "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        .engine_sha256="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        .solver_config_sha256="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    };
    return cfg;
}

static void release(Solver *s) { free(s->list); free(s->ties); }

static void print_result(const Solver *s,int rc) {
    printf("{\"RETURN_CODE\":%d,\"CLOSED\":%s,\"BEST_F\":%lld,\"TIE_COUNT\":%llu,"
           "\"TIES_STORED\":%llu,\"TIES\":[",rc,s->closed?"true":"false",(long long)s->target,
           (unsigned long long)s->tie_count,(unsigned long long)s->ties_stored);
    for(uint64_t i=0;i<s->ties_stored;i++)
        printf("%s[%u,%u,%u]",i?",":"",s->ties[3*i],s->ties[3*i+1],s->ties[3*i+2]);
    printf("],\"A_BOUND_COUNT\":%llu,\"A_EXPLORED\":%llu,\"ANCHORS_COMPLETED\":%llu,"
           "\"CHECKPOINT_ANCHORS_RECORDED\":%llu,\"TRIPLES_ACCOUNTED\":\"",
           (unsigned long long)s->a_bound_count,(unsigned long long)s->a_explored,
           (unsigned long long)s->anchors_completed,(unsigned long long)s->checkpoint_anchor_records);
    char accounted[64]; u128_to_str(s->accounted,accounted);
    printf("%s\",\"JOURNAL_PREFIX_SHA256\":\"%s\"}\n",accounted,s->checkpoint_prefix_sha256);
}

int main(int argc,char **argv) {
    if(argc<2) return 2;
    char sha[65];
    n3_sha256_hex("abc",3,sha);
    if(strcmp(sha,"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")) {
        fprintf(stderr,"SHA256_IMPLEMENTATION_MISMATCH\n"); return 3;
    }
    int prune_case=strstr(argv[1],"-prune")!=NULL;
    int32_t r[NT6]; Ctx ctx={0}; init_case(&ctx,r,prune_case);
    int64_t f0=0;
    if(!strcmp(argv[1],"full") || !strcmp(argv[1],"full-prune")) {
        Solver s; solver_run(&s,&ctx,f0,100,0); print_result(&s,0); release(&s); return 0;
    }
    if(argc<3) return 2;
    int drift=!strcmp(argv[1],"bad-input");
    SolverResumeConfig cfg=config_for(argv[2],drift,prune_case);
    if(!strcmp(argv[1],"partial") || !strcmp(argv[1],"partial-prune")) {
        Solver s;
        int rc=solver_run_durable(&s,&ctx,f0,100,0,&cfg,1);
        if(rc) return rc;
        print_result(&s,rc); release(&s); return 0;
    }
    if(!strcmp(argv[1],"resume") || !strcmp(argv[1],"resume-prune")) {
        Solver s;
        int rc=solver_run_durable(&s,&ctx,f0,100,0,&cfg,0);
        if(rc) return rc;
        print_result(&s,rc); release(&s); return 0;
    }
    if(!strcmp(argv[1],"bad-input") || !strcmp(argv[1],"bad-engine") ||
       !strcmp(argv[1],"bad-config") || !strcmp(argv[1],"bad-destroy") ||
       !strcmp(argv[1],"bad-f0")) {
        if(!strcmp(argv[1],"bad-engine"))
            cfg.engine_sha256="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";
        else if(!strcmp(argv[1],"bad-config"))
            cfg.solver_config_sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff";
        else if(!strcmp(argv[1],"bad-destroy"))
            cfg.destroy_set="0000000000000008,0000000000000010,0000000000000020";
        Solver s;
        int64_t requested_f0=!strcmp(argv[1],"bad-f0") ? 1 : f0;
        int rc=solver_run_durable(&s,&ctx,requested_f0,100,0,&cfg,0);
        if(rc==0) { release(&s); fprintf(stderr,"DRIFT_WAS_ACCEPTED\n"); return 4; }
        puts("{\"DRIFT_FAIL_CLOSED\":\"PASS\"}");
        return 0;
    }
    return 2;
}
