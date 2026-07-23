import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

const clientSource = readFileSync(
  new URL('../src/api/historicalSuccessWindows.ts', import.meta.url),
  'utf8',
)
const pageSource = readFileSync(
  new URL(
    '../src/features/historical-success-windows/HistoricalSuccessWindowsPage.vue',
    import.meta.url,
  ),
  'utf8',
)

describe('Historical Success stability-matrix mutation guards', () => {
  it('pins criterion-outer and prefix-inner order with exactly 64 cells', () => {
    expect(clientSource).toContain('value.cell_count !== 64')
    expect(clientSource).toContain('value.cells.length !== 64')
    expect(clientSource).toContain(
      'Math.floor(index / HISTORICAL_SUCCESS_PREFIX_COUNTS.length)',
    )
    expect(clientSource).toContain(
      'index % HISTORICAL_SUCCESS_PREFIX_COUNTS.length',
    )
    expect(clientSource).toContain('if (seen.has(key)) return false')
  })

  it('pins signed exact delta direction and unavailable handling without floats', () => {
    expect(clientSource).toContain(
      'toRate.numerator * fromRate.denominator -',
    )
    expect(clientSource).toContain(
      'fromRate.numerator * toRate.denominator',
    )
    expect(clientSource).toContain("return [0, 0, false, 'UNAVAILABLE']")
    expect(clientSource).toContain('Number.isSafeInteger')
    expect(clientSource).not.toContain('parseFloat')
  })

  it('keeps selection manual, ordered, duplicate-free, and capped at four', () => {
    const toggle = pageSource.split('function toggleMatrixSelection(')[1]!.split(
      'function chooseRun(',
    )[0]!
    expect(toggle).toContain('matrixSelections.value.length >= 4')
    expect(toggle).toContain('matrixIdentity(selected) === identity')
    expect(toggle).toContain(
      'matrixSelections.value = [...matrixSelections.value, item]',
    )
    expect(toggle).not.toContain('sort(')
    expect(toggle).not.toContain('compareSelectedMatrices')
  })

  it('pins one shared generation guard and aborts compare, run-change, and unmount work', () => {
    expect(pageSource).toContain('const generation = ++matrixGeneration')
    expect(pageSource).toContain('matrixController?.abort()')
    expect(pageSource).toContain('generation !== matrixGeneration')
    expect(pageSource).toContain('clearMatrix(true)')
    expect(pageSource).toContain('matrixController?.abort()')
  })

  it('keeps comparison language neutral and prohibits performance sorting', () => {
    const matrixValidator = clientSource.split('function isStabilityMatrix(')[1]!.split(
      'function isFeatureKey(',
    )[0]!
    expect(pageSource).toContain('comparison.relation')
    expect(pageSource).not.toMatch(/\bwinner\b/i)
    expect(pageSource).not.toMatch(/\bbest strategy\b/i)
    expect(pageSource).not.toContain('.sort(')
    expect(matrixValidator).not.toContain('.sort(')
    expect(clientSource).not.toMatch(/IMPROVED|DEGRADED/)
  })
})

describe('Historical Success feature-cohort inferential diagnostics mutation guards', () => {
  it('pins exact BigInt probability validation and fixed method identities', () => {
    const validator = clientSource.split('function isExactProbability(')[1]!.split(
      'function compareExactProbabilities(',
    )[0]!
    expect(validator).toContain('BigInt(value.numerator)')
    expect(validator).toContain('BigInt(value.denominator)')
    expect(validator).toContain('greatestCommonDivisorBigInt')
    expect(clientSource).toContain('value.family_size !== 64')
    expect(clientSource).toContain(
      "value.raw_test_method !== 'FISHER_EXACT_TWO_SIDED_PROBABILITY_ORDERING'",
    )
    expect(clientSource).toContain(
      "value.adjustment_method !== 'BENJAMINI_YEKUTIELI'",
    )
  })

  it('pins canonical order, disjoint counts, test status, and monotone adjustment', () => {
    expect(clientSource).toContain('value.cohort_index !== index')
    expect(clientSource).toContain(
      'cohort.observation_count + outside.observation_count !==',
    )
    expect(clientSource).toContain('expectedDiagnosticStatus(cohort, outside)')
    expect(clientSource).toContain(
      "raw.numerator === '1' && raw.denominator === '1'",
    )
    expect(clientSource).toContain(
      'left.cohort_index - right.cohort_index',
    )
    expect(clientSource).toContain(
      'sorted[index - 1]!.adjusted_p_value',
    )
  })

  it('keeps diagnostics separate, explicit, ordered, and capped at four', () => {
    const toggle = pageSource.split('function toggleMatrixSelection(')[1]!.split(
      'function chooseRun(',
    )[0]!
    const evaluate = pageSource.split(
      'async function evaluateSelectedFeatureCohortDiagnostics(',
    )[1]!.split('async function loadResults(', 1)[0]!
    expect(pageSource).toContain('Evaluate cohort inferential diagnostics')
    expect(toggle).not.toContain('evaluateSelectedFeatureCohortDiagnostics')
    expect(evaluate).toContain('selections.length > 4')
    expect(evaluate).toContain('selections.map(async (selection)')
    expect(evaluate).not.toContain('.sort(')
  })

  it('pins abort and stale-generation guards across reevaluation and lifecycle changes', () => {
    expect(pageSource).toContain(
      'const generation = ++featureCohortDiagnosticsGeneration',
    )
    expect(pageSource).toContain('featureCohortDiagnosticsController?.abort()')
    expect(pageSource).toContain(
      'generation !== featureCohortDiagnosticsGeneration',
    )
    expect(pageSource).toContain('clearFeatureCohortDiagnostics()')
  })

  it('renders all diagnostics in server order without decision semantics', () => {
    const section = pageSource.split(
      'class="research-results feature-cohort-diagnostics"',
    )[1]!.split('<aside ', 1)[0]!
    expect(section).toContain(
      'v-for="diagnostic in outcome.result.diagnostics"',
    )
    expect(section).toContain('diagnostic.raw_p_value')
    expect(section).toContain('diagnostic.adjusted_p_value')
    expect(section).not.toContain('.sort(')
    expect(section).not.toMatch(
      /significant|winner|best pattern|promotion|prediction/i,
    )
  })
})

describe('Historical Success walk-forward feature-cohort mutation guards', () => {
  it('pins the exact 64-key nested relation order with no omission or duplicate', () => {
    expect(clientSource).toContain('value.cohort_count !== 64')
    expect(clientSource).toContain('value.cohorts.length !== 64')
    expect(clientSource).toContain('Math.floor(index / 16)')
    expect(clientSource).toContain('Math.floor((index % 16) / 4)')
    expect(clientSource).toContain('index % 4')
    expect(clientSource).toContain('if (!isFeatureCohort(cohort, index, baselineRate))')
  })

  it('pins count arithmetic, unavailable states, and cohort-minus-baseline direction', () => {
    expect(clientSource).toContain(
      'value.success_count + value.failure_count !== value.observation_count',
    )
    expect(clientSource).toContain('expectedSignedDelta(baselineRate, rate)')
    expect(clientSource).toContain('value.delta_vs_baseline.numerator === numerator')
    expect(clientSource).toContain("value.relation_vs_baseline === 'UNAVAILABLE'")
    expect(clientSource).not.toContain('parseFloat')
  })

  it('keeps feature evaluation separate, explicit, ordered, and capped at four', () => {
    const toggle = pageSource.split('function toggleMatrixSelection(')[1]!.split(
      'function chooseRun(',
    )[0]!
    const evaluate = pageSource.split(
      'async function evaluateSelectedFeatureCohorts(',
    )[1]!.split('async function loadResults(', 1)[0]!
    expect(pageSource).toContain('Evaluate walk-forward feature cohorts')
    expect(toggle).not.toContain('evaluateSelectedFeatureCohorts')
    expect(evaluate).toContain('selections.length > 4')
    expect(evaluate).toContain('selections.map(async (selection)')
    expect(evaluate).not.toContain('.sort(')
  })

  it('pins shared abort and generation guards for reevaluation, run change, and unmount', () => {
    expect(pageSource).toContain('const generation = ++featureCohortGeneration')
    expect(pageSource).toContain('featureCohortController?.abort()')
    expect(pageSource).toContain('generation !== featureCohortGeneration')
    expect(pageSource).toContain('clearFeatureCohorts()')
  })

  it('keeps the new result section descriptive and in server order', () => {
    const section = pageSource.split(
      '<section class="research-results feature-cohort-comparison"',
    )[1]!.split('<aside ', 1)[0]!
    expect(section).toContain('v-for="cohort in outcome.result.cohorts"')
    expect(section).not.toContain('.sort(')
    expect(section).not.toMatch(
      /best feature|winning pattern|recommendation|promotion|rejection|prediction/i,
    )
  })
})

describe('Historical Success 750/300 temporal holdout mutation guards', () => {
  it('pins fixed split counts, not-ready behavior, and all 64 comparisons', () => {
    const validator = clientSource.split('function isTemporalHoldout(')[1]!.split(
      'function isSuccessPage(',
    )[0]!
    expect(validator).toContain(
      "'FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION'",
    )
    expect(validator).toContain('split.discovery_count !== 750')
    expect(validator).toContain('split.confirmation_count !== 300')
    expect(validator).toContain('split.total_assignment_count < 1050')
    expect(validator).toContain('value.comparisons.length !== 64')
    expect(validator).not.toMatch(/percentage|fallback/i)
  })

  it('preserves exact probability strings and computes effect change with BigInt', () => {
    const effect = clientSource.split('function isExactEffectChange(')[1]!.split(
      'function expectedTemporalRelationship(',
    )[0]!
    expect(effect).toContain('BigInt(confirmation.numerator as number)')
    expect(effect).toContain('BigInt(discovery.numerator as number)')
    expect(effect).toContain('greatestCommonDivisorBigInt')
    expect(effect).not.toContain('Number(')
    expect(clientSource).toContain('isExactProbability(value.raw_p_value)')
  })

  it('keeps holdout requests explicit, ordered, capped at four, and unsorted', () => {
    const toggle = pageSource.split('function toggleMatrixSelection(')[1]!.split(
      'function chooseRun(',
    )[0]!
    const evaluate = pageSource.split(
      'async function evaluateSelectedTemporalHoldout(',
    )[1]!.split('async function loadResults(', 1)[0]!
    expect(pageSource).toContain('Evaluate 750/300 temporal holdout')
    expect(toggle).not.toContain('evaluateSelectedTemporalHoldout')
    expect(evaluate).toContain('selections.length > 4')
    expect(evaluate).toContain('selections.map(async (selection)')
    expect(evaluate).not.toContain('.sort(')
  })

  it('pins abort and stale-response guards for reevaluation and lifecycle changes', () => {
    expect(pageSource).toContain('const generation = ++temporalHoldoutGeneration')
    expect(pageSource).toContain('temporalHoldoutController?.abort()')
    expect(pageSource).toContain('generation !== temporalHoldoutGeneration')
    expect(pageSource).toContain('clearTemporalHoldout()')
  })

  it('renders every canonical comparison without decision or sorting semantics', () => {
    const section = pageSource.split(
      '<section class="research-results temporal-holdout-panel"',
    )[1]!.split('<aside ', 1)[0]!
    expect(section).toContain(
      'v-for="comparison in outcome.result.comparisons"',
    )
    expect(section).toContain('comparison.discovery_diagnostic.raw_p_value')
    expect(section).toContain('comparison.confirmation_diagnostic.adjusted_p_value')
    expect(section).toContain('comparison.relationship')
    expect(section).not.toContain('.sort(')
    expect(section).not.toMatch(
      /replicated|failed replication|significant|winner|promotion|rejection|prediction/i,
    )
  })
})
