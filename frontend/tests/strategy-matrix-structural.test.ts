import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  queryStrategyMatrixStructural,
  StrategyMatrixStructuralRequestError,
  type StrategyMatrixStructuralResponse,
} from '../src/api/strategyMatrixStructural'

function makeResponse(
  overrides: Partial<StrategyMatrixStructuralResponse> = {},
): StrategyMatrixStructuralResponse {
  return {
    schema_id: 'lottolab.strategy_matrix.structural',
    schema_version: '1.0.0',
    projection_sha256: 'e98f564e401cf4e380fa6e66eeb819409e2f0dc8b3d6ad9b3ec046d68483a246',
    authority: {
      kind: 'CANONICAL_PACKAGED_MATRIX',
      source_head: 'c6b03e2b6eb7219a35d619607897cc6969e95fce',
      source_tree: '0b0b6079e37257273ef41fe333b3c98fa11f1864',
      sources: {
        metric_surface: {
          repository_path: 'docs/research/matrix-native-results/expected-max-main-matches-v1-result.json',
          file_sha256: '2672c958d009cf7e3c09f54d30c1c536c92165ade54af85ce5cfb38a9f977c85',
        },
        matrix: {
          repository_path: 'docs/research/matrix-native-results/imported-optimizer-integration-r1-result.json',
          file_sha256: 'ca94489292a666e4521698d7b21314c7faca6e0881c82deb093bd21b344d88a0',
        },
        ledger: {
          repository_path: 'docs/research/cross_lottery_research_ledger_r1.json',
          file_sha256: '2b8e70c1f5cae670b9f8b01373906b8ed545dd04e87e51a020abeb90e20fe63a',
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
    cells: [
      {
        row_id: 'NATIVE_BIG_LOTTO|ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1|default|k20|m3',
        case_id: 'NATIVE_BIG_LOTTO',
        lottery: 'BIG_LOTTO',
        method_id: 'ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1',
        ticket_count: 20,
        method_objective: 'EXPECTED_MAX_MAIN_MATCHES_V1',
        source_status: 'MEASURED',
        measurement_status: 'MEASURED',
        value: { numerator: '8249099', denominator: '3495954' },
        portfolio_sha256: '86ccf20ecc149a78771295fa68685220b5726f43baa87dbef745655db972d686',
        unavailable_reason: null,
        local_optimum_status: 'COMPLETE_RADIUS_1_LOCAL_OPTIMUM',
      },
    ],
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
    expect(result.cells[0].value).toEqual({ numerator: '8249099', denominator: '3495954' })
  })

  it('builds the query string only from the filters actually supplied', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeResponse()))

    await queryStrategyMatrixStructural({
      lottery: 'BIG_LOTTO',
      methodId: 'ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1',
      ticketCount: 20,
    })

    const [url] = fetchMock.mock.calls[0] as [string]
    const parameters = new URL(url, 'https://example.test').searchParams
    expect(parameters.get('lottery')).toBe('BIG_LOTTO')
    expect(parameters.get('method_id')).toBe('ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1')
    expect(parameters.get('ticket_count')).toBe('20')
  })

  it('parses a typed NOT_APPLICABLE cell without a value', async () => {
    fetchMock.mockResolvedValue(
      apiResponse(
        makeResponse({
          cells: [
            {
              row_id: 'NATIVE_BIG_LOTTO|B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1|default|k2|m3',
              case_id: 'NATIVE_BIG_LOTTO',
              lottery: 'BIG_LOTTO',
              method_id: 'B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1',
              ticket_count: 2,
              method_objective: 'LEXICOGRAPHIC_MINIMUM_EXPOSURE_VECTOR_THEN_INPUT_ORDER',
              source_status: 'NOT_APPLICABLE',
              measurement_status: 'NOT_APPLICABLE',
              value: null,
              portfolio_sha256: null,
              unavailable_reason: 'NO_CANONICAL_PORTFOLIO_STORED:UNSUPPORTED_LOTTERY_OR_K',
              local_optimum_status: null,
            },
          ],
        }),
      ),
    )

    const result = await queryStrategyMatrixStructural()

    expect(result.cells[0].measurement_status).toBe('NOT_APPLICABLE')
    expect(result.cells[0].value).toBeNull()
    expect(result.cells[0].unavailable_reason).toBe('NO_CANONICAL_PORTFOLIO_STORED:UNSUPPORTED_LOTTERY_OR_K')
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

  it('fails closed when the response contract is malformed', async () => {
    const malformed = makeResponse()
    const { schema_id: _schemaId, ...withoutSchemaId } = malformed
    fetchMock.mockResolvedValue(apiResponse(withoutSchemaId))

    await expect(queryStrategyMatrixStructural()).rejects.toBeInstanceOf(
      StrategyMatrixStructuralRequestError,
    )
  })
})
