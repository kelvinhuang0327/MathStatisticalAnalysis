import type { components, paths } from './generated/openapi'

export type StrategyMatrixStructuralResponse =
  paths['/api/v1/strategy-matrix/structural']['get']['responses'][200]['content']['application/json']
export type StructuralMatrixCell = StrategyMatrixStructuralResponse['cells'][number]
export type StructuralMatrixValue = NonNullable<StructuralMatrixCell['value']>
export type StructuralLottery = components['schemas']['StructuralLottery']
export type StructuralCaseId = components['schemas']['StructuralCaseId']
export type StructuralMethodId = components['schemas']['StructuralMethodId']
export type StructuralTicketCount = components['schemas']['StructuralTicketCount']
export type StructuralSourceStatus = components['schemas']['StructuralSourceStatus']
export type StructuralMeasurementStatus = components['schemas']['StructuralMeasurementStatus']

export interface StrategyMatrixStructuralQuery {
  lottery?: StructuralLottery
  methodId?: StructuralMethodId
  ticketCount?: StructuralTicketCount
}

export class StrategyMatrixStructuralRequestError extends Error {
  readonly status: number
  readonly errorCode?: string

  constructor(message: string, status: number, errorCode?: string) {
    super(message)
    this.name = 'StrategyMatrixStructuralRequestError'
    this.status = status
    this.errorCode = errorCode
  }
}

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const DECIMAL_INTEGER_PATTERN = /^(?:0|[1-9][0-9]*)$/

const STRUCTURAL_LOTTERIES = [
  'BIG_LOTTO',
  'DAILY_539',
  'POWER_LOTTO_ZONE1',
] as const satisfies readonly StructuralLottery[]

const STRUCTURAL_CASE_IDS = [
  'NATIVE_BIG_LOTTO',
  'NATIVE_DAILY_539',
  'NATIVE_POWER_LOTTO_ZONE1',
] as const satisfies readonly StructuralCaseId[]

const STRUCTURAL_METHOD_IDS = [
  'CYCLIC_SIDON_SHIFT_V1',
  'GREEDY_MIN_OVERLAP_V1',
  'GREEDY_MINMAX_THEN_SUM_OVERLAP_V1',
  'GREEDY_MINMAX_SUM_THEN_REUSE_DISPERSION_V1',
  'CANDIDATE_LOW_OVERLAP_V1',
  'RESTART_GREEDY_SWAP_COVERAGE_SEARCH_V1',
  'REFERENCE_E_BEST_1EXCHANGE_EXACT_COVERAGE_V1',
  'ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1',
  'B649_CANDIDATE_SET_LOW_OVERLAP_V1',
  'B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1',
  'B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1',
  'HARD_DIV_PAIRWISE_OVERLAP_R1',
  'HARD_DIV_PAIRWISE_OVERLAP_R2',
  'ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1',
] as const satisfies readonly StructuralMethodId[]

const STRUCTURAL_TICKET_COUNTS = [2, 3, 5, 10, 20] as const satisfies
  readonly StructuralTicketCount[]

const CASE_ID_BY_LOTTERY = {
  BIG_LOTTO: 'NATIVE_BIG_LOTTO',
  DAILY_539: 'NATIVE_DAILY_539',
  POWER_LOTTO_ZONE1: 'NATIVE_POWER_LOTTO_ZONE1',
} as const satisfies Record<StructuralLottery, StructuralCaseId>

const DRAW_SIZE_BY_LOTTERY: Record<StructuralLottery, bigint> = {
  BIG_LOTTO: 6n,
  DAILY_539: 5n,
  POWER_LOTTO_ZONE1: 6n,
}

const VALID_STATUS_PAIRS = new Set([
  'MEASURED/MEASURED',
  'REUSED_VERIFIED/MEASURED',
  'REUSED_VERIFIED/UNAVAILABLE',
  'NOT_APPLICABLE/NOT_APPLICABLE',
  'NOT_RUN/UNAVAILABLE',
])

const PLACEHOLDER_ID_TOKENS = new Set([
  'UNKNOWN',
  'NULL',
  'UNDEFINED',
  'NONE',
  'N/A',
  'NA',
  'TBD',
  'TODO',
  'UNSET',
  'NOT_SET',
  'NOT_PROVIDED',
  'PLACEHOLDER',
])

const RESPONSE_KEYS = [
  'schema_id',
  'schema_version',
  'projection_sha256',
  'authority',
  'scope',
  'supported_ticket_counts',
  'metric',
  'claim_boundary',
  'cells',
] as const

const CELL_KEYS = [
  'row_id',
  'case_id',
  'lottery',
  'method_id',
  'ticket_count',
  'method_objective',
  'source_status',
  'measurement_status',
  'value',
  'portfolio_sha256',
  'unavailable_reason',
  'local_optimum_status',
] as const

const PINNED_AUTHORITY = {
  kind: 'CANONICAL_PACKAGED_MATRIX',
  source_head: '9486a67ed358c96435cc8b913962380c3db6b100',
  source_tree: 'd53c0a23f9df12127f2ea16d480705c146f4e62b',
  sources: {
    metric_surface: {
      repository_path: 'docs/research/matrix-native-results/expected-max-main-matches-v1-result.json',
      file_sha256: 'bb0cb899dd301711f926617e74af01d14ce7c134b7ed96f7ae0acefcfa532d85',
    },
    matrix: {
      repository_path: 'docs/research/matrix-native-results/imported-optimizer-integration-r1-result.json',
      file_sha256: '0c2cfa9d1ec90238699f1a878ec00ef98aa29b14bb02cacbade38159c8cee802',
    },
    ledger: {
      repository_path: 'docs/research/cross_lottery_research_ledger_r1.json',
      file_sha256: '56a6d801636afeb883a2937762cf123ef2fa96a763f13bcb748dce32b66995d9',
    },
  },
} as const

const PINNED_METRIC = {
  metric_id: 'EXPECTED_MAX_MAIN_MATCHES_V1',
  definition: 'E[max_t |t intersection D|]',
  unit: 'MAIN_MATCHES',
  draw_distribution: 'LEGAL_UNIFORM_MAIN_DRAW',
  exactness: 'EXACT_COMBINATORIAL_EXPECTATION',
} as const

const PINNED_CLAIM_BOUNDARY = {
  historical_outcomes_used: false,
  historical_success_rate_claimed: false,
  ranking_score_claimed: false,
  global_optimum_claimed: false,
  cross_lottery_normalization: 'NOT_PERFORMED',
} as const

export async function queryStrategyMatrixStructural(
  query: StrategyMatrixStructuralQuery = {},
  signal?: AbortSignal,
): Promise<StrategyMatrixStructuralResponse> {
  const parameters = new URLSearchParams()
  if (query.lottery) parameters.set('lottery', query.lottery)
  if (query.methodId) parameters.set('method_id', query.methodId)
  if (query.ticketCount !== undefined) parameters.set('ticket_count', String(query.ticketCount))
  const suffix = parameters.toString()

  const response = await fetch(
    '/api/v1/strategy-matrix/structural' + (suffix ? '?' + suffix : ''),
    {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    },
  )
  let payload: unknown
  try {
    payload = await response.json()
  } catch (error) {
    if (!response.ok || isAbortError(error)) throw error
    throw malformedResponseError()
  }
  if (!response.ok) {
    throw new StrategyMatrixStructuralRequestError(
      isRecord(payload) && typeof payload.message === 'string'
        ? payload.message
        : 'Structural Matrix request failed with HTTP ' + response.status,
      response.status,
      isRecord(payload) && typeof payload.error_code === 'string' ? payload.error_code : undefined,
    )
  }
  if (!isStrategyMatrixStructuralResponse(payload) || !cellsMatchQuery(payload.cells, query)) {
    throw malformedResponseError()
  }
  return payload
}

function isStrategyMatrixStructuralResponse(
  value: unknown,
): value is StrategyMatrixStructuralResponse {
  if (!hasExactKeys(value, RESPONSE_KEYS)) return false
  return (
    value.schema_id === 'lottolab.strategy_matrix.structural' &&
    value.schema_version === '1.0.0' &&
    isSha256(value.projection_sha256) &&
    isPinnedAuthority(value.authority) &&
    value.scope === 'NATIVE_UNIFORM_WINNING_SPACE' &&
    isSupportedTicketCounts(value.supported_ticket_counts) &&
    isPinnedMetric(value.metric) &&
    isPinnedClaimBoundary(value.claim_boundary) &&
    Array.isArray(value.cells) &&
    value.cells.every(isStructuralMatrixCell) &&
    hasUniqueRowIds(value.cells)
  )
}

function isPinnedAuthority(value: unknown): boolean {
  if (
    !hasExactKeys(value, ['kind', 'source_head', 'source_tree', 'sources']) ||
    value.kind !== PINNED_AUTHORITY.kind ||
    value.source_head !== PINNED_AUTHORITY.source_head ||
    value.source_tree !== PINNED_AUTHORITY.source_tree ||
    !hasExactKeys(value.sources, ['metric_surface', 'matrix', 'ledger'])
  ) {
    return false
  }

  return (
    isPinnedSourceReference(value.sources.metric_surface, PINNED_AUTHORITY.sources.metric_surface) &&
    isPinnedSourceReference(value.sources.matrix, PINNED_AUTHORITY.sources.matrix) &&
    isPinnedSourceReference(value.sources.ledger, PINNED_AUTHORITY.sources.ledger)
  )
}

function isPinnedSourceReference(
  value: unknown,
  expected: { repository_path: string; file_sha256: string },
): boolean {
  return (
    hasExactKeys(value, ['repository_path', 'file_sha256']) &&
    value.repository_path === expected.repository_path &&
    value.file_sha256 === expected.file_sha256
  )
}

function isPinnedMetric(value: unknown): boolean {
  return (
    hasExactKeys(value, ['metric_id', 'definition', 'unit', 'draw_distribution', 'exactness']) &&
    value.metric_id === PINNED_METRIC.metric_id &&
    value.definition === PINNED_METRIC.definition &&
    value.unit === PINNED_METRIC.unit &&
    value.draw_distribution === PINNED_METRIC.draw_distribution &&
    value.exactness === PINNED_METRIC.exactness
  )
}

function isPinnedClaimBoundary(value: unknown): boolean {
  return (
    hasExactKeys(value, [
      'historical_outcomes_used',
      'historical_success_rate_claimed',
      'ranking_score_claimed',
      'global_optimum_claimed',
      'cross_lottery_normalization',
    ]) &&
    value.historical_outcomes_used === PINNED_CLAIM_BOUNDARY.historical_outcomes_used &&
    value.historical_success_rate_claimed === PINNED_CLAIM_BOUNDARY.historical_success_rate_claimed &&
    value.ranking_score_claimed === PINNED_CLAIM_BOUNDARY.ranking_score_claimed &&
    value.global_optimum_claimed === PINNED_CLAIM_BOUNDARY.global_optimum_claimed &&
    value.cross_lottery_normalization === PINNED_CLAIM_BOUNDARY.cross_lottery_normalization
  )
}

function isSupportedTicketCounts(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.length === STRUCTURAL_TICKET_COUNTS.length &&
    value.every(
      (ticketCount, index) =>
        typeof ticketCount === 'number' &&
        Number.isInteger(ticketCount) &&
        ticketCount === STRUCTURAL_TICKET_COUNTS[index],
    )
  )
}

function isStructuralMatrixCell(value: unknown): value is StructuralMatrixCell {
  if (!hasExactKeys(value, CELL_KEYS)) return false
  if (
    !isNonPlaceholderIdentity(value.row_id) ||
    !isOneOf(value.case_id, STRUCTURAL_CASE_IDS) ||
    !isOneOf(value.lottery, STRUCTURAL_LOTTERIES) ||
    !isOneOf(value.method_id, STRUCTURAL_METHOD_IDS) ||
    !isStructuralTicketCount(value.ticket_count) ||
    typeof value.method_objective !== 'string' ||
    value.method_objective.length === 0 ||
    !isOneOf(value.source_status, ['MEASURED', 'REUSED_VERIFIED', 'NOT_APPLICABLE', 'NOT_RUN'] as const) ||
    !isOneOf(value.measurement_status, ['MEASURED', 'NOT_APPLICABLE', 'UNAVAILABLE'] as const) ||
    !hasValidOptionalStatus(value.local_optimum_status)
  ) {
    return false
  }

  if (value.case_id !== CASE_ID_BY_LOTTERY[value.lottery]) return false
  if (!VALID_STATUS_PAIRS.has(value.source_status + '/' + value.measurement_status)) return false

  if (value.measurement_status === 'MEASURED') {
    return (
      isStructuralMatrixValue(value.value, DRAW_SIZE_BY_LOTTERY[value.lottery]) &&
      isSha256(value.portfolio_sha256) &&
      value.unavailable_reason === null
    )
  }

  return (
    value.value === null &&
    value.portfolio_sha256 === null &&
    isNonEmptyReason(value.unavailable_reason) &&
    value.local_optimum_status === null
  )
}

function isStructuralMatrixValue(
  value: unknown,
  drawSize: bigint,
): value is StructuralMatrixValue {
  if (
    !hasExactKeys(value, ['numerator', 'denominator']) ||
    typeof value.numerator !== 'string' ||
    !DECIMAL_INTEGER_PATTERN.test(value.numerator) ||
    typeof value.denominator !== 'string' ||
    !DECIMAL_INTEGER_PATTERN.test(value.denominator) ||
    value.denominator === '0'
  ) {
    return false
  }

  try {
    const numerator = BigInt(value.numerator)
    const denominator = BigInt(value.denominator)
    return (
      numerator <= drawSize * denominator &&
      (numerator === 0n || greatestCommonDivisor(numerator, denominator) === 1n)
    )
  } catch {
    return false
  }
}

function greatestCommonDivisor(left: bigint, right: bigint): bigint {
  let a = left
  let b = right
  while (b !== 0n) {
    ;[a, b] = [b, a % b]
  }
  return a
}

function isNonPlaceholderIdentity(value: unknown): value is string {
  if (typeof value !== 'string' || value.trim().length === 0) return false
  const parts = value.trim().split('|').map((part) => part.trim().toUpperCase())
  return parts.every(
    (part) =>
      part.length > 0 &&
      !PLACEHOLDER_ID_TOKENS.has(part) &&
      !/^<.+>$/.test(part),
  )
}

function isNonEmptyReason(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function hasValidOptionalStatus(value: unknown): value is string | null {
  return value === null || (typeof value === 'string' && value.length > 0)
}

function isSha256(value: unknown): value is string {
  return typeof value === 'string' && SHA256_PATTERN.test(value)
}

function isAbortError(value: unknown): boolean {
  return isRecord(value) && value.name === 'AbortError'
}

function malformedResponseError(): StrategyMatrixStructuralRequestError {
  return new StrategyMatrixStructuralRequestError(
    'Structural Matrix returned an invalid response contract',
    502,
  )
}

function isStructuralTicketCount(value: unknown): value is StructuralTicketCount {
  return (
    typeof value === 'number' &&
    Number.isInteger(value) &&
    STRUCTURAL_TICKET_COUNTS.includes(value as StructuralTicketCount)
  )
}

function isOneOf<const Values extends readonly string[]>(
  value: unknown,
  allowedValues: Values,
): value is Values[number] {
  return typeof value === 'string' && allowedValues.includes(value as Values[number])
}

function hasUniqueRowIds(cells: readonly StructuralMatrixCell[]): boolean {
  const rowIds = new Set<string>()
  for (const cell of cells) {
    if (rowIds.has(cell.row_id)) return false
    rowIds.add(cell.row_id)
  }
  return true
}

function cellsMatchQuery(
  cells: readonly StructuralMatrixCell[],
  query: StrategyMatrixStructuralQuery,
): boolean {
  return cells.every(
    (cell) =>
      (!query.lottery || cell.lottery === query.lottery) &&
      (!query.methodId || cell.method_id === query.methodId) &&
      (query.ticketCount === undefined || cell.ticket_count === query.ticketCount),
  )
}

function hasExactKeys(
  value: unknown,
  expectedKeys: readonly string[],
): value is Record<string, unknown> {
  if (!isRecord(value)) return false
  const actualKeys = Object.keys(value)
  return (
    actualKeys.length === expectedKeys.length &&
    expectedKeys.every((key) => Object.hasOwn(value, key))
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
