import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  queryStrategyMatrixStructural,
  StrategyMatrixStructuralRequestError,
  type StrategyMatrixStructuralQuery,
  type StrategyMatrixStructuralResponse,
  type StructuralMatrixCell,
} from '../src/api/strategyMatrixStructural'

function makeCell(overrides: Partial<StructuralMatrixCell> = {}): StructuralMatrixCell {
  return {
    row_id: 'NATIVE_BIG_LOTTO|CYCLIC_SIDON_SHIFT_V1|default|k2|m3',
    case_id: 'NATIVE_BIG_LOTTO',
    lottery: 'BIG_LOTTO',
    method_id: 'CYCLIC_SIDON_SHIFT_V1',
    ticket_count: 2,
    method_objective: 'CYCLIC_DIFFERENCE_SET_PAIRWISE_OVERLAP_AT_MOST_ONE',
    source_status: 'MEASURED',
    measurement_status: 'MEASURED',
    value: { numerator: '15624809', denominator: '13983816' },
    portfolio_sha256: 'f1b846bbf38d5ee2c103479609c8d49002d912a2d20f3360b5b03938763a5ac2',
    unavailable_reason: null,
    local_optimum_status: null,
    ...overrides,
  }
}

function makeResponse(
  overrides: Partial<StrategyMatrixStructuralResponse> = {},
): StrategyMatrixStructuralResponse {
  return {
    schema_id: 'lottolab.strategy_matrix.structural',
    schema_version: '1.0.0',
    projection_sha256: '428e06ad4e7d4fbd6205098950bb7671d8f97995493abb395df15be1785a253e',
    authority: {
      kind: 'CANONICAL_PACKAGED_MATRIX',
      source_head: '9486a67ed358c96435cc8b913962380c3db6b100',
      source_tree: 'd53c0a23f9df12127f2ea16d480705c146f4e62b',
      sources: {
        metric_surface: {
          repository_path: 'docs/research/matrix-native-results/expected-max-main-matches-v1-result.json',
          file_sha256: 'bb0cb899dd301711f926617e74af01d14ce7c134b7ed96f7ae0acefcfa532d85',
        },
        matrix: {
          repository_path: 'docs/research/matrix-native-results/imported-optimizer-integration-r1-result.json',
          file_sha256: '0c2cfa9d1ec90238699f1a878ec00ef98aa29b14bb02cacbade38159c8cee802',
        },
        ledger: {
          repository_path: 'docs/research/cross_lottery_research_ledger_r1.json',
          file_sha256: '56a6d801636afeb883a2937762cf123ef2fa96a763f13bcb748dce32b66995d9',
        },
      },
    },
    scope: 'NATIVE_UNIFORM_WINNING_SPACE',
    supported_ticket_counts: [2, 3, 5, 10, 20],
    metric: {
      metric_id: 'EXPECTED_MAX_MAIN_MATCHES_V1',
      definition: 'E[max_t |t intersection D|]',
      unit: 'MAIN_MATCHES',
      draw_distribution: 'LEGAL_UNIFORM_MAIN_DRAW',
      exactness: 'EXACT_COMBINATORIAL_EXPECTATION',
    },
    claim_boundary: {
      historical_outcomes_used: false,
      historical_success_rate_claimed: false,
      ranking_score_claimed: false,
      global_optimum_claimed: false,
      cross_lottery_normalization: 'NOT_PERFORMED',
    },
    cells: [makeCell()],
    ...overrides,
  }
}

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function responseWithCell(overrides: Record<string, unknown>): unknown {
  return {
    ...makeResponse(),
    cells: [{ ...makeCell(), ...overrides }],
  }
}

async function expectMalformedResponse(
  payload: unknown,
  query?: StrategyMatrixStructuralQuery,
): Promise<void> {
  fetchMock.mockResolvedValue(apiResponse(payload))

  await expect(queryStrategyMatrixStructural(query)).rejects.toMatchObject({
    name: 'StrategyMatrixStructuralRequestError',
    status: 502,
  })
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('queryStrategyMatrixStructural', () => {
  it('fetches the full snapshot with no query string when no filters are given', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeResponse()))

    const result = await queryStrategyMatrixStructural()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/strategy-matrix/structural',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result.cells).toHaveLength(1)
    expect(result.cells[0].value).toEqual({ numerator: '15624809', denominator: '13983816' })
    expect(result.projection_sha256).toBe(
      '428e06ad4e7d4fbd6205098950bb7671d8f97995493abb395df15be1785a253e',
    )
  })

  it('builds the query string only from the filters actually supplied', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeResponse()))

    await queryStrategyMatrixStructural({
      lottery: 'BIG_LOTTO',
      methodId: 'CYCLIC_SIDON_SHIFT_V1',
      ticketCount: 2,
    })

    const [url] = fetchMock.mock.calls[0] as [string]
    const parameters = new URL(url, 'https://example.test').searchParams
    expect(parameters.get('lottery')).toBe('BIG_LOTTO')
    expect(parameters.get('method_id')).toBe('CYCLIC_SIDON_SHIFT_V1')
    expect(parameters.get('ticket_count')).toBe('2')
  })

  it('keeps the complete projection identity when the returned cells are filtered', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeResponse()))

    const result = await queryStrategyMatrixStructural({
      lottery: 'BIG_LOTTO',
      methodId: 'CYCLIC_SIDON_SHIFT_V1',
      ticketCount: 2,
    })

    expect(result.projection_sha256).toBe(
      '428e06ad4e7d4fbd6205098950bb7671d8f97995493abb395df15be1785a253e',
    )
  })

  it('rejects a filtered response containing a different lottery', async () => {
    await expectMalformedResponse(makeResponse(), { lottery: 'DAILY_539' })
  })

  it('rejects a filtered response containing a different method', async () => {
    await expectMalformedResponse(makeResponse(), { methodId: 'GREEDY_MIN_OVERLAP_V1' })
  })

  it('rejects a filtered response containing a different ticket count', async () => {
    await expectMalformedResponse(makeResponse(), { ticketCount: 3 })
  })

  it('parses a typed NOT_APPLICABLE cell without a value', async () => {
    const cell = makeCell({
      row_id: 'NATIVE_BIG_LOTTO|B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1|default|k2|m3',
      method_id: 'B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1',
      method_objective: 'LEXICOGRAPHIC_MINIMUM_EXPOSURE_VECTOR_THEN_INPUT_ORDER',
      source_status: 'NOT_APPLICABLE',
      measurement_status: 'NOT_APPLICABLE',
      value: null,
      portfolio_sha256: null,
      unavailable_reason: 'NO_CANONICAL_PORTFOLIO_STORED:UNSUPPORTED_LOTTERY_OR_K',
      local_optimum_status: null,
    })
    fetchMock.mockResolvedValue(apiResponse(makeResponse({ cells: [cell] })))

    const result = await queryStrategyMatrixStructural()

    expect(result.cells[0].measurement_status).toBe('NOT_APPLICABLE')
    expect(result.cells[0].value).toBeNull()
    expect(result.cells[0].unavailable_reason).toBe('NO_CANONICAL_PORTFOLIO_STORED:UNSUPPORTED_LOTTERY_OR_K')
  })

  it('preserves exact rational strings without converting them to Number', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeResponse()))

    const result = await queryStrategyMatrixStructural()

    expect(result.cells[0].value).toEqual({ numerator: '15624809', denominator: '13983816' })
    expect(typeof result.cells[0].value?.numerator).toBe('string')
    expect(typeof result.cells[0].value?.denominator).toBe('string')
  })

  it('fails closed with the public error_code on a 422 response', async () => {
    fetchMock.mockResolvedValue(
      apiResponse(
        {
          error_code: 'REQUEST_VALIDATION_FAILED',
          message: 'Request validation failed.',
          fields: [{ location: 'query.lottery', type: 'enum' }],
        },
        422,
      ),
    )

    await expect(queryStrategyMatrixStructural({ lottery: 'BIG_LOTTO' })).rejects.toMatchObject({
      status: 422,
      errorCode: 'REQUEST_VALIDATION_FAILED',
    })
  })

  it('fails closed with the public error_code on a 503 authority-unavailable response', async () => {
    fetchMock.mockResolvedValue(
      apiResponse(
        {
          error_code: 'STRUCTURAL_MATRIX_AUTHORITY_UNAVAILABLE',
          message: 'Canonical structural Matrix authority is unavailable.',
        },
        503,
      ),
    )

    await expect(queryStrategyMatrixStructural()).rejects.toMatchObject({
      status: 503,
      errorCode: 'STRUCTURAL_MATRIX_AUTHORITY_UNAVAILABLE',
    })
  })

  it('converts malformed HTTP 200 responses to status 502', async () => {
    await expectMalformedResponse({ schema_id: 'not-the-structural-matrix' })
  })

  it('converts an unreadable HTTP 200 body to status 502', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockRejectedValue(new SyntaxError('invalid JSON')),
    } as unknown as Response)

    await expect(queryStrategyMatrixStructural()).rejects.toMatchObject({
      name: 'StrategyMatrixStructuralRequestError',
      status: 502,
    })
  })

  it('preserves AbortError from fetch', async () => {
    const abortError = new DOMException('The operation was aborted.', 'AbortError')
    fetchMock.mockRejectedValue(abortError)

    await expect(queryStrategyMatrixStructural()).rejects.toBe(abortError)
  })

  it('preserves AbortError while reading the response body', async () => {
    const abortError = new DOMException('The operation was aborted.', 'AbortError')
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockRejectedValue(abortError),
    } as unknown as Response)

    await expect(queryStrategyMatrixStructural()).rejects.toBe(abortError)
  })
})

describe('fixed authority, metric, and claim boundary', () => {
  it.each([
    ['schema_id', (payload: StrategyMatrixStructuralResponse) => (payload.schema_id = 'other')],
    ['schema_version', (payload: StrategyMatrixStructuralResponse) => (payload.schema_version = '2.0.0')],
    ['scope', (payload: StrategyMatrixStructuralResponse) => (payload.scope = 'HISTORICAL_OUTCOMES')],
    ['source kind', (payload: StrategyMatrixStructuralResponse) => (payload.authority.kind = 'OTHER')],
    ['source head', (payload: StrategyMatrixStructuralResponse) => (payload.authority.source_head = 'c6b03e2b6eb7219a35d619607897cc6969e95fce')],
    ['source tree', (payload: StrategyMatrixStructuralResponse) => (payload.authority.source_tree = '0b0b6079e37257273ef41fe333b3c98fa11f1864')],
    ['metric surface path', (payload: StrategyMatrixStructuralResponse) => (payload.authority.sources.metric_surface.repository_path = 'other.json')],
    ['metric surface checksum', (payload: StrategyMatrixStructuralResponse) => (payload.authority.sources.metric_surface.file_sha256 = 'a'.repeat(64))],
    ['matrix path', (payload: StrategyMatrixStructuralResponse) => (payload.authority.sources.matrix.repository_path = 'other.json')],
    ['matrix checksum', (payload: StrategyMatrixStructuralResponse) => (payload.authority.sources.matrix.file_sha256 = 'b'.repeat(64))],
    ['ledger path', (payload: StrategyMatrixStructuralResponse) => (payload.authority.sources.ledger.repository_path = 'other.json')],
    ['ledger checksum', (payload: StrategyMatrixStructuralResponse) => (payload.authority.sources.ledger.file_sha256 = 'c'.repeat(64))],
    ['metric definition', (payload: StrategyMatrixStructuralResponse) => (payload.metric.definition = 'different metric')],
    ['claim boundary', (payload: StrategyMatrixStructuralResponse) => (payload.claim_boundary.historical_success_rate_claimed = true)],
  ])('rejects a changed pinned %s', async (_label, mutate) => {
    const payload = structuredClone(makeResponse())
    mutate(payload)
    await expectMalformedResponse(payload)
  })

  it('rejects an invalid projection checksum', async () => {
    await expectMalformedResponse({ ...makeResponse(), projection_sha256: 'not-a-sha256' })
  })

  it('rejects a modified supported ticket-count list', async () => {
    await expectMalformedResponse({ ...makeResponse(), supported_ticket_counts: [2, 3, 5, 10] })
  })

  it('rejects extra top-level fields from a malformed success response', async () => {
    await expectMalformedResponse({ ...makeResponse(), historical_success_rate: 0.9 })
  })
})

describe('cell identity and fixed enums', () => {
  it.each([
    ['lottery enum', { lottery: 'UNKNOWN' }],
    ['method enum', { method_id: 'UNKNOWN' }],
    ['ticket count', { ticket_count: 4 }],
    ['boolean ticket count', { ticket_count: true }],
    ['case and lottery mapping', { case_id: 'NATIVE_DAILY_539' }],
    ['empty row id', { row_id: '' }],
    ['whitespace row id', { row_id: '   ' }],
    ['UNKNOWN placeholder', { row_id: 'UNKNOWN' }],
    ['null placeholder', { row_id: 'null' }],
    ['unfilled placeholder', { row_id: 'NATIVE_BIG_LOTTO|TBD|default|k2|m3' }],
  ])('rejects an invalid %s', async (_label, cellOverrides) => {
    await expectMalformedResponse(responseWithCell(cellOverrides))
  })

  it('rejects duplicate row identities', async () => {
    const cell = makeCell()
    await expectMalformedResponse(makeResponse({ cells: [cell, { ...cell }] }))
  })

  it('rejects extra fields on a cell', async () => {
    await expectMalformedResponse(
      responseWithCell({ source_history_success_rate: '0.9' }),
    )
  })
})

describe('source and measurement status pairings', () => {
  it.each([
    ['MEASURED/MEASURED', { source_status: 'MEASURED', measurement_status: 'MEASURED' }],
    ['REUSED_VERIFIED/MEASURED', { source_status: 'REUSED_VERIFIED', measurement_status: 'MEASURED' }],
    [
      'REUSED_VERIFIED/UNAVAILABLE',
      {
        source_status: 'REUSED_VERIFIED',
        measurement_status: 'UNAVAILABLE',
        value: null,
        portfolio_sha256: null,
        unavailable_reason: 'NO_CANONICAL_PORTFOLIO_STORED',
        local_optimum_status: null,
      },
    ],
    [
      'NOT_APPLICABLE/NOT_APPLICABLE',
      {
        source_status: 'NOT_APPLICABLE',
        measurement_status: 'NOT_APPLICABLE',
        value: null,
        portfolio_sha256: null,
        unavailable_reason: 'NOT_APPLICABLE_FOR_THIS_LOTTERY',
        local_optimum_status: null,
      },
    ],
    [
      'NOT_RUN/UNAVAILABLE',
      {
        source_status: 'NOT_RUN',
        measurement_status: 'UNAVAILABLE',
        value: null,
        portfolio_sha256: null,
        unavailable_reason: 'MEASUREMENT_NOT_RUN',
        local_optimum_status: null,
      },
    ],
  ])('accepts the fixed %s pairing', async (_label, cellOverrides) => {
    fetchMock.mockResolvedValue(apiResponse(responseWithCell(cellOverrides)))

    await expect(queryStrategyMatrixStructural()).resolves.toBeDefined()
  })

  it.each([
    ['MEASURED/UNAVAILABLE', { source_status: 'MEASURED', measurement_status: 'UNAVAILABLE' }],
    ['NOT_RUN/MEASURED', { source_status: 'NOT_RUN', measurement_status: 'MEASURED' }],
    ['NOT_APPLICABLE/UNAVAILABLE', { source_status: 'NOT_APPLICABLE', measurement_status: 'UNAVAILABLE' }],
    ['REUSED_VERIFIED/NOT_APPLICABLE', { source_status: 'REUSED_VERIFIED', measurement_status: 'NOT_APPLICABLE' }],
  ])('rejects the non-contract %s pairing', async (_label, cellOverrides) => {
    await expectMalformedResponse(responseWithCell(cellOverrides))
  })
})

describe('measured and unavailable values', () => {
  it.each([
    ['measured null value', { value: null }],
    ['measured missing portfolio checksum', { portfolio_sha256: null }],
    ['measured malformed portfolio checksum', { portfolio_sha256: 'not-a-sha256' }],
    ['measured unavailable reason', { unavailable_reason: 'SHOULD_NOT_BE_PRESENT' }],
  ])('rejects %s', async (_label, cellOverrides) => {
    await expectMalformedResponse(responseWithCell(cellOverrides))
  })

  it.each([
    ['unavailable value', { value: { numerator: '1', denominator: '2' } }],
    ['unavailable portfolio checksum', { portfolio_sha256: 'f'.repeat(64) }],
    ['empty unavailable reason', { unavailable_reason: '' }],
    ['whitespace unavailable reason', { unavailable_reason: '   ' }],
    ['unavailable local optimum status', { local_optimum_status: 'COMPLETE_RADIUS_1_LOCAL_OPTIMUM' }],
  ])('rejects %s', async (_label, cellOverrides) => {
    await expectMalformedResponse(
      responseWithCell({
        source_status: 'REUSED_VERIFIED',
        measurement_status: 'UNAVAILABLE',
        value: null,
        portfolio_sha256: null,
        unavailable_reason: 'NO_CANONICAL_PORTFOLIO_STORED',
        local_optimum_status: null,
        ...cellOverrides,
      }),
    )
  })
})

describe('exact rational values', () => {
  it.each([
    ['zero denominator', '15624809', '0'],
    ['negative denominator', '15624809', '-2'],
    ['decimal denominator', '15624809', '1.5'],
    ['empty denominator', '15624809', ''],
    ['leading-zero denominator', '15624809', '013983816'],
    ['negative numerator', '-1', '2'],
    ['decimal numerator', '1.5', '2'],
    ['empty numerator', '', '2'],
    ['leading-zero numerator', '01', '2'],
  ])('rejects %s', async (_label, numerator, denominator) => {
    await expectMalformedResponse(
      responseWithCell({ value: { numerator, denominator } }),
    )
  })

  it('rejects an unreduced fraction', async () => {
    await expectMalformedResponse(
      responseWithCell({ value: { numerator: '31249618', denominator: '27967632' } }),
    )
  })

  it('rejects a value above the lottery draw-size bound', async () => {
    await expectMalformedResponse(
      responseWithCell({ value: { numerator: '83902897', denominator: '13983816' } }),
    )
  })
})
