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
