<script setup lang="ts">
import { computed } from 'vue'

import type { GameCode, ReplayExplorerItem, TicketCount } from '../types'
import { ALL_CANONICAL_TICKET_COUNTS } from '../types'

const props = withDefaults(
  defineProps<{
    game: GameCode
    items: ReplayExplorerItem[]
    availableTicketCounts: readonly TicketCount[]
    periodLabel: string
    loading?: boolean
  }>(),
  {
    loading: false,
  },
)

const emit = defineEmits<{
  (e: 'inspect', item: ReplayExplorerItem): void
}>()

// Group items by strategy
interface StrategyMatrixRow {
  strategyId: string
  displayLabel: string
  strategyVersion: string
  methodFamily: string | null
  cells: Map<TicketCount, ReplayExplorerItem | undefined>
}

const matrixRows = computed<StrategyMatrixRow[]>(() => {
  const rowMap = new Map<string, StrategyMatrixRow>()

  for (const item of props.items) {
    let row = rowMap.get(item.strategyId)
    if (!row) {
      row = {
        strategyId: item.strategyId,
        displayLabel: item.displayLabel,
        strategyVersion: item.strategyVersion,
        methodFamily: item.methodFamily,
        cells: new Map<TicketCount, ReplayExplorerItem | undefined>(),
      }
      rowMap.set(item.strategyId, row)
    }
    row.cells.set(item.ticketCount, item)
  }

  return Array.from(rowMap.values()).sort((a, b) => a.displayLabel.localeCompare(b.displayLabel))
})

// Check if a ticket count is available for this game
function isCountSupported(count: TicketCount): boolean {
  return props.availableTicketCounts.includes(count)
}

function getItem(row: StrategyMatrixRow, count: TicketCount): ReplayExplorerItem | undefined {
  return row.cells.get(count)
}
</script>

<template>
  <div class="replay-matrix-view">
    <div class="matrix-header-info">
      <div>
        <h4 class="matrix-title">Multi-Ticket Matrix Grid</h4>
        <p class="matrix-subtitle text-muted">
          Active Period / Horizon: <strong>{{ periodLabel }}</strong> · Ticket Counts 1..20
        </p>
      </div>
      <div class="matrix-legend">
        <span class="legend-item">
          <span class="legend-dot legend-dot--available" />
          Available Backtest
        </span>
        <span class="legend-item">
          <span class="legend-dot legend-dot--unavailable" />
          Unavailable / Unrecorded
        </span>
      </div>
    </div>

    <!-- Scroll container for responsive / mobile containment -->
    <div class="matrix-scroll-container">
      <table class="matrix-table">
        <thead>
          <tr>
            <th class="th--strategy-fixed" scope="col">Strategy</th>
            <th
              v-for="count in ALL_CANONICAL_TICKET_COUNTS"
              :key="count"
              class="th--ticket-col"
              :class="{ 'th--ticket-unavailable': !isCountSupported(count) }"
              scope="col"
            >
              <span>{{ count }}T</span>
              <span v-if="!isCountSupported(count)" class="col-unavailable-tag">N/A</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td :colspan="ALL_CANONICAL_TICKET_COUNTS.length + 1" class="loading-cell">
              <span class="spinner" aria-hidden="true" />
              <span>Loading matrix data…</span>
            </td>
          </tr>
          <tr v-else-if="matrixRows.length === 0">
            <td :colspan="ALL_CANONICAL_TICKET_COUNTS.length + 1" class="empty-cell">
              No strategies available for the selected filters.
            </td>
          </tr>
          <tr v-for="row in matrixRows" :key="row.strategyId" class="matrix-row">
            <!-- Strategy identity column -->
            <td class="td--strategy-fixed">
              <div class="strategy-id-wrapper">
                <strong class="strategy-name">{{ row.displayLabel }}</strong>
                <span v-if="row.methodFamily" class="strategy-meta text-muted">{{ row.methodFamily }}</span>
              </div>
            </td>

            <!-- Ticket count cells (1..20) -->
            <td
              v-for="count in ALL_CANONICAL_TICKET_COUNTS"
              :key="count"
              class="matrix-cell"
              :class="{
                'cell--supported': isCountSupported(count),
                'cell--unavailable': !isCountSupported(count),
                'cell--has-data': !!getItem(row, count)?.isAvailable,
              }"
            >
              <template v-if="getItem(row, count)?.isAvailable">
                <button
                  type="button"
                  class="cell-content-btn"
                  :title="`Inspect ${row.displayLabel} @ ${count}T (${getItem(row, count)?.hitRateFormatted})`"
                  @click="emit('inspect', getItem(row, count)!)"
                >
                  <span class="cell-rate">{{ getItem(row, count)?.hitRateFormatted }}</span>
                  <span v-if="getItem(row, count)?.rank" class="cell-rank">#{{ getItem(row, count)?.rank }}</span>
                </button>
              </template>
              <template v-else-if="isCountSupported(count)">
                <span class="cell-empty text-muted">—</span>
              </template>
              <template v-else>
                <div class="cell-unavailable-block" title="Ticket count not recorded in canonical evidence">
                  <span class="cell-na">—</span>
                </div>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.replay-matrix-view {
  width: 100%;
  min-width: 0;
  background: var(--bg-card, rgba(22, 18, 40, 0.78));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: var(--radius-xl, 20px);
  padding: 1.25rem;
}

.matrix-header-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.matrix-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.matrix-subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
}

.matrix-legend {
  display: flex;
  align-items: center;
  gap: 1rem;
  font-size: 0.8rem;
  color: var(--text-secondary, #cbd5e1);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-dot--available {
  background: var(--primary-color, #a855f7);
  box-shadow: 0 0 8px var(--primary-color, #a855f7);
}

.legend-dot--unavailable {
  background: var(--text-tertiary, #64748b);
}

.matrix-scroll-container {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: var(--radius-lg, 14px);
  background: rgba(9, 7, 20, 0.72);
}

.matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  text-align: center;
}

.matrix-table th,
.matrix-table td {
  padding: 0.6rem 0.5rem;
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.05));
}

.th--strategy-fixed,
.td--strategy-fixed {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #17122e;
  text-align: left;
  min-width: 220px;
  max-width: 260px;
  box-shadow: 2px 0 4px rgba(0, 0, 0, 0.3);
}

.th--ticket-col {
  min-width: 60px;
  font-weight: 600;
  color: var(--text-secondary, #cbd5e1);
}

.th--ticket-unavailable {
  color: var(--text-tertiary, #64748b);
  background: rgba(0, 0, 0, 0.15);
}

.col-unavailable-tag {
  display: block;
  font-size: 0.65rem;
  color: var(--text-tertiary, #64748b);
  font-weight: normal;
}

.strategy-id-wrapper {
  display: flex;
  flex-direction: column;
}

.strategy-name {
  color: var(--text-primary, #f1f5f9);
  font-size: 0.85rem;
  word-break: break-word;
}

.strategy-meta {
  font-size: 0.75rem;
}

.matrix-cell {
  vertical-align: middle;
  height: 52px;
}

.cell--unavailable {
  background: rgba(9, 7, 20, 0.42);
}

.cell-content-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  padding: 0.2rem;
  background: rgba(59, 130, 246, 0.14);
  border: 1px solid rgba(124, 58, 237, 0.38);
  border-radius: var(--radius-sm, 6px);
  cursor: pointer;
  color: #bfdbfe;
  transition: all 0.15s ease;
}

.cell-content-btn:hover {
  background: rgba(168, 85, 247, 0.22);
  border-color: var(--border-hover, rgba(192, 132, 252, 0.35));
  transform: translateY(-1px);
}

.cell-rate {
  font-weight: 700;
  font-size: 0.8rem;
}

.cell-rank {
  font-size: 0.7rem;
  color: #c4b5fd;
}

.cell-unavailable-block {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary, #475569);
  font-size: 0.8rem;
}

.cell-na {
  color: var(--text-tertiary, #475569);
}

.cell-empty {
  color: var(--text-tertiary, #64748b);
}

.loading-cell,
.empty-cell {
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary, #94a3b8);
}

.text-muted {
  color: var(--text-secondary, #94a3b8);
}
</style>
