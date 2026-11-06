import { describe, expect, it } from 'vitest'

import type { B649MultiTicketRecord } from '../src/api/b649MultiTicketRecords'
import { transformB649Record } from '../src/api/bestReplay'

function makeRecord(
  overrides: Partial<B649MultiTicketRecord> = {},
): B649MultiTicketRecord {
  return {
    strategy_id: 'official-source-fixture',
    strategy_version: 'fixture-v1',
    legacy_method_id: 'official-source-fixture',
    method_family: 'fixture',
    reproduction_status: 'BACKTESTED',
    rank: 1,
    official_rank: 1,
    official_any_prize_count: 41,
    official_any_prize_rate: '0.250000000000000000',
    official_random_baseline_probability: '0.100000000000000000',
    official_random_baseline_delta: '0.150000000000000000',
    success_count: 91,
    successful_execution_count: 20,
    historical_success_rate: '0.910000000000000000',
    random_baseline_success_rate: '0.880000000000000000',
    random_baseline_rate_difference: '0.770000000000000000',
    coverage: '0.950000000000000000',
    official_prize_counts: null,
    unranked_reason: null,
    ...overrides,
  } as unknown as B649MultiTicketRecord
}

describe('Best Replay B649 official metric source isolation', () => {
  it('keeps missing official numerator and baselines unavailable despite M3_PLUS values', () => {
    const item = transformB649Record(
      makeRecord({
        official_any_prize_count: null,
        official_random_baseline_probability: null,
        official_random_baseline_delta: null,
      }),
      'FULL',
      5,
    )

    expect(item.isAvailable).toBe(true)
    expect(item.rank).toBe(1)
    expect(item.evaluatedTargets).toBe(20)
    expect(item.hitRate).toBe(0.25)
    expect({
      winningTargets: item.winningTargets,
      baselineProbability: item.baselineProbability,
      baselineDelta: item.baselineDelta,
    }).toEqual({
      winningTargets: null,
      baselineProbability: null,
      baselineDelta: null,
    })
    expect(item.hitRateFormatted).toBe('25.00%')
    expect(item.baselineDeltaFormatted).toBe('Unavailable')
  })

  it('does not display historical_success_rate when the official rate is missing', () => {
    const item = transformB649Record(
      makeRecord({ official_any_prize_rate: null }),
      'FULL',
      5,
    )

    expect(item.isAvailable).toBe(false)
    expect(item.hitRate).toBeNull()
    expect(item.hitRateFormatted).toBe('Unavailable')
  })

  it.each(['CLOSED_UNEXECUTABLE', 'DUPLICATE_ALIAS'] as const)(
    'keeps %s unavailable when M3_PLUS metrics are present',
    (reproductionStatus) => {
      const item = transformB649Record(
        makeRecord({
          reproduction_status: reproductionStatus,
          rank: null,
          official_rank: null,
          successful_execution_count: 0,
        }),
        'FULL',
        5,
      )

      expect(item.isAvailable).toBe(false)
      expect(item.rank).toBeNull()
      expect(item.evaluatedTargets).toBe(0)
      expect(item.winningTargets).toBeNull()
      expect(item.hitRate).toBeNull()
      expect(item.hitRateFormatted).toBe('Unavailable')
      expect(item.baselineProbability).toBeNull()
      expect(item.baselineDelta).toBeNull()
    },
  )

  it.each([
    {
      name: 'official zero values',
      count: 0,
      rate: '0.000000000000000000',
      baseline: '0.000000000000000000',
      delta: '0.000000000000000000',
    },
    {
      name: 'official non-zero values',
      count: 7,
      rate: '0.125000000000000000',
      baseline: '0.062500000000000000',
      delta: '0.062500000000000000',
    },
  ])('preserves $name without substituting M3_PLUS values', ({ count, rate, baseline, delta }) => {
    const item = transformB649Record(
      makeRecord({
        official_any_prize_count: count,
        official_any_prize_rate: rate,
        official_random_baseline_probability: baseline,
        official_random_baseline_delta: delta,
      }),
      'FULL',
      5,
    )

    expect(item.isAvailable).toBe(true)
    expect(item.winningTargets).toBe(count)
    expect(item.hitRate).toBe(Number.parseFloat(rate))
    expect(item.baselineProbability).toBe(Number.parseFloat(baseline))
    expect(item.baselineDelta).toBe(Number.parseFloat(delta))
  })
})
