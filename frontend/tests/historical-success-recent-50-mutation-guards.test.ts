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

describe('Historical Success recent-50 mutation guards', () => {
  it('pins exact 250/50 counts, chronology, two 64 families, and comparison order', () => {
    const validator = clientSource.split('function isRecent50StabilityAudit(')[1]!.split(
      'function isCrossImportConcordance(',
    )[0]!
    expect(validator).toContain('split.reference_count !== 250')
    expect(validator).toContain('split.recent_count !== 50')
    expect(validator).toContain('split.confirmation_count !== split.reference_count + split.recent_count')
    expect(validator).toContain('compareDrawIdentities(referenceLast, recentFirst)')
    expect(validator).toContain('value.reference.baseline.observation_count !== 250')
    expect(validator).toContain('value.recent.baseline.observation_count !== 50')
    expect(validator).toContain('value.comparisons.length !== 64')
    expect(validator).toContain('comparison.cohort_index !== index')
    expect(validator).not.toContain('128')
    expect(validator).not.toContain('.sort(')
  })

  it('keeps exact probabilities as BigInt-validated strings and exact effect direction', () => {
    const probabilityValidator = clientSource.split('function isExactProbability(')[1]!.split(
      'function compareExactProbabilities(',
    )[0]!
    const effectValidator = clientSource.split('function isExactEffectChange(')[1]!.split(
      'function expectedTemporalRelationship(',
    )[0]!
    expect(probabilityValidator).toContain('BigInt(value.numerator)')
    expect(probabilityValidator).toContain('BigInt(value.denominator)')
    expect(probabilityValidator).not.toContain('Number(')
    expect(effectValidator).toContain(
      'BigInt(confirmation.numerator as number) *',
    )
    expect(effectValidator).toContain(
      'BigInt(discovery.numerator as number) *',
    )
  })

  it('requires an explicit ordered one-to-four request action with stale guards', () => {
    const evaluate = pageSource.split(
      'async function evaluateRecent50StabilityAudit(',
    )[1]!.split('async function evaluateCrossImportConcordance(', 1)[0]!
    const toggle = pageSource.split('function toggleMatrixSelection(')[1]!.split(
      'function chooseRun(',
    )[0]!
    expect(pageSource).toContain('Evaluate recent-50 stability audit')
    expect(toggle).not.toContain('evaluateRecent50StabilityAudit')
    expect(toggle).toContain('matrixSelections.value.length >= 4')
    expect(evaluate).toContain('selections.length > 4')
    expect(evaluate).toContain('selections.map(async (selection)')
    expect(evaluate).toContain('generation !== recent50StabilityAuditGeneration')
    expect(evaluate).toContain('recent50StabilityAuditController?.abort()')
    expect(evaluate).not.toContain('.sort(')
    expect(pageSource).toContain('clearRecent50StabilityAudit()')
  })

  it('renders all 64 server-ordered rows with neutral descriptive language', () => {
    const panel = pageSource
      .split('class="research-results recent-50-stability-audit-panel"')[1]!
      .split('</section>', 1)[0]!
    expect(panel).toContain('v-for="comparison in outcome.result.comparisons"')
    expect(panel).toContain('reference_diagnostic.raw_p_value')
    expect(panel).toContain('recent_diagnostic.adjusted_p_value')
    expect(panel).toContain('Descriptive only')
    expect(panel).not.toContain('.sort(')
    expect(panel).not.toMatch(
      /\bveto\b|\bpass\b|\bfail(?:ed|ure)?\b|degraded|promoted|rejected|significant|winner|score|rank|prediction/i,
    )
  })
})
