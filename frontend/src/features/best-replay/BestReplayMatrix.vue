<script setup lang="ts">
import { computed } from 'vue'

import {
  ALL_TICKET_COUNTS,
  type BestReplayItem,
  type BestReplayMatrixRow,
  type TicketCount,
} from './types'

const props = defineProps<{
  rows: BestReplayMatrixRow[]
  selectedTicketCount?: TicketCount | null
  selectedStrategyId?: string | null
}>()

const emit = defineEmits<{
  (e: 'select-cell', strategyId: string, ticketCount: TicketCount): void
}>()

// Calculate max hit rate across all available cells for relative intensity coloring
const maxHitRate = computed(() => {
  let max = 0.01
  for (const row of props.rows) {
    for (const count of ALL_TICKET_COUNTS) {
      const cell = row.cells[count]
      if (cell && cell.isAvailable && cell.hitRate !== null && cell.hitRate > max) {
        max = cell.hitRate
      }
    }
  }
  return max
})

function getCellBgStyle(cell: BestReplayItem | null): Record<string, string> {
  if (!cell || !cell.isAvailable || cell.hitRate === null) {
    return {}
  }
  const intensity = Math.min(1, Math.max(0.15, cell.hitRate / maxHitRate.value))
  return {
    backgroundColor: `rgba(124, 58, 237, ${intensity * 0.45})`,
    borderColor: `rgba(139, 92, 246, ${intensity * 0.7})`,
  }
}
</script>

<template>
  <div class="matrix-container" data-testid="best-replay-matrix">
    <div class="matrix-legend">
      <div class="legend-item">
        <span class="legend-box legend-box--available" />
        <span>Canonical Evidence Available (Heatmap Intensity)</span>
      </div>
      <div class="legend-item">
        <span class="legend-box legend-box--unavailable" />
        <span>Evidence Unavailable (Explicitly Distinct from Zero)</span>
      </div>
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
              {{ count }}T
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
              <span class="strategy-label" :title="row.strategyId">
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
              :style="getCellBgStyle(row.cells[count])"
              :tabindex="row.cells[count]?.isAvailable ? 0 : -1"
              :title="
                row.cells[count]?.isAvailable
                  ? `${row.strategyId} (${count} Tickets): ${row.cells[count]?.hitRateFormatted} (Delta: ${row.cells[count]?.baselineDeltaFormatted})`
                  : `${row.strategyId} (${count} Tickets): Evidence Unavailable`
              "
              @click="emit('select-cell', row.strategyId, count)"
              @keydown.enter="emit('select-cell', row.strategyId, count)"
              @keydown.space.prevent="emit('select-cell', row.strategyId, count)"
            >
              <template v-if="row.cells[count]?.isAvailable">
                <span class="cell-rate">{{ row.cells[count]?.hitRateFormatted }}</span>
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
