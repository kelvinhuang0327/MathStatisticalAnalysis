// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import B649OwnerRankingPage from '../src/features/b649-owner-ranking/B649OwnerRankingPage.vue'

const DISCLAIMER =
  '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

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
    method_families: ['frequency', 'statistical'],
    reproduction_statuses: ['BACKTESTED', 'CLOSED_UNEXECUTABLE', 'DUPLICATE_ALIAS'],
    catalog_sha256: 'c'.repeat(64),
    records_available: recordsAvailable,
    projection_sha256: recordsAvailable ? 'd'.repeat(64) : null,
    source_report_count: recordsAvailable ? 17 : null,
    metrics_available_strategy_count: recordsAvailable ? 133 : null,
    metrics_unavailable_strategy_count: recordsAvailable ? 2 : null,
    research_disclaimer: DISCLAIMER,
  }
}

function record(
  prefixCount: number,
  window: string,
  strategyToken: string,
  options: {
    rank?: number | null
    rate?: string
    coverage?: string
    observations?: number
    delta?: string
  } = {},
) {
  return {
    strategy_id: `legacy_biglotto__${strategyToken}__fixture`,
    strategy_version: 'r2-fixture',
    legacy_method_id: strategyToken,
    source_path: `fixture/${strategyToken}.json`,
    method_family: strategyToken.includes('6bet') ? 'frequency' : 'statistical',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: prefixCount,
    window,
    criterion: 'M3_PLUS',
    rank: options.rank ?? null,
    official_rank: options.rank ?? null,
    official_any_prize_count: options.observations ?? 0,
    official_any_prize_rate: options.rate ?? '0.100000000000000000',
    official_random_baseline_probability: '0.145470735730114392',
    official_random_baseline_delta: options.delta ?? '-0.045470735730114392',
    unranked_reason: options.rank === null ? 'NO_SUCCESSFUL_EXECUTIONS_IN_WINDOW' : null,
    success_count: options.observations ?? 0,
    effective_backtest_draw_count: options.observations ?? 0,
    successful_execution_count: options.observations ?? 0,
    historical_success_rate: '0.100000000000000000',
    random_baseline_success_rate: '0.100000000000000000',
    random_baseline_rate_difference: '0.000000000000000000',
    coverage: options.coverage ?? '1.000000000000000000',
    window_available_draws: window === 'FULL' ? 2149 : Number(window.replace('RECENT_', '')),
    window_requested_draws: window === 'FULL' ? 2149 : Number(window.replace('RECENT_', '')),
    window_complete: true,
    official_prize_counts: {
      first: 0,
      second: 0,
      third: 0,
      fourth: 0,
      fifth: 0,
      sixth: 0,
      seventh: options.observations ?? 0,
      general: 0,
    },
    no_prize_count: 0,
    report_sha256: 'a'.repeat(64),
    report_file_sha256: 'b'.repeat(64),
    catalog_sha256: 'c'.repeat(64),
  }
}

function rowsFor(url: URL) {
  const prefixCount = Number(url.searchParams.get('prefix_count'))
  const window = url.searchParams.get('window') ?? 'FULL'
  const rows = [record(prefixCount, window, `fixture_${prefixCount}_${window}`, { rank: 99 })]

  if (window === 'FULL') {
    rows.push(
      record(prefixCount, window, 'quick_ml_predict', {
        rank: 1,
        rate: '0.500000000000000000',
        coverage: '0.001861330851558865',
        observations: 4,
        delta: '0.354529264269885608',
      }),
      record(prefixCount, window, 'backtest_biglotto_6bet_ewma', {
        rank: prefixCount === 5 ? 23 : 2,
        rate: prefixCount === 5 ? '0.151360000000000000' : '0.487430000000000000',
        coverage: '0.906930000000000000',
        observations: 1949,
        delta: '0.020650000000000000',
      }),
    )
  }

  if (window === 'RECENT_50') {
    if (prefixCount === 5) {
      rows.push(
        record(prefixCount, window, 'big_lotto_exhaustive_audit', {
          rank: 1,
          rate: '0.300000000000000000',
          observations: 50,
          delta: '0.154500000000000000',
        }),
      )
    } else if (prefixCount === 10 || prefixCount === 15) {
      rows.push(
        record(prefixCount, window, 'research_cluster_enhancements', {
          rank: 1,
          rate: '0.500000000000000000',
          coverage: '0.040000000000000000',
          observations: 2,
          delta: '0.100000000000000000',
        }),
        record(prefixCount, window, 'backtest_biglotto_coldpool_15', {
          rank: 2,
          rate: '0.480000000000000000',
          observations: 50,
          delta: '0.104000000000000000',
        }),
      )
    } else {
      rows.push(
        record(prefixCount, window, 'covering_strategy_research', {
          rank: 1,
          rate: '0.560000000000000000',
          observations: 50,
          delta: '0.093200000000000000',
        }),
      )
    }
    rows.push(
      record(prefixCount, window, 'quick_ml_predict', {
        rank: null,
        rate: '0.000000000000000000',
        coverage: '0.000000000000000000',
        observations: 0,
        delta: '-0.145470735730114392',
      }),
    )
  }

  return {
    items: rows,
    total: rows.length,
    limit: 100,
    offset: 0,
    prefix_count: prefixCount,
    window,
    criterion: 'M3_PLUS',
    research_disclaimer: DISCLAIMER,
  }
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname.endsWith('/summary')) return Promise.resolve(apiResponse(summary()))
    return Promise.resolve(apiResponse(rowsFor(url)))
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('B649OwnerRankingPage', () => {
  it('shows R2 ticket separation, evidence warnings, baseline, and matrix fields', async () => {
    const wrapper = mount(B649OwnerRankingPage)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(17)
    expect(wrapper.text()).toContain('B649 Owner Ranking')
    expect(wrapper.text()).toContain('HIGH_RANK_LOW_COVERAGE')
    expect(wrapper.text()).toContain('quick_ml_predict')
    expect(wrapper.text()).toContain('4 Obs.')
    expect(wrapper.text()).toContain('0.19% cov')
    expect(wrapper.text()).toContain('6bet_ewma')
    expect(wrapper.text()).toContain('20 注')
    expect(wrapper.text()).toContain('2/20')
    expect(wrapper.get('[aria-label="B649 Owner Decision Matrix table"]').attributes('tabindex')).toBe('0')
    expect(wrapper.text()).toContain('coverage、Obs.、delta 不隱藏')
    wrapper.unmount()
  })

  it('switches ticket count and ranking window without creating a cross-ticket ranking', async () => {
    const wrapper = mount(B649OwnerRankingPage)
    await flushPromises()

    const ticketTabs = wrapper.get('[role="tablist"]').findAll('button')
    await ticketTabs[3]?.trigger('click')
    expect(wrapper.text()).toContain('Current view20 注')
    expect(wrapper.text()).toContain('covering_strategy_research')
    expect(wrapper.text()).toContain('10/20')

    const windowTabs = wrapper.get('.window-tabs').findAll('button')
    await windowTabs[3]?.trigger('click')
    expect(wrapper.text()).toContain('50 · 短期觀察')
    expect(wrapper.text()).toContain('RECENT_MOVER')
    expect(wrapper.text()).toContain('不存在跨票數 overall ranking')
    wrapper.unmount()
  })

  it('uses the R2 portfolio snapshot instead of a mismatched API strategy id', async () => {
    const wrapper = mount(B649OwnerRankingPage)
    await flushPromises()

    const ticketTabs = wrapper.get('[role="tablist"]').findAll('button')
    await ticketTabs[2]?.trigger('click')
    const row15 = wrapper
      .get('[aria-label="B649 Owner Decision Matrix table"]')
      .findAll('tbody tr')
      .find((row) => row.text().includes('portfolio_optimizer'))
    expect(row15?.text()).toContain('#14/#6/#3/#9')
    expect(row15?.text()).toContain('90.69% / 100.00% / 100.00% / 100.00%')

    await ticketTabs[3]?.trigger('click')
    const row20 = wrapper
      .get('[aria-label="B649 Owner Decision Matrix table"]')
      .findAll('tbody tr')
      .find((row) => row.text().includes('portfolio_optimizer'))
    expect(row20?.text()).toContain('#17/#6/#2/#9')
    expect(row20?.text()).toContain('90.69% / 100.00% / 100.00% / 100.00%')
    wrapper.unmount()
  })

  it('fails closed when the checksum-pinned ranking projection is unavailable', async () => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValue(apiResponse(summary(false)))
    const wrapper = mount(B649OwnerRankingPage)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('B649 R2 ranking projection 無法載入')
    expect(wrapper.text()).toContain('checksum-pinned B649 ranking projection is unavailable')
    wrapper.unmount()
  })
})
