import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  commitHistoricalDrawImport,
  previewHistoricalDrawImport,
} from '../src/api/historicalDrawImports'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

const previewPayload = {
  run_id: null,
  status: 'PREVIEW',
  lottery_filter: 'POWER_LOTTO',
  files: [],
  chunks: [],
  summary: { imported_rows: 0 },
  row_results: [],
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('historical draw import API client', () => {
  it('posts one JSON base64 request for preview and preserves the abort signal', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(previewPayload), { status: 200 }),
    )
    const controller = new AbortController()
    const request = {
      files: [{ filename: 'legacy.zip', content_base64: 'UEsDBA==' }],
      lottery_filter: 'POWER_LOTTO' as const,
    }

    await previewHistoricalDrawImport(request, controller.signal)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/historical-results/imports/preview',
      expect.objectContaining({ method: 'POST', signal: controller.signal }),
    )
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual(request)
  })

  it('uses the commit endpoint and surfaces sanitized API errors', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error_code: 'NOT_CONFIGURED', message: 'not configured' }), {
        status: 503,
      }),
    )

    await expect(
      commitHistoricalDrawImport({
        files: [{ filename: 'legacy.csv', content_base64: 'YQ==' }],
      }),
    ).rejects.toMatchObject({ status: 503, errorCode: 'NOT_CONFIGURED' })
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('/api/v1/historical-results/imports')
  })
})
