import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { listHistoricalImportRuns } from '../src/api/historicalImports'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function response(): Response {
  return new Response(
    JSON.stringify({
      items: [],
      total_count: 0,
      limit: 50,
      offset: 0,
    }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  )
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('historical imports API client', () => {
  it.each(['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO'] as const)(
    'sends the internal %s lottery value with bounded pagination and AbortSignal',
    async (lotteryType) => {
      fetchMock.mockResolvedValue(response())
      const controller = new AbortController()

      await listHistoricalImportRuns(controller.signal, {
        lotteryType,
        limit: 25,
        offset: 5,
      })

      const [input, init] = fetchMock.mock.calls[0] ?? []
      const url = new URL(String(input), 'http://localhost')
      expect(Object.fromEntries(url.searchParams)).toEqual({
        limit: '25',
        offset: '5',
        lottery_type: lotteryType,
      })
      expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
      expect(String(input)).not.toMatch(/T539|L649|P638/)
    },
  )

  it('omits the lottery filter while retaining compatible defaults', async () => {
    fetchMock.mockResolvedValue(response())
    await listHistoricalImportRuns()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/historical-results/runs?limit=50&offset=0',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it.each([
    [{ limit: 0 }, 'limit'],
    [{ limit: 201 }, 'limit'],
    [{ offset: -1 }, 'offset'],
  ])('rejects invalid client pagination %j', async (options, message) => {
    await expect(listHistoricalImportRuns(undefined, options)).rejects.toThrow(message)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
