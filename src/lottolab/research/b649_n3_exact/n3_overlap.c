/* Exact pairwise and triple residual overlaps.
 *
 * Pair: i(B,C) = #{E in U : |E&B| >= 3, |E&C| >= 3}.  The indicator depends only on
 * W = E & (B|C); its Moebius transform over the Venn sizes (|W&s|, |W&b|, |W&c|) with
 * s = B&C, b = B\C, c = C\B is KAPPA, so i(B,C) = sum_{W <= B|C, |W| <= 7} KAPPA(W) N(W),
 * where N(W) = #{E in U : E >= W} (N7 is the residual bit).
 *
 * Triple: i(A,B,C) is enumerated directly: every E in U with >= 3 numbers of each ticket,
 * as W = E & (A|B|C) plus a completion outside A|B|C, each E exactly once. */
#include "n3.h"

static int64_t KAPPA[7][7][7];

static int64_t binom_small(int n, int k) { return (k < 0 || k > n) ? 0 : (int64_t)BIN[n][k]; }

void n3_init_kappa(void) {
    for (int a = 0; a < 7; a++)
        for (int b = 0; b < 7; b++)
            for (int g = 0; g < 7; g++) {
                int64_t sum = 0;
                for (int a2 = 0; a2 <= a; a2++)
                    for (int b2 = 0; b2 <= b; b2++)
                        for (int g2 = 0; g2 <= g; g2++) {
                            if (a2 + b2 < 3 || a2 + g2 < 3) continue;
                            int64_t term = binom_small(a, a2) * binom_small(b, b2) * binom_small(g, g2);
                            int parity = (a - a2) + (b - b2) + (g - g2);
                            sum += (parity & 1) ? -term : term;
                        }
                KAPPA[a][b][g] = sum;
            }
}

int64_t n3_pair_overlap(const Ctx *c, uint64_t B, uint64_t C) {
    uint64_t s = B & C, b = B & ~C, cc = C & ~B;
    int64_t total = 0;
    uint64_t ws = s;
    for (;;) {
        int al = __builtin_popcountll(ws);
        uint64_t wb = b;
        for (;;) {
            int be = __builtin_popcountll(wb);
            if (al + be >= 3) {
                uint64_t wc = cc;
                for (;;) {
                    int ga = __builtin_popcountll(wc);
                    if (al + ga >= 3 && al + be + ga <= 7) {
                        int64_t k = KAPPA[al][be][ga];
                        if (k) total += k * (int64_t)n3_count_N(c, ws | wb | wc);
                    }
                    if (!wc) break;
                    wc = (wc - 1) & cc;
                }
            }
            if (!wb) break;
            wb = (wb - 1) & b;
        }
        if (!ws) break;
        ws = (ws - 1) & s;
    }
    return total;
}

static int64_t completions(const Ctx *c, uint64_t W, const int *out, int no, int start, int need) {
    if (need == 0) return u_get(c->U, rank_mask(W));
    int64_t t = 0;
    for (int i = start; i <= no - need; i++) t += completions(c, W | (1ull << out[i]), out, no, i + 1, need - 1);
    return t;
}

int64_t n3_triple_overlap(const Ctx *c, uint64_t A, uint64_t B, uint64_t C) {
    uint64_t u = A | B | C, b2 = B & ~A, c2 = C & ~(A | B);
    int out[NPOOL], no = 0;
    for (int x = 0; x < NPOOL; x++)
        if (!((u >> x) & 1)) out[no++] = x;
    int64_t total = 0;
    uint64_t wa = A;
    for (;;) {
        int ka = __builtin_popcountll(wa);
        if (ka >= 3) {
            uint64_t wb = b2;
            for (;;) {
                int kb = __builtin_popcountll(wb);
                if (ka + kb <= 7) {
                    uint64_t wc = c2;
                    for (;;) {
                        uint64_t W = wa | wb | wc;
                        int k = __builtin_popcountll(W);
                        if (k <= 7 && __builtin_popcountll(W & B) >= 3 && __builtin_popcountll(W & C) >= 3)
                            total += completions(c, W, out, no, 0, 7 - k);
                        if (!wc) break;
                        wc = (wc - 1) & c2;
                    }
                }
                if (!wb) break;
                wb = (wb - 1) & b2;
            }
        }
        if (!wa) break;
        wa = (wa - 1) & A;
    }
    return total;
}
