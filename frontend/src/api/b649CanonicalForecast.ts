import type { paths } from './generated/openapi'

export type B649CanonicalForecast =
  paths['/api/b649/canonical-forecast/current']['get']['responses'][200]['content']['application/json']

type B649CanonicalForecastTicket = B649CanonicalForecast['k5_tickets'][number]

const CURRENT_FORECAST_ENDPOINT = '/api/b649/canonical-forecast/current'
const SHA256_PATTERN = /^[0-9a-f]{64}$/

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
    if (error instanceof Error && error.name === 'AbortError') throw error
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
  } catch {
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
    isIntegerArray(value.consensus_numbers) &&
    isNonNegativeInteger(value.source_stream_count) &&
    isTicketArray(value.k5_tickets, 5) &&
    isTicketArray(value.k10_tickets, 10) &&
    isTicketArray(value.k20_tickets, 20) &&
    isSha256(value.forecast_actual_sha256) &&
    isNonEmptyString(value.forecast_method_id) &&
    isNonEmptyString(value.forecast_method_version) &&
    isSha256(value.portfolio_actual_sha256) &&
    isNonEmptyString(value.portfolio_method_id) &&
    isNonEmptyString(value.portfolio_method_version)
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
      (ticket) =>
        isRecord(ticket) &&
        isPositiveInteger(ticket.ticket_position) &&
        isIntegerArray(ticket.predicted_numbers),
    )
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function isIntegerArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every(Number.isInteger)
}

function isPositiveInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) > 0
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 0
}

function isSha256(value: unknown): value is string {
  return typeof value === 'string' && SHA256_PATTERN.test(value)
}
