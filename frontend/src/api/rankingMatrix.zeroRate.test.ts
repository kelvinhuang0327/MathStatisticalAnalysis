import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  B649_RESEARCH_DISCLAIMER,
  type B649MultiTicketRecord,
} from './b649MultiTicketRecords'
import type { B649K10Record } from './b649MultiTicketRecords'
import {
  fetchRankingData,
  transformB649K10ToRankingRow,
  type RankingWindow,
} from './rankingMatrix'

const sourceStrategyId = 'legacy_biglotto__quick_ml_predict__8b7ba0b52e2d'
const sourceStrategyVersion = 'legacy-source-49a25effa62f-8b7ba0b52e2d'
const sourceWindows = ['RECENT_750', 'RECENT_300', 'RECENT_50'] as const
const windowDraws: Record<(typeof sourceWindows)[number], number> = {
  RECENT_750: 750,
  RECENT_300: 300,
  RECENT_50: 50,
}

function makeRecord(overrides: Partial<B649MultiTicketRecord> = {}): B649MultiTicketRecord {
  const window = overrides.window ?? 'RECENT_750'
  const drawCount = windowDraws[window as (typeof sourceWindows)[number]] ?? 750
  return {
    strategy_id: sourceStrategyId,
    strategy_version: sourceStrategyVersion,
    legacy_method_id: 'quick_ml_predict',
    source_path: 'tools/quick_ml_predict.py',
    method_family: 'legacy_ml',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: 20,
    window,
    criterion: 'M3_PLUS',
    rank: null,
    official_rank: null,
    official_any_prize_count: 0,
    official_any_prize_rate: '0.000000000000000000',
    official_random_baseline_probability: '0.466778366783290660',
    official_random_baseline_delta: '-0.466778366783290660',
    unranked_reason: 'NO_SUCCESSFUL_EXECUTIONS_IN_WINDOW',
    success_count: 0,
    effective_backtest_draw_count: 1,
    successful_execution_count: 0,
    historical_success_rate: '0.000000000000000000',
    random_baseline_success_rate: '0.313581825150641678',
    random_baseline_rate_difference: '-0.313581825150641678',
    coverage: '0.000000000000000000',
    window_available_draws: drawCount,
    window_requested_draws: drawCount,
    window_complete: true,
    official_prize_counts: {
      first: 0,
      second: 0,
      third: 0,
      fourth: 0,
      fifth: 0,
      sixth: 0,
      seventh: 0,
      general: 0,
    },
    no_prize_count: 0,
    report_sha256: 'a'.repeat(64),
    report_file_sha256: 'b'.repeat(64),
    catalog_sha256: 'c'.repeat(64),
    authority_mode: 'HISTORICAL_SEALED_EVIDENCE_V1',
    metrics_unavailable_reason: null,
    ...overrides,
  }
}

function installRankingResponse(record: B649MultiTicketRecord): void {
  const summary = {
    progress: {
      total_strategy_count: 1,
      reproduced_count: 1,
      backtested_count: 1,
      closed_count: 0,
      duplicate_alias_count: 0,
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
    method_families: ['legacy_ml'],
    reproduction_statuses: ['BACKTESTED', 'CLOSED_UNEXECUTABLE', 'DUPLICATE_ALIAS'],
    catalog_sha256: 'd'.repeat(64),
    records_available: true,
    projection_sha256: 'e'.repeat(64),
    source_report_count: 1,
    metrics_available_strategy_count: 1,
    metrics_unavailable_strategy_count: 0,
    primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
    research_disclaimer: B649_RESEARCH_DISCLAIMER,
  }

  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (input) => {
    const url = String(input)
    if (url.includes('/api/v1/b649-multi-ticket-records/summary')) {
      return new Response(JSON.stringify(summary))
    }
    if (url === '/api/v1/strategies') return new Response('[]')
    if (url.includes('/api/v1/b649-multi-ticket-records')) {
      return new Response(JSON.stringify({
        total: 1,
        limit: 100,
        offset: 0,
        prefix_count: 20,
        window: record.window,
        criterion: 'M3_PLUS',
        research_disclaimer: B649_RESEARCH_DISCLAIMER,
        items: [record],
      }))
    }
    return new Response('{}', { status: 404 })
  }))
}

async function loadK20(record: B649MultiTicketRecord) {
  installRankingResponse(record)
  const [row] = await fetchRankingData('BIG_LOTTO', 20, record.window as RankingWindow)
  expect(row).toBeDefined()
  return row!
}

afterEach(() => vi.unstubAllGlobals())

describe('K20 official rate denominator handling', () => {
  it.each(sourceWindows)('marks the pinned %s zero-execution source unavailable and retains its raw rate', async (window) => {
    const record = makeRecord({ window })
    const row = await loadK20(record)

    expect(row.rawOfficialAnyPrizeRate).toBe(0)
    expect(row.officialAnyPrizeRate).toBeNull()
    expect(row.officialAnyPrizeRateFormatted).toBe('Unavailable')
    expect(row.isAvailable).toBe(false)
    expect(row.comparabilityStatus).toBe('UNAVAILABLE')
    expect(row.observations).toBe(windowDraws[window])
    expect(row.successes).toBe(0)
    expect(row.strategyId).toBe(sourceStrategyId)
    expect(row.strategyVersion).toBe(sourceStrategyVersion)
    expect(row.lifecycleStatus).toBe('BACKTESTED')
    expect(row.unrankedReason).toBe('NO_SUCCESSFUL_EXECUTIONS_IN_WINDOW')
    expect(record.official_any_prize_rate).toBe('0.000000000000000000')
  })

  it('keeps a legally scored zero-prize result available at 0%', async () => {
    const row = await loadK20(makeRecord({
      official_any_prize_count: 0,
      official_any_prize_rate: '0.000000000000000000',
      successful_execution_count: 12,
      unranked_reason: null,
    }))

    expect(row.rawOfficialAnyPrizeRate).toBe(0)
    expect(row.officialAnyPrizeRate).toBe(0)
    expect(row.officialAnyPrizeRateFormatted).toBe('0.00%')
    expect(row.isAvailable).toBe(true)
    expect(row.successes).toBe(0)
  })

  it('keeps a valid positive success rate unchanged', async () => {
    const row = await loadK20(makeRecord({
      official_any_prize_count: 2,
      official_any_prize_rate: '0.250000000000000000',
      successful_execution_count: 8,
      unranked_reason: null,
    }))

    expect(row.rawOfficialAnyPrizeRate).toBe(0.25)
    expect(row.officialAnyPrizeRate).toBe(0.25)
    expect(row.isAvailable).toBe(true)
  })

  it('does not treat a missing denominator as legal even when the raw rate is nonzero', async () => {
    const row = await loadK20(makeRecord({
      official_any_prize_count: 1,
      official_any_prize_rate: '0.500000000000000000',
      successful_execution_count: null,
      unranked_reason: null,
    }))

    expect(row.rawOfficialAnyPrizeRate).toBe(0.5)
    expect(row.officialAnyPrizeRate).toBeNull()
    expect(row.isAvailable).toBe(false)
  })

  it('preserves null raw rates and valid rates for a different strategy version', async () => {
    const nullRate = await loadK20(makeRecord({
      official_any_prize_rate: null,
      successful_execution_count: 4,
      unranked_reason: null,
    }))
    expect(nullRate.rawOfficialAnyPrizeRate).toBeNull()
    expect(nullRate.officialAnyPrizeRate).toBeNull()
    expect(nullRate.isAvailable).toBe(false)

    const otherVersion = await loadK20(makeRecord({
      strategy_id: 'another_strategy',
      strategy_version: 'v2',
      official_any_prize_count: 1,
      official_any_prize_rate: '0.250000000000000000',
      successful_execution_count: 4,
      unranked_reason: null,
    }))
    expect(otherVersion.strategyId).toBe('another_strategy')
    expect(otherVersion.strategyVersion).toBe('v2')
    expect(otherVersion.officialAnyPrizeRate).toBe(0.25)
    expect(otherVersion.isAvailable).toBe(true)
  })

  it('keeps window observations separate from the official scoring denominator', async () => {
    const row = await loadK20(makeRecord({
      official_any_prize_count: 2,
      official_any_prize_rate: '0.500000000000000000',
      successful_execution_count: 4,
      window_available_draws: 750,
      effective_backtest_draw_count: 1,
      unranked_reason: null,
    }))

    expect(row.observations).toBe(750)
    expect(row.officialAnyPrizeRate).toBe(0.5)
    expect(row.isAvailable).toBe(true)
  })

  it('leaves the K10 rate adapter behavior unchanged', () => {
    const record = {
      strategy_id: 'k10_strategy',
      display_name: 'K10 strategy',
      strategy_version: 'v1',
      method_family: 'baseline',
      window: 'RECENT_300',
      official_rank: 1,
      rank: 1,
      position: 1,
      source_order: 1,
      requested_draws: 300,
      reproduction_status: 'BACKTESTED',
      official_any_prize_numerator: 0,
      official_any_prize_rate: '0.000000000000000000',
      official_random_baseline: '0.2',
      baseline_delta: '-0.2',
      coverage: '1',
      metric_status: 'AVAILABLE',
      unranked_reason: null,
      unavailable_reason: null,
      evaluated_draws: 300,
      best_prize_counts: {
        FIRST: 0,
        SECOND: 0,
        THIRD: 0,
        FOURTH: 0,
        FIFTH: 0,
        SIXTH: 0,
        SEVENTH: 0,
        GENERAL: 0,
      },
    } as unknown as B649K10Record
    const row = transformB649K10ToRankingRow(record)

    expect(row.ticketCount).toBe(10)
    expect(row.officialAnyPrizeRate).toBe(0)
    expect(row.officialAnyPrizeRateFormatted).toBe('0.00%')
    expect(row.isAvailable).toBe(true)
  })
})
