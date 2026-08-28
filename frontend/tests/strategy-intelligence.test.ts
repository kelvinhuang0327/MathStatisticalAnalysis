// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { StrategyOverviewResponse } from '../src/api/strategies'
import type { StrategyEvidenceResponse } from '../src/api/strategyEvidence'
import StrategyIntelligencePage from '../src/features/strategy-intelligence/StrategyIntelligencePage.vue'

const sampleStrategy = {
  strategy_id: 'b649_social_wisdom_anti_popularity',
  display_name: 'B649 Social Wisdom Anti-Popularity',
  version: 'v0.1',
  supported_lottery_types: ['BIG_LOTTO'],
  minimum_history: 1,
  lifecycle_status: 'OBSERVATION',
  executable: false,
  provenance: [
    'legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f',
    'migration_task:P600B_R2',
  ],
} as const

const sampleOnlineStrategy = {
  strategy_id: 't539_frequency_zone_split',
  display_name: 'T539 Frequency Zone Split',
  version: 'v1.0',
  supported_lottery_types: ['DAILY_539'],
  minimum_history: 30,
  lifecycle_status: 'ONLINE',
  executable: true,
  provenance: ['fixture:strategy_catalog'],
} as const

function makeOverview(items = [sampleStrategy, sampleOnlineStrategy]): StrategyOverviewResponse {
  const executableCount = items.filter((i) => i.executable).length
  return {
    items: [...items],
    summary: {
      total: items.length,
      executable_count: executableCount,
      metadata_only_count: items.length - executableCount,
      lifecycle_counts: {
        IDEA: 0,
        OBSERVATION: items.filter((i) => i.lifecycle_status === 'OBSERVATION').length,
        ONLINE: items.filter((i) => i.lifecycle_status === 'ONLINE').length,
        REJECTED: 0,
        RETIRED: 0,
      },
      lottery_type_counts: {
        DAILY_539: items.filter((i) => i.supported_lottery_types.includes('DAILY_539')).length,
        BIG_LOTTO: items.filter((i) => i.supported_lottery_types.includes('BIG_LOTTO')).length,
        POWER_LOTTO: 0,
      },
    },
    capabilities: {
      evaluation_metrics_available: false,
      d3_status_available: false,
      best_strategy_ranking_available: false,
      unavailable_reason_codes: ['NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE'],
    },
  }
}

function makeEvidence(items = [sampleStrategy, sampleOnlineStrategy]): StrategyEvidenceResponse {
  return {
    items: items.map((item) => ({
      strategy_id: item.strategy_id,
      strategy_version: item.version,
      replicate: 'NOT_APPLICABLE',
      display_name: item.display_name,
      lifecycle_status: item.lifecycle_status,
      executable: item.executable,
      supported_lottery_types: [...item.supported_lottery_types],
      minimum_history: item.minimum_history,
      provenance: [...item.provenance],
      adapter_available: true,
      registration_status: 'CANONICAL_EVIDENCE_MISSING',
      definition_status: 'DEFINITION_AVAILABLE',
      verification_status: 'EVIDENCE_MISSING',
      unavailable_reason_code: 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE',
    })),
    best_strategy: {
      status: 'UNAVAILABLE',
      reason: 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE',
    },
    strategy_combination_hit_rate: {
      status: 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE',
      value: 'NOT_AVAILABLE',
      owner: 'ACTIVE_MULTITICKET_AGENT',
    },
    d3: {
      status: 'RESERVED_UNAVAILABLE',
      value: 'NOT_AVAILABLE',
    },
  }
}

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = String(input)
    if (url.includes('/api/v1/strategy-overview')) {
      return Promise.resolve(apiResponse(makeOverview()))
    }
    if (url.includes('/api/v1/strategy-evidence')) {
      return Promise.resolve(apiResponse(makeEvidence()))
    }
    return Promise.resolve(apiResponse({}))
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('StrategyIntelligencePage Workspace', () => {
  it('renders unified header, metric cards, and default Overview tab', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    expect(wrapper.get('.section-header__title').text()).toBe('Strategy Intelligence')

    const metricsText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(metricsText).toContain('Total Strategies')
    expect(metricsText).toContain('2')
    expect(metricsText).toContain('Executable')
    expect(metricsText).toContain('1')
    expect(metricsText).toContain('Evidence Ready')
    expect(metricsText).toContain('EVIDENCE UNAVAILABLE')
    expect(metricsText).toContain('Empirical Eligible')
    expect(metricsText).toContain('EMPIRICAL INELIGIBLE')
    expect(metricsText).toContain('Portfolio Evidence')
    expect(metricsText).toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')
    expect(metricsText).toContain('D3 SSOT Status')
    expect(metricsText).toContain('RESERVED_UNAVAILABLE')

    // Active tab is Overview
    const overviewTab = wrapper.findAll('button[role="tab"]')[0]
    expect(overviewTab.text()).toBe('Overview')
    expect(overviewTab.attributes('aria-selected')).toBe('true')
    expect(wrapper.text()).toContain('Strategy Catalog & Descriptors')
    expect(wrapper.text()).toContain(sampleStrategy.display_name)
    expect(wrapper.text()).toContain(sampleOnlineStrategy.display_name)

    wrapper.unmount()
  })

  it('filters strategies by search query and game selector in Overview tab', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // Search query filter
    const searchInput = wrapper.get('input#strategy-search')
    await searchInput.setValue('Anti-Popularity')
    expect(wrapper.text()).toContain(sampleStrategy.display_name)
    expect(wrapper.text()).not.toContain(sampleOnlineStrategy.display_name)

    // Reset search
    await searchInput.setValue('')
    expect(wrapper.text()).toContain(sampleStrategy.display_name)
    expect(wrapper.text()).toContain(sampleOnlineStrategy.display_name)

    // Game filter
    const gameSelect = wrapper.get('select#game-filter')
    await gameSelect.setValue('T539')
    expect(wrapper.text()).not.toContain(sampleStrategy.display_name)
    expect(wrapper.text()).toContain(sampleOnlineStrategy.display_name)

    // Lifecycle filter
    const lifecycleSelect = wrapper.get('select#lifecycle-filter')
    await lifecycleSelect.setValue('OBSERVATION')
    expect(wrapper.text()).toContain('No matching strategies')

    // Reset filters button
    const resetBtn = wrapper.findAll('button').find((b) => b.text().includes('Reset filters'))
    expect(resetBtn).toBeDefined()
    await resetBtn?.trigger('click')
    expect(wrapper.text()).toContain(sampleStrategy.display_name)
    expect(wrapper.text()).toContain(sampleOnlineStrategy.display_name)

    wrapper.unmount()
  })

  it('switches to Table and Cards view in Overview tab', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    expect(wrapper.find('.data-table').exists()).toBe(true)
    expect(wrapper.find('.strategy-card-grid').exists()).toBe(false)

    // Switch to Cards view
    const cardsBtn = wrapper.findAll('button').find((b) => b.text() === 'Cards')
    await cardsBtn?.trigger('click')

    expect(wrapper.find('.strategy-card-grid').exists()).toBe(true)
    expect(wrapper.findAll('.strategy-card')).toHaveLength(2)

    wrapper.unmount()
  })

  it('switches to Portfolio Hit Rate tab and displays explicit canonical unavailability', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const portfolioTab = wrapper.findAll('button[role="tab"]')[1]
    expect(portfolioTab.text()).toBe('Portfolio Hit Rate')
    await portfolioTab.trigger('click')
    await flushPromises()

    expect(portfolioTab.attributes('aria-selected')).toBe('true')
    expect(wrapper.text()).toContain('Combination & Portfolio Evidence Status')
    expect(wrapper.text()).toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')
    expect(wrapper.text()).toContain('ACTIVE_MULTITICKET_AGENT')
    expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')

    // Table rows for B649, P638, T539
    expect(wrapper.text()).toContain('B649')
    expect(wrapper.text()).toContain('P638')
    expect(wrapper.text()).toContain('T539')
    expect(wrapper.text()).toContain('Big Lotto 6/49')
    expect(wrapper.text()).toContain('Power Lotto 6/38')
    expect(wrapper.text()).toContain('Daily Cash 5/39')

    // Guard rail text
    expect(wrapper.text()).toContain('Combinatorial and multi-strategy hit rates cannot be derived')
    expect(wrapper.text()).not.toContain('0.00%')

    wrapper.unmount()
  })

  it('switches to D3 SSOT tab and displays canonical authority and definition prose', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const d3Tab = wrapper.findAll('button[role="tab"]')[2]
    expect(d3Tab.text()).toBe('D3 SSOT')
    await d3Tab.trigger('click')
    await flushPromises()

    expect(d3Tab.attributes('aria-selected')).toBe('true')
    expect(wrapper.text()).toContain('D3 Strategy Status & SSOT Definition')
    expect(wrapper.text()).toContain('RESERVED_UNAVAILABLE')
    expect(wrapper.text()).toContain('NOT_AVAILABLE')
    expect(wrapper.text()).toContain('contracts/evidence/metric_definitions/d3.json')
    expect(wrapper.text()).toContain('D3 is reserved for a future Owner-approved primary ranking metric')

    // Per-strategy rows
    expect(wrapper.text()).toContain('Per-Strategy D3 Evaluation Status')
    expect(wrapper.text()).toContain(sampleStrategy.strategy_id)
    expect(wrapper.text()).toContain(sampleOnlineStrategy.strategy_id)

    wrapper.unmount()
  })

  it('renders ErrorState with retry button when API fails', async () => {
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve(apiResponse({ message: 'Service unavailable' }, 503)),
    )
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load Strategy Intelligence workspace')
    expect(wrapper.text()).toContain('HTTP 503')

    // Click retry
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        return Promise.resolve(apiResponse(makeOverview()))
      }
      return Promise.resolve(apiResponse(makeEvidence()))
    })

    const retryBtn = wrapper.get('.error-state__actions button')
    await retryBtn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Strategy Catalog & Descriptors')
    expect(wrapper.text()).toContain(sampleStrategy.display_name)

    wrapper.unmount()
  })

  it('enforces English-only user-visible copy with zero CJK characters', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // Test Overview tab
    const textOverview = wrapper.text()
    const cjkRegex = /[\u4e00-\u9fff\u3400-\u4dbf]/g
    const cjkMatchesOverview = textOverview.match(cjkRegex) || []
    expect(cjkMatchesOverview).toHaveLength(0)

    // Test Portfolio tab
    await wrapper.findAll('button[role="tab"]')[1].trigger('click')
    await flushPromises()
    const textPortfolio = wrapper.text()
    const cjkMatchesPortfolio = textPortfolio.match(cjkRegex) || []
    expect(cjkMatchesPortfolio).toHaveLength(0)

    // Test D3 tab
    await wrapper.findAll('button[role="tab"]')[2].trigger('click')
    await flushPromises()
    const textD3 = wrapper.text()
    const cjkMatchesD3 = textD3.match(cjkRegex) || []
    expect(cjkMatchesD3).toHaveLength(0)

    wrapper.unmount()
  })

  it('contains no forbidden predictive claims or betting recommendations', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const allText = wrapper.text().toUpperCase()
    expect(allText).not.toContain('BEST FUTURE STRATEGY')
    expect(allText).not.toContain('RECOMMENDED BET')
    expect(allText).not.toContain('HIGH WIN PROBABILITY')
    expect(allText).not.toContain('GUARANTEED')

    wrapper.unmount()
  })
})
