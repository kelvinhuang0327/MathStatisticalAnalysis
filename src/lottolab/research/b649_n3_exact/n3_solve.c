/* R2 exact complete-N3 search. Global anchors still use (r desc, colex asc).
 * For each anchor, sort ALL potentially competitive suffix tickets by the exact
 * conditional marginal gA(T)=r(T)-i(A,T). Discarding the other suffix tickets
 * follows rA+r(a+1)+r(T)<target, never a fixed ticket/pool size cutoff.
 * Conditional blocks use rA+gA(B)+gA(C), retaining equality. Pair and leaf values
 * remain the R1 inclusion-exclusion formula. A bounded exact-key overlap cache
 * changes only recomputation, never which candidates are searched.
 */
#include "n3_solve.h"
#include "n3_bounds.h"

uint64_t n3_anchor_limit = 0;
unsigned n3_cache_bits = 0;

typedef struct {
    uint64_t *keys;
    int32_t *values;
    uint64_t mask;
    Solver *s;
    const Ctx *c;
} PairCache;

static int cmp_cand(const void *pa, const void *pb) {
    const Cand *a = pa, *b = pb;
    if (a->r != b->r) return a->r > b->r ? -1 : 1;
    return a->rank < b->rank ? -1 : a->rank > b->rank;
}

static int64_t cached_pair(PairCache *p, const Cand *a, const Cand *b) {
    if (!p->keys) {
        p->s->cache_misses++;
        return n3_pair_overlap(p->c, a->mask, b->mask);
    }
    uint32_t lo = a->rank < b->rank ? a->rank : b->rank;
    uint32_t hi = a->rank < b->rank ? b->rank : a->rank;
    /* NT6 < 2^24; rank identities are exact, fingerprints never merge pairs. */
    uint64_t key = (((uint64_t)lo << 24) | hi) + 1;
    uint64_t slot = splitmix64(key) & p->mask;
    if (p->keys && p->keys[slot] == key) {
        p->s->cache_hits++;
#ifdef MUTANT_CACHE_VALUE
        return p->values[slot] + 1;
#else
        return p->values[slot];
#endif
    }
    int64_t value = n3_pair_overlap(p->c, a->mask, b->mask);
    p->s->cache_misses++;
    if (p->keys) {
        p->values[slot] = (int32_t)value;
        p->keys[slot] = key;
    }
    return value;
}

static void record(Solver *s, const Cand *a, const Cand *b, const Cand *c, int64_t value) {
    if (value > s->target) {
        s->target = value;
        s->improved = 1;
        s->tie_count = 0;
        s->ties_stored = 0;
    }
    if (value == s->target) {
        s->tie_count++;
        if (s->ties_stored < MAX_TIES_STORED) {
            uint32_t *t = s->ties + 3 * s->ties_stored++;
            t[0] = a->rank; t[1] = b->rank; t[2] = c->rank;
        }
    }
}

static int64_t max64(int64_t a, int64_t b) { return a > b ? a : b; }
static int pow2(uint64_t a) { return a && !(a & (a - 1)); }

void solver_run(Solver *s, const Ctx *ctx, int64_t F0, double tl, int verbose) {
    double t0 = n3_now();
    memset(s, 0, sizeof *s);
    s->incumbent = s->target = F0;
    s->time_limit_s = tl;
    s->a_break_position = -1;
    s->open_upper_bound = -1;
    uint64_t n = NT6;
    int64_t rho = 0;
    for (uint64_t i = 0; i < n; i++) if (ctx->r[i] > rho) rho = ctx->r[i];
    s->rmin = F0 - 2 * rho;
    if (s->rmin < 0) s->rmin = 0;
    uint64_t L = 0;
    for (uint64_t i = 0; i < n; i++) if (ctx->r[i] >= s->rmin) L++;
    s->list = malloc(sizeof(Cand) * (L + 1));
    s->ties = malloc(sizeof(uint32_t) * 3 * MAX_TIES_STORED);
    Cand *conditional = malloc(sizeof(Cand) * (L + 1));
    if (!s->list || !s->ties || !conditional) { fprintf(stderr, "search allocation failed\n"); exit(3); }
    uint64_t q = 0;
    for (uint64_t i = 0; i < n; i++) if (ctx->r[i] >= s->rmin)
        s->list[q++] = (Cand){n3_unrank6((uint32_t)i), (uint32_t)i, ctx->r[i]};
    qsort(s->list, L, sizeof(Cand), cmp_cand);
    s->L = L;
    s->accounted = choose3_128(n) - choose3_128(L);
    const Cand *list = s->list;
    for (uint64_t a = 0; a + 2 < L; a++) {
        if ((int64_t)list[a].r + list[a + 1].r + list[a + 2].r < F0) break;
        s->a_bound_count++;
    }
    PairCache pc = {.s = s, .c = ctx};
    if (n3_cache_bits) {
        if (n3_cache_bits > 25) { fprintf(stderr, "cache bits must be <=25\n"); exit(2); }
        uint64_t slots = 1ull << n3_cache_bits;
        pc.mask = slots - 1;
        pc.keys = calloc(slots, sizeof(uint64_t));
        pc.values = malloc(slots * sizeof(int32_t));
        if (!pc.keys || !pc.values) { fprintf(stderr, "cache allocation failed\n"); exit(3); }
    }
    double last_report = t0;
    for (uint64_t a = 0; a + 2 < L; a++) {
        int64_t rA = list[a].r;
        int64_t global = rA + list[a + 1].r + list[a + 2].r;
        if (global < s->target) {
            s->accounted += choose3_128(L - a);
            s->a_break_position = (int64_t)a;
            s->closed = 1;
            break;
        }
        if ((n3_anchor_limit && a >= n3_anchor_limit) || n3_now() - t0 >= tl) {
            s->stop_reason = n3_anchor_limit && a >= n3_anchor_limit ? 2 : 1;
            s->open_upper_bound = global;
            break;
        }
        s->a_explored++;
        s->a_last = a;
        int64_t next_global = a + 3 < L ?
            (int64_t)list[a + 1].r + list[a + 2].r + list[a + 3].r : -1;
        /* No pair containing a ticket below this threshold can attain target. */
        int64_t threshold = s->target - rA - list[a + 1].r;
#ifdef MUTANT_SUFFIX_CUTOFF
        threshold++;
#endif
        uint64_t lo = a + 1, hi = L;
        while (lo < hi) {
            uint64_t mid = lo + (hi - lo) / 2;
            if (list[mid].r >= threshold) lo = mid + 1;
            else hi = mid;
        }
        uint64_t m = lo - (a + 1);
        s->accounted += choose2_128(L - a - 1) - choose2_128(m);
        double tc = n3_now();
        int timeout = 0;
        for (uint64_t i = 0; i < m; i++) {
            const Cand *c = list + a + 1 + i;
            conditional[i] = *c;
            conditional[i].r -= (int32_t)cached_pair(&pc, list + a, c);
            s->gA_evals++;
            if ((i & 4095) == 0 && n3_now() - t0 >= tl) {
                timeout = 1;
                s->open_upper_bound = global;
                break;
            }
        }
        s->conditional_candidates += m;
        if (!timeout) qsort(conditional, m, sizeof(Cand), cmp_cand);
        s->seconds_conditional += n3_now() - tc;
        if (timeout) { s->stop_reason = 1; break; }
        if (m < 2 || n3_strict_prune(n3_two_slot_bound(rA, conditional[0].r,
                                                     conditional[1].r), s->target)) {
            s->accounted += choose2_128(m);
            s->anchors_pruned_conditional++;
        } else for (uint64_t b = 0; b + 1 < m; b++) {
            const Cand *B = conditional + b;
            int64_t ub = n3_two_slot_bound(rA, B->r, conditional[b + 1].r);
            if (n3_strict_prune(ub, s->target)) {
                s->accounted += choose2_128(m - b);
                s->b_loop_breaks++;
                break;
            }
            s->b_explored++;
            int64_t iAB = (int64_t)ctx->r[B->rank] - B->r;
            int64_t base = rA + B->r;
            for (uint64_t c = b + 1; c < m; c++) {
                const Cand *C = conditional + c;
                int64_t marginal_ub = n3_two_slot_bound(rA, B->r, C->r);
                if (n3_strict_prune(marginal_ub, s->target)) {
                    s->accounted += m - c;
                    s->c_loop_breaks++;
                    break;
                }
                if ((s->lower_calls & 4095) == 0 && n3_now() - t0 >= tl) {
                    timeout = 1;
                    /* Current C tail, later B blocks, and later global anchors. */
                    s->open_upper_bound = max64(max64(marginal_ub, ub), next_global);
                    break;
                }
                int64_t iAC = (int64_t)ctx->r[C->rank] - C->r;
                s->lower_calls++;
                unsigned shared = __builtin_popcountll(B->mask & C->mask);
                if (shared <= 6) s->pair_shared[shared]++;
                int64_t lower = n3_pair_overlap_lower_bound(ctx, B->mask, C->mask);
                int64_t quick = n3_lower_pair_bound(base, C->r, iAB, iAC, lower);
                if (n3_strict_prune(quick, s->target)) {
                    s->accounted++;
                    s->leaves_pruned_lower++;
                    if (pow2(s->leaves_pruned_lower)) {
                        uint64_t tickets[3] = {list[a].mask, B->mask, C->mask};
                        int64_t exact = n3_direct_union(ctx, tickets, 3);
                        s->prune_audits++;
                        if (exact > quick || exact >= s->target) s->prune_audit_failures++;
                    }
                    continue;
                }
                int64_t iBC = cached_pair(&pc, B, C);
                s->pair_calls++;
                int64_t bound = n3_pair_bound(base, C->r, iAB, iAC, iBC);
                s->accounted++;
                if (n3_strict_prune(bound, s->target)) {
                    s->leaves_pruned_pair++;
                    if (pow2(s->leaves_pruned_pair)) {
                        uint64_t tickets[3] = {list[a].mask, B->mask, C->mask};
                        int64_t exact = n3_direct_union(ctx, tickets, 3);
                        s->prune_audits++;
                        if (exact > bound || exact >= s->target) s->prune_audit_failures++;
                    }
                    continue;
                }
                int64_t iABC = n3_triple_overlap(ctx, list[a].mask, B->mask, C->mask);
                s->triple_calls++;
                s->leaves_exact++;
                int64_t value = base + C->r - iBC + iABC;
                if (pow2(s->leaves_exact) || (value >= s->target && s->leaf_audits_at_best < 8)) {
                    uint64_t tickets[3] = {list[a].mask, B->mask, C->mask};
                    int64_t exact = n3_direct_union(ctx, tickets, 3);
                    s->leaf_audits++;
                    if (value >= s->target) s->leaf_audits_at_best++;
                    if (value != exact) s->leaf_audit_failures++;
                }
                record(s, list + a, B, C, value);
            }
            if (timeout) break;
        }
        if (timeout) { s->stop_reason = 1; break; }
        s->anchors_completed++;
        double now = n3_now();
        if (verbose && now - last_report >= 30) {
            last_report = now;
            fprintf(stderr, "{\"progress\":{\"elapsed\":%.3f,\"anchors_completed\":%llu,"
                    "\"anchors_total\":%llu,\"conditional_pruned\":%llu,\"rA\":%lld,"
                    "\"target\":%lld,\"upper_bound\":%lld,\"pair_requests\":%llu,"
                    "\"cache_hits\":%llu,\"cache_misses\":%llu}}\n", now-t0,
                    (unsigned long long)s->anchors_completed, (unsigned long long)s->a_bound_count,
                    (unsigned long long)s->anchors_pruned_conditional, (long long)rA,
                    (long long)s->target, (long long)max64(s->target, next_global),
                    (unsigned long long)s->pair_calls, (unsigned long long)s->cache_hits,
                    (unsigned long long)s->cache_misses);
        }
    }
    /* Exhausted all anchors (including n<3). */
    if (!s->stop_reason) s->closed = 1;
    s->seconds = n3_now() - t0;
    free(conditional);
    free(pc.keys);
    free(pc.values);
}
