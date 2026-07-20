import type { components, paths } from './generated/openapi'

export type LiveZoneSplitBetsRequest = components['schemas']['LiveZoneSplitRequest']
export type LiveZoneSplitBetsResponse =
  paths['/api/v1/live-zone-split-bets']['post']['responses'][200]['content']['application/json']

export const MIN_NUM_BETS = 1
export const MAX_NUM_BETS = 10

const LIVE_ZONE_SPLIT_BETS_ENDPOINT = '/api/v1/live-zone-split-bets'
const STATUSES = ['OK', 'INVALID_REQUEST', 'INVALID_OUTPUT', 'EXECUTION_ERROR'] as const
const REASONS = ['INVALID_NUM_BETS', 'MALFORMED_OUTPUT', 'EXECUTION_ERROR'] as const

export type LiveZoneSplitBetsErrorKind =
  | 'invalid_local_input'
  | 'network'
  | 'http_422'
  | 'malformed_response'
  | 'http_error'

export class LiveZoneSplitBetsRequestError extends Error {
  readonly kind: LiveZoneSplitBetsErrorKind
  readonly status: number | null

  constructor(message: string, kind: LiveZoneSplitBetsErrorKind, status: number | null) {
    super(message)
    this.name = 'LiveZoneSplitBetsRequestError'
    this.kind = kind
    this.status = status
  }
}

export function isValidNumBets(numBets: unknown): numBets is number {
  return (
    typeof numBets === 'number' &&
    Number.isInteger(numBets) &&
    numBets >= MIN_NUM_BETS &&
    numBets <= MAX_NUM_BETS
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNumberArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === 'number')
}

function isStatus(value: unknown): value is (typeof STATUSES)[number] {
  return typeof value === 'string' && (STATUSES as readonly string[]).includes(value)
}

function isReasonCode(value: unknown): value is (typeof REASONS)[number] {
  return typeof value === 'string' && (REASONS as readonly string[]).includes(value)
}

function isLiveZoneSplitBetsResponse(value: unknown): value is LiveZoneSplitBetsResponse {
  if (!isRecord(value) || !isStatus(value.status)) return false

  if (value.status === 'OK') {
    return (
      Array.isArray(value.bets) &&
      value.bets.length > 0 &&
      value.bets.every(isNumberArray) &&
      typeof value.coverage_rate === 'number' &&
      typeof value.total_unique_numbers === 'number' &&
      typeof value.method === 'string' &&
      typeof value.philosophy === 'string' &&
      value.reason_code === null
    )
  }

  return (
    value.bets === null &&
    value.coverage_rate === null &&
    value.total_unique_numbers === null &&
    value.method === null &&
    value.philosophy === null &&
    isReasonCode(value.reason_code)
  )
}

export async function generateLiveZoneSplitBets(
  numBets: number,
  signal?: AbortSignal,
): Promise<LiveZoneSplitBetsResponse> {
  if (!isValidNumBets(numBets)) {
    throw new LiveZoneSplitBetsRequestError(
      `num_bets must be an integer from ${MIN_NUM_BETS} through ${MAX_NUM_BETS}`,
      'invalid_local_input',
      null,
    )
  }

  const request: LiveZoneSplitBetsRequest = { num_bets: numBets }
  let response: Response
  try {
    response = await fetch(LIVE_ZONE_SPLIT_BETS_ENDPOINT, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new LiveZoneSplitBetsRequestError(
      'Live Zone Split request failed before a response was received.',
      'network',
      null,
    )
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new LiveZoneSplitBetsRequestError(
      'Live Zone Split returned an unreadable response.',
      'malformed_response',
      response.status,
    )
  }

  if (response.status === 200) {
    if (!isLiveZoneSplitBetsResponse(payload)) {
      throw new LiveZoneSplitBetsRequestError(
        'Live Zone Split returned an invalid response contract.',
        'malformed_response',
        response.status,
      )
    }
    return payload
  }

  if (response.status === 422) {
    throw new LiveZoneSplitBetsRequestError(
      'Live Zone Split rejected the request as invalid.',
      'http_422',
      response.status,
    )
  }

  throw new LiveZoneSplitBetsRequestError(
    `Live Zone Split request failed with HTTP ${response.status}.`,
    'http_error',
    response.status,
  )
}
