#ifndef N3_SOLVE_H
#define N3_SOLVE_H
#include "n3.h"

#define MAX_TIES_STORED (1u << 20)

typedef struct {
    uint64_t mask;
    uint32_t rank;
    int32_t r;
} Cand;

typedef struct {
    /* configuration */
    double time_limit_s;
    int64_t incumbent; /* F0: residual union of the destroyed triple */
    /* state */
    int64_t target;    /* current best known F (ties are kept, strict prune only) */
    int closed;
    int stop_reason;   /* 0 closed, 1 time limit */
    /* candidate prefix of the complete (r desc, rank asc) order */
    Cand *list;
    uint64_t L;
    int64_t rmin;
    /* incumbent ties / optimum */
    uint64_t tie_count;
    uint32_t *ties; /* 3 colex ranks per stored optimal triple */
    uint64_t ties_stored;
    int improved;
    /* accounting: every unordered triple of distinct tickets is either evaluated
       exactly or eliminated by a proven bound; at closure the sum is C(n,3) */
    __int128 accounted;
    /* statistics */
    uint64_t a_explored, a_pruned_individual, b_explored, b_pruned, b_loop_breaks, c_loop_breaks;
    uint64_t leaves_exact, leaves_pruned_marginal, leaves_pruned_pair;
    uint64_t pair_calls, triple_calls, mtab_builds, gA_evals;
    uint64_t a_bound_count; /* A positions passing the initial r-sum bound at F0 */
    uint64_t prune_audits, prune_audit_failures, leaf_audits, leaf_audit_failures, leaf_audits_at_best;
    int64_t a_break_position; /* full-order position where the A loop closed (-1 if not) */
    uint64_t a_last;          /* last A position processed */
    double seconds, seconds_mtab, seconds_pair, seconds_triple;
    /* upper bound on any unexplored triple at stop (for timeout reporting) */
    int64_t open_upper_bound;
    uint64_t anchors_completed, anchors_pruned_conditional, conditional_candidates;
    uint64_t cache_hits, cache_misses;
    double seconds_conditional;
    uint64_t leaves_pruned_lower, lower_calls, pair_shared[7];
} Solver;

void solver_run(Solver *s, const Ctx *c, int64_t incumbent, double time_limit_s, int verbose);
void solver_run_legacy(Solver *s, const Ctx *c, int64_t incumbent, double time_limit_s, int verbose);
extern uint64_t n3_anchor_limit; /* profiling stop only; never a proof of closure */
extern unsigned n3_cache_bits; /* storage limit; cache misses are evaluated exactly */
void u128_to_str(__int128 v, char *buf);
__int128 choose3_128(uint64_t n);
__int128 choose2_128(uint64_t n);

#endif
