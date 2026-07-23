import type { components, paths } from './generated/openapi'

export type HistoricalRunPage =
  paths['/api/v1/historical-results/runs']['get']['responses'][200]['content']['application/json']
export type HistoricalRun = HistoricalRunPage['items'][number]
export type HistoricalSuccessWindowPage =
  paths['/api/v1/historical-prefix-success-windows']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessWindowResult = HistoricalSuccessWindowPage['items'][number]
export type HistoricalSuccessStabilityMatrix =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/matrix']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessFeatureCohorts =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessPrefixCount =
  components['schemas']['HistoricalPrefixSuccessPrefixCount']
export type HistoricalSuccessCriterion =
  components['schemas']['HistoricalPrefixSuccessCriterion']

export const HISTORICAL_SUCCESS_PREFIX_COUNTS = [
  1, 2, 3, 4, 5, 10, 15, 20,
] as const satisfies readonly HistoricalSuccessPrefixCount[]
export const HISTORICAL_SUCCESS_CRITERIA = [
  'M3_PLUS',
  'M4_PLUS',
  'M5_PLUS',
  'M6',
  'M2_PLUS_SPECIAL',
  'M3_PLUS_SPECIAL',
  'M4_PLUS_SPECIAL',
  'M5_PLUS_SPECIAL',
] as const satisfies readonly HistoricalSuccessCriterion[]

const RUNS_ENDPOINT = '/api/v1/historical-results/runs'
const WINDOWS_ENDPOINT = '/api/v1/historical-prefix-success-windows'
const SHA256_PATTERN = /^[0-9a-f]{64}$/
const PREFIX_COUNT_SET = new Set<number>(HISTORICAL_SUCCESS_PREFIX_COUNTS)
const CRITERION_SET = new Set<string>(HISTORICAL_SUCCESS_CRITERIA)
const WINDOW_KINDS = ['FULL_HISTORY', 'LONG', 'MEDIUM', 'SHORT'] as const
const WINDOW_ROLES = [
  'REFERENCE_ONLY',
  'PRIMARY_EVIDENCE',
  'STABILITY_CONFIRMATION',
  'DEGRADATION_VETO',
] as const
const WINDOW_DRAW_COUNTS = [null, 750, 300, 50] as const
const COMPARISON_DEFINITIONS = [
  ['FULL_HISTORY_TO_LONG', 0, 1],
  ['LONG_TO_MEDIUM', 1, 2],
  ['MEDIUM_TO_SHORT', 2, 3],
  ['LONG_TO_SHORT', 1, 3],
] as const
export const HISTORICAL_SUCCESS_FEATURE_RELATIONS = [
  'HIGHER',
  'EQUAL',
  'LOWER',
  'UNAVAILABLE',
] as const
const EVALUATION_STATUSES = new Set([
  'COMPLETE',
  'INSUFFICIENT_DRAWS',
  'NO_ELIGIBLE_DRAWS',
])
const EVIDENCE_STATUSES = new Set([
  'DESCRIPTIVE_ONLY',
  'HISTORICAL_OOS_VERIFIED',
  'CROSS_GAME_VERIFIED',
  'SHADOW_CAPTURE',
  'PRODUCTION_ELIGIBLE',
  'REJECTED',
  'NOT_READY',
])
const CRITERION_PARAMETERS = {
  M3_PLUS: [3, false],
  M4_PLUS: [4, false],
  M5_PLUS: [5, false],
  M6: [6, false],
  M2_PLUS_SPECIAL: [2, true],
  M3_PLUS_SPECIAL: [3, true],
  M4_PLUS_SPECIAL: [4, true],
  M5_PLUS_SPECIAL: [5, true],
} as const satisfies Record<HistoricalSuccessCriterion, readonly [number, boolean]>

export interface HistoricalRunQuery {
  limit: number
  offset: number
}

export interface HistoricalSuccessWindowQuery extends HistoricalRunQuery {
  import_identity_sha256: string
  prefix_count: HistoricalSuccessPrefixCount
  criterion: HistoricalSuccessCriterion
}

export interface HistoricalSuccessExactQuery {
  import_identity_sha256: string
  strategy_id: string
  strategy_version: string
  replicate: number
  prefix_count: HistoricalSuccessPrefixCount
  criterion: HistoricalSuccessCriterion
}

export interface HistoricalSuccessMatrixQuery {
  import_identity_sha256: string
  strategy_id: string
  strategy_version: string
  replicate: number
}

export interface HistoricalSuccessFeatureCohortQuery
  extends HistoricalSuccessExactQuery {}

export type HistoricalSuccessErrorKind =
  | 'NOT_CONFIGURED'
  | 'UNAVAILABLE'
  | 'NOT_FOUND'
  | 'INVALID_REQUEST'
  | 'MALFORMED_RESPONSE'
  | 'NETWORK'

export class HistoricalSuccessWindowsRequestError extends Error {
  readonly status: number
  readonly kind: HistoricalSuccessErrorKind
  readonly errorCode: string | null

  constructor(
    message: string,
    status: number,
    kind: HistoricalSuccessErrorKind,
    errorCode: string | null = null,
  ) {
    super(message)
    this.name = 'HistoricalSuccessWindowsRequestError'
    this.status = status
    this.kind = kind
    this.errorCode = errorCode
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function isNonBlankString(value: unknown): value is string {
  return isString(value) && value.trim().length > 0
}

function isNullableString(value: unknown): value is string | null {
  return value === null || isString(value)
}

function isNullableNonBlankString(value: unknown): value is string | null {
  return value === null || isNonBlankString(value)
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function isPositiveInteger(value: unknown): value is number {
  return isNonNegativeInteger(value) && value > 0
}

function isSha256(value: unknown): value is string {
  return isString(value) && SHA256_PATTERN.test(value)
}

function isPageShape(
  value: Record<string, unknown>,
): value is Record<string, unknown> & {
  total_count: number
  limit: number
  offset: number
} {
  return (
    isNonNegativeInteger(value.total_count) &&
    isPositiveInteger(value.limit) &&
    isNonNegativeInteger(value.offset)
  )
}

function isHistoricalRun(value: unknown): value is HistoricalRun {
  if (!isRecord(value)) return false
  return (
    isNonBlankString(value.run_id) &&
    isSha256(value.import_identity_sha256) &&
    isSha256(value.manifest_sha256) &&
    isNonBlankString(value.contract_version) &&
    isNonBlankString(value.source_kind) &&
    isNonBlankString(value.source_repository) &&
    isNonBlankString(value.source_commit_oid) &&
    isSha256(value.source_artifact_sha256) &&
    isNonBlankString(value.dataset_identity) &&
    isSha256(value.dataset_sha256) &&
    isNullableString(value.legacy_run_id) &&
    isNonBlankString(value.lottery_type) &&
    isNonBlankString(value.started_at) &&
    isNonBlankString(value.completed_at)
  )
}

function isHistoricalRunPage(value: unknown): value is HistoricalRunPage {
  if (!isRecord(value) || !Array.isArray(value.items) || !isPageShape(value)) return false
  return (
    value.items.every(isHistoricalRun) &&
    value.items.length <= value.limit &&
    value.offset + value.items.length <= value.total_count
  )
}

function isDrawIdentity(value: unknown): boolean {
  return (
    isRecord(value) &&
    isNonNegativeInteger(value.draw_number) &&
    isNonBlankString(value.draw_date) &&
    isSha256(value.draw_sha256)
  )
}

function isExactRate(value: unknown): boolean {
  if (
    !isRecord(value) ||
    !isNonNegativeInteger(value.numerator) ||
    !isNonNegativeInteger(value.denominator) ||
    typeof value.available !== 'boolean'
  ) {
    return false
  }
  return (
    value.numerator <= value.denominator &&
    value.available === (value.denominator > 0)
  )
}

function isStrategyIdentity(value: unknown): boolean {
  return (
    isRecord(value) &&
    isNonBlankString(value.strategy_id) &&
    isNonBlankString(value.effective_strategy_id) &&
    isNonBlankString(value.strategy_version) &&
    isPositiveInteger(value.replicate) &&
    isNonBlankString(value.identity_kind) &&
    isNonBlankString(value.governance_status) &&
    isNullableNonBlankString(value.alias_of_strategy_id) &&
    isNullableNonBlankString(value.equivalence_group) &&
    typeof value.nested_prefix_supported === 'boolean' &&
    isSha256(value.descriptor_sha256)
  )
}

function isCriterion(value: unknown, expected: HistoricalSuccessCriterion): boolean {
  const [minimumMainHits, requireSpecialHit] = CRITERION_PARAMETERS[expected]
  return (
    isRecord(value) &&
    value.criterion === expected &&
    value.minimum_main_hits === minimumMainHits &&
    value.require_special_hit === requireSpecialHit &&
    value.measurement_mode === 'LEGAL_TICKET_PRIZE'
  )
}

function isWindow(value: unknown, index: number): boolean {
  if (!isRecord(value)) return false
  if (
    value.window_kind !== WINDOW_KINDS[index] ||
    value.window_role !== WINDOW_ROLES[index] ||
    value.requested_draw_count !== WINDOW_DRAW_COUNTS[index] ||
    !isNonNegativeInteger(value.source_draw_count) ||
    !isNonNegativeInteger(value.eligible_draw_count) ||
    !isNonNegativeInteger(value.excluded_draw_count) ||
    !isNonNegativeInteger(value.success_count) ||
    !isNonNegativeInteger(value.failure_count) ||
    !isExactRate(value.success_rate) ||
    !isDrawIdentity(value.first_target) ||
    !isDrawIdentity(value.last_target) ||
    !isDrawIdentity(value.first_cutoff) ||
    !isDrawIdentity(value.last_cutoff) ||
    typeof value.nested_windows_independent !== 'boolean' ||
    !isString(value.evaluation_status) ||
    !EVALUATION_STATUSES.has(value.evaluation_status) ||
    !isString(value.evidence_status) ||
    !EVIDENCE_STATUSES.has(value.evidence_status)
  ) {
    return false
  }
  const rate = value.success_rate as Record<string, unknown>
  return (
    value.source_draw_count === value.eligible_draw_count + value.excluded_draw_count &&
    value.eligible_draw_count === value.success_count + value.failure_count &&
    rate.numerator === value.success_count &&
    rate.denominator === value.eligible_draw_count
  )
}

function isSuccessResult(
  value: unknown,
  expected: Pick<
    HistoricalSuccessExactQuery,
    'strategy_id' | 'strategy_version' | 'replicate' | 'prefix_count' | 'criterion'
  > | null,
): value is HistoricalSuccessWindowResult {
  const returnedCriterion =
    isRecord(value) &&
    isRecord(value.criterion) &&
    isString(value.criterion.criterion) &&
    CRITERION_SET.has(value.criterion.criterion)
      ? (value.criterion.criterion as HistoricalSuccessCriterion)
      : null
  if (
    !isRecord(value) ||
    !isStrategyIdentity(value.strategy) ||
    returnedCriterion === null ||
    !isCriterion(value.criterion, expected?.criterion ?? returnedCriterion) ||
    !PREFIX_COUNT_SET.has(value.prefix_count as number) ||
    !isRecord(value.selection) ||
    !isNonBlankString(value.selection.lottery) ||
    !isNonBlankString(value.selection.strategy_id) ||
    !isNonBlankString(value.selection.strategy_version) ||
    !isPositiveInteger(value.selection.replicate) ||
    value.selection.ticket_count !== value.prefix_count ||
    value.selection.max_bet_index !== value.prefix_count ||
    !isNonBlankString(value.status) ||
    !isNonNegativeInteger(value.source_observation_count) ||
    !Array.isArray(value.windows)
  ) {
    return false
  }
  const strategy = value.strategy as Record<string, unknown>
  if (
    value.selection.strategy_id !== strategy.strategy_id ||
    value.selection.strategy_version !== strategy.strategy_version ||
    value.selection.replicate !== strategy.replicate
  ) {
    return false
  }
  if (expected !== null) {
    if (
      strategy.strategy_id !== expected.strategy_id ||
      strategy.strategy_version !== expected.strategy_version ||
      strategy.replicate !== expected.replicate ||
      value.prefix_count !== expected.prefix_count
    ) {
      return false
    }
  }
  if (value.source_observation_count === 0) {
    return value.status === 'NO_OBSERVATIONS' && value.windows.length === 0
  }
  return value.windows.length === 4 && value.windows.every(isWindow)
}

function isMetadata(value: unknown, importIdentity: string): boolean {
  return (
    isRecord(value) &&
    isNonBlankString(value.run_id) &&
    isNonBlankString(value.contract_version) &&
    value.import_identity_sha256 === importIdentity &&
    isNonBlankString(value.source_kind) &&
    isNonBlankString(value.source_repository) &&
    isNonBlankString(value.source_commit_oid) &&
    isSha256(value.source_artifact_sha256) &&
    isNonBlankString(value.dataset_identity) &&
    isSha256(value.dataset_sha256) &&
    isNonBlankString(value.lottery_type)
  )
}

function exactRateEquals(left: unknown, right: unknown): boolean {
  return (
    isRecord(left) &&
    isRecord(right) &&
    left.numerator === right.numerator &&
    left.denominator === right.denominator &&
    left.available === right.available
  )
}

function greatestCommonDivisor(left: number, right: number): number {
  let a = Math.abs(left)
  let b = Math.abs(right)
  while (b !== 0) {
    const remainder = a % b
    a = b
    b = remainder
  }
  return a
}

function expectedSignedDelta(
  fromRate: Record<string, unknown>,
  toRate: Record<string, unknown>,
): readonly [number, number, boolean, string] | null {
  if (fromRate.available === false || toRate.available === false) {
    return [0, 0, false, 'UNAVAILABLE']
  }
  if (
    !isNonNegativeInteger(fromRate.numerator) ||
    !isPositiveInteger(fromRate.denominator) ||
    !isNonNegativeInteger(toRate.numerator) ||
    !isPositiveInteger(toRate.denominator)
  ) {
    return null
  }
  const numerator =
    toRate.numerator * fromRate.denominator -
    fromRate.numerator * toRate.denominator
  const denominator = toRate.denominator * fromRate.denominator
  if (!Number.isSafeInteger(numerator) || !Number.isSafeInteger(denominator)) return null
  const divisor = greatestCommonDivisor(numerator, denominator)
  const reducedNumerator = numerator / divisor
  const reducedDenominator = reducedNumerator === 0 ? 1 : denominator / divisor
  const relation =
    reducedNumerator > 0 ? 'HIGHER' : reducedNumerator < 0 ? 'LOWER' : 'EQUAL'
  return [reducedNumerator, reducedDenominator, true, relation]
}

function isMatrixComparison(
  value: unknown,
  index: number,
  windows: unknown[],
): boolean {
  const definition = COMPARISON_DEFINITIONS[index]
  if (definition === undefined || !isRecord(value)) return false
  const [comparisonKind, fromIndex, toIndex] = definition
  const fromWindow = windows[fromIndex]
  const toWindow = windows[toIndex]
  if (
    !isRecord(fromWindow) ||
    !isRecord(toWindow) ||
    !isRecord(fromWindow.success_rate) ||
    !isRecord(toWindow.success_rate) ||
    value.comparison_kind !== comparisonKind ||
    value.from_window_kind !== WINDOW_KINDS[fromIndex] ||
    value.to_window_kind !== WINDOW_KINDS[toIndex] ||
    !exactRateEquals(value.from_rate, fromWindow.success_rate) ||
    !exactRateEquals(value.to_rate, toWindow.success_rate) ||
    !isRecord(value.delta)
  ) {
    return false
  }
  const expected = expectedSignedDelta(fromWindow.success_rate, toWindow.success_rate)
  if (expected === null) return false
  const [numerator, denominator, available, relation] = expected
  return (
    value.delta.numerator === numerator &&
    value.delta.denominator === denominator &&
    value.delta.available === available &&
    value.relation === relation
  )
}

function isMatrixCell(
  value: unknown,
  expectedCriterion: HistoricalSuccessCriterion,
  expectedPrefix: HistoricalSuccessPrefixCount,
  expectedStrategy: Record<string, unknown>,
  sourceObservationCount: number,
): boolean {
  if (
    !isRecord(value) ||
    !isCriterion(value.criterion, expectedCriterion) ||
    value.prefix_count !== expectedPrefix ||
    !isRecord(value.selection) ||
    value.selection.lottery !== 'BIG_LOTTO' ||
    value.selection.strategy_id !== expectedStrategy.strategy_id ||
    value.selection.strategy_version !== expectedStrategy.strategy_version ||
    value.selection.replicate !== expectedStrategy.replicate ||
    value.selection.ticket_count !== expectedPrefix ||
    value.selection.max_bet_index !== expectedPrefix ||
    value.source_observation_count !== sourceObservationCount ||
    !Array.isArray(value.windows) ||
    !Array.isArray(value.comparisons)
  ) {
    return false
  }
  const windows = value.windows
  const comparisons = value.comparisons
  if (sourceObservationCount === 0) {
    return (
      value.status === 'NO_OBSERVATIONS' &&
      windows.length === 0 &&
      comparisons.length === 0
    )
  }
  return (
    value.status === 'EVALUATED' &&
    windows.length === 4 &&
    windows.every(isWindow) &&
    comparisons.length === 4 &&
    comparisons.every((item, index) =>
      isMatrixComparison(item, index, windows),
    )
  )
}

function isStabilityMatrix(
  value: unknown,
  query: HistoricalSuccessMatrixQuery,
): value is HistoricalSuccessStabilityMatrix {
  if (
    !isRecord(value) ||
    !isMetadata(value.metadata, query.import_identity_sha256) ||
    !isStrategyIdentity(value.strategy) ||
    !isNonNegativeInteger(value.source_observation_count) ||
    !Array.isArray(value.prefix_counts) ||
    !Array.isArray(value.criteria) ||
    value.cell_count !== 64 ||
    !Array.isArray(value.cells) ||
    value.cells.length !== 64
  ) {
    return false
  }
  const strategy = value.strategy as Record<string, unknown>
  const sourceObservationCount = value.source_observation_count
  if (
    strategy.strategy_id !== query.strategy_id ||
    strategy.strategy_version !== query.strategy_version ||
    strategy.replicate !== query.replicate ||
    value.prefix_counts.length !== HISTORICAL_SUCCESS_PREFIX_COUNTS.length ||
    !value.prefix_counts.every(
      (prefix, index) => prefix === HISTORICAL_SUCCESS_PREFIX_COUNTS[index],
    ) ||
    value.criteria.length !== HISTORICAL_SUCCESS_CRITERIA.length ||
    !value.criteria.every((item, index) => {
      const expected = HISTORICAL_SUCCESS_CRITERIA[index]
      return expected !== undefined && isCriterion(item, expected)
    })
  ) {
    return false
  }
  const seen = new Set<string>()
  return value.cells.every((cell, index) => {
    const criterionIndex = Math.floor(index / HISTORICAL_SUCCESS_PREFIX_COUNTS.length)
    const prefixIndex = index % HISTORICAL_SUCCESS_PREFIX_COUNTS.length
    const expectedCriterion = HISTORICAL_SUCCESS_CRITERIA[criterionIndex]
    const expectedPrefix = HISTORICAL_SUCCESS_PREFIX_COUNTS[prefixIndex]
    if (expectedCriterion === undefined || expectedPrefix === undefined) return false
    const key = `${expectedCriterion}:${expectedPrefix}`
    if (seen.has(key)) return false
    seen.add(key)
    return isMatrixCell(
      cell,
      expectedCriterion,
      expectedPrefix,
      strategy,
      sourceObservationCount,
    )
  })
}

function isFeatureKey(value: unknown, index: number): boolean {
  if (!isRecord(value)) return false
  const longToMedium =
    HISTORICAL_SUCCESS_FEATURE_RELATIONS[Math.floor(index / 16)]
  const mediumToShort =
    HISTORICAL_SUCCESS_FEATURE_RELATIONS[Math.floor((index % 16) / 4)]
  const longToShort = HISTORICAL_SUCCESS_FEATURE_RELATIONS[index % 4]
  return (
    longToMedium !== undefined &&
    mediumToShort !== undefined &&
    longToShort !== undefined &&
    value.long_to_medium === longToMedium &&
    value.medium_to_short === mediumToShort &&
    value.long_to_short === longToShort
  )
}

function isFeatureCohort(
  value: unknown,
  index: number,
  baselineRate: Record<string, unknown>,
): boolean {
  if (
    !isRecord(value) ||
    !isFeatureKey(value.feature_key, index) ||
    !isNonNegativeInteger(value.observation_count) ||
    !isNonNegativeInteger(value.success_count) ||
    !isNonNegativeInteger(value.failure_count) ||
    !isExactRate(value.success_rate) ||
    !isRecord(value.success_rate) ||
    !isRecord(value.delta_vs_baseline)
  ) {
    return false
  }
  if (
    value.success_count + value.failure_count !== value.observation_count
  ) {
    return false
  }
  const rate = value.success_rate
  if (value.observation_count === 0) {
    return (
      value.success_count === 0 &&
      value.failure_count === 0 &&
      rate.numerator === 0 &&
      rate.denominator === 0 &&
      rate.available === false &&
      value.delta_vs_baseline.numerator === 0 &&
      value.delta_vs_baseline.denominator === 0 &&
      value.delta_vs_baseline.available === false &&
      value.relation_vs_baseline === 'UNAVAILABLE' &&
      value.first_target === null &&
      value.last_target === null
    )
  }
  if (
    rate.numerator !== value.success_count ||
    rate.denominator !== value.observation_count ||
    rate.available !== true ||
    !isDrawIdentity(value.first_target) ||
    !isDrawIdentity(value.last_target)
  ) {
    return false
  }
  const expected = expectedSignedDelta(baselineRate, rate)
  if (expected === null) return false
  const [numerator, denominator, available, relation] = expected
  return (
    value.delta_vs_baseline.numerator === numerator &&
    value.delta_vs_baseline.denominator === denominator &&
    value.delta_vs_baseline.available === available &&
    value.relation_vs_baseline === relation
  )
}

function isFeatureCohorts(
  value: unknown,
  query: HistoricalSuccessFeatureCohortQuery,
): value is HistoricalSuccessFeatureCohorts {
  if (
    !isRecord(value) ||
    !isMetadata(value.metadata, query.import_identity_sha256) ||
    !isStrategyIdentity(value.strategy) ||
    !isCriterion(value.criterion, query.criterion) ||
    value.prefix_count !== query.prefix_count ||
    !isRecord(value.baseline) ||
    !isNonNegativeInteger(value.baseline.observation_count) ||
    !isNonNegativeInteger(value.baseline.success_count) ||
    !isNonNegativeInteger(value.baseline.failure_count) ||
    !isExactRate(value.baseline.success_rate) ||
    !isRecord(value.baseline.success_rate) ||
    value.cohort_count !== 64 ||
    !Array.isArray(value.cohorts) ||
    value.cohorts.length !== 64
  ) {
    return false
  }
  const strategy = value.strategy as Record<string, unknown>
  const baseline = value.baseline as Record<string, unknown> & {
    observation_count: number
    success_count: number
    failure_count: number
    success_rate: Record<string, unknown> & {
      numerator: number
      denominator: number
      available: boolean
    }
  }
  const baselineRate = baseline.success_rate
  if (
    strategy.strategy_id !== query.strategy_id ||
    strategy.strategy_version !== query.strategy_version ||
    strategy.replicate !== query.replicate ||
    baseline.success_count + baseline.failure_count !==
      baseline.observation_count ||
    baselineRate.numerator !== baseline.success_count ||
    baselineRate.denominator !==
      (baseline.observation_count === 0 ? 0 : baseline.observation_count) ||
    baselineRate.available !== (baseline.observation_count > 0)
  ) {
    return false
  }
  let assigned = 0
  for (const [index, cohort] of value.cohorts.entries()) {
    if (!isFeatureCohort(cohort, index, baselineRate)) return false
    assigned += cohort.observation_count
  }
  return assigned === baseline.observation_count
}

function isSuccessPage(
  value: unknown,
  query: HistoricalSuccessWindowQuery,
): value is HistoricalSuccessWindowPage {
  if (
    !isRecord(value) ||
    !isMetadata(value.metadata, query.import_identity_sha256) ||
    !isCriterion(value.criterion, query.criterion) ||
    value.prefix_count !== query.prefix_count ||
    !isPageShape(value) ||
    !Array.isArray(value.items)
  ) {
    return false
  }
  return (
    value.limit === query.limit &&
    value.offset === query.offset &&
    value.items.length <= value.limit &&
    value.offset + value.items.length <= value.total_count &&
    value.items.every(
      (item) =>
        isSuccessResult(item, null) &&
        item.prefix_count === query.prefix_count &&
        item.criterion.criterion === query.criterion,
    )
  )
}

function errorCodeFromPayload(payload: unknown): string | null {
  return isRecord(payload) && isString(payload.error_code) ? payload.error_code : null
}

function requestError(status: number, payload: unknown): HistoricalSuccessWindowsRequestError {
  const errorCode = errorCodeFromPayload(payload)
  if (status === 503 && errorCode?.endsWith('_NOT_CONFIGURED')) {
    return new HistoricalSuccessWindowsRequestError(
      'Configure LOTTOLAB_HISTORICAL_RESULTS_DB to use this workspace.',
      status,
      'NOT_CONFIGURED',
      errorCode,
    )
  }
  if (status === 503) {
    return new HistoricalSuccessWindowsRequestError(
      'The configured Historical Results database is unavailable.',
      status,
      'UNAVAILABLE',
      errorCode,
    )
  }
  if (status === 404) {
    return new HistoricalSuccessWindowsRequestError(
      'The exact historical source or strategy no longer exists.',
      status,
      'NOT_FOUND',
      errorCode,
    )
  }
  if (status === 422) {
    return new HistoricalSuccessWindowsRequestError(
      'The server rejected the exact historical selection.',
      status,
      'INVALID_REQUEST',
      errorCode,
    )
  }
  return new HistoricalSuccessWindowsRequestError(
    'The historical research request failed.',
    status,
    'UNAVAILABLE',
    errorCode,
  )
}

async function fetchPayload(url: string, signal?: AbortSignal): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error: unknown) {
    if (signal?.aborted) throw error
    throw new HistoricalSuccessWindowsRequestError(
      'The historical research request failed before receiving a response.',
      0,
      'NETWORK',
    )
  }
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new HistoricalSuccessWindowsRequestError(
      'The backend returned an invalid historical response.',
      502,
      'MALFORMED_RESPONSE',
    )
  }
  if (!response.ok) throw requestError(response.status, payload)
  return payload
}

function malformedResponse(): HistoricalSuccessWindowsRequestError {
  return new HistoricalSuccessWindowsRequestError(
    'The backend returned an invalid historical response.',
    502,
    'MALFORMED_RESPONSE',
  )
}

export async function listHistoricalRuns(
  query: HistoricalRunQuery,
  signal?: AbortSignal,
): Promise<HistoricalRunPage> {
  const parameters = new URLSearchParams()
  parameters.set('limit', String(query.limit))
  parameters.set('offset', String(query.offset))
  const payload = await fetchPayload(`${RUNS_ENDPOINT}?${parameters.toString()}`, signal)
  if (
    !isHistoricalRunPage(payload) ||
    payload.limit !== query.limit ||
    payload.offset !== query.offset
  ) {
    throw malformedResponse()
  }
  return payload
}

function successQueryParameters(
  query: Pick<
    HistoricalSuccessWindowQuery,
    'import_identity_sha256' | 'prefix_count' | 'criterion'
  >,
): URLSearchParams {
  const parameters = new URLSearchParams()
  parameters.set('import_identity_sha256', query.import_identity_sha256)
  parameters.set('prefix_count', String(query.prefix_count))
  parameters.set('criterion', query.criterion)
  return parameters
}

export async function listHistoricalSuccessWindows(
  query: HistoricalSuccessWindowQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessWindowPage> {
  const parameters = successQueryParameters(query)
  parameters.set('limit', String(query.limit))
  parameters.set('offset', String(query.offset))
  const payload = await fetchPayload(`${WINDOWS_ENDPOINT}?${parameters.toString()}`, signal)
  if (!isSuccessPage(payload, query)) throw malformedResponse()
  return payload
}

export async function getHistoricalSuccessWindows(
  query: HistoricalSuccessExactQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessWindowResult> {
  const parameters = successQueryParameters(query)
  const identity = [query.strategy_id, query.strategy_version, String(query.replicate)]
    .map((part) => encodeURIComponent(part))
    .join('/')
  const payload = await fetchPayload(
    `${WINDOWS_ENDPOINT}/strategies/${identity}?${parameters.toString()}`,
    signal,
  )
  if (!isSuccessResult(payload, query)) throw malformedResponse()
  return payload
}

export async function getHistoricalSuccessStabilityMatrix(
  query: HistoricalSuccessMatrixQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessStabilityMatrix> {
  const parameters = new URLSearchParams()
  parameters.set('import_identity_sha256', query.import_identity_sha256)
  const identity = [query.strategy_id, query.strategy_version, String(query.replicate)]
    .map((part) => encodeURIComponent(part))
    .join('/')
  const payload = await fetchPayload(
    `${WINDOWS_ENDPOINT}/strategies/${identity}/matrix?${parameters.toString()}`,
    signal,
  )
  if (!isStabilityMatrix(payload, query)) throw malformedResponse()
  return payload
}

export async function getHistoricalSuccessFeatureCohorts(
  query: HistoricalSuccessFeatureCohortQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessFeatureCohorts> {
  const parameters = successQueryParameters(query)
  const identity = [query.strategy_id, query.strategy_version, String(query.replicate)]
    .map((part) => encodeURIComponent(part))
    .join('/')
  const payload = await fetchPayload(
    `${WINDOWS_ENDPOINT}/strategies/${identity}/feature-cohorts?${parameters.toString()}`,
    signal,
  )
  if (!isFeatureCohorts(payload, query)) throw malformedResponse()
  return payload
}
