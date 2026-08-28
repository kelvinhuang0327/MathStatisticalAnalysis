<script setup lang="ts">
import { computed } from 'vue'

import StatusBadge from '../../components/StatusBadge.vue'
import {
  CANONICAL_HORIZONS,
  type BestReplayItem,
  type TicketCount,
} from './types'

const props = defineProps<{
  strategyId: string
  strategyVersion?: string
  ticketCount: TicketCount
  game: string
  itemsByHorizon: Partial<Record<string, BestReplayItem | null>>
}>()

const maxHitRate = computed(() => {
  let max = 0.01
  for (const h of CANONICAL_HORIZONS) {
    const item = props.itemsByHorizon[h.key]
    if (item && item.hitRate !== null && item.hitRate > max) {
      max = item.hitRate
    }
  }
  return max
})
</script>

<template>
  <div class="horizon-comparison-card" data-testid="horizon-comparison">
    <div class="horizon-comparison__header">
      <div class="horizon-comparison__title-group">
        <span class="horizon-comparison__eyebrow">{{ game }} · Ticket Count {{ ticketCount }}</span>
        <h3 class="horizon-comparison__title">{{ strategyId }}</h3>
      </div>
      <div class="horizon-comparison__meta">
        <span class="status-badge status-badge--accent">
          {{ strategyVersion || 'v1.0' }}
        </span>
      </div>
    </div>

    <div class="horizon-cards-grid">
      <div
        v-for="h in CANONICAL_HORIZONS"
        :key="h.key"
        class="horizon-card"
        :class="{ 'horizon-card--available': itemsByHorizon[h.key]?.isAvailable }"
        :data-testid="`horizon-card-${h.key.toLowerCase().replace('_', '-')}`"
      >
        <div class="horizon-card__header">
          <div>
            <strong class="horizon-card__name">{{ h.label }}</strong>
            <small class="horizon-card__desc">{{ h.description }}</small>
          </div>
          <StatusBadge
            v-if="itemsByHorizon[h.key]"
            :status="itemsByHorizon[h.key]?.evidenceStatus || 'EVIDENCE UNAVAILABLE'"
            size="sm"
          />
          <StatusBadge
            v-else
            status="EVIDENCE UNAVAILABLE"
            size="sm"
          />
        </div>

        <div v-if="itemsByHorizon[h.key]?.isAvailable" class="horizon-card__body">
          <div class="horizon-card__metric-row">
            <span class="metric-label">Historical Hit Rate</span>
            <strong class="metric-value metric-value--highlight">
              {{ itemsByHorizon[h.key]?.hitRateFormatted }}
            </strong>
          </div>

          <!-- Mini visual progress bar -->
          <div class="mini-bar-track" aria-hidden="true">
            <div
              class="mini-bar-fill"
              :style="{
                width: `${Math.min(100, ((itemsByHorizon[h.key]?.hitRate || 0) / maxHitRate) * 100)}%`,
              }"
            />
          </div>

          <div class="horizon-card__details-grid">
            <div class="detail-item">
              <span class="detail-item__label">Baseline Delta</span>
              <span
                class="detail-item__value"
                :class="{
                  'text-success': (itemsByHorizon[h.key]?.baselineDelta || 0) > 0,
                  'text-danger': (itemsByHorizon[h.key]?.baselineDelta || 0) < 0,
                }"
              >
                {{ itemsByHorizon[h.key]?.baselineDeltaFormatted }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-item__label">Evaluated Draws</span>
              <span class="detail-item__value">
                {{ itemsByHorizon[h.key]?.evaluatedTargets }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-item__label">Winning Targets</span>
              <span class="detail-item__value">
                {{ itemsByHorizon[h.key]?.winningTargets ?? '—' }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-item__label">Best Hit</span>
              <span class="detail-item__value">
                {{ itemsByHorizon[h.key]?.bestHit }}
              </span>
            </div>
          </div>

          <p class="horizon-card__note">
            {{ itemsByHorizon[h.key]?.notes }}
          </p>
        </div>

        <div v-else class="horizon-card__unavailable">
          <span class="unavailable-icon" aria-hidden="true">🔒</span>
          <p class="unavailable-title">Evidence Unavailable</p>
          <p class="unavailable-desc">
            No canonical backtest evidence is recorded for ticket count {{ ticketCount }} at horizon {{ h.label }}.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.horizon-comparison-card {
  padding: 24px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: var(--shadow-md);
  margin-bottom: 24px;
}

.horizon-comparison__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 16px;
}

.horizon-comparison__eyebrow {
  display: block;
  font: 700 11px/1 var(--font-mono);
  color: var(--text-cyan);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}

.horizon-comparison__title {
  margin: 0;
  font-size: 20px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  word-break: break-all;
}

.horizon-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.horizon-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: rgba(13, 17, 27, 0.7);
  padding: 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: all 0.2s ease;
}

.horizon-card--available:hover {
  border-color: var(--border-hover);
  background: rgba(22, 28, 44, 0.85);
}

.horizon-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 14px;
}

.horizon-card__name {
  display: block;
  font-size: 15px;
  color: var(--text-primary);
  font-weight: 700;
}

.horizon-card__desc {
  display: block;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
  line-height: 1.3;
}

.horizon-card__metric-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 6px;
}

.metric-label {
  font-size: 11.5px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric-value--highlight {
  font-size: 22px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-weight: 800;
}

.mini-bar-track {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-bottom: 16px;
}

.mini-bar-fill {
  height: 100%;
  background: var(--gradient-primary);
  border-radius: var(--radius-full);
  transition: width 0.4s ease;
}

.horizon-card__details-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
}

.detail-item__label {
  font-size: 10.5px;
  color: var(--text-tertiary);
  text-transform: uppercase;
}

.detail-item__value {
  font-size: 13px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.text-success {
  color: var(--color-success) !important;
}

.text-danger {
  color: var(--color-danger) !important;
}

.horizon-card__note {
  margin: 0;
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.4;
  border-top: 1px dashed var(--border-subtle);
  padding-top: 8px;
}

.horizon-card__unavailable {
  padding: 24px 12px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.15);
  border: 1px dashed rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-sm);
  min-height: 180px;
}

.unavailable-icon {
  font-size: 24px;
  opacity: 0.4;
  margin-bottom: 8px;
}

.unavailable-title {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
}

.unavailable-desc {
  margin: 0;
  font-size: 11px;
  color: var(--text-tertiary);
  line-height: 1.4;
  max-width: 220px;
}
</style>
