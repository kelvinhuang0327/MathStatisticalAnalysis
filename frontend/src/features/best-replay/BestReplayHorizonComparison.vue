<script setup lang="ts">
import StatusBadge from '../../components/StatusBadge.vue'
import BestReplaySourceMeta from './BestReplaySourceMeta.vue'
import {
  CANONICAL_HORIZONS,
  type BestReplayItem,
  type TicketCount,
} from './types'

const props = defineProps<{
  strategyId: string
  strategyVersion?: string | null
  ticketCount: TicketCount
  game: string
  itemsByHorizon: Partial<Record<string, BestReplayItem | null>>
}>()

const dimensionLabel = props.game === 'B649' ? 'Prefix Count' : 'Ticket Count'
const successDefinition = props.game === 'B649'
  ? 'official_any_prize_rate · M3_PLUS criterion'
  : `${props.game} winning_target_rate · canonical run ranking`
</script>

<template>
  <div class="horizon-comparison-card" data-testid="horizon-comparison">
    <div class="horizon-comparison__header">
      <div class="horizon-comparison__title-group">
        <span class="horizon-comparison__eyebrow">{{ game }} · {{ dimensionLabel }} {{ ticketCount }}</span>
        <h3 class="horizon-comparison__title">{{ strategyId }}</h3>
      </div>
      <div class="horizon-comparison__meta">
        <span class="status-badge status-badge--accent">
          {{ strategyVersion || 'Version not provided' }}
        </span>
      </div>
    </div>

    <p class="horizon-comparison__scope-note">
      {{ successDefinition }}. Each period is a separate source scope; rates and ranks are not compared across periods.
    </p>

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
            <small class="horizon-card__source-rank">
              Source Rank {{ itemsByHorizon[h.key]?.rank !== null && itemsByHorizon[h.key]?.rank !== undefined ? `#${itemsByHorizon[h.key]?.rank}` : 'Unavailable' }}
              · Rate {{ itemsByHorizon[h.key]?.isAvailable && itemsByHorizon[h.key]?.hitRate !== null ? 'available' : 'Unavailable' }}
            </small>
            <BestReplaySourceMeta
              v-if="itemsByHorizon[h.key]"
              :item="itemsByHorizon[h.key]!"
            />
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
                {{ itemsByHorizon[h.key]?.evaluatedTargets?.toLocaleString() ?? 'Unknown' }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-item__label">Winning Targets</span>
              <span class="detail-item__value">
                {{ itemsByHorizon[h.key]?.winningTargets?.toLocaleString() ?? 'Not provided' }}
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
            {{ itemsByHorizon[h.key]?.notes || `No canonical backtest evidence is recorded for ${dimensionLabel.toLowerCase()} ${ticketCount} at horizon ${h.label}.` }}
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

.horizon-comparison__scope-note {
  margin: 14px 0 18px;
  color: var(--text-secondary);
  font-size: 12px;
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

.horizon-card__source-rank {
  display: block;
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: 10px;
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
