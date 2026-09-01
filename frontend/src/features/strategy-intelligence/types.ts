import type { LifecycleStatus, LotteryType } from '../../api/strategies'

export type StrategyIntelligenceTab = 'overview' | 'portfolio' | 'd3'

export type CanonicalLotteryCode = 'B649' | 'P638' | 'T539'
export type GameFilter = 'ALL' | CanonicalLotteryCode
export type LifecycleFilter = 'ALL' | LifecycleStatus
export type ExecutableFilter = '' | 'true' | 'false'
export type EvidenceStatusFilter = 'ALL' | 'REGISTERED' | 'MISSING'
export type ViewMode = 'table' | 'cards'

export interface GameOption {
  code: CanonicalLotteryCode
  lotteryType: LotteryType
  name: string
  fullName: string
}

export const GAME_OPTIONS: readonly GameOption[] = [
  { code: 'B649', lotteryType: 'BIG_LOTTO', name: 'Big Lotto', fullName: 'Big Lotto 6/49' },
  { code: 'P638', lotteryType: 'POWER_LOTTO', name: 'Power Lotto', fullName: 'Power Lotto 6/38' },
  { code: 'T539', lotteryType: 'DAILY_539', name: 'Daily Cash 5/39', fullName: 'Daily Cash 5/39' },
] as const

export interface StrategyCombinedItem {
  strategyId: string
  displayName: string
  version: string
  supportedLotteryTypes: readonly LotteryType[]
  gameLabels: string[]
  minimumHistory: number
  lifecycleStatus: LifecycleStatus
  executable: boolean
  provenance: readonly string[]
  adapterAvailable: boolean
  registrationStatus: string
  definitionStatus: string
  verificationStatus: string
  empiricalEligibility: 'EMPIRICAL INELIGIBLE' | 'EMPIRICAL ELIGIBLE'
  evidenceStatus: 'CANONICAL EVIDENCE REGISTERED' | 'CANONICAL EVIDENCE MISSING'
  unavailableReasonCode: string | null
}

export interface PortfolioGameEvidenceRow {
  game: 'B649' | 'P638' | 'T539'
  gameName: string
  portfolioId: string | null
  includedStrategies: string[]
  portfolioSize: number | null
  evaluatedTargets: number | null
  unionHitRate: string | null
  bestComparator: string | null
  marginalContribution: string | null
  diversityMetric: string | null
  horizon: string | null
  evidenceStatus: 'EVIDENCE UNAVAILABLE' | 'EXCLUDED' | 'EVIDENCE AVAILABLE'
  reasonCode: string
}

export interface D3MetricDefinitionInfo {
  metricId: string
  metricVersion: string
  schemaId: string
  schemaVersion: string
  formulaStatus: string
  direction: string
  aggregation: string
  sampleUnit: string
  decimalScale: number
  roundingMode: string
  unit: string
  definitionProse: string
  authorityPath: string
}
