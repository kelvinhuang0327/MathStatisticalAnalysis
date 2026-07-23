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
    expect(pageSource).toContain('comparison.relation')
    expect(pageSource).not.toMatch(/\bwinner\b/i)
    expect(pageSource).not.toMatch(/\bbest strategy\b/i)
    expect(pageSource).not.toContain('.sort(')
    expect(clientSource).not.toContain('.sort(')
    expect(clientSource).not.toMatch(/IMPROVED|DEGRADED/)
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
