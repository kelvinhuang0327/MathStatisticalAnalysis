/* Per-ticket overlap tables: for a fixed ticket X, M_X(Y) = #{E in res(X) : E >= Y} for
 * |Y| = 3, 4, 5.  Then for every ticket T,
 *   i(X,T) = |res(X) & res(T)| = sum_{Y<=T,|Y|=3} M3 - 3 sum_{|Y|=4} M4 + 6 sum_{|Y|=5} M5 - 10 M6(T)
 * with M6(T) = #{x : T+x in res(X)} evaluated directly (it needs |T & X| >= 2). */
#include "n3_mtab.h"

static int P7_3[35][3], P7_4[35][4], P7_5[21][5], P6_3[20][3], P6_4[15][4], P6_5[6][5];
static int ready = 0;

static void tables(void) {
    if (ready) return;
    int n3 = 0, n4 = 0, n5 = 0;
    for (int m = 0; m < 128; m++) {
        int k = __builtin_popcount(m), p[7], q = 0;
        for (int i = 0; i < 7; i++)
            if ((m >> i) & 1) p[q++] = i;
        if (k == 3) memcpy(P7_3[n3++], p, sizeof(int) * 3);
        if (k == 4) memcpy(P7_4[n4++], p, sizeof(int) * 4);
        if (k == 5) memcpy(P7_5[n5++], p, sizeof(int) * 5);
    }
    n3 = n4 = n5 = 0;
    for (int m = 0; m < 64; m++) {
        int k = __builtin_popcount(m), p[6], q = 0;
        for (int i = 0; i < 6; i++)
            if ((m >> i) & 1) p[q++] = i;
        if (k == 3) memcpy(P6_3[n3++], p, sizeof(int) * 3);
        if (k == 4) memcpy(P6_4[n4++], p, sizeof(int) * 4);
        if (k == 5) memcpy(P6_5[n5++], p, sizeof(int) * 5);
    }
    ready = 1;
}

void mtab_init(MTab *m) {
    tables();
    m->M3 = calloc(NT3, sizeof(int32_t));
    m->M4 = calloc(NT4, sizeof(int32_t));
    m->M5 = calloc(NT5, sizeof(uint16_t));
    m->X = 0;
    m->count = 0;
}

void mtab_free(MTab *m) { free(m->M3); free(m->M4); free(m->M5); }

static inline void add_E(MTab *m, uint64_t E) {
    int e[7];
    n3_mask_to_sorted(E, e);
    for (int q = 0; q < 35; q++) {
        m->M3[BIN[e[P7_3[q][0]]][1] + BIN[e[P7_3[q][1]]][2] + BIN[e[P7_3[q][2]]][3]]++;
        m->M4[BIN[e[P7_4[q][0]]][1] + BIN[e[P7_4[q][1]]][2] + BIN[e[P7_4[q][2]]][3] + BIN[e[P7_4[q][3]]][4]]++;
    }
    for (int q = 0; q < 21; q++)
        m->M5[BIN[e[P7_5[q][0]]][1] + BIN[e[P7_5[q][1]]][2] + BIN[e[P7_5[q][2]]][3] + BIN[e[P7_5[q][3]]][4] +
              BIN[e[P7_5[q][4]]][5]]++;
}

/* enumerate res(X) explicitly and fill the tables */
void mtab_build(MTab *m, const Ctx *c, uint64_t X) {
    memset(m->M3, 0, NT3 * sizeof(int32_t));
    memset(m->M4, 0, NT4 * sizeof(int32_t));
    memset(m->M5, 0, NT5 * sizeof(uint16_t));
    m->X = X;
    uint64_t cnt = 0;
    int xin[6], out[NPOOL], no = 0;
    n3_mask_to_sorted(X, xin);
    for (int x = 0; x < NPOOL; x++)
        if (!((X >> x) & 1)) out[no++] = x;
    for (int sub = 0; sub < 64; sub++) {
        int k = __builtin_popcount(sub);
        if (k < 3) continue;
        uint64_t part = 0;
        for (int i = 0; i < 6; i++)
            if ((sub >> i) & 1) part |= 1ull << xin[i];
        int need = 7 - k;
        if (need == 1) {
            for (int i = 0; i < no; i++) {
                uint64_t E = part | (1ull << out[i]);
                if (u_get(c->U, rank_mask(E))) { add_E(m, E); cnt++; }
            }
        } else if (need == 2) {
            for (int i = 0; i < no; i++)
                for (int j = i + 1; j < no; j++) {
                    uint64_t E = part | (1ull << out[i]) | (1ull << out[j]);
                    if (u_get(c->U, rank_mask(E))) { add_E(m, E); cnt++; }
                }
        } else if (need == 3) {
            for (int i = 0; i < no; i++)
                for (int j = i + 1; j < no; j++)
                    for (int l = j + 1; l < no; l++) {
                        uint64_t E = part | (1ull << out[i]) | (1ull << out[j]) | (1ull << out[l]);
                        if (u_get(c->U, rank_mask(E))) { add_E(m, E); cnt++; }
                    }
        } else { /* need == 4 */
            for (int i = 0; i < no; i++)
                for (int j = i + 1; j < no; j++)
                    for (int l = j + 1; l < no; l++)
                        for (int h = l + 1; h < no; h++) {
                            uint64_t E = part | (1ull << out[i]) | (1ull << out[j]) | (1ull << out[l]) | (1ull << out[h]);
                            if (u_get(c->U, rank_mask(E))) { add_E(m, E); cnt++; }
                        }
        }
    }
    m->count = cnt;
}

int64_t mtab_overlap(const MTab *m, const Ctx *c, uint64_t T) {
    int e[6];
    n3_mask_to_sorted(T, e);
    int64_t s3 = 0, s4 = 0, s5 = 0, m6 = 0;
    for (int q = 0; q < 20; q++) s3 += m->M3[BIN[e[P6_3[q][0]]][1] + BIN[e[P6_3[q][1]]][2] + BIN[e[P6_3[q][2]]][3]];
    for (int q = 0; q < 15; q++)
        s4 += m->M4[BIN[e[P6_4[q][0]]][1] + BIN[e[P6_4[q][1]]][2] + BIN[e[P6_4[q][2]]][3] + BIN[e[P6_4[q][3]]][4]];
    for (int q = 0; q < 6; q++)
        s5 += m->M5[BIN[e[P6_5[q][0]]][1] + BIN[e[P6_5[q][1]]][2] + BIN[e[P6_5[q][2]]][3] + BIN[e[P6_5[q][3]]][4] +
                    BIN[e[P6_5[q][4]]][5]];
    int sh = __builtin_popcountll(T & m->X);
    if (sh >= 3) {
        m6 = c->N6[rank_mask(T)];
    } else if (sh == 2) {
        uint64_t rest = m->X & ~T;
        while (rest) {
            int x = __builtin_ctzll(rest);
            rest &= rest - 1;
            m6 += u_get(c->U, rank_mask(T | (1ull << x)));
        }
    }
    return s3 - 3 * s4 + 6 * s5 - 10 * m6;
}
