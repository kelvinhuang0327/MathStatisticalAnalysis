/* Independent 7-set recount: enumerate each 7-subset once; no residual kernel. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
int main(int argc, char **argv) {
    if (argc < 3) return 2;
    int n = atoi(argv[1]);
    if (n < 7 || n > 49) return 2;
    uint64_t masks[20];
    int count = argc - 2;
    if (count > 20) return 2;
    for (int i=0;i<count;i++) {
        char *end; errno=0;
        masks[i]=strtoull(argv[i+2],&end,10);
        if (errno || *end || __builtin_popcountll(masks[i]) != 6 || masks[i] >= (1ULL<<n)) return 2;
    }
    uint64_t covered=0, total=0;
    for (int a=0;a<n-6;a++) for (int b=a+1;b<n-5;b++)
    for (int c=b+1;c<n-4;c++) for (int d=c+1;d<n-3;d++)
    for (int e=d+1;e<n-2;e++) for (int f=e+1;f<n-1;f++)
    for (int g=f+1;g<n;g++) {
        uint64_t s=(1ULL<<a)|(1ULL<<b)|(1ULL<<c)|(1ULL<<d)|(1ULL<<e)|(1ULL<<f)|(1ULL<<g);
        total++;
        for (int i=0;i<count;i++) if (__builtin_popcountll(s&masks[i])>=3) {covered++;break;}
    }
    if (n == 49 && total != 85900584ULL) return 1;
    printf("%llu\n",(unsigned long long)covered);
    return 0;
}
