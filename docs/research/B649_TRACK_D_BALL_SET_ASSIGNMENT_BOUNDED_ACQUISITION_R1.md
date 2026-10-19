# B649 Track D — Ball-Set Assignment Bounded Acquisition R1

**TASK_ID:** `B649_TRACK_D_BALL_SET_ASSIGNMENT_BOUNDED_ACQUISITION_R1`
**MODE:** `CONTINUATION_HANDOFF` (resumed from quota exhaustion; predecessor recon not repeated)
**DATE:** 2026-08-15 Asia/Taipei
**STATUS:** `COMPLETE`

## Primary decision

`BALL_SET_DATA_USABLE_FOR_RETROSPECTIVE_DISCOVERY_ONLY`

Betting-cutoff timing is now resolved on an **authoritative, official, primary-source basis** (not inferred from a single video, as in the predecessor recon). The official Taiwan Lottery FAQ states, verbatim, why the draw is fixed at 20:30:

> **Q6. 能不能準時在八時投注截止時就開獎？**
> 目前正式開獎時間為晚間8點30分，此一時間的訂定是因**投注截止後**，需預留30分鐘給主電腦中心進行當期銷售統計，待統計完成後，有正確的銷售統計資訊公布給消費大眾後，**始能進行開獎程序**。
> — [taiwanlottery.com/customer_service/faq](https://www.taiwanlottery.com/customer_service/faq/)

This is decisive: the entire **開獎程序** (draw procedure) — which the predecessor report established includes machine/ball-set/loading-order selection — is officially defined as unable to start until *after* a 30-minute post-cutoff sales-statistics window. Ticket sales cutoff (投注截止) is therefore a distinct, named, prior event, corroborated explicitly as 20:00 by independent secondary sources (news/lottery-guide aggregators). The ball-set assignment ceremony cannot occur before cutoff by the official process's own design — it is structurally downstream of it. No exception channel (pre-announcement page, API field, earlier session record) was found; this reinforces rather than overturns the predecessor's existing finding that the live official API and repo/DB expose no machine/ball-set field at any point, pre- or post-cutoff.

A small bounded sample (below) was then used to check retrospective usability: join quality, archive coverage, and label readability/consistency across eras. Archive **coverage boundary was established by complete enumeration**, not sampling — the official archive channel's own "oldest" sort was read directly, which is stronger evidence than any number of individual spot-checks.

## Evidence summary

- `[Confirmed]` Official FAQ Q1/Q2: draws occur Mon–Sat 20:30–21:00 at SETN Studio 5; broadcast simulcasts on SETN iNews and USTV News, "全民i彩券" program.
- `[Confirmed]` Official FAQ Q6 (quoted above): draw time is fixed at 20:30 specifically because it is 30 minutes after ticket-sales cutoff, and the draw procedure cannot begin until that post-cutoff sales-statistics computation completes.
- `[Confirmed]` Independent secondary sources (news/lottery-guide sites) explicitly state 20:00 as the B649 sales/betting cutoff, consistent with the FAQ's arithmetic.
- `[Confirmed]` Official FAQ Q8 independently establishes that the broadcast interleaves regular news/ads between game draws — meaning the ball-set reveal for any one game is **not at a fixed relative timestamp** across episodes and must be located per-video.
- `[Confirmed]` The official "開獎實況轉播" nav link on taiwanlottery.com points to YouTube channel **全民i彩券 (@48ilottery48)**, 95.4k subscribers, 1,056 videos, with a dedicated "彩券開獎直播｜各期彩券開獎直播現場" playlist (836 videos).
- `[Confirmed]` That channel's "streams" tab, sorted oldest-first, starts at exactly **【20240101】彩券開獎** ([watch?v=GCMXXh9tmFY](https://www.youtube.com/watch?v=GCMXXh9tmFY)). Nothing earlier exists on this channel. This closes the predecessor report's open "pre-2024 availability: UNKNOWN" item — the answer is **UNAVAILABLE before 2024-01-01**, for the full 2007–2023 span of local B649 history.
- `[Confirmed]` Coverage from 2024-01-01 to present (2026-08-15, live) is one video per broadcast day, Mon–Sat, with Sundays absent — consistent with the official schedule in both the earliest window (Jan 2024) and the most recent window (Jul–Aug 2026) inspected.
- `[Confirmed]` Naming is usually `【YYYYMMDD】彩券開獎` but **not always**: 2024-07-05 is titled `【20240705】台彩端午加碼特別節目` (holiday bonus special), which would break a naive fixed-pattern parser.
- `[Confirmed]` Video length varies materially by era (~30 min in Jan 2024 vs. ~60–70 min in mid-2025 through 2026), so the B649 segment's position is not a stable fraction of runtime either.
- `[Confirmed]` Local read-only snapshot (`.local/snapshots/p600ab-r1-20260715T122730+0800/lottery_v2.db`, view `draws_big_lotto_canonical_main` — the same corpus already sealed per the legacy-reference-corpus memory) gives authoritative date↔period pairs for B649, 2,124 rows, 2007-01-02 to 2026-07-10. Two spot-checked on-screen period numbers (115000022 for 2026-02-21; 113000002 for 2024-01-05) matched this table exactly, with zero discrepancy.
- `[Confirmed]` Reused without re-verification: predecessor's single clean instance, 2026-02-21 / period 115000022 / [watch?v=60oYVtUDx38](https://www.youtube.com/watch?v=60oYVtUDx38) — machine 1 (t=404s), reverse loading direction (t=429s), ball set 2 (t=439s), each a distinct, clearly labeled full-screen or large-graphic reveal.
- `[Confirmed, new, ambiguous]` 2024-01-05 / period 113000002 / [watch?v=aQUKJ_Zkm_M](https://www.youtube.com/watch?v=aQUKJ_Zkm_M): on-screen period matched local DB exactly at t≈830s. A numeric badge "2" is visible on a small picture-in-picture inset during the active ball-drop phase (t≈962s, clock 20:44:51), but unlike the 2026-02-21 instance, machine ID, ball-set ID, and loading direction are **not separately labeled** here — the single badge cannot be confidently disambiguated as one or the other.
- `[Attempted, not located within budget]` 2025-06-06 / period 114000059 / [watch?v=bqjOD4gz32A](https://www.youtube.com/watch?v=bqjOD4gz32A) (1:09:20 long): the B649 segment window was located (~t=3300–3450s, clock ≈20:45–20:47) via bumper graphics, but the specific ball-set-reveal frame was not pinned down within a 5-seek bounded search budget — the segment appears to hold a generic branded bumper graphic for an extended real-time span rather than a quick, easily-targeted cutaway.
- `[Confirmed, existence/naming only]` 2024-07-05 ([watch?v=1NpHgsbTLUY](https://www.youtube.com/watch?v=1NpHgsbTLUY)), 2026-01-13 ([watch?v=JvzLRQ7zE6A](https://www.youtube.com/watch?v=JvzLRQ7zE6A)), 2026-07-10 ([watch?v=DlLWYtt7orE](https://www.youtube.com/watch?v=DlLWYtt7orE)): each exists, each lists 大樂透 among that day's draw items; none deep-inspected for the ball-set frame (out of bounded budget).

## Sample table

Full detail in the companion CSV. Summary:

| draw_number | draw_date | ball_set_id | machine_id | join_quality | readability | confidence |
|---|---|---|---|---|---|---|
| 115000022 | 2026-02-21 | 2 | 1 | exact | clean, 3 separately labeled fields (reused, not re-verified) | MEDIUM |
| 113000002 | 2024-01-05 | 2 (ambiguous) | 2 (ambiguous — same badge) | exact | single unlabeled badge, fields not disambiguated | LOW–MEDIUM |
| n/a (archive-boundary anchor) | 2024-01-01 | not inspected | not inspected | n/a | used only to confirm earliest archived video | n/a |
| not extracted | 2024-07-05 | not inspected | not inspected | n/a (title exception) | existence/naming check only | n/a |
| 114000059 | 2025-06-06 | not located | not located | exact | segment window found, exact frame not pinned down in budget | n/a |
| 115000004 | 2026-01-13 | not inspected | not inspected | n/a | existence/naming check only | n/a |
| 115000069 | 2026-07-10 | not inspected | not inspected | n/a | existence/naming check only | n/a |

CONFIRMED_BALL_SET_ROWS: **2** (1 reused clean, 1 new but ambiguous)
AMBIGUOUS_ROWS: **2** (2024-01-05 field-disambiguation; 2025-06-06 frame-not-located)
Pre-2024 rows: **0 possible** — archive does not extend before 2024-01-01 (complete-enumeration finding, not a gap in sampling).

## Why this stays bounded, and what it actually shows

Among the 3 dates where a full ball-set-frame read was attempted (2026-02-21 reused, 2024-01-05, 2025-06-06 new), only **1 of 3** produced a clean, unambiguous, fully-labeled read. That is a materially different picture from treating the predecessor's single confirmed 2026 instance as representative. Two concrete, non-obvious costs emerged this round:

1. **Format is not stable across eras.** At least one 2024 episode presents ball-set/machine information as a small, unlabeled numeric badge on a picture-in-picture inset rather than the dedicated, separately-labeled full-screen reveal seen in the 2026 instance. A double-coding protocol would need to handle both formats (and possibly others not yet sampled) rather than one fixed template.
2. **The segment's location inside a video is not predictable by a fixed timestamp or a fixed fraction of runtime**, because (a) the broadcast genuinely interleaves unrelated news/ads (confirmed by the official FAQ's own Q8), and (b) video length itself varies 2x–3x across eras. Locating it currently requires per-video manual/visual scrubbing; this is the real acquisition cost driver, not the labeling itself.

Both points argue for treating any further work on this line as needing a scoped feasibility check on segment-localization (e.g., whether YouTube auto-chapters, silence/scene-cut heuristics, or the on-screen "今日開獎項目" bumper graphic can be used as a reliable per-video anchor) before committing to a larger double-coding acquisition — not for abandoning the line, since retrospective usability itself is still intact.

## Final

TASK_ID:
`B649_TRACK_D_BALL_SET_ASSIGNMENT_BOUNDED_ACQUISITION_R1`

STATUS:
`COMPLETE`

OFFICIAL_TIMING_SOURCES_CHECKED:
taiwanlottery.com/customer_service/faq (Q1, Q2, Q5, Q6, Q8, Q9); taiwanlottery.com/run_lottery/info; taiwanlottery.com/run_lottery/schedule; corroborating secondary sources (news/lottery-guide aggregators) for the explicit "20:00" cutoff figure.

BETTING_CUTOFF:
20:00 (投注截止) — derived with certainty from the FAQ's own stated arithmetic (30-minute post-cutoff gap fixes the 20:30 draw time) and independently corroborated by secondary sources stating 20:00 explicitly.

DRAW_BROADCAST_TIME:
20:30–21:00, Monday–Saturday, SETN Studio 5; simulcast on SETN iNews / USTV News "全民i彩券" program; official archive on YouTube channel @48ilottery48.

EARLIER_OFFICIAL_BALL_SET_PUBLICATION_FOUND:
NO

PUBLICATION_TIMING:
`PRE_DRAW_BUT_AFTER_BETTING_CUTOFF`

DRAWS_SAMPLED:
7 distinct dates touched (1 reused from predecessor + 6 new: 2024-01-01 archive-boundary anchor, 2024-01-05, 2024-07-05, 2025-06-06, 2026-01-13, 2026-07-10), plus one complete (non-sampled) enumeration check that closes the entire pre-2024 question at once.

CONFIRMED_BALL_SET_ROWS:
2 (1 reused clean triple-field; 1 new but ambiguous single-field)

AMBIGUOUS_ROWS:
2

JOIN_QUALITY:
HIGH — `YYYYMMDD` video title maps 1:1 to official draw date; local canonical table (`draws_big_lotto_canonical_main`, 2,124 rows, 2007–2026-07-10) supplies authoritative period numbers; both spot-checked on-screen periods matched exactly.

ARCHIVE_AVAILABILITY:
Starts exactly 2024-01-01 (confirmed by complete oldest-first enumeration of the official channel, not sampling); continuous Mon–Sat coverage through present; nothing before 2024-01-01 exists on this channel, so the 2007–2023 span of local B649 history has no available ball-set source via this channel. Naming and video length are not fully uniform (holiday-special titles; 30-min vs. 60–70-min runtimes across eras).

PRIMARY_DECISION:
`BALL_SET_DATA_USABLE_FOR_RETROSPECTIVE_DISCOVERY_ONLY`

PREDICTIVE_LIVE_USABILITY:
NO

RETROSPECTIVE_RESEARCH_USABILITY:
YES, with a material caveat — clean-read rate in this bounded sample was 1/3 among fully-attempted dates, and per-video segment localization (not labeling itself) is the dominant acquisition-cost driver. Not yet "ready to scale" without a further scoped localization-feasibility check.

NEXT_TASK_ID:
`OWNER_DECISION_PENDING` — whether to fund a small segment-localization feasibility check (e.g., chapter markers / scene-cut heuristics / bumper-graphic anchoring) before any larger double-coding acquisition, or to deprioritize this metadata line given Track D's broader pattern of null/low-yield results and return to the main research frontier queue.

REPO_MUTATION:
NONE

DB_MUTATION:
NONE

END
