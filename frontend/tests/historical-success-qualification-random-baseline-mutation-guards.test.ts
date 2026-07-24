import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

const apiSource = readFileSync(
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

describe('qualification random-baseline mutation guards', () => {
  it('pins the adjacent request, strict validator, order, and independent controller', () => {
    expect(apiSource).toContain(
      '/research-qualification/random-baseline-evidence?${parameters.toString()}',
    )
    expect(apiSource).toContain(
      'function isQualificationRandomBaselineEvidence(',
    )
    expect(apiSource).toContain(
      "['FULL_HISTORY', 'REFERENCE_ONLY']",
    )
    expect(apiSource).toContain(
      "['LONG', 'PRIMARY_DESCRIPTIVE_COMPARISON']",
    )
    expect(apiSource).toContain(
      "['MEDIUM', 'CONFIRMATION_DESCRIPTIVE_COMPARISON']",
    )
    expect(apiSource).toContain(
      "['SHORT', 'AUDIT_ONLY_NON_BLOCKING']",
    )
    expect(apiSource).toContain(
      'identities.length * QUALIFICATION_RANDOM_WINDOW_ROLES.length',
    )
    expect(apiSource).toContain(
      'isRandomBaselineResponse(cell.baseline, {',
    )
    expect(apiSource).toContain('const sourceHashes = new Map<number, string>()')
    expect(pageSource).toContain(
      'void evaluateQualificationRandomBaselineEvidence()',
    )
    expect(pageSource).toContain(
      'qualificationRandomBaselineController?.abort()',
    )
    expect(pageSource).toContain(
      'generation !== qualificationRandomBaselineGeneration',
    )
  })

  it('keeps loading explicit and renders every required descriptive field', () => {
    const section = pageSource.slice(
      pageSource.indexOf(
        'class="qualification-random-baseline-result-list"',
      ),
      pageSource.indexOf('</section>', pageSource.indexOf(
        'class="qualification-random-baseline-result-list"',
      )),
    )

    expect(pageSource).toContain('@click="evaluateResearchQualification"')
    expect(pageSource).not.toContain(
      'watch(qualificationRandomBaseline',
    )
    expect(section).toContain('availability_summary.availability_status')
    expect(section).toContain('availability_summary.evaluated_cell_count')
    expect(section).toContain('availability_summary.ready_cell_count')
    expect(section).toContain('multiple_testing_warning')
    expect(section).toContain('qualification_random_role')
    expect(section).toContain('baseline.reason_codes')
    expect(section).toContain('baseline.observed_success_count')
    expect(section).toContain('baseline.eligible_observation_count')
    expect(section).toContain('baseline.expected_successes')
    expect(section).toContain('baseline.upper_tail_probability')
    expect(section).toContain('baseline.observed_duplicate_ticket_count')
    expect(section).toContain('baseline.observation_count_with_duplicates')
    expect(section).toContain('baseline.interpretation_caveat')
  })

  it('permits only the exact negative warnings and no affirmative policy hook', () => {
    const exactCandidateCaveat =
      'Exact official-six-number IID random-benchmark cells are available as descriptive evidence when READY; NOT_READY cells expose no observed, expected, or upper-tail result. No significance threshold, random-advantage decision, ranking, promotion, rejection, production-eligibility decision, or monetary-cost equivalence has been authorized.'
    const exactWarningParts = [
      'No multiplicity adjustment, threshold, pooled probability, combined decision, ',
      'or random-advantage inference is authorized.',
    ]
    const exactCellCaveat =
      'Descriptive official-six-number IID random benchmark only. This result does not establish statistical significance, ranking, promotion, rejection, prediction quality, production eligibility, or monetary cost equivalence.'
    const constants = apiSource.slice(
      apiSource.indexOf(
        'export const HISTORICAL_SUCCESS_RANDOM_BASELINE_CAVEAT',
      ),
      apiSource.indexOf('const PREFIX_COUNT_SET'),
    )
    const validator = apiSource.slice(
      apiSource.indexOf('function qualificationRandomWarning('),
      apiSource.indexOf('function isSuccessPage('),
    )
    const request = apiSource.slice(
      apiSource.indexOf(
        'export async function getHistoricalSuccessQualificationRandomBaselineEvidence(',
      ),
    )
    const rendering = pageSource.slice(
      pageSource.indexOf(
        'class="qualification-random-baseline-result-list"',
      ),
      pageSource.indexOf(
        '</section>',
        pageSource.indexOf(
          'class="qualification-random-baseline-result-list"',
        ),
      ),
    )
    const sanitized = `${constants}\n${validator}\n${request}\n${rendering}`
      .replaceAll(exactCandidateCaveat, '')
      .replaceAll(exactWarningParts[0], '')
      .replaceAll(exactWarningParts[1], '')
      .replaceAll(exactCellCaveat, '')
      .toLowerCase()

    for (const forbidden of [
      'alpha',
      'adjusted_probability',
      'combined_probability',
      'pooled_probability',
      'ranking_score',
      'promotion_status',
      'production_eligible',
      'random_advantage',
    ]) {
      expect(sanitized).not.toContain(forbidden)
    }
  })
})
