<script setup lang="ts">
import { computed } from 'vue'

import MetricCard from '../../components/MetricCard.vue'
import SectionHeader from '../../components/SectionHeader.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import { lotteryTypeDisplayLabel } from '../../utils/lotteryDisplayLabel'
import type { LotteryType } from '../../api/strategies'
import type { StrategyCombinedItem } from './types'

const props = withDefaults(
  defineProps<{
    selectedLotteryType?: LotteryType
    combinationStatus?: string
    combinationValue?: string
    combinationOwner?: string
    strategies?: StrategyCombinedItem[]
  }>(),
  {
    selectedLotteryType: 'BIG_LOTTO',
    combinationStatus: 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE',
    combinationValue: 'NOT_AVAILABLE',
    combinationOwner: 'ACTIVE_MULTITICKET_AGENT',
    strategies: () => [],
  },
)

const currentGameCode = computed(() => lotteryTypeDisplayLabel(props.selectedLotteryType))

const currentGameFullName = computed(() => {
  switch (props.selectedLotteryType) {
    case 'BIG_LOTTO':
      return 'Big Lotto 6/49'
    case 'POWER_LOTTO':
      return 'Power Lotto 6/38'
    case 'DAILY_539':
      return 'Daily Cash 5/39'
  }
})

const totalCandidateStrategies = computed(() => props.strategies.length)
</script>

<template>
  <div class="strategy-portfolio-workspace">
    <!-- Top Status & Governance Banner -->
    <div class="portfolio-governance-panel">
      <div class="governance-header">
        <div>
          <p class="step-label">Strategy Combination Hit Rate · Evidence Boundary</p>
          <h2>Registry-wide Combination Evidence Boundary</h2>
          <p class="governance-desc">
            Multi-strategy combination evaluation answers: <em>"What is known about combining strategies?"</em>.
            No canonical combination metric is exposed by the current strategy-evidence contract.
            The active evidence contract defines a registry-wide boundary without game-specific portfolio records.
          </p>
        </div>
        <div class="scope-card" aria-label="Portfolio evidence status">
          <span>Registry Combination Scope</span>
          <strong>{{ combinationStatus }}</strong>
          <small>Value: {{ combinationValue }} · Owner: {{ combinationOwner }}</small>
        </div>
      </div>

      <div class="metrics-grid">
        <MetricCard
          label="Portfolio Hit Rate"
          :value="combinationValue"
          :subvalue="`Status: ${combinationStatus}`"
          variant="warning"
          :badge="combinationStatus"
          badge-variant="warning"
        />
        <MetricCard
          label="Active Governance"
          :value="combinationOwner"
          subvalue="Registry combination authority"
          variant="default"
        />
        <MetricCard
          label="Selected Catalog Context"
          :value="`${currentGameCode} (${currentGameFullName})`"
          :subvalue="`${totalCandidateStrategies} individual candidate strategies`"
          variant="accent"
        />
        <MetricCard
          label="Candidate Pool"
          :value="totalCandidateStrategies"
          :subvalue="`Supported in ${currentGameCode}`"
          variant="default"
        />
      </div>
    </div>

    <!-- Research Protocol Guard Banner -->
    <div class="research-guard-banner" role="note">
      <span class="guard-icon" aria-hidden="true">🔒</span>
      <div class="guard-content">
        <strong>Strict Quantitative Guard:</strong>
        Combinatorial and multi-strategy hit rates cannot be derived from isolated single-strategy summary numbers.
        No portfolio optimization formula or oracle selector is synthesized without frozen canonical artifacts.
        Missing portfolio metrics are displayed explicitly as <code>UNAVAILABLE</code> rather than zero.
      </div>
    </div>

    <!-- Registry-wide Combination Evidence Boundary -->
    <SectionHeader
      title="Registry-wide Combination Evidence Boundary"
      eyebrow="Evidence Authority Boundary"
      description="Evaluated combination evidence exposed by the canonical strategy-evidence contract."
    />

    <div class="boundary-panel" data-testid="portfolio-evidence-boundary">
      <div class="boundary-grid">
        <div class="boundary-card">
          <span class="boundary-label">Combination Status</span>
          <div class="boundary-status-wrapper">
            <StatusBadge :status="combinationStatus" variant="warning" size="sm" />
            <code class="boundary-code">{{ combinationStatus }}</code>
          </div>
          <small class="boundary-hint">Registry-wide scope status from canonical contract.</small>
        </div>

        <div class="boundary-card">
          <span class="boundary-label">Combination Value</span>
          <strong class="boundary-value font-mono">{{ combinationValue }}</strong>
          <small class="boundary-hint">No multi-strategy hit rate is computed or assumed.</small>
        </div>

        <div class="boundary-card">
          <span class="boundary-label">Combination Authority / Owner</span>
          <span class="boundary-owner font-mono">{{ combinationOwner }}</span>
          <small class="boundary-hint">Assigned quantitative governance domain.</small>
        </div>

        <div class="boundary-card boundary-card--context">
          <span class="boundary-label">Selected Catalog Context</span>
          <div class="context-indicator">
            <span class="game-tag">{{ currentGameCode }}</span>
            <span class="game-full-name">{{ currentGameFullName }}</span>
          </div>
          <small class="boundary-hint">
            Catalog context only ({{ totalCandidateStrategies }} candidate strategies). The combination evidence boundary is registry-wide and not evaluated per game.
          </small>
        </div>
      </div>
    </div>

    <!-- Detailed Evidence Registry Explanatory Section -->
    <article class="panel registry-details-panel">
      <div class="panel__heading">
        <p class="step-label">Evidence Registry Specification</p>
        <h3>Why is Portfolio Hit Rate Unavailable?</h3>
      </div>
      <div class="registry-reasons">
        <div class="reason-card">
          <h4>01 · Contract Boundary Scope</h4>
          <p>
            No canonical combination metric is exposed by the current strategy-evidence contract.
          </p>
        </div>
        <div class="reason-card">
          <h4>02 · No Optimization Policy Synthesis</h4>
          <p>
            The system forbids generating unverified optimization policies or computing heuristic combinations
            without frozen ranking artifacts.
          </p>
        </div>
        <div class="reason-card">
          <h4>03 · Replay History is Non-Ex-Ante</h4>
          <p>
            Post-hoc replay ranking artifacts are descriptive historical records and are not converted into forward
            portfolio hit-rate claims.
          </p>
        </div>
      </div>
    </article>
  </div>
</template>

<style scoped>
.strategy-portfolio-workspace {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.portfolio-governance-panel {
  padding: 24px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  background: var(--bg-card);
  backdrop-filter: blur(18px);
  box-shadow: var(--shadow-md);
}

.governance-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}

.governance-header h2 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
}

.governance-desc {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.5;
  max-width: 720px;
}

.research-guard-banner {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 20px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(35, 20, 50, 0.7) 0%, rgba(13, 17, 28, 0.7) 100%);
  border: 1px solid rgba(139, 92, 246, 0.3);
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.55;
}

.guard-icon {
  font-size: 20px;
  flex-shrink: 0;
  margin-top: 1px;
}

.guard-content strong {
  color: var(--text-primary);
  display: inline;
  margin-right: 4px;
}

.guard-content code {
  color: var(--text-accent);
}

.boundary-panel {
  padding: 20px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  backdrop-filter: blur(12px);
}

.boundary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.boundary-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: rgba(12, 17, 28, 0.6);
}

.boundary-card--context {
  border-left: 3px solid rgba(56, 189, 248, 0.6);
}

.boundary-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.boundary-status-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.boundary-code {
  font-size: 10px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}

.boundary-value {
  font-size: 18px;
  color: var(--text-primary);
}

.boundary-owner {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
}

.boundary-hint {
  font-size: 11.5px;
  color: var(--text-tertiary);
  line-height: 1.4;
  margin-top: auto;
}

.context-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.game-tag {
  display: inline-block;
  padding: 3px 6px;
  border-radius: var(--radius-sm);
  background: rgba(56, 189, 248, 0.12);
  border: 1px solid rgba(56, 189, 248, 0.25);
  color: #38bdf8;
  font: 700 10.5px/1 var(--font-mono);
  width: fit-content;
}

.game-full-name {
  color: var(--text-secondary);
  font-size: 11px;
}

.registry-details-panel {
  margin-top: 8px;
}

.registry-reasons {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.reason-card {
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: rgba(12, 17, 28, 0.6);
}

.reason-card h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.reason-card p {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.reason-card code {
  color: var(--text-accent);
}

</style>
