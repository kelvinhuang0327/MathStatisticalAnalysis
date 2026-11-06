import { afterEach, describe, expect, it, vi } from 'vitest'
import { listReplayBackfillPredictions } from '../src/api/replayBackfill'

const item = {
  lottery_type: 'BIG_LOTTO', strategy_id: 's', strategy_version: 'v1',
  target_draw_number: '1', target_draw_date: '2026-01-01',
  prediction_status: 'COMPLETE', predicted_tickets: [], actual_main_numbers: [],
  actual_special_numbers: [], portfolio_any_prize: null, best_main_hits: null,
  source_kind: 'native', data_status: 'REBUILDABLE', training: {
    training_status: 'NOT_TRAINABLE', model_version: null, training_cutoff: null,
    training_artifact_id: null,
  },
}

function stubPrediction(overrides: Record<string, unknown>) {
  const payload = { run_id: null, total_count: 1, next_cursor: null, items: [{ ...item, ...overrides }] }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => payload }))
  return payload
}

const query = { lotteryType: 'BIG_LOTTO', period: 50 } as const

afterEach(() => vi.unstubAllGlobals())

describe('prediction lifecycle status', () => {
  it.each([
    ['missing', {}],
    ['null', { lifecycle_status: null }],
    ['string', { lifecycle_status: 'ONLINE' }],
  ])('accepts %s', async (_label, overrides) => {
    const expected = stubPrediction(overrides)
    await expect(listReplayBackfillPredictions(query)).resolves.toEqual(expected)
  })

  it.each([
    ['number', 1], ['boolean', false], ['object', {}], ['array', []],
  ])('rejects %s', async (_label, value) => {
    stubPrediction({ lifecycle_status: value })
    await expect(listReplayBackfillPredictions(query)).rejects.toThrow('invalid response')
  })
})
