# BIG_LOTTO rule-contract provenance

The sole machine-readable runtime contract is
`src/lottolab/domain/lottery_rules.py::BIG_LOTTO_RULE_CONTRACT`. This document is an
evidence ledger and does not define a second set of executable rule values.
Its `contract_version` value is a LottoLab-internal descriptor version, not an official
rule-document version.

## Current game sources

### Canonical rendered page

- Publisher: 台灣彩券股份有限公司
- Title: 台灣彩券-遊戲介紹（大樂透）
- Canonical URL: <https://www.taiwanlottery.com/lotto/info/lotto649/>
- Accessed: `2026-07-16T05:19:34Z`
- Observed site footer/build version: `ver.1_0_8_0`; this is not presented as an official
  rule-document version, and no rule-effective date is stated
- Page-response SHA-256: `1aa7926f2397619a457cb10c2854728d47e1b0d0f957d12f01758ff439ec9971`
- Locator: rendered heading `什麼是大樂透?`
- Language: Traditional Chinese (`zh-TW`)
- Evidence: this is the official canonical route that renders the game-rule asset recorded below.
- Status: `CORROBORATING`

### Content-bearing first-party asset

- Publisher: 台灣彩券股份有限公司
- Title: `/_nuxt/_game_.1_0_8_04.js`
- Canonical content URL: <https://www.taiwanlottery.com/_nuxt/_game_.1_0_8_04.js>
- Accessed: `2026-07-16T05:19:34Z`
- Version identifier: exact versioned asset filename; no rule-effective date is stated
- SHA-256: `397639210969faba3002ffbd309dba10c44ead2063dd51ed47def98624994c15`
- Locator: `BaseRule → lotto649.text`, beginning near UTF-8 byte 6690
- Language: Traditional Chinese (`zh-TW`) within JavaScript
- Evidence: the asset describes choosing six numbers from 01–49 and the draw producing six main
  numbers plus one special number.
- Status: `PRIMARY`

The runtime provenance tuple binds only the content-bearing asset: its asset title, asset URL,
asset digest, and byte locator all identify that same first-party response. The canonical rendered
page and its separate `CORROBORATING` response digest remain recorded above for navigation.

## Current prize-tier contract

- Publisher: 台灣彩券股份有限公司
- Title: `/_nuxt/_game_.1_0_8_04.js`
- Canonical content URL: <https://www.taiwanlottery.com/_nuxt/_game_.1_0_8_04.js>
- Accessed: `2026-07-21T07:25:51Z`
- Response SHA-256: `397639210969faba3002ffbd309dba10c44ead2063dd51ed47def98624994c15`
- Response metadata: `application/javascript`; 120,610 bytes; server-reported last modified
  `2026-03-24T07:06:12Z`
- Locator: `lotto649.tableData`, UTF-8 bytes 7446–8159
- Language/encoding: Traditional Chinese in UTF-8 JavaScript
- Status: `PRIMARY`, current

Current-route corroboration:

- Publisher: 台灣彩券股份有限公司
- Title: `/_nuxt/entry.1_0_8_0.js`
- Canonical content URL: <https://www.taiwanlottery.com/_nuxt/entry.1_0_8_0.js>
- Accessed: `2026-07-21T07:33:54Z`
- Response SHA-256: `8f386a4d4e3f2e0028172b22eafa6f52385d06e5bd7936eca289d12f3ee674bb`
- Locator: `/lotto/info/:game` route component import at UTF-8 byte 195374
- Language/encoding: JavaScript in UTF-8
- Status: `CORROBORATING`, current route manifest

Current applicability was established by reloading the canonical rendered game page on the access
date. The route manifest above loads the exact `_game_.1_0_8_04.js` asset for
`/lotto/info/:game`, and the asset returned HTTP 200 from the operator's official host. Neither the
page nor the asset states a rule-effective or expiry date. No current official source with
conflicting tier labels or hit conditions was found. The website build identifiers and asset
filename are deployment identifiers, not official rule versions.

The official rows normalize to the runtime hit-signature contract as follows. `main_hits` counts
matches against the six main winning numbers; `special_hit` records whether the ticket also matches
the distinct special number. Prize amounts shown elsewhere in the source are deliberately excluded.

| Stable LottoLab tier ID | Official label | `main_hits` | `special_hit` |
|---|---:|---:|---:|
| `FIRST` | 頭獎 | 6 | false |
| `SECOND` | 貳獎 | 5 | true |
| `THIRD` | 參獎 | 5 | false |
| `FOURTH` | 肆獎 | 4 | true |
| `FIFTH` | 伍獎 | 4 | false |
| `SIXTH` | 陸獎 | 3 | true |
| `SEVENTH` | 柒獎 | 2 | true |
| `GENERAL` | 普獎 | 3 | false |

All other logically possible hit signatures are valid non-winning results. `(6, true)` is invalid:
a six-number ticket that matches all six distinct main numbers cannot also contain the separate
special number. The runtime resolver therefore distinguishes explicit `NO_PRIZE` from invalid
input.

The executable values live only in
`src/lottolab/domain/lottery_rules.py::BIG_LOTTO_RULE_CONTRACT`; this ledger records their evidence
and derivation but is not a second runtime table. The prize section uses LottoLab-internal schema
version `1.0.0`. The encompassing game-mechanics descriptor remains `2026-07-16.1` because the
prize section has its own version identity and changing the existing descriptor would invalidate
unrelated evidence hashes. Neither value is presented as an official rule version.

## Current procedural corroboration

- Publisher: 台灣彩券股份有限公司
- Title: 台灣彩券-開獎流程
- Canonical URL: <https://www.taiwanlottery.com/run_lottery/info/>
- Accessed: `2026-07-16T05:19:34Z`
- Observed site footer/build version: `ver.1_0_8_0`; no rule-effective date is stated
- SHA-256: `9ba7429f946e1490ecfde6f5324eac3a570a02cbdcdcceb3371459a04fa705f7`
- Locators:
  - `開獎異常狀況應變措施 → 1.1`, bytes 209306 and 209977
  - `開獎異常狀況應變措施 → 1.4`, bytes 226491 and 228316
- Language: Traditional Chinese (`zh-TW`)
- Evidence: BIG_LOTTO is a sequential-ball draw; the last valid ball is the special number; a
  previously valid ball is excluded rather than reinserted when a draw must continue.
- Status: `CORROBORATING`

The sources do not use the standalone phrase “drawn from the remaining 43.” The required fields
are nevertheless established by the following explicit deductive chain from the official
sources:

- Main-number uniqueness: the draw uses one numbered 01–49 ball set, proceeds sequentially, and
  already-valid balls remain out rather than being reinserted.
- Special-number range: the special is the last valid ball in that same 01–49 sequence, so its
  inclusive bounds are the ball-set bounds.
- Special-number uniqueness: the game defines exactly one special number; it is also one ball in
  the no-reinsertion sequence.
- Main/special non-overlap: the special is the final valid ball, after the six main balls have
  remained out of the machine, so it cannot repeat a main-ball value.

These are drawn-ball and drawn-number-set conclusions, not statements about LottoLab's textual
`draw_number` issue identifier.

## Historical formal corroboration and supersession

- Publisher: 中國信託商業銀行股份有限公司 彩券管理部
- Title: 公告公益彩券電腦型彩券「威力彩」、「大樂透」、「今彩539」、
  「38樂合彩」、「49樂合彩」、「39樂合彩」、「3星彩」、「4星彩」及
  「bingo bingo賓果賓果」發行等相關事宜
- Canonical URL: <https://lotto.ctbcbank.com/news1021227-2.htm>
- Published: `2013-12-27`; effective: `2014-01-01`
- Accessed: `2026-07-16T05:19:34Z`
- Raw Big5 response SHA-256:
  `4497164dd7b9ae11c8a861cd90084d7fe7b8fb0b0938c2c6ecba0424f389b14f`
- Locator: `公告事項 → 貳、電腦型彩券「大樂透」 → 二、三、六、七(一)1`
- Language: Traditional Chinese (`Big5`)
- Evidence: it explicitly describes six non-repeating selections from 01–49, six main numbers
  plus a special number, and order-insensitive matching.
- Status: `SUPERSEDED`

Supersession record:

- Publisher: 中國信託商業銀行股份有限公司 彩券管理部
- Title: 公告第四屆公益彩券電腦型彩券「威力彩」及「大樂透」最後一期未開出
  獎項之獎金分配規則
- Canonical URL: <https://lotto.ctbcbank.com/news1121016.htm>
- Published: `2023-10-16`; accessed: `2026-07-16T05:19:34Z`
- Raw Big5 response SHA-256:
  `bc1bb8b441481629abdfe3a1c77cd5edb4abeec360cabfc1089042b831f0c1b6`
- Locator: `公告事項 → 一(二)`; it records the fourth-session BIG_LOTTO stop at
  `2023-12-29 20:00`.
- Language: Traditional Chinese (`Big5`)
- Status: `CORROBORATING` (this evidence establishes that the older formal rule record is
  superseded)

The current sources do not state when the current mechanics took effect or will end, so the
runtime contract deliberately leaves both effective-date fields unset. No official-source
conflict was found.

## LottoLab record-format policies

These are deterministic LottoLab normalization decisions, not claims about official game
mathematics:

- Main and special number collections use ascending numeric order. The formal source says
  matching is order-insensitive; it does not mandate ascending storage.
- A draw number is trimmed, must be a non-empty string of ASCII digits, preserves leading
  zeroes, is never converted to an integer, and has a maximum normalized length of 32 characters.
