import type { paths } from './generated/openapi'

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
    typeof value.d3.status === 'string' &&
    value.d3.value === 'NOT_AVAILABLE' &&
    isD3Definition(value.d3.definition)
  )
}

function isD3Definition(
  value: unknown,
): value is StrategyEvidenceResponse['d3']['definition'] {
  return (
    isRecord(value) &&
    typeof value.metric_id === 'string' &&
    typeof value.metric_version === 'string' &&
    typeof value.schema_id === 'string' &&
    typeof value.schema_version === 'string' &&
    typeof value.formula_status === 'string' &&
    typeof value.direction === 'string' &&
    typeof value.aggregation === 'string' &&
    typeof value.sample_unit === 'string' &&
    typeof value.decimal_scale === 'number' &&
    typeof value.rounding_mode === 'string' &&
    typeof value.unit === 'string' &&
    typeof value.definition_prose === 'string' &&
    typeof value.authority_path === 'string'
  )
}

function isEvidenceItem(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.strategy_id === 'string' &&
    typeof value.strategy_version === 'string' &&
    (value.replicate === 'NOT_APPLICABLE' ||
      (typeof value.replicate === 'number' && Number.isInteger(value.replicate))) &&
    typeof value.display_name === 'string' &&
    typeof value.lifecycle_status === 'string' &&
    typeof value.executable === 'boolean' &&
    Array.isArray(value.supported_lottery_types) &&
    typeof value.minimum_history === 'number' &&
    Array.isArray(value.provenance) &&
    typeof value.adapter_available === 'boolean' &&
    ['CANONICAL_EVIDENCE_REGISTERED', 'CANONICAL_EVIDENCE_MISSING'].includes(
      String(value.registration_status),
    ) &&
    ['DEFINITION_AVAILABLE', 'DEFINITION_UNAVAILABLE'].includes(
      String(value.definition_status),
    ) &&
    [
      'EVIDENCE_VERIFIED',
      'EVIDENCE_DECLARED_NOT_RECOMPUTED',
      'EVIDENCE_STALE',
      'EVIDENCE_INCOMPATIBLE',
      'EVIDENCE_MISSING',
    ].includes(String(value.verification_status)) &&
    (value.unavailable_reason_code === null ||
      typeof value.unavailable_reason_code === 'string')
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
