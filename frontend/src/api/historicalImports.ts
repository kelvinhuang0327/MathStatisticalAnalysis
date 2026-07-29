import type { paths } from './generated/openapi'

export type HistoricalImportRunPage =
  paths['/api/v1/historical-results/runs']['get']['responses'][200]['content']['application/json']

export class HistoricalImportsRequestError extends Error {
  readonly status: number
  readonly errorCode: string | undefined

  constructor(message: string, status: number, errorCode?: string) {
    super(message)
    this.name = 'HistoricalImportsRequestError'
    this.status = status
    this.errorCode = errorCode
  }
}

export async function listHistoricalImportRuns(
  signal?: AbortSignal,
): Promise<HistoricalImportRunPage> {
  const response = await fetch('/api/v1/historical-results/runs?limit=50&offset=0', {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  const payload: unknown = await response.json()
  if (!response.ok) {
    const error = isRecord(payload) ? payload : {}
    throw new HistoricalImportsRequestError(
      typeof error.message === 'string'
        ? error.message
        : `Historical imports request failed with HTTP ${response.status}`,
      response.status,
      typeof error.error_code === 'string' ? error.error_code : undefined,
    )
  }
  if (!isHistoricalImportRunPage(payload)) {
    throw new HistoricalImportsRequestError(
      'Historical imports returned an invalid response contract',
      502,
    )
  }
  return payload
}

function isHistoricalImportRunPage(value: unknown): value is HistoricalImportRunPage {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(
      (item) =>
        isRecord(item) &&
        typeof item.run_id === 'string' &&
        typeof item.import_identity_sha256 === 'string' &&
        typeof item.source_kind === 'string' &&
        item.status === 'COMPLETED' &&
        isNonNegativeInteger(item.strategy_count) &&
        isNonNegativeInteger(item.draw_count) &&
        isNonNegativeInteger(item.portfolio_count) &&
        typeof item.started_at === 'string' &&
        typeof item.completed_at === 'string' &&
        typeof item.is_idempotent_replay === 'boolean',
    ) &&
    isNonNegativeInteger(value.total_count) &&
    isNonNegativeInteger(value.limit) &&
    isNonNegativeInteger(value.offset)
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}
