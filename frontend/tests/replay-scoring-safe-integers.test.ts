import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getReplayScoringOverallAggregate,
  getReplayScoringRun,
  listReplayScoringPredictions,
  listReplayScoringStrategyAggregates,
  ReplayScoringProjectionsRequestError,
} from '../src/api/replayScoringProjections'

const SAFE_MAX = 9007199254740991
const UNSAFE = 9007199254740992
const VALID_SHA256 = 'a'.repeat(64)

const AGGREGATE_COUNT_FIELDS = [
  'source_snapshot_count',
  'scored_count',
  'history_closed_count',
  'prediction_closed_count',
  'target_outcome_not_found_count',
  'target_identity_mismatch_count',
  'first_prize_count',
  'second_prize_count',
  'third_prize_count',
  'fourth_prize_count',
  'fifth_prize_count',
  'sixth_prize_count',
  'seventh_prize_count',
  'general_prize_count',
  'no_prize_count',
] as const

function validAggregateCounts(fillValue = 0) {
  return AGGREGATE_COUNT_FIELDS.reduce(
    (acc, field) => {
      acc[field] = fillValue
      return acc
    },
    {} as Record<(typeof AGGREGATE_COUNT_FIELDS)[number], number>,
  )
}

function validScoringRun(overrides: Record<string, unknown> = {}) {
  return {
    scoring_artifact_schema_version: 'scoring-v1',
    scoring_artifact_payload_sha256: VALID_SHA256,
    source_replay_artifact_payload_sha256: 'b'.repeat(64),
    dataset_id: 'test-dataset',
    dataset_version: 'v1',
    lottery_type: 'BIG_LOTTO',
    target_count: 10,
    strategy_count: 2,
    scored_record_count: 5,
    overall_aggregate_sha256: 'c'.repeat(64),
    ...overrides,
  }
}

function validPrediction(overrides: Record<string, unknown> = {}) {
  return {
    run_payload_sha256: VALID_SHA256,
    ordinal: 1,
    source_snapshot_result_sha256: 'd'.repeat(64),
    scored_result_sha256: 'e'.repeat(64),
    target_draw_number: '113000100',
    target_draw_date: '2026-11-01',
    strategy_id: 'strat-1',
    source_history_status: 'SUCCESS',
    scoring_status: 'SUCCESS',
    ...overrides,
  }
}

function validStrategyAggregate(overrides: Record<string, unknown> = {}) {
  return {
    run_payload_sha256: VALID_SHA256,
    ordinal: 1,
    strategy_id: 'strat-1',
    ...validAggregateCounts(0),
    aggregate_sha256: 'f'.repeat(64),
    ...overrides,
  }
}

function validOverallAggregate(overrides: Record<string, unknown> = {}) {
  return {
    run_payload_sha256: VALID_SHA256,
    ...validAggregateCounts(0),
    aggregate_sha256: '0'.repeat(64),
    ...overrides,
  }
}

function stubApiResponse(payload: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('Replay Scoring Projections API client safe integer validation', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  // 1. Unsafe integer rejection tests
  it.each([
    ['run target_count', () => getReplayScoringRun(VALID_SHA256), validScoringRun({ target_count: UNSAFE })],
    ['run strategy_count', () => getReplayScoringRun(VALID_SHA256), validScoringRun({ strategy_count: UNSAFE })],
    ['run scored_record_count', () => getReplayScoringRun(VALID_SHA256), validScoringRun({ scored_record_count: UNSAFE })],
    ['prediction ordinal', () => listReplayScoringPredictions(VALID_SHA256), [validPrediction({ ordinal: UNSAFE })]],
    ['strategy aggregate ordinal', () => listReplayScoringStrategyAggregates(VALID_SHA256), [validStrategyAggregate({ ordinal: UNSAFE })]],
    ...AGGREGATE_COUNT_FIELDS.map((field) => [
      `strategy aggregate ${field}`,
      () => listReplayScoringStrategyAggregates(VALID_SHA256),
      [validStrategyAggregate({ [field]: UNSAFE })],
    ] as const),
    ...AGGREGATE_COUNT_FIELDS.map((field) => [
      `overall aggregate ${field}`,
      () => getReplayScoringOverallAggregate(VALID_SHA256),
      validOverallAggregate({ [field]: UNSAFE }),
    ] as const),
  ])('rejects unsafe integer for %s from the fetch response', async (_name, request, payload) => {
    const fetchMock = stubApiResponse(payload)

    await expect(request()).rejects.toBeInstanceOf(ReplayScoringProjectionsRequestError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  // 2. Negative value rejection tests
  it.each([
    ['run target_count', () => getReplayScoringRun(VALID_SHA256), validScoringRun({ target_count: -1 })],
    ['run strategy_count', () => getReplayScoringRun(VALID_SHA256), validScoringRun({ strategy_count: -1 })],
    ['run scored_record_count', () => getReplayScoringRun(VALID_SHA256), validScoringRun({ scored_record_count: -1 })],
    ...AGGREGATE_COUNT_FIELDS.map((field) => [
      `strategy aggregate ${field}`,
      () => listReplayScoringStrategyAggregates(VALID_SHA256),
      [validStrategyAggregate({ [field]: -1 })],
    ] as const),
    ...AGGREGATE_COUNT_FIELDS.map((field) => [
      `overall aggregate ${field}`,
      () => getReplayScoringOverallAggregate(VALID_SHA256),
      validOverallAggregate({ [field]: -1 }),
    ] as const),
  ])('rejects negative value for %s as invalid API response', async (_name, request, payload) => {
    const fetchMock = stubApiResponse(payload)

    await expect(request()).rejects.toBeInstanceOf(ReplayScoringProjectionsRequestError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  // 3. Floating point (non-integer) rejection tests
  it.each([
    ['run target_count', () => getReplayScoringRun(VALID_SHA256), validScoringRun({ target_count: 1.5 })],
    ['run strategy_count', () => getReplayScoringRun(VALID_SHA256), validScoringRun({ strategy_count: 1.5 })],
    ['run scored_record_count', () => getReplayScoringRun(VALID_SHA256), validScoringRun({ scored_record_count: 1.5 })],
    ['prediction ordinal', () => listReplayScoringPredictions(VALID_SHA256), [validPrediction({ ordinal: 1.5 })]],
    ['strategy aggregate ordinal', () => listReplayScoringStrategyAggregates(VALID_SHA256), [validStrategyAggregate({ ordinal: 1.5 })]],
    ...AGGREGATE_COUNT_FIELDS.map((field) => [
      `strategy aggregate ${field}`,
      () => listReplayScoringStrategyAggregates(VALID_SHA256),
      [validStrategyAggregate({ [field]: 1.5 })],
    ] as const),
    ...AGGREGATE_COUNT_FIELDS.map((field) => [
      `overall aggregate ${field}`,
      () => getReplayScoringOverallAggregate(VALID_SHA256),
      validOverallAggregate({ [field]: 1.5 }),
    ] as const),
  ])('rejects non-integer float for %s as invalid API response', async (_name, request, payload) => {
    const fetchMock = stubApiResponse(payload)

    await expect(request()).rejects.toBeInstanceOf(ReplayScoringProjectionsRequestError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  // 4. Safe boundary and legal zeros / empty lists preservation
  it('accepts safe integer boundary SAFE_MAX across all response structures', async () => {
    const boundaryRun = validScoringRun({
      target_count: SAFE_MAX,
      strategy_count: SAFE_MAX,
      scored_record_count: SAFE_MAX,
    })
    stubApiResponse(boundaryRun)
    await expect(getReplayScoringRun(VALID_SHA256)).resolves.toEqual(boundaryRun)

    const boundaryPredictions = [
      validPrediction({ ordinal: SAFE_MAX }),
    ]
    stubApiResponse(boundaryPredictions)
    await expect(listReplayScoringPredictions(VALID_SHA256)).resolves.toEqual(boundaryPredictions)

    const boundaryStrategyAggregates = [
      validStrategyAggregate({
        ordinal: SAFE_MAX,
        ...validAggregateCounts(SAFE_MAX),
      }),
    ]
    stubApiResponse(boundaryStrategyAggregates)
    await expect(listReplayScoringStrategyAggregates(VALID_SHA256)).resolves.toEqual(boundaryStrategyAggregates)

    const boundaryOverallAggregate = validOverallAggregate(validAggregateCounts(SAFE_MAX))
    stubApiResponse(boundaryOverallAggregate)
    await expect(getReplayScoringOverallAggregate(VALID_SHA256)).resolves.toEqual(boundaryOverallAggregate)
  })

  it('accepts zeros and legal empty arrays without converting to fake failures', async () => {
    const zeroRun = validScoringRun({
      target_count: 0,
      strategy_count: 0,
      scored_record_count: 0,
    })
    stubApiResponse(zeroRun)
    await expect(getReplayScoringRun(VALID_SHA256)).resolves.toEqual(zeroRun)

    stubApiResponse([])
    await expect(listReplayScoringPredictions(VALID_SHA256)).resolves.toEqual([])

    stubApiResponse([])
    await expect(listReplayScoringStrategyAggregates(VALID_SHA256)).resolves.toEqual([])

    const zeroPrediction = [
      validPrediction({ ordinal: 0 }),
    ]
    stubApiResponse(zeroPrediction)
    await expect(listReplayScoringPredictions(VALID_SHA256)).resolves.toEqual(zeroPrediction)

    const zeroStrategyAggregates = [
      validStrategyAggregate({
        ordinal: 0,
        ...validAggregateCounts(0),
      }),
    ]
    stubApiResponse(zeroStrategyAggregates)
    await expect(listReplayScoringStrategyAggregates(VALID_SHA256)).resolves.toEqual(zeroStrategyAggregates)

    const zeroOverallAggregate = validOverallAggregate(validAggregateCounts(0))
    stubApiResponse(zeroOverallAggregate)
    await expect(getReplayScoringOverallAggregate(VALID_SHA256)).resolves.toEqual(zeroOverallAggregate)
  })

  // 5. Error formatting: verify 502 status and message
  it('rejects invalid contract with HTTP status 502 and appropriate message', async () => {
    stubApiResponse(validScoringRun({ target_count: UNSAFE }))

    await expect(getReplayScoringRun(VALID_SHA256)).rejects.toMatchObject({
      name: 'ReplayScoringProjectionsRequestError',
      status: 502,
      message: 'Replay scoring artifact returned an invalid response contract',
    })
  })
})
