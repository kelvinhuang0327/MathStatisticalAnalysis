import type { components, paths } from './generated/openapi'

export type DrawImportPreviewRequest = components['schemas']['DrawImportPreviewRequest']
export type DrawImportCommitRequest = components['schemas']['DrawImportCommitRequest']
export type BatchImportFileRequest = components['schemas']['BatchImportFileRequest']
export type BatchImportPreviewRequest = components['schemas']['BatchImportPreviewRequest']
export type BatchImportCommitRequest = components['schemas']['BatchImportCommitRequest']
export type DrawImportPreview =
  paths['/api/v1/draw-imports/preview']['post']['responses'][200]['content']['application/json']
export type ImportCommitResult =
  paths['/api/v1/draw-imports/commit']['post']['responses'][200]['content']['application/json']
export type BatchImportPreview =
  paths['/api/v1/draw-imports/batch/preview']['post']['responses'][200]['content']['application/json']
export type BatchImportCommit =
  paths['/api/v1/draw-imports/batch/commit']['post']['responses'][200]['content']['application/json']
export type DrawHistoryResponse =
  paths['/api/v1/draws']['get']['responses'][200]['content']['application/json']
export type DrawRecord = DrawHistoryResponse['records'][number]
export type IngestionRunPage =
  paths['/api/v1/ingestion-runs']['get']['responses'][200]['content']['application/json']
export type IngestionRun = IngestionRunPage['records'][number]
export type IngestionRunDetail =
  paths['/api/v1/ingestion-runs/{run_id}']['get']['responses'][200]['content']['application/json']
export type DrawSyncRequest = components['schemas']['DrawSyncRequestView']
export type DrawSyncResponse =
  paths['/api/v1/draw-sync/manual']['post']['responses'][200]['content']['application/json']
export type DrawSyncOperation = 'manual' | 'missing-scan' | 'backfill' | 'scheduled'

export interface PreviewOutcome {
  ok: boolean
  status: number
  errorCode?: string
  message?: string
  preview: DrawImportPreview | null
}

export interface CommitOutcome {
  ok: boolean
  status: number
  errorCode?: string
  message?: string
  result: ImportCommitResult | null
  preview: DrawImportPreview | null
}

export interface BatchPreviewOutcome {
  ok: boolean
  status: number
  errorCode?: string
  message?: string
  preview: BatchImportPreview | null
}

export interface BatchCommitOutcome {
  ok: boolean
  status: number
  errorCode?: string
  message?: string
  result: BatchImportCommit | null
  preview: BatchImportPreview | null
}

export interface DrawHistoryQuery {
  lotteryType: 'BIG_LOTTO'
  drawNumber: string
  dateFrom: string
  dateTo: string
  page: number
  pageSize: number
}

export interface IngestionRunQuery {
  status?: 'RUNNING' | 'SUCCESS' | 'FAILED'
  operationType?: IngestionRun['operation_type']
  source?: string
  dateFrom?: string
  dateTo?: string
  page?: number
  pageSize?: number
}

export class DrawDataRequestError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'DrawDataRequestError'
    this.status = status
  }
}

export async function previewDrawImport(
  request: DrawImportPreviewRequest,
  signal?: AbortSignal,
): Promise<PreviewOutcome> {
  const response = await fetch('/api/v1/draw-imports/preview', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(request),
    signal,
  })
  const payload = await responseJson(response)
  if (response.status === 200 && isPreview(payload)) {
    return { ok: true, status: response.status, preview: payload }
  }
  if (response.status === 422 && isErrorRecord(payload)) {
    const preview = isPreview(payload.preview) ? payload.preview : null
    return {
      ok: false,
      status: response.status,
      errorCode: payload.error_code,
      message: payload.message,
      preview,
    }
  }
  throw malformedResponse('CSV preview', response.status)
}

export async function commitDrawImport(
  request: DrawImportCommitRequest,
  signal?: AbortSignal,
): Promise<CommitOutcome> {
  const response = await fetch('/api/v1/draw-imports/commit', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(request),
    signal,
  })
  const payload = await responseJson(response)
  if (response.status === 200 && isCommitResult(payload)) {
    return { ok: true, status: response.status, result: payload, preview: null }
  }
  if ((response.status === 409 || response.status === 422) && isErrorRecord(payload)) {
    return {
      ok: false,
      status: response.status,
      errorCode: payload.error_code,
      message: payload.message,
      result: isCommitResult(payload.result) ? payload.result : null,
      preview: isPreview(payload.preview) ? payload.preview : null,
    }
  }
  if (response.status === 503 && isErrorRecord(payload)) {
    throw new DrawDataRequestError(payload.message, response.status)
  }
  throw malformedResponse('CSV commit', response.status)
}

export async function previewBatchDrawImport(
  request: BatchImportPreviewRequest,
  signal?: AbortSignal,
): Promise<BatchPreviewOutcome> {
  const response = await fetch('/api/v1/draw-imports/batch/preview', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(request),
    signal,
  })
  const payload = await responseJson(response)
  if (response.status === 200 && isBatchPreview(payload)) {
    return { ok: true, status: response.status, preview: payload }
  }
  if (response.status === 422 && isErrorRecord(payload)) {
    return {
      ok: false,
      status: response.status,
      errorCode: payload.error_code,
      message: payload.message,
      preview: isBatchPreview(payload.preview) ? payload.preview : null,
    }
  }
  throw malformedResponse('Batch preview', response.status)
}

export async function commitBatchDrawImport(
  request: BatchImportCommitRequest,
  signal?: AbortSignal,
): Promise<BatchCommitOutcome> {
  const response = await fetch('/api/v1/draw-imports/batch/commit', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(request),
    signal,
  })
  const payload = await responseJson(response)
  if (response.status === 200 && isBatchCommit(payload)) {
    const ok = payload.status === 'SUCCESS'
    return {
      ok,
      status: response.status,
      result: payload,
      preview: null,
      message: ok ? undefined : (payload.error_summary ?? 'Batch import was not committed.'),
    }
  }
  if ((response.status === 409 || response.status === 422) && isErrorRecord(payload)) {
    return {
      ok: false,
      status: response.status,
      errorCode: payload.error_code,
      message: payload.message,
      result: null,
      preview: isBatchPreview(payload.preview) ? payload.preview : null,
    }
  }
  if (response.status === 503 && isErrorRecord(payload)) {
    throw new DrawDataRequestError(payload.message, response.status)
  }
  throw malformedResponse('Batch commit', response.status)
}

export async function runDrawSync(
  operation: DrawSyncOperation,
  request: DrawSyncRequest,
  signal?: AbortSignal,
): Promise<DrawSyncResponse> {
  const response = await fetch(`/api/v1/draw-sync/${operation}`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(request),
    signal,
  })
  const payload = await responseJson(response)
  if (!response.ok) throw responseError('Draw automation', response.status, payload)
  if (!isDrawSyncResponse(payload)) throw malformedResponse('Draw automation', response.status)
  return payload
}

export async function listIngestionRuns(
  query: IngestionRunQuery = {},
  signal?: AbortSignal,
): Promise<IngestionRunPage> {
  const parameters = new URLSearchParams({
    lottery_type: 'BIG_LOTTO',
    page: String(query.page ?? 1),
    page_size: String(query.pageSize ?? 25),
  })
  if (query.status) parameters.set('status', query.status)
  if (query.operationType) parameters.set('operation_type', query.operationType)
  if (query.source) parameters.set('source', query.source)
  if (query.dateFrom) parameters.set('date_from', query.dateFrom)
  if (query.dateTo) parameters.set('date_to', query.dateTo)
  const response = await fetch(`/api/v1/ingestion-runs?${parameters.toString()}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  const payload = await responseJson(response)
  if (!response.ok) throw responseError('Ingestion runs', response.status, payload)
  if (!isIngestionRunPage(payload)) throw malformedResponse('Ingestion runs', response.status)
  return payload
}

export async function getIngestionRun(
  runId: string,
  signal?: AbortSignal,
): Promise<IngestionRunDetail> {
  const response = await fetch(`/api/v1/ingestion-runs/${encodeURIComponent(runId)}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  const payload = await responseJson(response)
  if (!response.ok) throw responseError('Ingestion run detail', response.status, payload)
  if (!isIngestionRunDetail(payload)) {
    throw malformedResponse('Ingestion run detail', response.status)
  }
  return payload
}

export async function listDraws(
  query: DrawHistoryQuery,
  signal?: AbortSignal,
): Promise<DrawHistoryResponse> {
  const parameters = new URLSearchParams({
    lottery_type: query.lotteryType,
    page: String(query.page),
    page_size: String(query.pageSize),
  })
  if (query.drawNumber) parameters.set('draw_number', query.drawNumber)
  if (query.dateFrom) parameters.set('date_from', query.dateFrom)
  if (query.dateTo) parameters.set('date_to', query.dateTo)

  const response = await fetch(`/api/v1/draws?${parameters.toString()}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  const payload = await responseJson(response)
  if (!response.ok) throw responseError('Draw History', response.status, payload)
  if (!isDrawHistory(payload)) throw malformedResponse('Draw History', response.status)
  return payload
}

function jsonHeaders(): Record<string, string> {
  return { Accept: 'application/json', 'Content-Type': 'application/json' }
}

async function responseJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    throw malformedResponse('API', response.status)
  }
}

function malformedResponse(label: string, status: number): DrawDataRequestError {
  return new DrawDataRequestError(`${label} returned an invalid response`, status || 502)
}

function responseError(label: string, status: number, payload: unknown): DrawDataRequestError {
  const message = isErrorRecord(payload)
    ? payload.message
    : `${label} request failed with HTTP ${status}`
  return new DrawDataRequestError(message, status)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function isOptionalString(value: unknown): value is string | null {
  return value === null || isString(value)
}

function isInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString)
}

function isNumberArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every(isInteger)
}

function isLotteryType(value: unknown): value is 'DAILY_539' | 'BIG_LOTTO' | 'POWER_LOTTO' {
  return value === 'DAILY_539' || value === 'BIG_LOTTO' || value === 'POWER_LOTTO'
}

function isErrorRecord(value: unknown): value is Record<string, unknown> & {
  error_code: string
  message: string
} {
  return isRecord(value) && isString(value.error_code) && isString(value.message)
}

function isPreviewRow(value: unknown): boolean {
  return (
    isRecord(value) &&
    isInteger(value.source_row_number) &&
    isLotteryType(value.lottery_type) &&
    isString(value.draw_number) &&
    isString(value.draw_date) &&
    isNumberArray(value.main_numbers) &&
    isNumberArray(value.special_numbers) &&
    isOptionalString(value.source_reference) &&
    isString(value.normalized_record_hash)
  )
}

function isPreviewError(value: unknown): boolean {
  return (
    isRecord(value) &&
    isString(value.code) &&
    isString(value.message) &&
    (value.row_number === null || isInteger(value.row_number)) &&
    isOptionalString(value.field)
  )
}

function isPreview(value: unknown): value is DrawImportPreview {
  return (
    isRecord(value) &&
    isString(value.filename) &&
    typeof value.is_valid === 'boolean' &&
    isString(value.content_sha256) &&
    isString(value.parser_version) &&
    Array.isArray(value.supported_lottery_types) &&
    value.supported_lottery_types.every(isLotteryType) &&
    isInteger(value.total_rows) &&
    isInteger(value.valid_rows) &&
    isInteger(value.blank_rows) &&
    isInteger(value.duplicate_rows) &&
    isInteger(value.conflict_rows_inside_input) &&
    isInteger(value.validation_error_count) &&
    isStringArray(value.ignored_columns) &&
    Array.isArray(value.normalized_preview) &&
    value.normalized_preview.every(isPreviewRow) &&
    Array.isArray(value.validation_errors) &&
    value.validation_errors.every(isPreviewError) &&
    typeof value.preview_truncated === 'boolean' &&
    typeof value.errors_truncated === 'boolean'
  )
}

function isBatchImportIssue(value: unknown): boolean {
  return (
    isRecord(value) &&
    isString(value.code) &&
    isString(value.message) &&
    (value.row_number === null || isInteger(value.row_number)) &&
    (value.member_name === null || isString(value.member_name))
  )
}

function isBatchImportFile(value: unknown): boolean {
  return (
    isRecord(value) &&
    isString(value.source_filename) &&
    isString(value.source_locator) &&
    isString(value.source_sha256) &&
    isString(value.status) &&
    (value.lottery_type === null || isLotteryType(value.lottery_type)) &&
    isInteger(value.discovered_rows) &&
    isInteger(value.accepted_rows) &&
    isInteger(value.excluded_rows) &&
    isInteger(value.duplicate_rows) &&
    isInteger(value.conflict_rows) &&
    isInteger(value.failed_rows) &&
    Array.isArray(value.issues) &&
    value.issues.every(isBatchImportIssue)
  )
}

function isBatchImportSummary(value: unknown): boolean {
  return (
    isRecord(value) &&
    isInteger(value.discovered_files) &&
    isInteger(value.accepted_files) &&
    isInteger(value.excluded_files) &&
    isInteger(value.parsed_rows) &&
    isInteger(value.accepted_rows) &&
    isInteger(value.excluded_rows) &&
    isInteger(value.duplicate_rows) &&
    isInteger(value.conflict_rows) &&
    isInteger(value.imported_rows) &&
    isInteger(value.failed_rows)
  )
}

function isBatchPreview(value: unknown): value is BatchImportPreview {
  return (
    isRecord(value) &&
    isString(value.source_filename) &&
    typeof value.is_valid === 'boolean' &&
    isString(value.manifest_sha256) &&
    isString(value.parser_version) &&
    Array.isArray(value.files) &&
    value.files.every(isBatchImportFile) &&
    isBatchImportSummary(value.summary) &&
    Array.isArray(value.normalized_preview) &&
    value.normalized_preview.every(isPreviewRow) &&
    typeof value.preview_truncated === 'boolean'
  )
}

function isBatchCommit(value: unknown): value is BatchImportCommit {
  return (
    isRecord(value) &&
    isOptionalString(value.run_id) &&
    isString(value.status) &&
    isString(value.manifest_sha256) &&
    isBatchImportSummary(value.summary) &&
    Array.isArray(value.files) &&
    value.files.every(isBatchImportFile) &&
    isString(value.completed_at) &&
    isOptionalString(value.error_summary)
  )
}

function isCommitResult(value: unknown): value is ImportCommitResult {
  return (
    isRecord(value) &&
    isOptionalString(value.run_id) &&
    (value.status === 'SUCCESS' || value.status === 'FAILED') &&
    (value.lottery_type === null || isLotteryType(value.lottery_type)) &&
    isInteger(value.total_count) &&
    isInteger(value.inserted_count) &&
    isInteger(value.skipped_count) &&
    isInteger(value.conflict_count) &&
    isInteger(value.failed_count) &&
    isOptionalString(value.first_draw_number) &&
    isOptionalString(value.last_draw_number) &&
    isString(value.completed_at)
  )
}

function isDrawRecord(value: unknown): boolean {
  return (
    isRecord(value) &&
    isLotteryType(value.lottery_type) &&
    isString(value.draw_number) &&
    isString(value.draw_date) &&
    isNumberArray(value.main_numbers) &&
    isNumberArray(value.special_numbers) &&
    isOptionalString(value.source_name) &&
    isOptionalString(value.source_reference) &&
    isString(value.ingestion_run_id) &&
    isString(value.created_at) &&
    isString(value.updated_at)
  )
}

function isDrawHistory(value: unknown): value is DrawHistoryResponse {
  return (
    isRecord(value) &&
    Array.isArray(value.records) &&
    value.records.every(isDrawRecord) &&
    isInteger(value.page) &&
    isInteger(value.page_size) &&
    isInteger(value.total_count) &&
    isInteger(value.total_pages) &&
    isStringArray(value.sort)
  )
}

function isIngestionRun(value: unknown): boolean {
  const operationTypes = [
    'DRAW_CSV_IMPORT',
    'MANUAL_SYNC',
    'MISSING_DRAW_SCAN',
    'BOUNDED_BACKFILL',
    'SCHEDULED_SYNC',
  ]
  return (
    isRecord(value) &&
    isString(value.run_id) &&
    operationTypes.includes(String(value.operation_type)) &&
    ['RUNNING', 'SUCCESS', 'FAILED'].includes(String(value.status)) &&
    (value.lottery_type === null || isLotteryType(value.lottery_type)) &&
    isString(value.source_filename) &&
    isString(value.source_sha256) &&
    isString(value.parser_version) &&
    value.trigger === value.operation_type &&
    isOptionalString(value.provider) &&
    isOptionalString(value.provider_version) &&
    isOptionalString(value.requested_start) &&
    isOptionalString(value.requested_end) &&
    isOptionalString(value.resolved_start) &&
    isOptionalString(value.resolved_end) &&
    isInteger(value.fetched_count) &&
    isInteger(value.total_count) &&
    isInteger(value.inserted_count) &&
    isInteger(value.skipped_count) &&
    isInteger(value.conflict_count) &&
    isInteger(value.failed_count) &&
    isOptionalString(value.first_draw_number) &&
    isOptionalString(value.last_draw_number) &&
    isString(value.started_at) &&
    isOptionalString(value.completed_at) &&
    isOptionalString(value.error_summary)
  )
}

function isIngestionRunPage(value: unknown): value is IngestionRunPage {
  return (
    isRecord(value) &&
    Array.isArray(value.records) &&
    value.records.every(isIngestionRun) &&
    isInteger(value.page) &&
    isInteger(value.page_size) &&
    isInteger(value.total_count) &&
    isInteger(value.total_pages) &&
    isStringArray(value.sort)
  )
}

function isIngestionItem(value: unknown): boolean {
  return (
    isRecord(value) &&
    isInteger(value.source_row_number) &&
    (value.lottery_type === null || value.lottery_type === 'BIG_LOTTO') &&
    isOptionalString(value.draw_number) &&
    isOptionalString(value.source) &&
    ['INSERTED', 'SKIPPED_DUPLICATE', 'CONFLICT', 'FAILED'].includes(
      String(value.disposition),
    ) &&
    isOptionalString(value.normalized_record_hash) &&
    isOptionalString(value.message)
  )
}

function isIngestionRunDetail(value: unknown): value is IngestionRunDetail {
  return (
    isRecord(value) &&
    isIngestionRun(value.run) &&
    Array.isArray(value.items) &&
    value.items.every(isIngestionItem) &&
    isInteger(value.item_count) &&
    typeof value.items_truncated === 'boolean'
  )
}

function isDrawSyncResponse(value: unknown): value is DrawSyncResponse {
  return (
    isRecord(value) &&
    ['MANUAL_SYNC', 'MISSING_DRAW_SCAN', 'BOUNDED_BACKFILL', 'SCHEDULED_SYNC'].includes(
      String(value.operation_type),
    ) &&
    isString(value.provider) &&
    isString(value.requested_start) &&
    isString(value.requested_end) &&
    isOptionalString(value.resolved_start) &&
    isOptionalString(value.resolved_end) &&
    isInteger(value.fetched_count) &&
    isCommitResult(value.result)
  )
}
