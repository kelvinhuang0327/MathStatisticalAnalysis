import type {
  HistoricalRun,
  HistoricalRunPage,
  HistoricalSuccessFeatureCohortDiagnostics,
  HistoricalSuccessFeatureCohorts,
  HistoricalSuccessStabilityMatrix,
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

const criteria = [
  ['M3_PLUS', 3, false],
  ['M4_PLUS', 4, false],
  ['M5_PLUS', 5, false],
  ['M6', 6, false],
  ['M2_PLUS_SPECIAL', 2, true],
  ['M3_PLUS_SPECIAL', 3, true],
  ['M4_PLUS_SPECIAL', 4, true],
  ['M5_PLUS_SPECIAL', 5, true],
] as const
const prefixes = [1, 2, 3, 4, 5, 10, 15, 20] as const
const featureRelations = ['HIGHER', 'EQUAL', 'LOWER', 'UNAVAILABLE'] as const

function gcd(left: number, right: number): number {
  let a = Math.abs(left)
  let b = Math.abs(right)
  while (b !== 0) {
    const remainder = a % b
    a = b
    b = remainder
  }
  return a
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

export function makeMatrix(
  overrides: Partial<HistoricalSuccessStabilityMatrix> = {},
): HistoricalSuccessStabilityMatrix {
  const result = makeResult()
  const criterionViews = criteria.map(
    ([criterion, minimum_main_hits, require_special_hit]) => ({
      criterion,
      minimum_main_hits,
      require_special_hit,
      measurement_mode: 'LEGAL_TICKET_PRIZE' as const,
    }),
  )
  const cells = criterionViews.flatMap((criterion) =>
    prefixes.map((prefix_count) => {
      const windows = makeWindows()
      const comparisons = [
        ['FULL_HISTORY_TO_LONG', 0, 1],
        ['LONG_TO_MEDIUM', 1, 2],
        ['MEDIUM_TO_SHORT', 2, 3],
        ['LONG_TO_SHORT', 1, 3],
      ].map(([comparison_kind, fromIndex, toIndex]) => {
        const from = windows[Number(fromIndex)]!
        const to = windows[Number(toIndex)]!
        const rawNumerator =
          to.success_rate.numerator * from.success_rate.denominator -
          from.success_rate.numerator * to.success_rate.denominator
        const denominator = to.success_rate.denominator * from.success_rate.denominator
        const divisor = gcd(rawNumerator, denominator)
        const numerator = rawNumerator / divisor
        return {
          comparison_kind,
          from_window_kind: from.window_kind,
          to_window_kind: to.window_kind,
          from_rate: { ...from.success_rate },
          to_rate: { ...to.success_rate },
          delta: {
            numerator,
            denominator: numerator === 0 ? 1 : denominator / divisor,
            available: true,
          },
          relation: numerator > 0 ? 'HIGHER' : numerator < 0 ? 'LOWER' : 'EQUAL',
        }
      })
      return {
        criterion,
        prefix_count,
        selection: {
          lottery: 'BIG_LOTTO',
          strategy_id: result.strategy.strategy_id,
          strategy_version: result.strategy.strategy_version,
          replicate: result.strategy.replicate,
          ticket_count: prefix_count,
          max_bet_index: prefix_count,
        },
        status: 'EVALUATED',
        source_observation_count: 5,
        windows,
        comparisons,
      }
    }),
  )
  return {
    metadata: makeWindowPage().metadata,
    strategy: result.strategy,
    source_observation_count: 5,
    prefix_counts: [...prefixes],
    criteria: criterionViews,
    cell_count: 64,
    cells,
    ...overrides,
  } as HistoricalSuccessStabilityMatrix
}

export function makeZeroObservationMatrix(): HistoricalSuccessStabilityMatrix {
  const zero = makeZeroObservationResult()
  const matrix = makeMatrix({
    strategy: zero.strategy,
    source_observation_count: 0,
  })
  return {
    ...matrix,
    cells: matrix.cells.map((cell) => ({
      ...cell,
      selection: {
        ...cell.selection,
        strategy_id: zero.strategy.strategy_id,
        strategy_version: zero.strategy.strategy_version,
        replicate: zero.strategy.replicate,
      },
      status: 'NO_OBSERVATIONS',
      source_observation_count: 0,
      windows: [],
      comparisons: [],
    })),
  }
}

export function makeMatrixForResult(
  result: HistoricalSuccessWindowResult,
): HistoricalSuccessStabilityMatrix {
  const matrix = makeMatrix({
    strategy: result.strategy,
    source_observation_count: result.source_observation_count,
  })
  return {
    ...matrix,
    cells: matrix.cells.map((cell) => ({
      ...cell,
      selection: {
        ...cell.selection,
        strategy_id: result.strategy.strategy_id,
        strategy_version: result.strategy.strategy_version,
        replicate: result.strategy.replicate,
      },
      source_observation_count: result.source_observation_count,
    })),
  }
}

function featureDelta(
  successCount: number,
  observationCount: number,
  baselineSuccessCount: number,
  baselineObservationCount: number,
): {
  numerator: number
  denominator: number
  available: boolean
  relation: 'HIGHER' | 'EQUAL' | 'LOWER' | 'UNAVAILABLE'
} {
  if (observationCount === 0 || baselineObservationCount === 0) {
    return {
      numerator: 0,
      denominator: 0,
      available: false,
      relation: 'UNAVAILABLE',
    }
  }
  const rawNumerator =
    successCount * baselineObservationCount -
    baselineSuccessCount * observationCount
  const rawDenominator = observationCount * baselineObservationCount
  const divisor = gcd(rawNumerator, rawDenominator)
  const numerator = rawNumerator / divisor
  return {
    numerator,
    denominator: numerator === 0 ? 1 : rawDenominator / divisor,
    available: true,
    relation: numerator > 0 ? 'HIGHER' : numerator < 0 ? 'LOWER' : 'EQUAL',
  }
}

export function makeFeatureCohorts(
  overrides: Partial<HistoricalSuccessFeatureCohorts> = {},
): HistoricalSuccessFeatureCohorts {
  const result = makeResult()
  const baseline = {
    observation_count: 5,
    success_count: 2,
    failure_count: 3,
    success_rate: { numerator: 2, denominator: 5, available: true },
  }
  const observed = new Map<number, readonly [number, number]>([
    [0, [1, 1]],
    [1, [1, 0]],
    [63, [3, 1]],
  ])
  const cohorts = featureRelations.flatMap((long_to_medium) =>
    featureRelations.flatMap((medium_to_short) =>
      featureRelations.map((long_to_short) => ({
        feature_key: {
          long_to_medium,
          medium_to_short,
          long_to_short,
        },
      })),
    ),
  ).map((item, index) => {
    const [observation_count, success_count] = observed.get(index) ?? [0, 0]
    const delta = featureDelta(
      success_count,
      observation_count,
      baseline.success_count,
      baseline.observation_count,
    )
    const first_target =
      observation_count === 0
        ? null
        : {
            draw_number: index + 1,
            draw_date: `2025-02-${String(index + 1).padStart(2, '0')}`,
            draw_sha256: String((index % 9) + 1).repeat(64),
          }
    const last_target =
      observation_count === 0
        ? null
        : {
            draw_number: index + observation_count,
            draw_date: `2025-03-${String(index + 1).padStart(2, '0')}`,
            draw_sha256: String(((index + 1) % 9) + 1).repeat(64),
          }
    return {
      ...item,
      observation_count,
      success_count,
      failure_count: observation_count - success_count,
      success_rate:
        observation_count === 0
          ? { numerator: 0, denominator: 0, available: false }
          : {
              numerator: success_count,
              denominator: observation_count,
              available: true,
            },
      delta_vs_baseline: {
        numerator: delta.numerator,
        denominator: delta.denominator,
        available: delta.available,
      },
      relation_vs_baseline: delta.relation,
      first_target,
      last_target,
    }
  })
  return {
    metadata: makeWindowPage().metadata,
    strategy: result.strategy,
    criterion: result.criterion,
    prefix_count: result.prefix_count,
    baseline,
    cohort_count: 64,
    cohorts,
    ...overrides,
  } as HistoricalSuccessFeatureCohorts
}

export function makeFeatureCohortsForResult(
  result: HistoricalSuccessWindowResult,
): HistoricalSuccessFeatureCohorts {
  return makeFeatureCohorts({
    strategy: result.strategy,
  })
}

export function makeZeroObservationFeatureCohorts(): HistoricalSuccessFeatureCohorts {
  const zero = makeZeroObservationResult()
  const cohorts = makeFeatureCohortsForResult(zero)
  return {
    ...cohorts,
    baseline: {
      observation_count: 0,
      success_count: 0,
      failure_count: 0,
      success_rate: { numerator: 0, denominator: 0, available: false },
    },
    cohorts: cohorts.cohorts.map((cohort) => ({
      ...cohort,
      observation_count: 0,
      success_count: 0,
      failure_count: 0,
      success_rate: { numerator: 0, denominator: 0, available: false },
      delta_vs_baseline: { numerator: 0, denominator: 0, available: false },
      relation_vs_baseline: 'UNAVAILABLE',
      first_target: null,
      last_target: null,
    })),
  }
}

export function makeFeatureCohortDiagnostics(
  overrides: Partial<HistoricalSuccessFeatureCohortDiagnostics> = {},
): HistoricalSuccessFeatureCohortDiagnostics {
  const cohorts = makeFeatureCohorts()
  const diagnostics = cohorts.cohorts.map((cohort, cohort_index) => {
    const outside = {
      observation_count:
        cohorts.baseline.observation_count - cohort.observation_count,
      success_count: cohorts.baseline.success_count - cohort.success_count,
      failure_count: cohorts.baseline.failure_count - cohort.failure_count,
    }
    const effect = featureDelta(
      cohort.success_count,
      cohort.observation_count,
      outside.success_count,
      outside.observation_count,
    )
    const status =
      cohort.observation_count === 0
        ? 'NOT_TESTABLE_EMPTY_COHORT'
        : outside.observation_count === 0
          ? 'NOT_TESTABLE_EMPTY_COMPLEMENT'
          : cohorts.baseline.success_count === 0 ||
              cohorts.baseline.success_count === cohorts.baseline.observation_count
            ? 'NOT_TESTABLE_NO_OUTCOME_VARIATION'
            : 'TESTED'
    return {
      cohort_index,
      feature_key: cohort.feature_key,
      test_status: status,
      cohort_counts: {
        observation_count: cohort.observation_count,
        success_count: cohort.success_count,
        failure_count: cohort.failure_count,
      },
      outside_counts: outside,
      cohort_success_rate: cohort.success_rate,
      outside_success_rate:
        outside.observation_count === 0
          ? { numerator: 0, denominator: 0, available: false }
          : {
              numerator: outside.success_count,
              denominator: outside.observation_count,
              available: true,
            },
      risk_difference: {
        numerator: effect.numerator,
        denominator: effect.denominator,
        available: effect.available,
      },
      relation_vs_outside: effect.relation,
      raw_p_value: { numerator: '1', denominator: '1' },
      adjusted_p_value: { numerator: '1', denominator: '1' },
      first_target: cohort.first_target,
      last_target: cohort.last_target,
    }
  })
  return {
    metadata: cohorts.metadata,
    strategy: cohorts.strategy,
    criterion: cohorts.criterion,
    prefix_count: cohorts.prefix_count,
    baseline: cohorts.baseline,
    family_size: 64,
    raw_test_method: 'FISHER_EXACT_TWO_SIDED_PROBABILITY_ORDERING',
    adjustment_method: 'BENJAMINI_YEKUTIELI',
    diagnostics,
    ...overrides,
  } as HistoricalSuccessFeatureCohortDiagnostics
}

export function makeFeatureCohortDiagnosticsForResult(
  result: HistoricalSuccessWindowResult,
): HistoricalSuccessFeatureCohortDiagnostics {
  return makeFeatureCohortDiagnostics({ strategy: result.strategy })
}

export function makeZeroObservationFeatureCohortDiagnostics():
  HistoricalSuccessFeatureCohortDiagnostics {
  const zero = makeZeroObservationResult()
  const cohorts = makeZeroObservationFeatureCohorts()
  return makeFeatureCohortDiagnostics({
    strategy: zero.strategy,
    baseline: cohorts.baseline,
    diagnostics: cohorts.cohorts.map((cohort, cohort_index) => ({
      cohort_index,
      feature_key: cohort.feature_key,
      test_status: 'NOT_TESTABLE_EMPTY_COHORT',
      cohort_counts: {
        observation_count: 0,
        success_count: 0,
        failure_count: 0,
      },
      outside_counts: {
        observation_count: 0,
        success_count: 0,
        failure_count: 0,
      },
      cohort_success_rate: {
        numerator: 0,
        denominator: 0,
        available: false,
      },
      outside_success_rate: {
        numerator: 0,
        denominator: 0,
        available: false,
      },
      risk_difference: {
        numerator: 0,
        denominator: 0,
        available: false,
      },
      relation_vs_outside: 'UNAVAILABLE',
      raw_p_value: { numerator: '1', denominator: '1' },
      adjusted_p_value: { numerator: '1', denominator: '1' },
      first_target: null,
      last_target: null,
    })),
  })
}

function rebuildComparisons(
  cell: HistoricalSuccessStabilityMatrix['cells'][number],
): void {
  const definitions = [
    ['FULL_HISTORY_TO_LONG', 0, 1],
    ['LONG_TO_MEDIUM', 1, 2],
    ['MEDIUM_TO_SHORT', 2, 3],
    ['LONG_TO_SHORT', 1, 3],
  ] as const
  cell.comparisons = definitions.map(([comparison_kind, fromIndex, toIndex]) => {
    const from = cell.windows[fromIndex]!
    const to = cell.windows[toIndex]!
    if (!from.success_rate.available || !to.success_rate.available) {
      return {
        comparison_kind,
        from_window_kind: from.window_kind,
        to_window_kind: to.window_kind,
        from_rate: { ...from.success_rate },
        to_rate: { ...to.success_rate },
        delta: { numerator: 0, denominator: 0, available: false },
        relation: 'UNAVAILABLE',
      }
    }
    const rawNumerator =
      to.success_rate.numerator * from.success_rate.denominator -
      from.success_rate.numerator * to.success_rate.denominator
    const rawDenominator =
      to.success_rate.denominator * from.success_rate.denominator
    const divisor = gcd(rawNumerator, rawDenominator)
    const numerator = rawNumerator / divisor
    return {
      comparison_kind,
      from_window_kind: from.window_kind,
      to_window_kind: to.window_kind,
      from_rate: { ...from.success_rate },
      to_rate: { ...to.success_rate },
      delta: {
        numerator,
        denominator: numerator === 0 ? 1 : rawDenominator / divisor,
        available: true,
      },
      relation: numerator > 0 ? 'HIGHER' : numerator < 0 ? 'LOWER' : 'EQUAL',
    }
  })
}

export function makeAllRelationsMatrix(): HistoricalSuccessStabilityMatrix {
  const matrix = makeMatrix()
  for (const [cellIndex, numerators] of [
    [0, [1, 2, 3, 4]],
    [1, [4, 3, 2, 1]],
    [2, [2, 2, 2, 2]],
  ] as const) {
    const cell = matrix.cells[cellIndex]!
    cell.windows = cell.windows.map((window, index) => ({
      ...window,
      success_count: numerators[index]!,
      failure_count: 4 - numerators[index]!,
      success_rate: {
        numerator: numerators[index]!,
        denominator: 4,
        available: true,
      },
    }))
    rebuildComparisons(cell)
  }
  const unavailable = matrix.cells[3]!
  unavailable.windows = unavailable.windows.map((window) => ({
    ...window,
    eligible_draw_count: 0,
    excluded_draw_count: 5,
    success_count: 0,
    failure_count: 0,
    success_rate: { numerator: 0, denominator: 0, available: false },
    evaluation_status: 'NO_ELIGIBLE_DRAWS',
    evidence_status: 'NOT_READY',
  }))
  rebuildComparisons(unavailable)
  return matrix
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
