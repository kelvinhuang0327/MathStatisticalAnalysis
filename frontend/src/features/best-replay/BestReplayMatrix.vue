<script setup lang="ts">
import {
  ALL_TICKET_COUNTS,
  type BestReplayMatrixRow,
  type TicketCount,
} from './types'

defineProps<{
  rows: BestReplayMatrixRow[]
  selectedTicketCount?: TicketCount | null
  selectedStrategyId?: string | null
}>()

const emit = defineEmits<{
  (e: 'select-cell', strategyId: string, ticketCount: TicketCount): void
}>()

function getCellTitle(row: BestReplayMatrixRow, count: TicketCount): string {
  const cell = row.cells[count]
  const dimension = row.game === 'B649' ? 'prefix count' : 'ticket count'
  const source = row.game === 'B649'
    ? 'official_any_prize_rate · M3_PLUS criterion'
    : `${row.game} canonical run ranking · winning_target_rate`
  if (cell) {
    const rateStatus = cell.isAvailable ? cell.hitRateFormatted : 'Unavailable'
    const sourceIdentity = cell.sourceRunId
      ? `source run ${cell.sourceRunId}`
      : cell.legacyMethodId
        ? `source identity ${cell.legacyMethodId}`
        : 'source identity not provided'
    const sourceTime = cell.sourceCompletedAt
      ? ` · completed ${cell.sourceCompletedAt}`
      : cell.sourceAsOfDate
        ? ` · as of ${cell.sourceAsOfDate}`
        : ''
    return `${row.strategyLabel} · ${row.game} · ${dimension} ${count} · ${cell.horizon} · ${source} · ${sourceIdentity}${sourceTime} · source rank ${cell.rank ?? 'unavailable'} · rate ${rateStatus} (Delta: ${cell.baselineDeltaFormatted})`
  }
  return `${row.strategyLabel} · ${row.game} · ${dimension} ${count}: no source record`
}
</script>

<template>
  <div class="matrix-container" data-testid="best-replay-matrix">
    <div class="matrix-legend">
      <div class="legend-item">
        <span class="legend-box legend-box--available" />
        <span>Source record available</span>
      </div>
      <div class="legend-item">
        <span class="legend-box legend-box--unavailable" />
        <span>Evidence Unavailable (Explicitly Distinct from Zero)</span>
      </div>
      <p class="matrix-scope-note">
        Each game and ticket or prefix count is a separate source-defined scope. Source rank and rate are shown per cell; shading does not compare rates across columns.
      </p>
    </div>

    <div class="matrix-table-wrapper">
      <table class="matrix-table">
        <thead>
          <tr>
            <th class="col-strategy sticky-col">Strategy</th>
            <th class="col-game">Game</th>
            <th
              v-for="count in ALL_TICKET_COUNTS"
              :key="count"
              class="col-ticket"
              :class="{ 'col-ticket--selected': selectedTicketCount === count }"
            >
              {{ count }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.strategyId"
            class="matrix-row"
            :class="{ 'matrix-row--selected': selectedStrategyId === row.strategyId }"
          >
            <td class="col-strategy sticky-col">
              <span class="strategy-label" :title="row.strategyLabel">
                {{ row.strategyLabel || row.strategyId }}
              </span>
              <small class="family-tag">{{ row.methodFamily }}</small>
            </td>
            <td class="col-game">
              <span class="game-badge">{{ row.game }}</span>
            </td>
            <td
              v-for="count in ALL_TICKET_COUNTS"
              :key="count"
              class="matrix-cell"
              :class="{
                'matrix-cell--available': row.cells[count]?.isAvailable,
                'matrix-cell--unavailable': !row.cells[count]?.isAvailable,
                'matrix-cell--active': selectedTicketCount === count && selectedStrategyId === row.strategyId,
              }"
              :tabindex="row.cells[count]?.isAvailable ? 0 : -1"
              :title="getCellTitle(row, count)"
              @click="emit('select-cell', row.strategyId, count)"
              @keydown.enter="emit('select-cell', row.strategyId, count)"
              @keydown.space.prevent="emit('select-cell', row.strategyId, count)"
            >
              <template v-if="row.cells[count]?.isAvailable">
                <span class="cell-rate">{{ row.cells[count]?.hitRateFormatted }}</span>
                <small class="cell-rank">Source #{{ row.cells[count]?.rank ?? 'Unavailable' }}</small>
                <small
                  v-if="row.cells[count]?.baselineDeltaFormatted !== 'Unavailable'"
                  class="cell-delta"
                  :class="{
                    'text-success': (row.cells[count]?.baselineDelta || 0) > 0,
                    'text-danger': (row.cells[count]?.baselineDelta || 0) < 0,
                  }"
                >
                  {{ row.cells[count]?.baselineDeltaFormatted }}
                </small>
              </template>
              <template v-else>
                <span class="cell-unavailable" aria-label="Evidence Unavailable">—</span>
                <small v-if="row.cells[count]?.rank !== null && row.cells[count]?.rank !== undefined" class="cell-rank">
                  Source #{{ row.cells[count]?.rank }} · Rate unavailable
                </small>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.matrix-container {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  padding: 20px;
  box-shadow: var(--shadow-md);
  margin-bottom: 24px;
}

.matrix-legend {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-secondary);
}

.matrix-scope-note {
  flex-basis: 100%;
  margin: 0;
  color: var(--text-secondary);
  font-size: 11px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-box {
  width: 14px;
  height: 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.legend-box--available {
  background: rgba(124, 58, 237, 0.45);
  border-color: rgba(139, 92, 246, 0.7);
}

.legend-box--unavailable {
  background: rgba(255, 255, 255, 0.03);
  border: 1px dashed rgba(255, 255, 255, 0.15);
}

.matrix-table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: rgba(10, 14, 23, 0.8);
  max-height: 520px;
}

.matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  white-space: nowrap;
}

.matrix-table th,
.matrix-table td {
  padding: 10px 8px;
  border: 1px solid var(--border-subtle);
  text-align: center;
}

.matrix-table thead {
  position: sticky;
  top: 0;
  background: #0f1523;
  z-index: 10;
}

.matrix-table th {
  color: var(--text-secondary);
  font: 700 11px/1 var(--font-mono);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.col-strategy {
  text-align: left !important;
  min-width: 220px;
  max-width: 280px;
}

.sticky-col {
  position: sticky;
  left: 0;
  background: #0d121f;
  z-index: 5;
  border-right: 2px solid var(--border-color);
}

.matrix-table thead .sticky-col {
  z-index: 15;
  background: #111827;
}

.strategy-label {
  display: block;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
}

.family-tag {
  display: block;
  font-size: 10px;
  color: var(--text-accent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.col-game {
  min-width: 60px;
}

.game-badge {
  font: 700 10px/1 var(--font-mono);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: rgba(56, 189, 248, 0.15);
  color: var(--mint);
}

.col-ticket {
  min-width: 64px;
}

.col-ticket--selected {
  background: rgba(124, 58, 237, 0.2);
  color: var(--text-accent);
}

.matrix-row:hover .sticky-col {
  background: #161f33;
}

.matrix-row--selected .sticky-col {
  background: #1e293b;
  border-left: 3px solid var(--primary-color);
}

.matrix-cell {
  position: relative;
  cursor: default;
  transition: all 0.15s ease;
}

.matrix-cell--available {
  cursor: pointer;
  background: rgba(124, 58, 237, 0.12);
  border-color: rgba(139, 92, 246, 0.3);
}

.matrix-cell--available:hover,
.matrix-cell--available:focus-visible {
  outline: 2px solid var(--text-cyan);
  outline-offset: -2px;
  filter: brightness(1.25);
  z-index: 2;
}

.matrix-cell--active {
  outline: 2px solid var(--primary-light);
  outline-offset: -2px;
}

.matrix-cell--unavailable {
  background: rgba(255, 255, 255, 0.015);
  color: var(--text-tertiary);
}

.cell-rate {
  display: block;
  font-weight: 700;
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--text-primary);
}

.cell-rank {
  display: block;
  margin-top: 2px;
  color: var(--text-secondary);
  font-size: 9px;
  font-family: var(--font-mono);
}

.cell-delta {
  display: block;
  font-size: 9.5px;
  font-family: var(--font-mono);
  margin-top: 2px;
}

.cell-unavailable {
  font-size: 13px;
  opacity: 0.35;
}

.text-success {
  color: var(--color-success) !important;
}

.text-danger {
  color: var(--color-danger) !important;
}
</style>
