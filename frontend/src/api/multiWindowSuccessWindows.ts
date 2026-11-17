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
    typeof value.source_sha256 === 'string' &&
    typeof value.source_commit === 'string' &&
    typeof value.strategy_set_fingerprint === 'string' &&
    typeof value.status === 'string' &&
    isNonNegativeInteger(value.draw_count) &&
    typeof value.event === 'string' &&
    typeof value.evidence_status === 'string' &&
    typeof value.research_only === 'boolean' &&
    typeof value.promotion_allowed === 'boolean' &&
    Array.isArray(value.window_definitions) &&
    value.window_definitions.every(isWindowDefinition) &&
    isNullContract(value.null_contract, lotteryType) &&
    isNonNegativeInteger(value.strategy_count) &&
    isNonNegativeInteger(value.family_size) &&
    Array.isArray(value.rows) &&
    value.rows.every((row: unknown) => isMultiWindowRow(row, runId, lotteryType)) &&
    Array.isArray(value.stability) &&
    value.stability.every(isStabilityDelta) &&
    typeof value.source_authority === 'string'
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
    isNonNegativeInteger(value.source_target_count) &&
    isNullableNonNegativeInteger(value.requested_target_count) &&
    isNonNegativeInteger(value.actual_target_count) &&
    value.actual_target_count <= value.source_target_count &&
    isNullableString(value.first_target_id) &&
    isNullableString(value.first_target_date) &&
    isNullableString(value.last_target_id) &&
    isNullableString(value.last_target_date) &&
    value.observed_winning_target_count <= value.actual_target_count &&
    isNullableProbabilityRational(value.observed_winning_target_rate) &&
    (value.actual_target_count > 0 || value.observed_winning_target_rate === null) &&
    isNonNegativeInteger(value.observed_ticket_count) &&
    isNonNegativeInteger(value.observed_winning_ticket_count) &&
    value.observed_winning_ticket_count <= value.observed_ticket_count &&
    isNullableProbabilityRational(value.observed_ticket_winning_rate) &&
    (value.observed_ticket_count > 0 || value.observed_ticket_winning_rate === null) &&
    Array.isArray(value.prize_tier_vector) &&
    value.prize_tier_vector.every(isTierCount) &&
    isNullableString(value.highest_prize_tier) &&
    isProbabilityRational(value.null_single_ticket_probability) &&
    isProbabilityRational(value.null_portfolio_probability) &&
    isNullableNonNegativeRational(value.expected_null_target_successes) &&
    isNullableRateDifference(value.observed_minus_null_rate) &&
    isNullableNonNegativeRational(value.lift_vs_null) &&
    isNullableProbabilityRational(value.raw_p_value) &&
    isNullableProbabilityRational(value.by_adjusted_p_value) &&
    typeof value.evidence_status === 'string'
  )
}

function isWindowDefinition(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.window_kind === 'string' &&
    isNullableNonNegativeInteger(value.requested_target_count) &&
    typeof value.selection === 'string' &&
    typeof value.window_role === 'string'
  )
}

function isNullContract(value: unknown, lotteryType: string): boolean {
  return (
    isRecord(value) &&
    value.lottery_type === lotteryType &&
    typeof value.game_spec === 'string' &&
    typeof value.sampling_policy === 'string' &&
    typeof value.official_evaluator === 'string' &&
    typeof value.prize_rule_version === 'string' &&
    typeof value.prize_rule_source_sha256 === 'string' &&
    isNonNegativeInteger(value.legal_ticket_count) &&
    isNonNegativeInteger(value.any_prize_ticket_count) &&
    value.any_prize_ticket_count <= value.legal_ticket_count &&
    isProbabilityRational(value.single_ticket_any_prize_probability) &&
    typeof value.portfolio_formula === 'string' &&
    Array.isArray(value.hit_state_weights) &&
    value.hit_state_weights.every(isRecord)
  )
}

function isTierCount(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.tier_id === 'string' &&
    isNonNegativeInteger(value.tier_order) &&
    isNonNegativeInteger(value.count)
  )
}

function isStabilityDelta(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.strategy_id === 'string' &&
    typeof value.strategy_version === 'string' &&
    typeof value.from_window === 'string' &&
    typeof value.to_window === 'string' &&
    isNullableRateDifference(value.delta_observed_winning_target_rate) &&
    typeof value.relation === 'string'
  )
}

function isExactRational(value: unknown): value is ExactRational {
  if (
    !isRecord(value) ||
    typeof value.numerator !== 'string' ||
    !/^-?(?:0|[1-9][0-9]*)$/.test(value.numerator) ||
    typeof value.denominator !== 'string' ||
    !/^[1-9][0-9]*$/.test(value.denominator) ||
    typeof value.decimal_18 !== 'string' ||
    !/^-?(?:0|[1-9][0-9]*)\.[0-9]{18}$/.test(value.decimal_18)
  ) {
    return false
  }

  return value.decimal_18 === renderExactDecimal18(BigInt(value.numerator), BigInt(value.denominator))
}

function renderExactDecimal18(numerator: bigint, denominator: bigint): string {
  const scale = 10n ** 18n
  const isNegative = numerator < 0n
  const scaled = (isNegative ? -numerator : numerator) * scale
  const quotient = scaled / denominator
  const remainder = scaled % denominator
  const doubledRemainder = remainder * 2n
  const rounded =
    quotient +
    (doubledRemainder > denominator ||
    (doubledRemainder === denominator && quotient % 2n === 1n)
      ? 1n
      : 0n)
  const integerPart = rounded / scale
  const fractionalPart = String(rounded % scale).padStart(18, '0')
  const sign = isNegative && rounded !== 0n ? '-' : ''
  return `${sign}${integerPart}.${fractionalPart}`
}

function isProbabilityRational(value: unknown): value is ExactRational {
  if (!isExactRational(value)) return false
  const numerator = BigInt(value.numerator)
  return numerator >= 0n && numerator <= BigInt(value.denominator)
}

function isNonNegativeRational(value: unknown): value is ExactRational {
  return isExactRational(value) && BigInt(value.numerator) >= 0n
}

function isRateDifference(value: unknown): value is ExactRational {
  if (!isExactRational(value)) return false
  const numerator = BigInt(value.numerator)
  const denominator = BigInt(value.denominator)
  return numerator >= -denominator && numerator <= denominator
}

function isNullableProbabilityRational(value: unknown): boolean {
  return value === null || isProbabilityRational(value)
}

function isNullableNonNegativeRational(value: unknown): boolean {
  return value === null || isNonNegativeRational(value)
}

function isNullableRateDifference(value: unknown): boolean {
  return value === null || isRateDifference(value)
}

function isNullableNonNegativeInteger(value: unknown): boolean {
  return value === null || isNonNegativeInteger(value)
}

function isNullableString(value: unknown): boolean {
  return value === null || typeof value === 'string'
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
