/* n3sig: one destroy triple -> exact signature compression report + exact complete-N3 B&B.
 *
 * usage: n3sig --kept "a,b,c,d,e,f;..." --removed "...;...;..." --out result.json
 *              [--probe "t;t;..."] [--checkpoint JOURNAL]
 *              [--time-limit SECONDS] [--no-solve] [--verbose]
 * Tickets are 1-based in the interface. */
#include "n3.h"
#include "n3_mtab.h"
#include "n3_sig.h"
#include "n3_solve.h"
#include "n3_bounds.h"
#include "n3_checkpoint.h"

#ifndef N3_ENGINE_SHA256
#define N3_ENGINE_SHA256 ""
#endif

static int parse_tickets(const char *s, uint64_t *out, int cap) {
    int n = 0, cur = 0, cnt = 0;
    uint64_t m = 0;
    for (const char *p = s;; p++) {
        if (*p >= '0' && *p <= '9') { cur = cur * 10 + (*p - '0'); continue; }
        if (*p == ',' || *p == ';' || *p == 0) {
            if (cur < 1 || cur > NPOOL) { fprintf(stderr, "bad number %d\n", cur); exit(2); }
            if ((m >> (cur - 1)) & 1) { fprintf(stderr, "repeated number\n"); exit(2); }
            m |= 1ull << (cur - 1);
            cnt++;
            cur = 0;
            if (*p == ';' || *p == 0) {
                if (cnt != 6) { fprintf(stderr, "ticket must have 6 numbers\n"); exit(2); }
                if (n >= cap) { fprintf(stderr, "too many tickets\n"); exit(2); }
                out[n++] = m;
                m = 0;
                cnt = 0;
            }
            if (*p == 0) break;
        }
    }
    return n;
}

static void put_ticket(FILE *f, uint64_t m) {
    int e[6];
    n3_mask_to_sorted(m, e);
    fprintf(f, "[%d,%d,%d,%d,%d,%d]", e[0] + 1, e[1] + 1, e[2] + 1, e[3] + 1, e[4] + 1, e[5] + 1);
}

static uint32_t rank6(uint64_t m) { return rank_mask(m); }

int main(int argc, char **argv) {
    const char *kept_s = NULL, *removed_s = NULL, *out_path = NULL, *probe_s = NULL;
    const char *checkpoint_path = NULL;
    double time_limit = 3600.0;
    int solve = 1, verbose = 0, legacy = 0;
    const char *witness_path = NULL;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--kept")) kept_s = argv[++i];
        else if (!strcmp(argv[i], "--removed")) removed_s = argv[++i];
        else if (!strcmp(argv[i], "--out")) out_path = argv[++i];
        else if (!strcmp(argv[i], "--checkpoint")) checkpoint_path = argv[++i];
        else if (!strcmp(argv[i], "--probe")) probe_s = argv[++i];
        else if (!strcmp(argv[i], "--time-limit")) time_limit = atof(argv[++i]);
        else if (!strcmp(argv[i], "--no-solve")) solve = 0;
        else if (!strcmp(argv[i], "--legacy")) legacy = 1;
        else if (!strcmp(argv[i], "--anchor-limit")) n3_anchor_limit = strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--cache-bits")) n3_cache_bits = (unsigned)strtoul(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--witness-file")) { witness_path = argv[++i]; solve = 0; }
        else if (!strcmp(argv[i], "--verbose")) verbose = 1;
        else { fprintf(stderr, "unknown arg %s\n", argv[i]); return 2; }
    }
    if (!kept_s || !removed_s || !out_path) { fprintf(stderr, "missing args\n"); return 2; }
    n3_init_binom();
    n3_init_kappa();
    static Ctx ctx;
    Ctx *c = &ctx;
    c->nR = parse_tickets(kept_s, c->Rmask, 20);
    uint64_t X[3];
    if (parse_tickets(removed_s, X, 3) != 3) { fprintf(stderr, "need 3 removed tickets\n"); return 2; }
    memcpy(c->Xmask, X, sizeof X);
    c->seed1 = 0x5eed000000000001ull ^ 0x20261005ull;
    c->seed2 = 0x5eed000000000002ull ^ 0xb649b649ull;
    uint64_t probes[128];
    int nprobe = probe_s ? parse_tickets(probe_s, probes, 128) : 0;

    double t0 = n3_now();
    n3_build_residual(c, 1);
    double t_res = n3_now();
    n3_build_n6(c);
    n3_lift(c);
    double t_lift = n3_now();
    uint64_t sum_r = 0, sum_n6 = 0;
    n3_score_all(c, &sum_r, &sum_n6);
    double t_score = n3_now();
    uint64_t *f1 = malloc(sizeof(uint64_t) * NT6), *f2 = malloc(sizeof(uint64_t) * NT6);
    n3_fingerprints(c, f1, f2);
    double t_fp = n3_now();
    static SigReport sig;
    n3_signature_classes(c, f1, f2, &sig);
    double t_sig = n3_now();
    int identities_ok = (sum_n6 == 7 * c->Usize) && (sum_r == HITS_PER_7SET * c->Usize);

    /* r statistics */
    int64_t rho = 0;
    uint64_t at_max = 0, zero_r = 0;
    for (uint64_t i = 0; i < NT6; i++) {
        if (c->r[i] > rho) { rho = c->r[i]; at_max = 0; }
        if (c->r[i] == rho) at_max++;
        if (c->r[i] == 0) zero_r++;
    }

    /* direct checks */
    int check_fail = 0;
    int checkpoint_fail = 0;
    FILE *chk = tmpfile();
    uint64_t sample[16];
    int ns = 0;
    for (int i = 0; i < 3; i++) sample[ns++] = X[i];
    {
        uint32_t best = 0;
        for (uint64_t i = 0; i < NT6; i++)
            if (c->r[i] == rho) { best = (uint32_t)i; break; }
        sample[ns++] = n3_unrank6(best);
    }
    for (int i = 0; i < 2 && i < c->nR; i++) sample[ns++] = c->Rmask[i];
    for (int i = 0; i < 6; i++) sample[ns++] = n3_unrank6((uint32_t)(splitmix64(0xc0ffee + i) % NT6));
    int witnesses = 0, witnesses_detected = 0;
    for (int i = 0; i < ns; i++) {
        uint64_t x1, x2;
        uint64_t d = n3_direct_res(c, sample[i], &x1, &x2);
        uint32_t rk = rank6(sample[i]);
        int ok = d == (uint64_t)c->r[rk] && x1 == f1[rk] && x2 == f2[rk];
        /* falsifiability witnesses: the coefficient -3 replaced by -2 and the fingerprint without
           its 4-subset term must both disagree with the direct enumeration when r > 0 */
        int e[6];
        n3_mask_to_sorted(sample[i], e);
        int64_t s4 = 0;
        uint64_t x3only = 0;
        for (int p = 0; p < 6; p++)
            for (int q2 = p + 1; q2 < 6; q2++)
                for (int u = q2 + 1; u < 6; u++) {
                    x3only ^= c->g3a[BIN[e[p]][1] + BIN[e[q2]][2] + BIN[e[u]][3]];
                    for (int v = u + 1; v < 6; v++) s4 += c->N4[BIN[e[p]][1] + BIN[e[q2]][2] + BIN[e[u]][3] + BIN[e[v]][4]];
                }
        int detected = -1;
        if (d > 0) {
            witnesses++;
            detected = ((uint64_t)(c->r[rk] + s4) != d) && (x3only != x1);
            witnesses_detected += detected;
        }
        if (!ok) check_fail++;
        fprintf(chk, "%s{\"TICKET\":", i ? "," : "");
        put_ticket(chk, sample[i]);
        fprintf(chk, ",\"R_MOEBIUS\":%d,\"R_DIRECT\":%llu,\"XOR_MATCH\":%s,\"PASS\":%s,\"FAULT_INJECTION_DETECTED\":%s}", c->r[rk],
                (unsigned long long)d, (x1 == f1[rk] && x2 == f2[rk]) ? "true" : "false", ok ? "true" : "false",
                detected < 0 ? "null" : (detected ? "true" : "false"));
    }
    /* pair overlaps: kappa formula vs direct, across intersection sizes */
    uint64_t pairs[12][2];
    int np = 0;
    pairs[np][0] = X[0]; pairs[np][1] = X[1]; np++;
    pairs[np][0] = X[0]; pairs[np][1] = X[2]; np++;
    pairs[np][0] = X[1]; pairs[np][1] = X[2]; np++;
    pairs[np][0] = sample[3]; pairs[np][1] = X[0]; np++;
    for (int sh = 1; sh <= 5; sh++) { /* T sharing exactly 6 - sh numbers with X[0] */
        int orig[6];
        n3_mask_to_sorted(X[0], orig);
        uint64_t t = X[0];
        for (int k = 0; k < sh; k++) t &= ~(1ull << orig[k]);
        int added = 0;
        for (int x = NPOOL - 1; x >= 0 && added < sh; x--) {
            if ((X[0] >> x) & 1) continue;
            t |= 1ull << x;
            added++;
        }
        pairs[np][0] = X[0]; pairs[np][1] = t; np++;
    }
    pairs[np][0] = sample[6]; pairs[np][1] = sample[7]; np++;
    int pair_fail = 0;
    FILE *pchk = tmpfile();
    for (int i = 0; i < np; i++) {
        int64_t k = n3_pair_overlap(c, pairs[i][0], pairs[i][1]);
        int64_t d = n3_pair_overlap_direct(c, pairs[i][0], pairs[i][1]);
        MTab mt;
        mtab_init(&mt);
        mtab_build(&mt, c, pairs[i][0]);
        int64_t mo = mtab_overlap(&mt, c, pairs[i][1]);
        mtab_free(&mt);
        int ok = (k == d) && (mo == d);
        if (!ok) pair_fail++;
        fprintf(pchk, "%s{\"SHARED\":%d,\"KAPPA\":%lld,\"MTAB\":%lld,\"DIRECT\":%lld,\"PASS\":%s}", i ? "," : "",
                __builtin_popcountll(pairs[i][0] & pairs[i][1]), (long long)k, (long long)mo, (long long)d, ok ? "true" : "false");
    }
    /* incumbent union */
    int64_t F0_direct = (int64_t)n3_direct_union(c, X, 3);
    int64_t rX[3];
    for (int i = 0; i < 3; i++) rX[i] = c->r[rank6(X[i])];
    int64_t i01 = n3_pair_overlap(c, X[0], X[1]), i02 = n3_pair_overlap(c, X[0], X[2]), i12 = n3_pair_overlap(c, X[1], X[2]);
    int64_t i012 = n3_triple_overlap(c, X[0], X[1], X[2]);
    int64_t F0_ie = rX[0] + rX[1] + rX[2] - i01 - i02 - i12 + i012;
    double t_checks = n3_now();

    /* threshold counts for the solver geometry */
    int64_t thr[5] = {(F0_direct + 2) / 3, (F0_direct - rho + 1) / 2, F0_direct - 2 * rho, rho - (3 * rho - F0_direct) / 2, 0};
    uint64_t thr_count[5] = {0};
    for (uint64_t i = 0; i < NT6; i++)
        for (int k = 0; k < 4; k++)
            if (c->r[i] >= thr[k]) thr_count[k]++;

    static Solver sol;
    double solver_budget = 0.0;
    if (solve && identities_ok && check_fail == 0 && pair_fail == 0 && F0_direct == F0_ie) {
        solver_budget = time_limit - (n3_now() - t0);
        if (checkpoint_path && legacy) {
            fprintf(stderr,"durable checkpoints are supported by the R2 exact solver only\n");
            checkpoint_fail = 1;
        } else if (checkpoint_path) {
            char destroy_set[64], canonical_input[1200], solver_config[256];
            char input_sha256[65], solver_config_sha256[65];
            int used = snprintf(destroy_set,sizeof destroy_set,
                "%016llx,%016llx,%016llx",
                (unsigned long long)X[0],(unsigned long long)X[1],(unsigned long long)X[2]);
            if (used < 0 || (size_t)used >= sizeof destroy_set) return 2;
            used = snprintf(canonical_input,sizeof canonical_input,"NPOOL=%d;R=",NPOOL);
            for (int i=0;i<c->nR && used>0 && (size_t)used<sizeof canonical_input;i++)
                used += snprintf(canonical_input+used,sizeof canonical_input-(size_t)used,
                    "%s%016llx",i?",":"",(unsigned long long)c->Rmask[i]);
            if (used < 0 || (size_t)used>=sizeof canonical_input) return 2;
            used += snprintf(canonical_input+used,sizeof canonical_input-(size_t)used,";X=");
            for (int i=0;i<3 && used>0 && (size_t)used<sizeof canonical_input;i++)
                used += snprintf(canonical_input+used,sizeof canonical_input-(size_t)used,
                    "%s%016llx",i?",":"",(unsigned long long)X[i]);
            if (used < 0 || (size_t)used>=sizeof canonical_input) return 2;
            used = snprintf(solver_config,sizeof solver_config,
                "R2;legacy=0;time_limit=%.17g;cache_bits=%u;anchor_limit=%llu;NT6=%u;NPOOL=%d",
                time_limit,n3_cache_bits,(unsigned long long)n3_anchor_limit,(unsigned)NT6,NPOOL);
            if (used < 0 || (size_t)used>=sizeof solver_config) return 2;
            n3_sha256_hex(canonical_input,strlen(canonical_input),input_sha256);
            n3_sha256_hex(solver_config,strlen(solver_config),solver_config_sha256);
            SolverResumeConfig resume = {
                .path=checkpoint_path,.destroy_set=destroy_set,.input_sha256=input_sha256,
                .engine_sha256=N3_ENGINE_SHA256,.solver_config_sha256=solver_config_sha256
            };
            checkpoint_fail = solver_run_durable(&sol,c,F0_direct,solver_budget,verbose,&resume,0);
        } else if (legacy) solver_run_legacy(&sol, c, F0_direct, solver_budget, verbose);
        else solver_run(&sol, c, F0_direct, solver_budget, verbose);
    }
    double t_end = n3_now();

    FILE *f = fopen(out_path, "w");
    if (!f) { perror("out"); return 1; }
    fprintf(f, "{\"SCHEMA\":\"B649_N3_SIGNATURE_ENGINE_SET_V1\",\"KEPT\":[");
    for (int i = 0; i < c->nR; i++) { if (i) fputc(',', f); put_ticket(f, c->Rmask[i]); }
    fprintf(f, "],\"REMOVED\":[");
    for (int i = 0; i < 3; i++) { if (i) fputc(',', f); put_ticket(f, X[i]); }
    fprintf(f, "],\"TOTAL_7SUBSETS\":%u,\"RESIDUAL_SUBSETS\":%llu,\"COVERED_BY_R_SUBSETS\":%llu,\"FROZEN_REMAINDER_COUNT\":%llu,",
            NT7, (unsigned long long)c->Usize, (unsigned long long)(NT7 - c->Usize), (unsigned long long)(7 * (NT7 - c->Usize)));
    fprintf(f, "\"IDENTITIES\":{\"SUM_N6\":%llu,\"SUM_N6_EXPECTED\":%llu,\"SUM_R\":%llu,\"SUM_R_EXPECTED\":%llu,\"PASS\":%s},",
            (unsigned long long)sum_n6, (unsigned long long)(7 * c->Usize), (unsigned long long)sum_r,
            (unsigned long long)(HITS_PER_7SET * c->Usize), identities_ok ? "true" : "false");
    fprintf(f, "\"SIGNATURES\":{\"TOTAL_TICKETS\":%llu,\"UNIQUE_SIGNATURES\":%llu,\"COMPRESSION_RATIO\":%.9f,\"LARGEST_SIGNATURE_CLASS\":%llu,"
               "\"MULTI_MEMBER_CLASSES\":%llu,\"FINGERPRINT_RUNS_MULTI\":%llu,\"EXACT_PAIR_CHECKS\":%llu,\"FINGERPRINT_FALSE_MERGES\":%llu,\"CLASSES\":[",
            (unsigned long long)sig.total, (unsigned long long)sig.unique, (double)sig.total / (double)sig.unique,
            (unsigned long long)sig.largest, (unsigned long long)sig.n_multi, (unsigned long long)sig.fingerprint_runs_multi,
            (unsigned long long)sig.exact_pair_checks, (unsigned long long)sig.fingerprint_false_merges);
    for (uint64_t i = 0; i < sig.n_multi && i < SIG_MAX_LISTED; i++) {
        SigClass *sc = &sig.multi[i];
        fprintf(f, "%s{\"SIZE\":%llu,\"R\":%d,\"REPRESENTATIVE\":", i ? "," : "", (unsigned long long)sc->size, sc->r);
        put_ticket(f, n3_unrank6(sc->representative));
        fprintf(f, ",\"MEMBERS\":[");
        for (int k = 0; k < sc->nmembers; k++) { if (k) fputc(',', f); put_ticket(f, n3_unrank6(sc->members[k])); }
        fprintf(f, "]}");
    }
    fprintf(f, "]},");
    fprintf(f, "\"R_STATS\":{\"MAX\":%lld,\"COUNT_AT_MAX\":%llu,\"ZERO_R_TICKETS\":%llu,\"THRESHOLDS\":[", (long long)rho,
            (unsigned long long)at_max, (unsigned long long)zero_r);
    const char *tn[4] = {"F0_DIV_3", "HALF_F0_MINUS_RHO", "F0_MINUS_2RHO", "RHO_MINUS_HALF_SLACK"};
    for (int k = 0; k < 4; k++)
        fprintf(f, "%s{\"NAME\":\"%s\",\"VALUE\":%lld,\"TICKETS_AT_OR_ABOVE\":%llu}", k ? "," : "", tn[k], (long long)thr[k],
                (unsigned long long)thr_count[k]);
    fprintf(f, "]},\"PROBES\":[");
    for (int i = 0; i < nprobe; i++) {
        fprintf(f, "%s{\"TICKET\":", i ? "," : "");
        put_ticket(f, probes[i]);
        fprintf(f, ",\"R\":%d}", c->r[rank6(probes[i])]);
    }
    fprintf(f, "],\"CHECKS\":{\"SINGLE_TICKET\":[");
    rewind(chk);
    int ch;
    while ((ch = fgetc(chk)) != EOF) fputc(ch, f);
    fprintf(f, "],\"PAIR_OVERLAP\":[");
    rewind(pchk);
    while ((ch = fgetc(pchk)) != EOF) fputc(ch, f);
    fprintf(f, "],\"SINGLE_TICKET_FAILURES\":%d,\"PAIR_FAILURES\":%d,\"FAULT_INJECTION_WITNESSES\":%d,\"FAULT_INJECTION_DETECTED\":%d},",
            check_fail, pair_fail, witnesses, witnesses_detected);
    fprintf(f, "\"INCUMBENT\":{\"REMOVED_R\":[%lld,%lld,%lld],\"PAIR_OVERLAPS\":[%lld,%lld,%lld],\"TRIPLE_OVERLAP\":%lld,"
               "\"F0_DIRECT\":%lld,\"F0_INCLUSION_EXCLUSION\":%lld,\"SLACK_3RHO_MINUS_F0\":%lld},",
            (long long)rX[0], (long long)rX[1], (long long)rX[2], (long long)i01, (long long)i02, (long long)i12, (long long)i012,
            (long long)F0_direct, (long long)F0_ie, (long long)(3 * rho - F0_direct));
    fprintf(f, "\"TIMING\":{\"RESIDUAL_AND_FINGERPRINT_TABLES\":%.3f,\"N6_AND_LIFT\":%.3f,\"SCORE_ALL\":%.3f,\"FINGERPRINTS\":%.3f,"
               "\"SIGNATURE_CLASSES\":%.3f,\"CHECKS\":%.3f,\"SOLVER\":%.3f,\"TOTAL\":%.3f},",
            t_res - t0, t_lift - t_res, t_score - t_lift, t_fp - t_score, t_sig - t_fp, t_checks - t_sig, t_end - t_checks, t_end - t0);
    if (solve && sol.L) {
        char acc[64], tot[64];
        u128_to_str(sol.accounted, acc);
        u128_to_str(choose3_128(NT6), tot);
        fprintf(f, "\"SOLVER\":{\"RAN\":true,\"CLOSED\":%s,\"STOP_REASON\":\"%s\",\"TIME_LIMIT_SECONDS\":%.1f,\"SOLVER_BUDGET_SECONDS\":%.3f,\"SECONDS\":%.3f,"
                   "\"INCUMBENT_F0\":%lld,\"BEST_F\":%lld,\"IMPROVED\":%s,\"OPTIMAL_TRIPLE_COUNT\":%llu,\"TIES_STORED\":%llu,"
                   "\"CANDIDATE_PREFIX_L\":%llu,\"RMIN\":%lld,\"A_BREAK_POSITION\":%lld,\"A_LAST\":%llu,"
                   "\"PRUNE_AUDITS\":%llu,\"PRUNE_AUDIT_FAILURES\":%llu,\"LEAF_DIRECT_AUDITS\":%llu,\"LEAF_DIRECT_AUDIT_FAILURES\":%llu,"
                   "\"A_BOUND_COUNT\":%llu,\"A_EXPLORED\":%llu,\"B_EXPLORED\":%llu,\"B_PRUNED\":%llu,\"B_LOOP_BREAKS\":%llu,\"C_LOOP_BREAKS\":%llu,"
                   "\"LEAVES_EXACT\":%llu,\"LEAVES_PRUNED_MARGINAL\":%llu,\"LEAVES_PRUNED_PAIR\":%llu,"
                   "\"PAIR_CALLS\":%llu,\"TRIPLE_CALLS\":%llu,\"MTAB_BUILDS\":%llu,\"GA_EVALS\":%llu,"
                   "\"SECONDS_MTAB\":%.3f,\"SECONDS_PAIR\":%.3f,\"SECONDS_TRIPLE\":%.3f,"
                   "\"TRIPLES_ACCOUNTED\":\"%s\",\"TRIPLES_TOTAL\":\"%s\",\"ACCOUNTING_COMPLETE\":%s,\"OPEN_UPPER_BOUND\":%lld,\"TIES\":[",
                sol.closed ? "true" : "false", sol.closed ? "CLOSED" :
                    sol.stop_reason == 2 ? "ANCHOR_PROFILE_LIMIT" :
                    sol.stop_reason == 3 ? "DURABLE_CHECKPOINT_TEST_STOP" :
                    sol.stop_reason == 4 ? "CHECKPOINT_ERROR" : "TIME_LIMIT",
                time_limit, solver_budget, sol.seconds,
                (long long)sol.incumbent, (long long)sol.target, sol.improved ? "true" : "false", (unsigned long long)sol.tie_count,
                (unsigned long long)sol.ties_stored, (unsigned long long)sol.L, (long long)sol.rmin, (long long)sol.a_break_position,
                (unsigned long long)sol.a_last, (unsigned long long)sol.prune_audits, (unsigned long long)sol.prune_audit_failures,
                (unsigned long long)sol.leaf_audits, (unsigned long long)sol.leaf_audit_failures, (unsigned long long)sol.a_bound_count, (unsigned long long)sol.a_explored, (unsigned long long)sol.b_explored,
                (unsigned long long)sol.b_pruned, (unsigned long long)sol.b_loop_breaks, (unsigned long long)sol.c_loop_breaks,
                (unsigned long long)sol.leaves_exact, (unsigned long long)sol.leaves_pruned_marginal,
                (unsigned long long)sol.leaves_pruned_pair, (unsigned long long)sol.pair_calls, (unsigned long long)sol.triple_calls,
                (unsigned long long)sol.mtab_builds, (unsigned long long)sol.gA_evals, sol.seconds_mtab, sol.seconds_pair,
                sol.seconds_triple, acc, tot, (sol.accounted == choose3_128(NT6)) ? "true" : "false", (long long)sol.open_upper_bound);
        for (uint64_t i = 0; i < sol.ties_stored; i++) {
            fprintf(f, "%s[", i ? "," : "");
            for (int k = 0; k < 3; k++) { if (k) fputc(',', f); put_ticket(f, n3_unrank6(sol.ties[3 * i + k])); }
            fprintf(f, "]");
        }
        fprintf(f, "],\"ANCHORS_COMPLETED\":%llu,\"ANCHORS_PRUNED_CONDITIONAL\":%llu,\"CONDITIONAL_CANDIDATES\":%llu,\"CACHE_HITS\":%llu,\"CACHE_MISSES\":%llu,\"SECONDS_CONDITIONAL\":%.6f,\"LOWER_BOUND_CALLS\":%llu,\"LEAVES_PRUNED_LOWER\":%llu,\"PAIR_SHARED_COUNTS\":[%llu,%llu,%llu,%llu,%llu,%llu,%llu],"
                   "\"DURABLE_CHECKPOINT_AVAILABLE\":%s,\"CHECKPOINT_ANCHORS_RECORDED\":%llu,\"JOURNAL_PREFIX_SHA256\":\"%s\"},",
                (unsigned long long)sol.anchors_completed, (unsigned long long)sol.anchors_pruned_conditional,
                (unsigned long long)sol.conditional_candidates, (unsigned long long)sol.cache_hits,
                (unsigned long long)sol.cache_misses, sol.seconds_conditional,
                (unsigned long long)sol.lower_calls, (unsigned long long)sol.leaves_pruned_lower,
                (unsigned long long)sol.pair_shared[0], (unsigned long long)sol.pair_shared[1],
                (unsigned long long)sol.pair_shared[2], (unsigned long long)sol.pair_shared[3],
                (unsigned long long)sol.pair_shared[4], (unsigned long long)sol.pair_shared[5],
                (unsigned long long)sol.pair_shared[6],
                checkpoint_path && !legacy && !checkpoint_fail ? "true" : "false",
                (unsigned long long)sol.checkpoint_anchor_records, sol.checkpoint_prefix_sha256);
    } else {
        fprintf(f, "\"SOLVER\":{\"RAN\":false},");
    }
    if (witness_path) {
        FILE *w = fopen(witness_path, "r");
        if (!w) { perror("witness-file"); return 2; }
        char line[512];
        uint64_t count = 0, failures = 0, direct_checks = 0;
        while (fgets(line, sizeof line, w)) {
            line[strcspn(line, "\r\n")] = 0;
            uint64_t t[3];
            if (parse_tickets(line, t, 3) != 3) return 2;
            int64_t r[3], i[3];
            for (int j = 0; j < 3; j++) r[j] = c->r[rank6(t[j])];
            i[0] = n3_pair_overlap(c, t[0], t[1]);
            i[1] = n3_pair_overlap(c, t[0], t[2]);
            i[2] = n3_pair_overlap(c, t[1], t[2]);
            int64_t exact = r[0]+r[1]+r[2]-i[0]-i[1]-i[2]+
                n3_triple_overlap(c, t[0], t[1], t[2]);
            int bad = exact != F0_direct;
            for (int j = 0; j < 3; j++) {
                int b = (j+1)%3, z = (j+2)%3;
                int64_t iab = n3_pair_overlap(c, t[j], t[b]);
                int64_t iac = n3_pair_overlap(c, t[j], t[z]);
                int64_t ibc = n3_pair_overlap(c, t[b], t[z]);
                int64_t ub = n3_two_slot_bound(r[j], r[b]-iab, r[z]-iac);
                int64_t pb = n3_pair_bound(r[j]+r[b]-iab, r[z]-iac, iab, iac, ibc);
                int64_t lower = n3_pair_overlap_lower_bound(c, t[b], t[z]);
                int64_t quick = n3_lower_pair_bound(r[j]+r[b]-iab, r[z]-iac, iab, iac, lower);
                bad |= lower > ibc || n3_strict_prune(quick, exact) ||
                    n3_strict_prune(ub, exact) || n3_strict_prune(pb, exact);
            }
            if (count < 4) {
                direct_checks++;
                bad |= (int64_t)n3_direct_union(c, t, 3) != exact;
            }
            failures += bad;
            count++;
        }
        fclose(w);
        fprintf(f, "\"STORED_PROOF_REPLAY\":{\"WITNESSES\":%llu,\"DIRECT_CHECKS\":%llu,"
                   "\"MISMATCHES\":%llu,\"REFERENCE_F\":%lld,\"SEARCH_RAN\":false},",
                (unsigned long long)count, (unsigned long long)direct_checks,
                (unsigned long long)failures, (long long)F0_direct);
        if (failures) check_fail++;
    }
    fprintf(f, "\"PEAK_RSS_BYTES\":%zu}\n", n3_peak_rss());
    fclose(f);
    return checkpoint_fail || check_fail || pair_fail || !identities_ok || F0_direct != F0_ie ||
        (solve && (sol.prune_audit_failures || sol.leaf_audit_failures)) ? 1 : 0;
}
