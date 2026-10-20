#ifndef N3_CHECKPOINT_H
#define N3_CHECKPOINT_H

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

typedef struct {
    FILE *file;
    uint64_t next_anchor;
    uint64_t anchors_completed;
    int64_t incumbent;
    uint64_t tie_count;
    uint32_t *ties;
    uint64_t ties_stored;
    uint64_t ties_capacity;
    __int128 accounted;
    char prefix_sha256[65];
} N3Checkpoint;

void n3_sha256_hex(const void *data, size_t len, char out[65]);

int n3_checkpoint_open(
    N3Checkpoint *checkpoint,
    const char *path,
    const char *destroy_set,
    uint64_t total_anchors,
    int64_t f0,
    const char *input_sha256,
    const char *engine_sha256,
    const char *solver_config_sha256,
    __int128 accounted_base,
    uint64_t max_ties,
    char *error,
    size_t error_size
);

int n3_checkpoint_append(
    N3Checkpoint *checkpoint,
    uint64_t anchor_id,
    int pruned,
    int64_t incumbent,
    int64_t upper_bound,
    uint64_t tie_count,
    const uint32_t *ties,
    uint64_t ties_stored,
    __int128 accounted,
    char *error,
    size_t error_size
);

void n3_checkpoint_close(N3Checkpoint *checkpoint);

#endif
