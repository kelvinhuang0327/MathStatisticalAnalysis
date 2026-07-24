import type {
  HistoricalRun,
  HistoricalRunPage,
  HistoricalSuccessFeatureCohortDiagnostics,
  HistoricalSuccessFeatureCohorts,
  HistoricalSuccessCrossImportConcordance,
  HistoricalSuccessMultiImportConcordanceCensus,
  HistoricalSuccessRecent50StabilityAudit,
  HistoricalSuccessResearchQualification,
  HistoricalSuccessStabilityMatrix,
  HistoricalSuccessTemporalHoldout,
  HistoricalSuccessWindowPage,
  HistoricalSuccessWindowResult,
} from '../src/api/historicalSuccessWindows'
import { vi } from 'vitest'

export const IMPORT_SHA = 'a'.repeat(64)
export const RIGHT_IMPORT_SHA = 'b'.repeat(64)
export const THIRD_IMPORT_SHA = 'c'.repeat(64)
export const FOURTH_IMPORT_SHA = 'd'.repeat(64)

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

function makeTemporalPhase(
  observationCount: 750 | 300 | 250 | 50,
  successCount: 300 | 120 | 99 | 18,
): HistoricalSuccessFeatureCohortDiagnostics {
  const base = makeFeatureCohortDiagnostics()
  const firstCount = observationCount / 2
  const firstSuccesses = successCount * (2 / 3)
  const observed = new Map<number, readonly [number, number]>([
    [0, [firstCount, firstSuccesses]],
    [1, [observationCount - firstCount, successCount - firstSuccesses]],
  ])
  const baseline = {
    observation_count: observationCount,
    success_count: successCount,
    failure_count: observationCount - successCount,
    success_rate: {
      numerator: successCount,
      denominator: observationCount,
      available: true,
    },
  }
  return {
    ...base,
    baseline,
    diagnostics: base.diagnostics.map((diagnostic, cohort_index) => {
      const [cohortCount, cohortSuccesses] = observed.get(cohort_index) ?? [0, 0]
      const outsideCount = observationCount - cohortCount
      const outsideSuccesses = successCount - cohortSuccesses
      const effect = featureDelta(
        cohortSuccesses,
        cohortCount,
        outsideSuccesses,
        outsideCount,
      )
      return {
        ...diagnostic,
        cohort_counts: {
          observation_count: cohortCount,
          success_count: cohortSuccesses,
          failure_count: cohortCount - cohortSuccesses,
        },
        outside_counts: {
          observation_count: outsideCount,
          success_count: outsideSuccesses,
          failure_count: outsideCount - outsideSuccesses,
        },
        cohort_success_rate:
          cohortCount === 0
            ? { numerator: 0, denominator: 0, available: false }
            : {
                numerator: cohortSuccesses,
                denominator: cohortCount,
                available: true,
              },
        outside_success_rate: {
          numerator: outsideSuccesses,
          denominator: outsideCount,
          available: true,
        },
        risk_difference: {
          numerator: effect.numerator,
          denominator: effect.denominator,
          available: effect.available,
        },
        relation_vs_outside: effect.relation,
        test_status:
          cohortCount === 0 ? 'NOT_TESTABLE_EMPTY_COHORT' : 'TESTED',
        first_target:
          cohortCount === 0
            ? null
            : {
                draw_number: cohort_index + 1,
                draw_date: `2025-04-0${cohort_index + 1}`,
                draw_sha256: String(cohort_index + 1).repeat(64),
              },
        last_target:
          cohortCount === 0
            ? null
            : {
                draw_number: cohort_index + cohortCount,
                draw_date: `2025-05-0${cohort_index + 1}`,
                draw_sha256: String(cohort_index + 2).repeat(64),
              },
      }
    }),
  }
}

export function makeTemporalHoldout(
  overrides: Partial<HistoricalSuccessTemporalHoldout> = {},
): HistoricalSuccessTemporalHoldout {
  const discovery = makeTemporalPhase(750, 300)
  const confirmation = makeTemporalPhase(300, 120)
  const comparisons = discovery.diagnostics.map((discovery_diagnostic, index) => {
    const confirmation_diagnostic = confirmation.diagnostics[index]!
    const discoveryEffect = discovery_diagnostic.risk_difference
    const confirmationEffect = confirmation_diagnostic.risk_difference
    const bothAvailable = discoveryEffect.available && confirmationEffect.available
    let effect_change = { numerator: 0, denominator: 0, available: false }
    if (bothAvailable) {
      const rawNumerator =
        confirmationEffect.numerator * discoveryEffect.denominator -
        discoveryEffect.numerator * confirmationEffect.denominator
      const rawDenominator =
        confirmationEffect.denominator * discoveryEffect.denominator
      const divisor = gcd(rawNumerator, rawDenominator)
      effect_change = {
        numerator: rawNumerator / divisor,
        denominator: rawDenominator / divisor,
        available: true,
      }
    }
    const discoveryRelation = discovery_diagnostic.relation_vs_outside
    const confirmationRelation = confirmation_diagnostic.relation_vs_outside
    const relationship =
      discoveryRelation === 'UNAVAILABLE' || confirmationRelation === 'UNAVAILABLE'
        ? 'UNAVAILABLE'
        : discoveryRelation !== confirmationRelation
          ? 'DIFFERENT'
          : discoveryRelation === 'HIGHER'
            ? 'SAME_HIGHER'
            : discoveryRelation === 'EQUAL'
              ? 'SAME_EQUAL'
              : 'SAME_LOWER'
    return {
      cohort_index: index,
      feature_key: discovery_diagnostic.feature_key,
      discovery_diagnostic,
      confirmation_diagnostic,
      effect_change,
      relationship,
    }
  })
  return {
    metadata: discovery.metadata,
    strategy: discovery.strategy,
    criterion: discovery.criterion,
    prefix_count: discovery.prefix_count,
    split: {
      split_method: 'FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION',
      total_assignment_count: 1100,
      warmup_count: 50,
      discovery_count: 750,
      confirmation_count: 300,
      discovery_first_target: {
        draw_number: 51,
        draw_date: '2025-02-20',
        draw_sha256: '1'.repeat(64),
      },
      discovery_last_target: {
        draw_number: 800,
        draw_date: '2027-03-10',
        draw_sha256: '2'.repeat(64),
      },
      confirmation_first_target: {
        draw_number: 801,
        draw_date: '2027-03-11',
        draw_sha256: '3'.repeat(64),
      },
      confirmation_last_target: {
        draw_number: 1100,
        draw_date: '2028-01-04',
        draw_sha256: '4'.repeat(64),
      },
    },
    evaluation_status: 'COMPLETE',
    family_size: 64,
    discovery,
    confirmation,
    comparisons,
    ...overrides,
  } as HistoricalSuccessTemporalHoldout
}

export function makeNotReadyTemporalHoldout():
  HistoricalSuccessTemporalHoldout {
  const complete = makeTemporalHoldout()
  return {
    ...complete,
    split: {
      ...complete.split,
      total_assignment_count: 1049,
      warmup_count: 1049,
      discovery_count: 0,
      confirmation_count: 0,
      discovery_first_target: null,
      discovery_last_target: null,
      confirmation_first_target: null,
      confirmation_last_target: null,
    },
    evaluation_status: 'NOT_READY_INSUFFICIENT_HISTORY',
    discovery: null,
    confirmation: null,
    comparisons: [],
  }
}

export function makeRecent50StabilityAudit(
  overrides: Partial<HistoricalSuccessRecent50StabilityAudit> = {},
): HistoricalSuccessRecent50StabilityAudit {
  const reference = makeTemporalPhase(250, 99)
  const recent = makeTemporalPhase(50, 18)
  const comparisons = reference.diagnostics.map((reference_diagnostic, index) => {
    const recent_diagnostic = recent.diagnostics[index]!
    const referenceEffect = reference_diagnostic.risk_difference
    const recentEffect = recent_diagnostic.risk_difference
    const bothAvailable = referenceEffect.available && recentEffect.available
    let effect_change = { numerator: 0, denominator: 0, available: false }
    if (bothAvailable) {
      const rawNumerator =
        recentEffect.numerator * referenceEffect.denominator -
        referenceEffect.numerator * recentEffect.denominator
      const rawDenominator =
        recentEffect.denominator * referenceEffect.denominator
      const divisor = gcd(rawNumerator, rawDenominator)
      effect_change = {
        numerator: rawNumerator / divisor,
        denominator: rawDenominator / divisor,
        available: true,
      }
    }
    const referenceRelation = reference_diagnostic.relation_vs_outside
    const recentRelation = recent_diagnostic.relation_vs_outside
    const relationship =
      referenceRelation === 'UNAVAILABLE' || recentRelation === 'UNAVAILABLE'
        ? 'UNAVAILABLE'
        : referenceRelation !== recentRelation
          ? 'DIFFERENT'
          : referenceRelation === 'HIGHER'
            ? 'SAME_HIGHER'
            : referenceRelation === 'EQUAL'
              ? 'SAME_EQUAL'
              : 'SAME_LOWER'
    return {
      cohort_index: index,
      feature_key: reference_diagnostic.feature_key,
      reference_diagnostic,
      recent_diagnostic,
      effect_change,
      relationship,
    }
  })
  return {
    metadata: reference.metadata,
    strategy: reference.strategy,
    criterion: reference.criterion,
    prefix_count: reference.prefix_count,
    split: {
      source_temporal_split_method:
        'FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION',
      audit_split_method:
        'FIXED_CONFIRMATION_FIRST_250_REFERENCE_LAST_50_RECENT',
      total_assignment_count: 1100,
      warmup_count: 50,
      discovery_count: 750,
      confirmation_count: 300,
      reference_count: 250,
      recent_count: 50,
      discovery_first_target: {
        draw_number: 51,
        draw_date: '2025-02-20',
        draw_sha256: '1'.repeat(64),
      },
      discovery_last_target: {
        draw_number: 800,
        draw_date: '2027-03-10',
        draw_sha256: '2'.repeat(64),
      },
      confirmation_first_target: {
        draw_number: 801,
        draw_date: '2027-03-11',
        draw_sha256: '3'.repeat(64),
      },
      confirmation_last_target: {
        draw_number: 1100,
        draw_date: '2028-01-04',
        draw_sha256: '4'.repeat(64),
      },
      reference_first_target: {
        draw_number: 801,
        draw_date: '2027-03-11',
        draw_sha256: '3'.repeat(64),
      },
      reference_last_target: {
        draw_number: 1050,
        draw_date: '2027-11-15',
        draw_sha256: '5'.repeat(64),
      },
      recent_first_target: {
        draw_number: 1051,
        draw_date: '2027-11-16',
        draw_sha256: '6'.repeat(64),
      },
      recent_last_target: {
        draw_number: 1100,
        draw_date: '2028-01-04',
        draw_sha256: '4'.repeat(64),
      },
    },
    audit_status: 'COMPLETE',
    family_size: 64,
    reference,
    recent,
    comparisons,
    ...overrides,
  }
}

export function makeNotReadyRecent50StabilityAudit():
  HistoricalSuccessRecent50StabilityAudit {
  const complete = makeRecent50StabilityAudit()
  return {
    ...complete,
    split: {
      ...complete.split,
      total_assignment_count: 1049,
      warmup_count: 1049,
      discovery_count: 0,
      confirmation_count: 0,
      reference_count: 0,
      recent_count: 0,
      discovery_first_target: null,
      discovery_last_target: null,
      confirmation_first_target: null,
      confirmation_last_target: null,
      reference_first_target: null,
      reference_last_target: null,
      recent_first_target: null,
      recent_last_target: null,
    },
    audit_status: 'NOT_READY_INSUFFICIENT_HISTORY',
    reference: null,
    recent: null,
    comparisons: [],
  }
}

export function makeCrossImportConcordance(
  overrides: Partial<HistoricalSuccessCrossImportConcordance> = {},
): HistoricalSuccessCrossImportConcordance {
  const holdout = makeTemporalHoldout()
  const confirmation = holdout.confirmation!
  return {
    metadata: {
      left: holdout.metadata,
      right: {
        ...holdout.metadata,
        run_id: 'run-explicit-2',
        import_identity_sha256: RIGHT_IMPORT_SHA,
      },
      same_dataset_sha256: true,
      same_source_artifact_sha256: true,
    },
    strategy: holdout.strategy,
    criterion: holdout.criterion,
    prefix_count: holdout.prefix_count,
    pair_status: 'COMPLETE',
    left_holdout_status: 'COMPLETE',
    right_holdout_status: 'COMPLETE',
    confirmation_target_overlap: {
      left_confirmation_target_count: 300,
      right_confirmation_target_count: 300,
      overlap_count: 300,
      left_only_count: 0,
      right_only_count: 0,
      relation: 'IDENTICAL',
    },
    comparisons: confirmation.diagnostics.map((diagnostic, cohort_index) => ({
      cohort_index,
      feature_key: diagnostic.feature_key,
      left_confirmation_diagnostic: diagnostic,
      right_confirmation_diagnostic: structuredClone(diagnostic),
      effect_change: diagnostic.risk_difference.available
        ? { numerator: 0, denominator: 1, available: true }
        : { numerator: 0, denominator: 0, available: false },
      relationship:
        diagnostic.relation_vs_outside === 'UNAVAILABLE'
          ? 'UNAVAILABLE'
          : diagnostic.relation_vs_outside === 'HIGHER'
            ? 'SAME_HIGHER'
            : diagnostic.relation_vs_outside === 'EQUAL'
              ? 'SAME_EQUAL'
              : 'SAME_LOWER',
    })),
    ...overrides,
  } as HistoricalSuccessCrossImportConcordance
}

export function makeNotReadyCrossImportConcordance(
  overrides: Partial<HistoricalSuccessCrossImportConcordance> = {},
): HistoricalSuccessCrossImportConcordance {
  const complete = makeCrossImportConcordance()
  return {
    ...complete,
    pair_status: 'LEFT_NOT_READY',
    left_holdout_status: 'NOT_READY_INSUFFICIENT_HISTORY',
    confirmation_target_overlap: null,
    comparisons: [],
    ...overrides,
  }
}

export function makeMultiImportConcordanceCensus(
  importCount = 3,
  overrides: Partial<HistoricalSuccessMultiImportConcordanceCensus> = {},
  selectedIdentities?: readonly string[],
): HistoricalSuccessMultiImportConcordanceCensus {
  const identities = [
    ...(selectedIdentities ?? [
      IMPORT_SHA,
      RIGHT_IMPORT_SHA,
      THIRD_IMPORT_SHA,
      FOURTH_IMPORT_SHA,
    ]),
  ].slice(0, importCount)
  const holdout = makeTemporalHoldout()
  const diagnostics = holdout.confirmation!.diagnostics
  const imports = identities.map((identity, import_index) => ({
    import_index,
    metadata: {
      ...holdout.metadata,
      run_id: `run-explicit-${import_index + 1}`,
      import_identity_sha256: identity,
    },
    holdout_status: 'COMPLETE' as const,
  }))
  const pairs = identities.flatMap((_, left_import_index) =>
    identities.slice(left_import_index + 1).map((__, offset) => {
      const right_import_index = left_import_index + offset + 1
      return {
        left_import_index,
        right_import_index,
        metadata: {
          left: imports[left_import_index]!.metadata,
          right: imports[right_import_index]!.metadata,
          same_dataset_sha256: true,
          same_source_artifact_sha256: true,
        },
        pair_status: 'COMPLETE' as const,
        left_holdout_status: 'COMPLETE' as const,
        right_holdout_status: 'COMPLETE' as const,
        confirmation_target_overlap: {
          left_confirmation_target_count: 300 as const,
          right_confirmation_target_count: 300 as const,
          overlap_count: 300,
          left_only_count: 0,
          right_only_count: 0,
          relation: 'IDENTICAL' as const,
        },
      }
    }),
  )
  const cohort_census = diagnostics.map((diagnostic, cohort_index) => {
    const relation = diagnostic.relation_vs_outside
    const higher_count = relation === 'HIGHER' ? importCount : 0
    const equal_count = relation === 'EQUAL' ? importCount : 0
    const lower_count = relation === 'LOWER' ? importCount : 0
    const unavailable_count = relation === 'UNAVAILABLE' ? importCount : 0
    return {
      cohort_index,
      feature_key: diagnostic.feature_key,
      confirmation_diagnostics: identities.map(
        (import_identity_sha256, import_index) => ({
          import_index,
          import_identity_sha256,
          diagnostic: structuredClone(diagnostic),
        }),
      ),
      higher_count,
      equal_count,
      lower_count,
      unavailable_count,
      summary:
        unavailable_count === importCount
          ? ('NO_AVAILABLE_EFFECT' as const)
          : higher_count === importCount
            ? ('ALL_AVAILABLE_HIGHER' as const)
            : equal_count === importCount
              ? ('ALL_AVAILABLE_EQUAL' as const)
              : ('ALL_AVAILABLE_LOWER' as const),
    }
  })
  return {
    imports,
    strategy: holdout.strategy,
    criterion: holdout.criterion,
    prefix_count: holdout.prefix_count,
    census_status: 'COMPLETE',
    pair_count: pairs.length,
    pairs,
    cohort_census_count: cohort_census.length,
    cohort_census,
    ...overrides,
  } as HistoricalSuccessMultiImportConcordanceCensus
}

export function makeResearchQualification(
  overrides: Partial<HistoricalSuccessResearchQualification> = {},
): HistoricalSuccessResearchQualification {
  return {
    identity: {
      strategy_id: 'alias strategy/one',
      strategy_version: 'v1 beta',
      replicate: 1,
      prefix_count: 1,
      criterion: 'M3_PLUS',
    },
    ordered_import_evidence: [
      {
        import_index: 0,
        import_identity_sha256: IMPORT_SHA,
        dataset_sha256: '1'.repeat(64),
        source_artifact_sha256: '3'.repeat(64),
        source_observation_count: 1050,
        strategy_window_status: 'COMPLETE',
        temporal_holdout_status: 'COMPLETE',
        recent_audit_status: 'COMPLETE',
        recent_relationship_difference_count: 0,
      },
      {
        import_index: 1,
        import_identity_sha256: RIGHT_IMPORT_SHA,
        dataset_sha256: '2'.repeat(64),
        source_artifact_sha256: '4'.repeat(64),
        source_observation_count: 1050,
        strategy_window_status: 'COMPLETE',
        temporal_holdout_status: 'COMPLETE',
        recent_audit_status: 'COMPLETE',
        recent_relationship_difference_count: 0,
      },
    ],
    primary_status: 'RESEARCH_CANDIDATE',
    informational_flags: ['HISTORICAL_CONCORDANCE_OBSERVED'],
    random_baseline_caveat:
      'Random/null benchmark unavailable; random advantage has not been evaluated.',
    comparable_import_count: 2,
    expected_pair_count: 1,
    actual_pair_count: 1,
    census_status: 'COMPLETE',
    cohort_census_count: 64,
    pair_evidence: [
      {
        left_import_index: 0,
        right_import_index: 1,
        pair_status: 'COMPLETE',
        same_dataset_sha256: false,
        same_source_artifact_sha256: false,
        confirmation_overlap_relation: 'DISJOINT',
        r1_comparable: true,
      },
    ],
    ...overrides,
  }
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
