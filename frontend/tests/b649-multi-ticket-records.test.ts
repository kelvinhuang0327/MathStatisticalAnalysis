// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import B649MultiTicketRecordsPage from '../src/features/b649-multi-ticket-records/B649MultiTicketRecordsPage.vue'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

const DISCLAIMER =
  '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。'

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function summary(recordsAvailable = true) {
  return {
    progress: {
      total_strategy_count: 221,
      reproduced_count: 135,
      backtested_count: 135,
      closed_count: 74,
      duplicate_alias_count: 12,
      owner_decision_required_count: 0,
      uncompleted_count: 0,
    },
    prefix_counts: [5, 10, 15, 20],
    windows: ['FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50'],
    success_criteria: [
      'M3_PLUS',
      'M4_PLUS',
      'M5_PLUS',
      'M6',
      'M2_PLUS_SPECIAL',
      'M3_PLUS_SPECIAL',
      'M4_PLUS_SPECIAL',
      'M5_PLUS_SPECIAL',
    ],
    primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
    method_families: ['graph', 'statistical'],
    reproduction_statuses: [
      'BACKTESTED',
      'CLOSED_UNEXECUTABLE',
      'DUPLICATE_ALIAS',
    ],
    catalog_sha256: 'c'.repeat(64),
    records_available: recordsAvailable,
    projection_sha256: recordsAvailable ? 'd'.repeat(64) : null,
    source_report_count: recordsAvailable ? 53 : null,
    research_disclaimer: DISCLAIMER,
  }
}

function record(strategyId = 'legacy_strategy_a') {
  return {
    strategy_id: strategyId,
    strategy_version: 'legacy-source-v1',
    legacy_method_id: 'tools/legacy_method.py',
    source_path: 'tools/legacy_method.py',
    method_family: 'statistical',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: 10,
    window: 'RECENT_300',
    criterion: 'M4_PLUS',
    rank: 7,
    official_rank: 5,
    official_any_prize_count: 12,
    official_any_prize_rate: '0.040000000000000000',
    official_random_baseline_probability: '0.010000000000000000',
    official_random_baseline_delta: '0.030000000000000000',
    unranked_reason: null,
    success_count: 9,
    effective_backtest_draw_count: 300,
    successful_execution_count: 300,
    historical_success_rate: '0.030000000000000000',
    random_baseline_success_rate: '0.020000000000000000',
    random_baseline_rate_difference: '0.010000000000000000',
    coverage: '1.000000000000000000',
    window_available_draws: 300,
    window_requested_draws: 300,
    window_complete: true,
    official_prize_counts: {
      first: 0,
      second: 1,
      third: 2,
      fourth: 3,
      fifth: 4,
      sixth: 5,
      seventh: 6,
      general: 7,
    },
    no_prize_count: 2972,
    report_sha256: 'a'.repeat(64),
    report_file_sha256: 'b'.repeat(64),
    catalog_sha256: 'c'.repeat(64),
  }
}

function page(items = [record()], total = items.length, offset = 0) {
  return {
    items,
    total,
    limit: 25,
    offset,
    prefix_count: 10,
    window: 'RECENT_300',
    criterion: 'M4_PLUS',
    research_disclaimer: DISCLAIMER,
  }
}

async function selectRequiredConditions(
  wrapper: ReturnType<typeof mount>,
): Promise<void> {
  await wrapper.get('select[name="prefix-count"]').setValue('10')
  await wrapper.get('select[name="history-window"]').setValue('RECENT_300')
  await wrapper.get('select[name="success-criterion"]').setValue('M4_PLUS')
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('B649MultiTicketRecordsPage', () => {
  it('shows the complete formal progress but never auto-queries or chooses a winner', async () => {
    fetchMock.mockResolvedValue(apiResponse(summary()))
    const wrapper = mount(B649MultiTicketRecordsPage)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      '/api/v1/b649-multi-ticket-records/summary',
    )
    expect(wrapper.text()).toContain('全部方法221')
    expect(wrapper.text()).toContain('已復現並回測135')
    expect(wrapper.text()).toContain('正式不可執行74')
    expect(wrapper.text()).toContain('重複別名12')
    expect(wrapper.text()).toContain(DISCLAIMER)
    expect(wrapper.text()).toContain('不會自動選擇排名、最新資料或最佳策略')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('offers every closed condition and queries only after all three explicit selections', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(summary()))
      .mockResolvedValueOnce(apiResponse(page()))
    const wrapper = mount(B649MultiTicketRecordsPage)
    await flushPromises()

    expect(
      wrapper.get('select[name="prefix-count"]').findAll('option').map((option) => option.text()),
    ).toEqual(['請選擇', '5 注', '10 注', '15 注', '20 注'])
    expect(
      wrapper.get('select[name="history-window"]').findAll('option').map((option) => option.text()),
    ).toEqual(['請選擇', 'FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50'])
    expect(
      wrapper
        .get('select[name="success-criterion"]')
        .findAll('option')
        .map((option) => option.text()),
    ).toEqual([
      '請選擇',
      'M3_PLUS',
      'M4_PLUS',
      'M5_PLUS',
      'M6',
      'M2_PLUS_SPECIAL',
      'M3_PLUS_SPECIAL',
      'M4_PLUS_SPECIAL',
      'M5_PLUS_SPECIAL',
    ])

    await selectRequiredConditions(wrapper)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await wrapper.get('form.records-query').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    const request = new URL(String(fetchMock.mock.calls[1]?.[0]), 'http://localhost')
    expect(Object.fromEntries(request.searchParams)).toMatchObject({
      prefix_count: '10',
      window: 'RECENT_300',
      criterion: 'M4_PLUS',
      limit: '25',
      offset: '0',
    })
    expect(wrapper.text()).toContain('legacy_strategy_a')
    expect(wrapper.text()).toContain('9 / 300')
    expect(wrapper.text()).toContain('3.000000%')
    expect(wrapper.text()).toContain('+1.000000 pp')
    expect(wrapper.text()).toContain('2972')
    expect(wrapper.get('table').attributes()).toBeDefined()
    expect(wrapper.get('.records-table-scroll').attributes('tabindex')).toBe('0')
    wrapper.unmount()
  })

  it('fails closed when the pinned projection is unavailable and can retry availability', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(summary(false)))
      .mockResolvedValueOnce(apiResponse(summary(true)))
    const wrapper = mount(B649MultiTicketRecordsPage)
    await flushPromises()

    expect(wrapper.text()).toContain('聚合歷史紀錄目前不可用')
    expect(wrapper.text()).toContain('查詢維持關閉')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()

    await wrapper.get('.records-state--warning button').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('尚未送出查詢')
    wrapper.unmount()
  })

  it('aborts and ignores a stale query when a newer explicit query starts', async () => {
    let resolveFirst!: (response: Response) => void
    let resolveSecond!: (response: Response) => void
    const first = new Promise<Response>((resolve) => {
      resolveFirst = resolve
    })
    const second = new Promise<Response>((resolve) => {
      resolveSecond = resolve
    })
    fetchMock
      .mockResolvedValueOnce(apiResponse(summary()))
      .mockReturnValueOnce(first)
      .mockReturnValueOnce(second)
    const wrapper = mount(B649MultiTicketRecordsPage)
    await flushPromises()
    await selectRequiredConditions(wrapper)

    await wrapper.get('form.records-query').trigger('submit')
    await wrapper.get('input[name="strategy-search"]').setValue('new')
    await wrapper.get('form.records-query').trigger('submit')
    const firstSignal = fetchMock.mock.calls[1]?.[1]?.signal
    expect(firstSignal?.aborted).toBe(true)

    resolveSecond(apiResponse(page([record('new_result')])))
    await flushPromises()
    resolveFirst(apiResponse(page([record('stale_result')])))
    await flushPromises()

    expect(wrapper.text()).toContain('new_result')
    expect(wrapper.text()).not.toContain('stale_result')
    wrapper.unmount()
  })
})
