/* Exact complete-universe three-ticket repair by branch and bound.
 *
 * Order every legal ticket by (r desc, colex rank asc); an unordered triple of distinct
 * tickets is visited once as positions a < b < c.  F(A,B,C) = r(A) + g_A(B) + g_AB(C) with
 * g_A(T) = r(T) - i(A,T).  Admissible bounds (all proven upper bounds on F):
 *   A-loop break  : r(a) + r(a+1) + r(a+2)            (every triple with first position >= a)
 *   B-loop break  : r(A) + r(b) + r(b+1)              (every triple (A, b' >= b, c'))
 *   B prune       : r(A) + g_A(B) + r(b+1)            (submodularity: g_AB(C) <= g_A(C) <= r(C))
 *   C-loop break  : r(A) + g_A(B) + r(c)
 *   leaf marginal : r(A) + g_A(B) + g_A(C)
 *   leaf pair     : r(A) + g_A(B) + g_A(C) - i(B,C) + min(i(A,B), i(A,C), i(B,C))
 * A node is cut only when its bound is strictly below the current best, so every triple
 * attaining the final optimum is evaluated exactly (complete tie enumeration).  Exact leaf
 * value: r(A) + r(B) + r(C) - i(A,B) - i(A,C) - i(B,C) + i(A,B,C).
 * Accounting: every triple is either one exact/pruned leaf or inside an eliminated block of
 * known size; at closure the total equals C(13983816, 3). */
#include "n3_solve.h"

static int cmp_cand(const void *pa, const void *pb) {
    const Cand *x = pa, *y = pb;
    if (x->r != y->r) return (x->r > y->r) ? -1 : 1;
    return (x->rank < y->rank) ? -1 : (x->rank > y->rank);
}

__int128 choose3_128(uint64_t n) { return n < 3 ? 0 : (__int128)n * (n - 1) * (n - 2) / 6; }
__int128 choose2_128(uint64_t n) { return n < 2 ? 0 : (__int128)n * (n - 1) / 2; }

void u128_to_str(__int128 v, char *buf) {
    char tmp[64];
    int k = 0;
    if (v == 0) { strcpy(buf, "0"); return; }
    while (v > 0) { tmp[k++] = (char)('0' + (int)(v % 10)); v /= 10; }
    for (int i = 0; i < k; i++) buf[i] = tmp[k - 1 - i];
    buf[k] = 0;
}

typedef struct {
    uint64_t A;
    int32_t *iA;
    uint32_t *stamp;
    uint32_t version;
    const Ctx *c;
    const Cand *list;
    uint64_t *gA_evals;
} AMemo;

/* i(A, T) for the current anchor A, exact (kappa-Moebius), memoized per anchor */
static inline int64_t iA_at(AMemo *m, uint64_t pos) {
    if (m->stamp[pos] != m->version) {
        m->stamp[pos] = m->version;
        m->iA[pos] = (int32_t)n3_pair_overlap(m->c, m->A, m->list[pos].mask);
        (*m->gA_evals)++;
    }
    return m->iA[pos];
}

static void record_tie(Solver *s, uint32_t a, uint32_t b, uint32_t cc) {
    if (s->ties_stored < MAX_TIES_STORED) {
        s->ties[3 * s->ties_stored + 0] = a;
        s->ties[3 * s->ties_stored + 1] = b;
        s->ties[3 * s->ties_stored + 2] = cc;
        s->ties_stored++;
    }
}

static inline int is_pow2(uint64_t x) { return x && !(x & (x - 1)); }

/* brute-force F(A,B,C) by explicit enumeration of the three coverage sets */
static int64_t direct_F(const Ctx *c, uint64_t A, uint64_t B, uint64_t C) {
    uint64_t t[3] = {A, B, C};
    return (int64_t)n3_direct_union(c, t, 3);
}

void solver_run_legacy(Solver *s, const Ctx *c, int64_t F0, double tl, int verbose) {
    memset(s, 0, sizeof *s);
    s->incumbent = F0;
    s->target = F0;
    s->time_limit_s = tl;
    s->a_break_position = -1;
    const uint64_t n = NT6;
    int64_t rho = 0;
    for (uint64_t i = 0; i < n; i++)
        if (c->r[i] > rho) rho = c->r[i];
    s->rmin = F0 - 2 * rho;
    if (s->rmin < 1) s->rmin = 1;
    uint64_t L = 0;
    for (uint64_t i = 0; i < n; i++)
        if (c->r[i] >= s->rmin) L++;
    s->list = malloc(sizeof(Cand) * (L + 1));
    uint64_t q = 0;
    for (uint64_t i = 0; i < n; i++)
        if (c->r[i] >= s->rmin) { s->list[q].mask = n3_unrank6((uint32_t)i); s->list[q].rank = (uint32_t)i; s->list[q].r = c->r[i]; q++; }
    qsort(s->list, L, sizeof(Cand), cmp_cand);
    s->L = L;
    const Cand *list = s->list;
    const int64_t below = s->rmin - 1; /* every position >= L has r <= rmin - 1 */
#define RAT(pos) ((pos) < L ? (int64_t)list[(pos)].r : below)

    s->ties = malloc(sizeof(uint32_t) * 3 * MAX_TIES_STORED);
    for (uint64_t a = 0; RAT(a) + RAT(a + 1) + RAT(a + 2) >= F0; a++) s->a_bound_count++;
    AMemo memo;
    memo.A = 0;
    memo.iA = malloc(sizeof(int32_t) * (L + 1));
    memo.stamp = calloc(L + 1, sizeof(uint32_t));
    memo.version = 0;
    memo.c = c;
    memo.list = list;
    memo.gA_evals = &s->gA_evals;

    double t0 = n3_now(), last_report = t0;
    s->open_upper_bound = -1;
    for (uint64_t a = 0;; a++) {
        if (n3_anchor_limit && a >= n3_anchor_limit) {
            s->stop_reason = 2;
            s->open_upper_bound = RAT(a) + RAT(a + 1) + RAT(a + 2);
            break;
        }
        int64_t T = s->target;
        int64_t rA = RAT(a);
        if (rA + RAT(a + 1) + RAT(a + 2) < T) {
            s->accounted += choose3_128(n - a);
            s->a_break_position = (int64_t)a;
            s->closed = 1;
            break;
        }
        if (n3_now() - t0 > tl) {
            s->stop_reason = 1;
            s->open_upper_bound = rA + RAT(a + 1) + RAT(a + 2);
            break;
        }
        s->a_explored++;
        s->a_last = a;
        const uint64_t A = list[a].mask;
        memo.A = A;
        memo.version++;
        int timed_out = 0;
        for (uint64_t b = a + 1;; b++) {
            T = s->target;
            int64_t rB = RAT(b), rBn = RAT(b + 1);
            if (rA + rB + rBn < T) {
                s->accounted += choose2_128(n - b);
                s->b_loop_breaks++;
                break;
            }
            if ((b & 255) == 0) {
                double now = n3_now();
                if (now - t0 > tl) {
                    timed_out = 1;
                    int64_t ub_here = rA + rB + rBn, ub_next = RAT(a + 1) + RAT(a + 2) + RAT(a + 3);
                    s->open_upper_bound = ub_here > ub_next ? ub_here : ub_next;
                    break;
                }
                if (verbose && now - last_report > 30.0) {
                    last_report = now;
                    fprintf(stderr, "{\"progress\":{\"elapsed\":%.1f,\"a\":%llu,\"b\":%llu,\"rA\":%lld,\"rB\":%lld,\"target\":%lld,\"b_explored\":%llu,\"leaves_exact\":%llu,\"pair_calls\":%llu}}\n",
                            now - t0, (unsigned long long)a, (unsigned long long)b, (long long)rA, (long long)rB, (long long)T,
                            (unsigned long long)s->b_explored, (unsigned long long)s->leaves_exact, (unsigned long long)s->pair_calls);
                }
            }
            const int64_t iAB = iA_at(&memo, b);
            const int64_t base = rA + rB - iAB;
            if (base + rBn < T) {
                s->accounted += (__int128)(n - 1 - b);
                s->b_pruned++;
                continue;
            }
            s->b_explored++;
            const uint64_t B = list[b].mask;
            for (uint64_t cp = b + 1;; cp++) {
                T = s->target;
                int64_t rC = RAT(cp);
                if (base + rC < T) {
                    s->accounted += (__int128)(n - cp);
                    s->c_loop_breaks++;
                    break;
                }
                if ((cp & 4095) == 0 && n3_now() - t0 > tl) {
                    timed_out = 1;
                    int64_t ub_here = base + rC, ub_b = rA + rB + rBn, ub_next = RAT(a + 1) + RAT(a + 2) + RAT(a + 3);
                    int64_t ub = ub_here > ub_b ? ub_here : ub_b;
                    s->open_upper_bound = ub > ub_next ? ub : ub_next;
                    break;
                }
                const int64_t iAC = iA_at(&memo, cp);
                const int64_t gC = rC - iAC;
                if (base + gC < T) {
                    s->accounted += 1;
                    s->leaves_pruned_marginal++;
                    if (is_pow2(s->leaves_pruned_marginal)) { /* audit: exact value must respect the bound */
                        int64_t Fx = direct_F(c, A, list[b].mask, list[cp].mask);
                        s->prune_audits++;
                        if (!(Fx <= base + gC && Fx < T)) s->prune_audit_failures++;
                    }
                    continue;
                }
                const uint64_t C = list[cp].mask;
                double tp = n3_now();
                const int64_t iBC = n3_pair_overlap(c, B, C);
                s->seconds_pair += n3_now() - tp;
                s->pair_calls++;
                int64_t mn = iAB < iAC ? iAB : iAC;
                if (iBC < mn) mn = iBC;
#ifdef MUTANT_DROP_TRIPLE_TERM /* falsifiability mutant: inadmissible bound (ignores i(A,B,C) >= 0) */
                mn = 0;
#endif
                if (base + gC - iBC + mn < T) {
                    s->accounted += 1;
                    s->leaves_pruned_pair++;
                    if (is_pow2(s->leaves_pruned_pair)) {
                        int64_t Fx = direct_F(c, A, B, C);
                        s->prune_audits++;
                        if (!(Fx <= base + gC - iBC + mn && Fx < T)) s->prune_audit_failures++;
                    }
                    continue;
                }
                double tt = n3_now();
                const int64_t iABC = n3_triple_overlap(c, A, B, C);
                s->seconds_triple += n3_now() - tt;
                s->triple_calls++;
                const int64_t F = base + gC - iBC + iABC;
                s->accounted += 1;
                s->leaves_exact++;
                if (is_pow2(s->leaves_exact) || (F >= s->target && s->leaf_audits_at_best < 8)) {
                    int64_t Fx = direct_F(c, A, B, C);
                    s->leaf_audits++;
                    if (F >= s->target) s->leaf_audits_at_best++;
                    if (Fx != F) s->leaf_audit_failures++;
                }
                if (F > s->target) {
                    s->target = F;
                    s->improved = 1;
                    s->tie_count = 1;
                    s->ties_stored = 0;
                    record_tie(s, list[a].rank, list[b].rank, list[cp].rank);
                } else if (F == s->target) {
                    s->tie_count++;
                    record_tie(s, list[a].rank, list[b].rank, list[cp].rank);
                }
            }
            if (timed_out) break;
        }
        if (timed_out) { s->stop_reason = 1; break; }
    }
    s->seconds = n3_now() - t0;
    free(memo.iA);
    free(memo.stamp);
#undef RAT
}
