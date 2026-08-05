// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import T539StrategyAnalysisPage from '../src/features/t539-strategy-analysis/T539StrategyAnalysisPage.vue'

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function makeRun(runId: string): Record<string, unknown> {
  return {
    run_id: runId,
    schema_version: 'v1',
    lottery_type: 'DAILY_539',
    source_endpoint: 'https://example.invalid/t539',
    source_sha256: 'a'.repeat(64),
    as_of_date: '2026-08-01',
    adapter_source_commit: 'b'.repeat(40),
    status: 'COMPLETE',
    strategy_count: 8,
    draw_count: 100,
    eligible_target_count: 90,
    ticket_count: 900,
    failure_count: 0,
    first_draw_id: 'draw-1',
    first_draw_date: '2020-01-01',
    last_draw_id: 'draw-100',
    last_draw_date: '2026-07-30',
  }
}

function runPage(runId = 'run-t539-1'): Record<string, unknown> {
  return { items: [makeRun(runId)], total_count: 1, limit: 25, offset: 0 }
}

function makeStrategy(runId: string, strategyId: string): Record<string, unknown> {
  return {
    run_id: runId,
    strategy_id: strategyId,
    strategy_version: 'v1',
    native_ticket_count: 1,
    min_history: 30,
    first_eligible_target_draw_id: 'draw-31',
    expected_target_draw_count: 90,
    processed_target_draw_count: 90,
    successful_target_draw_count: 90,
    failed_target_draw_count: 0,
    status: 'SUCCESS',
    ticket_count: 90,
    winning_ticket_count: 9,
    hit_distribution: [{ value: 3, count: 9 }],
    first_target_draw_date: '2020-02-01',
    last_target_draw_date: '2026-07-30',
  }
}

const EXECUTED_IDS = Array.from({ length: 8 }, (_value, index) => `t539_executed_${index + 1}`)
const BLOCKED_IDS = Array.from({ length: 7 }, (_value, index) => `t539_blocked_${index + 1}`)

function strategiesPage(runId = 'run-t539-1'): Record<string, unknown> {
  return {
    run_id: runId,
    items: EXECUTED_IDS.map((id) => makeStrategy(runId, id)),
    total_count: EXECUTED_IDS.length,
    limit: 100,
    offset: 0,
  }
}

function makeRanking(runId: string, strategyId: string, rank: number): Record<string, unknown> {
  return {
    run_id: runId,
    rank,
    strategy_id: strategyId,
    strategy_version: 'v1',
    native_ticket_count: 1,
    eligible_target_count: 90,
    winning_target_count: 9,
    winning_target_rate: 0.1,
    total_ticket_count: 90,
    winning_ticket_count: 9,
    ticket_winning_rate: 0.1,
    prize_tier_counts: [{ prize_tier: 'sixth', count: 9 }],
    highest_prize_tier_achieved: 'sixth',
    first_eligible_draw: 'draw-31',
    last_eligible_draw: 'draw-100',
    prize_rule_version: 'v1',
    prize_rule_provenance: 'fixture',
  }
}

function rankingsPage(runId = 'run-t539-1'): Record<string, unknown> {
  return {
    run_id: runId,
    items: EXECUTED_IDS.map((id, index) => makeRanking(runId, id, index + 1)),
    disclaimer: 'Historical winning rank describes past replay only and does not guarantee future winning.',
  }
}

function coverageLedger(runId = 'run-t539-1', coverageComplete = false): Record<string, unknown> {
  return {
    run_id: runId,
    executed: EXECUTED_IDS.map((id) => ({
      strategy_id: id,
      strategy_version: 'v1',
      native_ticket_count: 1,
      min_history: 30,
      selection_reason: 'wave1_fixed_scope',
    })),
    blocked: BLOCKED_IDS.map((id) => ({
      strategy_id: id,
      reason_code: 'INSUFFICIENT_HISTORY',
      reason: `${id} does not have enough history for replay.`,
    })),
    coverage_complete: coverageComplete,
  }
}

function metrics(runId = 'run-t539-1', strategyId: string | null = null): Record<string, unknown> {
  return {
    run_id: runId,
    strategy_id: strategyId,
    target_count: 90,
    ticket_count: 900,
    winning_ticket_count: 72,
    winning_target_count: 60,
    hit_distribution: [{ value: 3, count: 60 }],
    prize_tier_counts: [{ prize_tier: 'sixth', count: 60 }],
    first_target_draw_date: '2020-02-01',
    last_target_draw_date: '2026-07-30',
  }
}

function baseFetchMock(runId = 'run-t539-1', coverageComplete = false): ReturnType<typeof vi.fn<typeof fetch>> {
  return vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = String(input)
    if (url.includes('/strategies?')) return Promise.resolve(apiResponse(strategiesPage(runId)))
    if (url.includes('/rankings')) return Promise.resolve(apiResponse(rankingsPage(runId)))
    if (url.includes('/coverage')) return Promise.resolve(apiResponse(coverageLedger(runId, coverageComplete)))
    if (url.includes('/metrics')) {
      const parsed = new URL(url, 'http://localhost')
      const strategyId = parsed.searchParams.get('strategy_id')
      return Promise.resolve(apiResponse(metrics(runId, strategyId)))
    }
    if (url.includes('/t539-historical/runs?')) return Promise.resolve(apiResponse(runPage(runId)))
    throw new Error(`Unexpected fetch: ${url}`)
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('T539StrategyAnalysisPage', () => {
  it('renders all 8 ranked strategies, 7 blocked identities, the incomplete-coverage notice, and a screen-safe label', async () => {
    const fetchMock = baseFetchMock()
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(T539StrategyAnalysisPage)
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('#t539-analysis-title').exists()).toBe(true)
    expect(wrapper.text()).toContain('T539')
    expect(wrapper.text()).not.toContain('DAILY_539')

    const rankRows = wrapper.findAll('table')[0]?.findAll('tbody tr') ?? []
    expect(rankRows).toHaveLength(8)
    expect(rankRows[0]?.text()).toContain(EXECUTED_IDS[0])
    expect(rankRows[7]?.text()).toContain(EXECUTED_IDS[7])

    expect(wrapper.text()).toContain('8 executed')
    expect(wrapper.text()).toContain('7 blocked/deferred')
    expect(wrapper.find('[data-testid="t539-coverage-incomplete-notice"]').exists()).toBe(true)

    const blockedTable = wrapper
      .findAll('table')
      .find((table) => table.text().includes('Blocked / deferred identities'))
    expect(blockedTable).toBeDefined()
    expect(blockedTable?.findAll('tbody tr')).toHaveLength(7)
    for (const id of BLOCKED_IDS) {
      expect(blockedTable?.text()).toContain(id)
    }

    wrapper.unmount()
  })

  it('loads strategy-specific metrics when an executed strategy is selected', async () => {
    const fetchMock = baseFetchMock()
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(T539StrategyAnalysisPage)
    await flushPromises()
    await flushPromises()

    const selectButton = wrapper.get(`[data-testid="t539-select-strategy-${EXECUTED_IDS[0]}"]`)
    await selectButton.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(EXECUTED_IDS[0])
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes(`strategy_id=${EXECUTED_IDS[0]}`),
      ),
    ).toBe(true)

    wrapper.unmount()
  })

  it('clears stale selected-strategy metrics when the selected run changes', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/strategies?')) {
        const parsed = new URL(url, 'http://localhost')
        const runId = parsed.pathname.split('/')[5]
        return Promise.resolve(apiResponse(strategiesPage(runId)))
      }
      if (url.includes('/rankings')) {
        const parsed = new URL(url, 'http://localhost')
        const runId = parsed.pathname.split('/')[5]
        return Promise.resolve(apiResponse(rankingsPage(runId)))
      }
      if (url.includes('/coverage')) {
        const parsed = new URL(url, 'http://localhost')
        const runId = parsed.pathname.split('/')[5]
        return Promise.resolve(apiResponse(coverageLedger(runId)))
      }
      if (url.includes('/metrics')) {
        const parsed = new URL(url, 'http://localhost')
        const runId = parsed.pathname.split('/')[5]
        const strategyId = parsed.searchParams.get('strategy_id')
        return Promise.resolve(apiResponse(metrics(runId, strategyId)))
      }
      if (url.includes('/t539-historical/runs?')) {
        return Promise.resolve(
          apiResponse({ items: [makeRun('run-a'), makeRun('run-b')], total_count: 2, limit: 25, offset: 0 }),
        )
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(T539StrategyAnalysisPage)
    await flushPromises()
    await flushPromises()

    await wrapper.get(`[data-testid="t539-select-strategy-${EXECUTED_IDS[0]}"]`).trigger('click')
    await flushPromises()
    expect(wrapper.find('.panel[aria-live="polite"]').exists()).toBe(true)

    await wrapper.get('[data-testid="t539-run-select"]').setValue('run-b')
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('.panel[aria-live="polite"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows a not-configured message on a T539_HISTORICAL_NOT_CONFIGURED 503 response', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      apiResponse({ error_code: 'T539_HISTORICAL_NOT_CONFIGURED', message: 'not configured' }, 503),
    )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(T539StrategyAnalysisPage)
    await flushPromises()

    expect(wrapper.text()).toContain('not configured for this local runtime')
    wrapper.unmount()
  })

  it('surfaces a general-unavailable error with a working retry control', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      apiResponse({ error_code: 'T539_HISTORICAL_UNAVAILABLE', message: 'sanitized unavailable message' }, 503),
    )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(T539StrategyAnalysisPage)
    await flushPromises()

    expect(wrapper.text()).toContain('sanitized unavailable message')
    const retry = wrapper.get('[data-testid="t539-retry-runs"]')
    fetchMock.mockClear()
    await retry.trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('reports a malformed run page distinctly from a general error', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      apiResponse({ items: [{ run_id: 'incomplete' }], total_count: 1, limit: 25, offset: 0 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(T539StrategyAnalysisPage)
    await flushPromises()

    expect(wrapper.text()).toContain('unexpected response')
    wrapper.unmount()
  })

  it('shows an empty-state message when no run is available', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      apiResponse({ items: [], total_count: 0, limit: 25, offset: 0 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(T539StrategyAnalysisPage)
    await flushPromises()

    expect(wrapper.text()).toContain('No completed T539 analysis run is available.')
    wrapper.unmount()
  })
})
