import type {
  HistoricalRun,
  HistoricalRunPage,
  HistoricalSuccessWindowPage,
  HistoricalSuccessWindowResult,
} from '../src/api/historicalSuccessWindows'
import { vi } from 'vitest'

export const IMPORT_SHA = 'a'.repeat(64)

export function makeRun(overrides: Partial<HistoricalRun> = {}): HistoricalRun {
  return {
    run_id: 'run-explicit-1',
    import_identity_sha256: IMPORT_SHA,
    manifest_sha256: 'b'.repeat(64),
    contract_version: '1.0.0',
    source_kind: 'HISTORICAL_RESULTS',
    source_repository: 'kelvinhuang0327/MathStatisticalAnalysis',
    source_commit_oid: 'c'.repeat(40),
    source_artifact_sha256: 'd'.repeat(64),
    dataset_identity: 'historical-big-lotto-r1',
    dataset_sha256: 'e'.repeat(64),
    legacy_run_id: null,
    lottery_type: 'BIG_LOTTO',
    started_at: '2026-07-20T00:00:00Z',
    completed_at: '2026-07-20T01:00:00Z',
    ...overrides,
  }
}

export function makeRunPage(overrides: Partial<HistoricalRunPage> = {}): HistoricalRunPage {
  return {
    items: [makeRun()],
    total_count: 1,
    limit: 10,
    offset: 0,
    ...overrides,
  }
}

const windowAxes = [
  ['FULL_HISTORY', 'REFERENCE_ONLY', null],
  ['LONG', 'PRIMARY_EVIDENCE', 750],
  ['MEDIUM', 'STABILITY_CONFIRMATION', 300],
  ['SHORT', 'DEGRADATION_VETO', 50],
] as const

function makeWindows(): HistoricalSuccessWindowResult['windows'] {
  return windowAxes.map(([window_kind, window_role, requested_draw_count], index) => ({
    window_kind,
    window_role,
    requested_draw_count,
    source_draw_count: 5,
    eligible_draw_count: 4,
    excluded_draw_count: 1,
    success_count: index + 1 > 4 ? 4 : index + 1,
    failure_count: 4 - (index + 1 > 4 ? 4 : index + 1),
    success_rate: {
      numerator: index + 1 > 4 ? 4 : index + 1,
      denominator: 4,
      available: true,
    },
    first_target: {
      draw_number: 1,
      draw_date: '2025-01-01',
      draw_sha256: '1'.repeat(64),
    },
    last_target: {
      draw_number: 5,
      draw_date: '2025-01-05',
      draw_sha256: '2'.repeat(64),
    },
    first_cutoff: {
      draw_number: 0,
      draw_date: '2024-12-31',
      draw_sha256: '3'.repeat(64),
    },
    last_cutoff: {
      draw_number: 4,
      draw_date: '2025-01-04',
      draw_sha256: '4'.repeat(64),
    },
    nested_windows_independent: false,
    evaluation_status: 'INSUFFICIENT_DRAWS',
    evidence_status: 'DESCRIPTIVE_ONLY',
  }))
}

export function makeResult(
  overrides: Partial<HistoricalSuccessWindowResult> = {},
): HistoricalSuccessWindowResult {
  return {
    strategy: {
      strategy_id: 'alias strategy/one',
      effective_strategy_id: 'effective-strategy',
      strategy_version: 'v1 beta',
      replicate: 1,
      identity_kind: 'ALIAS',
      governance_status: 'CANDIDATE',
      alias_of_strategy_id: 'effective-strategy',
      equivalence_group: 'group-a',
      nested_prefix_supported: true,
      descriptor_sha256: '5'.repeat(64),
    },
    criterion: {
      criterion: 'M3_PLUS',
      minimum_main_hits: 3,
      require_special_hit: false,
      measurement_mode: 'LEGAL_TICKET_PRIZE',
    },
    prefix_count: 1,
    selection: {
      lottery: 'BIG_LOTTO',
      strategy_id: 'alias strategy/one',
      strategy_version: 'v1 beta',
      replicate: 1,
      ticket_count: 1,
      max_bet_index: 1,
    },
    status: 'EVALUATED',
    source_observation_count: 5,
    windows: makeWindows(),
    ...overrides,
  }
}

export function makeZeroObservationResult(): HistoricalSuccessWindowResult {
  const base = makeResult()
  return {
    ...base,
    strategy: {
      ...base.strategy,
      strategy_id: 'zero-observation',
      effective_strategy_id: 'zero-observation',
      strategy_version: 'v2',
      replicate: 2,
      identity_kind: 'PRIMARY',
      alias_of_strategy_id: null,
      equivalence_group: null,
      descriptor_sha256: '6'.repeat(64),
    },
    selection: {
      ...base.selection,
      strategy_id: 'zero-observation',
      strategy_version: 'v2',
      replicate: 2,
    },
    status: 'NO_OBSERVATIONS',
    source_observation_count: 0,
    windows: [],
  }
}

export function makeWindowPage(
  overrides: Partial<HistoricalSuccessWindowPage> = {},
): HistoricalSuccessWindowPage {
  const items = [makeResult(), makeZeroObservationResult()]
  return {
    metadata: {
      run_id: 'run-explicit-1',
      contract_version: '1.0.0',
      import_identity_sha256: IMPORT_SHA,
      source_kind: 'HISTORICAL_RESULTS',
      source_repository: 'kelvinhuang0327/MathStatisticalAnalysis',
      source_commit_oid: 'c'.repeat(40),
      source_artifact_sha256: 'd'.repeat(64),
      dataset_identity: 'historical-big-lotto-r1',
      dataset_sha256: 'e'.repeat(64),
      lottery_type: 'BIG_LOTTO',
    },
    criterion: {
      criterion: 'M3_PLUS',
      minimum_main_hits: 3,
      require_special_hit: false,
      measurement_mode: 'LEGAL_TICKET_PRIZE',
    },
    prefix_count: 1,
    total_count: items.length,
    limit: 20,
    offset: 0,
    items,
    ...overrides,
  }
}

export function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

export function deferred<T>(): {
  promise: Promise<T>
  resolve: (value: T | PromiseLike<T>) => void
} {
  let resolve!: (value: T | PromiseLike<T>) => void
  const promise = new Promise<T>((resolver) => {
    resolve = resolver
  })
  return { promise, resolve }
}
