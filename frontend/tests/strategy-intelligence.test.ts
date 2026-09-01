// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { StrategyOverviewItem, StrategyOverviewResponse } from '../src/api/strategies'
import type { StrategyEvidenceResponse } from '../src/api/strategyEvidence'
import StrategyIntelligencePage from '../src/features/strategy-intelligence/StrategyIntelligencePage.vue'

const b649Strategy: StrategyOverviewItem = {
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
}

const t539Strategy: StrategyOverviewItem = {
  strategy_id: 't539_frequency_zone_split',
  display_name: 'T539 Frequency Zone Split',
  version: 'v1.0',
  supported_lottery_types: ['DAILY_539'],
  minimum_history: 30,
  lifecycle_status: 'ONLINE',
  executable: true,
  provenance: ['fixture:strategy_catalog'],
}

const p638Strategy: StrategyOverviewItem = {
  strategy_id: 'p638_jackpot_tail_weight',
  display_name: 'P638 Jackpot Tail Weight',
  version: 'v0.5',
  supported_lottery_types: ['POWER_LOTTO'],
  minimum_history: 50,
  lifecycle_status: 'IDEA',
  executable: false,
  provenance: ['fixture:strategy_catalog_p638'],
}

const multiGameStrategy: StrategyOverviewItem = {
  strategy_id: 'cross_game_markov_transition',
  display_name: 'Cross Game Markov Transition',
  version: 'v2.0',
  supported_lottery_types: ['BIG_LOTTO', 'DAILY_539'],
  minimum_history: 15,
  lifecycle_status: 'ONLINE',
  executable: true,
  provenance: ['fixture:cross_game'],
}

const ALL_STRATEGIES = [b649Strategy, t539Strategy, p638Strategy, multiGameStrategy]

function makeOverviewForGame(
  lotteryType?: string,
  customItems?: StrategyOverviewItem[],
): StrategyOverviewResponse {
  let items = customItems ?? ALL_STRATEGIES
  if (lotteryType) {
    items = items.filter((item) => item.supported_lottery_types.includes(lotteryType as any))
  }
  const executableCount = items.filter((i) => i.executable).length
  return {
    items: [...items],
    summary: {
      total: items.length,
      executable_count: executableCount,
      metadata_only_count: items.length - executableCount,
      lifecycle_counts: {
        IDEA: items.filter((i) => i.lifecycle_status === 'IDEA').length,
        OBSERVATION: items.filter((i) => i.lifecycle_status === 'OBSERVATION').length,
        ONLINE: items.filter((i) => i.lifecycle_status === 'ONLINE').length,
        REJECTED: items.filter((i) => i.lifecycle_status === 'REJECTED').length,
        RETIRED: items.filter((i) => i.lifecycle_status === 'RETIRED').length,
      },
      lottery_type_counts: {
        DAILY_539: items.filter((i) => i.supported_lottery_types.includes('DAILY_539')).length,
        BIG_LOTTO: items.filter((i) => i.supported_lottery_types.includes('BIG_LOTTO')).length,
        POWER_LOTTO: items.filter((i) => i.supported_lottery_types.includes('POWER_LOTTO')).length,
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

function makeEvidence(
  customOverrides?: Record<string, { registration_status?: string; verification_status?: string }>,
): StrategyEvidenceResponse {
  return {
    items: ALL_STRATEGIES.map((item) => {
      const overrides = customOverrides?.[item.strategy_id]
      const regStatus = overrides?.registration_status ?? 'CANONICAL_EVIDENCE_MISSING'
      const verStatus = overrides?.verification_status ?? 'EVIDENCE_MISSING'
      return {
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
        registration_status: regStatus as any,
        definition_status: 'DEFINITION_AVAILABLE',
        verification_status: verStatus as any,
        unavailable_reason_code:
          regStatus === 'CANONICAL_EVIDENCE_REGISTERED'
            ? null
            : 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE',
      }
    }),
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
      const urlObj = new URL(url, 'http://localhost')
      const lotteryType = urlObj.searchParams.get('lottery_type') ?? undefined
      return Promise.resolve(apiResponse(makeOverviewForGame(lotteryType)))
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

describe('StrategyIntelligencePage Cross-Game Unified UI', () => {
  it('1. default B649 game selection on load', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // Header & Game Selector
    expect(wrapper.get('.section-header__title').text()).toBe('Strategy Intelligence')
    const b649Btn = wrapper.get('[data-testid="game-selector-b649"]')
    expect(b649Btn.attributes('aria-checked')).toBe('true')
    expect(b649Btn.classes()).toContain('button--primary')

    // Initial query uses BIG_LOTTO
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('lottery_type=BIG_LOTTO'),
      expect.anything(),
    )

    // Summary metrics reflect B649 scope (2 strategies: b649Strategy, multiGameStrategy)
    const metricsText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(metricsText).toContain('Total Strategies')
    expect(metricsText).toContain('2')
    expect(metricsText).toContain('Executable')
    expect(metricsText).toContain('1')

    // Overview shows B649 strategies
    expect(wrapper.text()).toContain(b649Strategy.display_name)
    expect(wrapper.text()).toContain(multiGameStrategy.display_name)
    expect(wrapper.text()).not.toContain(t539Strategy.display_name)
    expect(wrapper.text()).not.toContain(p638Strategy.display_name)

    wrapper.unmount()
  })

  it('2. switch B649 -> P638', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const p638Btn = wrapper.get('[data-testid="game-selector-p638"]')
    await p638Btn.trigger('click')
    await flushPromises()

    expect(p638Btn.attributes('aria-checked')).toBe('true')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('lottery_type=POWER_LOTTO'),
      expect.anything(),
    )

    // Metrics reflect P638 scope (1 strategy: p638Strategy)
    const metricsText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(metricsText).toContain('Total Strategies')
    expect(metricsText).toContain('1')

    expect(wrapper.text()).toContain(p638Strategy.display_name)
    expect(wrapper.text()).not.toContain(b649Strategy.display_name)
    expect(wrapper.text()).not.toContain(t539Strategy.display_name)

    wrapper.unmount()
  })

  it('3. switch P638 -> T539', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // Switch to P638 then T539
    await wrapper.get('[data-testid="game-selector-p638"]').trigger('click')
    await flushPromises()

    const t539Btn = wrapper.get('[data-testid="game-selector-t539"]')
    await t539Btn.trigger('click')
    await flushPromises()

    expect(t539Btn.attributes('aria-checked')).toBe('true')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('lottery_type=DAILY_539'),
      expect.anything(),
    )

    // Metrics reflect T539 scope (2 strategies: t539Strategy, multiGameStrategy)
    const metricsText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(metricsText).toContain('Total Strategies')
    expect(metricsText).toContain('2')

    expect(wrapper.text()).toContain(t539Strategy.display_name)
    expect(wrapper.text()).toContain(multiGameStrategy.display_name)
    expect(wrapper.text()).not.toContain(p638Strategy.display_name)

    wrapper.unmount()
  })

  it('4. switch back does not retain old game data', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // Switch to P638
    await wrapper.get('[data-testid="game-selector-p638"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(p638Strategy.display_name)
    expect(wrapper.text()).not.toContain(b649Strategy.display_name)

    // Switch back to B649
    await wrapper.get('[data-testid="game-selector-b649"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(b649Strategy.display_name)
    expect(wrapper.text()).not.toContain(p638Strategy.display_name)

    wrapper.unmount()
  })

  it('5. strategy overview request passes correct lottery_type', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const lastCallInitial = fetchMock.mock.calls.find((call) =>
      String(call[0]).includes('/api/v1/strategy-overview'),
    )
    expect(lastCallInitial?.[0]).toContain('lottery_type=BIG_LOTTO')

    await wrapper.get('[data-testid="game-selector-p638"]').trigger('click')
    await flushPromises()
    const lastCallP638 = fetchMock.mock.calls.findLast((call) =>
      String(call[0]).includes('/api/v1/strategy-overview'),
    )
    expect(lastCallP638?.[0]).toContain('lottery_type=POWER_LOTTO')

    await wrapper.get('[data-testid="game-selector-t539"]').trigger('click')
    await flushPromises()
    const lastCallT539 = fetchMock.mock.calls.findLast((call) =>
      String(call[0]).includes('/api/v1/strategy-overview'),
    )
    expect(lastCallT539?.[0]).toContain('lottery_type=DAILY_539')

    wrapper.unmount()
  })

  it('6. strategy rows only contain selected game', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // B649 scope: rows only have B649-supported items
    const rows = wrapper.findAll('.data-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain(b649Strategy.strategy_id)
    expect(rows[1].text()).toContain(multiGameStrategy.strategy_id)

    wrapper.unmount()
  })

  it('7. multi-game strategy appears in all supported games', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // In B649: multiGameStrategy appears
    expect(wrapper.text()).toContain(multiGameStrategy.display_name)

    // In P638: multiGameStrategy does NOT appear
    await wrapper.get('[data-testid="game-selector-p638"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain(multiGameStrategy.display_name)

    // In T539: multiGameStrategy appears
    await wrapper.get('[data-testid="game-selector-t539"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(multiGameStrategy.display_name)

    wrapper.unmount()
  })

  it('8. Evidence Ready is dynamic and not hardcoded', async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        return Promise.resolve(apiResponse(makeOverviewForGame('BIG_LOTTO')))
      }
      if (url.includes('/api/v1/strategy-evidence')) {
        return Promise.resolve(
          apiResponse(
            makeEvidence({
              [b649Strategy.strategy_id]: {
                registration_status: 'CANONICAL_EVIDENCE_REGISTERED',
                verification_status: 'EVIDENCE_DECLARED_NOT_RECOMPUTED',
              },
            }),
          ),
        )
      }
      return Promise.resolve(apiResponse({}))
    })

    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const metricsText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(metricsText).toContain('Evidence Ready')
    expect(metricsText).toContain('1')
    expect(metricsText).toContain('REGISTERED')

    wrapper.unmount()
  })

  it('9. Empirical Eligible is dynamic and not hardcoded', async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        return Promise.resolve(apiResponse(makeOverviewForGame('BIG_LOTTO')))
      }
      if (url.includes('/api/v1/strategy-evidence')) {
        return Promise.resolve(
          apiResponse(
            makeEvidence({
              [b649Strategy.strategy_id]: {
                registration_status: 'CANONICAL_EVIDENCE_REGISTERED',
                verification_status: 'EVIDENCE_VERIFIED',
              },
            }),
          ),
        )
      }
      return Promise.resolve(apiResponse({}))
    })

    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const metricsText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(metricsText).toContain('Empirical Eligible')
    expect(metricsText).toContain('1')
    expect(metricsText).toContain('EMPIRICAL ELIGIBLE')

    wrapper.unmount()
  })

  it('10. registered + verified eligibility semantics', async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        return Promise.resolve(apiResponse(makeOverviewForGame('BIG_LOTTO')))
      }
      if (url.includes('/api/v1/strategy-evidence')) {
        return Promise.resolve(
          apiResponse(
            makeEvidence({
              [b649Strategy.strategy_id]: {
                registration_status: 'CANONICAL_EVIDENCE_REGISTERED',
                verification_status: 'EVIDENCE_VERIFIED',
              },
              [multiGameStrategy.strategy_id]: {
                registration_status: 'CANONICAL_EVIDENCE_REGISTERED',
                verification_status: 'EVIDENCE_MISSING',
              },
            }),
          ),
        )
      }
      return Promise.resolve(apiResponse({}))
    })

    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // 2 registered, but only 1 eligible (the verified one)
    const metricsText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(metricsText).toContain('Evidence Ready')
    expect(metricsText).toContain('2')
    expect(metricsText).toContain('Empirical Eligible')
    expect(metricsText).toContain('1')

    wrapper.unmount()
  })

  it('11. unregistered or incompatible evidence cannot be eligible', async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        return Promise.resolve(apiResponse(makeOverviewForGame('BIG_LOTTO')))
      }
      if (url.includes('/api/v1/strategy-evidence')) {
        return Promise.resolve(
          apiResponse(
            makeEvidence({
              [b649Strategy.strategy_id]: {
                registration_status: 'CANONICAL_EVIDENCE_REGISTERED',
                verification_status: 'EVIDENCE_INCOMPATIBLE',
              },
              [multiGameStrategy.strategy_id]: {
                registration_status: 'CANONICAL_EVIDENCE_MISSING',
                verification_status: 'EVIDENCE_VERIFIED',
              },
            }),
          ),
        )
      }
      return Promise.resolve(apiResponse({}))
    })

    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const metricsText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(metricsText).toContain('Empirical Eligible')
    expect(metricsText).toContain('0')
    expect(metricsText).toContain('EMPIRICAL INELIGIBLE')

    wrapper.unmount()
  })

  it('12. Best Strategy unavailable correctly displayed', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const metricsText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(metricsText).toContain('Best Strategy')
    expect(metricsText).toContain('UNAVAILABLE')

    expect(wrapper.text()).toContain('Best Strategy Overview')
    expect(wrapper.text()).toContain('BEST STRATEGY EVIDENCE UNAVAILABLE')
    expect(wrapper.text()).toContain('GAME-SPECIFIC BEST STRATEGY EVIDENCE UNAVAILABLE')
    expect(wrapper.text()).toContain('NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE')

    wrapper.unmount()
  })

  it('13. Portfolio unavailable correctly displayed', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const portfolioTab = wrapper.findAll('button[role="tab"]')[1]
    await portfolioTab.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Combination & Portfolio Evidence Status')
    expect(wrapper.text()).toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')
    expect(wrapper.text()).toContain('NOT_AVAILABLE')
    expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')

    wrapper.unmount()
  })

  it('14. Portfolio owner preserved', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const portfolioTab = wrapper.findAll('button[role="tab"]')[1]
    await portfolioTab.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('ACTIVE_MULTITICKET_AGENT')

    wrapper.unmount()
  })

  it('15. D3 unavailable correctly displayed', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const d3Tab = wrapper.findAll('button[role="tab"]')[2]
    await d3Tab.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('D3 Strategy Status & SSOT Definition')
    expect(wrapper.text()).toContain('RESERVED_UNAVAILABLE')
    expect(wrapper.text()).toContain('NOT_AVAILABLE')
    expect(wrapper.text()).toContain('contracts/evidence/metric_definitions/d3.json')

    wrapper.unmount()
  })

  it('16. unavailable does not display 0', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // Portfolio tab
    await wrapper.findAll('button[role="tab"]')[1].trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('0.00%')
    expect(wrapper.text()).toContain('UNAVAILABLE')

    // D3 tab
    await wrapper.findAll('button[role="tab"]')[2].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('NOT_AVAILABLE')

    wrapper.unmount()
  })

  it('17. tabs switching does not lose selected game', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // Switch to P638
    await wrapper.get('[data-testid="game-selector-p638"]').trigger('click')
    await flushPromises()

    // Switch to Portfolio tab
    const tabs = wrapper.findAll('button[role="tab"]')
    await tabs[1].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Combination & Portfolio Evidence Status · P638')

    // Switch to D3 tab
    await tabs[2].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('D3 Strategy Status & SSOT Definition · P638')

    // Switch back to Overview tab
    await tabs[0].trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="game-selector-p638"]').attributes('aria-checked')).toBe('true')
    expect(wrapper.text()).toContain(p638Strategy.display_name)

    wrapper.unmount()
  })

  it('18. request error and evidence unavailable separated', async () => {
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve(apiResponse({ message: 'Service unavailable' }, 503)),
    )
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load Strategy Intelligence workspace')
    expect(wrapper.text()).toContain('HTTP 503')

    // Retry recovery
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        return Promise.resolve(apiResponse(makeOverviewForGame('BIG_LOTTO')))
      }
      return Promise.resolve(apiResponse(makeEvidence()))
    })

    const retryBtn = wrapper.get('.error-state__actions button')
    await retryBtn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Strategy Intelligence')
    expect(wrapper.text()).toContain(b649Strategy.display_name)
    expect(wrapper.text()).not.toContain('Failed to load')

    wrapper.unmount()
  })

  describe('Bounded Smoke Matrix (A - I)', () => {
    it('A. B649 -> Overview', async () => {
      const wrapper = mount(StrategyIntelligencePage)
      await flushPromises()
      expect(wrapper.text()).toContain('Catalog Summary · B649')
      expect(wrapper.text()).toContain(b649Strategy.display_name)
      wrapper.unmount()
    })

    it('B. B649 -> Portfolio Hit Rate', async () => {
      const wrapper = mount(StrategyIntelligencePage)
      await flushPromises()
      await wrapper.findAll('button[role="tab"]')[1].trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('Combination & Portfolio Evidence Status · B649')
      expect(wrapper.text()).toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')
      wrapper.unmount()
    })

    it('C. B649 -> D3', async () => {
      const wrapper = mount(StrategyIntelligencePage)
      await flushPromises()
      await wrapper.findAll('button[role="tab"]')[2].trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('D3 Strategy Status & SSOT Definition · B649')
      expect(wrapper.text()).toContain('RESERVED_UNAVAILABLE')
      wrapper.unmount()
    })

    it('D. P638 -> Overview', async () => {
      const wrapper = mount(StrategyIntelligencePage)
      await flushPromises()
      await wrapper.get('[data-testid="game-selector-p638"]').trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('Catalog Summary · P638')
      expect(wrapper.text()).toContain(p638Strategy.display_name)
      wrapper.unmount()
    })

    it('E. P638 -> Portfolio', async () => {
      const wrapper = mount(StrategyIntelligencePage)
      await flushPromises()
      await wrapper.get('[data-testid="game-selector-p638"]').trigger('click')
      await flushPromises()
      await wrapper.findAll('button[role="tab"]')[1].trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('Combination & Portfolio Evidence Status · P638')
      wrapper.unmount()
    })

    it('F. P638 -> D3', async () => {
      const wrapper = mount(StrategyIntelligencePage)
      await flushPromises()
      await wrapper.get('[data-testid="game-selector-p638"]').trigger('click')
      await flushPromises()
      await wrapper.findAll('button[role="tab"]')[2].trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('D3 Strategy Status & SSOT Definition · P638')
      wrapper.unmount()
    })

    it('G. T539 -> Overview', async () => {
      const wrapper = mount(StrategyIntelligencePage)
      await flushPromises()
      await wrapper.get('[data-testid="game-selector-t539"]').trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('Catalog Summary · T539')
      expect(wrapper.text()).toContain(t539Strategy.display_name)
      wrapper.unmount()
    })

    it('H. T539 -> Portfolio', async () => {
      const wrapper = mount(StrategyIntelligencePage)
      await flushPromises()
      await wrapper.get('[data-testid="game-selector-t539"]').trigger('click')
      await flushPromises()
      await wrapper.findAll('button[role="tab"]')[1].trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('Combination & Portfolio Evidence Status · T539')
      wrapper.unmount()
    })

    it('I. T539 -> D3', async () => {
      const wrapper = mount(StrategyIntelligencePage)
      await flushPromises()
      await wrapper.get('[data-testid="game-selector-t539"]').trigger('click')
      await flushPromises()
      await wrapper.findAll('button[role="tab"]')[2].trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('D3 Strategy Status & SSOT Definition · T539')
      wrapper.unmount()
    })
  })

  it('enforces English-only user-visible copy with zero CJK characters', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const cjkRegex = /[\u4e00-\u9fff\u3400-\u4dbf]/g

    // Test Overview tab
    const textOverview = wrapper.text()
    expect(textOverview.match(cjkRegex) || []).toHaveLength(0)

    // Test Portfolio tab
    await wrapper.findAll('button[role="tab"]')[1].trigger('click')
    await flushPromises()
    const textPortfolio = wrapper.text()
    expect(textPortfolio.match(cjkRegex) || []).toHaveLength(0)

    // Test D3 tab
    await wrapper.findAll('button[role="tab"]')[2].trigger('click')
    await flushPromises()
    const textD3 = wrapper.text()
    expect(textD3.match(cjkRegex) || []).toHaveLength(0)

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
