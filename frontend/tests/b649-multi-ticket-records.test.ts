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
    expect(wrapper.text()).toContain('All Methods221')
    expect(wrapper.text()).toContain('Reproduced & Backtested135')
    expect(wrapper.text()).toContain('Formally Unexecutable74')
    expect(wrapper.text()).toContain('Duplicate Alias12')
    expect(wrapper.text()).toContain(
      'Historical success rates, rankings, and random baseline differences',
    )
    expect(wrapper.text()).toContain(
      'does not automatically select rankings, latest data, or top strategies',
    )
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
    ).toEqual(['Select ticket count', '5 Tickets', '10 Tickets', '15 Tickets', '20 Tickets'])
    expect(
      wrapper.get('select[name="history-window"]').findAll('option').map((option) => option.text()),
    ).toEqual(['Select window', 'FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50'])
    expect(
      wrapper
        .get('select[name="success-criterion"]')
        .findAll('option')
        .map((option) => option.text()),
    ).toEqual([
      'Select criterion',
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
    expect(wrapper.text()).toContain('3%')
    expect(wrapper.text()).toContain('+1 pp')
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

    expect(wrapper.text()).toContain('Aggregate historical records are currently unavailable')
    expect(wrapper.text()).toContain('query remains disabled')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()

    await wrapper.get('.records-state--warning button').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('No query submitted yet')
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

  it('uses raw execution counts and the source rates for each distinct success event', async () => {
    const expected = {
      ...record('nine-of-forty-eight'),
      official_any_prize_count: 3,
      official_any_prize_rate: '0.062500000000000000',
      success_count: 9,
      effective_backtest_draw_count: 16,
      successful_execution_count: 48,
      historical_success_rate: '0.187500000000000000',
    }
    const sourceRate = {
      ...record('source-rates-are-authoritative'),
      official_any_prize_count: 2,
      official_any_prize_rate: '0.050000000000000000',
      success_count: 9,
      effective_backtest_draw_count: 16,
      successful_execution_count: 48,
      historical_success_rate: '0.125000000000000000',
    }
    fetchMock
      .mockResolvedValueOnce(apiResponse(summary()))
      .mockResolvedValueOnce(apiResponse(page([expected, sourceRate])))
    const wrapper = mount(B649MultiTicketRecordsPage)
    await flushPromises()
    await selectRequiredConditions(wrapper)
    await wrapper.get('form.records-query').trigger('submit')
    await flushPromises()

    const rows = wrapper.get('tbody').findAll('tr')
    const expectedCells = rows[0]!.findAll('td').map((cell) => cell.text().trim())
    const sourceCells = rows[1]!.findAll('td').map((cell) => cell.text().trim())
    expect(expectedCells[5]).toBe('3 / 48')
    expect(expectedCells[6]).toBe('6.25%')
    expect(expectedCells[10]).toBe('9 / 48')
    expect(expectedCells[11]).toBe('18.75%')
    expect(expectedCells[10]).not.toBe('9 / 16')
    expect(sourceCells[6]).toBe('5%')
    expect(sourceCells[11]).toBe('12.5%')
    wrapper.unmount()
  })

  it('distinguishes zero observations, observed zero success, and null metrics', async () => {
    const zeroZero = {
      ...record('zero-of-zero'),
      official_any_prize_count: 0,
      official_any_prize_rate: '0.000000000000000000',
      success_count: 0,
      effective_backtest_draw_count: 1,
      successful_execution_count: 0,
      historical_success_rate: '0.000000000000000000',
      official_random_baseline_delta: '0.100000000000000000',
      random_baseline_rate_difference: '0.100000000000000000',
    }
    const zeroObserved = {
      ...record('zero-of-twelve'),
      official_any_prize_count: 0,
      official_any_prize_rate: '0.000000000000000000',
      success_count: 0,
      effective_backtest_draw_count: 1,
      successful_execution_count: 12,
      historical_success_rate: '0.000000000000000000',
    }
    const nullNumerator = {
      ...record('missing-numerator'),
      official_any_prize_count: null,
      official_any_prize_rate: null,
      success_count: null,
      effective_backtest_draw_count: null,
      successful_execution_count: 12,
      historical_success_rate: null,
    }
    const nullDenominator = {
      ...record('missing-denominator'),
      official_any_prize_count: 3,
      official_any_prize_rate: '0.250000000000000000',
      success_count: 9,
      effective_backtest_draw_count: 16,
      successful_execution_count: null,
      historical_success_rate: '0.500000000000000000',
    }
    fetchMock
      .mockResolvedValueOnce(apiResponse(summary()))
      .mockResolvedValueOnce(
        apiResponse(page([zeroZero, zeroObserved, nullNumerator, nullDenominator])),
      )
    const wrapper = mount(B649MultiTicketRecordsPage)
    await flushPromises()
    await selectRequiredConditions(wrapper)
    await wrapper.get('form.records-query').trigger('submit')
    await flushPromises()

    const rows = wrapper.get('tbody').findAll('tr')
    const cells = rows.map((row) => row.findAll('td').map((cell) => cell.text().trim()))
    expect(cells[0]![5]).toBe('0 / 0')
    expect(cells[0]![6]).toBe('—')
    expect(cells[0]![8]).toBe('—')
    expect(cells[0]![10]).toBe('0 / 0')
    expect(cells[0]![11]).toBe('—')
    expect(cells[0]![13]).toBe('—')
    expect(cells[1]![5]).toBe('0 / 12')
    expect(cells[1]![6]).toBe('0%')
    expect(cells[1]![10]).toBe('0 / 12')
    expect(cells[1]![11]).toBe('0%')
    expect(cells[2]![5]).toBe('—')
    expect(cells[2]![10]).toBe('—')
    expect(cells[3]![5]).toBe('—')
    expect(cells[3]![6]).toBe('—')
    expect(cells[3]![10]).toBe('—')
    expect(cells[3]![11]).toBe('—')
    wrapper.unmount()
  })

  it('preserves positive, negative, and zero deltas and all strategy identities', async () => {
    const positive = {
      ...record('positive-delta'),
      official_random_baseline_delta: '0.010000000000000000',
      random_baseline_rate_difference: '0.020000000000000000',
    }
    const negative = {
      ...record('negative-delta'),
      official_random_baseline_delta: '-0.010000000000000000',
      random_baseline_rate_difference: '-0.020000000000000000',
    }
    const zero = {
      ...record('zero-delta'),
      official_random_baseline_delta: '0.000000000000000000',
      random_baseline_rate_difference: '0.000000000000000000',
    }
    const tinyPositive = {
      ...record('tiny-positive-delta'),
      official_random_baseline_delta: '0.000000000000000001',
      random_baseline_rate_difference: '0.000000000000000001',
    }
    const tinyNegative = {
      ...record('tiny-negative-delta'),
      official_random_baseline_delta: '-0.000000000000000001',
      random_baseline_rate_difference: '-0.000000000000000001',
    }
    const closed = {
      ...record('closed-unexecutable'),
      reproduction_status: 'CLOSED_UNEXECUTABLE',
      official_rank: null,
      rank: null,
      official_any_prize_count: null,
      official_any_prize_rate: null,
      successful_execution_count: null,
      success_count: null,
      effective_backtest_draw_count: null,
      historical_success_rate: null,
      unranked_reason: 'CLOSED_BY_OWNER',
    }
    const alias = {
      ...record('duplicate-alias'),
      reproduction_status: 'DUPLICATE_ALIAS',
      duplicate_alias_target: 'backtested-target',
      official_rank: null,
      rank: null,
      official_any_prize_count: null,
      official_any_prize_rate: null,
      successful_execution_count: null,
      success_count: null,
      effective_backtest_draw_count: null,
      historical_success_rate: null,
      unranked_reason: 'DUPLICATE_OF_BACKTESTED_TARGET',
    }
    fetchMock
      .mockResolvedValueOnce(apiResponse(summary()))
      .mockResolvedValueOnce(apiResponse(page([positive, negative, zero, tinyPositive, tinyNegative, closed, alias])))
    const wrapper = mount(B649MultiTicketRecordsPage)
    await flushPromises()
    await selectRequiredConditions(wrapper)
    await wrapper.get('form.records-query').trigger('submit')
    await flushPromises()

    const rows = wrapper.get('tbody').findAll('tr')
    const cells = rows.map((row) => row.findAll('td').map((cell) => cell.text().trim()))
    expect(cells[0]![8]).toBe('+1 pp')
    expect(cells[0]![13]).toBe('+2 pp')
    expect(cells[1]![8]).toBe('-1 pp')
    expect(cells[1]![13]).toBe('-2 pp')
    expect(cells[2]![8]).toBe('0 pp')
    expect(cells[2]![13]).toBe('0 pp')
    expect(cells[3]![8]).toBe('+0.0000000000000001 pp')
    expect(cells[3]![13]).toBe('+0.0000000000000001 pp')
    expect(cells[4]![8]).toBe('-0.0000000000000001 pp')
    expect(cells[4]![13]).toBe('-0.0000000000000001 pp')
    expect(rows).toHaveLength(7)
    expect(rows[5]!.text()).toContain('CLOSED_UNEXECUTABLE')
    expect(rows[5]!.text()).toContain('CLOSED_BY_OWNER')
    expect(cells[5]![6]).toBe('—')
    expect(cells[5]![11]).toBe('—')
    expect(rows[6]!.text()).toContain('DUPLICATE_ALIAS')
    expect(rows[6]!.text()).toContain('backtested-target')
    expect(rows[6]!.text()).toContain('DUPLICATE_OF_BACKTESTED_TARGET')
    expect(cells[6]![6]).toBe('—')
    expect(cells[6]![11]).toBe('—')
    wrapper.unmount()
  })

  it('keeps an ordinary empty result separate from an HTTP 503 unavailable response', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(summary()))
      .mockResolvedValueOnce(apiResponse(page([], 0)))
      .mockResolvedValueOnce(
        apiResponse(
          {
            error_code: 'B649_MULTI_TICKET_RECORDS_UNAVAILABLE',
            message: 'projection is unavailable',
          },
          503,
        ),
      )
    const wrapper = mount(B649MultiTicketRecordsPage)
    await flushPromises()
    await selectRequiredConditions(wrapper)
    await wrapper.get('form.records-query').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('No matching strategies found')
    expect(wrapper.text()).not.toContain('Aggregate historical records are currently unavailable')

    await wrapper.get('form.records-query').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Aggregate historical records are currently unavailable')
    expect(wrapper.text()).toContain('projection is unavailable')
    wrapper.unmount()
  })

  it('keeps explicit K, window, and criterion selections through next and previous pages', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(summary()))
      .mockResolvedValueOnce(apiResponse(page([record('first-page')], 26, 0)))
      .mockResolvedValueOnce(apiResponse(page([record('second-page')], 26, 25)))
      .mockResolvedValueOnce(apiResponse(page([record('first-page-again')], 26, 0)))
    const wrapper = mount(B649MultiTicketRecordsPage)
    await flushPromises()
    await selectRequiredConditions(wrapper)
    await wrapper.get('form.records-query').trigger('submit')
    await flushPromises()

    await wrapper.get('.records-pagination button:last-child').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('second-page')
    const nextRequest = new URL(String(fetchMock.mock.calls[2]?.[0]), 'http://localhost')
    expect(Object.fromEntries(nextRequest.searchParams)).toMatchObject({
      prefix_count: '10',
      window: 'RECENT_300',
      criterion: 'M4_PLUS',
      offset: '25',
    })

    await wrapper.get('.records-pagination button:first-child').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('first-page-again')
    const previousRequest = new URL(String(fetchMock.mock.calls[3]?.[0]), 'http://localhost')
    expect(Object.fromEntries(previousRequest.searchParams)).toMatchObject({
      prefix_count: '10',
      window: 'RECENT_300',
      criterion: 'M4_PLUS',
      offset: '0',
    })
    wrapper.unmount()
  })
})
