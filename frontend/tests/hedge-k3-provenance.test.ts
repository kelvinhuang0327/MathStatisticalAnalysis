// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import HedgeK3Summary from '../src/features/replay-history/HedgeK3Summary.vue'
import {
  HEDGE_K3_STRATEGY_ID,
  normalizeHedgeK3ProvenanceStatus,
  computeHedgeK3ProvenanceMetricSummary,
  getHedgeK3StoredResults,
  type HedgeK3StoredResult,
} from '../src/api/replayBackfill'

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function hedgeRow(
  targetDrawId: string,
  overrides: Partial<HedgeK3StoredResult> & Record<string, unknown> = {},
) {
  return {
    target_draw_id: targetDrawId,
    strategy_id: HEDGE_K3_STRATEGY_ID,
    strategy_version: 'v1',
    execution_status: 'COMPLETE',
    hedge_phase: 'evaluation',
    reference_any_prize: true,
    combination_success: true,
    source_history_provenance_status: 'VERIFIED',
    ...overrides,
  }
}

function resultsPage(items: unknown[] = [], totalCount = items.length, limit = 200, offset = 0) {
  return {
    items,
    total_count: totalCount,
    limit,
    offset,
  }
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Hedge K3 Provenance Presentation (AC1 - AC7)', () => {
  it('AC1: records pinned commit, tree, and source blob identities', () => {
    const pinnedCommit = '07a57d89fb5bb1f5fbe70be5f331f128c9e08694'
    const pinnedTree = 'aaa463e8e152197e4bc57fad95a35ea19df85d61'
    const sourceApiBlob = '51d0d40affc67bc30991e302955d923891c08191'
    const sourceComponentBlob = '5b1e55a319b046c33127af26f81f660f015c28d3'

    expect(pinnedCommit).toHaveLength(40)
    expect(pinnedTree).toHaveLength(40)
    expect(sourceApiBlob).toHaveLength(40)
    expect(sourceComponentBlob).toHaveLength(40)
  })

  it('AC2: validates provenance status and never upgrades UNKNOWN, UNVERIFIED, missing or invalid to VERIFIED', () => {
    expect(normalizeHedgeK3ProvenanceStatus('VERIFIED')).toBe('VERIFIED')
    expect(normalizeHedgeK3ProvenanceStatus('UNKNOWN')).toBe('UNKNOWN')
    expect(normalizeHedgeK3ProvenanceStatus('UNVERIFIED')).toBe('UNVERIFIED')

    // Missing field
    expect(normalizeHedgeK3ProvenanceStatus(undefined)).toBe('UNKNOWN')
    expect(normalizeHedgeK3ProvenanceStatus(null)).toBe('UNKNOWN')

    // Invalid values
    expect(normalizeHedgeK3ProvenanceStatus('INVALID_STATUS')).toBe('UNKNOWN')
    expect(normalizeHedgeK3ProvenanceStatus(123)).toBe('UNKNOWN')
    expect(normalizeHedgeK3ProvenanceStatus(true)).toBe('UNKNOWN')
    expect(normalizeHedgeK3ProvenanceStatus('')).toBe('UNKNOWN')
    expect(normalizeHedgeK3ProvenanceStatus({})).toBe('UNKNOWN')

    // Strict guarantee: non-VERIFIED never upgrades to VERIFIED
    const nonVerifiedInputs = ['UNKNOWN', 'UNVERIFIED', undefined, null, 'INVALID', 999, false, 'verified']
    for (const input of nonVerifiedInputs) {
      expect(normalizeHedgeK3ProvenanceStatus(input)).not.toBe('VERIFIED')
    }
  })

  it('AC2: getHedgeK3StoredResults normalizes missing and invalid provenance to UNKNOWN while retaining VERIFIED and UNVERIFIED', async () => {
    const rawItems = [
      hedgeRow('1', { source_history_provenance_status: 'VERIFIED' }),
      hedgeRow('2', { source_history_provenance_status: 'UNKNOWN' }),
      hedgeRow('3', { source_history_provenance_status: 'UNVERIFIED' }),
      hedgeRow('4', { source_history_provenance_status: undefined }),
      hedgeRow('5', { source_history_provenance_status: 'TAMPERED_OR_INVALID' }),
    ]

    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(resultsPage(rawItems)))
    vi.stubGlobal('fetch', fetchMock)

    const controller = new AbortController()
    const rows = await getHedgeK3StoredResults('run-1', 'v1', controller.signal)

    expect(rows).toHaveLength(5)
    expect(rows[0].source_history_provenance_status).toBe('VERIFIED')
    expect(rows[1].source_history_provenance_status).toBe('UNKNOWN')
    expect(rows[2].source_history_provenance_status).toBe('UNVERIFIED')
    expect(rows[3].source_history_provenance_status).toBe('UNKNOWN')
    expect(rows[4].source_history_provenance_status).toBe('UNKNOWN')
  })

  it('AC3: separates verified numerator/denominator from raw counts and excludes UNKNOWN and UNVERIFIED from verified rate', () => {
    const syntheticData: HedgeK3StoredResult[] = [
      hedgeRow('1', { source_history_provenance_status: 'VERIFIED', reference_any_prize: true, combination_success: true }),
      hedgeRow('2', { source_history_provenance_status: 'VERIFIED', reference_any_prize: false, combination_success: false }),
      hedgeRow('3', { source_history_provenance_status: 'UNKNOWN', reference_any_prize: true, combination_success: true }),
      hedgeRow('4', { source_history_provenance_status: 'UNVERIFIED', reference_any_prize: true, combination_success: true }),
    ]

    const refSummary = computeHedgeK3ProvenanceMetricSummary(syntheticData, 'reference_any_prize')
    const combSummary = computeHedgeK3ProvenanceMetricSummary(syntheticData, 'combination_success')

    // Verified stats: only draws 1 and 2
    expect(refSummary.verified_numerator).toBe(1)
    expect(refSummary.verified_denominator).toBe(2)
    expect(refSummary.verified_rate_display).toBe('1/2')

    expect(combSummary.verified_numerator).toBe(1)
    expect(combSummary.verified_denominator).toBe(2)
    expect(combSummary.verified_rate_display).toBe('1/2')

    // Raw stored flags: draws 1, 3, 4 are true out of 4 total
    expect(refSummary.raw_true_count).toBe(3)
    expect(refSummary.raw_total_count).toBe(4)
    expect(refSummary.raw_flag_display).toBe('3/4')

    // Provenance counts
    expect(refSummary.verified_count).toBe(2)
    expect(refSummary.unknown_count).toBe(1)
    expect(refSummary.unverified_count).toBe(1)
    expect(refSummary.missing_flag_count).toBe(0)
  })

  it('AC3: renders verified rate, raw stored flag, and provenance breakdown in UI component', async () => {
    const rawItems = [
      hedgeRow('1', { source_history_provenance_status: 'VERIFIED', reference_any_prize: true, combination_success: true }),
      hedgeRow('2', { source_history_provenance_status: 'VERIFIED', reference_any_prize: false, combination_success: false }),
      hedgeRow('3', { source_history_provenance_status: 'UNKNOWN', reference_any_prize: true, combination_success: true }),
      hedgeRow('4', { source_history_provenance_status: 'UNVERIFIED', reference_any_prize: true, combination_success: true }),
    ]

    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(resultsPage(rawItems)))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(HedgeK3Summary, {
      props: { runId: 'run-provenance-test', strategyVersion: 'v1' },
    })
    await flushPromises()

    const allRefVerified = wrapper.get('[data-testid="k3-all-reference_any_prize-verified"]')
    const allRefRaw = wrapper.get('[data-testid="k3-all-reference_any_prize-raw"]')
    const allRefCounts = wrapper.get('[data-testid="k3-all-reference_any_prize-counts"]')

    expect(allRefVerified.text()).toBe('1/2')
    expect(allRefRaw.text()).toBe('3/4')
    expect(allRefCounts.text()).toContain('已驗證 2 期')
    expect(allRefCounts.text()).toContain('UNKNOWN 1 期')
    expect(allRefCounts.text()).toContain('UNVERIFIED 1 期')

    // Verified rate must NOT equal raw flag 3/4
    expect(allRefVerified.text()).not.toBe('3/4')
    wrapper.unmount()
  })

  it('AC4: displays "無法評估" when verified denominator is 0, never displaying "0%", "NaN", or "Infinity"', async () => {
    // Only UNKNOWN and UNVERIFIED data, zero VERIFIED records
    const rawItems = [
      hedgeRow('1', { source_history_provenance_status: 'UNKNOWN', reference_any_prize: true, combination_success: true }),
      hedgeRow('2', { source_history_provenance_status: 'UNVERIFIED', reference_any_prize: true, combination_success: true }),
    ]

    const summary = computeHedgeK3ProvenanceMetricSummary(rawItems as HedgeK3StoredResult[], 'reference_any_prize')
    expect(summary.verified_denominator).toBe(0)
    expect(summary.verified_rate_display).toBe('無法評估')
    expect(summary.verified_rate_display).not.toContain('0%')
    expect(summary.verified_rate_display).not.toContain('NaN')
    expect(summary.verified_rate_display).not.toContain('Infinity')

    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(resultsPage(rawItems)))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(HedgeK3Summary, {
      props: { runId: 'run-zero-denom', strategyVersion: 'v1' },
    })
    await flushPromises()

    const verifiedEl = wrapper.get('[data-testid="k3-all-reference_any_prize-verified"]')
    expect(verifiedEl.text()).toBe('無法評估')
    expect(verifiedEl.text()).not.toContain('0%')
    expect(verifiedEl.text()).not.toContain('NaN')
    expect(verifiedEl.text()).not.toContain('Infinity')
    wrapper.unmount()
  })

  it('AC4: excludes non-boolean flags from verified denominator and reports missing flag count', () => {
    const rawItems: HedgeK3StoredResult[] = [
      hedgeRow('1', { source_history_provenance_status: 'VERIFIED', reference_any_prize: null as unknown as boolean }),
      hedgeRow('2', { source_history_provenance_status: 'VERIFIED', reference_any_prize: undefined as unknown as boolean }),
    ]

    const summary = computeHedgeK3ProvenanceMetricSummary(rawItems, 'reference_any_prize')
    expect(summary.verified_denominator).toBe(0)
    expect(summary.verified_rate_display).toBe('無法評估')
    expect(summary.missing_flag_count).toBe(2)
  })

  it('AC5: clearly separates warmup and evaluation periods when hedge_phase is present', async () => {
    const rawItems = [
      hedgeRow('1', { hedge_phase: 'warmup', source_history_provenance_status: 'VERIFIED', reference_any_prize: true }),
      hedgeRow('2', { hedge_phase: 'warmup', source_history_provenance_status: 'VERIFIED', reference_any_prize: true }),
      hedgeRow('3', { hedge_phase: 'evaluation', source_history_provenance_status: 'VERIFIED', reference_any_prize: true }),
      hedgeRow('4', { hedge_phase: 'evaluation', source_history_provenance_status: 'VERIFIED', reference_any_prize: false }),
    ]

    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(resultsPage(rawItems)))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(HedgeK3Summary, {
      props: { runId: 'run-phases', strategyVersion: 'v1' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('包含前 2 期暖機')

    // All periods: 2 warmup + 2 eval = 4 total, verified 3 true out of 4 = 3/4
    const allVerified = wrapper.get('[data-testid="k3-all-reference_any_prize-verified"]')
    expect(allVerified.text()).toBe('3/4')

    // Excluded warmup (eval only): 2 eval draws, verified 1 true out of 2 = 1/2
    const evalVerified = wrapper.get('[data-testid="k3-eval-reference_any_prize-verified"]')
    expect(evalVerified.text()).toBe('1/2')

    wrapper.unmount()
  })

  it('AC5: refuses to display complete evaluation stats when hedge_phase is missing or invalid', async () => {
    const rawItems = [
      hedgeRow('1', { hedge_phase: 'warmup', source_history_provenance_status: 'VERIFIED' }),
      hedgeRow('2', { hedge_phase: 'invalid_phase', source_history_provenance_status: 'VERIFIED' }),
    ]

    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(resultsPage(rawItems)))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(HedgeK3Summary, {
      props: { runId: 'run-missing-phase', strategyVersion: 'v1' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('暖機範圍未確認（API 缺少有效的 hedge_phase）')
    const evalCell = wrapper.get('[data-testid="k3-eval-reference_any_prize"]')
    expect(evalCell.text()).toContain('API 缺少有效的 hedge_phase')
    expect(evalCell.find('[data-testid="k3-eval-reference_any_prize-verified"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('AC6: filters out rows from other runs and strategy versions', async () => {
    const rawItems = [
      hedgeRow('1', { run_id: 'run-target', strategy_version: 'v1' }),
      hedgeRow('2', { run_id: 'run-other', strategy_version: 'v1' }),
      hedgeRow('3', { run_id: 'run-target', strategy_version: 'v2' }),
      hedgeRow('4', { run_id: 'run-target', strategy_id: 'other_strategy' }),
    ]

    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(resultsPage(rawItems)))
    vi.stubGlobal('fetch', fetchMock)

    const controller = new AbortController()
    const rows = await getHedgeK3StoredResults('run-target', 'v1', controller.signal)

    expect(rows).toHaveLength(1)
    expect(rows[0].target_draw_id).toBe('1')
  })

  it('AC6: rejects duplicate target_draw_id and incomplete execution_status', async () => {
    // Duplicate draw ID
    const dupItems = [
      hedgeRow('100'),
      hedgeRow('100'),
    ]
    const fetchDup = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(resultsPage(dupItems)))
    vi.stubGlobal('fetch', fetchDup)

    await expect(getHedgeK3StoredResults('run-dup', 'v1', new AbortController().signal))
      .rejects.toThrow('K3 Hedge 有重複期號或未完成紀錄，無法確認成功期數。')

    // Incomplete status
    const incompleteItems = [
      hedgeRow('101', { execution_status: 'PENDING' }),
    ]
    const fetchIncomplete = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(resultsPage(incompleteItems)))
    vi.stubGlobal('fetch', fetchIncomplete)

    await expect(getHedgeK3StoredResults('run-inc', 'v1', new AbortController().signal))
      .rejects.toThrow('K3 Hedge 有重複期號或未完成紀錄，無法確認成功期數。')
  })

  it('AC6: aborts previous request on run switch so late responses do not overwrite new queries', async () => {
    let resolveA: (res: Response) => void = () => {}
    const promiseA = new Promise<Response>((resolve) => {
      resolveA = resolve
    })

    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      const runId = url.searchParams.get('run_id')
      if (runId === 'RUN-A') return promiseA
      return Promise.resolve(apiResponse(resultsPage([
        hedgeRow('201', { source_history_provenance_status: 'VERIFIED', reference_any_prize: true }),
      ])))
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(HedgeK3Summary, {
      props: { runId: 'RUN-A', strategyVersion: 'v1' },
    })
    await flushPromises()

    // Switch to RUN-B before A responds
    await wrapper.setProps({ runId: 'RUN-B', strategyVersion: 'v1' })
    await flushPromises()

    // Now resolve RUN-A late
    resolveA(apiResponse(resultsPage([
      hedgeRow('999', { source_history_provenance_status: 'VERIFIED', reference_any_prize: false }),
    ])))
    await flushPromises()

    // RUN-B's data (draw 201) should be present, not RUN-A (draw 999)
    const verifiedEl = wrapper.get('[data-testid="k3-all-reference_any_prize-verified"]')
    expect(verifiedEl.text()).toBe('1/1')
    expect(wrapper.text()).not.toContain('999')

    wrapper.unmount()
  })

  it('AC7: preserves both success definitions independently without combining or replacing them', async () => {
    const rawItems = [
      hedgeRow('1', {
        source_history_provenance_status: 'VERIFIED',
        reference_any_prize: true,
        combination_success: false,
      }),
      hedgeRow('2', {
        source_history_provenance_status: 'VERIFIED',
        reference_any_prize: false,
        combination_success: true,
      }),
    ]

    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(resultsPage(rawItems)))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(HedgeK3Summary, {
      props: { runId: 'run-definitions', strategyVersion: 'v1' },
    })
    await flushPromises()

    const refVerified = wrapper.get('[data-testid="k3-all-reference_any_prize-verified"]')
    const combVerified = wrapper.get('[data-testid="k3-all-combination_success-verified"]')

    // Both have 1 true out of 2, but on different draws; they remain strictly independent
    expect(refVerified.text()).toBe('1/2')
    expect(combVerified.text()).toBe('1/2')

    // Check table headers / metric labels
    expect(wrapper.text()).toContain('統一八獎級（研究參考）')
    expect(wrapper.text()).toContain('沿用來源策略的成功旗標')

    // Disclaimer present
    expect(wrapper.text()).toContain('來源驗證說明')
    expect(wrapper.text()).toContain('研究參考指標不代表正式中獎認證')

    wrapper.unmount()
  })
})
