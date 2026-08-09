import {
  B649_HISTORY_WINDOWS,
  B649_PREFIX_COUNTS,
  B649RecordsRequestError,
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
  type B649HistoryWindow,
  type B649MultiTicketRecord,
  type B649MultiTicketSummary,
  type B649PrefixCount,
} from './b649MultiTicketRecords'

export type B649OwnerResearchRole =
  | 'CORE_REGIME'
  | 'STABLE_CORE'
  | 'RECENT_MOVER'
  | 'LOW_COVERAGE_CONTROL'
  | 'NEGATIVE_CONTROL'
  | 'WATCH'

export interface B649OwnerMetadata {
  strategyToken: string
  label: string
  role: B649OwnerResearchRole
  recentDirection: string
}

export interface B649OwnerMatrixDefinition extends B649OwnerMetadata {
  prefixCount: B649PrefixCount
}

export interface B649OwnerLeaderDefinition {
  strategyToken: string
  label: string
  note: string
}

export interface B649OwnerRankingData {
  summary: B649MultiTicketSummary
  records: B649MultiTicketRecord[]
}

export const B649_OWNER_RANKING_CRITERION = 'M3_PLUS' as const
const OWNER_PAGE_SIZE = 100

export const R2_BASELINE_SNAPSHOT: Record<
  B649PrefixCount,
  { full: string; recent750: string; recent300: string; recent50: string }
> = {
  5: { full: '20/20', recent750: '20/20', recent300: '20/20', recent50: '20/20' },
  10: { full: '18/20', recent750: '14/20', recent300: '11/20', recent50: '20/20' },
  15: { full: '6/20', recent750: '7/20', recent300: '6/20', recent50: '20/20' },
  20: { full: '2/20', recent750: '3/20', recent300: '5/20', recent50: '10/20' },
}

export interface B649OwnerSnapshot {
  rank: number
  rate: string
  coverage: string
  observations: number
  delta: string
}

// R2 identifies this strategy as portfolio_optimizer. The current projection has a
// different backtest_biglotto_portfolio utility strategy, so do not alias the two.
export const R2_PORTFOLIO_SNAPSHOT: Partial<
  Record<B649PrefixCount, Partial<Record<B649HistoryWindow, B649OwnerSnapshot>>>
> = {
  15: {
    FULL: { rank: 14, rate: '0.384000000000000000', coverage: '0.906900000000000000', observations: 1949, delta: '-0.009700000000000000' },
    RECENT_750: { rank: 6, rate: '0.384000000000000000', coverage: '1.000000000000000000', observations: 750, delta: '0.008000000000000000' },
    RECENT_300: { rank: 3, rate: '0.386700000000000000', coverage: '1.000000000000000000', observations: 300, delta: '0.010700000000000000' },
    RECENT_50: { rank: 9, rate: '0.440000000000000000', coverage: '1.000000000000000000', observations: 50, delta: '0.064000000000000000' },
  },
  20: {
    FULL: { rank: 17, rate: '0.461300000000000000', coverage: '0.906900000000000000', observations: 1949, delta: '-0.031700000000000000' },
    RECENT_750: { rank: 6, rate: '0.461300000000000000', coverage: '1.000000000000000000', observations: 750, delta: '-0.005400000000000000' },
    RECENT_300: { rank: 2, rate: '0.476700000000000000', coverage: '1.000000000000000000', observations: 300, delta: '0.009900000000000000' },
    RECENT_50: { rank: 9, rate: '0.480000000000000000', coverage: '1.000000000000000000', observations: 50, delta: '0.013200000000000000' },
  },
}

export const R2_CORE_OBSERVATIONS: Record<B649PrefixCount, readonly B649OwnerMetadata[]> = {
  5: [
    {
      strategyToken: 'backtest_biglotto_coldpool_15',
      label: 'coldpool_15',
      role: 'CORE_REGIME',
      recentDirection: 'recent rank returns to FULL level',
    },
    {
      strategyToken: 'analyze_prediction_115000019',
      label: 'analyze_prediction_115000019',
      role: 'STABLE_CORE',
      recentDirection: 'RECENT_50 higher than FULL',
    },
    {
      strategyToken: 'edge_splicer_5bet',
      label: 'edge_splicer_5bet',
      role: 'STABLE_CORE',
      recentDirection: 'RECENT_50 higher than FULL',
    },
  ],
  10: [
    {
      strategyToken: 'backtest_biglotto_6bet_ewma',
      label: '6bet_ewma',
      role: 'STABLE_CORE',
      recentDirection: 'stable with positive recent deltas',
    },
    {
      strategyToken: 'backtest_biglotto_coldpool_15',
      label: 'coldpool_15',
      role: 'STABLE_CORE',
      recentDirection: 'stable with positive recent deltas',
    },
    {
      strategyToken: 'analyze_prediction_115000019',
      label: 'analyze_prediction_115000019',
      role: 'STABLE_CORE',
      recentDirection: 'RECENT_50 remains Top 20',
    },
    {
      strategyToken: 'smart_multi_bet',
      label: 'smart_multi_bet',
      role: 'WATCH',
      recentDirection: 'RECENT_DETERIORATION after strong 750/300 ranks',
    },
  ],
  15: [
    {
      strategyToken: 'backtest_biglotto_6bet_ewma',
      label: '6bet_ewma',
      role: 'CORE_REGIME',
      recentDirection: 'recent movement is not four-window stability',
    },
    {
      strategyToken: 'backtest_biglotto_coldpool_15',
      label: 'coldpool_15',
      role: 'STABLE_CORE',
      recentDirection: 'stable across four windows',
    },
    {
      strategyToken: 'portfolio_optimizer',
      label: 'portfolio_optimizer',
      role: 'STABLE_CORE',
      recentDirection: 'stable rank, FULL below random',
    },
    {
      strategyToken: 'orthogonal_diversification_benchmark',
      label: 'orthogonal_diversification_benchmark',
      role: 'STABLE_CORE',
      recentDirection: 'stable rank, recent 50 positive',
    },
  ],
  20: [
    {
      strategyToken: 'orthogonal_diversification_benchmark',
      label: 'orthogonal_diversification_benchmark',
      role: 'STABLE_CORE',
      recentDirection: 'RECENT_MOVER with broad coverage',
    },
    {
      strategyToken: 'backtest_biglotto_6bet_ewma',
      label: '6bet_ewma',
      role: 'STABLE_CORE',
      recentDirection: 'recent 50 remains positive',
    },
    {
      strategyToken: 'backtest_biglotto_coldpool_15',
      label: 'coldpool_15',
      role: 'CORE_REGIME',
      recentDirection: 'recent 50 above baseline, FULL below',
    },
    {
      strategyToken: 'portfolio_optimizer',
      label: 'portfolio_optimizer',
      role: 'STABLE_CORE',
      recentDirection: 'stable rank, FULL/750 below random',
    },
  ],
}

export const R2_SHORT_TERM_HIGH_COVERAGE_LEADERS: Record<
  B649PrefixCount,
  B649OwnerLeaderDefinition
> = {
  5: {
    strategyToken: 'big_lotto_exhaustive_audit',
    label: 'big_lotto_exhaustive_audit',
    note: 'RECENT_50 #1 with 100% coverage',
  },
  10: {
    strategyToken: 'backtest_biglotto_coldpool_15',
    label: 'coldpool_15',
    note: 'RECENT_50 #2 with 100% coverage; #1 is sparse',
  },
  15: {
    strategyToken: 'backtest_biglotto_coldpool_15',
    label: 'coldpool_15',
    note: 'RECENT_50 #2 with 100% coverage; #1 is sparse',
  },
  20: {
    strategyToken: 'covering_strategy_research',
    label: 'covering_strategy_research',
    note: 'RECENT_50 #1 with 100% coverage',
  },
}

export const R2_REGIME_CANDIDATES: Record<B649PrefixCount, readonly string[]> = {
  5: ['coldpool_15', 'analyze_prediction_115000019', 'edge_splicer_5bet', 'big_lotto_exhaustive_audit'],
  10: ['6bet_ewma', 'coldpool_15', 'analyze_prediction_115000019', 'smart_multi_bet'],
  15: [
    '6bet_ewma',
    'coldpool_15',
    'portfolio_optimizer',
    'orthogonal_diversification_benchmark',
    'backtest_sum_constraint',
  ],
  20: [
    'orthogonal_diversification_benchmark',
    '6bet_ewma',
    'coldpool_15',
    'portfolio_optimizer',
    'covering_strategy_research',
    'backtest_sum_constraint',
  ],
}

export const R2_OWNER_MATRIX: readonly B649OwnerMatrixDefinition[] = [
  { prefixCount: 5, strategyToken: 'analyze_prediction_115000019', label: 'analyze_prediction_115000019', role: 'STABLE_CORE', recentDirection: 'RECENT_50 higher than FULL' },
  { prefixCount: 5, strategyToken: 'edge_splicer_5bet', label: 'edge_splicer_5bet', role: 'STABLE_CORE', recentDirection: 'RECENT_50 higher than FULL' },
  { prefixCount: 5, strategyToken: 'backtest_biglotto_coldpool_15', label: 'coldpool_15', role: 'CORE_REGIME', recentDirection: 'recent rank returns to FULL level' },
  { prefixCount: 5, strategyToken: 'big_lotto_exhaustive_audit', label: 'big_lotto_exhaustive_audit', role: 'RECENT_MOVER', recentDirection: 'RECENT_IMPROVEMENT' },
  { prefixCount: 5, strategyToken: 'quick_ml_predict', label: 'quick_ml_predict', role: 'LOW_COVERAGE_CONTROL', recentDirection: 'RECENT_NO_OBS' },
  { prefixCount: 10, strategyToken: 'backtest_biglotto_6bet_ewma', label: '6bet_ewma', role: 'STABLE_CORE', recentDirection: 'stable with positive recent deltas' },
  { prefixCount: 10, strategyToken: 'backtest_biglotto_coldpool_15', label: 'coldpool_15', role: 'STABLE_CORE', recentDirection: 'stable with positive recent deltas' },
  { prefixCount: 10, strategyToken: 'analyze_prediction_115000019', label: 'analyze_prediction_115000019', role: 'STABLE_CORE', recentDirection: 'RECENT_50 remains Top 20' },
  { prefixCount: 10, strategyToken: 'smart_multi_bet', label: 'smart_multi_bet', role: 'WATCH', recentDirection: 'RECENT_DETERIORATION after strong 750/300 ranks' },
  { prefixCount: 10, strategyToken: 'research_cluster_enhancements', label: 'research_cluster_enhancements', role: 'LOW_COVERAGE_CONTROL', recentDirection: 'volatile sparse movement' },
  { prefixCount: 15, strategyToken: 'backtest_biglotto_6bet_ewma', label: '6bet_ewma', role: 'CORE_REGIME', recentDirection: 'recent movement is not four-window stability' },
  { prefixCount: 15, strategyToken: 'backtest_biglotto_coldpool_15', label: 'coldpool_15', role: 'STABLE_CORE', recentDirection: 'stable across four windows' },
  { prefixCount: 15, strategyToken: 'portfolio_optimizer', label: 'portfolio_optimizer', role: 'STABLE_CORE', recentDirection: 'stable rank, FULL below random' },
  { prefixCount: 15, strategyToken: 'orthogonal_diversification_benchmark', label: 'orthogonal_diversification_benchmark', role: 'STABLE_CORE', recentDirection: 'stable rank, recent 50 positive' },
  { prefixCount: 15, strategyToken: 'quantum_random_predictor', label: 'quantum_random_predictor', role: 'NEGATIVE_CONTROL', recentDirection: 'short-window lift with mixed deltas' },
  { prefixCount: 15, strategyToken: 'backtest_sum_constraint', label: 'backtest_sum_constraint', role: 'RECENT_MOVER', recentDirection: 'RECENT_IMPROVEMENT' },
  { prefixCount: 20, strategyToken: 'backtest_biglotto_6bet_ewma', label: '6bet_ewma', role: 'STABLE_CORE', recentDirection: 'recent 50 remains positive' },
  { prefixCount: 20, strategyToken: 'backtest_biglotto_coldpool_15', label: 'coldpool_15', role: 'CORE_REGIME', recentDirection: 'recent 50 above baseline, FULL below' },
  { prefixCount: 20, strategyToken: 'portfolio_optimizer', label: 'portfolio_optimizer', role: 'STABLE_CORE', recentDirection: 'stable rank, FULL/750 below random' },
  { prefixCount: 20, strategyToken: 'orthogonal_diversification_benchmark', label: 'orthogonal_diversification_benchmark', role: 'STABLE_CORE', recentDirection: 'RECENT_MOVER with broad coverage' },
  { prefixCount: 20, strategyToken: 'covering_strategy_research', label: 'covering_strategy_research', role: 'RECENT_MOVER', recentDirection: 'RECENT_MOVER' },
  { prefixCount: 20, strategyToken: 'backtest_sum_constraint', label: 'backtest_sum_constraint', role: 'RECENT_MOVER', recentDirection: 'RECENT_IMPROVEMENT' },
  { prefixCount: 20, strategyToken: 'quantum_random_predictor', label: 'quantum_random_predictor', role: 'NEGATIVE_CONTROL', recentDirection: 'mixed baseline relation' },
  { prefixCount: 20, strategyToken: 'quick_ml_predict', label: 'quick_ml_predict', role: 'LOW_COVERAGE_CONTROL', recentDirection: 'RECENT_NO_OBS' },
  { prefixCount: 20, strategyToken: 'research_cluster_enhancements', label: 'research_cluster_enhancements', role: 'LOW_COVERAGE_CONTROL', recentDirection: 'volatile sparse movement' },
]

export async function fetchB649OwnerRankingData(
  signal?: AbortSignal,
): Promise<B649OwnerRankingData> {
  const summary = await fetchB649MultiTicketSummary(signal)
  if (!summary.records_available) {
    throw new B649RecordsRequestError(
      'The checksum-pinned B649 ranking projection is unavailable.',
      503,
      'UNAVAILABLE',
      'B649_MULTI_TICKET_RECORDS_UNAVAILABLE',
    )
  }

  const slices = await Promise.all(
    B649_PREFIX_COUNTS.flatMap((prefixCount) =>
      B649_HISTORY_WINDOWS.map((window) =>
        fetchAllRows(prefixCount, window, signal),
      ),
    ),
  )

  return { summary, records: slices.flat() }
}

async function fetchAllRows(
  prefixCount: B649PrefixCount,
  window: B649HistoryWindow,
  signal?: AbortSignal,
): Promise<B649MultiTicketRecord[]> {
  const firstPage = await fetchB649MultiTicketRecords(
    {
      prefixCount,
      window,
      criterion: B649_OWNER_RANKING_CRITERION,
      limit: OWNER_PAGE_SIZE,
      offset: 0,
    },
    signal,
  )
  if (firstPage.items.length >= firstPage.total) return firstPage.items

  const offsets = []
  for (let offset = firstPage.items.length; offset < firstPage.total; offset += OWNER_PAGE_SIZE) {
    offsets.push(offset)
  }
  const remaining = await Promise.all(
    offsets.map((offset) =>
      fetchB649MultiTicketRecords(
        {
          prefixCount,
          window,
          criterion: B649_OWNER_RANKING_CRITERION,
          limit: OWNER_PAGE_SIZE,
          offset,
        },
        signal,
      ),
    ),
  )
  return [firstPage, ...remaining].flatMap((page) => page.items)
}
