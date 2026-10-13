# C235 full-profile bound proof

This is the compact, reproducible proof artifact for profile
`66655555555422000000`. It materializes the completed report from Codex task
`B649_FINAL_TIED_OWNER_C_FULL_PROFILE_R1` (thread
`01a132f3-6c00-7042-89ff-0f60a1b6fa52`, turn
`01a132f3-9a57-74c0-8c95-7e2212c5ddd8`, final item
`msg_0178b51303703352016acd91cca0808191ba728af34c7cadf0`). That report was
read for this integration. This file contains the proof premises and the
arithmetic needed by the local checker; it does not claim a legal witness or
cap attainment.

## Profile and Goodman identity

There are 20 tickets, each carrying six labels. The 22 triple supports are
linear and lie in the core; the 27 pair supports complete the six-label
incidences. The overlap graph `G` has 93 edges and degree `6+d_v`, where the
full triple-degree profile is

```text
d = (6^3, 5^8, 4, 2^2, 0^6).
```

Thus the core `K={v:d_v>0}` has 14 vertices and the zero set `Z` has six.
For `H=Ḡ`, `|E(H)|=97`. Inclusion-exclusion over the 66 triangle edges and
the 27 pair edges gives

```text
T = C(20,3) - 18|E(H)| + Σ_v C(13-d_v,2) - t(H)
  = 1140 - 18·97 + 901 - t(H)
  = 295 - t(H).
```

Write `M=H[K]` and `F=H[Z]`. For a core vertex `x`, let
`σ_x=|N_G(x)∩Z|`; for a zero vertex `u`, let
`ℓ_u=deg_F(u)` and `ζ_u=|N_G(u)∩K|`. Since every zero has six neighbours and
only five other zero vertices,

```text
ζ_u = 1 + ℓ_u,
Σ_x σ_x = Σ_u ζ_u = 6 + 2e,   e=|E(F)|.
```

Triple supports do not contain zeros, so every core-to-zero edge is a pair
support and `0≤σ_x≤6-d_x`. The mixed-triangle decomposition is

```text
T = 241 + Σ_x σ_x(σ_x+4-d_x) + Σ_u ζ_u(ζ_u-8) - P,
P = t(M)+t(F)
    + Σ_{xy∈E(M)} |N_G(x)∩N_G(y)∩Z|
    + Σ_{uv∈E(F)} |N_G(u)∩N_G(v)∩K|  ≥ 0.
```

Let `a` be the sum of the eight degree-5 core values of `σ`, let `q` be the
degree-4 value, and let `b,c` be the two degree-2 values. Their ranges and
sum are

```text
0≤a≤8, 0≤q≤2, 0≤b,c≤4,
a+q+b+c = 6+2e.
```

The degree-6 core values are zero. Substituting `ζ=1+ℓ` in the identity gives
the exact integer formula

```text
T = 211 + Q + Σ_u ℓ_u² - 8e - P,
Q = -2a + q(q-2) + b² + c².
```

For a simple graph with `e` edges,
`Σℓ_u² = 2ΣC(ℓ_u,2)+2e ≤ e(e+1)`: each unordered pair of edges shares at
most one endpoint. Also `Σσ≤18`, hence `e≤6`. Enumerating the finite integer
ranges for `(a,q,b,c)` at each `a+q+b+c=6+2e` gives the following complete
relaxation table. The column “before `P`” is
`211 + max(Q) + e(e+1) - 8e`.

| `e` | `r=6+2e` | `max Q` | `T` bound before `P` | final bound |
|---:|---:|---:|---:|---:|
| 0 | 6 | 20 | 231 | 231 |
| 1 | 8 | 32 | 237 | 235 |
| 2 | 10 | 32 | 233 | 233 |
| 3 | 12 | 28 | 227 | 227 |
| 4 | 14 | 24 | 223 | 223 |
| 5 | 16 | 20 | 221 | 221 |
| 6 | 18 | 16 | 221 | 221 |

For `e=1`, `Q=32` is attained only at `(a,q,b,c)=(0,0,4,4)`. In that case
only the two degree-2 core vertices have core-to-zero edges. The unique edge
of `F` has endpoints with `ℓ=1`, hence each endpoint has two core neighbours;
both endpoints must therefore meet both degree-2 core vertices. The last
nonnegative sum in `P` contributes two common core neighbours, so `P≥2` and
the exceptional bound is `237-2=235`. Every other `e=1` integer case has
`Q≤24`, and gives `T≤229`. Therefore `T≤235` for every legal realization of
the full profile. The cap is a proved upper bound; attainment is unknown.

## Route-B envelope

For this profile, let `w=Σ_v C(6+d_v,2)=829` and
`u=Σ_v C(6+d_v,3)`. For each integer `22≤t≤235`, compute with exact integer
rounding:

```text
K4(t) = max(0, ceil((u - 10(w-3t))/4))
       = max(0, ceil((30t-5958)/4))
Amax  = floor(596/3) = 198
S4(t) = max(112, 679K4(t) - 231min(K4(t),198))
S3(t) = 2029216 + 11872t
U(t)  = 308390040 + S3(t) - floor(4S4(t)/7).
```

The 214 integer terms increase through the cap. At `t=235`,
`K4=273`, `S4=139629`, `S3=4819136`, and
`floor(4S4/7)=79788`; therefore the admissible owner bound is
`U(235)=313129388`. The original row had cap 265, S4 base 112, and bound
313398248. The new bound is full-profile and self-check-only; formal family
authority and global K20 optimality are not asserted here.
