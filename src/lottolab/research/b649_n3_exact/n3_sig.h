#ifndef N3_SIG_H
#define N3_SIG_H
#include "n3.h"

#define SIG_MAX_LISTED 64
#define SIG_MAX_MEMBERS 64

typedef struct {
    uint64_t size;
    uint32_t representative; /* lexicographically lowest member (colex rank) */
    int32_t r;
    int nmembers;
    uint32_t members[SIG_MAX_MEMBERS];
} SigClass;

typedef struct {
    uint64_t total, unique, largest;
    uint64_t n_multi;                  /* exact classes with >= 2 members */
    uint64_t fingerprint_runs_multi;   /* XOR1 runs with >= 2 members */
    uint64_t exact_pair_checks;        /* explicit residual-list comparisons */
    uint64_t fingerprint_false_merges; /* equal fingerprints, different residual lists */
    SigClass multi[SIG_MAX_LISTED];
} SigReport;

void n3_signature_classes(const Ctx *c, const uint64_t *f1, const uint64_t *f2, SigReport *rep);

#endif
