import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  B649RecordsRequestError,
  fetchB649ExactNativeRecords,
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
} from '../src/api/b649MultiTicketRecords'

const SAFE_MAX = 9007199254740991
const UNSAFE = 9007199254740992
const DISCLAIMER =
  '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。'
const SHA = 'a'.repeat(64)
const DECIMAL_18 = '0.123456789012345678'

type JsonRecord = Record<string, any>
type UnsafeResponseCase = {
  label: string
  payload: () => JsonRecord
  path: string[]
  request: () => Promise<unknown>
}

function prizeCounts(overrides: JsonRecord = {}) {
  return {
    first: 0,
    second: 0,
    third: 0,
    fourth: 0,
    fifth: 0,
    sixth: 0,
    seventh: 0,
    general: 0,
    ...overrides,
  }
}

function summaryPayload(progress: JsonRecord = {}, extra: JsonRecord = {}): JsonRecord {
  return {
    progress: {
      total_strategy_count: 0,
      reproduced_count: 0,
      backtested_count: 0,
      closed_count: 0,
      duplicate_alias_count: 0,
      owner_decision_required_count: 0,
      uncompleted_count: 0,
      ...progress,
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
    method_families: [],
    reproduction_statuses: ['BACKTESTED', 'CLOSED_UNEXECUTABLE', 'DUPLICATE_ALIAS'],
    catalog_sha256: SHA,
    records_available: true,
    projection_sha256: null,
    source_report_count: null,
    research_disclaimer: DISCLAIMER,
    ...extra,
  }
}

function multiTicketRecord(overrides: JsonRecord = {}): JsonRecord {
  return {
    strategy_id: 'strategy_1',
    strategy_version: 'v1',
    legacy_method_id: 'tools/strategy.py',
    source_path: 'src/strategy.py',
    method_family: 'statistical',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: 10,
    window: 'FULL',
    criterion: 'M3_PLUS',
    rank: 1,
    official_rank: 1,
    official_any_prize_count: 0,
    official_any_prize_rate: null,
    official_random_baseline_probability: null,
    official_random_baseline_delta: null,
    unranked_reason: null,
    success_count: 0,
    effective_backtest_draw_count: 0,
    successful_execution_count: 0,
    historical_success_rate: null,
    random_baseline_success_rate: null,
    random_baseline_rate_difference: null,
    coverage: null,
    window_available_draws: 0,
    window_requested_draws: 0,
    window_complete: false,
    official_prize_counts: prizeCounts(),
    no_prize_count: 0,
    report_sha256: null,
    report_file_sha256: null,
    catalog_sha256: SHA,
    ...overrides,
  }
}

function multiTicketPage(options: JsonRecord = {}): JsonRecord {
  const { item = multiTicketRecord(), items = [item], ...pageOverrides } = options
  return {
    items,
    total: items.length,
    limit: 25,
    offset: 0,
    prefix_count: 10,
    window: 'FULL',
    criterion: 'M3_PLUS',
    research_disclaimer: DISCLAIMER,
    ...pageOverrides,
  }
}

function exactNativeRecord(ticketCount: number, overrides: JsonRecord = {}): JsonRecord {
  return {
    strategy_id: `strategy_k${ticketCount}`,
    strategy_version: 'v1',
    legacy_method_id: 'tools/strategy.py',
    source_path: 'src/strategy.py',
    method_family: 'statistical',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    ticket_count: ticketCount,
    window: 'FULL',
    criterion: 'OFFICIAL_ANY_PRIZE',
    metric_status: 'UNAVAILABLE',
    rankable: false,
    unavailable_reason: 'Unavailable',
    metrics_unavailable_reason: null,
    unranked_reason: null,
    official_any_prize_count: 0,
    official_any_prize_rate: null,
    official_random_baseline_probability: null,
    official_random_baseline_delta: null,
    coverage: null,
    official_prize_counts: prizeCounts(),
    no_prize_count: 0,
    available_observation_count: 0,
    effective_backtest_draw_count: 0,
    successful_observation_count: 0,
    window_available_draws: 0,
    window_requested_draws: 0,
    window_complete: false,
    native_ticket_count_classification: null,
    authority_mode: null,
    catalog_sha256: SHA,
    official_rank: null,
    rank: null,
    ...overrides,
  }
}

function exactNativePage(ticketCount: number, item = exactNativeRecord(ticketCount), extra: JsonRecord = {}) {
  return {
    items: [item],
    total: 1,
    limit: 25,
    offset: 0,
    ticket_count: ticketCount,
    window: 'FULL',
    criterion: 'OFFICIAL_ANY_PRIZE',
    research_disclaimer: DISCLAIMER,
    ...extra,
  }
}

function k5Record(overrides: JsonRecord = {}): JsonRecord {
  return {
    ticket_count: 5,
    native_ticket_count: 5,
    criterion: 'OFFICIAL_ANY_PRIZE',
    window: 'FULL',
    strategy_id: 'strategy_k5',
    display_name: 'K5 strategy',
    strategy_version: 'v1',
    catalog_strategy_version: null,
    legacy_method_id: null,
    source_path: null,
    method_family: 'statistical',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    source_order: 1,
    position: 1,
    rank: 1,
    official_rank: 1,
    metric_unavailable_reason: null,
    metric_status: 'AVAILABLE',
    official_any_prize_rate: DECIMAL_18,
    official_random_baseline: DECIMAL_18,
    baseline_delta: DECIMAL_18,
    coverage: DECIMAL_18,
    official_any_prize_numerator: 1,
    official_any_prize_denominator: 100,
    evaluated_draws: 100,
    requested_draws: 100,
    first_evaluated_draw: '115000001',
    last_evaluated_draw: '115000100',
    best_prize_counts: prizeCounts(),
    replay_status_counts: { BACKTESTED: 1 },
    typed_replay_failures_count: 0,
    provenance: { source_ranking_sha256: SHA, k: 5, cutoff: '115000084' },
    window_boundary: { last_target: '115000084' },
    ...overrides,
  }
}

function k5Page(item = k5Record(), extra: JsonRecord = {}): JsonRecord {
  return {
    items: [item],
    total: 1,
    limit: 25,
    offset: 0,
    ticket_count: 5,
    criterion: 'OFFICIAL_ANY_PRIZE',
    window: 'FULL',
    projection_sha256: SHA,
    provenance: {
      k: 5,
      cutoff: '115000084',
      sealed_manifest_k_values: [2, 3, 5],
      target_evidence_k_values: [2, 3, 5],
      source_ranking_k_values: [2, 3, 5, 10],
    },
    window_boundary: { last_target: '115000084' },
    ties: [{ rank: 1, strategy_id: 'strategy_k5' }],
    research_disclaimer: DISCLAIMER,
    ...extra,
  }
}

function k10Record(overrides: JsonRecord = {}): JsonRecord {
  return {
    ticket_count: 10,
    native_ticket_count: 10,
    criterion: 'OFFICIAL_ANY_PRIZE',
    window: 'FULL',
    strategy_id: 'strategy_k10',
    display_name: 'K10 strategy',
    strategy_version: 'v1',
    method_family: 'statistical',
    reproduction_status: 'BACKTESTED',
    source_order: 1,
    position: null,
    rank: 1,
    official_rank: 1,
    metric_status: 'AVAILABLE',
    unranked_reason: null,
    unavailable_reason: null,
    official_any_prize_rate: DECIMAL_18,
    official_random_baseline: DECIMAL_18,
    baseline_delta: DECIMAL_18,
    coverage: DECIMAL_18,
    official_any_prize_numerator: 1,
    official_any_prize_denominator: 100,
    evaluated_draws: 100,
    requested_draws: 100,
    best_prize_counts: prizeCounts(),
    provenance: { source_ranking_sha256: SHA, cutoff: '115000084', k: 10 },
    ...overrides,
  }
}

function k10Page(item = k10Record(), extra: JsonRecord = {}): JsonRecord {
  return {
    items: [item],
    total: 1,
    limit: 25,
    offset: 0,
    ticket_count: 10,
    window: 'FULL',
    criterion: 'OFFICIAL_ANY_PRIZE',
    research_disclaimer: DISCLAIMER,
    ...extra,
  }
}

function setFetchPayload(payload: unknown) {
  const mock = vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => payload,
  }) as unknown as Response)
  vi.stubGlobal('fetch', mock)
  return mock
}

function setPath(payload: JsonRecord, path: string[], value: unknown): JsonRecord {
  const copy = structuredClone(payload)
  let current = copy
  for (const key of path.slice(0, -1)) current = current[key]
  current[path[path.length - 1]] = value
  return copy
}

const multiQuery = (overrides: JsonRecord = {}) => ({
  prefixCount: 10 as const,
  window: 'FULL' as const,
  criterion: 'M3_PLUS' as const,
  limit: 25,
  offset: 0,
  ...overrides,
})

const exactQuery = (ticketCount: 2 | 3 | 5 | 10, overrides: JsonRecord = {}) => ({
  ticketCount,
  window: 'FULL' as const,
  ...overrides,
})

const unsafeResponseCases: UnsafeResponseCase[] = [
  ...[
    'total_strategy_count',
    'reproduced_count',
    'backtested_count',
    'closed_count',
    'duplicate_alias_count',
    'owner_decision_required_count',
    'uncompleted_count',
  ].map((field) => ({
    label: `summary progress.${field}`,
    payload: () => summaryPayload(),
    path: ['progress', field],
    request: () => fetchB649MultiTicketSummary(),
  })),
  {
    label: 'summary source_report_count',
    payload: () => summaryPayload({}, { source_report_count: 1 }),
    path: ['source_report_count'],
    request: () => fetchB649MultiTicketSummary(),
  },
  ...['total', 'limit', 'offset'].map((field) => ({
    label: `RecordPage.${field}`,
    payload: () => multiTicketPage(),
    path: [field],
    request: () => fetchB649MultiTicketRecords(multiQuery()),
  })),
  ...[
    'rank',
    'official_rank',
    'official_any_prize_count',
    'success_count',
    'effective_backtest_draw_count',
    'successful_execution_count',
    'window_available_draws',
    'window_requested_draws',
  ].map((field) => ({
    label: `MultiTicketRecord.${field}`,
    payload: () => multiTicketPage(),
    path: ['items', '0', field],
    request: () => fetchB649MultiTicketRecords(multiQuery()),
  })),
  {
    label: 'official_prize_counts.first',
    payload: () => multiTicketPage(),
    path: ['items', '0', 'official_prize_counts', 'first'],
    request: () => fetchB649MultiTicketRecords(multiQuery()),
  },
  ...[2, 3].flatMap((ticketCount) => [
    ...['total', 'limit', 'offset'].map((field) => ({
      label: `K${ticketCount} ExactNativeRecordPage.${field}`,
      payload: () => exactNativePage(ticketCount),
      path: [field],
      request: () => fetchB649ExactNativeRecords(exactQuery(ticketCount as 2 | 3)),
    })),
    ...[
      'rank',
      'official_any_prize_count',
      'available_observation_count',
      'effective_backtest_draw_count',
      'successful_observation_count',
      'window_available_draws',
      'window_requested_draws',
    ].map((field) => ({
      label: `K${ticketCount} ExactNativeRecord.${field}`,
      payload: () => exactNativePage(ticketCount),
      path: ['items', '0', field],
      request: () => fetchB649ExactNativeRecords(exactQuery(ticketCount as 2 | 3)),
    })),
    {
      label: `K${ticketCount} ExactNativeRecord official prize count`,
      payload: () => exactNativePage(ticketCount),
      path: ['items', '0', 'official_prize_counts', 'first'],
      request: () => fetchB649ExactNativeRecords(exactQuery(ticketCount as 2 | 3)),
    },
  ]),
  ...[
    ['official_any_prize_numerator', 'K5 official numerator'],
    ['official_any_prize_denominator', 'K5 official denominator'],
    ['rank', 'K5 rank'],
    ['evaluated_draws', 'K5 evaluated period count'],
    ['requested_draws', 'K5 requested period count'],
    ['source_order', 'K5 source order'],
    ['typed_replay_failures_count', 'K5 replay failure count'],
  ].map(([field, label]) => ({
    label,
    payload: () => k5Page(),
    path: ['items', '0', field],
    request: () => fetchB649ExactNativeRecords(exactQuery(5)),
  })),
  {
    label: 'K5 official prize-level count',
    payload: () => k5Page(),
    path: ['items', '0', 'best_prize_counts', 'first'],
    request: () => fetchB649ExactNativeRecords(exactQuery(5)),
  },
  {
    label: 'K5 page tie rank',
    payload: () => k5Page(),
    path: ['ties', '0', 'rank'],
    request: () => fetchB649ExactNativeRecords(exactQuery(5)),
  },
  {
    label: 'K5 replay status count',
    payload: () => k5Page(),
    path: ['items', '0', 'replay_status_counts', 'BACKTESTED'],
    request: () => fetchB649ExactNativeRecords(exactQuery(5)),
  },
  ...[
    ['official_any_prize_numerator', 'K10 official numerator'],
    ['official_any_prize_denominator', 'K10 official denominator'],
    ['rank', 'K10 rank'],
    ['evaluated_draws', 'K10 evaluated period count'],
    ['requested_draws', 'K10 requested period count'],
    ['source_order', 'K10 source order'],
  ].map(([field, label]) => ({
    label,
    payload: () => k10Page(),
    path: ['items', '0', field],
    request: () => fetchB649ExactNativeRecords(exactQuery(10)),
  })),
  {
    label: 'K10 official prize-level count',
    payload: () => k10Page(),
    path: ['items', '0', 'best_prize_counts', 'first'],
    request: () => fetchB649ExactNativeRecords(exactQuery(10)),
  },
]

afterEach(() => vi.unstubAllGlobals())

describe('B649 safe integer response contract', () => {
  it.each(unsafeResponseCases)('rejects unsafe values in $label', async ({ payload, path, request }) => {
    setFetchPayload(setPath(payload(), path, UNSAFE))
    await expect(request()).rejects.toMatchObject({
      name: 'B649RecordsRequestError',
      kind: 'MALFORMED_RESPONSE',
      status: 200,
    })
  })

  const queryFailures: Array<{
    label: string
    value: number
    request: () => Promise<unknown>
  }> = []
  for (const value of [UNSAFE, -1, 1.5, 0]) {
    queryFailures.push({
      label: `multi-ticket limit ${value}`,
      value,
      request: () => fetchB649MultiTicketRecords(multiQuery({ limit: value })),
    })
  }
  for (const value of [UNSAFE, -1, 1.5]) {
    queryFailures.push({
      label: `multi-ticket offset ${value}`,
      value,
      request: () => fetchB649MultiTicketRecords(multiQuery({ offset: value })),
    })
  }
  for (const value of [UNSAFE, -1, 1.5, 0]) {
    queryFailures.push({
      label: `exact-native limit ${value}`,
      value,
      request: () => fetchB649ExactNativeRecords(exactQuery(2, { limit: value })),
    })
  }
  for (const value of [UNSAFE, -1, 1.5]) {
    queryFailures.push({
      label: `exact-native offset ${value}`,
      value,
      request: () => fetchB649ExactNativeRecords(exactQuery(2, { offset: value })),
    })
  }

  it.each(queryFailures)('rejects $label before fetch', async ({ request }) => {
    const fetchMock = setFetchPayload(multiTicketPage())
    await expect(request()).rejects.toMatchObject({
      name: 'B649RecordsRequestError',
      kind: 'INVALID_REQUEST',
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('preserves zero, SAFE_MAX, null, false, empty items, and 18-digit decimals', async () => {
    setFetchPayload(summaryPayload({ total_strategy_count: SAFE_MAX }, { source_report_count: SAFE_MAX }))
    const summary = await fetchB649MultiTicketSummary()
    expect(summary.progress.total_strategy_count).toBe(SAFE_MAX)
    expect(summary.source_report_count).toBe(SAFE_MAX)

    setFetchPayload(summaryPayload({ total_strategy_count: 0 }, { source_report_count: null }))
    const zeroSummary = await fetchB649MultiTicketSummary()
    expect(zeroSummary.progress.total_strategy_count).toBe(0)
    expect(zeroSummary.source_report_count).toBeNull()

    setFetchPayload(multiTicketPage({ items: [], total: SAFE_MAX, limit: SAFE_MAX, offset: SAFE_MAX }))
    const safeMaxPage = await fetchB649MultiTicketRecords(multiQuery())
    expect(safeMaxPage.total).toBe(SAFE_MAX)
    expect(safeMaxPage.limit).toBe(SAFE_MAX)
    expect(safeMaxPage.offset).toBe(SAFE_MAX)

    setFetchPayload(multiTicketPage({ items: [], total: 0, offset: 0 }))
    const emptyPage = await fetchB649MultiTicketRecords(multiQuery())
    expect(emptyPage.items).toEqual([])
    expect(emptyPage.total).toBe(0)

    setFetchPayload(multiTicketPage({
      item: multiTicketRecord({
        rank: SAFE_MAX,
        official_any_prize_count: 0,
        official_any_prize_rate: null,
        window_complete: false,
        official_prize_counts: prizeCounts({ first: SAFE_MAX }),
      }),
    }))
    const multiPage = await fetchB649MultiTicketRecords(multiQuery())
    expect(multiPage.items[0].rank).toBe(SAFE_MAX)
    expect(multiPage.items[0].official_any_prize_count).toBe(0)
    expect(multiPage.items[0].official_any_prize_rate).toBeNull()
    expect(multiPage.items[0].window_complete).toBe(false)
    expect(multiPage.items[0].official_prize_counts?.first).toBe(SAFE_MAX)

    setFetchPayload(exactNativePage(2, exactNativeRecord(2, {
      rank: SAFE_MAX,
      official_any_prize_count: 0,
      rankable: false,
      unavailable_reason: 'Unavailable',
    })))
    const exactPage = await fetchB649ExactNativeRecords(exactQuery(2))
    expect(exactPage.items[0].rank).toBe(SAFE_MAX)
    expect(exactPage.items[0].official_any_prize_count).toBe(0)
    expect(exactPage.items[0].rankable).toBe(false)
    expect(exactPage.items[0].unavailable_reason).toBe('Unavailable')

    setFetchPayload(k5Page(k5Record({
      official_any_prize_numerator: SAFE_MAX,
      official_any_prize_denominator: SAFE_MAX,
      official_any_prize_rate: DECIMAL_18,
    })))
    const k5 = await fetchB649ExactNativeRecords(exactQuery(5))
    expect(k5.items[0].official_any_prize_numerator).toBe(SAFE_MAX)
    expect(k5.items[0].official_any_prize_denominator).toBe(SAFE_MAX)
    expect(k5.items[0].official_any_prize_rate).toBe(DECIMAL_18)

    setFetchPayload(k10Page(k10Record({
      official_any_prize_numerator: SAFE_MAX,
      official_any_prize_denominator: SAFE_MAX,
      official_any_prize_rate: DECIMAL_18,
    })))
    const k10 = await fetchB649ExactNativeRecords(exactQuery(10))
    expect(k10.items[0].official_any_prize_numerator).toBe(SAFE_MAX)
    expect(k10.items[0].official_any_prize_denominator).toBe(SAFE_MAX)
    expect(k10.items[0].official_any_prize_rate).toBe(DECIMAL_18)
  })

  it('keeps legal query URLs and GET fetch behavior unchanged', async () => {
    const multiFetch = setFetchPayload(multiTicketPage())
    await fetchB649MultiTicketRecords(multiQuery({ limit: 100, offset: 0 }))
    expect(multiFetch).toHaveBeenCalledOnce()
    expect(multiFetch.mock.calls[0][0]).toBe(
      '/api/v1/b649-multi-ticket-records?prefix_count=10&window=FULL&criterion=M3_PLUS&limit=100&offset=0',
    )
    expect(multiFetch.mock.calls[0][1]).toEqual({ signal: undefined })

    const exactFetch = setFetchPayload(exactNativePage(2))
    await fetchB649ExactNativeRecords(exactQuery(2, { limit: 25, offset: 0 }))
    expect(exactFetch).toHaveBeenCalledOnce()
    expect(exactFetch.mock.calls[0][0]).toBe(
      '/api/v1/b649-exact-native-records?ticket_count=2&window=FULL&limit=25&offset=0',
    )
    expect(exactFetch.mock.calls[0][1]).toEqual({ signal: undefined })
  })

  it('uses the existing request error class for malformed unsafe responses', async () => {
    setFetchPayload(setPath(summaryPayload(), ['progress', 'total_strategy_count'], UNSAFE))
    const request = fetchB649MultiTicketSummary()
    await expect(request).rejects.toBeInstanceOf(B649RecordsRequestError)
    await expect(request).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE' })
  })
})
