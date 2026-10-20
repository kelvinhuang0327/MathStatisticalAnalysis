#ifndef N3_MTAB_H
#define N3_MTAB_H
#include "n3.h"

typedef struct {
    int32_t *M3;
    int32_t *M4;
    uint16_t *M5;
    uint64_t X;
    uint64_t count; /* |res(X)| as enumerated */
} MTab;

void mtab_init(MTab *m);
void mtab_free(MTab *m);
void mtab_build(MTab *m, const Ctx *c, uint64_t X);
int64_t mtab_overlap(const MTab *m, const Ctx *c, uint64_t T);

#endif
