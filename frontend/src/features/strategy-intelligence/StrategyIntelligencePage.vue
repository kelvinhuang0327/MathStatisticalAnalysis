<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  queryStrategyOverview,
  type LotteryType,
  type StrategyOverviewResponse,
} from '../../api/strategies'
import {
  queryStrategyEvidence,
  type StrategyEvidenceResponse,
} from '../../api/strategyEvidence'
import { lotteryTypeDisplayLabel } from '../../utils/lotteryDisplayLabel'
import ErrorState from '../../components/ErrorState.vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionHeader from '../../components/SectionHeader.vue'
import SkeletonLoader from '../../components/SkeletonLoader.vue'

import StrategyIntelligenceD3 from './StrategyIntelligenceD3.vue'
import StrategyIntelligenceOverview from './StrategyIntelligenceOverview.vue'
import StrategyIntelligencePortfolio from './StrategyIntelligencePortfolio.vue'
import {
  GAME_OPTIONS,
  type StrategyCombinedItem,
  type StrategyIntelligenceTab,
} from './types'

type LoadState = 'loading' | 'ready' | 'error'

const activeTab = ref<StrategyIntelligenceTab>('overview')
const selectedLotteryType = ref<LotteryType>('BIG_LOTTO')
const loadState = ref<LoadState>('loading')
const errorMessage = ref('')

const overviewData = ref<StrategyOverviewResponse | null>(null)
const evidenceData = ref<StrategyEvidenceResponse | null>(null)

let requestController: AbortController | undefined
let requestGeneration = 0
let isMounted = false

const currentGameCode = computed(() => lotteryTypeDisplayLabel(selectedLotteryType.value))

const combinedStrategies = computed<StrategyCombinedItem[]>(() => {
  if (!overviewData.value) return []
  const evidenceItems = evidenceData.value?.items ?? []
  const evidenceMap = new Map(
    evidenceItems.map((e) => [`${e.strategy_id}::${e.strategy_version}`, e]),
  )

  return overviewData.value.items.map((item) => {
    const matchedEvidence = evidenceMap.get(`${item.strategy_id}::${item.version}`)
    const regStatus = matchedEvidence?.registration_status ?? 'CANONICAL_EVIDENCE_MISSING'
    const verStatus = matchedEvidence?.verification_status ?? 'EVIDENCE_MISSING'
    const isRegistered = regStatus === 'CANONICAL_EVIDENCE_REGISTERED'
    const isVerified = verStatus === 'EVIDENCE_VERIFIED'

    return {
      strategyId: item.strategy_id,
      displayName: item.display_name,
      version: item.version,
      supportedLotteryTypes: item.supported_lottery_types,
      gameLabels: item.supported_lottery_types.map(lotteryTypeDisplayLabel),
      minimumHistory: item.minimum_history,
      lifecycleStatus: item.lifecycle_status,
      executable: item.executable,
      provenance: item.provenance,
      adapterAvailable: matchedEvidence?.adapter_available ?? false,
      registrationStatus: regStatus,
      definitionStatus: matchedEvidence?.definition_status ?? 'DEFINITION_AVAILABLE',
      verificationStatus: verStatus,
      empiricalEligibility: isRegistered && isVerified ? 'EMPIRICAL ELIGIBLE' : 'EMPIRICAL INELIGIBLE',
      evidenceStatus: isRegistered ? 'CANONICAL EVIDENCE REGISTERED' : 'CANONICAL EVIDENCE MISSING',
      unavailableReasonCode: matchedEvidence?.unavailable_reason_code ?? 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE',
    }
  })
})

const evidenceReadyCount = computed(() => {
  return combinedStrategies.value.filter(
    (item) => item.registrationStatus === 'CANONICAL_EVIDENCE_REGISTERED',
  ).length
})

const empiricalEligibleCount = computed(() => {
  return combinedStrategies.value.filter(
    (item) => item.empiricalEligibility === 'EMPIRICAL ELIGIBLE',
  ).length
})

const summary = computed(() => {
  const total = overviewData.value?.summary.total ?? 0
  const executable = overviewData.value?.summary.executable_count ?? 0
  const metadataOnly = overviewData.value?.summary.metadata_only_count ?? 0
  const lifecycleCounts = overviewData.value?.summary.lifecycle_counts ?? {
    IDEA: 0,
    OBSERVATION: 0,
    ONLINE: 0,
    REJECTED: 0,
    RETIRED: 0,
  }
  const unavailableReasons = overviewData.value?.capabilities.unavailable_reason_codes ?? [
    'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE',
  ]
  const bestStrategyStatus = evidenceData.value?.best_strategy.status ?? 'UNAVAILABLE'
  const bestStrategyReason = evidenceData.value?.best_strategy.reason ?? 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE'
  const d3Status = evidenceData.value?.d3.status ?? 'RESERVED_UNAVAILABLE'
  const d3Value = evidenceData.value?.d3.value ?? 'NOT_AVAILABLE'
  const portfolioStatus = evidenceData.value?.strategy_combination_hit_rate.status ?? 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE'
  const portfolioValue = evidenceData.value?.strategy_combination_hit_rate.value ?? 'NOT_AVAILABLE'
  const portfolioOwner = evidenceData.value?.strategy_combination_hit_rate.owner ?? 'ACTIVE_MULTITICKET_AGENT'

  return {
    total,
    executable,
    metadataOnly,
    lifecycleCounts,
    unavailableReasons,
    bestStrategyStatus,
    bestStrategyReason,
    d3Status,
    d3Value,
    portfolioStatus,
    portfolioValue,
    portfolioOwner,
  }
})

async function loadData(): Promise<void> {
  const generation = ++requestGeneration
  requestController?.abort()
  const controller = new AbortController()
  requestController = controller

  loadState.value = 'loading'
  errorMessage.value = ''
  overviewData.value = null

  try {
    const [overviewResponse, evidenceResponse] = await Promise.all([
      queryStrategyOverview(
        { lottery_type: selectedLotteryType.value },
        controller.signal,
      ),
      queryStrategyEvidence(controller.signal),
    ])

    if (!isMounted || generation !== requestGeneration || controller.signal.aborted) return

    overviewData.value = overviewResponse
    evidenceData.value = evidenceResponse
    loadState.value = 'ready'
  } catch (error: unknown) {
    if (!isMounted || generation !== requestGeneration || controller.signal.aborted) return
    errorMessage.value =
      error instanceof Error ? error.message : 'Unable to load Strategy Intelligence data.'
    loadState.value = 'error'
  }
}

function selectGame(lotteryType: LotteryType): void {
  if (selectedLotteryType.value === lotteryType && loadState.value === 'ready') return
  selectedLotteryType.value = lotteryType
  void loadData()
}

onMounted(() => {
  isMounted = true
  void loadData()
})

onBeforeUnmount(() => {
  isMounted = false
  requestGeneration += 1
  requestController?.abort()
})
</script>

<template>
  <section class="workspace-page" aria-labelledby="strategy-intelligence-title">
    <SectionHeader
      id="strategy-intelligence-title"
      title="Strategy Intelligence"
      eyebrow="Quantitative Strategy Discovery & Validation"
      description="Unified strategy catalog, portfolio hit rate evaluation, and canonical D3 Single Source of Truth validation gates."
    >
      <template #actions>
        <div class="tab-list" role="tablist" aria-label="Strategy Intelligence Sections">
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeTab === 'overview', 'button--quiet': activeTab !== 'overview' }"
            :aria-pressed="activeTab === 'overview'"
            :aria-selected="activeTab === 'overview'"
            role="tab"
            @click="activeTab = 'overview'"
          >
            Overview
          </button>
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeTab === 'portfolio', 'button--quiet': activeTab !== 'portfolio' }"
            :aria-pressed="activeTab === 'portfolio'"
            :aria-selected="activeTab === 'portfolio'"
            role="tab"
            @click="activeTab = 'portfolio'"
          >
            Portfolio Hit Rate
          </button>
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeTab === 'd3', 'button--quiet': activeTab !== 'd3' }"
            :aria-pressed="activeTab === 'd3'"
            :aria-selected="activeTab === 'd3'"
            role="tab"
            @click="activeTab = 'd3'"
          >
            D3 SSOT
          </button>
        </div>
      </template>
    </SectionHeader>

    <!-- Game Scope Selector -->
    <div class="game-selector-container" role="region" aria-label="Game Scope Selection">
      <div class="game-selector-bar">
        <span class="game-selector-label">Game Scope:</span>
        <div class="game-selector-group" role="radiogroup" aria-label="Lottery Game Scope">
          <button
            v-for="game in GAME_OPTIONS"
            :key="game.code"
            type="button"
            class="button game-selector-btn"
            :class="{
              'button--primary': selectedLotteryType === game.lotteryType,
              'button--quiet': selectedLotteryType !== game.lotteryType,
            }"
            :aria-checked="selectedLotteryType === game.lotteryType"
            :data-testid="`game-selector-${game.code.toLowerCase()}`"
            role="radio"
            @click="selectGame(game.lotteryType)"
          >
            <span class="game-code">{{ game.code }}</span>
            <span class="game-name">{{ game.name }}</span>
          </button>
        </div>
        <div class="game-selector-dropdown">
          <label for="game-scope-select" class="sr-only">Select Lottery Game</label>
          <select
            id="game-scope-select"
            v-model="selectedLotteryType"
            class="select-input select-input--sm"
            data-testid="game-scope-select"
            @change="selectGame(selectedLotteryType)"
          >
            <option v-for="game in GAME_OPTIONS" :key="game.code" :value="game.lotteryType">
              {{ game.code }} ({{ game.fullName }})
            </option>
          </select>
        </div>
      </div>
    </div>

    <!-- Top Unified MetricCards Summary Row -->
    <div class="metrics-grid" data-testid="strategy-intelligence-metrics-grid">
      <MetricCard
        label="Total Strategies"
        :value="loadState === 'ready' ? summary.total : '—'"
        :subvalue="loadState === 'ready' ? `${summary.executable} executable · ${summary.metadataOnly} metadata only` : 'Loading…'"
        variant="accent"
      />
      <MetricCard
        label="Executable"
        :value="loadState === 'ready' ? summary.executable : '—'"
        subvalue="Online descriptor execution state"
        :variant="summary.executable > 0 ? 'success' : 'default'"
      />
      <MetricCard
        label="Evidence Ready"
        :value="loadState === 'ready' ? evidenceReadyCount : '—'"
        :subvalue="loadState === 'ready' ? (evidenceReadyCount > 0 ? `${evidenceReadyCount} registered evidence artifacts` : 'No canonical evidence registered') : 'Loading…'"
        :badge="evidenceReadyCount > 0 ? 'REGISTERED' : 'EVIDENCE UNAVAILABLE'"
        :badge-variant="evidenceReadyCount > 0 ? 'success' : 'default'"
        :variant="evidenceReadyCount > 0 ? 'success' : 'default'"
      />
      <MetricCard
        label="Empirical Eligible"
        :value="loadState === 'ready' ? empiricalEligibleCount : '—'"
        :subvalue="loadState === 'ready' ? `${empiricalEligibleCount} strategies pass canonical gate` : 'Loading…'"
        :badge="empiricalEligibleCount > 0 ? 'EMPIRICAL ELIGIBLE' : 'EMPIRICAL INELIGIBLE'"
        :badge-variant="empiricalEligibleCount > 0 ? 'success' : 'danger'"
        :variant="empiricalEligibleCount > 0 ? 'success' : 'default'"
      />
      <MetricCard
        label="Best Strategy"
        :value="loadState === 'ready' ? summary.bestStrategyStatus : '—'"
        :subvalue="loadState === 'ready' ? `Status: ${summary.bestStrategyStatus} · Evidence missing` : 'Loading…'"
        badge="UNAVAILABLE"
        badge-variant="warning"
        variant="warning"
      />
      <MetricCard
        label="Portfolio Hit Rate"
        :value="loadState === 'ready' ? summary.portfolioValue : '—'"
        :subvalue="loadState === 'ready' ? `Status: ${summary.portfolioStatus}` : 'Loading…'"
        badge="EXCLUDED"
        badge-variant="warning"
        variant="warning"
      />
      <MetricCard
        label="D3 SSOT Status"
        :value="loadState === 'ready' ? summary.d3Status : '—'"
        :subvalue="loadState === 'ready' ? `Value: ${summary.d3Value}` : 'Loading…'"
        badge="RESERVED"
        badge-variant="default"
      />
    </div>

    <!-- Quantitative Research Disclaimer Banner -->
    <div class="research-protocol-banner" role="note">
      <span class="protocol-icon" aria-hidden="true">🛡️</span>
      <div class="protocol-content">
        <strong>Strict Evidence Protocol ({{ currentGameCode }}):</strong>
        Strategy Intelligence presents descriptive quantitative metadata, combination availability, and canonical D3 validation gates.
        Unavailable evidence is explicitly labeled as unavailable rather than zero. No prediction claims, ranking formulas, or heuristic bets are computed.
      </div>
    </div>

    <!-- Error State -->
    <ErrorState
      v-if="loadState === 'error'"
      title="Failed to load Strategy Intelligence workspace"
      :message="errorMessage"
      @retry="loadData"
    />

    <!-- Loading State -->
    <SkeletonLoader
      v-else-if="loadState === 'loading'"
      type="table"
      :rows="8"
      height="48px"
    />

    <!-- Ready Workspace Views -->
    <div v-else-if="loadState === 'ready'" class="tab-content-wrapper">
      <!-- Tab 1: Strategy Overview -->
      <div v-if="activeTab === 'overview'" role="tabpanel" aria-label="Strategy Overview">
        <StrategyIntelligenceOverview
          :items="combinedStrategies"
          :selected-lottery-type="selectedLotteryType"
          :total-count="summary.total"
          :executable-count="summary.executable"
          :metadata-only-count="summary.metadataOnly"
          :lifecycle-counts="summary.lifecycleCounts"
          :unavailable-reasons="summary.unavailableReasons"
          :best-strategy-status="summary.bestStrategyStatus"
          :best-strategy-reason="summary.bestStrategyReason"
        />
      </div>

      <!-- Tab 2: Portfolio Hit Rate -->
      <div v-else-if="activeTab === 'portfolio'" role="tabpanel" aria-label="Portfolio Hit Rate">
        <StrategyIntelligencePortfolio
          :selected-lottery-type="selectedLotteryType"
          :combination-status="summary.portfolioStatus"
          :combination-value="summary.portfolioValue"
          :combination-owner="summary.portfolioOwner"
          :strategies="combinedStrategies"
        />
      </div>

      <!-- Tab 3: D3 SSOT -->
      <div v-if="activeTab === 'd3'" role="tabpanel" aria-label="D3 SSOT">
        <StrategyIntelligenceD3
          :selected-lottery-type="selectedLotteryType"
          :d3-status="summary.d3Status"
          :d3-value="summary.d3Value"
          :strategies="combinedStrategies"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.workspace-page {
  padding-bottom: 48px;
}

.game-selector-container {
  margin-top: 16px;
  margin-bottom: 8px;
}

.game-selector-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 16px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  backdrop-filter: blur(12px);
}

.game-selector-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.game-selector-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.game-selector-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 13px;
  border-radius: var(--radius-md);
}

.game-code {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 0.02em;
}

.game-name {
  font-size: 12px;
  opacity: 0.85;
}

.game-selector-dropdown {
  margin-left: auto;
}

.select-input--sm {
  min-height: 32px;
  padding: 4px 8px;
  font-size: 12px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.research-protocol-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(30, 20, 50, 0.7) 0%, rgba(13, 17, 28, 0.7) 100%);
  border: 1px solid rgba(139, 92, 246, 0.25);
  margin-top: 20px;
  margin-bottom: 24px;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.protocol-icon {
  font-size: 18px;
  flex-shrink: 0;
  margin-top: 1px;
}

.protocol-content strong {
  color: var(--text-primary);
}

.tab-content-wrapper {
  margin-top: 8px;
}
</style>
