import type { paths } from './generated/openapi'
import d3Definition from '../../../contracts/evidence/metric_definitions/d3.json'

const LIFECYCLE_STATUSES = ['IDEA', 'OBSERVATION', 'ONLINE', 'REJECTED', 'RETIRED'] as const
const LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO'] as const
const REGISTRATION_STATUSES = [
  'CANONICAL_EVIDENCE_REGISTERED',
  'CANONICAL_EVIDENCE_MISSING',
] as const
const DEFINITION_STATUSES = ['DEFINITION_AVAILABLE', 'DEFINITION_UNAVAILABLE'] as const
const VERIFICATION_STATUSES = [
  'EVIDENCE_VERIFIED',
  'EVIDENCE_DECLARED_NOT_RECOMPUTED',
  'EVIDENCE_STALE',
  'EVIDENCE_INCOMPATIBLE',
  'EVIDENCE_MISSING',
] as const
const IDENTITY_PLACEHOLDERS = new Set([
  '-',
  'na',
  'n/a',
  'none',
  'null',
  'undefined',
  'unknown',
  'unavailable',
  'not available',
  'tbd',
  'todo',
  'placeholder',
  '未填',
  '待填',
  '未設定',
  '待補',
])
const D3_AUTHORITY_PATH = 'contracts/evidence/metric_definitions/d3.json'

export type StrategyEvidenceResponse =
  paths['/api/v1/strategy-evidence']['get']['responses'][200]['content']['application/json']

export class StrategyEvidenceRequestError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'StrategyEvidenceRequestError'
    this.status = status
  }
}

export async function queryStrategyEvidence(
  signal?: AbortSignal,
): Promise<StrategyEvidenceResponse> {
  const response = await fetch('/api/v1/strategy-evidence', {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  const payload: unknown = await response.json()
  if (!response.ok) {
    throw new StrategyEvidenceRequestError(
      isRecord(payload) && typeof payload.message === 'string'
        ? payload.message
        : `Strategy Evidence request failed with HTTP ${response.status}`,
      response.status,
    )
  }
  if (!isStrategyEvidenceResponse(payload)) {
    throw new StrategyEvidenceRequestError(
      'Strategy Evidence returned an invalid response contract',
      502,
    )
  }
  return payload
}

function isStrategyEvidenceResponse(value: unknown): value is StrategyEvidenceResponse {
  if (!isRecord(value) || !Array.isArray(value.items)) return false
  return (
    value.items.every(isEvidenceItem) &&
    isRecord(value.best_strategy) &&
    value.best_strategy.status === 'UNAVAILABLE' &&
    value.best_strategy.reason === 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE' &&
    isRecord(value.strategy_combination_hit_rate) &&
    value.strategy_combination_hit_rate.status === 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE' &&
    value.strategy_combination_hit_rate.value === 'NOT_AVAILABLE' &&
    value.strategy_combination_hit_rate.owner === 'ACTIVE_MULTITICKET_AGENT' &&
    isRecord(value.d3) &&
    value.d3.status === 'RESERVED_UNAVAILABLE' &&
    value.d3.value === 'NOT_AVAILABLE' &&
    isD3Definition(value.d3.definition)
  )
}

function isD3Definition(
  value: unknown,
): value is StrategyEvidenceResponse['d3']['definition'] {
  if (!isRecord(value) || !Number.isSafeInteger(value.decimal_scale)) return false
  if (typeof value.decimal_scale !== 'number' || value.decimal_scale < 0) return false

  return (
    Object.entries(d3Definition).every(([key, expected]) => value[key] === expected) &&
    value.authority_path === D3_AUTHORITY_PATH
  )
}

function isEvidenceItem(value: unknown): boolean {
  return (
    isRecord(value) &&
    isIdentityString(value.strategy_id) &&
    isIdentityString(value.strategy_version) &&
    (value.replicate === 'NOT_APPLICABLE' ||
      (typeof value.replicate === 'number' &&
        Number.isSafeInteger(value.replicate) &&
        value.replicate >= 0)) &&
    isIdentityString(value.display_name) &&
    isOneOf(value.lifecycle_status, LIFECYCLE_STATUSES) &&
    typeof value.executable === 'boolean' &&
    Array.isArray(value.supported_lottery_types) &&
    value.supported_lottery_types.every((lotteryType) => isOneOf(lotteryType, LOTTERY_TYPES)) &&
    typeof value.minimum_history === 'number' &&
    Number.isSafeInteger(value.minimum_history) &&
    value.minimum_history > 0 &&
    Array.isArray(value.provenance) &&
    value.provenance.every((entry) => typeof entry === 'string') &&
    typeof value.adapter_available === 'boolean' &&
    isOneOf(value.registration_status, REGISTRATION_STATUSES) &&
    isOneOf(value.definition_status, DEFINITION_STATUSES) &&
    isOneOf(value.verification_status, VERIFICATION_STATUSES) &&
    (value.unavailable_reason_code === null ||
      typeof value.unavailable_reason_code === 'string')
  )
}

function isIdentityString(value: unknown): value is string {
  if (typeof value !== 'string') return false
  const normalized = value.trim().toLocaleLowerCase()
  return normalized.length > 0 && !IDENTITY_PLACEHOLDERS.has(normalized)
}

function isOneOf<const Values extends readonly string[]>(
  value: unknown,
  values: Values,
): value is Values[number] {
  return typeof value === 'string' && values.includes(value)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
