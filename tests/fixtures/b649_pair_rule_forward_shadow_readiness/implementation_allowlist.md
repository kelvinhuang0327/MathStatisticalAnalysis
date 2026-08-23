# Forward-shadow implementation allowlist

This is the bounded allowlist for `BIG_LOTTO_PAIR_RULE_FORWARD_SHADOW_IMPLEMENTATION_R1`. It is not implementation authorization and it does not authorize migration of blocked components.

## Immutable authority

- Read-only freeze: `/Users/kelvin/VibeCoding-WorkSpace/.task-data/BIG_LOTTO_PAIR_RULE_FORWARD_SHADOW_READINESS_FREEZE_R1/forward_shadow_candidate_freeze.json`
- Required SHA-256: `88cb22d721a0cf0742e121dfe254ed88221cd61921cef59957eda35fbd5e05d8`
- Require exactly five frozen candidates; enable only the three marked `IMPLEMENTATION_READY`.
- Never reselect, fall back to a runner-up, or automatically enable a migrated component.

## Repository paths allowed in the next implementation task

- NEW: `tools/b649_pair_rule_forward_shadow.py`
- MODIFY: `tools/b649_goalc_local_scheduler.py`
- NEW: `tests/unit/test_b649_pair_rule_forward_shadow.py`
- MODIFY: `tests/unit/test_b649_goalc_local_scheduler.py`

All other repository source, test, configuration, deployment, and metadata paths are forbidden unless a new owner-authorized packet expands the allowlist.

## Read-only reuse paths

- `tools/b649_operational_prediction_loop.py`
- `src/lottolab/application/use_cases/generate_bet.py`
- `src/lottolab/application/strategy_preserving_20_ticket.py`
- `src/lottolab/strategies/catalog.py`
- `src/lottolab/strategies/executable_registry.py`

## Runtime write boundary

- Preferred sole subroot: `/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OPERATIONAL_PREDICTION_LOOP_R1/research_shadow/biglotto_pair_rule_forward_v1`
- Allowed descendants after separate explicit runtime authorization: `authority/`, `predictions/`, `scores/`, `comparison.jsonl`, and `health.json`.
- Writes must be atomic create-or-byte-verify and keyed by the contract idempotence preimage.
- A missed pre-draw deadline is terminal for that draw: record `MISSED_DEADLINE_NO_BACKFILL`; do not generate after the deadline.

## Explicitly forbidden

- Any primary Goal-C `predictions/`, `outcomes/`, `scores/`, `performance.jsonl`, `head_to_head.jsonl`, or primary health accounting mutation.
- `tools/b649_operational_prediction_loop.py`, StrategyCatalog, executable-registry, or adapter edits for the three ready candidates.
- Any LaunchAgent/plist, scheduler label/job, announcement, canonical database, or database schema change.
- Any primary 11-stream ID/count or Trigger A cohort change.
- Any write under `/Users/kelvin/VibeCoding-WorkSpace/.task-data/BIG_LOTTO_PAIR_COMPLEMENTARITY_RULE_ROLLING_FALSIFICATION_R1`.
- Any Matrix-lane or migration/open-source-lane write.
- Any implementation of the three rows in `migration_handoff.csv` under this allowlist.

## Required authorization envelope

A later source implementation requires a fresh owner-authorized packet naming the four repository paths above and an isolated worktree. Tests may use temporary directories only. Any live write below the proposed runtime subroot requires separate explicit owner authorization naming that subroot and the target draw. No authorization is implied for Goal-C primary artifacts, the canonical database, announcements, LaunchAgents, protected sibling lanes, commit, push, PR, or promotion.
