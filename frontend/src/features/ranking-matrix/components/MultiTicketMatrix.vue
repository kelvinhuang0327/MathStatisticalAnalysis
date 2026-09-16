<script setup lang="ts">
import { computed } from 'vue'

import type { MatrixRow, TicketCount } from '../types'

const props = defineProps<{
  rows: MatrixRow[]
  selectedStrategyId: string | null
  activeWindow: string
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'selectStrategy', strategyId: string, displayName: string): void
}>()

const ticketCounts: TicketCount[] = [2, 3, 5, 10, 20]

const filteredRows = computed(() => props.rows)

function handleRowSelect(row: MatrixRow): void {
  emit('selectStrategy', row.strategyId, row.displayName)
}
</script>

<template>
  <div class="matrix-container" data-testid="multi-ticket-matrix">
    <div class="matrix-header-info">
      <div class="matrix-title">
        <strong>多注數比較矩陣 (Multi-Ticket Matrix)</strong>
        <span class="matrix-window-badge">當前窗口：{{ activeWindow }}</span>
      </div>
      <p class="matrix-desc">
        以策略為列，橫向比較 2、3、5、10、20 注之官方排名與成功率。若該注數無回測資料，明確標示為不可用，不以 0% 充當結果。
      </p>
    </div>

    <div v-if="loading" class="matrix-loading">
      <span class="spinner" aria-hidden="true" />
      <span>載入多注數矩陣中…</span>
    </div>

    <div v-else-if="filteredRows.length === 0" class="matrix-empty" data-testid="matrix-empty">
      <p>當前窗口無多注數回測矩陣資料。</p>
    </div>

    <div v-else class="matrix-scroll-wrapper">
      <table class="matrix-table" data-testid="matrix-table">
        <thead>
          <tr>
            <th scope="col" class="th-matrix-strategy th-sticky">Strategy / 策略名稱</th>
            <th
              v-for="tc in ticketCounts"
              :key="tc"
              scope="col"
              class="th-matrix-ticket"
              :data-testid="`th-ticket-${tc}`"
            >
              <span>{{ tc }} 注 (Tickets)</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in filteredRows"
            :key="row.strategyId"
            class="matrix-row"
            :class="{ 'matrix-row--selected': row.strategyId === selectedStrategyId }"
            :data-testid="`matrix-row-${row.strategyId}`"
            @click="handleRowSelect(row)"
          >
            <!-- Sticky Strategy Column -->
            <td class="td-matrix-strategy td-sticky">
              <div class="matrix-strategy-cell">
                <strong class="matrix-strategy-name">{{ row.displayName }}</strong>
                <div class="matrix-strategy-sub">
                  <span class="matrix-id">{{ row.strategyId }}</span>
                  <span v-if="row.methodFamily" class="matrix-family">{{ row.methodFamily }}</span>
                </div>
              </div>
            </td>

            <!-- Ticket Count Cells -->
            <td
              v-for="tc in ticketCounts"
              :key="tc"
              class="td-matrix-cell"
              :class="{
                'cell--available': row.cells[tc].isAvailable,
                'cell--unavailable': !row.cells[tc].isAvailable,
              }"
              :data-testid="`matrix-cell-${row.strategyId}-${tc}`"
            >
              <div v-if="row.cells[tc].isAvailable" class="cell-content">
                <div class="cell-top">
                  <span
                    v-if="row.cells[tc].officialRank !== null"
                    class="cell-rank"
                    :class="{ 'cell-rank--top3': row.cells[tc].officialRank! <= 3 }"
                  >
                    #{{ row.cells[tc].officialRank }}
                  </span>
                  <span v-else class="cell-rank cell-rank--unranked">
                    —
                  </span>
                  <span class="cell-rate">
                    {{ row.cells[tc].officialAnyPrizeRateFormatted }}
                  </span>
                </div>
                <div v-if="row.cells[tc].baselineDeltaFormatted !== 'Unavailable'" class="cell-delta">
                  <small :class="row.cells[tc].baselineDelta! > 0 ? 'delta-pos' : 'delta-neg'">
                    {{ row.cells[tc].baselineDeltaFormatted }}
                  </small>
                </div>
              </div>

              <!-- Explicit Unavailable State (NEVER 0%) -->
              <div v-else class="cell-unavailable-content">
                <span class="unavailable-tag">不可比較 / 無資料</span>
                <small class="unavailable-reason">{{ row.cells[tc].comparabilityLabel }}</small>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.matrix-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-3, 12px);
  width: 100%;
}

.matrix-header-info {
  background: var(--bg-tertiary, #131927);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  border-radius: var(--radius-md, 10px);
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.matrix-title {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-primary, #f8fafc);
  font-size: 0.95rem;
}

.matrix-window-badge {
  background: rgba(99, 102, 241, 0.18);
  color: #a5b4fc;
  border: 1px solid rgba(99, 102, 241, 0.3);
  padding: 2px 8px;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.78rem;
  font-weight: 600;
}

.matrix-desc {
  font-size: 0.8rem;
  color: var(--text-secondary, #94a3b8);
  margin: 0;
}

.matrix-loading,
.matrix-empty {
  padding: 40px;
  text-align: center;
  background: var(--bg-card, rgba(18, 24, 38, 0.72));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  border-radius: var(--radius-md, 10px);
  color: var(--text-secondary, #94a3b8);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.matrix-scroll-wrapper {
  overflow-x: auto;
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  border-radius: var(--radius-md, 10px);
  background: var(--bg-card, rgba(18, 24, 38, 0.72));
}

.matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  min-width: 900px;
}

.matrix-table th,
.matrix-table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.05));
  text-align: left;
}

.matrix-table th {
  background: var(--bg-secondary, #0d111b);
  color: var(--text-secondary, #94a3b8);
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.th-sticky,
.td-sticky {
  position: sticky;
  left: 0;
  z-index: 2;
  background: var(--bg-secondary, #0d111b);
  box-shadow: 2px 0 6px rgba(0, 0, 0, 0.4);
}

.th-matrix-strategy,
.td-matrix-strategy {
  min-width: 220px;
  max-width: 280px;
}

.matrix-row {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.matrix-row:hover td {
  background-color: var(--bg-card-hover, rgba(26, 34, 52, 0.85));
}

.matrix-row--selected td {
  background-color: rgba(99, 102, 241, 0.18) !important;
}

.matrix-row--selected .td-sticky {
  background-color: #1a2238 !important;
  border-left: 3px solid var(--primary-color, #8b5cf6);
}

.matrix-strategy-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.matrix-strategy-name {
  color: var(--text-primary, #f8fafc);
  font-size: 0.88rem;
}

.matrix-strategy-sub {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.72rem;
  color: var(--text-tertiary, #64748b);
  flex-wrap: wrap;
}

.matrix-id {
  font-family: var(--font-mono, monospace);
}

.matrix-family {
  background: rgba(255, 255, 255, 0.05);
  padding: 1px 4px;
  border-radius: 3px;
}

.th-matrix-ticket {
  min-width: 130px;
  text-align: center;
}

.td-matrix-cell {
  text-align: center;
  vertical-align: middle;
}

.cell-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}

.cell-top {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cell-rank {
  font-family: var(--font-mono, monospace);
  font-weight: 700;
  font-size: 0.82rem;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary, #f8fafc);
}

.cell-rank--top3 {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.4);
}

.cell-rank--unranked {
  color: var(--text-tertiary, #64748b);
}

.cell-rate {
  font-family: var(--font-mono, monospace);
  font-weight: 600;
  color: #38bdf8;
}

.cell-delta {
  font-size: 0.72rem;
  font-family: var(--font-mono, monospace);
}

.delta-pos {
  color: #34d399;
}

.delta-neg {
  color: #f87171;
}

.cell-unavailable-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  opacity: 0.6;
}

.unavailable-tag {
  font-size: 0.75rem;
  color: var(--text-tertiary, #64748b);
  background: rgba(255, 255, 255, 0.04);
  padding: 2px 6px;
  border-radius: 3px;
  font-style: italic;
}

.unavailable-reason {
  font-size: 0.68rem;
  color: var(--text-tertiary, #64748b);
}
</style>
