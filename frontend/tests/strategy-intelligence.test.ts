// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { StrategyOverviewItem, StrategyOverviewResponse } from '../src/api/strategies'
import type { StrategyEvidenceResponse } from '../src/api/strategyEvidence'
import StrategyIntelligenceOverview from '../src/features/strategy-intelligence/StrategyIntelligenceOverview.vue'
import StrategyIntelligencePage from '../src/features/strategy-intelligence/StrategyIntelligencePage.vue'
import StrategyIntelligencePortfolio from '../src/features/strategy-intelligence/StrategyIntelligencePortfolio.vue'

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

const CANONICAL_D3_DEFINITION = {
  metric_id: 'D3',
  metric_version: 'v1',
  schema_id: 'lottolab.evidence.metric_definition',
  schema_version: '1.0.0',
  formula_status: 'RESERVED_UNAVAILABLE',
  direction: 'DESCRIPTIVE_ONLY',
  aggregation: 'NONE',
  sample_unit: 'DRAWS',
  decimal_scale: 4,
  rounding_mode: 'ROUND_HALF_EVEN',
  unit: 'UNITLESS',
  definition_prose: 'D3 is reserved for a future Owner-approved primary ranking metric.',
  authority_path: 'contracts/evidence/metric_definitions/d3.json',
} satisfies StrategyEvidenceResponse['d3']['definition']

function makeEvidence(
  customOverrides?: Record<string, { registration_status?: string; verification_status?: string }>,
  d3DefinitionOverrides?: Partial<StrategyEvidenceResponse['d3']['definition']>,
  combinationOverrides?: Partial<StrategyEvidenceResponse['strategy_combination_hit_rate']>,
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
      ...combinationOverrides,
    },
    d3: {
      status: 'RESERVED_UNAVAILABLE',
      value: 'NOT_AVAILABLE',
      definition: { ...CANONICAL_D3_DEFINITION, ...d3DefinitionOverrides },
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

  it('dropdown switches B649 -> P638 -> T539 -> B649 with matching queries and rows', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const gameSelect = wrapper.get('[data-testid="game-scope-select"]')
    const overviewRequests = () =>
      fetchMock.mock.calls
        .map(([input]) => String(input))
        .filter((url) => url.includes('/api/v1/strategy-overview'))

    expect((gameSelect.element as HTMLSelectElement).value).toBe('BIG_LOTTO')
    expect(overviewRequests()).toHaveLength(1)

    const transitions = [
      {
        lotteryType: 'POWER_LOTTO',
        button: 'p638',
        visibleStrategy: p638Strategy.display_name,
        hiddenStrategies: [b649Strategy.display_name, t539Strategy.display_name],
      },
      {
        lotteryType: 'DAILY_539',
        button: 't539',
        visibleStrategy: t539Strategy.display_name,
        hiddenStrategies: [b649Strategy.display_name, p638Strategy.display_name],
      },
      {
        lotteryType: 'BIG_LOTTO',
        button: 'b649',
        visibleStrategy: b649Strategy.display_name,
        hiddenStrategies: [p638Strategy.display_name, t539Strategy.display_name],
      },
    ]

    for (const transition of transitions) {
      await gameSelect.setValue(transition.lotteryType)
      await flushPromises()

      expect(overviewRequests().at(-1)).toContain(`lottery_type=${transition.lotteryType}`)
      expect((gameSelect.element as HTMLSelectElement).value).toBe(transition.lotteryType)
      expect(
        wrapper.get(`[data-testid="game-selector-${transition.button}"]`).attributes('aria-checked'),
      ).toBe('true')
      expect(wrapper.text()).toContain(transition.visibleStrategy)
      for (const hiddenStrategy of transition.hiddenStrategies) {
        expect(wrapper.text()).not.toContain(hiddenStrategy)
      }
    }

    expect(overviewRequests()).toHaveLength(4)

    // A change event for the already selected game is a no-op.
    await gameSelect.trigger('change')
    await flushPromises()
    expect(overviewRequests()).toHaveLength(4)

    // Buttons use the same transition path and keep the select in sync.
    await wrapper.get('[data-testid="game-selector-p638"]').trigger('click')
    await flushPromises()
    expect((gameSelect.element as HTMLSelectElement).value).toBe('POWER_LOTTO')
    expect(overviewRequests().at(-1)).toContain('lottery_type=POWER_LOTTO')

    wrapper.unmount()
  })

  it('keeps the search and descriptor filters visible and narrows results correctly', async () => {
    const makeItem = (overrides: Record<string, unknown> = {}) => ({
      strategyId: 'cross_game_markov_transition',
      displayName: 'Cross Game Markov Transition',
      version: 'v2.0',
      supportedLotteryTypes: ['BIG_LOTTO', 'DAILY_539'],
      gameLabels: ['B649', 'T539'],
      minimumHistory: 15,
      lifecycleStatus: 'ONLINE',
      executable: true,
      provenance: ['fixture:cross_game'],
      adapterAvailable: true,
      registrationStatus: 'CANONICAL_EVIDENCE_REGISTERED',
      definitionStatus: 'DEFINITION_AVAILABLE',
      verificationStatus: 'EVIDENCE_VERIFIED',
      empiricalEligibility: 'EMPIRICAL ELIGIBLE',
      evidenceStatus: 'CANONICAL EVIDENCE REGISTERED',
      unavailableReasonCode: null,
      ...overrides,
    })

    const items = [
      makeItem(),
      makeItem({
        strategyId: 'cross_game_missing_evidence',
        displayName: 'Cross Game Missing Evidence',
        registrationStatus: 'CANONICAL_EVIDENCE_MISSING',
        evidenceStatus: 'CANONICAL EVIDENCE MISSING',
        verificationStatus: 'EVIDENCE_MISSING',
        empiricalEligibility: 'EMPIRICAL INELIGIBLE',
        unavailableReasonCode: 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE',
      }),
      makeItem({
        strategyId: 'cross_game_b649_only',
        displayName: 'Cross Game B649 Only',
        gameLabels: ['B649'],
      }),
      makeItem({
        strategyId: 'cross_game_idea',
        displayName: 'Cross Game Idea',
        lifecycleStatus: 'IDEA',
      }),
      makeItem({
        strategyId: 'cross_game_metadata',
        displayName: 'Cross Game Metadata',
        executable: false,
      }),
    ]
    const wrapper = mount(StrategyIntelligenceOverview, {
      props: {
        items: items as any,
        totalCount: items.length,
        executableCount: 4,
        metadataOnlyCount: 1,
        lifecycleCounts: { ONLINE: 4, IDEA: 1 },
        unavailableReasons: ['NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE'],
        selectedLotteryType: 'BIG_LOTTO',
      },
    })

    await wrapper.get('#strategy-search').setValue('cross_game')
    await wrapper.get('#game-filter').setValue('T539')
    await wrapper.get('#lifecycle-filter').setValue('ONLINE')
    await wrapper.get('#executable-filter').setValue('true')
    await wrapper.get('#evidence-filter').setValue('REGISTERED')

    expect(wrapper.findAll('tbody tr.data-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('Cross Game Markov Transition')
    expect(wrapper.text()).not.toContain('Cross Game Missing Evidence')
    expect(wrapper.text()).not.toContain('Cross Game B649 Only')
    expect(wrapper.text()).not.toContain('Cross Game Idea')
    expect(wrapper.text()).not.toContain('Cross Game Metadata')
    expect(wrapper.get('[data-testid="strategy-query-context"]').text()).toContain(
      'Catalog scope: B649 · Search: cross_game · Game: T539 · Lifecycle: ONLINE · Execution: Executable · Evidence: Canonical Registered',
    )
    expect(wrapper.get('[data-testid="strategy-query-context"]').text()).toContain('1 of 5 strategies match')

    await wrapper.get('[data-testid="strategy-details-cross_game_markov_transition"]').trigger('click')
    const detail = wrapper.get('[data-testid="strategy-detail"]')
    expect(detail.text()).toContain('Strategy details · B649')
    expect(detail.text()).toContain('Evidence and availability')
    expect(detail.text()).toContain('Minimum history')
    expect(detail.text()).toContain('fixture:cross_game')
    expect(detail.text()).toContain('Search: cross_game · Game: T539')

    await wrapper.get('[data-testid="strategy-detail-return"]').trigger('click')
    expect(wrapper.get('#strategy-search').element).toHaveProperty('value', 'cross_game')
    expect((wrapper.get('#game-filter').element as HTMLSelectElement).value).toBe('T539')
    expect(wrapper.findAll('tbody tr.data-row')).toHaveLength(1)

    wrapper.unmount()
  })

  it('preserves same-page query conditions across lottery and tab changes without mixing rows', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    await wrapper.get('#strategy-search').setValue('cross_game_markov_transition')
    await wrapper.get('#game-filter').setValue('T539')
    await wrapper.get('#lifecycle-filter').setValue('ONLINE')
    await wrapper.get('#executable-filter').setValue('true')
    await wrapper.get('#evidence-filter').setValue('MISSING')

    expect(wrapper.findAll('tbody tr.data-row')).toHaveLength(1)
    await wrapper.get('[data-testid="strategy-details-cross_game_markov_transition"]').trigger('click')
    expect(wrapper.get('[data-testid="strategy-detail"]').text()).toContain('Strategy details · B649')

    await wrapper.get('[data-testid="game-selector-t539"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="game-selector-t539"]').attributes('aria-checked')).toBe('true')
    expect(wrapper.find('[data-testid="strategy-detail"]').exists()).toBe(false)
    expect((wrapper.get('#strategy-search').element as HTMLInputElement).value).toBe(
      'cross_game_markov_transition',
    )
    expect((wrapper.get('#game-filter').element as HTMLSelectElement).value).toBe('T539')
    expect((wrapper.get('#lifecycle-filter').element as HTMLSelectElement).value).toBe('ONLINE')
    expect((wrapper.get('#executable-filter').element as HTMLSelectElement).value).toBe('true')
    expect((wrapper.get('#evidence-filter').element as HTMLSelectElement).value).toBe('MISSING')
    expect(wrapper.get('[data-testid="strategy-query-context"]').text()).toContain('Catalog scope: T539')
    expect(wrapper.findAll('tbody tr.data-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('Cross Game Markov Transition')
    expect(wrapper.text()).not.toContain(t539Strategy.display_name)
    expect(wrapper.text()).not.toContain(p638Strategy.display_name)

    await wrapper.findAll('button[role="tab"]')[1].trigger('click')
    await wrapper.findAll('button[role="tab"]')[0].trigger('click')
    expect((wrapper.get('#strategy-search').element as HTMLInputElement).value).toBe(
      'cross_game_markov_transition',
    )
    expect((wrapper.get('#game-filter').element as HTMLSelectElement).value).toBe('T539')
    expect(wrapper.findAll('tbody tr.data-row')).toHaveLength(1)

    wrapper.unmount()
  })

  it('dropdown API errors clear the previous game rows and retain the selected scope', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()
    expect(wrapper.text()).toContain(b649Strategy.display_name)

    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        const lotteryType = new URL(url, 'http://localhost').searchParams.get('lottery_type')
        if (lotteryType === 'POWER_LOTTO') {
          return Promise.resolve(apiResponse({ message: 'P638 unavailable' }, 503))
        }
        return Promise.resolve(apiResponse(makeOverviewForGame(lotteryType ?? undefined)))
      }
      if (url.includes('/api/v1/strategy-evidence')) {
        return Promise.resolve(apiResponse(makeEvidence()))
      }
      return Promise.resolve(apiResponse({}))
    })

    const gameSelect = wrapper.get('[data-testid="game-scope-select"]')
    await gameSelect.setValue('POWER_LOTTO')
    await flushPromises()

    expect((gameSelect.element as HTMLSelectElement).value).toBe('POWER_LOTTO')
    expect(wrapper.get('[data-testid="game-selector-p638"]').attributes('aria-checked')).toBe('true')
    expect(wrapper.text()).toContain('Failed to load Strategy Intelligence workspace')
    expect(wrapper.text()).toContain('HTTP 503')
    expect(wrapper.text()).not.toContain(b649Strategy.display_name)
    expect(wrapper.text()).not.toContain(p638Strategy.display_name)

    wrapper.unmount()
  })

  it('dropdown preserves null evidence reasons, unavailable values, and an empty catalog', async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        const lotteryType = new URL(url, 'http://localhost').searchParams.get('lottery_type')
        if (lotteryType === 'DAILY_539') {
          return Promise.resolve(apiResponse(makeOverviewForGame('DAILY_539', [])))
        }
        return Promise.resolve(apiResponse(makeOverviewForGame(lotteryType ?? undefined)))
      }
      if (url.includes('/api/v1/strategy-evidence')) {
        return Promise.resolve(
          apiResponse(
            makeEvidence({
              [p638Strategy.strategy_id]: {
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
    const gameSelect = wrapper.get('[data-testid="game-scope-select"]')

    await gameSelect.setValue('POWER_LOTTO')
    await flushPromises()

    const p638Row = wrapper
      .findAll('.data-row')
      .find((row) => row.text().includes(p638Strategy.strategy_id))
    expect(p638Row).toBeDefined()
    expect(p638Row!.text()).toContain('CANONICAL EVIDENCE REGISTERED')
    expect(p638Row!.findAll('td').at(9)?.text().trim()).toBe('—')
    expect(p638Row!.find('code.reason-code-inline').exists()).toBe(false)

    await gameSelect.setValue('DAILY_539')
    await flushPromises()

    expect(wrapper.text()).toContain('Strategy Catalog is empty')
    expect(wrapper.text()).toContain('UNAVAILABLE')
    expect(wrapper.text()).toContain('NOT_AVAILABLE')
    expect(wrapper.text()).not.toContain(p638Strategy.display_name)
    expect(wrapper.text()).not.toContain(t539Strategy.display_name)
    expect(wrapper.text()).not.toContain('0.00%')

    wrapper.unmount()
  })

  it('rapid dropdown changes ignore aborted and stale API responses', async () => {
    const delayedOverviewResponses = new Map<string, (response: Response) => void>()
    const overviewSignals = new Map<string, AbortSignal | null>()

    fetchMock.mockImplementation((input, init) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        const lotteryType = new URL(url, 'http://localhost').searchParams.get('lottery_type') ?? ''
        overviewSignals.set(lotteryType, init?.signal ?? null)
        return new Promise<Response>((resolve) => {
          delayedOverviewResponses.set(lotteryType, resolve)
        })
      }
      if (url.includes('/api/v1/strategy-evidence')) {
        return Promise.resolve(apiResponse(makeEvidence()))
      }
      return Promise.resolve(apiResponse({}))
    })

    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()
    const gameSelect = wrapper.get('[data-testid="game-scope-select"]')

    await gameSelect.setValue('POWER_LOTTO')
    expect(wrapper.text()).not.toContain(b649Strategy.display_name)
    await gameSelect.setValue('DAILY_539')

    expect(overviewSignals.get('BIG_LOTTO')?.aborted).toBe(true)
    expect(overviewSignals.get('POWER_LOTTO')?.aborted).toBe(true)
    expect(overviewSignals.get('DAILY_539')?.aborted).toBe(false)

    delayedOverviewResponses.get('DAILY_539')?.(apiResponse(makeOverviewForGame('DAILY_539')))
    await flushPromises()
    expect(wrapper.text()).toContain(t539Strategy.display_name)
    expect(wrapper.text()).not.toContain(b649Strategy.display_name)
    expect(wrapper.text()).not.toContain(p638Strategy.display_name)

    delayedOverviewResponses.get('POWER_LOTTO')?.(apiResponse(makeOverviewForGame('POWER_LOTTO')))
    delayedOverviewResponses.get('BIG_LOTTO')?.(apiResponse(makeOverviewForGame('BIG_LOTTO')))
    await flushPromises()

    expect((gameSelect.element as HTMLSelectElement).value).toBe('DAILY_539')
    expect(wrapper.text()).toContain(t539Strategy.display_name)
    expect(wrapper.text()).not.toContain(b649Strategy.display_name)
    expect(wrapper.text()).not.toContain(p638Strategy.display_name)

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

  it('12. Best Strategy boundary correctly displayed in registry-wide scope without game-scoped claims', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const metricsText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(metricsText).toContain('Best Strategy')
    expect(metricsText).toContain('UNAVAILABLE')
    expect(metricsText).toContain('Status: UNAVAILABLE · Reason: NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE')

    // Registry-wide boundary semantics
    expect(wrapper.text()).toContain('Registry-wide Best Strategy Evidence Boundary')
    expect(wrapper.text()).toContain('Registry-wide Best Strategy Scope')
    expect(wrapper.text()).toContain('Best Strategy Evidence: UNAVAILABLE')
    expect(wrapper.text()).toContain('NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE')
    expect(wrapper.text()).toContain('Selected Catalog Context')
    expect(wrapper.text()).toContain('B649')

    // Strict authority-honesty: no game-specific best-strategy claims
    expect(wrapper.text()).not.toContain('GAME-SPECIFIC BEST STRATEGY EVIDENCE UNAVAILABLE')
    expect(wrapper.text()).not.toContain('Best Strategy Scope · B649')
    expect(wrapper.text()).not.toContain('Canonical Strategy Evidence · B649')

    wrapper.unmount()
  })

  it('12b. Best Strategy props dynamically drive rendered status and reason in StrategyIntelligenceOverview', async () => {
    const combinedItem = {
      strategyId: b649Strategy.strategy_id,
      displayName: b649Strategy.display_name,
      version: b649Strategy.version,
      supportedLotteryTypes: b649Strategy.supported_lottery_types,
      gameLabels: ['B649'],
      minimumHistory: b649Strategy.minimum_history,
      lifecycleStatus: b649Strategy.lifecycle_status,
      executable: b649Strategy.executable,
      provenance: b649Strategy.provenance,
      adapterAvailable: true,
      registrationStatus: 'CANONICAL_EVIDENCE_REGISTERED',
      definitionStatus: 'DEFINITION_AVAILABLE',
      verificationStatus: 'EVIDENCE_VERIFIED',
      empiricalEligibility: 'EMPIRICAL ELIGIBLE' as const,
      evidenceStatus: 'CANONICAL EVIDENCE REGISTERED' as const,
      unavailableReasonCode: null,
    }

    const wrapper = mount(StrategyIntelligenceOverview, {
      props: {
        items: [combinedItem],
        totalCount: 1,
        executableCount: 0,
        metadataOnlyCount: 1,
        lifecycleCounts: { OBSERVATION: 1 },
        unavailableReasons: ['CUSTOM_UNAVAILABLE_REASON'],
        selectedLotteryType: 'BIG_LOTTO',
        bestStrategyStatus: 'EXPERIMENTAL_STANDBY',
        bestStrategyReason: 'CUSTOM_API_EVALUATION_REASON',
      },
    })

    const text = wrapper.text()
    expect(text).toContain('Registry-wide Best Strategy Evidence Boundary')
    expect(text).toContain('Registry-wide Best Strategy Scope')
    expect(text).toContain('EXPERIMENTAL_STANDBY')
    expect(text).toContain('CUSTOM_API_EVALUATION_REASON')
    expect(text).toContain('Selected Catalog Context')
    expect(text).toContain('B649')

    // Confirm defaults / literal UNAVAILABLE are not pinned
    expect(text).not.toContain('Reason: NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE')
    expect(text).not.toContain('GAME-SPECIFIC BEST STRATEGY EVIDENCE UNAVAILABLE')
    expect(text).not.toContain('Best Strategy Scope · B649')

    wrapper.unmount()
  })

  it('12c. Page-level Best Strategy derives status, badge, and reason from API response', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const metricsGrid = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]')
    const metricCards = metricsGrid.findAll('.metric-card')
    const bestStrategyCard = metricCards.find((card) => card.text().includes('Best Strategy'))
    expect(bestStrategyCard).toBeDefined()
    expect(bestStrategyCard!.text()).toContain('UNAVAILABLE')
    expect(bestStrategyCard!.text()).toContain('Status: UNAVAILABLE · Reason: NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE')
    expect(bestStrategyCard!.find('.metric-card__badge').text()).toBe('UNAVAILABLE')

    wrapper.unmount()
  })

  it('12d. Switching games changes catalog context only without creating distinct best-strategy records', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // Initially B649
    expect(wrapper.text()).toContain('Selected Catalog Context')
    expect(wrapper.text()).toContain('B649')
    expect(wrapper.text()).not.toContain('Best Strategy Scope · B649')
    expect(wrapper.text()).not.toContain('GAME-SPECIFIC BEST STRATEGY EVIDENCE UNAVAILABLE')

    // Switch to P638
    await wrapper.get('[data-testid="game-selector-p638"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Selected Catalog Context')
    expect(wrapper.text()).toContain('P638')
    expect(wrapper.text()).toContain('Registry-wide Best Strategy Scope')
    expect(wrapper.text()).toContain('Registry-wide Best Strategy Evidence Boundary')
    expect(wrapper.text()).not.toContain('Best Strategy Scope · P638')
    expect(wrapper.text()).not.toContain('P638 Best Strategy')
    expect(wrapper.text()).not.toContain('GAME-SPECIFIC BEST STRATEGY EVIDENCE UNAVAILABLE')

    // Switch to T539
    await wrapper.get('[data-testid="game-selector-t539"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Selected Catalog Context')
    expect(wrapper.text()).toContain('T539')
    expect(wrapper.text()).toContain('Registry-wide Best Strategy Scope')
    expect(wrapper.text()).toContain('Registry-wide Best Strategy Evidence Boundary')
    expect(wrapper.text()).not.toContain('Best Strategy Scope · T539')
    expect(wrapper.text()).not.toContain('T539 Best Strategy')
    expect(wrapper.text()).not.toContain('GAME-SPECIFIC BEST STRATEGY EVIDENCE UNAVAILABLE')

    wrapper.unmount()
  })

  it('12e. No strategy ID, rank, score, or Best Replay promotion into best_strategy', async () => {
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

    const bestStrategyPanel = wrapper.get('.best-strategy-panel')
    expect(bestStrategyPanel.text()).not.toContain(b649Strategy.strategy_id)
    expect(bestStrategyPanel.text()).not.toContain(b649Strategy.display_name)
    expect(bestStrategyPanel.text()).not.toContain('Rank #1')
    expect(bestStrategyPanel.text()).not.toContain('Rank 1')
    expect(bestStrategyPanel.text()).not.toContain('Score')
    expect(bestStrategyPanel.text()).not.toContain('Top Strategy')

    wrapper.unmount()
  })

  it('13. Portfolio unavailable correctly displayed in registry-wide boundary', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const portfolioTab = wrapper.findAll('button[role="tab"]')[1]
    await portfolioTab.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Registry-wide Combination Evidence Boundary')
    expect(wrapper.text()).toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')
    expect(wrapper.text()).toContain('NOT_AVAILABLE')
    expect(wrapper.text()).toContain('Selected Catalog Context')
    expect(wrapper.text()).toContain('B649 (Big Lotto 6/49)')
    expect(wrapper.text()).not.toContain('Canonical Game Evidence Status')

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

  it('14b. Portfolio combination props dynamically drive rendered values and are not pinned', async () => {
    const wrapper = mount(StrategyIntelligencePortfolio, {
      props: {
        selectedLotteryType: 'BIG_LOTTO',
        combinationStatus: 'ACTIVE_EXPERIMENTAL_MULTITICKET',
        combinationValue: '0.4285_SAMPLE',
        combinationOwner: 'CUSTOM_AGENT_CELL',
        strategies: [b649Strategy as any],
      },
    })

    const text = wrapper.text()
    expect(text).toContain('Registry-wide Combination Evidence Boundary')
    expect(text).toContain('ACTIVE_EXPERIMENTAL_MULTITICKET')
    expect(text).toContain('0.4285_SAMPLE')
    expect(text).toContain('CUSTOM_AGENT_CELL')
    expect(text).toContain('B649 (Big Lotto 6/49)')
    expect(text).toContain('1 individual candidate strategies')
    expect(text).not.toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')
    expect(text).not.toContain('ACTIVE_MULTITICKET_AGENT')

    wrapper.unmount()
  })

  it('14c. Absence of synthetic per-game portfolio rows and tables in StrategyIntelligencePortfolio', async () => {
    const wrapper = mount(StrategyIntelligencePortfolio, {
      props: {
        selectedLotteryType: 'BIG_LOTTO',
        combinationStatus: 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE',
        combinationValue: 'NOT_AVAILABLE',
        combinationOwner: 'ACTIVE_MULTITICKET_AGENT',
        strategies: [b649Strategy as any],
      },
    })

    expect(wrapper.find('table').exists()).toBe(false)
    const text = wrapper.text()
    expect(text).not.toContain('Canonical Game Evidence Status')
    expect(text).not.toContain('Portfolio ID')
    expect(text).not.toContain('portfolioId')
    expect(text).not.toContain('Included Strategies')
    expect(text).not.toContain('Union Hit Rate')
    expect(text).not.toContain('unionHitRate')
    expect(text).not.toContain('Best Comparator')
    expect(text).not.toContain('Marginal Contribution')
    expect(text).not.toContain('Diversity Metric')
    expect(text).not.toContain('currently contains zero registered multi-strategy artifacts')

    wrapper.unmount()
  })

  it('14d. Switching games changes catalog context without creating portfolio evidence', async () => {
    const wrapper = mount(StrategyIntelligencePortfolio, {
      props: {
        selectedLotteryType: 'POWER_LOTTO',
        combinationStatus: 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE',
        combinationValue: 'NOT_AVAILABLE',
        combinationOwner: 'ACTIVE_MULTITICKET_AGENT',
        strategies: [p638Strategy as any],
      },
    })

    const text = wrapper.text()
    expect(text).toContain('P638 (Power Lotto 6/38)')
    expect(text).toContain('Catalog context only (1 candidate strategies)')
    expect(text).toContain('Registry Combination Scope')
    expect(text).toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')
    expect(text).not.toContain('P638 portfolio evidence')
    expect(text).not.toContain('Canonical Game Evidence Status')

    wrapper.unmount()
  })

  it('14e. Missing portfolio numbers render unavailable without zero or 0.00%', async () => {
    const wrapper = mount(StrategyIntelligencePortfolio, {
      props: {
        selectedLotteryType: 'BIG_LOTTO',
        combinationStatus: 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE',
        combinationValue: 'NOT_AVAILABLE',
        combinationOwner: 'ACTIVE_MULTITICKET_AGENT',
        strategies: [],
      },
    })

    const text = wrapper.text()
    expect(text).not.toContain('0.00%')
    expect(text).toContain('NOT_AVAILABLE')
    expect(text).toContain('UNAVAILABLE')

    wrapper.unmount()
  })

  it('14f. Page integration: strategy_combination_hit_rate from API propagates to summary cards and portfolio tab', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const summaryCardText = wrapper.get('[data-testid="strategy-intelligence-metrics-grid"]').text()
    expect(summaryCardText).toContain('NOT_AVAILABLE')
    expect(summaryCardText).toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')

    const portfolioTab = wrapper.findAll('button[role="tab"]')[1]
    await portfolioTab.trigger('click')
    await flushPromises()

    const portfolioText = wrapper.text()
    expect(portfolioText).toContain('Registry-wide Combination Evidence Boundary')
    expect(portfolioText).toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')
    expect(portfolioText).toContain('NOT_AVAILABLE')
    expect(portfolioText).toContain('ACTIVE_MULTITICKET_AGENT')
    expect(portfolioText).toContain('B649 (Big Lotto 6/49)')

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

  it('15b. D3 definition renders from the API response, not a pinned frontend constant', async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        return Promise.resolve(apiResponse(makeOverviewForGame('BIG_LOTTO')))
      }
      if (url.includes('/api/v1/strategy-evidence')) {
        return Promise.resolve(
          apiResponse(
            makeEvidence(undefined, {
              direction: 'MOCKED_DIRECTION_CUSTOM',
              aggregation: 'MOCKED_AGGREGATION_CUSTOM',
              unit: 'MOCKED_UNIT_CUSTOM',
              definition_prose: 'Mocked prose unique to this test case.',
              authority_path: 'mocked/authority/path/d3.json',
            }),
          ),
        )
      }
      return Promise.resolve(apiResponse({}))
    })

    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    await wrapper.findAll('button[role="tab"]')[2].trigger('click')
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('MOCKED_DIRECTION_CUSTOM')
    expect(text).toContain('MOCKED_AGGREGATION_CUSTOM')
    expect(text).toContain('MOCKED_UNIT_CUSTOM')
    expect(text).toContain('Mocked prose unique to this test case.')
    expect(text).toContain('mocked/authority/path/d3.json')
    expect(text).not.toContain('DESCRIPTIVE_ONLY')
    expect(text).not.toContain('contracts/evidence/metric_definitions/d3.json')

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
    expect(wrapper.text()).toContain('Registry-wide Combination Evidence Boundary')
    expect(wrapper.text()).toContain('Selected Catalog Context')
    expect(wrapper.text()).toContain('P638 (Power Lotto 6/38)')

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
      expect(wrapper.text()).toContain('Registry-wide Combination Evidence Boundary')
      expect(wrapper.text()).toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')
      expect(wrapper.text()).toContain('B649 (Big Lotto 6/49)')
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
      expect(wrapper.text()).toContain('Registry-wide Combination Evidence Boundary')
      expect(wrapper.text()).toContain('P638 (Power Lotto 6/38)')
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
      expect(wrapper.text()).toContain('Registry-wide Combination Evidence Boundary')
      expect(wrapper.text()).toContain('T539 (Daily Cash 5/39)')
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
