import type { components, paths } from './generated/openapi'

export type P638MultiWindowSuccessWindowsResponse =
  paths['/api/v1/p638-historical/current-runs/{run_id}/success-windows']['get']['responses'][200]['content']['application/json']
export type T539MultiWindowSuccessWindowsResponse =
  paths['/api/v1/t539-historical/runs/{run_id}/success-windows']['get']['responses'][200]['content']['application/json']

type MultiWindowSuccessWindowsResponse = components['schemas']['MultiWindowSuccessWindowsResponse']
type MultiWindowRow = components['schemas']['MultiWindowRowView']
type ExactRational = components['schemas']['ExactRationalView']

export type MultiWindowRequestErrorKind =
  | 'NOT_CONFIGURED'
  | 'NOT_FOUND'
  | 'INVALID_REQUEST'
  | 'UNAVAILABLE'
  | 'MALFORMED_RESPONSE'

export class MultiWindowSuccessWindowsRequestError extends Error {
  readonly kind: MultiWindowRequestErrorKind
  readonly status: number
  readonly errorCode: string | null

  constructor(
    kind: MultiWindowRequestErrorKind,
    message: string,
    status = 0,
    errorCode: string | null = null,
  ) {
    super(message)
    this.name = 'MultiWindowSuccessWindowsRequestError'
    this.kind = kind
    this.status = status
    this.errorCode = errorCode
  }
}

const P638_ENDPOINT = '/api/v1/p638-historical/current-runs'
const T539_ENDPOINT = '/api/v1/t539-historical/runs'

export function getP638MultiWindowSuccessWindows(
  runId: string,
  signal?: AbortSignal,
): Promise<P638MultiWindowSuccessWindowsResponse> {
  return requestMultiWindow<P638MultiWindowSuccessWindowsResponse>(
    `${P638_ENDPOINT}/${encodeURIComponent(runId)}/success-windows`,
    runId,
    'POWER_LOTTO',
    signal,
  )
}

export function getT539MultiWindowSuccessWindows(
  runId: string,
  signal?: AbortSignal,
): Promise<T539MultiWindowSuccessWindowsResponse> {
  return requestMultiWindow<T539MultiWindowSuccessWindowsResponse>(
    `${T539_ENDPOINT}/${encodeURIComponent(runId)}/success-windows`,
    runId,
    'DAILY_539',
    signal,
  )
}

async function requestMultiWindow<T extends MultiWindowSuccessWindowsResponse>(
  endpoint: string,
  runId: string,
  lotteryType: string,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(endpoint, { method: 'GET', signal })
  } catch (error: unknown) {
    if (isAbort(error)) throw error
    throw new MultiWindowSuccessWindowsRequestError(
      'UNAVAILABLE',
      'Multi-window success windows could not load.',
    )
  }

  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) throw requestError(response.status, payload)
  if (!isMultiWindowResponse(payload, runId, lotteryType)) throw malformedResponse()
  return payload as T
}

function requestError(status: number, payload: unknown): MultiWindowSuccessWindowsRequestError {
  const errorCode = isRecord(payload) && typeof payload.error_code === 'string' ? payload.error_code : null
  const message =
    isRecord(payload) && typeof payload.message === 'string'
      ? payload.message
      : `Multi-window success windows request failed (HTTP ${status}).`

  if (status === 404) {
    return new MultiWindowSuccessWindowsRequestError('NOT_FOUND', message, status, errorCode)
  }
  if (status === 422) {
    return new MultiWindowSuccessWindowsRequestError('INVALID_REQUEST', message, status, errorCode)
  }
  if (status === 503 && errorCode?.includes('NOT_CONFIGURED')) {
    return new MultiWindowSuccessWindowsRequestError('NOT_CONFIGURED', message, status, errorCode)
  }
  return new MultiWindowSuccessWindowsRequestError('UNAVAILABLE', message, status, errorCode)
}

function malformedResponse(): MultiWindowSuccessWindowsRequestError {
  return new MultiWindowSuccessWindowsRequestError(
    'MALFORMED_RESPONSE',
    'Multi-window success windows returned an unexpected response.',
  )
}

function isMultiWindowResponse(
  value: unknown,
  runId: string,
  lotteryType: string,
): value is MultiWindowSuccessWindowsResponse {
  return (
    isRecord(value) &&
    value.run_id === runId &&
    value.lottery_type === lotteryType &&
    typeof value.schema_version === 'string' &&
    typeof value.status === 'string' &&
    typeof value.evidence_status === 'string' &&
    Array.isArray(value.rows) &&
    value.rows.every((row: unknown) => isMultiWindowRow(row, runId, lotteryType))
  )
}

function isMultiWindowRow(value: unknown, runId: string, lotteryType: string): value is MultiWindowRow {
  return (
    isRecord(value) &&
    value.run_id === runId &&
    value.lottery_type === lotteryType &&
    typeof value.strategy_id === 'string' &&
    typeof value.strategy_version === 'string' &&
    isNonNegativeInteger(value.native_ticket_count) &&
    typeof value.window_kind === 'string' &&
    typeof value.window_role === 'string' &&
    typeof value.status === 'string' &&
    isNonNegativeInteger(value.observed_winning_target_count) &&
    (value.observed_winning_target_rate === null || isExactRational(value.observed_winning_target_rate)) &&
    isNonNegativeInteger(value.actual_target_count) &&
    isNonNegativeInteger(value.observed_ticket_count) &&
    isNonNegativeInteger(value.observed_winning_ticket_count) &&
    (value.observed_ticket_winning_rate === null || isExactRational(value.observed_ticket_winning_rate)) &&
    isExactRational(value.null_single_ticket_probability) &&
    isExactRational(value.null_portfolio_probability) &&
    (value.by_adjusted_p_value === null || isExactRational(value.by_adjusted_p_value)) &&
    typeof value.evidence_status === 'string'
  )
}

function isExactRational(value: unknown): value is ExactRational {
  return (
    isRecord(value) &&
    typeof value.numerator === 'string' &&
    /^-?(?:0|[1-9][0-9]*)$/.test(value.numerator) &&
    typeof value.denominator === 'string' &&
    /^[1-9][0-9]*$/.test(value.denominator) &&
    typeof value.decimal_18 === 'string'
  )
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}
