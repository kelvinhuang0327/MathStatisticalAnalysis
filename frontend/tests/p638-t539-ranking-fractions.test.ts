// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import P638StrategyAnalysisPage from '../src/features/p638-strategy-analysis/P638StrategyAnalysisPage.vue'
import T539StrategyAnalysisPage from '../src/features/t539-strategy-analysis/T539StrategyAnalysisPage.vue'

vi.mock('../src/features/multiwindow-success/MultiWindowSuccessWindowsPanel.vue', () => ({
  default: {
    name: 'MultiWindowSuccessWindowsPanelStub',
    props: ['lottery', 'runId'],
    template: '<div />',
  },
}))

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function p638Ranking(
  strategyId: string,
  rank: number,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    run_id: 'run-p638-1',
    rank,
    strategy_id: strategyId,
    strategy_version: 'v1',
    native_ticket_count: 4,
    eligible_target_count: 90,
    winning_target_count: 9,
    winning_target_rate: 0.1004,
    total_complete_ticket_count: 180,
    winning_ticket_count: 27,
    ticket_winning_rate: 0.15,
    // A decoy field guards against substituting the T539 denominator.
    total_ticket_count: 999,
    prize_tier_counts: [{ prize_tier: 'sixth', count: 9 }],
    highest_prize_tier_achieved: 'sixth',
    first_eligible_draw: 'draw-1',
    last_eligible_draw: 'draw-90',
    prize_rule_version: 'v1',
    prize_rule_provenance: 'fixture',
    provenance: 'P638 Historical API fixture',
    ...overrides,
  }
}

function t539Ranking(
  strategyId: string,
  rank: number,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    run_id: 'run-t539-1',
    rank,
    strategy_id: strategyId,
    strategy_version: 'v1',
    native_ticket_count: 5,
    eligible_target_count: 90,
    winning_target_count: 9,
    winning_target_rate: 0.1,
    total_ticket_count: 270,
    winning_ticket_count: 27,
    ticket_winning_rate: 0.1,
    // A decoy field guards against substituting the P638 denominator.
    total_complete_ticket_count: 999,
    prize_tier_counts: [{ prize_tier: 'sixth', count: 9 }],
    highest_prize_tier_achieved: 'sixth',
    first_eligible_draw: 'draw-1',
    last_eligible_draw: 'draw-90',
    prize_rule_version: 'v1',
    prize_rule_provenance: 'fixture',
    ...overrides,
  }
}

function p638Fetch(rows: Record<string, unknown>[]): ReturnType<typeof vi.fn<typeof fetch>> {
  return vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = String(input)
    if (url.includes('/rankings')) {
      return Promise.resolve(apiResponse({ run_id: 'run-p638-1', items: rows }))
    }
    if (url.includes('/p638-historical/runs?')) {
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 25, offset: 0 }))
    }
    return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 10, offset: 0 }))
  })
}

function t539Fetch(rows: Record<string, unknown>[]): ReturnType<typeof vi.fn<typeof fetch>> {
  return vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = String(input)
    if (url.includes('/rankings')) {
      return Promise.resolve(
        apiResponse({
          run_id: 'run-t539-1',
          items: rows,
          disclaimer: 'Historical winning rank describes past replay only.',
        }),
      )
    }
    if (url.includes('/coverage')) {
      return Promise.resolve(
        apiResponse({ run_id: 'run-t539-1', executed: [], blocked: [], coverage_complete: true }),
      )
    }
    if (url.includes('/strategies?')) {
      return Promise.resolve(
        apiResponse({ run_id: 'run-t539-1', items: [], total_count: 0, limit: 100, offset: 0 }),
      )
    }
    if (url.includes('/metrics')) {
      return Promise.resolve(apiResponse({ message: 'metrics fixture unavailable' }, 503))
    }
    if (url.includes('/t539-historical/runs?')) {
      return Promise.resolve(
        apiResponse({
          items: [
            {
              run_id: 'run-t539-1',
              schema_version: 'v1',
              lottery_type: 'DAILY_539',
              source_endpoint: 'https://example.invalid/t539',
              source_sha256: 'a'.repeat(64),
              as_of_date: '2026-08-01',
              adapter_source_commit: 'b'.repeat(40),
              status: 'COMPLETE',
              strategy_count: 1,
              draw_count: 90,
              eligible_target_count: 90,
              ticket_count: 270,
              failure_count: 0,
              first_draw_id: 'draw-1',
              first_draw_date: '2026-01-01',
              last_draw_id: 'draw-90',
              last_draw_date: '2026-07-30',
            },
          ],
          total_count: 1,
          limit: 25,
          offset: 0,
        }),
      )
    }
    return Promise.resolve(apiResponse({ message: 'not found' }, 404))
  })
}

async function flushPage(): Promise<void> {
  await flushPromises()
  await flushPromises()
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('P638 and T539 ranking rate fractions', () => {
  it('uses P638 eligible-target and complete-ticket denominators while retaining source order and values', async () => {
    vi.stubGlobal(
      'fetch',
      p638Fetch([
        p638Ranking('p638-first', 7),
        p638Ranking('p638-second', 2, {
          winning_target_count: 3,
          winning_target_rate: 0.2,
          total_complete_ticket_count: 120,
          winning_ticket_count: 6,
          ticket_winning_rate: 0.5,
        }),
      ]),
    )

    const wrapper = mount(P638StrategyAnalysisPage)
    await flushPage()

    const rows = wrapper.get('section[aria-labelledby="p638-ranking-title"] tbody').findAll('tr')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.findAll('td')[0]?.text()).toBe('7')
    expect(rows[0]?.text()).toContain('p638-first')
    expect(rows[0]?.findAll('td')[2]?.text()).toBe('4')
    expect(rows[0]?.findAll('td')[5]?.text()).toContain('10.0%')
    expect(rows[0]?.findAll('td')[5]?.text()).toContain('9/90')
    expect(rows[0]?.findAll('td')[6]?.text()).toContain('15.0%')
    expect(rows[0]?.findAll('td')[6]?.text()).toContain('27/180')
    expect(rows[0]?.findAll('td')[6]?.text()).not.toContain('27/999')
    expect(rows[0]?.text()).toContain('sixth')

    expect(rows[1]?.findAll('td')[0]?.text()).toBe('2')
    expect(rows[1]?.text()).toContain('p638-second')
    expect(rows[1]?.findAll('td')[5]?.text()).toContain('20.0%')
    expect(rows[1]?.findAll('td')[5]?.text()).toContain('3/90')
    expect(rows[1]?.findAll('td')[5]?.text()).toContain('Source rate/count mismatch')
    expect(rows[1]?.findAll('td')[6]?.text()).toContain('50.0%')
    expect(rows[1]?.findAll('td')[6]?.text()).toContain('6/120')
    expect(rows[1]?.findAll('td')[6]?.text()).toContain('Source rate/count mismatch')

    wrapper.unmount()
  })

  it('uses T539 eligible-target and total-ticket denominators without changing ranking identity', async () => {
    vi.stubGlobal(
      'fetch',
      t539Fetch([
        t539Ranking('t539-first', 4),
        t539Ranking('t539-second', 1, {
          winning_target_count: 0,
          winning_target_rate: 0,
          winning_ticket_count: 0,
          ticket_winning_rate: 0,
        }),
        t539Ranking('t539-mismatch', 3, {
          winning_target_rate: 0.25,
          ticket_winning_rate: 0.2,
        }),
      ]),
    )

    const wrapper = mount(T539StrategyAnalysisPage)
    await flushPage()

    const rows = wrapper.get('section[aria-labelledby="t539-ranking-title"] tbody').findAll('tr')
    expect(rows).toHaveLength(3)
    expect(rows[0]?.findAll('td')[0]?.text()).toBe('4')
    expect(rows[0]?.text()).toContain('t539-first')
    expect(rows[0]?.findAll('td')[2]?.text()).toBe('5')
    expect(rows[0]?.findAll('td')[5]?.text()).toContain('10.0%')
    expect(rows[0]?.findAll('td')[5]?.text()).toContain('9/90')
    expect(rows[0]?.findAll('td')[6]?.text()).toContain('10.0%')
    expect(rows[0]?.findAll('td')[6]?.text()).toContain('27/270')
    expect(rows[0]?.findAll('td')[6]?.text()).not.toContain('27/999')

    expect(rows[1]?.findAll('td')[0]?.text()).toBe('1')
    expect(rows[1]?.text()).toContain('t539-second')
    expect(rows[1]?.findAll('td')[5]?.text()).toContain('0.0%')
    expect(rows[1]?.findAll('td')[5]?.text()).toContain('0/90')
    expect(rows[1]?.findAll('td')[6]?.text()).toContain('0.0%')
    expect(rows[1]?.findAll('td')[6]?.text()).toContain('0/270')

    expect(rows[2]?.findAll('td')[0]?.text()).toBe('3')
    expect(rows[2]?.text()).toContain('t539-mismatch')
    expect(rows[2]?.findAll('td')[5]?.text()).toContain('25.0%')
    expect(rows[2]?.findAll('td')[5]?.text()).toContain('9/90')
    expect(rows[2]?.findAll('td')[5]?.text()).toContain('Source rate/count mismatch')
    expect(rows[2]?.findAll('td')[6]?.text()).toContain('20.0%')
    expect(rows[2]?.findAll('td')[6]?.text()).toContain('27/270')
    expect(rows[2]?.findAll('td')[6]?.text()).toContain('Source rate/count mismatch')

    wrapper.unmount()
  })

  it('shows zero-denominator and invalid count/rate states without inventing percentages', async () => {
    vi.stubGlobal(
      'fetch',
      p638Fetch([
        p638Ranking('zero', 1, {
          winning_target_count: 0,
          winning_target_rate: 0,
          winning_ticket_count: 0,
          ticket_winning_rate: 0.5,
          total_complete_ticket_count: 0,
        }),
        p638Ranking('invalid', 2, {
          winning_target_count: null,
          winning_target_rate: Number.NaN,
          winning_ticket_count: 2,
          ticket_winning_rate: Number.POSITIVE_INFINITY,
          total_complete_ticket_count: null,
        }),
      ]),
    )

    const wrapper = mount(P638StrategyAnalysisPage)
    await flushPage()

    const rows = wrapper.get('section[aria-labelledby="p638-ranking-title"] tbody').findAll('tr')
    expect(rows[0]?.findAll('td')[5]?.text()).toContain('0.0%')
    expect(rows[0]?.findAll('td')[5]?.text()).toContain('0/90')
    expect(rows[0]?.findAll('td')[6]?.text()).toContain('50.0%')
    expect(rows[0]?.findAll('td')[6]?.text()).toContain('0/0')
    expect(rows[0]?.findAll('td')[6]?.text()).toContain('denominator is zero')

    expect(rows[1]?.findAll('td')[5]?.text()).toContain('Unavailable')
    expect(rows[1]?.findAll('td')[5]?.text()).toContain('invalid count data')
    expect(rows[1]?.findAll('td')[6]?.text()).toContain('Unavailable')
    expect(rows[1]?.findAll('td')[6]?.text()).toContain('invalid count data')
    expect(wrapper.text()).not.toMatch(/NaN|Infinity/)

    wrapper.unmount()
  })

  it('marks T539 denominator-zero data unavailable while preserving valid zero-over-positive counts', async () => {
    vi.stubGlobal(
      'fetch',
      t539Fetch([
        t539Ranking('t539-zero', 1, {
          winning_target_count: 0,
          winning_target_rate: 0,
          winning_ticket_count: 0,
          ticket_winning_rate: 0,
        }),
        t539Ranking('t539-unavailable', 2, {
          eligible_target_count: 0,
          winning_target_count: 0,
          winning_target_rate: 0.25,
          total_ticket_count: 0,
          winning_ticket_count: 0,
          ticket_winning_rate: 0,
        }),
      ]),
    )

    const wrapper = mount(T539StrategyAnalysisPage)
    await flushPage()

    const rows = wrapper.get('section[aria-labelledby="t539-ranking-title"] tbody').findAll('tr')
    expect(rows[0]?.findAll('td')[5]?.text()).toContain('0.0%')
    expect(rows[0]?.findAll('td')[5]?.text()).toContain('0/90')
    expect(rows[0]?.findAll('td')[6]?.text()).toContain('0/270')
    expect(rows[1]?.findAll('td')[5]?.text()).toContain('25.0%')
    expect(rows[1]?.findAll('td')[5]?.text()).toContain('0/0')
    expect(rows[1]?.findAll('td')[5]?.text()).toContain('denominator is zero')
    expect(rows[1]?.findAll('td')[6]?.text()).toContain('0.0%')
    expect(rows[1]?.findAll('td')[6]?.text()).toContain('0/0')
    expect(rows[1]?.findAll('td')[6]?.text()).toContain('denominator is zero')
    expect(wrapper.text()).not.toMatch(/NaN|Infinity/)

    wrapper.unmount()
  })

  it('keeps a null source rate in the API-unavailable state instead of rendering a percentage', async () => {
    vi.stubGlobal(
      'fetch',
      t539Fetch([t539Ranking('t539-null-rate', 1, { winning_target_rate: null })]),
    )

    const wrapper = mount(T539StrategyAnalysisPage)
    await flushPage()

    const ranking = wrapper.get('section[aria-labelledby="t539-ranking-title"]')
    expect(ranking.text()).toContain('unexpected response')
    expect(ranking.find('table').exists()).toBe(false)
    expect(ranking.text()).not.toMatch(/NaN|Infinity|0\.0%/)

    wrapper.unmount()
  })
})
