// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  HistoricalPrefixAnalyticsMetadata,
  HistoricalPrefixAnalyticsOverviewPrefixCount,
  HistoricalPrefixAnalyticsOverviewResponse,
  HistoricalPrefixAnalyticsRankingsResponse,
  HistoricalPrefixAnalyticsReplayPrefixCount,
  HistoricalPrefixAnalyticsReplayResponse,
  HistoricalPrefixAnalyticsStrategyIdentity,
  HistoricalPrefixAnalyticsStrategySummary,
} from '../src/api/historicalPrefixAnalytics'
import PrefixAnalyticsPanel from '../src/features/historical-success-windows/PrefixAnalyticsPanel.vue'
import HistoricalSuccessWindowsPage from '../src/features/historical-success-windows/HistoricalSuccessWindowsPage.vue'
import { apiResponse, deferred, makeRunPage } from './historical-success-windows-fixtures'

const RANKINGS_URL = '/api/v1/historical-prefix-analytics/rankings'
const STRATEGIES_URL = '/api/v1/historical-prefix-analytics/strategies'
const SOURCE_IMPORT_ID = 'a'.repeat(64)
const META: HistoricalPrefixAnalyticsMetadata = {
  result_schema_version: 'historical-prefix-analytics-v1',
  source_import_identity_sha256: SOURCE_IMPORT_ID,
  source_manifest_sha256: 'b'.repeat(64),
  source_artifact_sha256: 'c'.repeat(64),
  dataset_identity: 'big-lotto-history-r1',
  dataset_sha256: 'd'.repeat(64),
  lottery_type: 'BIG_LOTTO',
  ranking_policy_id: 'historical-prefix-ranking-r1',
  historical_only_disclaimer_id: 'historical-only-r1',
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function makeIdentity(
  strategyId: string,
  version = 'v 1',
  replicate = 2,
): HistoricalPrefixAnalyticsStrategyIdentity {
  return {
    strategy_id: strategyId,
    effective_strategy_id: `${strategyId}-effective`,
    strategy_version: version,
    replicate,
    identity_kind: 'EXACT_REPLAY',
    governance_status: 'DESCRIPTIVE_ONLY',
    alias_of_strategy_id: null,
    equivalence_group: null,
    nested_prefix_supported: true,
  }
}

function makeSummary(
  identity: HistoricalPrefixAnalyticsStrategyIdentity,
  prefixCount = 10,
  ratio: { numerator: number; denominator: number; is_available: boolean } = {
    numerator: 7,
    denominator: 12,
    is_available: true,
  },
): HistoricalPrefixAnalyticsStrategySummary {
  return {
    identity,
    prefix_count: prefixCount,
    status: 'READY',
    distinct_draw_count: 12,
    replay_ticket_count: 120,
    portfolio_success_count: 7,
    portfolio_success_rate: ratio,
    ranking_eligible: true,
    ranking_exclusion_reason: null,
  } as unknown as HistoricalPrefixAnalyticsStrategySummary
}

function makeRankings(
  identities: HistoricalPrefixAnalyticsStrategyIdentity[] = [makeIdentity('strategy/a')],
): HistoricalPrefixAnalyticsRankingsResponse {
  return {
    metadata: META,
    top_k: 20,
    groups: [
      {
        prefix_count: 1,
        status: identities.length === 0 ? 'NO_ELIGIBLE_STRATEGIES' : 'RANKED',
        total_candidate_count: identities.length,
        requested_top_k: 20,
        candidates: identities.map((identity, index) => ({
          rank: index + 1,
          identity,
          summary: makeSummary(identity, 1),
          tie_break_provenance: ['server-policy-order'],
        })),
      },
    ],
  }
}

function makeOverview(
  prefixCount: HistoricalPrefixAnalyticsOverviewPrefixCount = 10,
  identities: HistoricalPrefixAnalyticsStrategyIdentity[] = [makeIdentity('strategy/a')],
  ratio?: { numerator: number; denominator: number; is_available: boolean },
): HistoricalPrefixAnalyticsOverviewResponse {
  return {
    metadata: META,
    prefix_count: prefixCount,
    summaries: identities.map((identity) => makeSummary(identity, prefixCount, ratio)),
    total_count: identities.length,
  }
}

function makeReplay(
  identity: HistoricalPrefixAnalyticsStrategyIdentity = makeIdentity('strategy/a'),
  prefixCount: HistoricalPrefixAnalyticsReplayPrefixCount = 10,
  offset = 0,
  limit = 20,
  totalCount = 1,
): HistoricalPrefixAnalyticsReplayResponse {
  const item = {
    identity,
    prefix_count: prefixCount,
    prefix_ticket_count: prefixCount,
    included_ticket_positions: Array.from({ length: prefixCount }, (_, index) => index + 1),
    best_single_main_hit_count: 4,
    best_single_ticket_position: 3,
    total_main_hit_count: 16,
    portfolio_success: true,
    m3plus: true,
    m4plus: true,
    m5plus: false,
    m6: false,
    special_hit: false,
    target: {
      draw_number: offset + 1,
      draw_date: '2026-01-01',
      draw_sha256: String(offset + 1).padStart(64, '0'),
    },
    cutoff: {
      draw_number: offset,
      draw_date: '2025-12-25',
      draw_sha256: String(offset).padStart(64, '0'),
    },
  }
  return {
    metadata: META,
    strategy: identity,
    prefix_count: prefixCount,
    items: totalCount === 0 ? [] : [item],
    total_count: totalCount,
    limit,
    offset,
  } as unknown as HistoricalPrefixAnalyticsReplayResponse
}

function responseFor(input: RequestInfo | URL): Response {
  const url = new URL(String(input), 'http://localhost')
  if (url.pathname === RANKINGS_URL) return apiResponse(makeRankings())
  if (url.pathname === STRATEGIES_URL) {
    const count = Number(url.searchParams.get('prefix_count')) as HistoricalPrefixAnalyticsOverviewPrefixCount
    return apiResponse(makeOverview(count))
  }
  if (url.pathname.endsWith('/replay')) return apiResponse(makeReplay())
  return apiResponse({ message: 'unexpected request' }, 404)
}

async function mountOpenPanel(): Promise<ReturnType<typeof mount>> {
  fetchMock.mockImplementation((input) => Promise.resolve(responseFor(input)))
  const wrapper = mount(PrefixAnalyticsPanel)
  await flushPromises()
  await wrapper.get('.prefix-analytics__toggle').trigger('click')
  await flushPromises()
  return wrapper
}

async function chooseOverviewStrategy(
  wrapper: ReturnType<typeof mount>,
  strategyId: string,
): Promise<void> {
  const row = wrapper
    .findAll('.prefix-analytics__section[aria-labelledby="prefix-overview-title"] tbody tr')
    .find((candidate) => candidate.text().includes(strategyId))
  if (!row) throw new Error(`Overview row not found for ${strategyId}`)
  await row.get('button').trigger('click')
}

function readUrl(callIndex: number): URL {
  return new URL(String(fetchMock.mock.calls[callIndex]?.[0]), 'http://localhost')
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('Historical Prefix Analytics panel', () => {
  it('is a separate expandable section on the existing page and requests rankings without prefix_count', async () => {
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/v1/historical-results/runs') {
        return Promise.resolve(apiResponse(makeRunPage({ items: [], total_count: 0 })))
      }
      return Promise.resolve(responseFor(input))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Historical Success Windows')
    expect(wrapper.text()).toContain('Historical Prefix Analytics')
    expect(wrapper.get('[data-testid="prefix-analytics-provider-status"]').text()).toContain('NOT IMPLEMENTED')
    expect(wrapper.get('[data-testid="prefix-analytics-provider-status"]').text()).toContain('SOURCE_MISSING')
    expect(wrapper.get('.prefix-analytics__toggle').attributes('aria-expanded')).toBe('false')

    await wrapper.get('.prefix-analytics__toggle').trigger('click')
    await flushPromises()

    const rankingCall = fetchMock.mock.calls.find((call) => String(call[0]).includes(RANKINGS_URL))
    const overviewCall = fetchMock.mock.calls.find((call) => String(call[0]).startsWith(STRATEGIES_URL))
    expect(rankingCall?.[1]?.method).toBe('GET')
    expect(String(rankingCall?.[0])).toBe(RANKINGS_URL)
    expect(overviewCall?.[1]?.method).toBe('GET')
    expect(readUrl(fetchMock.mock.calls.indexOf(rankingCall!)).searchParams.has('prefix_count')).toBe(false)
    expect(new URL(String(overviewCall?.[0]), 'http://localhost').searchParams.get('prefix_count')).toBe('10')
    expect(wrapper.text()).toContain('Source import identity')
    expect(wrapper.text()).toContain('a'.repeat(64))
    expect(wrapper.text()).toContain('SUCCESS_WITH_DATA')
    expect(wrapper.text()).toContain('PREFIX_PORTFOLIO_SUCCESS')
    expect(wrapper.text()).toContain('OFFICIAL_ANY_PRIZE is a distinct event')
    expect(wrapper.text()).toContain('separate from the import-based Historical Prefix Success Windows results')
    wrapper.unmount()
  })

  it('limits overview prefixes to 10, 15, and 20 and shows the exact ratio without converting it', async () => {
    fetchMock.mockImplementation((input) => Promise.resolve(responseFor(input)))
    const wrapper = await mountOpenPanel()
    const prefixSelect = wrapper.get('select[name="prefix-analytics-overview-prefix"]')
    expect(prefixSelect.findAll('option').map((option) => option.element.value)).toEqual([
      '10',
      '15',
      '20',
    ])

    for (const prefix of ['15', '20']) {
      await prefixSelect.setValue(prefix)
      await flushPromises()
      const overviewCalls = fetchMock.mock.calls.filter((call) =>
        String(call[0]).startsWith(STRATEGIES_URL),
      )
      expect(overviewCalls.map((call) => readUrl(fetchMock.mock.calls.indexOf(call)).searchParams.get('prefix_count')))
        .toEqual(['10', ...overviewCalls.slice(1).map((call) => readUrl(fetchMock.mock.calls.indexOf(call)).searchParams.get('prefix_count'))])
      expect(readUrl(fetchMock.mock.calls.indexOf(overviewCalls.at(-1)!)).searchParams.get('prefix_count'))
        .toBe(prefix)
    }
    expect(wrapper.text()).toContain('7 / 12')
    expect(wrapper.text()).not.toContain('%')
    wrapper.unmount()

    fetchMock.mockReset()
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === RANKINGS_URL) return Promise.resolve(apiResponse(makeRankings()))
      if (url.pathname === STRATEGIES_URL) {
        return Promise.resolve(apiResponse(makeOverview(10, [makeIdentity('unavailable')], {
          numerator: 0,
          denominator: 0,
          is_available: true,
        })))
      }
      return Promise.resolve(responseFor(input))
    })
    const unavailable = mount(PrefixAnalyticsPanel)
    await flushPromises()
    await unavailable.get('.prefix-analytics__toggle').trigger('click')
    await flushPromises()
    expect(unavailable.text()).toContain('Unavailable')
    expect(unavailable.text()).toContain('ZERO_DENOMINATOR')
    expect(unavailable.text()).not.toContain('0 / 0')
    expect(unavailable.text()).not.toContain('0%')
    unavailable.unmount()
  })

  it('uses the selected strategy identity and sends replay pagination from the API controls', async () => {
    const identity = makeIdentity('strategy/a', 'v 1', 2)
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.endsWith('/replay')) {
        const offset = Number(url.searchParams.get('offset'))
        const limit = Number(url.searchParams.get('limit'))
        return Promise.resolve(apiResponse(makeReplay(identity, 2, offset, limit, 25)))
      }
      if (url.pathname === RANKINGS_URL) return Promise.resolve(apiResponse(makeRankings([identity])))
      if (url.pathname === STRATEGIES_URL) return Promise.resolve(apiResponse(makeOverview(10, [identity])))
      return Promise.resolve(responseFor(input))
    })
    const wrapper = mount(PrefixAnalyticsPanel)
    await flushPromises()
    await wrapper.get('.prefix-analytics__toggle').trigger('click')
    await flushPromises()
    await chooseOverviewStrategy(wrapper, identity.strategy_id)
    await wrapper.get('select[name="prefix-analytics-replay-prefix"]').setValue('2')
    await wrapper.get('select[name="prefix-analytics-replay-limit"]').setValue('10')
    expect(wrapper.get('select[name="prefix-analytics-replay-prefix"]').findAll('option').map((option) => option.element.value))
      .toEqual(['1', '2', '3', '4', '5', '10', '15', '20'])
    await wrapper.get('form.prefix-analytics__replay-controls').trigger('submit')
    await flushPromises()

    let replayCalls = fetchMock.mock.calls.filter((call) => String(call[0]).includes('/replay?'))
    expect(replayCalls).toHaveLength(1)
    let replayUrl = new URL(String(replayCalls[0]?.[0]), 'http://localhost')
    expect(replayUrl.pathname).toBe(
      '/api/v1/historical-prefix-analytics/strategies/strategy%2Fa/v%201/2/replay',
    )
    expect(Object.fromEntries(replayUrl.searchParams)).toEqual({
      prefix_count: '2',
      limit: '10',
      offset: '0',
    })
    expect(replayCalls[0]?.[1]?.method).toBe('GET')
    expect(wrapper.text()).toContain('2 · 2 tickets')

    await wrapper.get('nav[aria-label="Prefix replay pages"] button:last-child').trigger('click')
    await flushPromises()
    replayCalls = fetchMock.mock.calls.filter((call) => String(call[0]).includes('/replay?'))
    replayUrl = new URL(String(replayCalls[1]?.[0]), 'http://localhost')
    expect(replayUrl.searchParams.get('offset')).toBe('10')
    expect(replayUrl.searchParams.get('limit')).toBe('10')
    expect(wrapper.text()).toContain('11–11 of 25')
    wrapper.unmount()
  })

  it.each([
    [404, 'That exact strategy, version, and replicate was not found.'],
    [422, 'The API rejected these prefix or pagination values.'],
    [503, 'API_UNAVAILABLE'],
    [500, 'HTTP_ERROR'],
  ])('shows the retry state for replay HTTP %s', async (status, message) => {
    const identity = makeIdentity('missing-strategy')
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.endsWith('/replay')) {
        return Promise.resolve(apiResponse({ message: 'API response detail', error_code: `HTTP_${status}` }, status))
      }
      if (url.pathname === RANKINGS_URL) return Promise.resolve(apiResponse(makeRankings([identity])))
      if (url.pathname === STRATEGIES_URL) return Promise.resolve(apiResponse(makeOverview(10, [identity])))
      return Promise.resolve(responseFor(input))
    })
    const wrapper = mount(PrefixAnalyticsPanel)
    await flushPromises()
    await wrapper.get('.prefix-analytics__toggle').trigger('click')
    await flushPromises()
    await chooseOverviewStrategy(wrapper, identity.strategy_id)
    await wrapper.get('form.prefix-analytics__replay-controls').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(message)
    expect(wrapper.get('[role="alert"]').text()).toContain(`HTTP_${status}`)
    expect(wrapper.get('[role="alert"]').text()).toContain('Retry replay')
    wrapper.unmount()
  })

  it('labels a missing source separately from HTTP and service failures', async () => {
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === RANKINGS_URL || url.pathname === STRATEGIES_URL) {
        return Promise.resolve(
          apiResponse(
            { message: 'Formal provider is not configured.', error_code: 'PREFIX_SOURCE_NOT_CONFIGURED' },
            503,
          ),
        )
      }
      return Promise.resolve(responseFor(input))
    })
    const wrapper = mount(PrefixAnalyticsPanel)
    await flushPromises()
    await wrapper.get('.prefix-analytics__toggle').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('SOURCE_NOT_CONFIGURED')
    expect(wrapper.text()).toContain('PREFIX_SOURCE_NOT_CONFIGURED')
    wrapper.unmount()
  })

  it('shows empty ranking, overview, and replay responses', async () => {
    const identity = makeIdentity('replay-empty')
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === RANKINGS_URL) return Promise.resolve(apiResponse(makeRankings([])))
      if (url.pathname === STRATEGIES_URL) return Promise.resolve(apiResponse(makeOverview(10, [])))
      if (url.pathname.endsWith('/replay')) return Promise.resolve(apiResponse(makeReplay(identity, 10, 0, 20, 0)))
      return Promise.resolve(responseFor(input))
    })
    const wrapper = mount(PrefixAnalyticsPanel)
    await flushPromises()
    await wrapper.get('.prefix-analytics__toggle').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('No eligible strategies were returned')
    expect(wrapper.text()).toContain('No strategy summaries were returned')
    expect(wrapper.text()).toContain('SUCCESS_EMPTY')
    wrapper.unmount()

    fetchMock.mockReset()
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === RANKINGS_URL) return Promise.resolve(apiResponse(makeRankings([identity])))
      if (url.pathname === STRATEGIES_URL) return Promise.resolve(apiResponse(makeOverview(10, [identity])))
      if (url.pathname.endsWith('/replay')) return Promise.resolve(apiResponse(makeReplay(identity, 10, 0, 20, 0)))
      return Promise.resolve(responseFor(input))
    })
    const replayPanel = mount(PrefixAnalyticsPanel)
    await flushPromises()
    await replayPanel.get('.prefix-analytics__toggle').trigger('click')
    await flushPromises()
    await chooseOverviewStrategy(replayPanel, identity.strategy_id)
    await replayPanel.get('form.prefix-analytics__replay-controls').trigger('submit')
    await flushPromises()
    expect(replayPanel.text()).toContain('The replay API returned no rows for this page.')
    replayPanel.unmount()
  })

  it('ignores an older overview response after a rapid prefix selection change', async () => {
    const older = deferred<Response>()
    const newer = deferred<Response>()
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === RANKINGS_URL) return Promise.resolve(apiResponse(makeRankings()))
      if (url.pathname === STRATEGIES_URL) {
        return url.searchParams.get('prefix_count') === '10' ? older.promise : newer.promise
      }
      return Promise.resolve(responseFor(input))
    })
    const wrapper = mount(PrefixAnalyticsPanel)
    await flushPromises()
    await wrapper.get('.prefix-analytics__toggle').trigger('click')
    await wrapper.get('select[name="prefix-analytics-overview-prefix"]').setValue('15')

    newer.resolve(apiResponse(makeOverview(15, [makeIdentity('new-prefix-15')])));
    await flushPromises()
    older.resolve(apiResponse(makeOverview(10, [makeIdentity('stale-prefix-10')])));
    await flushPromises()

    expect(wrapper.text()).toContain('new-prefix-15')
    expect(wrapper.text()).not.toContain('stale-prefix-10')
    wrapper.unmount()
  })

  it('ignores replay results for an earlier strategy after a rapid identity change', async () => {
    const first = makeIdentity('strategy-first')
    const second = makeIdentity('strategy-second', 'v2', 3)
    const firstReplay = deferred<Response>()
    const secondReplay = deferred<Response>()
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === RANKINGS_URL) return Promise.resolve(apiResponse(makeRankings([first, second])))
      if (url.pathname === STRATEGIES_URL) return Promise.resolve(apiResponse(makeOverview(10, [first, second])))
      if (url.pathname.endsWith('/replay')) {
        return url.pathname.includes('strategy-first') ? firstReplay.promise : secondReplay.promise
      }
      return Promise.resolve(responseFor(input))
    })
    const wrapper = mount(PrefixAnalyticsPanel)
    await flushPromises()
    await wrapper.get('.prefix-analytics__toggle').trigger('click')
    await flushPromises()
    await chooseOverviewStrategy(wrapper, first.strategy_id)
    await wrapper.get('form.prefix-analytics__replay-controls').trigger('submit')
    await chooseOverviewStrategy(wrapper, second.strategy_id)
    await wrapper.get('form.prefix-analytics__replay-controls').trigger('submit')

    secondReplay.resolve(apiResponse(makeReplay(second)))
    await flushPromises()
    firstReplay.resolve(apiResponse(makeReplay(first)))
    await flushPromises()

    const replayTable = wrapper.get('.prefix-analytics__replay-table')
    expect(replayTable.text()).toContain(second.strategy_id)
    expect(replayTable.text()).not.toContain(first.strategy_id)
    wrapper.unmount()
  })
})
