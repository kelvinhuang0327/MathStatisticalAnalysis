import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getReplayBackfillCoverage,
  listReplayBackfillPredictions,
  listReplayBackfillStrategies,
  listReplayStrategyInventory,
  ReplayBackfillRequestError,
} from '../src/api/replayBackfill'

const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER
const UNSAFE_INTEGER = MAX_SAFE_INTEGER + 1

afterEach(() => vi.unstubAllGlobals())

function strategyItem(overrides: Record<string, unknown> = {}) {
  return {
    strategy_id: 'strategy-1',
    strategy_version: 'v1',
    display_name: 'Strategy 1',
    lottery_type: 'BIG_LOTTO',
    lifecycle_status: 'OFFLINE',
    data_status: 'NO_HISTORY',
    source_kind: 'fixture',
    executable: false,
    available_target_count: 0,
    training_status: 'NOT_TRAINABLE',
    ...overrides,
  }
}

function strategyPage(item: Record<string, unknown> | null = null, totalCount = item ? 1 : 0) {
  return {
    items: item ? [strategyItem(item)] : [],
    total_count: totalCount,
    next_cursor: null,
  }
}

function inventoryItem(overrides: Record<string, unknown> = {}) {
  return {
    lottery_type: 'BIG_LOTTO',
    strategy_id: 'strategy-1',
    display_name: 'Strategy 1',
    strategy_version: null,
    source_kind: 'fixture',
    source_locator: 'fixture:strategy-1',
    lifecycle_status: 'OFFLINE',
    replay_data_status: 'NO_HISTORY',
    execution_capability: 'NONE',
    reconstructable: null,
    wrapper_callable: null,
    backfill_native_binding: null,
    backfill_runnable: false,
    execution_block_reason: null,
    reconstruction_reason: 'fixture',
    historical_data_count: 0,
    historical_execution_count: 0,
    ...overrides,
  }
}

function predictionTicket(overrides: Record<string, unknown> = {}) {
  return {
    ticket_position: 1,
    main_numbers: [1, 2, 3, 4, 5, 6],
    special_numbers: [7],
    main_hit_count: 0,
    special_hit: false,
    prize_tier: null,
    ...overrides,
  }
}

function predictionItem(
  overrides: Record<string, unknown> = {},
  ticketOverrides: Record<string, unknown> = {},
) {
  return {
    lottery_type: 'BIG_LOTTO',
    strategy_id: 'strategy-1',
    strategy_version: 'v1',
    target_draw_number: '115000001',
    target_draw_date: '2026-01-01',
    prediction_status: 'COMPLETE',
    predicted_tickets: [predictionTicket(ticketOverrides)],
    actual_main_numbers: [1, 2, 3, 4, 5, 6],
    actual_special_numbers: [7],
    portfolio_any_prize: false,
    best_main_hits: 0,
    source_kind: 'fixture',
    data_status: 'REBUILDABLE',
    prediction_cutoff: {
      status: 'UNKNOWN',
      draw_date: null,
      draw_number: null,
      history_draw_count: null,
      reason_code: null,
      source_hash: null,
      source_identity: null,
      source_locator: null,
    },
    training: {
      training_status: 'NOT_TRAINABLE',
      model_version: null,
      training_cutoff: null,
      training_artifact_id: null,
    },
    ...overrides,
  }
}

function predictionPage(item: Record<string, unknown> | null = null, totalCount = item ? 1 : 0) {
  return {
    run_id: null,
    total_count: totalCount,
    items: item ? [item] : [],
    next_cursor: null,
  }
}

function coverage(overrides: Record<string, unknown> = {}) {
  return {
    expected_strategy_count: 0,
    expected_target_count: 0,
    expected_cell_count: 0,
    completed_cell_count: 0,
    failed_cell_count: 0,
    closed_cell_count: 0,
    complete_coverage_percent: 0,
    missing_strategy_ids: [],
    run_id: null,
    ...overrides,
  }
}

function stubApiResponse(payload: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const unsafeCases: Array<{ name: string, payload: unknown, request: () => Promise<unknown> }> = [
  {
    name: 'strategy page total_count',
    payload: strategyPage(null, UNSAFE_INTEGER),
    request: () => listReplayBackfillStrategies({ lotteryType: 'BIG_LOTTO' }),
  },
  {
    name: 'strategy available_target_count',
    payload: strategyPage({ available_target_count: UNSAFE_INTEGER }),
    request: () => listReplayBackfillStrategies({ lotteryType: 'BIG_LOTTO' }),
  },
  {
    name: 'inventory strategy_count',
    payload: { strategy_count: UNSAFE_INTEGER, strategies: [] },
    request: () => listReplayStrategyInventory('BIG_LOTTO'),
  },
  {
    name: 'inventory historical_data_count',
    payload: { strategy_count: 1, strategies: [inventoryItem({ historical_data_count: UNSAFE_INTEGER })] },
    request: () => listReplayStrategyInventory('BIG_LOTTO'),
  },
  {
    name: 'inventory historical_execution_count',
    payload: { strategy_count: 1, strategies: [inventoryItem({ historical_execution_count: UNSAFE_INTEGER })] },
    request: () => listReplayStrategyInventory('BIG_LOTTO'),
  },
  {
    name: 'prediction page total_count',
    payload: predictionPage(null, UNSAFE_INTEGER),
    request: () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }),
  },
  {
    name: 'prediction history_draw_count',
    payload: predictionPage(predictionItem({
      prediction_cutoff: { ...predictionItem().prediction_cutoff, history_draw_count: UNSAFE_INTEGER },
    })),
    request: () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }),
  },
  {
    name: 'ticket_position',
    payload: predictionPage(predictionItem({}, { ticket_position: UNSAFE_INTEGER })),
    request: () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }),
  },
  {
    name: 'main_hit_count',
    payload: predictionPage(predictionItem({}, { main_hit_count: UNSAFE_INTEGER })),
    request: () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }),
  },
  {
    name: 'best_main_hits',
    payload: predictionPage(predictionItem({ best_main_hits: UNSAFE_INTEGER })),
    request: () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }),
  },
  {
    name: 'ticket main_numbers entry',
    payload: predictionPage(predictionItem({}, { main_numbers: [UNSAFE_INTEGER] })),
    request: () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }),
  },
  {
    name: 'ticket special_numbers entry',
    payload: predictionPage(predictionItem({}, { special_numbers: [UNSAFE_INTEGER] })),
    request: () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }),
  },
  {
    name: 'actual_main_numbers entry',
    payload: predictionPage(predictionItem({ actual_main_numbers: [UNSAFE_INTEGER] })),
    request: () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }),
  },
  {
    name: 'actual_special_numbers entry',
    payload: predictionPage(predictionItem({ actual_special_numbers: [UNSAFE_INTEGER] })),
    request: () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }),
  },
  ...[
    'expected_strategy_count',
    'expected_target_count',
    'expected_cell_count',
    'completed_cell_count',
    'failed_cell_count',
    'closed_cell_count',
  ].map((field) => ({
    name: `coverage ${field}`,
    payload: coverage({ [field]: UNSAFE_INTEGER }),
    request: () => getReplayBackfillCoverage('BIG_LOTTO'),
  })),
]

describe('Replay Backfill API client safe integer validation', () => {
  it.each(unsafeCases)('rejects unsafe $name from the fetch response', async ({ payload, request }) => {
    const fetchMock = stubApiResponse(payload)

    await expect(request()).rejects.toBeInstanceOf(ReplayBackfillRequestError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('accepts the safe integer boundary and preserves null, zero, false, and empty arrays', async () => {
    const strategyPayload = strategyPage({ available_target_count: MAX_SAFE_INTEGER }, MAX_SAFE_INTEGER)
    stubApiResponse(strategyPayload)
    await expect(listReplayBackfillStrategies({ lotteryType: 'BIG_LOTTO' })).resolves.toEqual(strategyPayload)

    const inventoryPayload = {
      strategy_count: 1,
      strategies: [inventoryItem({
        historical_data_count: MAX_SAFE_INTEGER,
        historical_execution_count: MAX_SAFE_INTEGER,
      })],
    }
    stubApiResponse(inventoryPayload)
    await expect(listReplayStrategyInventory('BIG_LOTTO')).resolves.toEqual(inventoryPayload)

    const coveragePayload = coverage({
      expected_strategy_count: MAX_SAFE_INTEGER,
      expected_target_count: MAX_SAFE_INTEGER,
      expected_cell_count: MAX_SAFE_INTEGER,
      completed_cell_count: MAX_SAFE_INTEGER,
      failed_cell_count: MAX_SAFE_INTEGER,
      closed_cell_count: MAX_SAFE_INTEGER,
    })
    stubApiResponse(coveragePayload)
    await expect(getReplayBackfillCoverage('BIG_LOTTO')).resolves.toEqual(coveragePayload)

    const predictionPayload = predictionPage(predictionItem({
      actual_main_numbers: [],
      actual_special_numbers: [],
      portfolio_any_prize: false,
      best_main_hits: null,
      prediction_cutoff: { ...predictionItem().prediction_cutoff, history_draw_count: null },
    }, {
      main_numbers: [],
      special_numbers: [],
      main_hit_count: null,
    }))
    stubApiResponse(predictionPayload)
    await expect(listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 })).resolves.toEqual(predictionPayload)

    const boundaryPredictionPayload = predictionPage(predictionItem({
      actual_main_numbers: [MAX_SAFE_INTEGER],
      actual_special_numbers: [MAX_SAFE_INTEGER],
      best_main_hits: MAX_SAFE_INTEGER,
      prediction_cutoff: { ...predictionItem().prediction_cutoff, history_draw_count: MAX_SAFE_INTEGER },
    }, {
      ticket_position: MAX_SAFE_INTEGER,
      main_numbers: [MAX_SAFE_INTEGER],
      special_numbers: [MAX_SAFE_INTEGER],
      main_hit_count: MAX_SAFE_INTEGER,
    }), MAX_SAFE_INTEGER)
    stubApiResponse(boundaryPredictionPayload)
    await expect(listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 })).resolves.toEqual(boundaryPredictionPayload)

    const zeroHitPayload = predictionPage(predictionItem({}, { main_hit_count: 0 }))
    stubApiResponse(zeroHitPayload)
    await expect(listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 })).resolves.toEqual(zeroHitPayload)
  })

  it.each([
    ['strategy total_count', () => listReplayBackfillStrategies({ lotteryType: 'BIG_LOTTO' }), strategyPage(null, -1)],
    ['available_target_count', () => listReplayBackfillStrategies({ lotteryType: 'BIG_LOTTO' }), strategyPage({ available_target_count: -1 })],
    ['strategy_count', () => listReplayStrategyInventory('BIG_LOTTO'), { strategy_count: -1, strategies: [] }],
    ['historical_data_count', () => listReplayStrategyInventory('BIG_LOTTO'), { strategy_count: 1, strategies: [inventoryItem({ historical_data_count: -1 })] }],
    ['historical_execution_count', () => listReplayStrategyInventory('BIG_LOTTO'), { strategy_count: 1, strategies: [inventoryItem({ historical_execution_count: -1 })] },],
    ['prediction total_count', () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }), predictionPage(null, -1)],
    ['history_draw_count', () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }), predictionPage(predictionItem({ prediction_cutoff: { ...predictionItem().prediction_cutoff, history_draw_count: -1 } }))],
    ['main_hit_count', () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }), predictionPage(predictionItem({}, { main_hit_count: -1 }))],
    ['best_main_hits', () => listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', period: 50 }), predictionPage(predictionItem({ best_main_hits: -1 }))],
    ...[
      'expected_strategy_count',
      'expected_target_count',
      'expected_cell_count',
      'completed_cell_count',
      'failed_cell_count',
      'closed_cell_count',
    ].map((field) => [`coverage ${field}`, () => getReplayBackfillCoverage('BIG_LOTTO'), coverage({ [field]: -1 })]),
  ])('rejects negative %s values as invalid API responses', async (_name, request, payload) => {
    const fetchMock = stubApiResponse(payload)

    await expect(request()).rejects.toBeInstanceOf(ReplayBackfillRequestError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
