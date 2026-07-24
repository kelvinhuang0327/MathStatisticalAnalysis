import type { components, paths } from './generated/openapi'

export type HistoricalRunPage =
  paths['/api/v1/historical-results/runs']['get']['responses'][200]['content']['application/json']
export type HistoricalRun = HistoricalRunPage['items'][number]
export type HistoricalSuccessWindowPage =
  paths['/api/v1/historical-prefix-success-windows']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessWindowResult = HistoricalSuccessWindowPage['items'][number]
export type HistoricalSuccessStabilityMatrix =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/matrix']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessRandomBaseline =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/random-null-baseline']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessFeatureCohorts =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessFeatureCohortDiagnostics =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/diagnostics']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessTemporalHoldout =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/temporal-holdout']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessRecent50StabilityAudit =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/recent-50-stability-audit']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessCrossImportConcordance =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/cross-import-concordance']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessMultiImportConcordanceCensus =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/multi-import-concordance-census']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessResearchQualification =
  paths['/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/research-qualification']['get']['responses'][200]['content']['application/json']
export type HistoricalSuccessPrefixCount =
  components['schemas']['HistoricalPrefixSuccessPrefixCount']
export type HistoricalSuccessCriterion =
  components['schemas']['HistoricalPrefixSuccessCriterion']
export type HistoricalSuccessWindowKind = components['schemas']['WindowKind']

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
export const HISTORICAL_SUCCESS_WINDOW_KINDS = [
  'FULL_HISTORY',
  'LONG',
  'MEDIUM',
  'SHORT',
] as const satisfies readonly HistoricalSuccessWindowKind[]

const RUNS_ENDPOINT = '/api/v1/historical-results/runs'
const WINDOWS_ENDPOINT = '/api/v1/historical-prefix-success-windows'
const SHA256_PATTERN = /^[0-9a-f]{64}$/
const RANDOM_BASELINE_POLICY_VERSION =
  'HISTORICAL_SUCCESS_RANDOM_NULL_BASELINE_R1_OFFICIAL_SIX_NUMBER_IID'
const RANDOM_BASELINE_WINDOW_POLICY_VERSION = 'STRATEGY_SUCCESS_WINDOWS_V1'
const RANDOM_BASELINE_SAMPLING_POLICY =
  'UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT'
const RANDOM_BASELINE_TICKET_INTERPRETATION =
  'nominal-ticket-count equivalent'
const RANDOM_BASELINE_LEGAL_TICKET_COUNT = '13983816'
export const HISTORICAL_SUCCESS_RANDOM_BASELINE_CAVEAT =
  'Descriptive official-six-number IID random benchmark only. This result does not establish statistical significance, ranking, promotion, rejection, prediction quality, production eligibility, or monetary cost equivalence.'
const RANDOM_BASELINE_SUCCESS_TICKET_COUNTS = {
  M3_PLUS: '260624',
  M4_PLUS: '13804',
  M5_PLUS: '259',
  M6: '1',
  M2_PLUS_SPECIAL: '190056',
  M3_PLUS_SPECIAL: '17856',
  M4_PLUS_SPECIAL: '636',
  M5_PLUS_SPECIAL: '6',
} as const satisfies Record<HistoricalSuccessCriterion, string>
const RANDOM_BASELINE_NOT_READY_REASONS = [
  'NO_OBSERVATIONS',
  'WINDOW_INCOMPLETE',
  'EXCLUDED_OBSERVATIONS',
  'SOURCE_TICKET_SEMANTICS_CONFLICT',
  'EXACT_COMPUTATION_UNAVAILABLE',
] as const
const PREFIX_COUNT_SET = new Set<number>(HISTORICAL_SUCCESS_PREFIX_COUNTS)
const CRITERION_SET = new Set<string>(HISTORICAL_SUCCESS_CRITERIA)
const WINDOW_KINDS = HISTORICAL_SUCCESS_WINDOW_KINDS
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

export interface HistoricalSuccessRandomBaselineQuery
  extends HistoricalSuccessExactQuery {
  window_kind: HistoricalSuccessWindowKind
}

export interface HistoricalSuccessFeatureCohortQuery
  extends HistoricalSuccessExactQuery {}

export interface HistoricalSuccessFeatureCohortDiagnosticsQuery
  extends HistoricalSuccessExactQuery {}

export interface HistoricalSuccessTemporalHoldoutQuery
  extends HistoricalSuccessExactQuery {}

export interface HistoricalSuccessRecent50StabilityAuditQuery
  extends HistoricalSuccessExactQuery {}

export interface HistoricalSuccessCrossImportConcordanceQuery {
  left_import_identity_sha256: string
  right_import_identity_sha256: string
  strategy_id: string
  strategy_version: string
  replicate: number
  prefix_count: HistoricalSuccessPrefixCount
  criterion: HistoricalSuccessCriterion
}

export interface HistoricalSuccessMultiImportConcordanceCensusQuery {
  import_identity_sha256: readonly string[]
  strategy_id: string
  strategy_version: string
  replicate: number
  prefix_count: HistoricalSuccessPrefixCount
  criterion: HistoricalSuccessCriterion
}

export interface HistoricalSuccessResearchQualificationQuery {
  import_identity_sha256: readonly string[]
  strategy_id: string
  strategy_version: string
  replicate: number
  prefix_count: HistoricalSuccessPrefixCount
  criterion: HistoricalSuccessCriterion
}

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

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const keys = Object.keys(value)
  return (
    keys.length === expected.length &&
    expected.every((key) => Object.hasOwn(value, key))
  )
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

const CANONICAL_UNSIGNED_DECIMAL = /^(?:0|[1-9][0-9]*)$/
const EXACT_DECIMAL_18 = /^(?:0|[1-9][0-9]*)\.[0-9]{18}$/

function greatestCommonDivisorBigInt(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) {
    const remainder = a % b
    a = b
    b = remainder
  }
  return a
}

function renderExactDecimal18(numerator: bigint, denominator: bigint): string {
  const scale = 10n ** 18n
  const scaled = numerator * scale
  const quotient = scaled / denominator
  const remainder = scaled % denominator
  const doubled = remainder * 2n
  const rounded =
    quotient +
    (doubled > denominator ||
    (doubled === denominator && quotient % 2n === 1n)
      ? 1n
      : 0n)
  const integerPart = rounded / scale
  const fractionalPart = String(rounded % scale).padStart(18, '0')
  return `${integerPart}.${fractionalPart}`
}

function isRandomBaselineExactRational(
  value: unknown,
  probability: boolean,
): value is Record<string, string> {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ['numerator', 'denominator', 'decimal_18']) ||
    !isString(value.numerator) ||
    !isString(value.denominator) ||
    !isString(value.decimal_18) ||
    !CANONICAL_UNSIGNED_DECIMAL.test(value.numerator) ||
    !/^[1-9][0-9]*$/.test(value.denominator) ||
    !EXACT_DECIMAL_18.test(value.decimal_18)
  ) {
    return false
  }
  const numerator = BigInt(value.numerator)
  const denominator = BigInt(value.denominator)
  return (
    (!probability || numerator <= denominator) &&
    greatestCommonDivisorBigInt(numerator, denominator) === 1n &&
    value.decimal_18 === renderExactDecimal18(numerator, denominator)
  )
}

function exactRationalEquals(
  value: Record<string, string>,
  numerator: bigint,
  denominator: bigint,
): boolean {
  const divisor = greatestCommonDivisorBigInt(numerator, denominator)
  return (
    BigInt(value.numerator) === numerator / divisor &&
    BigInt(value.denominator) === denominator / divisor
  )
}

function exactBinomialUpperTailEquals(
  value: Record<string, string>,
  observationCount: number,
  observedSuccessCount: number,
  probability: Record<string, string>,
): boolean {
  const success = BigInt(probability.numerator)
  const total = BigInt(probability.denominator)
  const failure = total - success
  if (observedSuccessCount === 0 || failure === 0n) {
    return exactRationalEquals(value, 1n, 1n)
  }
  if (success === 0n) return exactRationalEquals(value, 0n, 1n)

  const denominator = total ** BigInt(observationCount)
  const lowerTermCount = observedSuccessCount
  const upperTermCount = observationCount - observedSuccessCount + 1
  let numerator: bigint
  if (upperTermCount <= lowerTermCount) {
    let successes = observationCount
    let term = success ** BigInt(observationCount)
    let upper = term
    while (successes > observedSuccessCount) {
      term =
        (term * BigInt(successes) * failure) /
        (BigInt(observationCount - successes + 1) * success)
      successes -= 1
      upper += term
    }
    numerator = upper
  } else {
    let successes = 0
    let term = failure ** BigInt(observationCount)
    let lower = term
    while (successes + 1 < observedSuccessCount) {
      term =
        (term * BigInt(observationCount - successes) * success) /
        (BigInt(successes + 1) * failure)
      successes += 1
      lower += term
    }
    numerator = denominator - lower
  }
  return (
    BigInt(value.numerator) * denominator ===
    numerator * BigInt(value.denominator)
  )
}

function isRandomBaselineCell(
  value: unknown,
  query: HistoricalSuccessRandomBaselineQuery,
): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      'policy_version',
      'import_identity_sha256',
      'dataset_sha256',
      'source_artifact_sha256',
      'strategy_id',
      'strategy_version',
      'replicate',
      'window_kind',
      'window_policy_version',
      'prefix_count',
      'criterion',
    ]) &&
    value.policy_version === RANDOM_BASELINE_POLICY_VERSION &&
    value.import_identity_sha256 === query.import_identity_sha256 &&
    isSha256(value.dataset_sha256) &&
    isSha256(value.source_artifact_sha256) &&
    value.strategy_id === query.strategy_id &&
    value.strategy_version === query.strategy_version &&
    value.replicate === query.replicate &&
    value.window_kind === query.window_kind &&
    value.window_policy_version === RANDOM_BASELINE_WINDOW_POLICY_VERSION &&
    value.prefix_count === query.prefix_count &&
    value.criterion === query.criterion
  )
}

function isRandomBaselineResponse(
  value: unknown,
  query: HistoricalSuccessRandomBaselineQuery,
): value is HistoricalSuccessRandomBaseline {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      'cell',
      'readiness',
      'reason_codes',
      'sampling_policy',
      'ticket_count_interpretation',
      'legal_ticket_count',
      'success_ticket_count',
      'portfolio_success_probability',
      'eligible_observation_count',
      'excluded_observation_count',
      'observed_success_count',
      'expected_successes',
      'upper_tail_probability',
      'observed_ticket_position_count',
      'observed_distinct_ticket_count',
      'observed_duplicate_ticket_count',
      'observation_count_with_duplicates',
      'interpretation_caveat',
    ]) ||
    !isRandomBaselineCell(value.cell, query) ||
    (value.readiness !== 'READY' && value.readiness !== 'NOT_READY') ||
    !Array.isArray(value.reason_codes) ||
    !value.reason_codes.every(
      (reason) =>
        typeof reason === 'string' &&
        RANDOM_BASELINE_NOT_READY_REASONS.includes(
          reason as (typeof RANDOM_BASELINE_NOT_READY_REASONS)[number],
        ),
    ) ||
    value.reason_codes.some(
      (reason, index) =>
        reason !==
        RANDOM_BASELINE_NOT_READY_REASONS.filter((candidate) =>
          (value.reason_codes as unknown[]).includes(candidate),
        )[index],
    ) ||
    value.sampling_policy !== RANDOM_BASELINE_SAMPLING_POLICY ||
    value.ticket_count_interpretation !==
      RANDOM_BASELINE_TICKET_INTERPRETATION ||
    value.legal_ticket_count !== RANDOM_BASELINE_LEGAL_TICKET_COUNT ||
    value.success_ticket_count !==
      RANDOM_BASELINE_SUCCESS_TICKET_COUNTS[query.criterion] ||
    !isRandomBaselineExactRational(
      value.portfolio_success_probability,
      true,
    ) ||
    !isNonNegativeInteger(value.eligible_observation_count) ||
    !isNonNegativeInteger(value.excluded_observation_count) ||
    !isNonNegativeInteger(value.observed_ticket_position_count) ||
    !isNonNegativeInteger(value.observed_distinct_ticket_count) ||
    !isNonNegativeInteger(value.observed_duplicate_ticket_count) ||
    !isNonNegativeInteger(value.observation_count_with_duplicates) ||
    value.observed_ticket_position_count !==
      value.observed_distinct_ticket_count +
        value.observed_duplicate_ticket_count ||
    value.observation_count_with_duplicates >
      value.eligible_observation_count ||
    value.interpretation_caveat !==
      HISTORICAL_SUCCESS_RANDOM_BASELINE_CAVEAT
  ) {
    return false
  }

  const legal = BigInt(RANDOM_BASELINE_LEGAL_TICKET_COUNT)
  const success = BigInt(
    RANDOM_BASELINE_SUCCESS_TICKET_COUNTS[query.criterion],
  )
  const denominator = legal ** BigInt(query.prefix_count)
  const numerator =
    denominator - (legal - success) ** BigInt(query.prefix_count)
  if (
    !exactRationalEquals(
      value.portfolio_success_probability,
      numerator,
      denominator,
    )
  ) {
    return false
  }

  if (value.readiness === 'NOT_READY') {
    return (
      value.reason_codes.length > 0 &&
      value.observed_success_count === null &&
      value.expected_successes === null &&
      value.upper_tail_probability === null
    )
  }
  if (
    value.reason_codes.length !== 0 ||
    value.eligible_observation_count === 0 ||
    value.excluded_observation_count !== 0 ||
    !isNonNegativeInteger(value.observed_success_count) ||
    value.observed_success_count > value.eligible_observation_count ||
    !isRandomBaselineExactRational(value.expected_successes, false) ||
    !isRandomBaselineExactRational(value.upper_tail_probability, true) ||
    value.observed_ticket_position_count !==
      value.eligible_observation_count * query.prefix_count
  ) {
    return false
  }
  return (
    exactRationalEquals(
      value.expected_successes,
      BigInt(value.eligible_observation_count) * numerator,
      denominator,
    ) &&
    exactBinomialUpperTailEquals(
      value.upper_tail_probability,
      value.eligible_observation_count,
      value.observed_success_count,
      value.portfolio_success_probability,
    )
  )
}

function isExactProbability(value: unknown): boolean {
  if (
    !isRecord(value) ||
    !isString(value.numerator) ||
    !isString(value.denominator) ||
    !CANONICAL_UNSIGNED_DECIMAL.test(value.numerator) ||
    !CANONICAL_UNSIGNED_DECIMAL.test(value.denominator)
  ) {
    return false
  }
  const numerator = BigInt(value.numerator)
  const denominator = BigInt(value.denominator)
  return (
    denominator > 0n &&
    numerator <= denominator &&
    greatestCommonDivisorBigInt(numerator, denominator) === 1n
  )
}

function compareExactProbabilities(
  left: Record<string, unknown>,
  right: Record<string, unknown>,
): number {
  const leftNumerator = BigInt(left.numerator as string)
  const leftDenominator = BigInt(left.denominator as string)
  const rightNumerator = BigInt(right.numerator as string)
  const rightDenominator = BigInt(right.denominator as string)
  const difference =
    leftNumerator * rightDenominator - rightNumerator * leftDenominator
  return difference < 0n ? -1 : difference > 0n ? 1 : 0
}

function isOutcomeCounts(value: unknown): value is Record<string, number> {
  return (
    isRecord(value) &&
    isNonNegativeInteger(value.observation_count) &&
    isNonNegativeInteger(value.success_count) &&
    isNonNegativeInteger(value.failure_count) &&
    value.success_count + value.failure_count === value.observation_count
  )
}

function expectedDiagnosticStatus(
  cohort: Record<string, number>,
  outside: Record<string, number>,
): string {
  if (cohort.observation_count === 0) return 'NOT_TESTABLE_EMPTY_COHORT'
  if (outside.observation_count === 0) return 'NOT_TESTABLE_EMPTY_COMPLEMENT'
  const successes = cohort.success_count + outside.success_count
  const observations = cohort.observation_count + outside.observation_count
  return successes === 0 || successes === observations
    ? 'NOT_TESTABLE_NO_OUTCOME_VARIATION'
    : 'TESTED'
}

function isDiagnosticRate(
  value: unknown,
  counts: Record<string, number>,
): value is Record<string, unknown> {
  return (
    isExactRate(value) &&
    isRecord(value) &&
    value.numerator === counts.success_count &&
    value.denominator ===
      (counts.observation_count === 0 ? 0 : counts.observation_count) &&
    value.available === (counts.observation_count > 0)
  )
}

function isFeatureCohortDiagnostic(
  value: unknown,
  index: number,
  baseline: Record<string, number>,
): boolean {
  if (
    !isRecord(value) ||
    value.cohort_index !== index ||
    !isFeatureKey(value.feature_key, index) ||
    !isOutcomeCounts(value.cohort_counts) ||
    !isOutcomeCounts(value.outside_counts) ||
    !isRecord(value.risk_difference) ||
    !isExactProbability(value.raw_p_value) ||
    !isExactProbability(value.adjusted_p_value)
  ) {
    return false
  }
  const cohort = value.cohort_counts
  const outside = value.outside_counts
  if (
    cohort.observation_count + outside.observation_count !==
      baseline.observation_count ||
    cohort.success_count + outside.success_count !== baseline.success_count ||
    cohort.failure_count + outside.failure_count !== baseline.failure_count ||
    !isDiagnosticRate(value.cohort_success_rate, cohort) ||
    !isDiagnosticRate(value.outside_success_rate, outside)
  ) {
    return false
  }
  const expectedStatus = expectedDiagnosticStatus(cohort, outside)
  if (value.test_status !== expectedStatus) return false
  const expectedEffect = expectedSignedDelta(
    value.outside_success_rate as Record<string, unknown>,
    value.cohort_success_rate as Record<string, unknown>,
  )
  if (expectedEffect === null) return false
  const [numerator, denominator, available, relation] = expectedEffect
  const raw = value.raw_p_value as Record<string, unknown>
  const adjusted = value.adjusted_p_value as Record<string, unknown>
  return (
    value.risk_difference.numerator === numerator &&
    value.risk_difference.denominator === denominator &&
    value.risk_difference.available === available &&
    value.relation_vs_outside === relation &&
    (expectedStatus === 'TESTED' ||
      (raw.numerator === '1' && raw.denominator === '1')) &&
    compareExactProbabilities(raw, adjusted) <= 0 &&
    (cohort.observation_count === 0
      ? value.first_target === null && value.last_target === null
      : isDrawIdentity(value.first_target) && isDrawIdentity(value.last_target))
  )
}

function isFeatureCohortDiagnostics(
  value: unknown,
  query: HistoricalSuccessFeatureCohortDiagnosticsQuery,
): value is HistoricalSuccessFeatureCohortDiagnostics {
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
    value.family_size !== 64 ||
    value.raw_test_method !== 'FISHER_EXACT_TWO_SIDED_PROBABILITY_ORDERING' ||
    value.adjustment_method !== 'BENJAMINI_YEKUTIELI' ||
    !Array.isArray(value.diagnostics) ||
    value.diagnostics.length !== 64
  ) {
    return false
  }
  const strategy = value.strategy as Record<string, unknown>
  const baseline = value.baseline as Record<string, number>
  const baselineRate = value.baseline.success_rate as Record<string, unknown>
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
  for (const [index, diagnostic] of value.diagnostics.entries()) {
    if (!isFeatureCohortDiagnostic(diagnostic, index, baseline)) return false
    assigned += diagnostic.cohort_counts.observation_count
  }
  if (assigned !== baseline.observation_count) return false
  const sorted = [...value.diagnostics].sort((left, right) => {
    const comparison = compareExactProbabilities(
      left.raw_p_value as Record<string, unknown>,
      right.raw_p_value as Record<string, unknown>,
    )
    return comparison === 0 ? left.cohort_index - right.cohort_index : comparison
  })
  return sorted.every(
    (diagnostic, index) =>
      index === 0 ||
      compareExactProbabilities(
        sorted[index - 1]!.adjusted_p_value as Record<string, unknown>,
        diagnostic.adjusted_p_value as Record<string, unknown>,
      ) <= 0,
  )
}

function isExactEffectChange(
  value: unknown,
  discovery: Record<string, unknown>,
  confirmation: Record<string, unknown>,
): boolean {
  if (
    !isRecord(value) ||
    !Number.isSafeInteger(value.numerator) ||
    !Number.isSafeInteger(value.denominator) ||
    typeof value.available !== 'boolean'
  ) {
    return false
  }
  if (discovery.available !== true || confirmation.available !== true) {
    return value.numerator === 0 && value.denominator === 0 && value.available === false
  }
  if (
    !Number.isSafeInteger(discovery.numerator) ||
    !Number.isSafeInteger(discovery.denominator) ||
    !Number.isSafeInteger(confirmation.numerator) ||
    !Number.isSafeInteger(confirmation.denominator) ||
    (discovery.denominator as number) <= 0 ||
    (confirmation.denominator as number) <= 0
  ) {
    return false
  }
  let expectedNumerator =
    BigInt(confirmation.numerator as number) *
      BigInt(discovery.denominator as number) -
    BigInt(discovery.numerator as number) *
      BigInt(confirmation.denominator as number)
  let expectedDenominator =
    BigInt(confirmation.denominator as number) *
    BigInt(discovery.denominator as number)
  const divisor = greatestCommonDivisorBigInt(expectedNumerator, expectedDenominator)
  expectedNumerator /= divisor
  expectedDenominator /= divisor
  return (
    value.available === true &&
    BigInt(value.numerator as number) === expectedNumerator &&
    BigInt(value.denominator as number) === expectedDenominator
  )
}

function expectedTemporalRelationship(
  discovery: unknown,
  confirmation: unknown,
): string {
  if (discovery === 'UNAVAILABLE' || confirmation === 'UNAVAILABLE') {
    return 'UNAVAILABLE'
  }
  if (discovery !== confirmation) return 'DIFFERENT'
  if (discovery === 'HIGHER') return 'SAME_HIGHER'
  if (discovery === 'EQUAL') return 'SAME_EQUAL'
  return discovery === 'LOWER' ? 'SAME_LOWER' : ''
}

function isTemporalHoldout(
  value: unknown,
  query: HistoricalSuccessTemporalHoldoutQuery,
): value is HistoricalSuccessTemporalHoldout {
  if (
    !isRecord(value) ||
    !isMetadata(value.metadata, query.import_identity_sha256) ||
    !isStrategyIdentity(value.strategy) ||
    !isCriterion(value.criterion, query.criterion) ||
    value.prefix_count !== query.prefix_count ||
    value.family_size !== 64 ||
    !isRecord(value.split) ||
    value.split.split_method !==
      'FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION' ||
    !isNonNegativeInteger(value.split.total_assignment_count) ||
    !isNonNegativeInteger(value.split.warmup_count) ||
    !isNonNegativeInteger(value.split.discovery_count) ||
    !isNonNegativeInteger(value.split.confirmation_count) ||
    !Array.isArray(value.comparisons)
  ) {
    return false
  }
  const strategy = value.strategy as Record<string, unknown>
  const split = value.split as Record<string, unknown> & {
    total_assignment_count: number
    warmup_count: number
    discovery_count: number
    confirmation_count: number
  }
  if (
    strategy.strategy_id !== query.strategy_id ||
    strategy.strategy_version !== query.strategy_version ||
    strategy.replicate !== query.replicate ||
    split.total_assignment_count !==
      split.warmup_count + split.discovery_count + split.confirmation_count
  ) {
    return false
  }
  if (value.evaluation_status === 'NOT_READY_INSUFFICIENT_HISTORY') {
    return (
      split.total_assignment_count < 1050 &&
      split.warmup_count === split.total_assignment_count &&
      split.discovery_count === 0 &&
      split.confirmation_count === 0 &&
      split.discovery_first_target === null &&
      split.discovery_last_target === null &&
      split.confirmation_first_target === null &&
      split.confirmation_last_target === null &&
      value.discovery === null &&
      value.confirmation === null &&
      value.comparisons.length === 0
    )
  }
  if (
    value.evaluation_status !== 'COMPLETE' ||
    split.discovery_count !== 750 ||
    split.confirmation_count !== 300 ||
    !isDrawIdentity(split.discovery_first_target) ||
    !isDrawIdentity(split.discovery_last_target) ||
    !isDrawIdentity(split.confirmation_first_target) ||
    !isDrawIdentity(split.confirmation_last_target) ||
    !isFeatureCohortDiagnostics(value.discovery, query) ||
    !isFeatureCohortDiagnostics(value.confirmation, query) ||
    value.discovery.baseline.observation_count !== 750 ||
    value.confirmation.baseline.observation_count !== 300 ||
    value.comparisons.length !== 64
  ) {
    return false
  }
  const discovery = value.discovery
  const confirmation = value.confirmation
  return value.comparisons.every((comparison, index) => {
    if (
      !isRecord(comparison) ||
      comparison.cohort_index !== index ||
      !isFeatureKey(comparison.feature_key, index) ||
      !isRecord(comparison.discovery_diagnostic) ||
      !isRecord(comparison.confirmation_diagnostic) ||
      !isRecord(comparison.discovery_diagnostic.risk_difference) ||
      !isRecord(comparison.confirmation_diagnostic.risk_difference) ||
      JSON.stringify(comparison.discovery_diagnostic) !==
        JSON.stringify(discovery.diagnostics[index]) ||
      JSON.stringify(comparison.confirmation_diagnostic) !==
        JSON.stringify(confirmation.diagnostics[index])
    ) {
      return false
    }
    return (
      isExactEffectChange(
        comparison.effect_change,
        comparison.discovery_diagnostic.risk_difference,
        comparison.confirmation_diagnostic.risk_difference,
      ) &&
      comparison.relationship ===
        expectedTemporalRelationship(
          comparison.discovery_diagnostic.relation_vs_outside,
          comparison.confirmation_diagnostic.relation_vs_outside,
        )
    )
  })
}

function compareDrawIdentities(left: unknown, right: unknown): number | null {
  if (!isRecord(left) || !isRecord(right) || !isDrawIdentity(left) || !isDrawIdentity(right)) {
    return null
  }
  const isoDate = /^\d{4}-\d{2}-\d{2}$/
  if (
    !isString(left.draw_date) ||
    !isString(right.draw_date) ||
    !isoDate.test(left.draw_date) ||
    !isoDate.test(right.draw_date)
  ) {
    return null
  }
  const leftParsed = new Date(`${left.draw_date}T00:00:00Z`)
  const rightParsed = new Date(`${right.draw_date}T00:00:00Z`)
  if (
    Number.isNaN(leftParsed.getTime()) ||
    Number.isNaN(rightParsed.getTime()) ||
    leftParsed.toISOString().slice(0, 10) !== left.draw_date ||
    rightParsed.toISOString().slice(0, 10) !== right.draw_date
  ) {
    return null
  }
  if (left.draw_date !== right.draw_date) {
    return left.draw_date < right.draw_date ? -1 : 1
  }
  return (left.draw_number as number) - (right.draw_number as number)
}

function isRecent50StabilityAudit(
  value: unknown,
  query: HistoricalSuccessRecent50StabilityAuditQuery,
): value is HistoricalSuccessRecent50StabilityAudit {
  if (
    !isRecord(value) ||
    !isMetadata(value.metadata, query.import_identity_sha256) ||
    !isStrategyIdentity(value.strategy) ||
    !isCriterion(value.criterion, query.criterion) ||
    value.prefix_count !== query.prefix_count ||
    value.family_size !== 64 ||
    !isRecord(value.split) ||
    value.split.source_temporal_split_method !==
      'FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION' ||
    value.split.audit_split_method !==
      'FIXED_CONFIRMATION_FIRST_250_REFERENCE_LAST_50_RECENT' ||
    !isNonNegativeInteger(value.split.total_assignment_count) ||
    !isNonNegativeInteger(value.split.warmup_count) ||
    !isNonNegativeInteger(value.split.discovery_count) ||
    !isNonNegativeInteger(value.split.confirmation_count) ||
    !isNonNegativeInteger(value.split.reference_count) ||
    !isNonNegativeInteger(value.split.recent_count) ||
    !Array.isArray(value.comparisons)
  ) {
    return false
  }
  const strategy = value.strategy as Record<string, unknown>
  const split = value.split as Record<string, unknown> & {
    total_assignment_count: number
    warmup_count: number
    discovery_count: number
    confirmation_count: number
    reference_count: number
    recent_count: number
  }
  if (
    strategy.strategy_id !== query.strategy_id ||
    strategy.strategy_version !== query.strategy_version ||
    strategy.replicate !== query.replicate ||
    split.total_assignment_count !==
      split.warmup_count + split.discovery_count + split.confirmation_count ||
    split.confirmation_count !== split.reference_count + split.recent_count
  ) {
    return false
  }
  const boundaries = [
    split.discovery_first_target,
    split.discovery_last_target,
    split.confirmation_first_target,
    split.confirmation_last_target,
    split.reference_first_target,
    split.reference_last_target,
    split.recent_first_target,
    split.recent_last_target,
  ]
  if (value.audit_status === 'NOT_READY_INSUFFICIENT_HISTORY') {
    return (
      split.total_assignment_count < 1050 &&
      split.warmup_count === split.total_assignment_count &&
      split.discovery_count === 0 &&
      split.confirmation_count === 0 &&
      split.reference_count === 0 &&
      split.recent_count === 0 &&
      boundaries.every((boundary) => boundary === null) &&
      value.reference === null &&
      value.recent === null &&
      value.comparisons.length === 0
    )
  }
  if (
    value.audit_status !== 'COMPLETE' ||
    split.total_assignment_count < 1050 ||
    split.discovery_count !== 750 ||
    split.confirmation_count !== 300 ||
    split.reference_count !== 250 ||
    split.recent_count !== 50 ||
    !boundaries.every(isDrawIdentity) ||
    !isFeatureCohortDiagnostics(value.reference, query) ||
    !isFeatureCohortDiagnostics(value.recent, query) ||
    value.reference.baseline.observation_count !== 250 ||
    value.recent.baseline.observation_count !== 50 ||
    value.comparisons.length !== 64
  ) {
    return false
  }
  const [
    discoveryFirst,
    discoveryLast,
    confirmationFirst,
    confirmationLast,
    referenceFirst,
    referenceLast,
    recentFirst,
    recentLast,
  ] = boundaries
  const boundaryComparisons = [
    compareDrawIdentities(discoveryFirst, discoveryLast),
    compareDrawIdentities(discoveryLast, confirmationFirst),
    compareDrawIdentities(confirmationFirst, referenceFirst),
    compareDrawIdentities(referenceFirst, referenceLast),
    compareDrawIdentities(referenceLast, recentFirst),
    compareDrawIdentities(recentFirst, recentLast),
    compareDrawIdentities(recentLast, confirmationLast),
  ]
  if (
    boundaryComparisons.some((comparison) => comparison === null) ||
    (boundaryComparisons[0] as number) > 0 ||
    (boundaryComparisons[1] as number) >= 0 ||
    boundaryComparisons[2] !== 0 ||
    (boundaryComparisons[3] as number) > 0 ||
    (boundaryComparisons[4] as number) >= 0 ||
    (boundaryComparisons[5] as number) > 0 ||
    boundaryComparisons[6] !== 0
  ) {
    return false
  }
  const reference = value.reference
  const recent = value.recent
  return value.comparisons.every((comparison, index) => {
    if (
      !isRecord(comparison) ||
      comparison.cohort_index !== index ||
      !isFeatureKey(comparison.feature_key, index) ||
      !isRecord(comparison.reference_diagnostic) ||
      !isRecord(comparison.recent_diagnostic) ||
      !isRecord(comparison.reference_diagnostic.risk_difference) ||
      !isRecord(comparison.recent_diagnostic.risk_difference) ||
      JSON.stringify(comparison.reference_diagnostic) !==
        JSON.stringify(reference.diagnostics[index]) ||
      JSON.stringify(comparison.recent_diagnostic) !==
        JSON.stringify(recent.diagnostics[index])
    ) {
      return false
    }
    return (
      isExactEffectChange(
        comparison.effect_change,
        comparison.reference_diagnostic.risk_difference,
        comparison.recent_diagnostic.risk_difference,
      ) &&
      comparison.relationship ===
        expectedTemporalRelationship(
          comparison.reference_diagnostic.relation_vs_outside,
          comparison.recent_diagnostic.relation_vs_outside,
        )
    )
  })
}

function isCrossImportConcordance(
  value: unknown,
  query: HistoricalSuccessCrossImportConcordanceQuery,
): value is HistoricalSuccessCrossImportConcordance {
  if (
    !isRecord(value) ||
    !isRecord(value.metadata) ||
    !isMetadata(value.metadata.left, query.left_import_identity_sha256) ||
    !isMetadata(value.metadata.right, query.right_import_identity_sha256) ||
    query.left_import_identity_sha256 === query.right_import_identity_sha256 ||
    !isStrategyIdentity(value.strategy) ||
    !isCriterion(value.criterion, query.criterion) ||
    value.prefix_count !== query.prefix_count ||
    !Array.isArray(value.comparisons)
  ) {
    return false
  }
  const metadata = value.metadata
  const leftMetadata = metadata.left as Record<string, unknown>
  const rightMetadata = metadata.right as Record<string, unknown>
  const strategy = value.strategy as Record<string, unknown>
  if (
    metadata.same_dataset_sha256 !==
      (leftMetadata.dataset_sha256 === rightMetadata.dataset_sha256) ||
    metadata.same_source_artifact_sha256 !==
      (leftMetadata.source_artifact_sha256 === rightMetadata.source_artifact_sha256) ||
    strategy.strategy_id !== query.strategy_id ||
    strategy.strategy_version !== query.strategy_version ||
    strategy.replicate !== query.replicate
  ) {
    return false
  }
  const leftReady = value.left_holdout_status === 'COMPLETE'
  const rightReady = value.right_holdout_status === 'COMPLETE'
  const expectedPairStatus =
    leftReady && rightReady
      ? 'COMPLETE'
      : !leftReady && !rightReady
        ? 'BOTH_NOT_READY'
        : !leftReady
          ? 'LEFT_NOT_READY'
          : 'RIGHT_NOT_READY'
  if (
    !['COMPLETE', 'NOT_READY_INSUFFICIENT_HISTORY'].includes(
      String(value.left_holdout_status),
    ) ||
    !['COMPLETE', 'NOT_READY_INSUFFICIENT_HISTORY'].includes(
      String(value.right_holdout_status),
    ) ||
    value.pair_status !== expectedPairStatus
  ) {
    return false
  }
  if (!leftReady || !rightReady) {
    return value.confirmation_target_overlap === null && value.comparisons.length === 0
  }
  const overlap = value.confirmation_target_overlap
  if (
    !isRecord(overlap) ||
    overlap.left_confirmation_target_count !== 300 ||
    overlap.right_confirmation_target_count !== 300 ||
    !isNonNegativeInteger(overlap.overlap_count) ||
    !isNonNegativeInteger(overlap.left_only_count) ||
    !isNonNegativeInteger(overlap.right_only_count) ||
    overlap.left_only_count + overlap.overlap_count !== 300 ||
    overlap.right_only_count + overlap.overlap_count !== 300 ||
    overlap.relation !==
      (overlap.overlap_count === 0
        ? 'DISJOINT'
        : overlap.overlap_count === 300
          ? 'IDENTICAL'
          : 'PARTIAL_OVERLAP') ||
    value.comparisons.length !== 64
  ) {
    return false
  }
  return value.comparisons.every((comparison, index) => {
    if (
      !isRecord(comparison) ||
      comparison.cohort_index !== index ||
      !isFeatureKey(comparison.feature_key, index) ||
      !isRecord(comparison.left_confirmation_diagnostic) ||
      !isRecord(comparison.right_confirmation_diagnostic)
    ) {
      return false
    }
    const left = comparison.left_confirmation_diagnostic
    const right = comparison.right_confirmation_diagnostic
    if (
      !isOutcomeCounts(left.cohort_counts) ||
      !isOutcomeCounts(left.outside_counts) ||
      !isOutcomeCounts(right.cohort_counts) ||
      !isOutcomeCounts(right.outside_counts)
    ) {
      return false
    }
    const leftBaseline = {
      observation_count:
        left.cohort_counts.observation_count + left.outside_counts.observation_count,
      success_count: left.cohort_counts.success_count + left.outside_counts.success_count,
      failure_count: left.cohort_counts.failure_count + left.outside_counts.failure_count,
    }
    const rightBaseline = {
      observation_count:
        right.cohort_counts.observation_count + right.outside_counts.observation_count,
      success_count:
        right.cohort_counts.success_count + right.outside_counts.success_count,
      failure_count:
        right.cohort_counts.failure_count + right.outside_counts.failure_count,
    }
    return (
      leftBaseline.observation_count === 300 &&
      rightBaseline.observation_count === 300 &&
      isFeatureCohortDiagnostic(left, index, leftBaseline) &&
      isFeatureCohortDiagnostic(right, index, rightBaseline) &&
      isRecord(left.risk_difference) &&
      isRecord(right.risk_difference) &&
      isExactEffectChange(
        comparison.effect_change,
        left.risk_difference,
        right.risk_difference,
      ) &&
      comparison.relationship ===
        expectedTemporalRelationship(
          left.relation_vs_outside,
          right.relation_vs_outside,
        )
    )
  })
}

function isMultiImportConcordanceCensus(
  value: unknown,
  query: HistoricalSuccessMultiImportConcordanceCensusQuery,
): value is HistoricalSuccessMultiImportConcordanceCensus {
  const identities = [...query.import_identity_sha256]
  if (
    !isRecord(value) ||
    identities.length < 2 ||
    identities.length > 4 ||
    new Set(identities).size !== identities.length ||
    !identities.every(isSha256) ||
    !isStrategyIdentity(value.strategy) ||
    !isCriterion(value.criterion, query.criterion) ||
    value.prefix_count !== query.prefix_count ||
    !Array.isArray(value.imports) ||
    value.imports.length !== identities.length ||
    !Array.isArray(value.pairs) ||
    !Array.isArray(value.cohort_census)
  ) {
    return false
  }
  const strategy = value.strategy as Record<string, unknown>
  if (
    strategy.strategy_id !== query.strategy_id ||
    strategy.strategy_version !== query.strategy_version ||
    strategy.replicate !== query.replicate
  ) {
    return false
  }
  const holdoutStatuses: string[] = []
  for (const [index, item] of value.imports.entries()) {
    if (
      !isRecord(item) ||
      item.import_index !== index ||
      !isMetadata(item.metadata, identities[index]!) ||
      !['COMPLETE', 'NOT_READY_INSUFFICIENT_HISTORY'].includes(
        String(item.holdout_status),
      )
    ) {
      return false
    }
    holdoutStatuses.push(String(item.holdout_status))
  }
  const readyCount = holdoutStatuses.filter((status) => status === 'COMPLETE').length
  const expectedCensusStatus =
    readyCount === identities.length
      ? 'COMPLETE'
      : readyCount === 0
        ? 'ALL_NOT_READY'
        : 'PARTIAL_NOT_READY'
  if (value.census_status !== expectedCensusStatus) return false

  const expectedPairs = identities.flatMap((_, left) =>
    identities.slice(left + 1).map((__, offset) => [left, left + offset + 1] as const),
  )
  if (
    value.pair_count !== expectedPairs.length ||
    value.pairs.length !== expectedPairs.length
  ) {
    return false
  }
  for (const [pairIndex, pair] of value.pairs.entries()) {
    const [leftIndex, rightIndex] = expectedPairs[pairIndex]!
    if (
      !isRecord(pair) ||
      pair.left_import_index !== leftIndex ||
      pair.right_import_index !== rightIndex ||
      !isRecord(pair.metadata) ||
      !isMetadata(pair.metadata.left, identities[leftIndex]!) ||
      !isMetadata(pair.metadata.right, identities[rightIndex]!) ||
      pair.left_holdout_status !== holdoutStatuses[leftIndex] ||
      pair.right_holdout_status !== holdoutStatuses[rightIndex]
    ) {
      return false
    }
    const leftMetadata = pair.metadata.left as Record<string, unknown>
    const rightMetadata = pair.metadata.right as Record<string, unknown>
    if (
      pair.metadata.same_dataset_sha256 !==
        (leftMetadata.dataset_sha256 === rightMetadata.dataset_sha256) ||
      pair.metadata.same_source_artifact_sha256 !==
        (leftMetadata.source_artifact_sha256 ===
          rightMetadata.source_artifact_sha256)
    ) {
      return false
    }
    const leftReady = holdoutStatuses[leftIndex] === 'COMPLETE'
    const rightReady = holdoutStatuses[rightIndex] === 'COMPLETE'
    const expectedPairStatus =
      leftReady && rightReady
        ? 'COMPLETE'
        : !leftReady && !rightReady
          ? 'BOTH_NOT_READY'
          : !leftReady
            ? 'LEFT_NOT_READY'
            : 'RIGHT_NOT_READY'
    if (pair.pair_status !== expectedPairStatus) return false
    if (!leftReady || !rightReady) {
      if (pair.confirmation_target_overlap !== null) return false
      continue
    }
    const overlap = pair.confirmation_target_overlap
    if (
      !isRecord(overlap) ||
      overlap.left_confirmation_target_count !== 300 ||
      overlap.right_confirmation_target_count !== 300 ||
      !isNonNegativeInteger(overlap.overlap_count) ||
      !isNonNegativeInteger(overlap.left_only_count) ||
      !isNonNegativeInteger(overlap.right_only_count) ||
      overlap.left_only_count + overlap.overlap_count !== 300 ||
      overlap.right_only_count + overlap.overlap_count !== 300 ||
      overlap.relation !==
        (overlap.overlap_count === 0
          ? 'DISJOINT'
          : overlap.overlap_count === 300
            ? 'IDENTICAL'
            : 'PARTIAL_OVERLAP')
    ) {
      return false
    }
  }

  if (expectedCensusStatus !== 'COMPLETE') {
    return value.cohort_census_count === 0 && value.cohort_census.length === 0
  }
  if (
    value.cohort_census_count !== 64 ||
    value.cohort_census.length !== 64
  ) {
    return false
  }
  return value.cohort_census.every((row, cohortIndex) => {
    if (
      !isRecord(row) ||
      row.cohort_index !== cohortIndex ||
      !isFeatureKey(row.feature_key, cohortIndex) ||
      !Array.isArray(row.confirmation_diagnostics) ||
      row.confirmation_diagnostics.length !== identities.length ||
      !isNonNegativeInteger(row.higher_count) ||
      !isNonNegativeInteger(row.equal_count) ||
      !isNonNegativeInteger(row.lower_count) ||
      !isNonNegativeInteger(row.unavailable_count) ||
      row.higher_count +
        row.equal_count +
        row.lower_count +
        row.unavailable_count !==
        identities.length
    ) {
      return false
    }
    const expectedSummary =
      row.unavailable_count === identities.length
        ? 'NO_AVAILABLE_EFFECT'
        : row.unavailable_count > 0
          ? 'PARTIAL_AVAILABILITY'
          : row.higher_count === identities.length
            ? 'ALL_AVAILABLE_HIGHER'
            : row.equal_count === identities.length
              ? 'ALL_AVAILABLE_EQUAL'
              : row.lower_count === identities.length
                ? 'ALL_AVAILABLE_LOWER'
                : 'MIXED_AVAILABLE'
    if (row.summary !== expectedSummary) return false
    return row.confirmation_diagnostics.every((item, importIndex) => {
      if (
        !isRecord(item) ||
        item.import_index !== importIndex ||
        item.import_identity_sha256 !== identities[importIndex] ||
        !isRecord(item.diagnostic) ||
        !isOutcomeCounts(item.diagnostic.cohort_counts) ||
        !isOutcomeCounts(item.diagnostic.outside_counts)
      ) {
        return false
      }
      const baseline = {
        observation_count:
          item.diagnostic.cohort_counts.observation_count +
          item.diagnostic.outside_counts.observation_count,
        success_count:
          item.diagnostic.cohort_counts.success_count +
          item.diagnostic.outside_counts.success_count,
        failure_count:
          item.diagnostic.cohort_counts.failure_count +
          item.diagnostic.outside_counts.failure_count,
      }
      return (
        baseline.observation_count === 300 &&
        isFeatureCohortDiagnostic(item.diagnostic, cohortIndex, baseline)
      )
    })
  })
}

const QUALIFICATION_PRIMARY_STATUSES = [
  'NOT_READY',
  'EVIDENCE_INCOMPLETE',
  'RESEARCH_CANDIDATE',
] as const
const QUALIFICATION_FLAG_ORDER = [
  'CROSS_IMPORT_UNRESOLVED',
  'HISTORICAL_CONCORDANCE_OBSERVED',
  'RECENT_RELATIONSHIP_DIFFERENCE',
] as const
const QUALIFICATION_EVIDENCE_STATUSES = ['COMPLETE', 'NOT_READY'] as const
const QUALIFICATION_PAIR_STATUSES = [
  'COMPLETE',
  'LEFT_NOT_READY',
  'RIGHT_NOT_READY',
  'BOTH_NOT_READY',
] as const
const QUALIFICATION_OVERLAP_RELATIONS = [
  'DISJOINT',
  'PARTIAL_OVERLAP',
  'IDENTICAL',
] as const
const QUALIFICATION_CENSUS_STATUSES = [
  'COMPLETE',
  'PARTIAL_NOT_READY',
  'ALL_NOT_READY',
] as const
const RANDOM_BASELINE_CAVEAT =
  'Random/null benchmark unavailable; random advantage has not been evaluated.'

function isResearchQualification(
  value: unknown,
  query: HistoricalSuccessResearchQualificationQuery,
): value is HistoricalSuccessResearchQualification {
  const identities = [...query.import_identity_sha256]
  if (
    !isRecord(value) ||
    identities.length < 2 ||
    identities.length > 4 ||
    new Set(identities).size !== identities.length ||
    !identities.every(isSha256) ||
    !isRecord(value.identity) ||
    value.identity.strategy_id !== query.strategy_id ||
    value.identity.strategy_version !== query.strategy_version ||
    value.identity.replicate !== query.replicate ||
    value.identity.prefix_count !== query.prefix_count ||
    value.identity.criterion !== query.criterion ||
    !Array.isArray(value.ordered_import_evidence) ||
    value.ordered_import_evidence.length !== identities.length ||
    !QUALIFICATION_PRIMARY_STATUSES.includes(
      value.primary_status as (typeof QUALIFICATION_PRIMARY_STATUSES)[number],
    ) ||
    !Array.isArray(value.informational_flags) ||
    !QUALIFICATION_CENSUS_STATUSES.includes(
      value.census_status as (typeof QUALIFICATION_CENSUS_STATUSES)[number],
    ) ||
    !isNonNegativeInteger(value.comparable_import_count) ||
    !isNonNegativeInteger(value.expected_pair_count) ||
    !isNonNegativeInteger(value.actual_pair_count) ||
    !isNonNegativeInteger(value.cohort_census_count) ||
    !Array.isArray(value.pair_evidence)
  ) {
    return false
  }

  const imports = value.ordered_import_evidence
  for (const [index, item] of imports.entries()) {
    if (
      !isRecord(item) ||
      item.import_index !== index ||
      item.import_identity_sha256 !== identities[index] ||
      !isSha256(item.dataset_sha256) ||
      !isSha256(item.source_artifact_sha256) ||
      !isNonNegativeInteger(item.source_observation_count) ||
      !QUALIFICATION_EVIDENCE_STATUSES.includes(
        item.strategy_window_status as (typeof QUALIFICATION_EVIDENCE_STATUSES)[number],
      ) ||
      !QUALIFICATION_EVIDENCE_STATUSES.includes(
        item.temporal_holdout_status as (typeof QUALIFICATION_EVIDENCE_STATUSES)[number],
      ) ||
      !QUALIFICATION_EVIDENCE_STATUSES.includes(
        item.recent_audit_status as (typeof QUALIFICATION_EVIDENCE_STATUSES)[number],
      ) ||
      !isNonNegativeInteger(item.recent_relationship_difference_count) ||
      item.recent_relationship_difference_count > 64 ||
      (item.temporal_holdout_status === 'COMPLETE') !==
        (item.recent_audit_status === 'COMPLETE') ||
      (item.recent_audit_status === 'NOT_READY' &&
        item.recent_relationship_difference_count !== 0)
    ) {
      return false
    }
  }

  const expectedPairCount = identities.length * (identities.length - 1) / 2
  if (
    value.expected_pair_count !== expectedPairCount ||
    value.actual_pair_count !== value.pair_evidence.length ||
    value.cohort_census_count > 64
  ) {
    return false
  }
  const pairIndexes: string[] = []
  const comparableIndexes = new Set<number>()
  for (const pair of value.pair_evidence) {
    if (
      !isRecord(pair) ||
      !isNonNegativeInteger(pair.left_import_index) ||
      !isNonNegativeInteger(pair.right_import_index) ||
      pair.left_import_index >= pair.right_import_index ||
      pair.right_import_index >= identities.length ||
      !QUALIFICATION_PAIR_STATUSES.includes(
        pair.pair_status as (typeof QUALIFICATION_PAIR_STATUSES)[number],
      ) ||
      typeof pair.same_dataset_sha256 !== 'boolean' ||
      typeof pair.same_source_artifact_sha256 !== 'boolean' ||
      (pair.confirmation_overlap_relation !== null &&
        !QUALIFICATION_OVERLAP_RELATIONS.includes(
          pair.confirmation_overlap_relation as (typeof QUALIFICATION_OVERLAP_RELATIONS)[number],
        )) ||
      typeof pair.r1_comparable !== 'boolean'
    ) {
      return false
    }
    const left = imports[pair.left_import_index]!
    const right = imports[pair.right_import_index]!
    const expectedComparable =
      pair.pair_status === 'COMPLETE' &&
      !pair.same_dataset_sha256 &&
      !pair.same_source_artifact_sha256 &&
      ['PARTIAL_OVERLAP', 'DISJOINT'].includes(
        String(pair.confirmation_overlap_relation),
      )
    if (
      pair.same_dataset_sha256 !==
        (left.dataset_sha256 === right.dataset_sha256) ||
      pair.same_source_artifact_sha256 !==
        (left.source_artifact_sha256 === right.source_artifact_sha256) ||
      pair.r1_comparable !== expectedComparable ||
      (pair.pair_status === 'COMPLETE') !==
        (pair.confirmation_overlap_relation !== null)
    ) {
      return false
    }
    const indexKey = `${pair.left_import_index}:${pair.right_import_index}`
    if (
      pairIndexes.includes(indexKey) ||
      (pairIndexes.length > 0 && pairIndexes[pairIndexes.length - 1]! >= indexKey)
    ) {
      return false
    }
    pairIndexes.push(indexKey)
    if (pair.r1_comparable) {
      comparableIndexes.add(pair.left_import_index)
      comparableIndexes.add(pair.right_import_index)
    }
  }
  if (value.comparable_import_count !== comparableIndexes.size) return false

  const flags = value.informational_flags
  if (
    flags.some(
      (flag) =>
        !QUALIFICATION_FLAG_ORDER.includes(
          flag as (typeof QUALIFICATION_FLAG_ORDER)[number],
        ),
    ) ||
    new Set(flags).size !== flags.length ||
    flags.join('\u0000') !==
      QUALIFICATION_FLAG_ORDER.filter((flag) => flags.includes(flag)).join('\u0000')
  ) {
    return false
  }
  const unresolved = flags.includes('CROSS_IMPORT_UNRESOLVED')
  const concordant = flags.includes('HISTORICAL_CONCORDANCE_OBSERVED')
  const recentDifference =
    value.primary_status !== 'NOT_READY' &&
    imports.some(
      (item) =>
        item.recent_audit_status === 'COMPLETE' &&
        item.recent_relationship_difference_count > 0,
    )
  if (
    (unresolved && concordant) ||
    flags.includes('RECENT_RELATIONSHIP_DIFFERENCE') !== recentDifference
  ) {
    return false
  }
  const notReady = imports.some(
    (item) =>
      item.source_observation_count === 0 ||
      item.strategy_window_status !== 'COMPLETE' ||
      item.temporal_holdout_status !== 'COMPLETE',
  )
  if (
    (notReady && value.primary_status !== 'NOT_READY') ||
    (!notReady && value.primary_status === 'NOT_READY')
  ) {
    return false
  }
  const candidate = value.primary_status === 'RESEARCH_CANDIDATE'
  if (
    candidate !== concordant ||
    (candidate
      ? value.random_baseline_caveat !== RANDOM_BASELINE_CAVEAT ||
        value.census_status !== 'COMPLETE' ||
        value.cohort_census_count !== 64 ||
        value.actual_pair_count !== value.expected_pair_count ||
        value.pair_evidence.some((pair) => !pair.r1_comparable)
      : value.random_baseline_caveat !== null) ||
    (value.primary_status === 'EVIDENCE_INCOMPLETE' && !unresolved)
  ) {
    return false
  }
  return true
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

export async function getHistoricalSuccessRandomBaseline(
  query: HistoricalSuccessRandomBaselineQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessRandomBaseline> {
  const parameters = successQueryParameters(query)
  parameters.set('window_kind', query.window_kind)
  const identity = [
    query.strategy_id,
    query.strategy_version,
    String(query.replicate),
  ]
    .map((part) => encodeURIComponent(part))
    .join('/')
  const payload = await fetchPayload(
    `${WINDOWS_ENDPOINT}/strategies/${identity}/random-null-baseline?${parameters.toString()}`,
    signal,
  )
  if (!isRandomBaselineResponse(payload, query)) throw malformedResponse()
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

export async function getHistoricalSuccessFeatureCohortDiagnostics(
  query: HistoricalSuccessFeatureCohortDiagnosticsQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessFeatureCohortDiagnostics> {
  const parameters = successQueryParameters(query)
  const identity = [query.strategy_id, query.strategy_version, String(query.replicate)]
    .map((part) => encodeURIComponent(part))
    .join('/')
  const payload = await fetchPayload(
    `${WINDOWS_ENDPOINT}/strategies/${identity}/feature-cohorts/diagnostics?${parameters.toString()}`,
    signal,
  )
  if (!isFeatureCohortDiagnostics(payload, query)) throw malformedResponse()
  return payload
}

export async function getHistoricalSuccessTemporalHoldout(
  query: HistoricalSuccessTemporalHoldoutQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessTemporalHoldout> {
  const parameters = successQueryParameters(query)
  const identity = [query.strategy_id, query.strategy_version, String(query.replicate)]
    .map((part) => encodeURIComponent(part))
    .join('/')
  const payload = await fetchPayload(
    `${WINDOWS_ENDPOINT}/strategies/${identity}/feature-cohorts/temporal-holdout?${parameters.toString()}`,
    signal,
  )
  if (!isTemporalHoldout(payload, query)) throw malformedResponse()
  return payload
}

export async function getHistoricalSuccessRecent50StabilityAudit(
  query: HistoricalSuccessRecent50StabilityAuditQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessRecent50StabilityAudit> {
  const parameters = successQueryParameters(query)
  const identity = [query.strategy_id, query.strategy_version, String(query.replicate)]
    .map((part) => encodeURIComponent(part))
    .join('/')
  const payload = await fetchPayload(
    `${WINDOWS_ENDPOINT}/strategies/${identity}/feature-cohorts/recent-50-stability-audit?${parameters.toString()}`,
    signal,
  )
  if (!isRecent50StabilityAudit(payload, query)) throw malformedResponse()
  return payload
}

export async function getHistoricalSuccessCrossImportConcordance(
  query: HistoricalSuccessCrossImportConcordanceQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessCrossImportConcordance> {
  if (query.left_import_identity_sha256 === query.right_import_identity_sha256) {
    throw new HistoricalSuccessWindowsRequestError(
      'Select two distinct historical imports.',
      422,
      'INVALID_REQUEST',
      'REQUEST_VALIDATION_FAILED',
    )
  }
  const parameters = new URLSearchParams()
  parameters.set('left_import_identity_sha256', query.left_import_identity_sha256)
  parameters.set('right_import_identity_sha256', query.right_import_identity_sha256)
  parameters.set('prefix_count', String(query.prefix_count))
  parameters.set('criterion', query.criterion)
  const identity = [query.strategy_id, query.strategy_version, String(query.replicate)]
    .map((part) => encodeURIComponent(part))
    .join('/')
  const payload = await fetchPayload(
    `${WINDOWS_ENDPOINT}/strategies/${identity}/feature-cohorts/cross-import-concordance?${parameters.toString()}`,
    signal,
  )
  if (!isCrossImportConcordance(payload, query)) throw malformedResponse()
  return payload
}

export async function getHistoricalSuccessMultiImportConcordanceCensus(
  query: HistoricalSuccessMultiImportConcordanceCensusQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessMultiImportConcordanceCensus> {
  const identities = [...query.import_identity_sha256]
  if (
    identities.length < 2 ||
    identities.length > 4 ||
    new Set(identities).size !== identities.length ||
    !identities.every(isSha256)
  ) {
    throw new HistoricalSuccessWindowsRequestError(
      'Select two to four distinct historical imports.',
      422,
      'INVALID_REQUEST',
      'REQUEST_VALIDATION_FAILED',
    )
  }
  const parameters = new URLSearchParams()
  for (const identity of identities) {
    parameters.append('import_identity_sha256', identity)
  }
  parameters.set('prefix_count', String(query.prefix_count))
  parameters.set('criterion', query.criterion)
  const strategyIdentity = [
    query.strategy_id,
    query.strategy_version,
    String(query.replicate),
  ]
    .map((part) => encodeURIComponent(part))
    .join('/')
  const payload = await fetchPayload(
    `${WINDOWS_ENDPOINT}/strategies/${strategyIdentity}/feature-cohorts/multi-import-concordance-census?${parameters.toString()}`,
    signal,
  )
  if (!isMultiImportConcordanceCensus(payload, query)) throw malformedResponse()
  return payload
}

export async function getHistoricalSuccessResearchQualification(
  query: HistoricalSuccessResearchQualificationQuery,
  signal?: AbortSignal,
): Promise<HistoricalSuccessResearchQualification> {
  const identities = [...query.import_identity_sha256]
  if (
    identities.length < 2 ||
    identities.length > 4 ||
    new Set(identities).size !== identities.length ||
    !identities.every(isSha256)
  ) {
    throw new HistoricalSuccessWindowsRequestError(
      'Select two to four distinct historical imports.',
      422,
      'INVALID_REQUEST',
      'REQUEST_VALIDATION_FAILED',
    )
  }
  const parameters = new URLSearchParams()
  for (const identity of identities) {
    parameters.append('import_identity_sha256', identity)
  }
  parameters.set('prefix_count', String(query.prefix_count))
  parameters.set('criterion', query.criterion)
  const strategyIdentity = [
    query.strategy_id,
    query.strategy_version,
    String(query.replicate),
  ]
    .map((part) => encodeURIComponent(part))
    .join('/')
  const payload = await fetchPayload(
    `${WINDOWS_ENDPOINT}/strategies/${strategyIdentity}/research-qualification?${parameters.toString()}`,
    signal,
  )
  if (!isResearchQualification(payload, query)) throw malformedResponse()
  return payload
}
