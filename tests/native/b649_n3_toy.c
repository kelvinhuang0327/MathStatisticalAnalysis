/* The production R2 and preserved R1 search execute against an independent
   explicit coverage-set oracle. NT6 is compiled to 12, with no solver rewrite. */
#include "n3_solve.h"
#include "n3_bounds.h"
#include <time.h>

static uint64_t signatures[NT6];
static uint64_t state = 0x5eed649;
uint32_t BIN[64][9];

double n3_now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec * 1e-9;
}
uint64_t n3_unrank6(uint32_t rank) { return signatures[rank]; }
int64_t n3_pair_overlap(const Ctx *c, uint64_t a, uint64_t b) {
    (void)c; return __builtin_popcountll(a & b);
}
int64_t n3_pair_overlap_lower_bound(const Ctx *c, uint64_t a, uint64_t b) {
    (void)c; return __builtin_popcountll(a & b & 0xaaaaaaaaaaaaaaaaull);
}
int64_t n3_triple_overlap(const Ctx *c, uint64_t a, uint64_t b, uint64_t z) {
    (void)c; return __builtin_popcountll(a & b & z);
}
uint64_t n3_direct_union(const Ctx *c, const uint64_t *a, int n) {
    (void)c;
    uint64_t mask = 0;
    for (int i = 0; i < n; i++) mask |= a[i];
    return __builtin_popcountll(mask);
}
static uint64_t random64(void) { state = splitmix64(state); return state; }
static void release(Solver *s) { free(s->list); free(s->ties); }
static int exact_ties_match(const Solver *s, const uint8_t *expected) {
    uint8_t seen[NT6 * NT6 * NT6] = {0};
    for (uint64_t i = 0; i < s->ties_stored; i++) {
        unsigned a = s->ties[3*i], b = s->ties[3*i+1], c = s->ties[3*i+2];
        if (a > b) { unsigned t = a; a = b; b = t; }
        if (b > c) { unsigned t = b; b = c; c = t; }
        if (a > b) { unsigned t = a; a = b; b = t; }
        unsigned idx = (a * NT6 + b) * NT6 + c;
        if (seen[idx]) return 0;
        seen[idx] = 1;
    }
    return !memcmp(seen, expected, sizeof seen);
}

int main(void) {
    uint64_t bounds = 0, cases = 0, legacy_cases = 0, timeout_checks = 0;
    uint64_t zero_cases = 0;
    n3_cache_bits = 3; /* deliberate collisions/eviction */
    for (unsigned trial = 0; trial < 600; trial++) {
        int32_t r[NT6];
        Ctx ctx = {.r = r};
        unsigned density = 1 + trial % 5;
        for (unsigned a = 0; a < NT6; a++) {
            uint64_t m = random64();
            for (unsigned k = 1; k < density; k++) m &= random64();
            signatures[a] = m;
            if (trial % 7 == 0 && a == 2) signatures[a] = signatures[1];
            if (trial % 11 == 0 && a == 4) signatures[a] = 0;
            r[a] = __builtin_popcountll(signatures[a]);
        }
        if (trial == 0) for (unsigned a = 0; a < NT6; a++) {
            signatures[a] = 0xffull << (8 * (a % 4)); r[a] = 8;
        }
        if (trial == 1) for (unsigned a = 0; a < NT6; a++) signatures[a] = r[a] = 0;
        int64_t optimum = 0, rho = 0;
        uint64_t ties = 0;
        uint8_t expected[NT6 * NT6 * NT6] = {0};
        for (unsigned a = 0; a < NT6; a++) {
            if (r[a] > rho) rho = r[a];
            for (unsigned b = a+1; b < NT6; b++) for (unsigned c = b+1; c < NT6; c++) {
                int64_t exact = __builtin_popcountll(signatures[a] | signatures[b] | signatures[c]);
                if (exact > optimum) { optimum = exact; ties = 0; memset(expected, 0, sizeof expected); }
                if (exact == optimum) { ties++; expected[(a * NT6 + b) * NT6 + c] = 1; }
                unsigned t[3] = {a,b,c};
                for (unsigned k = 0; k < 3; k++) {
                    uint64_t A = signatures[t[k]], B = signatures[t[(k+1)%3]], C = signatures[t[(k+2)%3]];
                    int64_t ra = __builtin_popcountll(A), rb = __builtin_popcountll(B), rc = __builtin_popcountll(C);
                    int64_t iab = __builtin_popcountll(A&B), iac = __builtin_popcountll(A&C), ibc = __builtin_popcountll(B&C);
                    int64_t ub = n3_two_slot_bound(ra, rb-iab, rc-iac);
                    int64_t pb = n3_pair_bound(ra+rb-iab, rc-iac, iab,iac,ibc);
                    int64_t lower = n3_pair_overlap_lower_bound(&ctx,B,C);
                    int64_t quick = n3_lower_pair_bound(ra+rb-iab,rc-iac,iab,iac,lower);
                    if (ub < exact || pb < exact || quick < exact) { fprintf(stderr,"BOUND_INADMISSIBLE trial=%u\n",trial); return 1; }
                    bounds += 3;
                }
            }
        }
        /* Lower incumbent and exact-optimum incumbent: both improvement and ties. */
        for (int exact_incumbent = 0; exact_incumbent < 2; exact_incumbent++) {
            int64_t f0 = exact_incumbent ? optimum :
                __builtin_popcountll(signatures[0]|signatures[1]|signatures[2]);
            Solver sol;
            n3_anchor_limit = 0;
            solver_run(&sol,&ctx,f0,10,0);
            if (!sol.closed || sol.target != optimum || sol.tie_count != ties ||
                sol.ties_stored != ties || !exact_ties_match(&sol, expected) ||
                sol.accounted != choose3_128(NT6) || sol.prune_audit_failures || sol.leaf_audit_failures) {
                fprintf(stderr,"BRUTE_PARITY_MISMATCH trial=%u best=%lld true=%lld ties=%llu true_ties=%llu accounted=%lld\n",
                        trial,(long long)sol.target,(long long)optimum,(unsigned long long)sol.tie_count,
                        (unsigned long long)ties,(long long)sol.accounted); return 1;
            }
            release(&sol);
            cases++;
            if (f0 == 0) zero_cases++;
            /* R1's rmin>=1 was only valid in the real task's F0>2*rho regime. */
            if (f0 > 2*rho) {
                solver_run_legacy(&sol,&ctx,f0,10,0);
                if (!sol.closed || sol.target != optimum || sol.tie_count != ties ||
                    !exact_ties_match(&sol, expected) || sol.accounted != choose3_128(NT6)) {
                    fprintf(stderr,"OLD_NEW_PARITY_MISMATCH trial=%u\n",trial); return 1;
                }
                legacy_cases++;
                release(&sol);
            }
            /* Every work-limited frontier bound must cover the global optimum. */
            n3_anchor_limit = 1;
            solver_run(&sol,&ctx,f0,10,0);
            if ((!sol.closed && sol.open_upper_bound < optimum) ||
                (sol.closed && sol.target != optimum) || sol.accounted > choose3_128(NT6)) {
                fprintf(stderr,"FRONTIER_INADMISSIBLE trial=%u\n",trial); return 1;
            }
            timeout_checks++;
            release(&sol);
            n3_anchor_limit = 0;
            solver_run(&sol,&ctx,f0,0,0);
            if ((!sol.closed && sol.open_upper_bound < optimum) ||
                (sol.closed && sol.target != optimum) || sol.accounted > choose3_128(NT6)) {
                fprintf(stderr,"TIMEOUT_FRONTIER_INADMISSIBLE trial=%u\n",trial); return 1;
            }
            timeout_checks++;
            release(&sol);
        }
    }
    printf("{\"BRUTE_CASES\":%llu,\"OLD_NEW_PARITY_CASES\":%llu,\"BOUND_CHECKS\":%llu,"
           "\"FRONTIER_CHECKS\":%llu,\"ZERO_INCUMBENT_CASES\":%llu,\"MISMATCHES\":0}\n",
           (unsigned long long)cases,(unsigned long long)legacy_cases,(unsigned long long)bounds,
           (unsigned long long)timeout_checks,(unsigned long long)zero_cases);
    return 0;
}
