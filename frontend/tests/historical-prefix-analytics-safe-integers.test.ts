import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getHistoricalPrefixAnalyticsRankings,
  getHistoricalPrefixAnalyticsReplay,
  getHistoricalPrefixAnalyticsStrategies,
  HistoricalPrefixAnalyticsRequestError,
} from '../src/api/historicalPrefixAnalytics'

const SAFE_MAX = Number.MAX_SAFE_INTEGER
const UNSAFE = SAFE_MAX + 1
const RANKINGS_URL = '/api/v1/historical-prefix-analytics/rankings'
const STRATEGIES_URL = '/api/v1/historical-prefix-analytics/strategies'
const REPLAY_PATH = '/api/v1/historical-prefix-analytics/strategies'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function metadata() {
  return {
    result_schema_version: 'historical-prefix-analytics-v1',
    source_import_identity_sha256: 'a'.repeat(64),
    source_manifest_sha256: 'b'.repeat(64),
    source_artifact_sha256: 'c'.repeat(64),
    dataset_identity: 'big-lotto-history-r1',
    dataset_sha256: 'd'.repeat(64),
    lottery_type: 'BIG_LOTTO',
    ranking_policy_id: 'historical-prefix-ranking-r1',
    historical_only_disclaimer_id: 'historical-only-r1',
  }
}

function identity(replicate = 2) {
  return {
    strategy_id: 'strategy/a',
    effective_strategy_id: 'strategy/a-effective',
    strategy_version: 'v 1',
    replicate,
    identity_kind: 'EXACT_REPLAY',
    governance_status: 'DESCRIPTIVE_ONLY',
    alias_of_strategy_id: null,
    equivalence_group: null,
    nested_prefix_supported: true,
  }
}

function summary() {
  const strategy = identity()
  return {
    identity: strategy,
    prefix_count: 1,
    status: 'READY',
    distinct_draw_count: 12,
    replay_ticket_count: 120,
    portfolio_success_count: 7,
    portfolio_success_rate: { numerator: 7, denominator: 12, is_available: true },
    ranking_eligible: true,
    ranking_exclusion_reason: null,
  }
}

function rankings() {
  const strategy = identity()
  return {
    metadata: metadata(),
    top_k: 20,
    groups: [
      {
        prefix_count: 1,
        status: 'RANKED',
        total_candidate_count: 1,
        requested_top_k: 20,
        candidates: [
          {
            rank: 1,
            identity: strategy,
            summary: summary(),
            tie_break_provenance: ['server-policy-order'],
          },
        ],
      },
    ],
  }
}

function overview() {
  return {
    metadata: metadata(),
    prefix_count: 10,
    total_count: 1,
    summaries: [summary()],
  }
}

function replay() {
  const strategy = identity()
  return {
    metadata: metadata(),
    strategy,
    prefix_count: 2,
    total_count: 1,
    limit: 20,
    offset: 0,
    items: [
      {
        identity: strategy,
        prefix_count: 2,
        prefix_ticket_count: 2,
        included_ticket_positions: [1, 2],
        best_single_main_hit_count: 4,
        best_single_ticket_position: 1,
        total_main_hit_count: 7,
        portfolio_success: false,
        m3plus: true,
        m4plus: false,
        m5plus: false,
        m6: false,
        special_hit: false,
        target: {
          draw_number: 10,
          draw_date: '2026-01-01',
          draw_sha256: 'e'.repeat(64),
        },
        cutoff: {
          draw_number: 9,
          draw_date: '2025-12-25',
          draw_sha256: 'f'.repeat(64),
        },
      },
    ],
  }
}

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function setAtPath(root: Record<string, unknown>, path: (string | number)[], value: unknown): void {
  let current: unknown = root
  for (const key of path.slice(0, -1)) {
    if (Array.isArray(current)) current = current[key as number]
    else if (isRecord(current)) current = current[key as string]
    else throw new Error(`Invalid test fixture path: ${path.join('.')}`)
  }

  const finalKey = path.at(-1)
  if (finalKey === undefined) throw new Error('A fixture path cannot be empty')
  if (Array.isArray(current)) current[finalKey as number] = value
  else if (isRecord(current)) current[finalKey as string] = value
  else throw new Error(`Invalid test fixture path: ${path.join('.')}`)
}

function requestFor(endpoint: 'rankings' | 'overview' | 'replay') {
  if (endpoint === 'rankings') return getHistoricalPrefixAnalyticsRankings(undefined, { top_k: 20 })
  if (endpoint === 'overview') return getHistoricalPrefixAnalyticsStrategies(10)
  return getHistoricalPrefixAnalyticsReplay(identity(), { prefix_count: 2, limit: 20, offset: 0 })
}

const unsafeResponseFields: {
  name: string
  endpoint: 'rankings' | 'overview' | 'replay'
  path: (string | number)[]
}[] = [
  { name: 'rankings top_k', endpoint: 'rankings', path: ['top_k'] },
  { name: 'rankings group prefix_count', endpoint: 'rankings', path: ['groups', 0, 'prefix_count'] },
  { name: 'rankings total_candidate_count', endpoint: 'rankings', path: ['groups', 0, 'total_candidate_count'] },
  { name: 'rankings requested_top_k', endpoint: 'rankings', path: ['groups', 0, 'requested_top_k'] },
  { name: 'candidate rank', endpoint: 'rankings', path: ['groups', 0, 'candidates', 0, 'rank'] },
  { name: 'candidate replicate', endpoint: 'rankings', path: ['groups', 0, 'candidates', 0, 'identity', 'replicate'] },
  { name: 'summary prefix_count', endpoint: 'rankings', path: ['groups', 0, 'candidates', 0, 'summary', 'prefix_count'] },
  { name: 'distinct_draw_count', endpoint: 'rankings', path: ['groups', 0, 'candidates', 0, 'summary', 'distinct_draw_count'] },
  { name: 'replay_ticket_count', endpoint: 'rankings', path: ['groups', 0, 'candidates', 0, 'summary', 'replay_ticket_count'] },
  { name: 'portfolio_success_count', endpoint: 'rankings', path: ['groups', 0, 'candidates', 0, 'summary', 'portfolio_success_count'] },
  { name: 'ratio numerator', endpoint: 'rankings', path: ['groups', 0, 'candidates', 0, 'summary', 'portfolio_success_rate', 'numerator'] },
  { name: 'ratio denominator', endpoint: 'rankings', path: ['groups', 0, 'candidates', 0, 'summary', 'portfolio_success_rate', 'denominator'] },
  { name: 'overview total_count', endpoint: 'overview', path: ['total_count'] },
  { name: 'overview summary replicate', endpoint: 'overview', path: ['summaries', 0, 'identity', 'replicate'] },
  { name: 'overview summary prefix_count', endpoint: 'overview', path: ['summaries', 0, 'prefix_count'] },
  { name: 'overview distinct_draw_count', endpoint: 'overview', path: ['summaries', 0, 'distinct_draw_count'] },
  { name: 'overview replay_ticket_count', endpoint: 'overview', path: ['summaries', 0, 'replay_ticket_count'] },
  { name: 'overview portfolio_success_count', endpoint: 'overview', path: ['summaries', 0, 'portfolio_success_count'] },
  { name: 'overview ratio numerator', endpoint: 'overview', path: ['summaries', 0, 'portfolio_success_rate', 'numerator'] },
  { name: 'overview ratio denominator', endpoint: 'overview', path: ['summaries', 0, 'portfolio_success_rate', 'denominator'] },
  { name: 'replay strategy replicate', endpoint: 'replay', path: ['strategy', 'replicate'] },
  { name: 'replay total_count', endpoint: 'replay', path: ['total_count'] },
  { name: 'replay limit', endpoint: 'replay', path: ['limit'] },
  { name: 'replay offset', endpoint: 'replay', path: ['offset'] },
  { name: 'item replicate', endpoint: 'replay', path: ['items', 0, 'identity', 'replicate'] },
  { name: 'prefix_ticket_count', endpoint: 'replay', path: ['items', 0, 'prefix_ticket_count'] },
  { name: 'included_ticket_positions', endpoint: 'replay', path: ['items', 0, 'included_ticket_positions', 0] },
  { name: 'best_single_main_hit_count', endpoint: 'replay', path: ['items', 0, 'best_single_main_hit_count'] },
  { name: 'best_single_ticket_position', endpoint: 'replay', path: ['items', 0, 'best_single_ticket_position'] },
  { name: 'total_main_hit_count', endpoint: 'replay', path: ['items', 0, 'total_main_hit_count'] },
  { name: 'target draw_number', endpoint: 'replay', path: ['items', 0, 'target', 'draw_number'] },
  { name: 'cutoff draw_number', endpoint: 'replay', path: ['items', 0, 'cutoff', 'draw_number'] },
]

const unsafeQueryRequests = [
  {
    name: 'top_k',
    request: () => getHistoricalPrefixAnalyticsRankings(undefined, { top_k: UNSAFE }),
  },
  {
    name: 'replicate',
    request: () => getHistoricalPrefixAnalyticsReplay({ ...identity(), replicate: UNSAFE }, { prefix_count: 2 }),
  },
  {
    name: 'limit',
    request: () => getHistoricalPrefixAnalyticsReplay(identity(), { prefix_count: 2, limit: UNSAFE }),
  },
  {
    name: 'offset',
    request: () => getHistoricalPrefixAnalyticsReplay(identity(), { prefix_count: 2, offset: UNSAFE }),
  },
]

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('Historical Prefix Analytics safe integer contract', () => {
  it.each(unsafeResponseFields)('rejects unsafe response integer: $name', async ({ endpoint, path }) => {
    const payload = endpoint === 'rankings' ? rankings() : endpoint === 'overview' ? overview() : replay()
    setAtPath(payload, path, UNSAFE)
    fetchMock.mockResolvedValue(jsonResponse(payload))

    await expect(requestFor(endpoint)).rejects.toMatchObject({
      name: 'HistoricalPrefixAnalyticsRequestError',
      status: 502,
      message: expect.stringContaining('does not match the OpenAPI contract'),
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it.each(unsafeQueryRequests)('rejects unsafe query integer $name before fetch', async ({ request }) => {
    fetchMock.mockResolvedValue(jsonResponse(rankings()))

    await expect(request()).rejects.toBeInstanceOf(HistoricalPrefixAnalyticsRequestError)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([-1, 1.5])('rejects negative and fractional response counts (%s)', async (invalid) => {
    const payload = overview()
    setAtPath(payload, ['total_count'], invalid)
    fetchMock.mockResolvedValue(jsonResponse(payload))

    await expect(getHistoricalPrefixAnalyticsStrategies(10)).rejects.toBeInstanceOf(
      HistoricalPrefixAnalyticsRequestError,
    )
  })

  it('accepts zero and Number.MAX_SAFE_INTEGER without coercing exact ratio fields', async () => {
    const maxPayload = rankings()
    for (const path of [
      ['top_k'],
      ['groups', 0, 'total_candidate_count'],
      ['groups', 0, 'requested_top_k'],
      ['groups', 0, 'candidates', 0, 'rank'],
      ['groups', 0, 'candidates', 0, 'identity', 'replicate'],
      ['groups', 0, 'candidates', 0, 'summary', 'distinct_draw_count'],
      ['groups', 0, 'candidates', 0, 'summary', 'replay_ticket_count'],
      ['groups', 0, 'candidates', 0, 'summary', 'portfolio_success_count'],
      ['groups', 0, 'candidates', 0, 'summary', 'portfolio_success_rate', 'numerator'],
      ['groups', 0, 'candidates', 0, 'summary', 'portfolio_success_rate', 'denominator'],
    ]) setAtPath(maxPayload, path, SAFE_MAX)
    fetchMock.mockResolvedValue(jsonResponse(maxPayload))

    const accepted = await getHistoricalPrefixAnalyticsRankings()
    expect(accepted.top_k).toBe(SAFE_MAX)
    expect(accepted.groups[0]?.candidates[0]?.summary.portfolio_success_rate).toEqual({
      numerator: SAFE_MAX,
      denominator: SAFE_MAX,
      is_available: true,
    })

    const zeroPayload = overview()
    setAtPath(zeroPayload, ['total_count'], 0)
    setAtPath(zeroPayload, ['summaries', 0, 'portfolio_success_rate'], {
      numerator: 0,
      denominator: 0,
      is_available: true,
    })
    fetchMock.mockResolvedValue(jsonResponse(zeroPayload))
    const zeroAccepted = await getHistoricalPrefixAnalyticsStrategies(10)
    expect(zeroAccepted.total_count).toBe(0)
    expect(zeroAccepted.summaries[0]?.portfolio_success_rate).toEqual({
      numerator: 0,
      denominator: 0,
      is_available: true,
    })
  })

  it('preserves null identity fields, false flags, and empty response lists', async () => {
    const emptyRankings = { metadata: metadata(), top_k: 0, groups: [] }
    fetchMock.mockResolvedValue(jsonResponse(emptyRankings))
    expect((await getHistoricalPrefixAnalyticsRankings()).groups).toEqual([])

    const emptyOverview = { metadata: metadata(), prefix_count: 10, total_count: 0, summaries: [] }
    fetchMock.mockResolvedValue(jsonResponse(emptyOverview))
    expect((await getHistoricalPrefixAnalyticsStrategies(10)).summaries).toEqual([])

    const emptyReplay = {
      metadata: metadata(),
      strategy: identity(0),
      prefix_count: 2,
      total_count: 0,
      limit: 0,
      offset: 0,
      items: [],
    }
    fetchMock.mockResolvedValue(jsonResponse(emptyReplay))
    const acceptedReplay = await getHistoricalPrefixAnalyticsReplay(identity(0), { prefix_count: 2, limit: 0, offset: 0 })
    expect(acceptedReplay.items).toEqual([])
    expect(acceptedReplay.strategy.alias_of_strategy_id).toBeNull()
    expect(acceptedReplay.strategy.equivalence_group).toBeNull()

    fetchMock.mockResolvedValue(jsonResponse(replay()))
    const replayWithFalseFlags = await getHistoricalPrefixAnalyticsReplay(identity(), { prefix_count: 2 })
    expect(replayWithFalseFlags.items[0]).toMatchObject({
      portfolio_success: false,
      m4plus: false,
      m5plus: false,
      m6: false,
      special_hit: false,
    })
  })

  it('keeps legal query URLs and strategy identity encoding unchanged', async () => {
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === RANKINGS_URL) return Promise.resolve(jsonResponse(rankings()))
      if (url.pathname === STRATEGIES_URL) return Promise.resolve(jsonResponse(overview()))
      if (url.pathname.endsWith('/replay')) return Promise.resolve(jsonResponse(replay()))
      return Promise.resolve(jsonResponse({}))
    })

    await getHistoricalPrefixAnalyticsRankings(undefined, { top_k: 20 })
    await getHistoricalPrefixAnalyticsStrategies(10)
    await getHistoricalPrefixAnalyticsReplay(identity(), { prefix_count: 2, limit: 10, offset: 20 })

    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
      `${RANKINGS_URL}?top_k=20`,
      `${STRATEGIES_URL}?prefix_count=10`,
      `${REPLAY_PATH}/strategy%2Fa/v%201/2/replay?prefix_count=2&limit=10&offset=20`,
    ])
  })
})
