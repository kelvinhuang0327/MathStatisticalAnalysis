// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import OfficialRankingPanel from '../src/features/ranking-matrix/OfficialRankingPanel.vue'
import {
  fetchOfficialRanking,
  type OfficialRankingRunDiagnostic,
  type OfficialRankingResponse,
} from '../src/api/rankingMatrix'

function response(
  item: Record<string, unknown>,
  runDiagnostics: OfficialRankingRunDiagnostic[] = [],
): OfficialRankingResponse {
  return {
    lottery_type: 'BIG_LOTTO',
    window: 'RECENT_300',
    baseline_policy: 'UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT',
    items: [item as OfficialRankingResponse['items'][number]],
    run_diagnostics: runDiagnostics,
  }
}

const failedItem = {
  strategy_id: 'failed-strategy',
  strategy_name: 'Failed Strategy',
  registered: true,
  strategy_version: 'v1',
  execution_version: 'e1',
  dataset_identity: 'd1',
  run_id: 'r1',
  scope_status: 'MANIFEST' as const,
  missing_target_evidence: 0,
  conflicting_target_evidence: 0,
  ticket_count: 1,
  target_ids: ['1', '2', '3', '4', '5'],
  start_date: '2026-01-01',
  end_date: '2026-01-01',
  successes: 0,
  evaluated: 0,
  missing: 2,
  unknown: 1,
  rate: null,
  baseline: null,
  delta: null,
  unknown_reason: 'UNKNOWN cells: 1; FAILED cells: 1; NOT_ELIGIBLE cells: 1',
  rank: null,
  failed_count: 1,
  not_eligible_count: 1,
}

afterEach(() => vi.restoreAllMocks())

describe('official ranking status counts', () => {
  it('defaults missing additive counts from older responses to zero', async () => {
    const olderItem: Record<string, unknown> = { ...failedItem }
    delete olderItem.failed_count
    delete olderItem.not_eligible_count
    const olderResponse = response(olderItem)
    delete olderResponse.run_diagnostics
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => olderResponse,
    } as Response)

    const result = await fetchOfficialRanking('BIG_LOTTO', 'RECENT_300')
    expect(result.items[0]?.failed_count).toBe(0)
    expect(result.items[0]?.not_eligible_count).toBe(0)
    expect(result.run_diagnostics).toEqual([])
  })

  it('shows failed and not-eligible counts and their reason', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => response(failedItem),
    } as Response)

    const wrapper = mount(OfficialRankingPanel)
    await flushPromises()
    const cells = wrapper.find('tbody tr').findAll('td')
    expect(cells[9]?.text()).toBe('2')
    expect(cells[10]?.text()).toBe('1')
    expect(cells[11]?.text()).toBe('1')
    expect(cells[12]?.text()).toBe('1')
    expect(cells[16]?.text()).toContain('FAILED')
    expect(cells[16]?.text()).toContain('NOT_ELIGIBLE')
  })

  it('shows an invalid-manifest run diagnostic without a strategy identity', async () => {
    const diagnostic: OfficialRankingRunDiagnostic = {
      kind: 'INVALID_MANIFEST_NO_STRATEGY_IDENTITY',
      run_id: 'run-without-strategies',
      matrix_reason: 'invalid_manifest_strategies; expected_cells_mismatch',
      successes: 0,
      evaluated: 0,
      denominator: 0,
      rate: null,
      baseline: null,
      delta: null,
      rank: null,
    }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => response(failedItem, [diagnostic]),
    } as Response)

    const wrapper = mount(OfficialRankingPanel)
    await flushPromises()
    const text = wrapper.get('[data-testid="ranking-run-diagnostics"]').text()
    expect(text).toContain('run-without-strategies')
    expect(text).toContain('invalid_manifest_strategies; expected_cells_mismatch')
    expect(text).toContain('分母皆為 0')
  })
})
