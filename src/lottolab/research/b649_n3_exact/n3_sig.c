/* Exact residual-coverage signature classes over the complete ticket universe.
 *
 * Two tickets share a signature iff res(t) == res(t') as sets.  The fingerprint
 * (r(t), XOR1(t), XOR2(t)) is a function of the set res(t), so different fingerprints prove
 * different signatures; every fingerprint class with >= 2 members is then split exactly by
 * comparing the explicit sorted residual lists.  UNIQUE_SIGNATURES is therefore exact. */
#include "n3_sig.h"

static void radix_sort_pairs(uint64_t *key, uint32_t *idx, uint64_t n) {
    uint64_t *k2 = malloc(sizeof(uint64_t) * n);
    uint32_t *i2 = malloc(sizeof(uint32_t) * n);
    uint64_t *cnt = malloc(sizeof(uint64_t) * 65536);
    for (int pass = 0; pass < 4; pass++) {
        int sh = pass * 16;
        memset(cnt, 0, sizeof(uint64_t) * 65536);
        for (uint64_t i = 0; i < n; i++) cnt[(key[i] >> sh) & 0xffff]++;
        uint64_t s = 0;
        for (int d = 0; d < 65536; d++) { uint64_t t = cnt[d]; cnt[d] = s; s += t; }
        for (uint64_t i = 0; i < n; i++) {
            uint64_t p = cnt[(key[i] >> sh) & 0xffff]++;
            k2[p] = key[i];
            i2[p] = idx[i];
        }
        memcpy(key, k2, sizeof(uint64_t) * n);
        memcpy(idx, i2, sizeof(uint32_t) * n);
    }
    free(k2); free(i2); free(cnt);
}

/* lexicographic comparison of the 1-based sorted number tuples of two tickets */
static int lex_less(uint64_t a, uint64_t b) {
    int x[6], y[6];
    n3_mask_to_sorted(a, x);
    n3_mask_to_sorted(b, y);
    for (int i = 0; i < 6; i++)
        if (x[i] != y[i]) return x[i] < y[i];
    return 0;
}

static int same_res(const Ctx *c, uint32_t a, uint32_t b) {
    if (c->r[a] != c->r[b]) return 0;
    if (c->r[a] == 0) return 1;
    uint64_t na, nb;
    uint32_t *la = n3_res_list(c, n3_unrank6(a), &na);
    uint32_t *lb = n3_res_list(c, n3_unrank6(b), &nb);
    int eq = (na == nb) && memcmp(la, lb, sizeof(uint32_t) * na) == 0;
    free(la); free(lb);
    return eq;
}

void n3_signature_classes(const Ctx *c, const uint64_t *f1, const uint64_t *f2, SigReport *rep) {
    memset(rep, 0, sizeof *rep);
    uint64_t n = NT6;
    uint64_t *key = malloc(sizeof(uint64_t) * n);
    uint32_t *idx = malloc(sizeof(uint32_t) * n);
    for (uint64_t i = 0; i < n; i++) { key[i] = f1[i]; idx[i] = (uint32_t)i; }
    radix_sort_pairs(key, idx, n);
    uint64_t merged = 0; /* sum over exact classes of (size - 1) */
    uint64_t largest = 1;
    uint64_t i = 0;
    while (i < n) {
        uint64_t j = i + 1;
        while (j < n && key[j] == key[i]) j++;
        uint64_t m = j - i;
        if (m > 1) {
            rep->fingerprint_runs_multi++;
            /* exact split of this f1 run into classes of identical res() */
            uint32_t *mem = idx + i;
            int *cls = malloc(sizeof(int) * m);
            for (uint64_t a = 0; a < m; a++) cls[a] = -1;
            int ncls = 0;
            for (uint64_t a = 0; a < m; a++) {
                if (cls[a] >= 0) continue;
                cls[a] = ncls;
                uint64_t size = 1;
                uint32_t rep_rank = mem[a];
                for (uint64_t b = a + 1; b < m; b++) {
                    if (cls[b] >= 0) continue;
                    if (f2[mem[a]] != f2[mem[b]] || c->r[mem[a]] != c->r[mem[b]]) continue;
                    rep->exact_pair_checks++;
                    if (same_res(c, mem[a], mem[b])) {
                        cls[b] = ncls;
                        size++;
                        if (lex_less(n3_unrank6(mem[b]), n3_unrank6(rep_rank))) rep_rank = mem[b];
                    } else {
                        rep->fingerprint_false_merges++;
                    }
                }
                if (size > 1) {
                    if (rep->n_multi < SIG_MAX_LISTED) {
                        SigClass *sc = &rep->multi[rep->n_multi];
                        sc->size = size;
                        sc->representative = rep_rank;
                        sc->r = c->r[rep_rank];
                        sc->nmembers = 0;
                        for (uint64_t b = 0; b < m && sc->nmembers < SIG_MAX_MEMBERS; b++)
                            if (cls[b] == ncls) sc->members[sc->nmembers++] = mem[b];
                    }
                    rep->n_multi++;
                    merged += size - 1;
                    if (size > largest) largest = size;
                }
                ncls++;
            }
            free(cls);
        }
        i = j;
    }
    rep->total = n;
    rep->unique = n - merged;
    rep->largest = largest;
    free(key);
    free(idx);
}
