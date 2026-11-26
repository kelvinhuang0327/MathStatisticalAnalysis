// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  B649NativeForecastRequestError,
  fetchB649NativeForecast,
} from '../src/api/b649NativeForecast'
import B649CurrentForecastPage from '../src/features/b649-current-forecast/B649CurrentForecastPage.vue'
import B649NativeForecastPanel from '../src/features/b649-current-forecast/B649NativeForecastPanel.vue'

type Target = { target_draw_number: string; target_draw_date: string }

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function candidate(
  strategy_id: string,
  metric: { numerator: number | null; denominator: number | null; rate: unknown } | null,
  counts: Record<string, number>,
) {
  return {
    strategy_id,
    strategy_version: 'fixture-version-1',
    native_k: 5,
    rankable: metric !== null && metric.denominator !== 0,
    evidence_complete: true,
    metric,
    coverage: {
      requested: Object.values(counts).reduce((total, count) => total + count, 0),
      counts,
      eligible_expected: Object.values(counts).reduce((total, count) => total + count, 0),
    },
  }
}

function nativeResponse(target: Target) {
  const first = candidate(
    'synthetic.fixture.k5.alpha',
    { numerator: 1, denominator: 2, rate: { numerator: '1', denominator: '2' } },
    { ELIGIBLE_EVALUATED: 2 },
  )
  const noDenominator = candidate(
    'synthetic.fixture.k5.zero-denominator',
    { numerator: 0, denominator: 0, rate: null },
    { REPLAY_GENERATION_FAILURE: 1, METRIC_UNAVAILABLE: 1 },
  )
  const buckets = [1, 2, 3, 5, 10, 20].map((native_k) => {
    if (native_k !== 5) {
      return {
        bucket: 'K' + native_k,
        native_k,
        status:
          native_k === 20
            ? 'UNAVAILABLE_NO_CANONICAL_NATIVE_K20_STRATEGY'
            : 'UNAVAILABLE_NO_CANONICAL_NATIVE_STRATEGY',
        entry_identity: [],
        ranking_complete: false,
        selected: null,
        tickets: [],
        generation_status: 'NOT_RUN',
        generation_failure: null,
        semantic_tie: false,
        tied_strategy_ids: [],
        display_tie_break: 'strategy_id ASCENDING',
        ranked_strategy_ids: [],
        candidate_count: 0,
        rankable_count: 0,
        excluded_count: 0,
        candidates: [],
        baseline: null,
      }
    }
    return {
      bucket: 'K5',
      native_k,
      status: 'AVAILABLE',
      entry_identity: ['fixture-bundle', native_k, first.strategy_id, first.strategy_version],
      ranking_complete: true,
      selected: {
        strategy_id: first.strategy_id,
        strategy_version: first.strategy_version,
        response_shape: 'PORTFOLIO',
        metric: first.metric,
        coverage: first.coverage,
      },
      tickets: Array.from({ length: 5 }, (_, index) => [1, 2, 3, 4, 5, index + 6]),
      generation_status: 'COMPLETE',
      generation_failure: null,
      semantic_tie: false,
      tied_strategy_ids: [first.strategy_id],
      display_tie_break: 'strategy_id ASCENDING',
      ranked_strategy_ids: [first.strategy_id],
      candidate_count: 2,
      rankable_count: 1,
      excluded_count: 1,
      candidates: [first, noDenominator],
      baseline: { native_k: 5 },
    }
  })

  return {
    scope: {
      lottery_type: 'BIG_LOTTO',
      target_draw_number: target.target_draw_number,
      target_draw_date: target.target_draw_date,
      forecast_stream_id: 'B649_NEXT_UNDRAWN_FORECAST',
      forecast_stream_version: 'B649_FULL_OFFICIAL_ANY_PRIZE_R1',
    },
    request_identity: {
      request_id: 'fixture-request-1',
      request_sha256: 'a'.repeat(64),
      version: 1,
      run_id: 'fixture-run-1',
      payload_sha256: 'b'.repeat(64),
      generation_started_at: '2026-10-01T10:00:00Z',
      generation_finished_at: '2026-10-01T10:00:05Z',
      committed_at: '2026-10-01T10:00:06Z',
    },
    payload: {
      bundle_id: 'c'.repeat(64),
      fixture_only: false,
      identity: {
        schema_version: 'B649_NEXT_UNDRAWN_FORECAST_V1',
        lottery_type: 'BIG_LOTTO',
        target_draw_number: target.target_draw_number,
        target_draw_date: target.target_draw_date,
        schedule_authority_sha256: 'd'.repeat(64),
        history_cutoff: '115000099',
        history_payload_sha256: 'e'.repeat(64),
        objective: 'OFFICIAL_ANY_PRIZE',
        ranking_policy_version: 'B649_FULL_OFFICIAL_ANY_PRIZE_R1',
        producer_id: 'synthetic-fixture-producer',
        producer_version: 'fixture-version-1',
        producer_fingerprint: 'f'.repeat(64),
        catalog_universe_sha256: '1'.repeat(64),
        generation_config_sha256: '2'.repeat(64),
        output_buckets: [1, 2, 3, 5, 10, 20],
        output_top_n: 1,
      },
      history: {
        draw_count: 2,
        history_sha256: 'e'.repeat(64),
        last_draw_date: '2026-10-02',
        last_draw_number: '115000099',
      },
      buckets,
    },
  }
}

function setK5CandidateMetric(
  response: ReturnType<typeof nativeResponse>,
  index: number,
  metric: unknown,
  options: {
    rankable?: boolean
    coverage?: { requested: number; counts: Record<string, number>; eligible_expected: number }
  } = {},
): void {
  const k5 = response.payload.buckets.find((bucket) => bucket.native_k === 5)
  const targetCandidate = k5?.candidates[index] as unknown as Record<string, unknown> | undefined
  if (!targetCandidate) throw new Error('K5 fixture candidate missing')
  targetCandidate.metric = metric
  if (options.rankable !== undefined) targetCandidate.rankable = options.rankable
  if (options.coverage !== undefined) targetCandidate.coverage = options.coverage
}

const nativePositionsTarget = { target_draw_number: '115000098', target_draw_date: '2099-01-01' }

function nativePositionsResponse() {
  const response = nativeResponse(nativePositionsTarget)
  const { payload } = response
  const tickets = (start: number) =>
    Array.from({ length: 5 }, (_, index) => [1, 2, 3, 4, 5, start + index])
  const native_strategies = [0, 1, 2].map((index) => ({
    strategy_id: 'synthetic.native.k5.' + index,
    strategy_version: 'v0.1',
    native_k: 5,
    source_rank: index + 1,
    adapter_source_sha256: String(index + 1).repeat(64),
    native_positions: tickets(6 + index * 5).map((numbers, position) => ({
      position: position + 1,
      numbers,
    })),
  }))
  const {
    strategy_id, strategy_version, native_k, adapter_source_sha256, native_positions,
  } = native_strategies[0]
  const available = {
    bucket: 'K5:' + strategy_id,
    native_k,
    status: 'AVAILABLE',
    generation_status: 'COMPLETE',
    selected: { strategy_id, strategy_version },
    entry_identity: [payload.bundle_id, native_k, strategy_id, strategy_version],
    candidates: [{ strategy_id, strategy_version, native_k, adapter_source_sha256 }],
    tickets: native_positions.map(({ numbers }) => [...numbers]),
    native_positions: structuredClone(native_positions),
  }
  const sha256 = payload.identity.history_payload_sha256
  return {
    ...response,
    payload: {
      ...payload,
      identity: { ...payload.identity, history_cutoff: '115000097' },
      forecast_output_semantics: 'STRATEGY_NATIVE_POSITIONS',
      source_proof_status: 'LOCAL_ONLY',
      history: { reference: 'research-live-history:sha256:' + sha256, sha256 },
      native_strategies,
      buckets: payload.buckets.map((bucket) => bucket.native_k === 5 ? available : bucket),
    },
    available,
  }
}

function errorResponse(error_code: string, message: string) {
  return { error_code, message }
}

function canonicalForecast() {
  const ticket = (position: number) => ({
    ticket_position: position,
    predicted_numbers: [1, 2, 3, 4, 5, position + 5],
  })
  const tickets = (count: number) => Array.from({ length: count }, (_, index) => ticket(index + 1))
  return {
    status: 'AVAILABLE',
    authority: 'SCHEDULER_ARTIFACT',
    current_target: {
      draw_number: '115000099',
      draw_date: '2026-10-02',
      scheduled_at: '2026-10-02T20:30:00+08:00',
    },
    consensus_numbers: [1, 2, 3, 4, 5, 6],
    source_stream_count: 11,
    k5_tickets: tickets(5),
    k10_tickets: tickets(10),
    k20_tickets: tickets(20),
    forecast_actual_sha256: 'a'.repeat(64),
    forecast_method_id: 'B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS',
    forecast_method_version: '1.0.0',
    portfolio_actual_sha256: 'b'.repeat(64),
    portfolio_method_id: 'B649_SEALED_GEOMETRY_PORTFOLIO',
    portfolio_method_version: '8.0.0',
  }
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function submitTarget(wrapper: ReturnType<typeof mount>, target: Target) {
  await wrapper.get('[data-testid="native-target-draw-number"]').setValue(target.target_draw_number)
  await wrapper.get('[data-testid="native-target-draw-date"]').setValue(target.target_draw_date)
  await wrapper.get('form').trigger('submit')
}

describe('B649 Native Forecast consumer', () => {
  it('renders the schema 6 main bucket in source order and reports all native positions separately', async () => {
    const { available, ...response } = nativePositionsResponse()
    fetchMock
      .mockResolvedValueOnce(apiResponse(response))
      .mockResolvedValueOnce(apiResponse(errorResponse('NOT_FOUND', 'target missing'), 404))
    const wrapper = mount(B649NativeForecastPanel)

    await submitTarget(wrapper, nativePositionsTarget)
    await flushPromises()

    const displayed = wrapper.findAll('[data-testid="native-selected-ticket"]')
    expect(displayed.map((row) => row.get('strong').text())).toEqual(
      available.tickets.map((numbers) => numbers.join(' · ')),
    )
    expect(displayed).toHaveLength(5)
    expect(wrapper.get('[data-testid="native-position-totals"]').text()).toContain('3 組策略、15 注')
    expect(wrapper.get('[data-testid="native-strategy-count"]').text()).toContain('1 筆')
    expect(wrapper.get('[data-testid="native-history-cutoff-date"]').text()).toBe('未提供')
    expect(wrapper.get('[data-testid="native-evidence-boundary"]').text()).toContain('LOCAL_ONLY')
    const labels = wrapper.get('[data-testid="native-strategy-candidate"]').findAll('dd')
    expect(labels[2].text()).toBe('未提供')
    expect(labels[4].text()).toBe('未提供')

    await submitTarget(wrapper, { ...nativePositionsTarget, target_draw_date: '2099-01-02' })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('所選期別沒有 Native 資料')
    expect(wrapper.findAll('[data-testid="native-selected-ticket"]')).toHaveLength(0)
    expect(wrapper.find('[data-testid="native-position-totals"]').exists()).toBe(false)
    wrapper.unmount()
  })

  const schema6Mutations: [string, (fixture: ReturnType<typeof nativePositionsResponse>) => void][] = [
    ['mismatched target', ({ scope }) => { scope.target_draw_number = '115000099' }],
    ['noncausal cutoff', ({ payload }) => { payload.identity.history_cutoff = '115000098' }],
    ['mismatched history hash', ({ payload }) => { payload.history.sha256 = '0'.repeat(64) }],
    ['unbound history reference', ({ payload }) => { payload.history.reference = 'unbound' }],
    ['missing semantics', ({ payload }) => { payload.forecast_output_semantics = '' }],
    ['unsupported proof claim', ({ payload }) => { payload.source_proof_status = 'EXTERNAL' }],
    ['unbound bucket ID', ({ available }) => { available.bucket = 'K5' }],
    ['wrong strategy version', ({ available }) => { available.selected.strategy_version = 'wrong' }],
    ['wrong adapter hash', ({ available }) => { available.candidates[0].adapter_source_sha256 = '0'.repeat(64) }],
    ['wrong native strategy ticket count', ({ payload }) => { payload.native_strategies[2].native_positions.pop() }],
    ['wrong main bucket ticket count', ({ available }) => { available.tickets.pop() }],
    ['out of order positions', ({ available }) => { available.native_positions.reverse() }],
    ['out of order main tickets', ({ available }) => { available.tickets.reverse() }],
    ['nonlegal ticket', ({ payload }) => { payload.native_strategies[2].native_positions[0].numbers[0] = 50 }],
    ['wrong bucket bundle', ({ available }) => { available.entry_identity[0] = '0'.repeat(64) }],
    ['invalid metric supplied', ({ available }) => {
      Object.assign(available.candidates[0], {
        metric: { numerator: 5, denominator: 100, rate: { numerator: '5', denominator: '100' } },
      })
    }],
  ]

  it.each(schema6Mutations)('rejects invalid schema 6 data: %s', async (_label, mutate) => {
    const response = nativePositionsResponse()
    mutate(response)
    const { available: _bucket, ...body } = response
    fetchMock.mockResolvedValueOnce(apiResponse(body))

    await expect(fetchB649NativeForecast(nativePositionsTarget)).rejects.toMatchObject({
      kind: 'MALFORMED_RESPONSE',
      status: 200,
    })
  })

  it.each([
    [
      '0/100',
      { numerator: 0, denominator: 100, rate: { numerator: '0', denominator: '1' } },
      '0 / 100（0.00%）',
    ],
    [
      '5/100',
      { numerator: 5, denominator: 100, rate: { numerator: '1', denominator: '20' } },
      '5 / 100（5.00%）',
    ],
    [
      '100/100',
      { numerator: 100, denominator: 100, rate: { numerator: '1', denominator: '1' } },
      '100 / 100（100.00%）',
    ],
  ] as const)('renders the original denominator for %s', async (_label, metric, expected) => {
    const target = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    const response = nativeResponse(target)
    setK5CandidateMetric(response, 1, metric, {
      rankable: true,
      coverage: {
        requested: 100,
        counts: { ELIGIBLE_EVALUATED: 100 },
        eligible_expected: 100,
      },
    })
    fetchMock.mockResolvedValueOnce(apiResponse(response))
    const wrapper = mount(B649NativeForecastPanel)

    await submitTarget(wrapper, target)
    await flushPromises()

    const metricText = wrapper.findAll('[data-testid="native-strategy-candidate"]')[1].text()
    expect(metricText).toContain(expected)
    expect(metricText).not.toContain('無法評估')
  })

  it('preserves source coverage states without deriving the exact metric from them', async () => {
    const target = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    const response = nativeResponse(target)
    setK5CandidateMetric(
      response,
      1,
      { numerator: 5, denominator: 100, rate: { numerator: '1', denominator: '20' } },
      {
        rankable: true,
        coverage: {
          requested: 103,
          counts: {
            ELIGIBLE_EVALUATED: 100,
            FAILED: 1,
            UNKNOWN: 1,
            NOT_ELIGIBLE: 1,
          },
          eligible_expected: 100,
        },
      },
    )
    fetchMock.mockResolvedValueOnce(apiResponse(response))
    const wrapper = mount(B649NativeForecastPanel)

    await submitTarget(wrapper, target)
    await flushPromises()

    const metricText = wrapper.findAll('[data-testid="native-strategy-candidate"]')[1].text()
    expect(metricText).toContain('5 / 100（5.00%）')
    expect(metricText).toContain('FAILED: 1')
    expect(metricText).toContain('UNKNOWN: 1')
    expect(metricText).toContain('NOT_ELIGIBLE: 1')
    expect(metricText).not.toContain('5 / 103')
  })

  it.each([
    ['missing numerator', { denominator: 100, rate: { numerator: '0', denominator: '1' } }],
    ['missing denominator', { numerator: 0, rate: { numerator: '0', denominator: '1' } }],
    ['NULL numerator', { numerator: null, denominator: 100, rate: null }],
    ['NULL denominator', { numerator: 0, denominator: null, rate: null }],
    ['missing rate', { numerator: 0, denominator: 100 }],
    ['NULL rate with a positive denominator', { numerator: 0, denominator: 100, rate: null }],
    ['non-NULL rate with a zero denominator', { numerator: 0, denominator: 0, rate: { numerator: '0', denominator: '1' } }],
    ['negative numerator', { numerator: -1, denominator: 100, rate: { numerator: '-1', denominator: '100' } }],
    ['negative denominator', { numerator: 0, denominator: -100, rate: null }],
    ['fractional numerator', { numerator: 0.5, denominator: 100, rate: { numerator: '1', denominator: '200' } }],
    ['fractional denominator', { numerator: 0, denominator: 100.5, rate: { numerator: '0', denominator: '1' } }],
    ['numerator greater than denominator', { numerator: 101, denominator: 100, rate: { numerator: '101', denominator: '100' } }],
    ['rate inconsistent with raw counts', { numerator: 0, denominator: 100, rate: { numerator: '0', denominator: '100' } }],
  ] as const)('rejects invalid metric data: %s', async (_label, metric) => {
    const target = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    const response = nativeResponse(target)
    setK5CandidateMetric(response, 1, metric)
    fetchMock.mockResolvedValueOnce(apiResponse(response))

    await expect(fetchB649NativeForecast(target)).rejects.toMatchObject({
      name: 'B649NativeForecastRequestError',
      kind: 'MALFORMED_RESPONSE',
      status: 200,
    })
  })

  it('sends the explicit target and separates the selected K5 bucket from strategy details', async () => {
    const target = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    const response = nativeResponse(target)
    fetchMock.mockResolvedValueOnce(apiResponse(response))
    const wrapper = mount(B649NativeForecastPanel)

    await submitTarget(wrapper, target)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/b649/native-forecast/current?target_draw_number=115000100&target_draw_date=2026-10-03',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(wrapper.get('[data-testid="native-scope-draw-number"]').text()).toBe('115000100')
    expect(wrapper.get('[data-testid="native-scope-draw-date"]').text()).toBe('2026-10-03')
    expect(wrapper.get('[data-testid="native-history-cutoff"]').text()).toBe('115000099')
    expect(wrapper.text()).toContain('2026-10-01T10:00:00Z')
    expect(wrapper.text()).toContain('2026-10-01T10:00:05Z')
    expect(wrapper.text()).toContain('2026-10-01T10:00:06Z')
    expect(wrapper.text()).toContain('fixture-request-1')
    expect(wrapper.text()).toContain('fixture-run-1')
    expect(wrapper.text()).toContain('LOCAL_ONLY')
    expect(wrapper.text()).toContain('未確認')
    expect(wrapper.text()).toContain('fixture_only=false')
    expect(wrapper.text()).toContain('issued_at')
    expect(wrapper.text()).toContain('未提供')

    expect(wrapper.get('[data-testid="native-k5-status"]').text()).toBe('AVAILABLE')
    expect(wrapper.get('[data-testid="native-k5-selection"]').text()).toContain(
      'synthetic.fixture.k5.alpha',
    )
    expect(wrapper.findAll('[data-testid="native-selected-ticket"]')).toHaveLength(5)
    expect(wrapper.findAll('[data-testid="native-strategy-candidate"]')).toHaveLength(2)
    expect(wrapper.get('[data-testid="native-strategy-count"]').text()).toContain('2 筆')
    const detailText = wrapper.findAll('[data-testid="native-strategy-candidate"]')
    expect(detailText[0].text()).toContain('1 / 2（50.00%）')
    expect(detailText[1].text()).toContain('無法評估')
    expect(detailText[1].text()).toContain('REPLAY_GENERATION_FAILURE: 1')
    expect(detailText[1].text()).not.toContain('0.00%')
    expect(detailText[0].findAll('[data-testid="native-selected-ticket"]')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('未中獎')
  })

  it('rejects a response whose scope belongs to a different target', async () => {
    const requested = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    const mismatched = nativeResponse({
      target_draw_number: '115000101',
      target_draw_date: '2026-10-04',
    })
    fetchMock.mockResolvedValueOnce(apiResponse(mismatched))
    const wrapper = mount(B649NativeForecastPanel)

    await submitTarget(wrapper, requested)
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('不一致')
    expect(wrapper.find('[data-testid="native-scope-draw-number"]').exists()).toBe(false)
  })

  it('rejects a history cutoff that is not strictly before the requested target', async () => {
    const target = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    const response = nativeResponse(target)
    response.payload.identity.history_cutoff = target.target_draw_number
    response.payload.history.last_draw_number = target.target_draw_number
    fetchMock.mockResolvedValueOnce(apiResponse(response))

    await expect(fetchB649NativeForecast(target)).rejects.toMatchObject({
      name: 'B649NativeForecastRequestError',
      kind: 'MALFORMED_RESPONSE',
      status: 200,
    } satisfies Partial<B649NativeForecastRequestError>)
  })

  it('renders a NULL metric as unavailable instead of zero percent', async () => {
    const target = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    const response = nativeResponse(target)
    const k5 = response.payload.buckets.find((bucket) => bucket.native_k === 5)
    if (!k5) throw new Error('K5 fixture missing')
    k5.candidates[1].metric = null
    fetchMock.mockResolvedValueOnce(apiResponse(response))
    const wrapper = mount(B649NativeForecastPanel)

    await submitTarget(wrapper, target)
    await flushPromises()

    const unavailableMetric = wrapper.findAll('[data-testid="native-strategy-candidate"]')[1]
    expect(unavailableMetric.text()).toContain('無法評估')
    expect(unavailableMetric.text()).not.toContain('0.00%')
  })

  it.each([
    [404, 'NOT_FOUND', '所選期別沒有 Native 資料。'],
    [409, 'CONFLICT', '完整性衝突'],
    [422, 'VALIDATION', '期別或日期無效'],
    [503, 'UNAVAILABLE', '無法使用'],
  ] as const)('shows the HTTP %s state and clears data', async (status, kind, message) => {
    const target = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    fetchMock.mockResolvedValue(apiResponse(errorResponse('NATIVE_ERROR', 'source message'), status))
    const wrapper = mount(B649NativeForecastPanel)

    await submitTarget(wrapper, target)
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(message)
    expect(wrapper.find('[data-testid="native-k5-status"]').exists()).toBe(false)
    await expect(fetchB649NativeForecast(target)).rejects.toMatchObject({ kind })
  })

  it('clears the previous Native result when a later target fails', async () => {
    const first = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    const second = { target_draw_number: '115000101', target_draw_date: '2026-10-04' }
    fetchMock
      .mockResolvedValueOnce(apiResponse(nativeResponse(first)))
      .mockResolvedValueOnce(apiResponse(errorResponse('CONFLICT', 'integrity failure'), 409))
    const wrapper = mount(B649NativeForecastPanel)

    await submitTarget(wrapper, first)
    await flushPromises()
    expect(wrapper.find('[data-testid="native-k5-status"]').exists()).toBe(true)

    await submitTarget(wrapper, second)
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('完整性衝突')
    expect(wrapper.find('[data-testid="native-k5-status"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="native-scope-draw-number"]').exists()).toBe(false)
  })

  it('supports the FastAPI 422 validation union fields', async () => {
    const target = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    fetchMock.mockResolvedValue(
      apiResponse(
        {
          error_code: 'REQUEST_VALIDATION_FAILED',
          message: 'Request validation failed.',
          fields: [{ location: 'query.target_draw_number', type: 'string_pattern_mismatch' }],
        },
        422,
      ),
    )

    await expect(fetchB649NativeForecast(target)).rejects.toMatchObject({
      kind: 'VALIDATION',
      message: expect.stringContaining('Request validation failed.'),
    })
    await expect(fetchB649NativeForecast(target)).rejects.toMatchObject({
      message: expect.stringContaining('query.target_draw_number'),
    })
  })

  it('reports invalid JSON and network errors without keeping old results', async () => {
    const target = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    const invalidJson = apiResponse(null)
    invalidJson.json = vi.fn().mockRejectedValueOnce(new SyntaxError('invalid json'))
    fetchMock.mockResolvedValueOnce(invalidJson)
    await expect(fetchB649NativeForecast(target)).rejects.toMatchObject({
      kind: 'MALFORMED_RESPONSE',
    })

    fetchMock.mockRejectedValueOnce(new TypeError('offline'))
    await expect(fetchB649NativeForecast(target)).rejects.toMatchObject({ kind: 'NETWORK' })
  })

  it('keeps Canonical and Native failures isolated in the combined page', async () => {
    const target = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    fetchMock.mockImplementation((input) => {
      if (String(input).startsWith('/api/b649/canonical-forecast/current')) {
        return Promise.resolve(apiResponse(canonicalForecast()))
      }
      return Promise.resolve(apiResponse(errorResponse('UNAVAILABLE', 'offline'), 503))
    })
    const canonicalValidPage = mount(B649CurrentForecastPage)
    await flushPromises()
    expect(canonicalValidPage.findAll('[data-testid="b649-ticket-k5"]')).toHaveLength(5)
    await submitTarget(canonicalValidPage, target)
    await flushPromises()
    expect(canonicalValidPage.findAll('[data-testid="b649-ticket-k5"]')).toHaveLength(5)
    expect(canonicalValidPage.find('[data-testid="native-k5-status"]').exists()).toBe(false)
    canonicalValidPage.unmount()

    fetchMock.mockImplementation((input) => {
      if (String(input).startsWith('/api/b649/canonical-forecast/current')) {
        return Promise.resolve(apiResponse(errorResponse('AUTHORITY_UNAVAILABLE', 'offline'), 503))
      }
      return Promise.resolve(apiResponse(nativeResponse(target)))
    })
    const nativeValidPage = mount(B649CurrentForecastPage)
    await flushPromises()
    expect(nativeValidPage.find('.b649-current-forecast__unavailable').exists()).toBe(true)
    expect(nativeValidPage.find('[data-testid="native-k5-status"]').exists()).toBe(false)
    await submitTarget(nativeValidPage, target)
    await flushPromises()
    expect(nativeValidPage.get('[data-testid="native-scope-draw-number"]').text()).toBe(
      target.target_draw_number,
    )
    expect(nativeValidPage.find('.b649-current-forecast__unavailable').exists()).toBe(true)
  })

  it('does not let a slower old target overwrite the latest target', async () => {
    const pending: Array<{
      target: Target
      resolve: (response: Response) => void
      signal: AbortSignal | null | undefined
    }> = []
    fetchMock.mockImplementation((input, init) => {
      const url = new URL(String(input), 'http://localhost')
      const target = {
        target_draw_number: url.searchParams.get('target_draw_number') ?? '',
        target_draw_date: url.searchParams.get('target_draw_date') ?? '',
      }
      return new Promise<Response>((resolve) => {
        pending.push({ target, resolve, signal: init?.signal })
      })
    })
    const wrapper = mount(B649NativeForecastPanel)
    const first = { target_draw_number: '115000100', target_draw_date: '2026-10-03' }
    const second = { target_draw_number: '115000101', target_draw_date: '2026-10-04' }

    await submitTarget(wrapper, first)
    await submitTarget(wrapper, second)
    expect(pending[0].signal?.aborted).toBe(true)
    pending[1].resolve(apiResponse(nativeResponse(second)))
    await flushPromises()
    pending[0].resolve(apiResponse(nativeResponse(first)))
    await flushPromises()

    expect(wrapper.get('[data-testid="native-scope-draw-number"]').text()).toBe(
      second.target_draw_number,
    )
  })

  it('aborts an unfinished request when the panel unmounts', async () => {
    let requestSignal: AbortSignal | null | undefined
    fetchMock.mockImplementation((_input, init) => {
      requestSignal = init?.signal
      return new Promise<Response>(() => {})
    })
    const wrapper = mount(B649NativeForecastPanel)
    await submitTarget(wrapper, {
      target_draw_number: '115000100',
      target_draw_date: '2026-10-03',
    })

    wrapper.unmount()
    expect(requestSignal?.aborted).toBe(true)
  })
})
