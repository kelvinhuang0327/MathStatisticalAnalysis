import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  HistoricalImportsRequestError,
  listHistoricalImportRuns,
} from '../src/api/historicalImports'
import {
  HistoricalResultsRequestError,
  listHistoricalRunReplayPortfolios,
  listHistoricalRunStrategies,
} from '../src/api/historicalResults'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockJsonResponse(payload: unknown, status = 200): void {
  fetchMock.mockImplementation(() => Promise.resolve(jsonResponse(payload, status)))
}

const SAFE_MAX = Number.MAX_SAFE_INTEGER // 9007199254740991
const UNSAFE_INTEGER = SAFE_MAX + 1 // 9007199254740992

const validImportRunItem = {
  run_id: 'run-safe-1',
  import_identity_sha256: 'a'.repeat(64),
  source_kind: 'HISTORICAL_RESULTS',
  status: 'COMPLETED',
  strategy_count: 5,
  draw_count: 40,
  portfolio_count: 10,
  started_at: '2026-07-20T00:00:00Z',
  completed_at: '2026-07-20T01:00:00Z',
  is_idempotent_replay: false,
}

const validStrategySummaryItem = {
  strategy_id: 'strat-1',
  effective_strategy_id: 'strat-1',
  strategy_version: 'v1',
  replicate: 1,
  governance_status: 'ONLINE',
  evaluated_draws: 40,
  complete_portfolios: 40,
  m4plus_hit_count: 4,
}

const validReplayPortfolioItem = {
  portfolio_id: 'portfolio-1',
  strategy_id: 'strat-1',
  m4plus: true,
  tickets: [{ ticket_id: 't-1' }],
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Safe integer validation - Historical Imports API client', () => {
  describe('Query parameter validation', () => {
    it('accepts valid offset values: 0 and MAX_SAFE_INTEGER', async () => {
      mockJsonResponse({
        items: [],
        total_count: 0,
        limit: 50,
        offset: 0,
      })

      await expect(listHistoricalImportRuns(undefined, { offset: 0 })).resolves.toBeDefined()
      await expect(listHistoricalImportRuns(undefined, { offset: SAFE_MAX })).resolves.toBeDefined()
      expect(fetchMock).toHaveBeenCalledTimes(2)
    })

    it.each([
      [UNSAFE_INTEGER, 'unsafe integer above MAX_SAFE_INTEGER'],
      [-1, 'negative integer'],
      [1.5, 'floating point number'],
      [NaN, 'NaN'],
      [Infinity, 'Infinity'],
    ])('rejects non-safe query offset %j (%s) before HTTP fetch', async (offset) => {
      await expect(listHistoricalImportRuns(undefined, { offset })).rejects.toThrow(/offset/i)
      expect(fetchMock).not.toHaveBeenCalled()
    })
  })

  describe('Response payload counts validation', () => {
    it('accepts valid counts at boundaries (0 and MAX_SAFE_INTEGER) and empty run list', async () => {
      fetchMock.mockResolvedValue(
        jsonResponse({
          items: [
            {
              ...validImportRunItem,
              strategy_count: 0,
              draw_count: SAFE_MAX,
              portfolio_count: 0,
            },
          ],
          total_count: SAFE_MAX,
          limit: 50,
          offset: 0,
        }),
      )

      const result = await listHistoricalImportRuns()
      expect(result.items).toHaveLength(1)
      expect(result.items[0]?.draw_count).toBe(SAFE_MAX)
      expect(result.total_count).toBe(SAFE_MAX)
    })

    it('preserves legitimate empty run list as empty data rather than error', async () => {
      fetchMock.mockResolvedValue(
        jsonResponse({
          items: [],
          total_count: 0,
          limit: 50,
          offset: 0,
        }),
      )

      const result = await listHistoricalImportRuns()
      expect(result.items).toEqual([])
      expect(result.total_count).toBe(0)
    })

    it.each([
      ['total_count', UNSAFE_INTEGER],
      ['total_count', -1],
      ['total_count', 1.5],
      ['limit', UNSAFE_INTEGER],
      ['limit', -1],
      ['limit', 1.5],
      ['offset', UNSAFE_INTEGER],
      ['offset', -1],
      ['offset', 1.5],
    ])('rejects unsafe page count %s = %j with HistoricalImportsRequestError 502', async (field, value) => {
      fetchMock.mockResolvedValue(
        jsonResponse({
          items: [],
          total_count: 0,
          limit: 50,
          offset: 0,
          [field]: value,
        }),
      )

      await expect(listHistoricalImportRuns()).rejects.toSatisfy((err) => {
        expect(err).toBeInstanceOf(HistoricalImportsRequestError)
        expect((err as HistoricalImportsRequestError).status).toBe(502)
        return true
      })
    })

    it.each([
      ['strategy_count', UNSAFE_INTEGER],
      ['strategy_count', -1],
      ['strategy_count', 1.5],
      ['draw_count', UNSAFE_INTEGER],
      ['draw_count', -1],
      ['draw_count', 1.5],
      ['portfolio_count', UNSAFE_INTEGER],
      ['portfolio_count', -1],
      ['portfolio_count', 1.5],
    ])('rejects unsafe run item count %s = %j with HistoricalImportsRequestError 502', async (field, value) => {
      fetchMock.mockResolvedValue(
        jsonResponse({
          items: [
            {
              ...validImportRunItem,
              [field]: value,
            },
          ],
          total_count: 1,
          limit: 50,
          offset: 0,
        }),
      )

      await expect(listHistoricalImportRuns()).rejects.toSatisfy((err) => {
        expect(err).toBeInstanceOf(HistoricalImportsRequestError)
        expect((err as HistoricalImportsRequestError).status).toBe(502)
        return true
      })
    })
  })
})

describe('Safe integer validation - Historical Results API client', () => {
  describe('listHistoricalRunStrategies', () => {
    it('accepts safe integer boundary values (0 and MAX_SAFE_INTEGER)', async () => {
      fetchMock.mockResolvedValue(
        jsonResponse({
          run_id: 'run-1',
          ticket_count: 10,
          items: [
            {
              ...validStrategySummaryItem,
              replicate: 0,
              evaluated_draws: SAFE_MAX,
              complete_portfolios: 0,
              m4plus_hit_count: SAFE_MAX,
            },
          ],
        }),
      )

      const result = await listHistoricalRunStrategies('run-1', 10)
      expect(result.run_id).toBe('run-1')
      expect(result.items[0]?.evaluated_draws).toBe(SAFE_MAX)
      expect(result.items[0]?.m4plus_hit_count).toBe(SAFE_MAX)
    })

    it('preserves empty strategy items list without error', async () => {
      fetchMock.mockResolvedValue(
        jsonResponse({
          run_id: 'run-1',
          ticket_count: 10,
          items: [],
        }),
      )

      const result = await listHistoricalRunStrategies('run-1', 10)
      expect(result.run_id).toBe('run-1')
      expect(result.items).toEqual([])
    })

    it.each([
      ['ticket_count', UNSAFE_INTEGER],
      ['ticket_count', -1],
      ['ticket_count', 1.5],
    ])('rejects non-safe summary top-level count %s = %j', async (field, value) => {
      fetchMock.mockResolvedValue(
        jsonResponse({
          run_id: 'run-1',
          ticket_count: 10,
          items: [],
          [field]: value,
        }),
      )

      await expect(listHistoricalRunStrategies('run-1', 10)).rejects.toSatisfy((err) => {
        expect(err).toBeInstanceOf(HistoricalResultsRequestError)
        expect((err as HistoricalResultsRequestError).status).toBe(502)
        return true
      })
    })

    it.each([
      ['replicate', UNSAFE_INTEGER],
      ['replicate', -1],
      ['replicate', 1.5],
      ['evaluated_draws', UNSAFE_INTEGER],
      ['evaluated_draws', -1],
      ['evaluated_draws', 1.5],
      ['complete_portfolios', UNSAFE_INTEGER],
      ['complete_portfolios', -1],
      ['complete_portfolios', 1.5],
      ['m4plus_hit_count', UNSAFE_INTEGER],
      ['m4plus_hit_count', -1],
      ['m4plus_hit_count', 1.5],
    ])('rejects non-safe strategy item count %s = %j', async (field, value) => {
      fetchMock.mockResolvedValue(
        jsonResponse({
          run_id: 'run-1',
          ticket_count: 10,
          items: [
            {
              ...validStrategySummaryItem,
              [field]: value,
            },
          ],
        }),
      )

      await expect(listHistoricalRunStrategies('run-1', 10)).rejects.toSatisfy((err) => {
        expect(err).toBeInstanceOf(HistoricalResultsRequestError)
        expect((err as HistoricalResultsRequestError).status).toBe(502)
        return true
      })
    })
  })

  describe('listHistoricalRunReplayPortfolios', () => {
    describe('Query parameter validation', () => {
      it('accepts valid offset values: 0 and MAX_SAFE_INTEGER', async () => {
        mockJsonResponse({
          run_id: 'run-1',
          strategy_id: 'strat-1',
          total_count: 0,
          limit: 20,
          offset: 0,
          items: [],
        })

        await expect(
          listHistoricalRunReplayPortfolios('run-1', {
            strategyId: 'strat-1',
            ticketCount: 10,
            offset: 0,
          }),
        ).resolves.toBeDefined()

        await expect(
          listHistoricalRunReplayPortfolios('run-1', {
            strategyId: 'strat-1',
            ticketCount: 10,
            offset: SAFE_MAX,
          }),
        ).resolves.toBeDefined()
        expect(fetchMock).toHaveBeenCalledTimes(2)
      })

      it.each([
        [UNSAFE_INTEGER, 'unsafe integer above MAX_SAFE_INTEGER'],
        [-1, 'negative integer'],
        [1.5, 'floating point number'],
        [NaN, 'NaN'],
        [Infinity, 'Infinity'],
      ])('rejects non-safe query offset %j (%s) before HTTP fetch', async (offset) => {
        await expect(
          listHistoricalRunReplayPortfolios('run-1', {
            strategyId: 'strat-1',
            ticketCount: 10,
            offset,
          }),
        ).rejects.toThrow(/offset/i)
        expect(fetchMock).not.toHaveBeenCalled()
      })
    })

    describe('Response payload counts validation', () => {
      it('accepts safe integer boundary counts (0 and MAX_SAFE_INTEGER)', async () => {
        fetchMock.mockResolvedValue(
          jsonResponse({
            run_id: 'run-1',
            strategy_id: 'strat-1',
            total_count: SAFE_MAX,
            limit: 20,
            offset: 0,
            items: [validReplayPortfolioItem],
          }),
        )

        const result = await listHistoricalRunReplayPortfolios('run-1', {
          strategyId: 'strat-1',
          ticketCount: 10,
        })
        expect(result.run_id).toBe('run-1')
        expect(result.strategy_id).toBe('strat-1')
        expect(result.total_count).toBe(SAFE_MAX)
      })

      it.each([
        ['total_count', UNSAFE_INTEGER],
        ['total_count', -1],
        ['total_count', 1.5],
        ['limit', UNSAFE_INTEGER],
        ['limit', -1],
        ['limit', 1.5],
        ['offset', UNSAFE_INTEGER],
        ['offset', -1],
        ['offset', 1.5],
      ])('rejects non-safe replay page count %s = %j with HistoricalResultsRequestError 502', async (field, value) => {
        fetchMock.mockResolvedValue(
          jsonResponse({
            run_id: 'run-1',
            strategy_id: 'strat-1',
            total_count: 10,
            limit: 20,
            offset: 0,
            items: [],
            [field]: value,
          }),
        )

        await expect(
          listHistoricalRunReplayPortfolios('run-1', {
            strategyId: 'strat-1',
            ticketCount: 10,
          }),
        ).rejects.toSatisfy((err) => {
          expect(err).toBeInstanceOf(HistoricalResultsRequestError)
          expect((err as HistoricalResultsRequestError).status).toBe(502)
          return true
        })
      })

      it('does not synthesize zero success on HTTP error status (404/500)', async () => {
        fetchMock.mockResolvedValue(
          jsonResponse(
            {
              error_code: 'RUN_NOT_FOUND',
              message: 'Run not found',
            },
            404,
          ),
        )

        await expect(
          listHistoricalRunReplayPortfolios('non-existent-run', {
            strategyId: 'strat-1',
            ticketCount: 10,
          }),
        ).rejects.toSatisfy((err) => {
          expect(err).toBeInstanceOf(HistoricalResultsRequestError)
          expect((err as HistoricalResultsRequestError).status).toBe(404)
          expect((err as HistoricalResultsRequestError).errorCode).toBe('RUN_NOT_FOUND')
          return true
        })
      })
    })
  })
})
