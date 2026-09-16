<script setup lang="ts">
import { computed } from 'vue'

import EmptyState from '../../../components/EmptyState.vue'
import StatusBadge from '../../../components/StatusBadge.vue'
import type { GameCode, ReplayExplorerItem } from '../types'

const props = withDefaults(
  defineProps<{
    game: GameCode
    items: ReplayExplorerItem[]
    selectedStrategyIds: string[]
    loading?: boolean
  }>(),
  {
    loading: false,
    selectedStrategyIds: () => [],
  },
)

const emit = defineEmits<{
  (e: 'remove-strategy', strategyId: string): void
  (e: 'inspect', item: ReplayExplorerItem): void
}>()

// Find items matching the compared strategies
const comparedItems = computed(() => {
  const selectedSet = new Set(props.selectedStrategyIds)
  const matched: ReplayExplorerItem[] = []
  const seen = new Set<string>()

  for (const it of props.items) {
    if (selectedSet.has(it.strategyId) && !seen.has(it.strategyId)) {
      matched.push(it)
      seen.add(it.strategyId)
    }
  }
  return matched.slice(0, 4) // Max 4 strategies
})
</script>

<template>
  <div class="replay-compare-view">
    <div v-if="comparedItems.length === 0" class="compare-empty">
      <EmptyState
        title="No Strategies Selected for Comparison"
        description="Select up to 4 strategies from the Table view or search list to inspect and compare side-by-side."
      />
    </div>

    <div v-else class="compare-grid-container">
      <div class="compare-header">
        <div>
          <h4 class="compare-title">Side-by-Side Replay Comparison</h4>
          <p class="compare-subtitle text-muted">
            Comparing {{ comparedItems.length }} of 4 strategies under the active configuration.
          </p>
        </div>
      </div>

      <div class="cards-grid">
        <div
          v-for="item in comparedItems"
          :key="item.id"
          class="compare-card"
          :class="{ 'card--unavailable': !item.isAvailable }"
        >
          <!-- Card Top -->
          <div class="card-top">
            <div class="card-strat-info">
              <span v-if="item.rank !== null" class="card-rank">#{{ item.rank }}</span>
              <h5 class="card-strat-name">{{ item.displayLabel }}</h5>
              <code class="card-strat-version">{{ item.strategyVersion }}</code>
            </div>
            <button
              type="button"
              class="remove-btn"
              title="Remove from comparison"
              @click="emit('remove-strategy', item.strategyId)"
            >
              ✕
            </button>
          </div>

          <!-- Evidence Status -->
          <div class="card-status-row">
            <StatusBadge
              :status="item.evidenceStatus"
              :variant="
                item.evidenceStatus === 'DESCRIPTIVE LEADER' || item.evidenceStatus === 'PARETO FRONTIER'
                  ? 'success'
                  : item.evidenceStatus === 'LOW POWER' || item.evidenceStatus === 'LIMITED SAMPLE'
                    ? 'warning'
                    : 'neutral'
              "
            />
            <span class="card-ticket-tag">{{ item.ticketCount }} Tickets</span>
          </div>

          <!-- Key Metrics List -->
          <div class="card-metrics-list">
            <div class="metric-row">
              <span class="metric-label text-muted">Historical Hit Rate</span>
              <strong class="metric-value metric-value--highlight">
                {{ item.hitRateFormatted }}
              </strong>
            </div>

            <div v-if="game === 'B649'" class="metric-row">
              <span class="metric-label text-muted">Baseline Delta</span>
              <span
                class="metric-value"
                :class="{
                  'delta--positive': item.baselineDelta !== null && item.baselineDelta > 0,
                  'delta--negative': item.baselineDelta !== null && item.baselineDelta < 0,
                }"
              >
                {{ item.baselineDeltaFormatted }}
              </span>
            </div>

            <div class="metric-row">
              <span class="metric-label text-muted">Period / Horizon</span>
              <span class="metric-value">{{ item.periodLabel }}</span>
            </div>

            <div class="metric-row">
              <span class="metric-label text-muted">Evaluated Targets</span>
              <span class="metric-value">{{ item.evaluatedTargets !== null ? item.evaluatedTargets.toLocaleString() : '—' }}</span>
            </div>

            <div class="metric-row">
              <span class="metric-label text-muted">Winning Targets</span>
              <span class="metric-value">{{ item.winningTargets !== null ? item.winningTargets.toLocaleString() : '—' }}</span>
            </div>

            <div class="metric-row">
              <span class="metric-label text-muted">Best Hit Level</span>
              <span class="metric-value best-hit-text">{{ item.bestHit }}</span>
            </div>
          </div>

          <!-- Prize Distribution (if available) -->
          <div v-if="item.prizeCounts" class="card-prize-summary">
            <span class="prize-summary-title text-muted">Prize Tier Hits:</span>
            <div class="prize-pills">
              <span v-if="item.prizeCounts.first > 0" class="prize-pill">1st: {{ item.prizeCounts.first }}</span>
              <span v-if="item.prizeCounts.second > 0" class="prize-pill">2nd: {{ item.prizeCounts.second }}</span>
              <span v-if="item.prizeCounts.third > 0" class="prize-pill">3rd: {{ item.prizeCounts.third }}</span>
              <span v-if="item.prizeCounts.fourth > 0" class="prize-pill">4th: {{ item.prizeCounts.fourth }}</span>
              <span v-if="item.prizeCounts.fifth > 0" class="prize-pill">5th: {{ item.prizeCounts.fifth }}</span>
            </div>
          </div>

          <!-- Notes -->
          <div class="card-notes text-muted">
            <small>{{ item.notes }}</small>
          </div>

          <!-- Card Actions -->
          <div class="card-bottom">
            <button
              type="button"
              class="button button--small button--primary full-width"
              @click="emit('inspect', item)"
            >
              Full Inspection
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.replay-compare-view {
  width: 100%;
}

.compare-grid-container {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 1.5rem;
}

.compare-header {
  margin-bottom: 1.5rem;
}

.compare-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--color-gray-100, #f1f5f9);
}

.compare-subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1.25rem;
}

.compare-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  transition: transform 0.15s ease, border-color 0.15s ease;
}

.compare-card:hover {
  border-color: rgba(99, 102, 241, 0.4);
}

.card--unavailable {
  opacity: 0.7;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.card-strat-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.card-rank {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-indigo-300, #a5b4fc);
}

.card-strat-name {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-gray-100, #f1f5f9);
  word-break: break-word;
}

.card-strat-version {
  font-size: 0.75rem;
  color: var(--color-gray-400, #94a3b8);
}

.remove-btn {
  background: none;
  border: none;
  color: var(--color-gray-400, #94a3b8);
  font-size: 0.9rem;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
}

.remove-btn:hover {
  color: var(--color-rose-400, #fb7185);
  background: rgba(244, 63, 94, 0.1);
}

.card-status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-ticket-tag {
  font-size: 0.8rem;
  color: var(--color-cyan-300, #67e8f9);
  background: rgba(6, 182, 212, 0.1);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
}

.card-metrics-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  background: rgba(15, 23, 42, 0.5);
  padding: 0.75rem;
  border-radius: 6px;
  font-size: 0.85rem;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-value--highlight {
  color: var(--color-cyan-300, #67e8f9);
  font-size: 0.95rem;
}

.best-hit-text {
  color: var(--color-gray-200, #e2e8f0);
}

.delta--positive {
  color: var(--color-emerald-400, #34d399);
  font-weight: 600;
}

.delta--negative {
  color: var(--color-rose-400, #fb7185);
}

.card-prize-summary {
  font-size: 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.prize-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.prize-pill {
  background: rgba(255, 255, 255, 0.05);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  color: var(--color-gray-300, #cbd5e1);
}

.card-notes {
  font-size: 0.75rem;
  line-height: 1.35;
  flex-grow: 1;
}

.card-bottom {
  margin-top: auto;
}

.full-width {
  width: 100%;
}

.text-muted {
  color: var(--color-gray-400, #94a3b8);
}
</style>
