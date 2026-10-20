/* Core exact passes: residual bitset, superset counts N3..N6, single-ticket residual
 * marginals r(t), XOR-linear signature fingerprints and direct (brute-force) checks. */
#include "n3.h"

#include <sys/resource.h>
#include <sys/time.h>
#include <time.h>

uint32_t BIN[64][9];

void n3_init_binom(void) {
    for (int n = 0; n < 64; n++) {
        for (int k = 0; k < 9; k++) {
            uint64_t v;
            if (k == 0)
                v = 1;
            else if (n == 0)
                v = 0;
            else
                v = (uint64_t)BIN[n - 1][k - 1] + BIN[n - 1][k];
            BIN[n][k] = (uint32_t)v;
        }
    }
}

double n3_now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

size_t n3_peak_rss(void) {
    struct rusage ru;
    getrusage(RUSAGE_SELF, &ru);
    return (size_t)ru.ru_maxrss; /* bytes on macOS */
}

int n3_mask_to_sorted(uint64_t m, int *out) {
    int k = 0;
    while (m) {
        out[k++] = __builtin_ctzll(m);
        m &= m - 1;
    }
    return k;
}

uint64_t n3_unrank6(uint32_t rank) {
    uint64_t m = 0;
    uint32_t rem = rank;
    for (int k = 6; k >= 1; k--) {
        int x = k - 1;
        while (BIN[x + 1][k] <= rem) x++;
        rem -= BIN[x][k];
        m |= 1ull << x;
    }
    return m;
}

/* 3- and 4-subset position tables of a 7-set, and of a 6-set */
static int C7_3[35][3], C7_4[35][4], C6_3[20][3], C6_4[15][4], C6_5[6][5];
static int tables_ready = 0;

static void build_position_tables(void) {
    if (tables_ready) return;
    int n = 0;
    for (int a = 0; a < 7; a++)
        for (int b = a + 1; b < 7; b++)
            for (int c = b + 1; c < 7; c++) { C7_3[n][0] = a; C7_3[n][1] = b; C7_3[n][2] = c; n++; }
    n = 0;
    for (int a = 0; a < 7; a++)
        for (int b = a + 1; b < 7; b++)
            for (int c = b + 1; c < 7; c++)
                for (int d = c + 1; d < 7; d++) { C7_4[n][0] = a; C7_4[n][1] = b; C7_4[n][2] = c; C7_4[n][3] = d; n++; }
    n = 0;
    for (int a = 0; a < 6; a++)
        for (int b = a + 1; b < 6; b++)
            for (int c = b + 1; c < 6; c++) { C6_3[n][0] = a; C6_3[n][1] = b; C6_3[n][2] = c; n++; }
    n = 0;
    for (int a = 0; a < 6; a++)
        for (int b = a + 1; b < 6; b++)
            for (int c = b + 1; c < 6; c++)
                for (int d = c + 1; d < 6; d++) { C6_4[n][0] = a; C6_4[n][1] = b; C6_4[n][2] = c; C6_4[n][3] = d; n++; }
    for (int drop = 0; drop < 6; drop++) {
        int q = 0;
        for (int i = 0; i < 6; i++)
            if (i != drop) C6_5[drop][q++] = i;
    }
    tables_ready = 1;
}

static inline void fp_update(Ctx *c, const int *e, uint32_t idx) {
    uint64_t h1 = splitmix64((uint64_t)idx ^ c->seed1);
    uint64_t h2 = splitmix64((uint64_t)idx ^ c->seed2);
    for (int q = 0; q < 35; q++) {
        uint32_t r3 = BIN[e[C7_3[q][0]]][1] + BIN[e[C7_3[q][1]]][2] + BIN[e[C7_3[q][2]]][3];
        c->g3a[r3] ^= h1;
        c->g3b[r3] ^= h2;
        uint32_t r4 = BIN[e[C7_4[q][0]]][1] + BIN[e[C7_4[q][1]]][2] + BIN[e[C7_4[q][2]]][3] + BIN[e[C7_4[q][3]]][4];
        c->g4a[r4] ^= h1;
        c->g4b[r4] ^= h2;
    }
}

/* U = 7-sets containing no 3-subset of a kept ticket.  Bit-sliced saturating counters:
 * s1/s2/s3 = kept tickets meeting the partial set in >= 1/2/3 numbers. */
void n3_build_residual(Ctx *c, int with_fp) {
    build_position_tables();
    uint32_t inc[NPOOL] = {0};
    for (int i = 0; i < c->nR; i++)
        for (int x = 0; x < NPOOL; x++)
            if ((c->Rmask[i] >> x) & 1) inc[x] |= 1u << i;
    c->U = calloc((NT7 + 7) / 8, 1);
    if (with_fp) {
        c->g3a = calloc(NT3, 8); c->g3b = calloc(NT3, 8);
        c->g4a = calloc(NT4, 8); c->g4b = calloc(NT4, 8);
    }
    uint32_t idx = 0;
    uint64_t cnt = 0;
    int e[7];
    for (int e6 = 6; e6 < NPOOL; e6++) {
        e[6] = e6;
        uint32_t a1 = inc[e6], a2 = 0, a3 = 0;
        for (int e5 = 5; e5 < e6; e5++) {
            e[5] = e5;
            uint32_t m = inc[e5];
            uint32_t b3 = a3 | (a2 & m), b2 = a2 | (a1 & m), b1 = a1 | m;
            for (int e4 = 4; e4 < e5; e4++) {
                e[4] = e4;
                m = inc[e4];
                uint32_t c3 = b3 | (b2 & m), c2 = b2 | (b1 & m), c1 = b1 | m;
                if (c3) { idx += BIN[e4][4]; continue; }
                for (int e3 = 3; e3 < e4; e3++) {
                    e[3] = e3;
                    m = inc[e3];
                    uint32_t d3 = c3 | (c2 & m), d2 = c2 | (c1 & m), d1 = c1 | m;
                    if (d3) { idx += BIN[e3][3]; continue; }
                    for (int e2 = 2; e2 < e3; e2++) {
                        e[2] = e2;
                        m = inc[e2];
                        uint32_t f3 = d3 | (d2 & m), f2 = d2 | (d1 & m), f1 = d1 | m;
                        if (f3) { idx += BIN[e2][2]; continue; }
                        for (int e1 = 1; e1 < e2; e1++) {
                            e[1] = e1;
                            m = inc[e1];
                            uint32_t g3 = f3 | (f2 & m), g2 = f2 | (f1 & m);
                            if (g3) { idx += (uint32_t)e1; continue; }
                            for (int e0 = 0; e0 < e1; e0++) {
                                if (!(g2 & inc[e0])) {
                                    c->U[idx >> 3] |= (uint8_t)(1u << (idx & 7));
                                    cnt++;
                                    if (with_fp) { e[0] = e0; fp_update(c, e, idx); }
                                }
                                idx++;
                            }
                        }
                    }
                }
            }
        }
    }
    if (idx != NT7) { fprintf(stderr, "residual enumeration covered %u != C(49,7)\n", idx); exit(3); }
    c->Usize = cnt;
    c->residual_matches_kept = 1;
}

/* N6(t) = #{x not in t : t + x in U} via pair links of the kept tickets' 3-subsets. */
void n3_build_n6(Ctx *c) {
    static uint64_t L[NPOOL][NPOOL];
    memset(L, 0, sizeof L);
    for (int i = 0; i < c->nR; i++) {
        int t[6];
        n3_mask_to_sorted(c->Rmask[i], t);
        for (int a = 0; a < 6; a++)
            for (int b = a + 1; b < 6; b++)
                for (int d = b + 1; d < 6; d++) {
                    L[t[a]][t[b]] |= 1ull << t[d]; L[t[b]][t[a]] |= 1ull << t[d];
                    L[t[a]][t[d]] |= 1ull << t[b]; L[t[d]][t[a]] |= 1ull << t[b];
                    L[t[b]][t[d]] |= 1ull << t[a]; L[t[d]][t[b]] |= 1ull << t[a];
                }
    }
    c->N6 = malloc(NT6);
    uint32_t idx = 0;
    for (int t5 = 5; t5 < NPOOL; t5++) {
        uint64_t M5 = 1ull << t5;
        for (int t4 = 4; t4 < t5; t4++) {
            uint64_t F4 = L[t4][t5], M4 = M5 | (1ull << t4);
            for (int t3 = 3; t3 < t4; t3++) {
                uint64_t F3 = F4 | L[t3][t4] | L[t3][t5], M3 = M4 | (1ull << t3);
                for (int t2 = 2; t2 < t3; t2++) {
                    uint64_t F2 = F3 | L[t2][t3] | L[t2][t4] | L[t2][t5], M2 = M3 | (1ull << t2);
                    for (int t1 = 1; t1 < t2; t1++) {
                        uint64_t F1 = F2 | L[t1][t2] | L[t1][t3] | L[t1][t4] | L[t1][t5], M1 = M2 | (1ull << t1);
                        for (int t0 = 0; t0 < t1; t0++) {
                            uint64_t F0 = F1 | L[t0][t1] | L[t0][t2] | L[t0][t3] | L[t0][t4] | L[t0][t5];
                            uint64_t M0 = M1 | (1ull << t0);
                            c->N6[idx++] = (F0 & M0) ? 0 : (uint8_t)(43 - __builtin_popcountll(F0));
                        }
                    }
                }
            }
        }
    }
    if (idx != NT6) { fprintf(stderr, "N6 enumeration %u != C(49,6)\n", idx); exit(3); }
}

static void colex_first(int *e, int k) { for (int i = 0; i < k; i++) e[i] = i; }
static int colex_next(int *e, int k, int n) {
    for (int i = 0; i < k; i++) {
        int lim = (i + 1 < k) ? e[i + 1] : n;
        if (e[i] + 1 < lim) {
            e[i]++;
            for (int j = 0; j < i; j++) e[j] = j;
            return 1;
        }
    }
    return 0;
}

/* N_k(Y) = sum_{x not in Y} N_{k+1}(Y + x) / (7 - k), asserted exact. */
static uint64_t lift_sum(const Ctx *c, const int *e, int k) {
    uint32_t pre[8], suf[8];
    pre[0] = 0;
    for (int p = 0; p < k; p++) pre[p + 1] = pre[p] + BIN[e[p]][p + 1];
    suf[k] = 0;
    for (int p = k - 1; p >= 0; p--) suf[p] = suf[p + 1] + BIN[e[p]][p + 2];
    uint64_t sum = 0;
    int p = 0;
    for (int x = 0; x < NPOOL; x++) {
        if (p < k && e[p] == x) { p++; continue; }
        uint32_t rk = pre[p] + BIN[x][p + 1] + suf[p];
        if (k == 5) sum += c->N6[rk];
        else if (k == 4) sum += c->N5[rk];
        else sum += c->N4[rk];
    }
    return sum;
}

void n3_lift(Ctx *c) {
    c->N5 = malloc(sizeof(uint16_t) * NT5);
    c->N4 = malloc(sizeof(uint16_t) * NT4);
    c->N3 = malloc(sizeof(uint32_t) * NT3);
    int e[8];
    for (int k = 5; k >= 3; k--) {
        uint32_t total = (k == 5) ? NT5 : (k == 4) ? NT4 : NT3, idx = 0;
        colex_first(e, k);
        do {
            uint64_t s = lift_sum(c, e, k);
            if (s % (uint64_t)(7 - k)) { fprintf(stderr, "lift not exact at k=%d\n", k); exit(3); }
            s /= (uint64_t)(7 - k);
            if (k == 5) c->N5[idx] = (uint16_t)s;
            else if (k == 4) c->N4[idx] = (uint16_t)s;
            else c->N3[idx] = (uint32_t)s;
            idx++;
        } while (colex_next(e, k, NPOOL));
        if (idx != total) { fprintf(stderr, "lift count mismatch k=%d\n", k); exit(3); }
    }
}

/* r(t) = sum_{B <= t, |B| >= 3} c(|B|) N(B), c = (1, -3, 6, -10). */
void n3_score_all(Ctx *c, uint64_t *sum_r, uint64_t *sum_n6) {
    build_position_tables();
    c->r = malloc(sizeof(int32_t) * NT6);
    uint64_t sr = 0, sn = 0;
    int e[6];
    uint32_t idx = 0;
    for (e[5] = 5; e[5] < NPOOL; e[5]++)
        for (e[4] = 4; e[4] < e[5]; e[4]++)
            for (e[3] = 3; e[3] < e[4]; e[3]++)
                for (e[2] = 2; e[2] < e[3]; e[2]++)
                    for (e[1] = 1; e[1] < e[2]; e[1]++)
                        for (e[0] = 0; e[0] < e[1]; e[0]++) {
                            int64_t s3 = 0, s4 = 0, s5 = 0;
                            for (int q = 0; q < 20; q++)
                                s3 += c->N3[BIN[e[C6_3[q][0]]][1] + BIN[e[C6_3[q][1]]][2] + BIN[e[C6_3[q][2]]][3]];
                            for (int q = 0; q < 15; q++)
                                s4 += c->N4[BIN[e[C6_4[q][0]]][1] + BIN[e[C6_4[q][1]]][2] + BIN[e[C6_4[q][2]]][3] +
                                            BIN[e[C6_4[q][3]]][4]];
                            for (int q = 0; q < 6; q++)
                                s5 += c->N5[BIN[e[C6_5[q][0]]][1] + BIN[e[C6_5[q][1]]][2] + BIN[e[C6_5[q][2]]][3] +
                                            BIN[e[C6_5[q][3]]][4] + BIN[e[C6_5[q][4]]][5]];
                            int64_t n6 = c->N6[idx];
                            int64_t v = s3 - 3 * s4 + 6 * s5 - 10 * n6;
                            c->r[idx] = (int32_t)v;
                            sr += (uint64_t)v;
                            sn += (uint64_t)n6;
                            idx++;
                        }
    if (idx != NT6) { fprintf(stderr, "score enumeration mismatch\n"); exit(3); }
    *sum_r = sr;
    *sum_n6 = sn;
}

/* sig fingerprint: XOR over res(t) of h(E) = XOR_{B<=t,|B|=3} G3(B) ^ XOR_{|B|=4} G4(B)
 * because C(m,3) + C(m,4) is odd for m = 3..6 and zero for m < 3. */
void n3_fingerprints(const Ctx *c, uint64_t *f1, uint64_t *f2) {
    build_position_tables();
    int e[6];
    uint32_t idx = 0;
    for (e[5] = 5; e[5] < NPOOL; e[5]++)
        for (e[4] = 4; e[4] < e[5]; e[4]++)
            for (e[3] = 3; e[3] < e[4]; e[3]++)
                for (e[2] = 2; e[2] < e[3]; e[2]++)
                    for (e[1] = 1; e[1] < e[2]; e[1]++)
                        for (e[0] = 0; e[0] < e[1]; e[0]++) {
                            uint64_t x1 = 0, x2 = 0;
                            for (int q = 0; q < 20; q++) {
                                uint32_t r3 = BIN[e[C6_3[q][0]]][1] + BIN[e[C6_3[q][1]]][2] + BIN[e[C6_3[q][2]]][3];
                                x1 ^= c->g3a[r3];
                                x2 ^= c->g3b[r3];
                            }
                            for (int q = 0; q < 15; q++) {
                                uint32_t r4 = BIN[e[C6_4[q][0]]][1] + BIN[e[C6_4[q][1]]][2] + BIN[e[C6_4[q][2]]][3] +
                                              BIN[e[C6_4[q][3]]][4];
                                x1 ^= c->g4a[r4];
                                x2 ^= c->g4b[r4];
                            }
                            f1[idx] = x1;
                            f2[idx] = x2;
                            idx++;
                        }
}

uint64_t n3_count_N(const Ctx *c, uint64_t w) {
    int k = __builtin_popcountll(w);
    uint32_t rk = rank_mask(w);
    switch (k) {
    case 7: return (uint64_t)u_get(c->U, rk);
    case 6: return c->N6[rk];
    case 5: return c->N5[rk];
    case 4: return c->N4[rk];
    case 3: return c->N3[rk];
    default: fprintf(stderr, "n3_count_N size %d\n", k); exit(3);
    }
}

/* ---- direct enumeration of cov(t) = {E : |t & E| >= 3} ------------------------------- */

typedef void (*e_visit)(uint64_t E, void *arg);

static void comb_rec(const int *pool, int np, int start, int need, uint64_t acc, e_visit fn, void *arg) {
    if (need == 0) { fn(acc, arg); return; }
    for (int i = start; i <= np - need; i++) comb_rec(pool, np, i + 1, need - 1, acc | (1ull << pool[i]), fn, arg);
}

/* every E with |E & t| >= 3, each exactly once */
static void for_cover(uint64_t t, e_visit fn, void *arg) {
    int tin[6], out[NPOOL], no = 0;
    n3_mask_to_sorted(t, tin);
    for (int x = 0; x < NPOOL; x++)
        if (!((t >> x) & 1)) out[no++] = x;
    for (int sub = 0; sub < 64; sub++) {
        int k = __builtin_popcount(sub);
        if (k < 3) continue;
        uint64_t part = 0;
        for (int i = 0; i < 6; i++)
            if ((sub >> i) & 1) part |= 1ull << tin[i];
        comb_rec(out, no, 0, 7 - k, part, fn, arg);
    }
}

typedef struct { const Ctx *c; uint64_t cnt, x1, x2; const uint64_t *prev; int nprev; uint64_t other; uint32_t *list; uint64_t cap; } dstate;

static void v_res(uint64_t E, void *arg) {
    dstate *s = arg;
    uint32_t rk = rank_mask(E);
    if (!u_get(s->c->U, rk)) return;
    s->cnt++;
    s->x1 ^= splitmix64((uint64_t)rk ^ s->c->seed1);
    s->x2 ^= splitmix64((uint64_t)rk ^ s->c->seed2);
    if (s->list) {
        if (s->cnt > s->cap) { fprintf(stderr, "res list overflow\n"); exit(3); }
        s->list[s->cnt - 1] = rk;
    }
}

uint64_t n3_direct_res(const Ctx *c, uint64_t t, uint64_t *xor1, uint64_t *xor2) {
    dstate s = {c, 0, 0, 0, NULL, 0, 0, NULL, 0};
    for_cover(t, v_res, &s);
    if (xor1) *xor1 = s.x1;
    if (xor2) *xor2 = s.x2;
    return s.cnt;
}

static int cmp_u32(const void *a, const void *b) {
    uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
    return (x > y) - (x < y);
}

uint32_t *n3_res_list(const Ctx *c, uint64_t t, uint64_t *count) {
    dstate s = {c, 0, 0, 0, NULL, 0, 0, NULL, COVER_PER_TICKET};
    s.list = malloc(sizeof(uint32_t) * COVER_PER_TICKET);
    for_cover(t, v_res, &s);
    qsort(s.list, s.cnt, sizeof(uint32_t), cmp_u32);
    *count = s.cnt;
    return s.list;
}

static void v_union(uint64_t E, void *arg) {
    dstate *s = arg;
    for (int j = 0; j < s->nprev; j++)
        if (__builtin_popcountll(E & s->prev[j]) >= 3) return;
    if (u_get(s->c->U, rank_mask(E))) s->cnt++;
}

uint64_t n3_direct_union(const Ctx *c, const uint64_t *tickets, int n) {
    uint64_t total = 0;
    for (int i = 0; i < n; i++) {
        dstate s = {c, 0, 0, 0, tickets, i, 0, NULL, 0};
        for_cover(tickets[i], v_union, &s);
        total += s.cnt;
    }
    return total;
}

static void v_pair(uint64_t E, void *arg) {
    dstate *s = arg;
    if (__builtin_popcountll(E & s->other) >= 3 && u_get(s->c->U, rank_mask(E))) s->cnt++;
}

int64_t n3_pair_overlap_direct(const Ctx *c, uint64_t b, uint64_t cc) {
    dstate s = {c, 0, 0, 0, NULL, 0, cc, NULL, 0};
    for_cover(b, v_pair, &s);
    return (int64_t)s.cnt;
}
