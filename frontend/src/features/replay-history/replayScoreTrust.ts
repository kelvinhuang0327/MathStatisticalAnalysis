export type ReplayScoreTrustStatus =
  | 'VERIFIED'
  | 'NOT_COMPUTED'
  | 'UNVERIFIABLE'
  | 'INCONSISTENT'

export interface ReplayScoreTrustInput {
  actual_main_numbers: readonly number[]
  predicted_tickets: ReadonlyArray<{
    main_numbers: readonly number[]
    main_hit_count: number | null
  }>
  best_main_hits: number | null
}

export interface ReplayTicketScoreTrust {
  status: ReplayScoreTrustStatus
  source_hits: number | null
  computed_hits: number | null
}

export interface ReplayScoreTrustAssessment {
  status: ReplayScoreTrustStatus
  aggregate_status: ReplayScoreTrustStatus
  computed_best_main_hits: number | null
  tickets: ReplayTicketScoreTrust[]
}

function hasCompleteMainNumbers(numbers: readonly number[] | null | undefined): numbers is readonly number[] {
  return Array.isArray(numbers) && numbers.length > 0 && numbers.every(Number.isInteger)
}

export function verifyMainHitCount(
  predictedMainNumbers: readonly number[] | null | undefined,
  actualMainNumbers: readonly number[] | null | undefined,
  sourceMainHitCount: number | null | undefined,
): ReplayTicketScoreTrust {
  if (sourceMainHitCount === null || sourceMainHitCount === undefined) {
    return { status: 'NOT_COMPUTED', source_hits: null, computed_hits: null }
  }

  if (
    !Number.isInteger(sourceMainHitCount) ||
    !hasCompleteMainNumbers(predictedMainNumbers) ||
    !hasCompleteMainNumbers(actualMainNumbers)
  ) {
    return {
      status: 'UNVERIFIABLE',
      source_hits: Number.isInteger(sourceMainHitCount) ? sourceMainHitCount : null,
      computed_hits: null,
    }
  }

  const actualSet = new Set(actualMainNumbers)
  let computedHits = 0
  for (const number of new Set(predictedMainNumbers)) {
    if (actualSet.has(number)) computedHits += 1
  }
  return {
    status: sourceMainHitCount === computedHits ? 'VERIFIED' : 'INCONSISTENT',
    source_hits: sourceMainHitCount,
    computed_hits: computedHits,
  }
}

export function assessReplayScoreTrust(input: ReplayScoreTrustInput): ReplayScoreTrustAssessment {
  const tickets = input.predicted_tickets.map((ticket) =>
    verifyMainHitCount(ticket.main_numbers, input.actual_main_numbers, ticket.main_hit_count),
  )
  const ticketsComparable = tickets.length > 0 && tickets.every(
    (ticket) => ticket.status === 'VERIFIED' || ticket.status === 'INCONSISTENT',
  )
  const computedBestMainHits = ticketsComparable
    ? Math.max(...tickets.map((ticket) => ticket.computed_hits ?? 0))
    : null

  let aggregateStatus: ReplayScoreTrustStatus
  if (input.best_main_hits === null) {
    aggregateStatus = 'NOT_COMPUTED'
  } else if (!ticketsComparable || computedBestMainHits === null) {
    aggregateStatus = 'UNVERIFIABLE'
  } else {
    aggregateStatus = input.best_main_hits === computedBestMainHits ? 'VERIFIED' : 'INCONSISTENT'
  }

  let status: ReplayScoreTrustStatus
  if (tickets.some((ticket) => ticket.status === 'INCONSISTENT') || aggregateStatus === 'INCONSISTENT') {
    status = 'INCONSISTENT'
  } else if (
    tickets.length === 0 ||
    tickets.some((ticket) => ticket.status === 'UNVERIFIABLE') ||
    aggregateStatus === 'UNVERIFIABLE'
  ) {
    status = 'UNVERIFIABLE'
  } else if (
    tickets.some((ticket) => ticket.status === 'NOT_COMPUTED') ||
    aggregateStatus === 'NOT_COMPUTED'
  ) {
    status = 'NOT_COMPUTED'
  } else {
    status = 'VERIFIED'
  }

  return { status, aggregate_status: aggregateStatus, computed_best_main_hits: computedBestMainHits, tickets }
}
