import type { components, paths } from './generated/openapi'

export type B649ResearchBacktestSummary =
  paths['/api/v1/b649-research-backtests/summary']['get']['responses'][200]['content']['application/json']
export type B649ResearchBacktestMethodsPage =
  paths['/api/v1/b649-research-backtests/methods']['get']['responses'][200]['content']['application/json']
export type B649ResearchBacktestMethod = components['schemas']['B649ResearchBoardMethodView']
export type B649ResearchBacktestRankingsPage =
  paths['/api/v1/b649-research-backtests/rankings']['get']['responses'][200]['content']['application/json']
export type B649ResearchBacktestRanking = components['schemas']['B649ResearchBoardRankingView']
export type B649ResearchBacktestWindow = B649ResearchBacktestSummary['windows'][number]
export type B649ResearchBacktestMethodsQuery =
  paths['/api/v1/b649-research-backtests/methods']['get']['parameters']['query']
export type B649ResearchBacktestRankingsQuery =
  paths['/api/v1/b649-research-backtests/rankings']['get']['parameters']['query']

export const B649_RESEARCH_BACKTEST_WINDOWS = [
  'FULL',
  'RECENT_750',
  'RECENT_300',
  'RECENT_50',
] as const satisfies readonly B649ResearchBacktestWindow[]

export const B649_RESEARCH_BACKTEST_PAGE_SIZE = 50
export const B649_RESEARCH_BACKTEST_GROUP_SCAN_SIZE = 100

export const EXPECTED_B649_RESEARCH_V2_SOURCE = {
  taskId: 'NUMBER2_D_LMS_HUMAN_BOARD_V2_INTEGRATION_20261102_R1',
  authorityCommit: 'fe3aa81d3844ac11d4360447c243e90fe4a6613a',
  observedCheckoutHead: 'b4e11ebd0981d549ce70055e70f8fbd0065cd2dd',
  sourceManifestSha256: 'aae584e9b4d991d549e1eacb378f5df7170c50ca3be804407cfaaed0f5125411',
} as const

const SUMMARY_ENDPOINT = '/api/v1/b649-research-backtests/summary'
const METHODS_ENDPOINT = '/api/v1/b649-research-backtests/methods'
const RANKINGS_ENDPOINT = '/api/v1/b649-research-backtests/rankings'

export type B649ResearchBacktestsErrorKind =
  | 'UNAVAILABLE'
  | 'INVALID_REQUEST'
  | 'MALFORMED_RESPONSE'
  | 'NETWORK'

export class B649ResearchBacktestsRequestError extends Error {
  readonly status: number
  readonly kind: B649ResearchBacktestsErrorKind
  readonly errorCode: string | null

  constructor(
    message: string,
    status: number,
    kind: B649ResearchBacktestsErrorKind,
    errorCode: string | null = null,
  ) {
    super(message)
    this.name = 'B649ResearchBacktestsRequestError'
    this.status = status
    this.kind = kind
    this.errorCode = errorCode
  }
}

export async function fetchB649ResearchBacktestSummary(
  signal?: AbortSignal,
): Promise<B649ResearchBacktestSummary> {
  return requestJson(SUMMARY_ENDPOINT, isSummary, signal)
}

export async function fetchB649ResearchBacktestMethods(
  query: B649ResearchBacktestMethodsQuery,
  signal?: AbortSignal,
): Promise<B649ResearchBacktestMethodsPage> {
  const parameters = new URLSearchParams()
  if (query.limit !== undefined) parameters.set('limit', String(query.limit))
  if (query.offset !== undefined) parameters.set('offset', String(query.offset))
  if (query.method_id) parameters.set('method_id', query.method_id)
  if (query.research_status) parameters.set('research_status', query.research_status)
  return requestJson(`${METHODS_ENDPOINT}?${parameters}`, isMethodsPage, signal)
}

export async function fetchB649ResearchBacktestRankings(
  query: B649ResearchBacktestRankingsQuery,
  signal?: AbortSignal,
): Promise<B649ResearchBacktestRankingsPage> {
  if ((query.target_draw_set_identity == null) !== (query.eligible_draws == null)) {
    throw new B649ResearchBacktestsRequestError(
      '比較群組必須同時指定 target_draw_set_identity 與 eligible_draws。',
      0,
      'INVALID_REQUEST',
      'INCOMPLETE_COMPARISON_GROUP',
    )
  }
  const parameters = new URLSearchParams({
    cohort: query.cohort,
    K: String(query.K),
    window: query.window,
    prize_metric: query.prize_metric,
  })
  if (query.target_draw_set_identity != null) {
    parameters.set('target_draw_set_identity', query.target_draw_set_identity)
  }
  if (query.eligible_draws != null) {
    parameters.set('eligible_draws', String(query.eligible_draws))
  }
  if (query.limit !== undefined) parameters.set('limit', String(query.limit))
  if (query.offset !== undefined) parameters.set('offset', String(query.offset))
  return requestJson(`${RANKINGS_ENDPOINT}?${parameters}`, isRankingsPage, signal)
}

export function isExpectedB649ResearchV2Source(
  summary: B649ResearchBacktestSummary,
): boolean {
  return summary.source_task_id === EXPECTED_B649_RESEARCH_V2_SOURCE.taskId &&
    summary.source_authority_commit === EXPECTED_B649_RESEARCH_V2_SOURCE.authorityCommit &&
    summary.observed_checkout_head === EXPECTED_B649_RESEARCH_V2_SOURCE.observedCheckoutHead &&
    summary.source_manifest_sha256 === EXPECTED_B649_RESEARCH_V2_SOURCE.sourceManifestSha256
}

async function requestJson<T>(
  url: string,
  validate: (value: unknown) => value is T,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, { signal })
  } catch (error) {
    if (signal?.aborted || (error instanceof Error && error.name === 'AbortError')) throw error
    throw new B649ResearchBacktestsRequestError('網路連線失敗。', 0, 'NETWORK')
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    if (!response.ok) {
      throw new B649ResearchBacktestsRequestError(
        `HTTP ${response.status}: 伺服器未提供可讀取的錯誤內容。`,
        response.status,
        response.status === 503 ? 'UNAVAILABLE' : 'INVALID_REQUEST',
      )
    }
    throw new B649ResearchBacktestsRequestError(
      '伺服器回傳的內容不是有效 JSON。',
      response.status,
      'MALFORMED_RESPONSE',
    )
  }

  if (!response.ok) {
    const errorCode = isRecord(payload) && typeof payload.error_code === 'string'
      ? payload.error_code
      : null
    const message = isRecord(payload) && typeof payload.message === 'string'
      ? payload.message
      : `HTTP ${response.status}`
    throw new B649ResearchBacktestsRequestError(
      `HTTP ${response.status}: ${message}`,
      response.status,
      response.status === 503 ? 'UNAVAILABLE' : 'INVALID_REQUEST',
      errorCode,
    )
  }

  if (!validate(payload)) {
    throw new B649ResearchBacktestsRequestError(
      '伺服器回應與已生成的 B649 V2 OpenAPI 契約不符。',
      response.status,
      'MALFORMED_RESPONSE',
    )
  }
  return payload
}

function isSummary(value: unknown): value is B649ResearchBacktestSummary {
  return isRecord(value) &&
    isString(value.source_task_id) &&
    isString(value.source_authority_commit) &&
    isString(value.observed_checkout_head) &&
    isString(value.source_manifest_sha256) &&
    isNonnegativeInteger(value.method_version_count) &&
    isNonnegativeInteger(value.inventory_count) &&
    isNonnegativeInteger(value.ranking_count) &&
    isCountMap(value.metrics_availability_counts) &&
    isCountMap(value.research_status_counts) &&
    isNonnegativeInteger(value.unavailable_count) &&
    isNonnegativeInteger(value.not_applicable_count) &&
    isNonnegativeInteger(value.comparable_group_count) &&
    isNonnegativeInteger(value.duplicate_output_groups) &&
    Array.isArray(value.windows) &&
    value.windows.every(isResearchWindow) &&
    Array.isArray(value.K_values) &&
    value.K_values.every(isPositiveInteger) &&
    Array.isArray(value.prize_metrics) &&
    value.prize_metrics.every(isString) &&
    Array.isArray(value.cohorts) &&
    value.cohorts.every(isString) &&
    isNonnegativeInteger(value.comparison_group_count)
}

function isMethodsPage(value: unknown): value is B649ResearchBacktestMethodsPage {
  return isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isMethod) &&
    isPageMetadata(value)
}

function isMethod(value: unknown): value is B649ResearchBacktestMethod {
  return isRecord(value) &&
    isString(value.method_id) &&
    isString(value.method_version) &&
    isString(value.method_family) &&
    isSourceIdentity(value.source_identity) &&
    isString(value.task_id) &&
    isString(value.evaluation_cohort) &&
    isString(value.history_window) &&
    isNullableInteger(value.K) &&
    isString(value.official_prize_metric) &&
    isNullableInteger(value.successful_draws) &&
    isNullableInteger(value.eligible_draws) &&
    isNullableString(value.success_rate) &&
    isString(value.baseline_identity) &&
    isNullableString(value.baseline_success_rate) &&
    isNullableString(value.paired_difference) &&
    isString(value.research_status) &&
    isString(value.original_advance_decision) &&
    isString(value.artifact_locator) &&
    isString(value.artifact_sha256) &&
    isString(value.backtest_artifact_locator) &&
    isString(value.backtest_artifact_sha256) &&
    isString(value.metrics_availability) &&
    isString(value.metrics_unavailable_reason) &&
    isString(value.shared_output_identity) &&
    isString(value.method_type) &&
    isRecord(value.auxiliary_statistics_json) &&
    isString(value.arm_identity) &&
    isString(value.lottery_type) &&
    isString(value.window) &&
    isString(value.prize_metric) &&
    isNullableInteger(value.wins) &&
    isNullableString(value.baseline_rate) &&
    isNullableString(value.delta_percentage_points) &&
    isString(value.research_class) &&
    isString(value.target_draw_set_identity) &&
    isNullableInteger(value.comparison_rank) &&
    isString(value.comparison_group_id) &&
    isString(value.comparison_status) &&
    isString(value.original_board_metrics_availability) &&
    isString(value.original_board_metrics_unavailable_reason) &&
    isString(value.board_original_advance_decision) &&
    isIdentityChain(value.source_identity_chain) &&
    isStringArray(value.source_shared_output_identities) &&
    isLineage(value.source_lineage) &&
    isString(value.source_record_id) &&
    isRecord(value.source_inventory_json) &&
    isString(value.owner_long_rank) &&
    isString(value.owner_middle_rank) &&
    isString(value.owner_short_rank) &&
    isString(value.owner_selected) &&
    isString(value.owner_reason)
}

function isRankingsPage(value: unknown): value is B649ResearchBacktestRankingsPage {
  return isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isRanking) &&
    isPageMetadata(value) &&
    isString(value.cohort) &&
    isPositiveInteger(value.K) &&
    isResearchWindow(value.window) &&
    isString(value.prize_metric) &&
    (value.target_draw_set_identity === null || isString(value.target_draw_set_identity)) &&
    (value.eligible_draws === null || isPositiveInteger(value.eligible_draws)) &&
    isNonnegativeInteger(value.comparison_group_count)
}

function isRanking(value: unknown): value is B649ResearchBacktestRanking {
  return isRecord(value) &&
    isString(value.method_id) &&
    isString(value.method_version) &&
    isString(value.arm_identity) &&
    isString(value.method_family) &&
    isString(value.task_id) &&
    isSourceIdentity(value.source_identity) &&
    isIdentityChain(value.source_identity_chain) &&
    isString(value.lottery_type) &&
    isString(value.evaluation_cohort) &&
    isString(value.target_draw_set_identity) &&
    isResearchWindow(value.window) &&
    isPositiveInteger(value.K) &&
    isString(value.prize_metric) &&
    isNonnegativeInteger(value.wins) &&
    isPositiveInteger(value.eligible_draws) &&
    isString(value.success_rate) &&
    isPositiveInteger(value.comparison_rank) &&
    isNonnegativeInteger(value.rank_basis_identity_count) &&
    isString(value.shared_output_identity) &&
    isStringArray(value.source_shared_output_identities) &&
    isString(value.baseline_identity) &&
    isNullableString(value.baseline_rate) &&
    isNullableString(value.delta_percentage_points) &&
    isString(value.research_status) &&
    isString(value.research_class) &&
    isString(value.original_advance_decision) &&
    isString(value.original_board_metrics_availability) &&
    isString(value.original_board_metrics_unavailable_reason) &&
    isString(value.board_original_advance_decision) &&
    isString(value.comparison_status) &&
    isString(value.comparison_notes) &&
    isString(value.artifact_locator) &&
    isString(value.artifact_sha256) &&
    (value.source_rank === null || isPositiveInteger(value.source_rank)) &&
    isLineage(value.source_lineage)
}

function isPageMetadata(value: Record<string, unknown>): boolean {
  return isNonnegativeInteger(value.total) &&
    isPositiveInteger(value.limit) &&
    isNonnegativeInteger(value.offset)
}

function isSourceIdentity(value: unknown): boolean {
  return isString(value) || isRecord(value)
}

function isIdentityChain(value: unknown): boolean {
  return Array.isArray(value) && value.every(isSourceIdentity)
}

function isLineage(value: unknown): boolean {
  return Array.isArray(value) && value.every((entry) =>
    isRecord(entry) && Object.values(entry).every(isString),
  )
}

function isCountMap(value: unknown): value is Record<string, number> {
  return isRecord(value) && Object.values(value).every(isNonnegativeInteger)
}

function isResearchWindow(value: unknown): value is B649ResearchBacktestWindow {
  return B649_RESEARCH_BACKTEST_WINDOWS.includes(value as B649ResearchBacktestWindow)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString)
}

function isNullableInteger(value: unknown): value is number | null {
  return value === null || Number.isInteger(value)
}

function isNullableString(value: unknown): value is string | null {
  return value === null || isString(value)
}

function isPositiveInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) > 0
}

function isNonnegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 0
}

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
