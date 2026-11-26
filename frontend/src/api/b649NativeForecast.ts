import type { components, paths } from './generated/openapi'

type GeneratedNativeForecastResponse =
  paths['/api/b649/native-forecast/current']['get']['responses'][200]['content']['application/json']

export type NativeMetric = { numerator: number; denominator: number } | null

export type NativeCandidate = {
  strategy_id: string
  strategy_version: string
  native_k: number
  status?: string
  metric?: NativeMetric
  coverage?: { requested: number; counts: Record<string, number> }
}

type NativeTicketPosition = { position: number; numbers: number[] }

type NativeStrategy = {
  strategy_id: string
  strategy_version: string
  native_k: number
  source_rank: number
  adapter_source_sha256: string
  native_positions: NativeTicketPosition[]
}

type NativeForecastPayload = {
  fixture_only: false
  identity: { history_cutoff: string }
  buckets: {
    native_k: number
    status: string
    selected: { strategy_id: string; strategy_version: string } | null
    tickets: number[][]
    candidates: NativeCandidate[]
  }[]
} & (
  | { history: { last_draw_date: string }; native_strategies?: never }
  | {
      history: { reference: string; sha256: string; last_draw_date?: never }
      forecast_output_semantics: 'STRATEGY_NATIVE_POSITIONS'
      source_proof_status: 'LOCAL_ONLY'
      native_strategies: NativeStrategy[]
    }
)

export type B649NativeForecastResponse = Omit<GeneratedNativeForecastResponse, 'payload'> & {
  payload: NativeForecastPayload
}

export type B649NativeForecastTarget = {
  target_draw_number: string
  target_draw_date: string
}

export type B649NativeForecastErrorKind =
  | 'NOT_FOUND'
  | 'CONFLICT'
  | 'VALIDATION'
  | 'UNAVAILABLE'
  | 'HTTP'
  | 'NETWORK'
  | 'MALFORMED_RESPONSE'

type ValidationError = components['schemas']['ApiValidationErrorResponse']

const CURRENT_FORECAST_ENDPOINT = '/api/b649/native-forecast/current'
const SHA256_PATTERN = /^[0-9a-f]{64}$/
const REQUIRED_NATIVE_BUCKETS = [1, 2, 3, 5, 10, 20]

export class B649NativeForecastRequestError extends Error {
  readonly status: number
  readonly kind: B649NativeForecastErrorKind
  readonly errorCode: string | null

  constructor(
    message: string,
    status: number,
    kind: B649NativeForecastErrorKind,
    errorCode: string | null = null,
  ) {
    super(message)
    this.name = 'B649NativeForecastRequestError'
    this.status = status
    this.kind = kind
    this.errorCode = errorCode
  }
}

export async function fetchB649NativeForecast(
  target: B649NativeForecastTarget,
  signal?: AbortSignal,
): Promise<B649NativeForecastResponse> {
  const query = new URLSearchParams({
    target_draw_number: target.target_draw_number,
    target_draw_date: target.target_draw_date,
  })
  let response: Response
  try {
    response = await fetch(CURRENT_FORECAST_ENDPOINT + '?' + query.toString(), { signal })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new B649NativeForecastRequestError('Native 網路請求失敗。', 0, 'NETWORK')
  }

  if (response.status !== 200) {
    const body = await readErrorBody(response)
    const errorCode = getErrorCode(body)
    const detail = getErrorMessage(body)
    const kind = errorKindForStatus(response.status)
    throw new B649NativeForecastRequestError(
      errorMessageForStatus(response.status, detail),
      response.status,
      kind,
      errorCode,
    )
  }

  let body: unknown
  try {
    body = await response.json()
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new B649NativeForecastRequestError(
      'Native 服務回傳無效 JSON。',
      response.status,
      'MALFORMED_RESPONSE',
    )
  }

  if (!isNativeForecastResponse(body, target)) {
    throw new B649NativeForecastRequestError(
      'Native 回應與所選期別或固定契約不一致，已拒絕顯示。',
      response.status,
      'MALFORMED_RESPONSE',
    )
  }
  return body
}

function errorKindForStatus(status: number): B649NativeForecastErrorKind {
  if (status === 404) return 'NOT_FOUND'
  if (status === 409) return 'CONFLICT'
  if (status === 422) return 'VALIDATION'
  if (status === 503) return 'UNAVAILABLE'
  return 'HTTP'
}

function errorMessageForStatus(status: number, detail: string | null): string {
  if (status === 404) return '所選期別沒有 Native 資料。'
  if (status === 409) return 'Native 資料完整性衝突，未顯示回應。'
  if (status === 422) {
    return 'Native 查詢的期別或日期無效。' + (detail ? ' ' + detail : '')
  }
  if (status === 503) return 'Native 服務目前無法使用。'
  return 'Native 查詢失敗（HTTP ' + status + '）。'
}

async function readErrorBody(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch (error) {
    if (isAbortError(error)) throw error
    return null
  }
}

function getErrorCode(value: unknown): string | null {
  if (!isRecord(value) || typeof value.error_code !== 'string') return null
  return value.error_code
}

function getErrorMessage(value: unknown): string | null {
  if (!isRecord(value)) return null
  const messages: string[] = []
  if (typeof value.message === 'string' && value.message.length > 0) {
    messages.push(value.message)
  }
  const validation = value as Partial<ValidationError>
  if (Array.isArray(validation.fields)) {
    const fieldMessages = validation.fields
      .map((field) => {
        if (!isRecord(field)) return null
        const location = typeof field.location === 'string' ? field.location : null
        const type = typeof field.type === 'string' ? field.type : null
        return location && type ? location + ': ' + type : location ?? type
      })
      .filter((message): message is string => message !== null)
    messages.push(...fieldMessages)
  }
  return messages.length > 0 ? messages.join('；') : null
}

function isNativeForecastResponse(
  value: unknown,
  target: B649NativeForecastTarget,
): value is B649NativeForecastResponse {
  if (!isRecord(value) || !isRecord(value.scope) || !isRecord(value.request_identity)) {
    return false
  }
  const scope = value.scope
  const identity = value.request_identity
  if (
    scope.lottery_type !== 'BIG_LOTTO' ||
    scope.target_draw_number !== target.target_draw_number ||
    scope.target_draw_date !== target.target_draw_date ||
    scope.forecast_stream_id !== 'B649_NEXT_UNDRAWN_FORECAST' ||
    scope.forecast_stream_version !== 'B649_FULL_OFFICIAL_ANY_PRIZE_R1' ||
    !isDrawNumber(scope.target_draw_number) ||
    !isIsoDate(scope.target_draw_date) ||
    typeof identity.request_id !== 'string' ||
    identity.request_id.length === 0 ||
    !isSha256(identity.request_sha256) ||
    !isPositiveSafeInteger(identity.version) ||
    typeof identity.run_id !== 'string' ||
    identity.run_id.length === 0 ||
    !isSha256(identity.payload_sha256) ||
    !isIsoDateTime(identity.generation_started_at) ||
    !isIsoDateTime(identity.generation_finished_at) ||
    !isIsoDateTime(identity.committed_at) ||
    Date.parse(identity.generation_started_at) > Date.parse(identity.generation_finished_at) ||
    !isRecord(value.payload)
  ) {
    return false
  }
  return isNativePayload(value.payload, target)
}

function isNativePayload(
  payload: Record<string, unknown>,
  target: B649NativeForecastTarget,
): boolean {
  const identity = payload.identity
  const history = payload.history
  const buckets = payload.buckets
  if (
    payload.fixture_only !== false ||
    !isSha256(payload.bundle_id) ||
    !isRecord(identity) ||
    !isRecord(history) ||
    identity.schema_version !== 'B649_NEXT_UNDRAWN_FORECAST_V1' ||
    identity.lottery_type !== 'BIG_LOTTO' ||
    identity.target_draw_number !== target.target_draw_number ||
    identity.target_draw_date !== target.target_draw_date ||
    identity.objective !== 'OFFICIAL_ANY_PRIZE' ||
    identity.ranking_policy_version !== 'B649_FULL_OFFICIAL_ANY_PRIZE_R1' ||
    !isDrawNumber(identity.history_cutoff) ||
    Number(identity.history_cutoff) >= Number(target.target_draw_number) ||
    !isSha256(identity.history_payload_sha256) ||
    !isSha256(identity.schedule_authority_sha256) ||
    !isSha256(identity.producer_fingerprint) ||
    !isSha256(identity.catalog_universe_sha256) ||
    !isSha256(identity.generation_config_sha256) ||
    !Array.isArray(buckets) ||
    buckets.length !== REQUIRED_NATIVE_BUCKETS.length
  ) {
    return false
  }

  // The identity schema_version is shared by the two producer formats.
  if (
    payload.forecast_output_semantics === 'STRATEGY_NATIVE_POSITIONS' ||
    'native_strategies' in payload ||
    'reference' in history ||
    'sha256' in history
  ) {
    return isNativePositionsPayload(payload, history, identity.history_payload_sha256, buckets)
  }

  if (
    identity.history_payload_sha256 !== history.history_sha256 ||
    history.last_draw_number !== identity.history_cutoff ||
    !isDrawNumber(history.last_draw_number) ||
    Number(history.last_draw_number) >= Number(target.target_draw_number) ||
    !isIsoDate(history.last_draw_date) ||
    history.last_draw_date >= target.target_draw_date ||
    !isPositiveSafeInteger(history.draw_count) ||
    !isSha256(history.history_sha256)
  ) {
    return false
  }
  return buckets.every((bucket, index) =>
    isNativeBucket(bucket, REQUIRED_NATIVE_BUCKETS[index]),
  )
}

function isNativePositionsPayload(
  payload: Record<string, unknown>,
  history: Record<string, unknown>,
  historySha256: string,
  buckets: unknown[],
): boolean {
  if (
    payload.forecast_output_semantics !== 'STRATEGY_NATIVE_POSITIONS' ||
    payload.source_proof_status !== 'LOCAL_ONLY' ||
    history.sha256 !== historySha256 ||
    history.reference !== 'research-live-history:sha256:' + historySha256 ||
    'last_draw_date' in history ||
    'last_draw_number' in history ||
    'history_sha256' in history ||
    'draw_count' in history ||
    !isSha256(payload.bundle_id) ||
    !Array.isArray(payload.native_strategies) ||
    payload.native_strategies.length === 0
  ) return false

  const strategies = new Map<string, NativeStrategy>()
  const sourceRanks = new Set<number>()
  for (const row of payload.native_strategies) {
    if (!isNativeStrategy(row) || strategies.has(row.strategy_id) || sourceRanks.has(row.source_rank)) {
      return false
    }
    strategies.set(row.strategy_id, row)
    sourceRanks.add(row.source_rank)
  }
  const bundleId = payload.bundle_id
  return buckets.every((bucket, index) =>
    isNativePositionsBucket(bucket, REQUIRED_NATIVE_BUCKETS[index], bundleId, strategies),
  )
}

function isNativeStrategy(value: unknown): value is NativeStrategy {
  return (
    isStrategyIdentity(value) &&
    isPositiveSafeInteger(value.native_k) &&
    isPositiveSafeInteger(value.source_rank) &&
    isSha256(value.adapter_source_sha256) &&
    isNativeTicketPositions(value.native_positions, value.native_k)
  )
}

function isStrategyIdentity(value: unknown): value is Record<string, unknown> & {
  strategy_id: string
  strategy_version: string
} {
  return (
    isRecord(value) &&
    typeof value.strategy_id === 'string' &&
    value.strategy_id.trim().length > 0 &&
    typeof value.strategy_version === 'string' &&
    value.strategy_version.trim().length > 0
  )
}

function isNativePositionsBucket(
  value: unknown,
  expectedK: number,
  bundleId: string,
  strategies: ReadonlyMap<string, NativeStrategy>,
): boolean {
  if (
    !isRecord(value) ||
    value.native_k !== expectedK ||
    typeof value.status !== 'string' ||
    !Array.isArray(value.tickets) ||
    !Array.isArray(value.candidates)
  ) return false

  const bucket = 'K' + expectedK
  if (value.status !== 'AVAILABLE') {
    return (
      value.bucket === bucket &&
      value.selected === null &&
      value.tickets.length === 0 &&
      value.candidates.length === 0 &&
      (value.native_positions === undefined || isNativeTicketPositions(value.native_positions, 0))
    )
  }

  const selected = value.selected
  const entry = value.entry_identity
  if (
    !isStrategyIdentity(selected) ||
    !hasOptionalEvidence(selected) ||
    value.bucket !== bucket + ':' + selected.strategy_id ||
    value.generation_status !== 'COMPLETE' ||
    !Array.isArray(entry) ||
    entry.length !== 4 ||
    entry[0] !== bundleId ||
    entry[1] !== expectedK ||
    entry[2] !== selected.strategy_id ||
    entry[3] !== selected.strategy_version ||
    !isNativeTicketPositions(value.native_positions, expectedK) ||
    value.tickets.length !== expectedK
  ) return false

  const ids = new Set<string>()
  for (const candidate of value.candidates) {
    if (!isStrategyIdentity(candidate) || !hasOptionalEvidence(candidate) || ids.has(candidate.strategy_id)) {
      return false
    }
    const source = strategies.get(candidate.strategy_id)
    if (
      !source ||
      candidate.strategy_version !== source.strategy_version ||
      candidate.native_k !== expectedK ||
      source.native_k !== expectedK ||
      candidate.adapter_source_sha256 !== source.adapter_source_sha256
    ) return false
    ids.add(candidate.strategy_id)
  }
  const source = strategies.get(selected.strategy_id)
  if (!ids.has(selected.strategy_id) || !source || source.strategy_version !== selected.strategy_version) {
    return false
  }

  const positions = value.native_positions
  return value.tickets.every((ticket, index) =>
    isSixNumberTicket(ticket) &&
    ticket.every((number, slot) =>
      number === positions[index].numbers[slot] &&
      number === source.native_positions[index].numbers[slot],
    ),
  )
}

function hasOptionalEvidence(value: Record<string, unknown>): boolean {
  return (
    (!('metric' in value) || isMetric(value.metric)) &&
    (!('coverage' in value) || isCoverage(value.coverage)) &&
    (!('status' in value) || typeof value.status === 'string') &&
    (!('rankable' in value) || typeof value.rankable === 'boolean') &&
    (!('evidence_complete' in value) || typeof value.evidence_complete === 'boolean')
  )
}

function isNativeTicketPositions(value: unknown, nativeK: number): value is NativeTicketPosition[] {
  return (
    Array.isArray(value) &&
    value.length === nativeK &&
    value.every((row, index) =>
      isRecord(row) && row.position === index + 1 && isSixNumberTicket(row.numbers),
    )
  )
}

function isNativeBucket(value: unknown, expectedK: number): boolean {
  if (!isRecord(value) || value.native_k !== expectedK) return false
  if (
    value.bucket !== 'K' + expectedK ||
    typeof value.status !== 'string' ||
    !Array.isArray(value.tickets) ||
    !Array.isArray(value.candidates)
  ) {
    return false
  }
  const candidates = value.candidates
  const seenIds = new Set<string>()
  for (const candidate of candidates) {
    if (!isNativeCandidate(candidate, expectedK)) return false
    if (seenIds.has(candidate.strategy_id)) return false
    seenIds.add(candidate.strategy_id)
  }
  const selected = value.selected
  if (selected !== null && !isNativeSelection(selected, candidates, expectedK)) return false
  if (value.status === 'AVAILABLE' && selected === null) return false
  if (value.status !== 'AVAILABLE' && selected !== null) return false
  if (value.status === 'AVAILABLE' && value.tickets.length !== expectedK) return false
  if (value.status !== 'AVAILABLE' && value.tickets.length !== 0) return false
  return value.tickets.every(isSixNumberTicket)
}

function isNativeCandidate(value: unknown, expectedK: number): value is Record<string, unknown> & {
  strategy_id: string
} {
  if (
    !isRecord(value) ||
    typeof value.strategy_id !== 'string' ||
    value.strategy_id.length === 0 ||
    typeof value.strategy_version !== 'string' ||
    value.strategy_version.length === 0 ||
    value.native_k !== expectedK ||
    typeof value.rankable !== 'boolean' ||
    typeof value.evidence_complete !== 'boolean' ||
    !isMetric(value.metric) ||
    !isCoverage(value.coverage)
  ) {
    return false
  }
  return value.status === undefined || typeof value.status === 'string'
}

function isNativeSelection(
  value: unknown,
  candidates: unknown[],
  expectedK: number,
): boolean {
  if (
    !isRecord(value) ||
    typeof value.strategy_id !== 'string' ||
    typeof value.strategy_version !== 'string' ||
    typeof value.response_shape !== 'string' ||
    !isMetric(value.metric) ||
    !isCoverage(value.coverage)
  ) {
    return false
  }
  return candidates.some(
    (candidate) =>
      isNativeCandidate(candidate, expectedK) &&
      candidate.strategy_id === value.strategy_id &&
      candidate.strategy_version === value.strategy_version,
  )
}

function isMetric(value: unknown): boolean {
  if (value === null) return true
  if (!isRecord(value)) return false
  const numerator = value.numerator
  const denominator = value.denominator
  if (
    !isNonNegativeSafeInteger(numerator) ||
    !isNonNegativeSafeInteger(denominator) ||
    numerator > denominator
  ) {
    return false
  }
  if (denominator === 0) return numerator === 0 && value.rate === null
  if (!isRecord(value.rate)) return false

  const divisor = greatestCommonDivisor(numerator, denominator)
  return (
    value.rate.numerator === String(numerator / divisor) &&
    value.rate.denominator === String(denominator / divisor)
  )
}

function greatestCommonDivisor(left: number, right: number): number {
  while (right !== 0) {
    const remainder = left % right
    left = right
    right = remainder
  }
  return left
}

function isCoverage(value: unknown): boolean {
  if (!isRecord(value) || !isNonNegativeSafeInteger(value.requested)) return false
  if (!isRecord(value.counts)) return false
  return Object.values(value.counts).every(isNonNegativeSafeInteger)
}

function isSixNumberTicket(value: unknown): value is number[] {
  if (!Array.isArray(value) || value.length !== 6) return false
  const numbers = value
  return (
    numbers.every(
      (number) => Number.isSafeInteger(number) && Number(number) >= 1 && Number(number) <= 49,
    ) && new Set(numbers).size === 6
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isDrawNumber(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9]{9}$/.test(value)
}

function isIsoDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const parsed = new Date(value + 'T00:00:00.000Z')
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

function isIsoDateTime(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    /^\d{4}-\d{2}-\d{2}T/.test(value) &&
    Number.isFinite(Date.parse(value))
  )
}

function isSha256(value: unknown): value is string {
  return typeof value === 'string' && SHA256_PATTERN.test(value)
}

function isNonNegativeSafeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0
}

function isPositiveSafeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) > 0
}

function isAbortError(value: unknown): boolean {
  return isRecord(value) && value.name === 'AbortError'
}
