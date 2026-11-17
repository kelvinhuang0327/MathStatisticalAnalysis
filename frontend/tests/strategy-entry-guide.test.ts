// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { StrategyOverviewResponse } from '../src/api/strategies'
import type { StrategyEvidenceResponse } from '../src/api/strategyEvidence'
import StrategyIntelligencePage from '../src/features/strategy-intelligence/StrategyIntelligencePage.vue'

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
  definition_prose:
    'D3 is reserved for a future Owner-approved primary ranking metric. No formula, threshold, or ranking direction is committed by this task. Any result declaring VALUE_PRESENT against this definition is a METRIC_DEFINITION_FAILURE.',
  authority_path: 'contracts/evidence/metric_definitions/d3.json',
} satisfies StrategyEvidenceResponse['d3']['definition']

function makeOverview(): StrategyOverviewResponse {
  return {
    items: [
      {
        strategy_id: 'b649_social_wisdom_anti_popularity',
        display_name: 'B649 Social Wisdom Anti-Popularity',
        version: 'v0.1',
        supported_lottery_types: ['BIG_LOTTO'],
        minimum_history: 1,
        lifecycle_status: 'OBSERVATION',
        executable: false,
        provenance: ['legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f'],
      },
    ],
    summary: {
      total: 1,
      executable_count: 0,
      metadata_only_count: 1,
      lifecycle_counts: {
        IDEA: 0,
        OBSERVATION: 1,
        ONLINE: 0,
        REJECTED: 0,
        RETIRED: 0,
      },
      lottery_type_counts: {
        DAILY_539: 0,
        BIG_LOTTO: 1,
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

function makeEvidence(): StrategyEvidenceResponse {
  return {
    items: [
      {
        strategy_id: 'b649_social_wisdom_anti_popularity',
        strategy_version: 'v0.1',
        replicate: 'NOT_APPLICABLE',
        display_name: 'B649 Social Wisdom Anti-Popularity',
        lifecycle_status: 'OBSERVATION',
        executable: false,
        supported_lottery_types: ['BIG_LOTTO'],
        minimum_history: 1,
        provenance: ['legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f'],
        adapter_available: true,
        registration_status: 'CANONICAL_EVIDENCE_REGISTERED',
        definition_status: 'DEFINITION_AVAILABLE',
        verification_status: 'EVIDENCE_VERIFIED',
        unavailable_reason_code: null,
      },
    ],
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
      definition: { ...CANONICAL_D3_DEFINITION },
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

describe('Strategy Exploration Entry Guide (AC1 - AC6)', () => {
  it('AC1: provides four canonical navigation entries with exact supported routes', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const guide = wrapper.get('[data-testid="strategy-entry-guide"]')
    expect(guide.exists()).toBe(true)

    // Check four required links
    const strategiesLink = wrapper.get('[data-testid="guide-link-strategies"]')
    expect(strategiesLink.attributes('href')).toBe('#/strategies')
    expect(strategiesLink.text()).toContain('Strategy Catalog')

    const replayLink = wrapper.get('[data-testid="guide-link-replay-history"]')
    expect(replayLink.attributes('href')).toBe('#/replay-history')
    expect(replayLink.text()).toContain('Replay History')

    const forecastResearchLink = wrapper.get('[data-testid="guide-link-strategy-forecast-research"]')
    expect(forecastResearchLink.attributes('href')).toBe('#/strategy-forecast-research')
    expect(forecastResearchLink.text()).toContain('B649 Forecast Research')

    const evidenceLink = wrapper.get('[data-testid="guide-link-strategy-evidence"]')
    expect(evidenceLink.attributes('href')).toBe('#/strategy-evidence')
    expect(evidenceLink.text()).toContain('Strategy Evidence')

    // Prohibit fictitious routes or empty links
    const allLinks = guide.findAll('a')
    expect(allLinks).toHaveLength(4)
    for (const link of allLinks) {
      const href = link.attributes('href')
      expect(href).toBeDefined()
      expect(href).not.toBe('')
      expect(href).not.toBe('#')
      expect(href).not.toContain('strategy-detail')
    }

    wrapper.unmount()
  })

  it('AC2: clarifies scope boundaries without misleading totality claims', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const guideText = wrapper.get('[data-testid="strategy-entry-guide"]').text()

    // Scope notice clarifies in-code overview vs formal/research union
    expect(guideText).toContain('not a complete union of the formal database and all research workspaces')
    expect(guideText).toContain('not project-wide totals')

    // Replay History clarifies Run and target range selection requirement
    const replayCardText = wrapper.get('[data-testid="guide-link-replay-history"]').text()
    expect(replayCardText).toContain('Requires selecting a specific Run and target draw range')
    expect(replayCardText).toContain('does not automatically search or aggregate all Runs')

    // B649 Research clarifies dedicated scope, not a cross-game leaderboard
    const b649CardText = wrapper.get('[data-testid="guide-link-strategy-forecast-research"]').text()
    expect(b649CardText).toContain('Dedicated to B649 research comparisons only')
    expect(b649CardText).toContain('not a cross-game leaderboard across all three lottery types')

    wrapper.unmount()
  })

  it('AC3: strictly separates capabilities and adds zero action buttons', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const guide = wrapper.get('[data-testid="strategy-entry-guide"]')
    const guideText = guide.text()

    // Capability separations
    expect(guideText).toContain('Catalog availability does not imply execution capability')
    expect(guideText).toContain('Historical replay does not imply live execution')
    expect(guideText).toContain('Retrospective comparisons do not represent live predictions or betting recommendations')
    expect(guideText).toContain('does not certify all underlying sources as verified or trustworthy')

    // Prohibit execution, backfill, recompute, or prediction action buttons
    const buttons = guide.findAll('button')
    expect(buttons).toHaveLength(0)

    const allButtonsInPage = wrapper.findAll('button')
    const buttonTexts = allButtonsInPage.map((b) => b.text().toLowerCase())
    for (const text of buttonTexts) {
      expect(text).not.toContain('execute')
      expect(text).not.toContain('backfill')
      expect(text).not.toContain('recompute')
      expect(text).not.toContain('predict')
    }

    wrapper.unmount()
  })

  it('AC4: preserves existing tab switching, game selection, and makes no extra API calls', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    // Verify initial API calls: 1 overview + 1 evidence
    const initialOverviewCalls = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes('/api/v1/strategy-overview'),
    ).length
    const initialEvidenceCalls = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes('/api/v1/strategy-evidence'),
    ).length
    expect(initialOverviewCalls).toBe(1)
    expect(initialEvidenceCalls).toBe(1)

    // Tab switching still works
    const tabs = wrapper.findAll('button[role="tab"]')
    expect(tabs).toHaveLength(3)

    await tabs[1].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Portfolio Hit Rate')

    await tabs[2].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('D3 SSOT')

    // Game switching still works
    const p638Btn = wrapper.get('[data-testid="game-selector-p638"]')
    await p638Btn.trigger('click')
    await flushPromises()
    expect(p638Btn.attributes('aria-checked')).toBe('true')

    wrapper.unmount()
  })

  it('AC5: remains visible and accessible during loading and error states', async () => {
    // 1. Loading state test
    let resolveOverview: ((val: Response) => void) | undefined
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/strategy-overview')) {
        return new Promise<Response>((resolve) => {
          resolveOverview = resolve
        })
      }
      return Promise.resolve(apiResponse(makeEvidence()))
    })

    const loadingWrapper = mount(StrategyIntelligencePage)
    // While loading (before resolveOverview)
    expect(loadingWrapper.find('[data-testid="strategy-entry-guide"]').exists()).toBe(true)
    expect(loadingWrapper.findAll('[data-testid="strategy-entry-guide"] a')).toHaveLength(4)
    expect(loadingWrapper.find('.skeleton-loader').exists()).toBe(true)

    // Resolve to cleanup
    resolveOverview?.(apiResponse(makeOverview()))
    await flushPromises()
    loadingWrapper.unmount()

    // 2. Error state test
    fetchMock.mockImplementation(() => {
      return Promise.resolve(apiResponse({ message: 'Internal Server Error' }, 500))
    })

    const errorWrapper = mount(StrategyIntelligencePage)
    await flushPromises()
    expect(errorWrapper.find('.error-state').exists()).toBe(true)
    expect(errorWrapper.find('[data-testid="strategy-entry-guide"]').exists()).toBe(true)
    expect(errorWrapper.findAll('[data-testid="strategy-entry-guide"] a')).toHaveLength(4)
    errorWrapper.unmount()
  })

  it('AC5 & AC6: semantic links with visible text, keyboard navigable, zero CJK, no forbidden claims', async () => {
    const wrapper = mount(StrategyIntelligencePage)
    await flushPromises()

    const guide = wrapper.get('[data-testid="strategy-entry-guide"]')
    expect(guide.element.tagName.toLowerCase()).toBe('nav')
    expect(guide.attributes('aria-label')).toBe('Strategy Navigation Guide')

    const links = guide.findAll('a')
    for (const link of links) {
      // Must have visible title and visible purpose (not just icon)
      const title = link.find('.guide-card__title')
      expect(title.exists()).toBe(true)
      expect(title.text().length).toBeGreaterThan(0)

      const purpose = link.find('.guide-card__purpose')
      expect(purpose.exists()).toBe(true)
      expect(purpose.text().length).toBeGreaterThan(0)

      const boundary = link.find('.guide-card__boundary')
      expect(boundary.exists()).toBe(true)
      expect(boundary.text().length).toBeGreaterThan(0)
    }

    // Zero CJK characters
    const cjkRegex = /[\u4e00-\u9fff\u3400-\u4dbf]/g
    const guideText = guide.text()
    expect(guideText.match(cjkRegex) || []).toHaveLength(0)

    // No forbidden predictive claims
    const upperText = guideText.toUpperCase()
    expect(upperText).not.toContain('BEST FUTURE STRATEGY')
    expect(upperText).not.toContain('RECOMMENDED BET')
    expect(upperText).not.toContain('HIGH WIN PROBABILITY')
    expect(upperText).not.toContain('GUARANTEED')

    wrapper.unmount()
  })
})
