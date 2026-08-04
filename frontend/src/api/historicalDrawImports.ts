import type { components, paths } from './generated/openapi'

export type HistoricalDrawImportRequest = components['schemas']['HistoricalImportRequest']
export type HistoricalDrawImportFileRequest = components['schemas']['HistoricalImportFileRequest']
export type HistoricalDrawImportResponse =
  paths['/api/v1/historical-results/imports/preview']['post']['responses'][200]['content']['application/json']
export type HistoricalDrawImportFilter = components['schemas']['HistoricalImportFilter']

export class HistoricalDrawImportsRequestError extends Error {
  readonly status: number
  readonly errorCode: string | undefined

  constructor(message: string, status: number, errorCode?: string) {
    super(message)
    this.name = 'HistoricalDrawImportsRequestError'
    this.status = status
    this.errorCode = errorCode
  }
}

export async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  const chunkSize = 0x8000
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize))
  }
  return btoa(binary)
}

export async function previewHistoricalDrawImport(
  request: HistoricalDrawImportRequest,
  signal?: AbortSignal,
): Promise<HistoricalDrawImportResponse> {
  return submitHistoricalDrawImport(
    '/api/v1/historical-results/imports/preview',
    request,
    signal,
  )
}

export async function commitHistoricalDrawImport(
  request: HistoricalDrawImportRequest,
  signal?: AbortSignal,
): Promise<HistoricalDrawImportResponse> {
  return submitHistoricalDrawImport('/api/v1/historical-results/imports', request, signal)
}

export async function getHistoricalDrawImport(
  runId: string,
  signal?: AbortSignal,
): Promise<HistoricalDrawImportResponse> {
  const response = await fetch(
    `/api/v1/historical-results/imports/${encodeURIComponent(runId)}`,
    { method: 'GET', headers: { Accept: 'application/json' }, signal },
  )
  const payload = await responseJson(response)
  if (!response.ok) throw requestError('Historical draw import', response.status, payload)
  if (!isHistoricalDrawImportResponse(payload)) {
    throw new HistoricalDrawImportsRequestError(
      'Historical draw import returned an invalid response contract',
      502,
    )
  }
  return payload
}

async function submitHistoricalDrawImport(
  path: string,
  request: HistoricalDrawImportRequest,
  signal?: AbortSignal,
): Promise<HistoricalDrawImportResponse> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })
  const payload = await responseJson(response)
  if (!response.ok) throw requestError('Historical draw import', response.status, payload)
  if (!isHistoricalDrawImportResponse(payload)) {
    throw new HistoricalDrawImportsRequestError(
      'Historical draw import returned an invalid response contract',
      502,
    )
  }
  return payload
}

async function responseJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    throw new HistoricalDrawImportsRequestError(
      'Historical draw import returned an invalid response',
      response.status || 502,
    )
  }
}

function requestError(label: string, status: number, payload: unknown): HistoricalDrawImportsRequestError {
  const record = isRecord(payload) ? payload : {}
  return new HistoricalDrawImportsRequestError(
    typeof record.message === 'string' ? record.message : `${label} request failed with HTTP ${status}`,
    status,
    typeof record.error_code === 'string' ? record.error_code : undefined,
  )
}

function isHistoricalDrawImportResponse(value: unknown): value is HistoricalDrawImportResponse {
  if (!isRecord(value) || !Array.isArray(value.files) || !Array.isArray(value.chunks)) return false
  if (!Array.isArray(value.row_results) || !isRecord(value.summary)) return false
  return (
    (value.run_id === null || typeof value.run_id === 'string') &&
    ['PREVIEW', 'COMPLETED', 'PARTIAL_SUCCESS', 'FAILED'].includes(String(value.status)) &&
    ['ALL', 'DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO'].includes(String(value.lottery_filter)) &&
    isInteger(value.summary.imported_rows) &&
    value.files.every(isHistoricalImportFile) &&
    value.chunks.every(isHistoricalImportChunk)
  )
}

function isHistoricalImportFile(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.filename === 'string' &&
    typeof value.source_sha256 === 'string' &&
    ['ACCEPTED', 'PARTIAL_SUCCESS', 'EXCLUDED', 'FAILED'].includes(String(value.status)) &&
    isInteger(value.imported_rows) &&
    isInteger(value.failed_rows) &&
    Array.isArray(value.rows)
  )
}

function isHistoricalImportChunk(value: unknown): boolean {
  return (
    isRecord(value) &&
    isInteger(value.chunk_index) &&
    isInteger(value.candidate_rows) &&
    isInteger(value.imported_rows) &&
    isInteger(value.failed_rows) &&
    ['COMMITTED', 'FAILED'].includes(String(value.status)) &&
    Array.isArray(value.historical_run_ids)
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value)
}
