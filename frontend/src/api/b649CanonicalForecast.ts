import type { paths } from './generated/openapi'

export type B649CanonicalForecast =
  paths['/api/b649/canonical-forecast/current']['get']['responses'][200]['content']['application/json']

type B649CanonicalForecastTicket = B649CanonicalForecast['k5_tickets'][number]

const CURRENT_FORECAST_ENDPOINT = '/api/b649/canonical-forecast/current'
const SHA256_PATTERN = /^[0-9a-f]{64}$/
const OFFICIAL_NUMBER_MIN = 1
const OFFICIAL_NUMBER_MAX = 49
const EXPECTED_TICKET_SIZE = 6
const EXPECTED_STREAM_COUNT = 11
const FORECAST_METHOD_ID = 'B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS'
const FORECAST_METHOD_VERSION = '1.0.0'
const PORTFOLIO_METHOD_ID = 'B649_SEALED_GEOMETRY_PORTFOLIO'
const PORTFOLIO_METHOD_VERSION = '8.0.0'

export type B649CanonicalForecastErrorKind =
  | 'HTTP'
  | 'NETWORK'
  | 'MALFORMED_RESPONSE'

export class B649CanonicalForecastRequestError extends Error {
  readonly status: number
  readonly kind: B649CanonicalForecastErrorKind

  constructor(
    message: string,
    status: number,
    kind: B649CanonicalForecastErrorKind,
  ) {
    super(message)
    this.name = 'B649CanonicalForecastRequestError'
    this.status = status
    this.kind = kind
  }
}

export async function fetchB649CanonicalForecast(
  signal?: AbortSignal,
): Promise<B649CanonicalForecast> {
  let response: Response
  try {
    response = await fetch(CURRENT_FORECAST_ENDPOINT, { signal })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new B649CanonicalForecastRequestError('Network request failed.', 0, 'NETWORK')
  }

  if (response.status !== 200) {
    throw new B649CanonicalForecastRequestError(
      'The current scheduler forecast is unavailable.',
      response.status,
      'HTTP',
    )
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new B649CanonicalForecastRequestError(
      'The server returned invalid JSON.',
      response.status,
      'MALFORMED_RESPONSE',
    )
  }

  if (!isCurrentForecast(payload)) {
    throw new B649CanonicalForecastRequestError(
      'The server response did not match the current forecast contract.',
      response.status,
      'MALFORMED_RESPONSE',
    )
  }

  return payload
}

function isCurrentForecast(value: unknown): value is B649CanonicalForecast {
  if (!isRecord(value) || !isRecord(value.current_target)) return false
  const target = value.current_target

  return (
    value.status === 'AVAILABLE' &&
    value.authority === 'SCHEDULER_ARTIFACT' &&
    isNonEmptyString(target.draw_number) &&
    isNonEmptyString(target.draw_date) &&
    isNonEmptyString(target.scheduled_at) &&
    isOfficialNumberArray(value.consensus_numbers) &&
    value.source_stream_count === EXPECTED_STREAM_COUNT &&
    isTicketArray(value.k5_tickets, 5) &&
    isTicketArray(value.k10_tickets, 10) &&
    isTicketArray(value.k20_tickets, 20) &&
    isSha256(value.forecast_actual_sha256) &&
    value.forecast_method_id === FORECAST_METHOD_ID &&
    value.forecast_method_version === FORECAST_METHOD_VERSION &&
    isSha256(value.portfolio_actual_sha256) &&
    value.portfolio_method_id === PORTFOLIO_METHOD_ID &&
    value.portfolio_method_version === PORTFOLIO_METHOD_VERSION
  )
}

function isTicketArray(
  value: unknown,
  expectedLength: number,
): value is B649CanonicalForecastTicket[] {
  return (
    Array.isArray(value) &&
    value.length === expectedLength &&
    value.every(
      (ticket, index) =>
        isRecord(ticket) &&
        ticket.ticket_position === index + 1 &&
        isOfficialNumberArray(ticket.predicted_numbers),
    )
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function isOfficialNumberArray(value: unknown): value is number[] {
  return (
    Array.isArray(value) &&
    value.length === EXPECTED_TICKET_SIZE &&
    value.every(isOfficialNumber) &&
    new Set(value).size === EXPECTED_TICKET_SIZE
  )
}

function isOfficialNumber(value: unknown): value is number {
  return (
    Number.isSafeInteger(value) &&
    Number(value) >= OFFICIAL_NUMBER_MIN &&
    Number(value) <= OFFICIAL_NUMBER_MAX
  )
}

function isAbortError(value: unknown): boolean {
  return isRecord(value) && value.name === 'AbortError'
}

function isSha256(value: unknown): value is string {
  return typeof value === 'string' && SHA256_PATTERN.test(value)
}
