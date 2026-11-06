import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../src/api/b649MultiTicketRecords', async () => {
  const actual = await vi.importActual<typeof import('../src/api/b649MultiTicketRecords')>(
    '../src/api/b649MultiTicketRecords',
  )
  return {
    ...actual,
    fetchB649MultiTicketRecords: vi.fn(),
    fetchB649MultiTicketSummary: vi.fn(),
  }
})

import {
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
  type B649MultiTicketRecord,
  type B649MultiTicketRecordPage,
  type B649MultiTicketSummary,
} from '../src/api/b649MultiTicketRecords'
import { loadB649BestReplayData } from '../src/api/bestReplay'

function makeSummary(recordsAvailable = true): B649MultiTicketSummary {
  return {
    progress: {
      total_strategy_count: 10,
      reproduced_count: 10,
      backtested_count: 10,
      closed_count: 0,
      duplicate_alias_count: 0,
      owner_decision_required_count: 0,
      uncompleted_count: 0,
    },
    prefix_counts: [5, 10, 15, 20],
    windows: ['FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50'],
    success_criteria: ['M3_PLUS'],
    primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
    method_families: ['frequency'],
    reproduction_statuses: ['BACKTESTED'],
    catalog_sha256: 'a'.repeat(64),
    records_available: recordsAvailable,
    projection_sha256: recordsAvailable ? 'b'.repeat(64) : null,
    source_report_count: recordsAvailable ? 1 : null,
    metrics_available_strategy_count: recordsAvailable ? 10 : null,
    metrics_unavailable_strategy_count: 0,
    research_disclaimer: 'disclaimer',
  }
}

function makeRecord(id: string, overrides: Partial<B649MultiTicketRecord> = {}): B649MultiTicketRecord {
  return {
    strategy_id: id,
    strategy_version: 'v1.0',
    legacy_method_id: id,
    source_path: `fixtures/${id}.json`,
    method_family: 'frequency',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: 5,
    window: 'FULL',
    criterion: 'M3_PLUS',
    rank: 1,
    official_rank: 1,
    official_any_prize_count: 10,
    official_any_prize_rate: '0.200000000000000000',
    official_random_baseline_probability: '0.100000000000000000',
    official_random_baseline_delta: '0.100000000000000000',
    success_count: 99,
    successful_execution_count: 50,
    historical_success_rate: '0.990000000000000000',
    random_baseline_success_rate: '0.880000000000000000',
    random_baseline_rate_difference: '0.770000000000000000',
    coverage: '0.900000000000000000',
    official_prize_counts: null,
    unranked_reason: null,
    ...overrides,
  } as unknown as B649MultiTicketRecord
}

function makePage(
  items: B649MultiTicketRecord[],
  total: number,
  limit: number,
  offset: number,
): B649MultiTicketRecordPage {
  return {
    items,
    total,
    limit,
    offset,
  }
}

describe('Best Replay B649 pagination progress and integrity', () => {
  beforeEach(() => {
    vi.mocked(fetchB649MultiTicketSummary).mockReset()
    vi.mocked(fetchB649MultiTicketRecords).mockReset()
    vi.mocked(fetchB649MultiTicketSummary).mockResolvedValue(makeSummary(true))
  })

  describe('AC02: partial page offset progress', () => {
    it('advances offset by actual item count on partial pages without skipping items', async () => {
      const page1Items = Array.from({ length: 40 }, (_, i) => makeRecord(`strat-${i}`))
      const page2Items = Array.from({ length: 30 }, (_, i) => makeRecord(`strat-${i + 40}`))

      vi.mocked(fetchB649MultiTicketRecords)
        .mockResolvedValueOnce(makePage(page1Items, 70, 100, 0))
        .mockResolvedValueOnce(makePage(page2Items, 70, 100, 40))

      const results = await loadB649BestReplayData([5], 'FULL')

      expect(fetchB649MultiTicketRecords).toHaveBeenCalledTimes(2)
      expect(fetchB649MultiTicketRecords).toHaveBeenNthCalledWith(
        1,
        expect.objectContaining({ prefixCount: 5, offset: 0, limit: 100 }),
        undefined,
      )
      expect(fetchB649MultiTicketRecords).toHaveBeenNthCalledWith(
        2,
        expect.objectContaining({ prefixCount: 5, offset: 40, limit: 100 }),
        undefined,
      )

      expect(results).toHaveLength(70)
      expect(results.map((r) => r.strategyId)).toEqual(
        Array.from({ length: 70 }, (_, i) => `strat-${i}`),
      )
    })
  })

  describe('AC03: empty page termination and non-progress protection', () => {
    it('fails immediately when the first page is empty but total > 0', async () => {
      vi.mocked(fetchB649MultiTicketRecords).mockResolvedValueOnce(makePage([], 50, 100, 0))

      await expect(loadB649BestReplayData([5], 'FULL')).rejects.toThrow(
        /incomplete.*page|no progress/i,
      )
      expect(fetchB649MultiTicketRecords).toHaveBeenCalledTimes(1)
    })

    it('fails immediately on subsequent empty page when total is not reached', async () => {
      const page1Items = Array.from({ length: 30 }, (_, i) => makeRecord(`strat-${i}`))

      vi.mocked(fetchB649MultiTicketRecords)
        .mockResolvedValueOnce(makePage(page1Items, 50, 100, 0))
        .mockResolvedValueOnce(makePage([], 50, 100, 30))

      await expect(loadB649BestReplayData([5], 'FULL')).rejects.toThrow(
        /incomplete.*page|no progress/i,
      )
      expect(fetchB649MultiTicketRecords).toHaveBeenCalledTimes(2)
    })
  })

  describe('AC04: normal complete pages, single page, and legitimate empty result', () => {
    it('handles multiple complete pages correctly', async () => {
      const page1Items = Array.from({ length: 100 }, (_, i) => makeRecord(`strat-${i}`))
      const page2Items = Array.from({ length: 100 }, (_, i) => makeRecord(`strat-${i + 100}`))
      const page3Items = Array.from({ length: 25 }, (_, i) => makeRecord(`strat-${i + 200}`))

      vi.mocked(fetchB649MultiTicketRecords)
        .mockResolvedValueOnce(makePage(page1Items, 225, 100, 0))
        .mockResolvedValueOnce(makePage(page2Items, 225, 100, 100))
        .mockResolvedValueOnce(makePage(page3Items, 225, 100, 200))

      const results = await loadB649BestReplayData([5], 'FULL')

      expect(fetchB649MultiTicketRecords).toHaveBeenCalledTimes(3)
      expect(fetchB649MultiTicketRecords).toHaveBeenNthCalledWith(
        1,
        expect.objectContaining({ offset: 0, limit: 100 }),
        undefined,
      )
      expect(fetchB649MultiTicketRecords).toHaveBeenNthCalledWith(
        2,
        expect.objectContaining({ offset: 100, limit: 100 }),
        undefined,
      )
      expect(fetchB649MultiTicketRecords).toHaveBeenNthCalledWith(
        3,
        expect.objectContaining({ offset: 200, limit: 100 }),
        undefined,
      )
      expect(results).toHaveLength(225)
    })

    it('handles a single complete page within limit', async () => {
      const items = Array.from({ length: 45 }, (_, i) => makeRecord(`strat-${i}`))
      vi.mocked(fetchB649MultiTicketRecords).mockResolvedValueOnce(makePage(items, 45, 100, 0))

      const results = await loadB649BestReplayData([5], 'FULL')

      expect(fetchB649MultiTicketRecords).toHaveBeenCalledTimes(1)
      expect(results).toHaveLength(45)
    })

    it('handles legitimate empty result (total = 0) without error', async () => {
      vi.mocked(fetchB649MultiTicketRecords).mockResolvedValueOnce(makePage([], 0, 100, 0))

      const results = await loadB649BestReplayData([5], 'FULL')

      expect(fetchB649MultiTicketRecords).toHaveBeenCalledTimes(1)
      expect(results).toEqual([])
    })

    it('returns empty array when summary has records_available = false without querying records', async () => {
      vi.mocked(fetchB649MultiTicketSummary).mockResolvedValue(makeSummary(false))

      const results = await loadB649BestReplayData([5], 'FULL')

      expect(fetchB649MultiTicketRecords).not.toHaveBeenCalled()
      expect(results).toEqual([])
    })
  })

  describe('AC01, AC05, AC06: preserves official metric isolation and zero/unavailable parity', () => {
    it('transforms records using official metrics without falling back to M3_PLUS values', async () => {
      const rec = makeRecord('official-test', {
        official_any_prize_count: 0,
        official_any_prize_rate: '0.000000000000000000',
        official_random_baseline_probability: '0.050000000000000000',
        official_random_baseline_delta: '-0.050000000000000000',
        success_count: 99,
        historical_success_rate: '0.990000000000000000',
        random_baseline_success_rate: '0.880000000000000000',
        random_baseline_rate_difference: '0.770000000000000000',
      })

      vi.mocked(fetchB649MultiTicketRecords).mockResolvedValueOnce(makePage([rec], 1, 100, 0))

      const [item] = await loadB649BestReplayData([5], 'FULL')

      expect(item.winningTargets).toBe(0)
      expect(item.hitRate).toBe(0)
      expect(item.hitRateFormatted).toBe('0.00%')
      expect(item.baselineProbability).toBe(0.05)
      expect(item.baselineDelta).toBe(-0.05)
      expect(item.baselineDeltaFormatted).toBe('-5.00%')
      expect(item.evaluatedTargets).toBe(50)
    })

    it('preserves null unavailable metrics without falling back to M3_PLUS values', async () => {
      const rec = makeRecord('official-null-test', {
        official_any_prize_count: null,
        official_any_prize_rate: null,
        official_random_baseline_probability: null,
        official_random_baseline_delta: null,
        success_count: 99,
        historical_success_rate: '0.990000000000000000',
        random_baseline_success_rate: '0.880000000000000000',
        random_baseline_rate_difference: '0.770000000000000000',
      })

      vi.mocked(fetchB649MultiTicketRecords).mockResolvedValueOnce(makePage([rec], 1, 100, 0))

      const [item] = await loadB649BestReplayData([5], 'FULL')

      expect(item.winningTargets).toBeNull()
      expect(item.hitRate).toBeNull()
      expect(item.hitRateFormatted).toBe('Unavailable')
      expect(item.baselineProbability).toBeNull()
      expect(item.baselineDelta).toBeNull()
      expect(item.baselineDeltaFormatted).toBe('Unavailable')
    })
  })
})
