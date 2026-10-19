import type { components, paths } from './generated/openapi'

export type StrategyMatrixStructuralResponse =
  paths['/api/v1/strategy-matrix/structural']['get']['responses'][200]['content']['application/json']
export type StructuralMatrixCell = StrategyMatrixStructuralResponse['cells'][number]
export type StructuralMatrixValue = NonNullable<StructuralMatrixCell['value']>
export type StructuralLottery = components['schemas']['StructuralLottery']
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

export async function queryStrategyMatrixStructural(
  query: StrategyMatrixStructuralQuery = {},
  signal?: AbortSignal,
): Promise<StrategyMatrixStructuralResponse> {
  const parameters = new URLSearchParams()
  if (query.lottery) parameters.set('lottery', query.lottery)
  if (query.methodId) parameters.set('method_id', query.methodId)
  if (query.ticketCount !== undefined) parameters.set('ticket_count', String(query.ticketCount))
  const suffix = parameters.toString()

  const response = await fetch(`/api/v1/strategy-matrix/structural${suffix ? `?${suffix}` : ''}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  const payload: unknown = await response.json()
  if (!response.ok) {
    throw new StrategyMatrixStructuralRequestError(
      isRecord(payload) && typeof payload.message === 'string'
        ? payload.message
        : `Structural Matrix request failed with HTTP ${response.status}`,
      response.status,
      isRecord(payload) && typeof payload.error_code === 'string' ? payload.error_code : undefined,
    )
  }
  if (!isStrategyMatrixStructuralResponse(payload)) {
    throw new StrategyMatrixStructuralRequestError(
      'Structural Matrix returned an invalid response contract',
      502,
    )
  }
  return payload
}

function isStrategyMatrixStructuralResponse(value: unknown): value is StrategyMatrixStructuralResponse {
  if (!isRecord(value)) return false
  return (
    typeof value.schema_id === 'string' &&
    typeof value.schema_version === 'string' &&
    typeof value.projection_sha256 === 'string' &&
    isRecord(value.authority) &&
    typeof value.scope === 'string' &&
    Array.isArray(value.supported_ticket_counts) &&
    isRecord(value.metric) &&
    isRecord(value.claim_boundary) &&
    Array.isArray(value.cells) &&
    value.cells.every(isStructuralMatrixCell)
  )
}

function isStructuralMatrixCell(value: unknown): value is StructuralMatrixCell {
  if (!isRecord(value)) return false
  return (
    typeof value.row_id === 'string' &&
    typeof value.case_id === 'string' &&
    typeof value.lottery === 'string' &&
    typeof value.method_id === 'string' &&
    typeof value.ticket_count === 'number' &&
    typeof value.method_objective === 'string' &&
    typeof value.source_status === 'string' &&
    typeof value.measurement_status === 'string' &&
    (value.value === null || isStructuralMatrixValue(value.value)) &&
    (value.portfolio_sha256 === null || typeof value.portfolio_sha256 === 'string') &&
    (value.unavailable_reason === null || typeof value.unavailable_reason === 'string') &&
    (value.local_optimum_status === null || typeof value.local_optimum_status === 'string')
  )
}

function isStructuralMatrixValue(value: unknown): value is StructuralMatrixValue {
  return isRecord(value) && typeof value.numerator === 'string' && typeof value.denominator === 'string'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
