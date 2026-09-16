<script setup lang="ts">
import StatusBadge from '../../components/StatusBadge.vue'
import {
  PRIMARY_TICKET_COUNTS,
  type BestReplayItem,
  type GameCode,
  type HorizonKey,
  type PrimaryTicketCount,
  type TicketCount,
} from './types'

const props = defineProps<{
  game: GameCode
  horizon: HorizonKey
  selectedTicketCount: TicketCount
  itemsByTicketCount: Record<PrimaryTicketCount, BestReplayItem | null>
}>()

const emit = defineEmits<{
  (e: 'select-ticket', count: PrimaryTicketCount): void
}>()
</script>

<template>
  <div class="one-to-five-overview" data-testid="one-to-five-overview">
    <div class="overview-header">
      <div class="overview-title-group">
        <h3 class="overview-title">1–5 Best Strategy Overview</h3>
        <span class="overview-subtitle">
          Canonical Rank #1 summary across 1–5 tickets for {{ props.game }} · {{ props.horizon }}
        </span>
      </div>
    </div>

    <div class="overview-grid" role="group" aria-label="1 to 5 Ticket Best Strategy Cards">
      <button
        v-for="count in PRIMARY_TICKET_COUNTS"
        :key="count"
        type="button"
        class="overview-card"
        :class="{
          'overview-card--selected': props.selectedTicketCount === count,
          'overview-card--available': props.itemsByTicketCount[count]?.isAvailable,
          'overview-card--unavailable': !props.itemsByTicketCount[count]?.isAvailable,
        }"
        :aria-pressed="props.selectedTicketCount === count"
        :data-testid="`overview-card-${count}`"
        @click="emit('select-ticket', count)"
      >
        <div class="card-top">
          <div class="ticket-badge">
            <span class="ticket-num">{{ count }}</span>
            <span class="ticket-label">Tickets</span>
          </div>
          <span
            v-if="props.itemsByTicketCount[count]?.isAvailable && props.itemsByTicketCount[count]?.rank"
            class="rank-chip"
          >
            Rank #{{ props.itemsByTicketCount[count]?.rank }}
          </span>
          <span v-else class="unavailable-chip">
            Unavailable
          </span>
        </div>

        <template v-if="props.itemsByTicketCount[count]?.isAvailable">
          <div class="strategy-identity">
            <strong class="strategy-id" :title="props.itemsByTicketCount[count]?.strategyId">
              {{ props.itemsByTicketCount[count]?.strategyId }}
            </strong>
            <small class="method-family">{{ props.itemsByTicketCount[count]?.methodFamily }}</small>
          </div>

          <div class="card-metrics">
            <div class="metric-row">
              <span class="metric-name">Hit Rate</span>
              <strong class="metric-value text-primary font-mono">
                {{ props.itemsByTicketCount[count]?.hitRateFormatted }}
              </strong>
            </div>
            <div class="metric-row">
              <span class="metric-name">Successes / Draws</span>
              <span class="metric-value font-mono">
                {{ props.itemsByTicketCount[count]?.winningTargets !== null ? props.itemsByTicketCount[count]?.winningTargets?.toLocaleString() : '—' }}
                /
                {{ props.itemsByTicketCount[count]?.evaluatedTargets?.toLocaleString() }}
              </span>
            </div>
            <div class="metric-row">
              <span class="metric-name">Baseline Delta</span>
              <span
                class="metric-value font-mono"
                :class="{
                  'text-success': (props.itemsByTicketCount[count]?.baselineDelta || 0) > 0,
                  'text-danger': (props.itemsByTicketCount[count]?.baselineDelta || 0) < 0,
                  'text-muted': props.itemsByTicketCount[count]?.baselineDelta === null,
                }"
              >
                {{ props.itemsByTicketCount[count]?.baselineDeltaFormatted }}
              </span>
            </div>
            <div v-if="props.itemsByTicketCount[count]?.coverage !== null" class="metric-row">
              <span class="metric-name">Coverage</span>
              <span class="metric-value font-mono">
                {{ (Number(props.itemsByTicketCount[count]?.coverage) * 100).toFixed(2) }}%
              </span>
            </div>
          </div>

          <div class="card-footer">
            <StatusBadge
              :status="props.itemsByTicketCount[count]?.evidenceStatus || 'EVIDENCE UNAVAILABLE'"
              size="sm"
            />
          </div>
        </template>

        <template v-else>
          <div class="unavailable-body">
            <div class="unavailable-icon" aria-hidden="true">🔒</div>
            <strong class="unavailable-heading">Evidence Unavailable</strong>
            <span class="reason-code-tag">
              {{ props.itemsByTicketCount[count]?.unavailableReasonCode || 'NO_CANONICAL_REPLAY_EVIDENCE' }}
            </span>
            <p class="unavailable-desc">
              {{ props.itemsByTicketCount[count]?.notes || `No canonical multi-ticket backtest evidence is recorded for ticket count ${count}.` }}
            </p>
          </div>
          <div class="card-footer">
            <StatusBadge status="EVIDENCE UNAVAILABLE" size="sm" />
          </div>
        </template>
      </button>
    </div>
  </div>
</template>

<style scoped>
.one-to-five-overview {
  margin-top: 24px;
  margin-bottom: 24px;
  background: rgba(13, 17, 28, 0.7);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 20px;
}

.overview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.overview-title-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.overview-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.overview-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 1024px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
}

.overview-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: rgba(18, 24, 38, 0.85);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: 220px;
  outline: none;
}

.overview-card:hover {
  border-color: var(--border-hover);
  background: rgba(24, 32, 50, 0.95);
  transform: translateY(-2px);
}

.overview-card--selected {
  border-color: var(--primary-color) !important;
  background: linear-gradient(180deg, rgba(124, 58, 237, 0.15) 0%, rgba(18, 24, 38, 0.95) 100%) !important;
  box-shadow: 0 0 16px rgba(124, 58, 237, 0.25);
}

.overview-card--unavailable {
  background: rgba(10, 14, 22, 0.6);
  border-style: dashed;
  opacity: 0.9;
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.ticket-badge {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}

.ticket-num {
  font: 800 18px/1 var(--font-mono);
  color: var(--text-accent);
}

.ticket-label {
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
}

.rank-chip {
  padding: 2px 7px;
  border-radius: var(--radius-full);
  background: var(--gradient-primary);
  color: #fff;
  font: 800 10px/1 var(--font-mono);
  letter-spacing: 0.04em;
}

.unavailable-chip {
  padding: 2px 6px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-muted);
  font: 700 10px/1 var(--font-mono);
}

.strategy-identity {
  margin-bottom: 12px;
}

.strategy-id {
  display: block;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.method-family {
  font-size: 10.5px;
  color: var(--text-tertiary);
}

.card-metrics {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
  font-size: 11px;
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.metric-name {
  color: var(--text-secondary);
}

.metric-value {
  font-size: 11.5px;
}

.unavailable-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 12px 4px;
  flex: 1;
}

.unavailable-icon {
  font-size: 20px;
  margin-bottom: 6px;
}

.unavailable-heading {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.reason-code-tag {
  display: inline-block;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  font: 700 9px/1 var(--font-mono);
  margin-bottom: 8px;
  letter-spacing: 0.03em;
}

.unavailable-desc {
  font-size: 10px;
  color: var(--text-tertiary);
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-footer {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  justify-content: flex-start;
}

.font-mono {
  font-family: var(--font-mono);
}

.text-primary {
  color: var(--primary-color-light, #a78bfa);
}

.text-success {
  color: var(--color-success) !important;
}

.text-danger {
  color: var(--color-danger) !important;
}

.text-muted {
  color: var(--text-tertiary);
}
</style>
