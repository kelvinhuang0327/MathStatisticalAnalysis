// Exact full-universe conditional marginals; no candidate filtering before scoring.
// Reuses the mathematical transform from the pinned residual-pool engine:
// m(t) = sum_{B subset t} (1,-3,6,-10)[|B|-3] g(B).
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <functional>
#include <thread>
#include <vector>

struct Universe {
    int n, workers;
    uint64_t binom[8][65]{};
    std::vector<uint8_t> rows[7];
    std::vector<uint32_t> ranks[6];
    std::vector<std::vector<int>> choices[6];
    std::vector<uint8_t> g6;
    std::vector<uint32_t> g[6];
    Universe(int pool, int threads): n(pool), workers(threads) {
        for (int x=0; x<=n; ++x) binom[0][x]=1;
        for (int k=1; k<=7; ++k)
            for (int x=1; x<=n; ++x) binom[k][x]=binom[k][x-1]+binom[k-1][x-1];
        for (int k=3; k<=6; ++k) {
            rows[k].resize(binom[k][n]*k);
            std::vector<int> row;
            std::function<void(int)> visit = [&](int low) {
                if (int(row.size())==k) {
                    uint64_t r=0;
                    for(int j=0;j<k;++j) r+=binom[j+1][row[j]];
                    for(int j=0;j<k;++j) rows[k][r*k+j]=row[j];
                    return;
                }
                for(int x=low; x<=n-(k-int(row.size())); ++x) {
                    row.push_back(x); visit(x+1); row.pop_back();
                }
            };
            visit(0);
        }
        for(int k=3;k<=5;++k) {
            std::vector<int> row;
            std::function<void(int)> visit = [&](int low) {
                if(int(row.size())==k) { choices[k].push_back(row); return; }
                for(int x=low;x<=6-(k-int(row.size()));++x) {
                    row.push_back(x); visit(x+1); row.pop_back();
                }
            };
            visit(0);
            ranks[k].resize(binom[6][n]*choices[k].size());
            parallel(binom[6][n], [&](uint64_t begin,uint64_t end) {
                for(uint64_t i=begin;i<end;++i) {
                    const uint8_t* t=&rows[6][6*i];
                    for(size_t c=0;c<choices[k].size();++c) {
                        uint32_t r=0;
                        for(int j=0;j<k;++j) r+=binom[j+1][t[choices[k][c][j]]];
                        ranks[k][i*choices[k].size()+c]=r;
                    }
                }
            });
            g[k].resize(binom[k][n]);
        }
        g6.resize(binom[6][n]);
    }
    template<class F> void parallel(uint64_t count,F f) {
        if(workers==1) { f(0,count); return; }
        std::thread second([&](){f(count/2,count);});
        f(0,count/2); second.join();
    }
    int score(const uint64_t* frozen,int size,int32_t* output,uint64_t* stats) {
        uint64_t links[64][64]{};
        for(int t=0;t<size;++t) {
            if(__builtin_popcountll(frozen[t])!=6 || (frozen[t]>>n)) return 1;
            for(int a=0;a<n;++a) if(frozen[t]&(1ULL<<a))
                for(int b=a+1;b<n;++b) if(frozen[t]&(1ULL<<b))
                    links[a][b]=links[b][a]=links[a][b]|(frozen[t]&~((1ULL<<a)|(1ULL<<b)));
        }
        uint64_t sum_top[2]{},sum_marginal[2]{};
        const uint64_t total=binom[6][n];
        parallel(total,[&](uint64_t begin,uint64_t end) {
            uint64_t sum=0;
            for(uint64_t i=begin;i<end;++i) {
                const uint8_t* t=&rows[6][6*i];
                uint64_t occupied=0,forbidden=0;
                for(int a=0;a<6;++a) {
                    occupied|=1ULL<<t[a];
                    for(int b=a+1;b<6;++b) forbidden|=links[t[a]][t[b]];
                }
                const int value=(occupied&forbidden)?0:n-6-__builtin_popcountll(forbidden);
                g6[i]=value; sum+=value;
            }
            sum_top[begin?1:0]=sum;
        });
        std::atomic<int> error{0};
        for(int k=5;k>=3;--k) {
            parallel(binom[k][n],[&](uint64_t begin,uint64_t end) {
                for(uint64_t i=begin;i<end;++i) {
                    const uint8_t* t=&rows[k][i*k];
                    uint64_t prefix[7]{},suffix[7]{};
                    for(int j=0;j<k;++j) prefix[j+1]=prefix[j]+binom[j+1][t[j]];
                    for(int j=k-1;j>=0;--j) suffix[j]=suffix[j+1]+binom[j+2][t[j]];
                    uint64_t sum=0;
                    for(int p=0;p<=k;++p) {
                        const int low=p?t[p-1]+1:0,high=p<k?t[p]:n;
                        for(int x=low;x<high;++x) {
                            const uint64_t r=prefix[p]+binom[p+1][x]+suffix[p];
                            sum+=k==5?g6[r]:g[k+1][r];
                        }
                    }
                    if(sum%(7-k)) error=2;
                    g[k][i]=sum/(7-k);
                }
            });
        }
        parallel(total,[&](uint64_t begin,uint64_t end) {
            uint64_t sum=0;
            for(uint64_t i=begin;i<end;++i) {
                int64_t value=-10*int64_t(g6[i]);
                for(int k=3;k<=5;++k) {
                    int64_t subtotal=0;
                    const uint32_t* r=&ranks[k][i*choices[k].size()];
                    for(size_t c=0;c<choices[k].size();++c) subtotal+=g[k][r[c]];
                    value+=(k==3?1:k==4?-3:6)*subtotal;
                }
                if(value<0 || value>INT32_MAX) error=3;
                output[i]=int32_t(value); sum+=value;
            }
            sum_marginal[begin?1:0]=sum;
        });
        stats[0]=total; stats[1]=sum_top[0]+sum_top[1];
        stats[2]=sum_marginal[0]+sum_marginal[1];
        return error;
    }
};
extern "C" {
void* b649_create(int n,int workers) {
    if(n<7 || n>49 || workers<1 || workers>2) return nullptr;
    try { return new Universe(n,workers); } catch(...) { return nullptr; }
}
void b649_destroy(void* u) { delete static_cast<Universe*>(u); }
uint64_t b649_total(void* u) { auto* p=static_cast<Universe*>(u); return p->binom[6][p->n]; }
const uint8_t* b649_rows(void* u) { return static_cast<Universe*>(u)->rows[6].data(); }
int b649_score(void* u,const uint64_t* masks,int size,int32_t* output,uint64_t* stats) {
    return static_cast<Universe*>(u)->score(masks,size,output,stats);
}
}
