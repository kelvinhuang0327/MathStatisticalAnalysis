#define _POSIX_C_SOURCE 200809L
#include "n3_checkpoint.h"
#include "n3.h"

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Small self-contained SHA-256 keeps the checkpoint format independent of
   optional crypto libraries and is used only for identity and journal chaining. */
typedef struct {
    uint32_t h[8];
    uint64_t bits;
    uint8_t block[64];
    size_t used;
} Sha256;

static const uint32_t K[64] = {
    0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
    0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
    0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
    0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
    0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
    0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
    0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
    0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
};

static uint32_t rotr(uint32_t x, unsigned n) { return (x >> n) | (x << (32 - n)); }

static void sha_block(Sha256 *s, const uint8_t *p) {
    uint32_t w[64];
    for (int i = 0; i < 16; i++)
        w[i] = ((uint32_t)p[4*i] << 24) | ((uint32_t)p[4*i+1] << 16) |
               ((uint32_t)p[4*i+2] << 8) | p[4*i+3];
    for (int i = 16; i < 64; i++) {
        uint32_t a = rotr(w[i-15],7) ^ rotr(w[i-15],18) ^ (w[i-15] >> 3);
        uint32_t b = rotr(w[i-2],17) ^ rotr(w[i-2],19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + a + w[i-7] + b;
    }
    uint32_t a=s->h[0], b=s->h[1], c=s->h[2], d=s->h[3];
    uint32_t e=s->h[4], f=s->h[5], g=s->h[6], h=s->h[7];
    for (int i = 0; i < 64; i++) {
        uint32_t s1=rotr(e,6)^rotr(e,11)^rotr(e,25), ch=(e&f)^(~e&g);
        uint32_t t1=h+s1+ch+K[i]+w[i];
        uint32_t s0=rotr(a,2)^rotr(a,13)^rotr(a,22), maj=(a&b)^(a&c)^(b&c);
        uint32_t t2=s0+maj;
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    s->h[0]+=a; s->h[1]+=b; s->h[2]+=c; s->h[3]+=d;
    s->h[4]+=e; s->h[5]+=f; s->h[6]+=g; s->h[7]+=h;
}

static void sha_init(Sha256 *s) {
    static const uint32_t initial[8] = {
        0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,
        0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u
    };
    memcpy(s->h, initial, sizeof initial);
    s->bits = 0; s->used = 0;
}

static void sha_update(Sha256 *s, const void *data, size_t len) {
    const uint8_t *p = data;
    s->bits += (uint64_t)len * 8;
    while (len) {
        size_t take = 64 - s->used;
        if (take > len) take = len;
        memcpy(s->block + s->used, p, take);
        s->used += take; p += take; len -= take;
        if (s->used == 64) { sha_block(s, s->block); s->used = 0; }
    }
}

static void sha_finish(Sha256 *s, uint8_t out[32]) {
    uint64_t bits = s->bits;
    s->block[s->used++] = 0x80;
    if (s->used > 56) {
        memset(s->block + s->used, 0, 64 - s->used);
        sha_block(s, s->block); s->used = 0;
    }
    memset(s->block + s->used, 0, 56 - s->used);
    for (int i = 0; i < 8; i++) s->block[63-i] = (uint8_t)(bits >> (8*i));
    sha_block(s, s->block);
    for (int i = 0; i < 8; i++) {
        out[4*i]=(uint8_t)(s->h[i]>>24); out[4*i+1]=(uint8_t)(s->h[i]>>16);
        out[4*i+2]=(uint8_t)(s->h[i]>>8); out[4*i+3]=(uint8_t)s->h[i];
    }
}

void n3_sha256_hex(const void *data, size_t len, char out[65]) {
    static const char hex[] = "0123456789abcdef";
    Sha256 s; uint8_t digest[32];
    sha_init(&s); sha_update(&s, data, len); sha_finish(&s, digest);
    for (int i = 0; i < 32; i++) { out[2*i]=hex[digest[i]>>4]; out[2*i+1]=hex[digest[i]&15]; }
    out[64]=0;
}

static void set_error(char *dst, size_t cap, const char *fmt, ...) {
    if (!dst || !cap) return;
    va_list ap; va_start(ap, fmt); vsnprintf(dst, cap, fmt, ap); va_end(ap);
}

static int valid_sha(const char *s) {
    if (!s || strlen(s) != 64) return 0;
    for (int i = 0; i < 64; i++)
        if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f'))) return 0;
    return 1;
}

static char *read_line(FILE *f, size_t *length) {
    size_t cap = 256, n = 0;
    char *line = malloc(cap);
    if (!line) return NULL;
    int ch;
    while ((ch = fgetc(f)) != EOF) {
        if (n + 1 >= cap) {
            if (cap >= 128u * 1024u * 1024u) { free(line); errno = EFBIG; return NULL; }
            cap *= 2;
            char *next = realloc(line, cap);
            if (!next) { free(line); return NULL; }
            line = next;
        }
        line[n++] = (char)ch;
        if (ch == '\n') break;
    }
    if (!n) { free(line); return NULL; }
    line[n] = 0;
    if (length) *length = n;
    return line;
}

static int parse_u64(const char *s, uint64_t *out) {
    char *end = NULL;
    errno = 0;
    unsigned long long v = strtoull(s, &end, 10);
    if (errno || !s[0] || !end || *end) return 0;
    *out = (uint64_t)v; return 1;
}

static int parse_i64(const char *s, int64_t *out) {
    char *end = NULL;
    errno = 0;
    long long v = strtoll(s, &end, 10);
    if (errno || !s[0] || !end || *end) return 0;
    *out = (int64_t)v; return 1;
}

static void int128_string(__int128 value, char out[64]) {
    char tmp[64]; size_t n = 0; int negative = value < 0;
    unsigned __int128 v = negative ? (unsigned __int128)(-value) : (unsigned __int128)value;
    do { tmp[n++] = (char)('0' + (v % 10)); v /= 10; } while (v && n < sizeof tmp);
    size_t j = 0;
    if (negative) out[j++] = '-';
    while (n) out[j++] = tmp[--n];
    out[j] = 0;
}

static int parse_int128(const char *s, __int128 *out) {
    if (!*s) return 0;
    unsigned __int128 value = 0;
    const unsigned __int128 max = (((unsigned __int128)-1) >> 1);
    for (; *s; s++) {
        if (*s < '0' || *s > '9') return 0;
        unsigned digit = (unsigned)(*s - '0');
        if (value > (max - digit) / 10) return 0;
        value = value * 10 + digit;
    }
    *out = (__int128)value;
    return 1;
}

static void update_aggregate(N3Checkpoint *cp, int64_t incumbent, uint64_t tie_count,
                            const uint32_t *ties, uint64_t ties_stored) {
    if (incumbent > cp->incumbent) {
        cp->incumbent = incumbent;
        cp->tie_count = tie_count;
        cp->ties_stored = 0;
    } else if (incumbent == cp->incumbent) {
        cp->tie_count += tie_count;
    }
    uint64_t room = cp->ties_capacity - cp->ties_stored;
    uint64_t copy = ties_stored < room ? ties_stored : room;
    if (copy) {
        memcpy(cp->ties + 3 * cp->ties_stored, ties, (size_t)copy * 3 * sizeof(uint32_t));
        cp->ties_stored += copy;
    }
}

static int parse_record(N3Checkpoint *cp, char *line, uint64_t total, uint64_t max_ties,
                        __int128 accounted_base, char *error, size_t error_size) {
    size_t len = strlen(line);
    if (!len || line[len-1] != '\n') { set_error(error,error_size,"truncated checkpoint journal line"); return 0; }
    line[len-1] = 0;
    char *hash_sep = strrchr(line, '|');
    if (!hash_sep || strlen(hash_sep + 1) != 64) { set_error(error,error_size,"malformed checkpoint journal digest"); return 0; }
    *hash_sep = 0;
    char expected_hash[65];
    Sha256 sh; uint8_t digest[32]; static const char hex[]="0123456789abcdef";
    sha_init(&sh); sha_update(&sh, cp->prefix_sha256, 64); sha_update(&sh, "\n", 1);
    sha_update(&sh, line, strlen(line)); sha_finish(&sh, digest);
    for (int i=0;i<32;i++) { expected_hash[2*i]=hex[digest[i]>>4]; expected_hash[2*i+1]=hex[digest[i]&15]; }
    expected_hash[64]=0;
    if (strcmp(expected_hash, hash_sep + 1)) { set_error(error,error_size,"checkpoint journal prefix SHA256 mismatch"); return 0; }

    char *fields[9], *save = NULL, *p = strtok_r(line, "|", &save);
    for (int i=0; i<9; i++) { fields[i] = p; if (!p) { set_error(error,error_size,"malformed checkpoint journal record"); return 0; } p = strtok_r(NULL,"|",&save); }
    if (p || strcmp(fields[0],"A")) { set_error(error,error_size,"unsupported checkpoint journal record"); return 0; }
    uint64_t anchor, count, stored;
    int64_t incumbent, bound;
    __int128 accounted;
    if (!parse_u64(fields[1],&anchor) || !parse_i64(fields[3],&incumbent) ||
        !parse_u64(fields[5],&count) || !parse_u64(fields[6],&stored) ||
        !parse_int128(fields[7],&accounted)) {
        set_error(error,error_size,"invalid numeric checkpoint field"); return 0;
    }
    int pruned = !strcmp(fields[2],"P");
    if (!pruned && strcmp(fields[2],"C")) { set_error(error,error_size,"invalid checkpoint anchor status"); return 0; }
    if (pruned) {
        if (!parse_i64(fields[4],&bound) || bound < 0 || bound >= incumbent || count || stored) {
            set_error(error,error_size,"invalid pruned-anchor certificate"); return 0;
        }
    } else if (strcmp(fields[4],"-")) { set_error(error,error_size,"complete anchor has a pruning bound"); return 0; }
    if (anchor != cp->next_anchor || anchor >= total || incumbent < cp->incumbent ||
        stored > count || stored > max_ties || accounted < accounted_base ||
        accounted < cp->accounted || accounted > (__int128)NT6*(NT6-1)*(NT6-2)/6 ||
        (!pruned && incumbent > cp->incumbent && count == 0) ||
        (!pruned && incumbent == cp->incumbent && count > UINT64_MAX-cp->tie_count)) {
        set_error(error,error_size,"checkpoint anchor order or aggregate is invalid"); return 0;
    }

    uint32_t *triples = stored ? malloc((size_t)stored * 3 * sizeof(uint32_t)) : NULL;
    if (stored && !triples) { set_error(error,error_size,"checkpoint tie allocation failed"); return 0; }
    if (!strcmp(fields[8],"-")) {
        if (stored) { free(triples); set_error(error,error_size,"missing checkpoint ties"); return 0; }
    } else {
        char *tie_save = NULL, *tok = strtok_r(fields[8],",",&tie_save);
        uint64_t n = 0;
        while (tok) {
            uint64_t rank;
            if (n >= stored * 3 || !parse_u64(tok,&rank) || rank >= NT6) {
                free(triples); set_error(error,error_size,"invalid checkpoint tie rank"); return 0;
            }
            triples[n++] = (uint32_t)rank;
            tok = strtok_r(NULL,",",&tie_save);
        }
        if (n != stored * 3) { free(triples); set_error(error,error_size,"checkpoint tie count mismatch"); return 0; }
    }
    if (pruned) {
        if (incumbent != cp->incumbent || stored || count) {
            free(triples); set_error(error,error_size,"pruned anchor changed the incumbent"); return 0;
        }
    } else {
        update_aggregate(cp,incumbent,count,triples,stored);
        cp->anchors_completed++;
    }
    free(triples);
    cp->accounted = accounted;
    cp->next_anchor++;
    memcpy(cp->prefix_sha256,hash_sep+1,65);
    (void)len;
    return 1;
}

int n3_checkpoint_open(N3Checkpoint *cp, const char *path, const char *destroy_set,
                       uint64_t total_anchors, int64_t f0, const char *input_sha256,
                       const char *engine_sha256, const char *solver_config_sha256,
                       __int128 accounted_base, uint64_t max_ties, char *error, size_t error_size) {
    memset(cp,0,sizeof *cp);
    if (!valid_sha(input_sha256) || !valid_sha(engine_sha256) || !valid_sha(solver_config_sha256)) {
        set_error(error,error_size,"checkpoint identities must be lowercase SHA256 values"); return 0;
    }
    char body[512], base_hash[65], header[600];
    int n = snprintf(body,sizeof body,
                     "N3RESUME1|DESTROY_SET=%s|TOTAL_ANCHORS=%" PRIu64 "|F0=%" PRId64
                     "|INPUT_SHA256=%s|ENGINE_SHA256=%s|SOLVER_CONFIG_SHA256=%s",
                     destroy_set,total_anchors,f0,input_sha256,engine_sha256,solver_config_sha256);
    if (n < 0 || (size_t)n >= sizeof body) { set_error(error,error_size,"checkpoint metadata is too long"); return 0; }
    n3_sha256_hex(body,(size_t)n,base_hash);
    n = snprintf(header,sizeof header,"%s|JOURNAL_PREFIX_SHA256=%s\n",body,base_hash);
    if (n < 0 || (size_t)n >= sizeof header) { set_error(error,error_size,"checkpoint metadata is too long"); return 0; }
    cp->incumbent = f0;
    cp->accounted = accounted_base;
    cp->ties_capacity = max_ties;
    cp->ties = calloc((size_t)max_ties * 3, sizeof(uint32_t));
    if (!cp->ties) { set_error(error,error_size,"checkpoint tie allocation failed"); return 0; }

    int fd = open(path,O_RDWR|O_CREAT|O_EXCL,0600);
    if (fd >= 0) {
        size_t left = (size_t)n; const char *at = header;
        while (left) {
            ssize_t wrote = write(fd,at,left);
            if (wrote <= 0) { set_error(error,error_size,"cannot write checkpoint metadata: %s",strerror(errno)); close(fd); return 0; }
            at += wrote; left -= (size_t)wrote;
        }
        if (fsync(fd) != 0) { set_error(error,error_size,"cannot sync checkpoint metadata: %s",strerror(errno)); close(fd); return 0; }
        close(fd);
    } else if (errno != EEXIST) {
        set_error(error,error_size,"cannot create checkpoint: %s",strerror(errno)); return 0;
    }

    cp->file = fopen(path,"r+b");
    if (!cp->file) { set_error(error,error_size,"cannot open checkpoint: %s",strerror(errno)); return 0; }
    size_t line_len = 0;
    char *line = read_line(cp->file,&line_len);
    if (!line || line_len != (size_t)n || memcmp(line,header,(size_t)n)) {
        free(line); set_error(error,error_size,"checkpoint immutable metadata mismatch"); return 0;
    }
    free(line);
    memcpy(cp->prefix_sha256,base_hash,65);
    if (fseek(cp->file,(long)n,SEEK_SET) != 0) { set_error(error,error_size,"cannot seek checkpoint journal"); return 0; }
    for (;;) {
        size_t record_len = 0;
        char *record = read_line(cp->file,&record_len);
        if (!record) {
            if (feof(cp->file)) break;
            set_error(error,error_size,"cannot read checkpoint journal"); return 0;
        }
        int ok = parse_record(cp,record,total_anchors,max_ties,accounted_base,error,error_size);
        free(record);
        if (!ok) return 0;
        (void)record_len;
    }
    if (fseek(cp->file,0,SEEK_END) != 0) { set_error(error,error_size,"cannot seek checkpoint end"); return 0; }
    return 1;
}

int n3_checkpoint_append(N3Checkpoint *cp, uint64_t anchor_id, int pruned,
                         int64_t incumbent, int64_t upper_bound, uint64_t tie_count,
                         const uint32_t *ties, uint64_t ties_stored, __int128 accounted,
                         char *error, size_t error_size) {
    if (!cp->file || anchor_id != cp->next_anchor || incumbent < cp->incumbent ||
        ties_stored > tie_count || ties_stored > cp->ties_capacity ||
        accounted < cp->accounted || accounted > (__int128)NT6*(NT6-1)*(NT6-2)/6 ||
        (!pruned && incumbent == cp->incumbent && tie_count > UINT64_MAX-cp->tie_count) ||
        (pruned && (incumbent != cp->incumbent || upper_bound < 0 ||
                    upper_bound >= incumbent || tie_count || ties_stored)) ||
        (!pruned && upper_bound != -1)) {
        set_error(error,error_size,"invalid or duplicate checkpoint anchor append"); return 0;
    }
    if (ties_stored && !ties) {
        set_error(error,error_size,"checkpoint tie data is missing"); return 0;
    }
    for (uint64_t i=0;i<ties_stored*3;i++) {
        if (ties[i] >= NT6) {
            set_error(error,error_size,"checkpoint tie rank is outside the candidate universe"); return 0;
        }
    }
    char acct[64]; int128_string(accounted,acct);
    size_t cap = 256 + (size_t)ties_stored * 36;
    char *payload = malloc(cap);
    if (!payload) { set_error(error,error_size,"checkpoint record allocation failed"); return 0; }
    int n = snprintf(payload,cap,"A|%" PRIu64 "|%c|%" PRId64 "|",
                     anchor_id,pruned?'P':'C',incumbent);
    if (n < 0 || (size_t)n >= cap) { free(payload); set_error(error,error_size,"checkpoint record overflow"); return 0; }
    size_t used = (size_t)n;
    if (pruned) n = snprintf(payload+used,cap-used,"%" PRId64 "|",upper_bound);
    else n = snprintf(payload+used,cap-used,"-|");
    if (n < 0 || (size_t)n >= cap-used) { free(payload); set_error(error,error_size,"checkpoint record overflow"); return 0; }
    used += (size_t)n;
    n = snprintf(payload+used,cap-used,"%" PRIu64 "|%" PRIu64 "|%s|",
                 tie_count,ties_stored,acct);
    if (n < 0 || (size_t)n >= cap-used) { free(payload); set_error(error,error_size,"checkpoint record overflow"); return 0; }
    used += (size_t)n;
    if (!ties_stored) {
        n = snprintf(payload+used,cap-used,"-");
        if (n < 0 || (size_t)n >= cap-used) { free(payload); set_error(error,error_size,"checkpoint record overflow"); return 0; }
        used += (size_t)n;
    } else {
        for (uint64_t i=0;i<ties_stored*3;i++) {
            n = snprintf(payload+used,cap-used,"%s%" PRIu32,i?",":"",ties[i]);
            if (n < 0 || (size_t)n >= cap-used) { free(payload); set_error(error,error_size,"checkpoint record overflow"); return 0; }
            used += (size_t)n;
        }
    }
    Sha256 sh; uint8_t digest[32]; static const char hex[]="0123456789abcdef"; char hash[65];
    sha_init(&sh); sha_update(&sh,cp->prefix_sha256,64); sha_update(&sh,"\n",1); sha_update(&sh,payload,used); sha_finish(&sh,digest);
    for(int i=0;i<32;i++){hash[2*i]=hex[digest[i]>>4];hash[2*i+1]=hex[digest[i]&15];} hash[64]=0;
    size_t line_cap = used + 67;
    char *line = malloc(line_cap);
    if (!line) { free(payload); set_error(error,error_size,"checkpoint line allocation failed"); return 0; }
    n = snprintf(line,line_cap,"%s|%s\n",payload,hash);
    free(payload);
    if (n < 0 || (size_t)n >= line_cap) { free(line); set_error(error,error_size,"checkpoint line overflow"); return 0; }
    if (fwrite(line,1,(size_t)n,cp->file)!=(size_t)n || fflush(cp->file)!=0 || fsync(fileno(cp->file))!=0) {
        free(line); set_error(error,error_size,"cannot durably append checkpoint: %s",strerror(errno)); return 0;
    }
    free(line);
    update_aggregate(cp,incumbent,tie_count,ties,ties_stored);
    if (!pruned) cp->anchors_completed++;
    cp->accounted=accounted;
    cp->next_anchor++;
    memcpy(cp->prefix_sha256,hash,65);
    return 1;
}

void n3_checkpoint_close(N3Checkpoint *cp) {
    if (cp->file) fclose(cp->file);
    free(cp->ties);
    memset(cp,0,sizeof *cp);
}
