<script setup lang="ts">
import { computed } from 'vue'

import DataTable from '../../components/DataTable.vue'
import EmptyState from '../../components/EmptyState.vue'
import StatusBadge from '../../components/StatusBadge.vue'

import type {
  ReplayOverviewMatrixRow,
  ReplayOverviewStrategyItem,
  ReplayOverviewWindow,
} from './types'

const props = withDefaults(
  defineProps<{
    rows: ReplayOverviewMatrixRow[]
    window: ReplayOverviewWindow
    loading?: boolean
    isDimensionAvailable?: boolean
    unavailableReason?: string | null
    searchQuery?: string
  }>(),
  {
    loading: false,
    isDimensionAvailable: true,
    unavailableReason: null,
    searchQuery: '',
  },
)

const filteredRows = computed(() => {
  const q = props.searchQuery.trim().toLowerCase()
  if (!q) return props.rows
  return props.rows.filter(
    (row) =>
      row.strategyId.toLowerCase().includes(q) ||
      row.strategyLabel.toLowerCase().includes(q) ||
      row.methodFamily.toLowerCase().includes(q),
  )
})

function formatCellRank(item: ReplayOverviewStrategyItem | null): string {
  if (!item || item.officialRank === null) return '--'
  return `#${item.officialRank}`
}

function formatCellHitRate(item: ReplayOverviewStrategyItem | null): string {
  if (!item || !item.isAvailable || item.officialAnyPrizeRateFormatted === 'Unavailable') {
    return 'Unavailable'
  }
  return item.officialAnyPrizeRateFormatted
}

function formatCellDelta(item: ReplayOverviewStrategyItem | null): string {
  if (!item || !item.isAvailable || item.officialRandomBaselineDeltaFormatted === 'Unavailable') {
    return '--'
  }
  return item.officialRandomBaselineDeltaFormatted
}

function isPositiveDelta(item: ReplayOverviewStrategyItem | null): boolean {
  return item !== null && item.officialRandomBaselineDelta !== null && item.officialRandomBaselineDelta > 0
}

function isNegativeDelta(item: ReplayOverviewStrategyItem | null): boolean {
  return item !== null && item.officialRandomBaselineDelta !== null && item.officialRandomBaselineDelta < 0
}
</script>

<template>
  <div class="replay-overview-matrix" data-testid="replay-overview-matrix">
    <div v-if="!isDimensionAvailable" class="unavailable-matrix-banner" data-testid="matrix-unavailable-banner">
      <div class="unavailable-matrix-banner__icon">ℹ️</div>
      <div>
        <h4>Canonical Multi-Ticket Matrix Unavailable</h4>
        <p>{{ unavailableReason ?? 'No canonical multi-ticket evidence is available for this game.' }}</p>
      </div>
    </div>

    <div v-else-if="filteredRows.length === 0 && !loading" class="matrix-empty">
      <EmptyState
        title="No strategies match query"
        description="Try adjusting your search query to view matrix performance."
      />
    </div>

    <DataTable
      v-else
      :loading="loading"
      :empty="filteredRows.length === 0"
      caption="10 / 15 / 20 Ticket Strategy Matrix across the active evaluation window"
      min-width="720px"
    >
      <template #head>
        <tr>
          <th scope="col" style="min-width: 220px;">Strategy</th>
          <th scope="col" style="min-width: 140px; text-align: center;">10 Tickets</th>
          <th scope="col" style="min-width: 140px; text-align: center;">15 Tickets</th>
          <th scope="col" style="min-width: 140px; text-align: center;">20 Tickets</th>
        </tr>
      </template>

      <template #default>
        <tr
          v-for="row in filteredRows"
          :key="row.strategyId"
          :data-testid="`matrix-row-${row.strategyId}`"
        >
          <td>
            <div class="strategy-matrix-ident">
              <span class="strategy-matrix-ident__id" :title="row.strategyId">{{ row.strategyId }}</span>
              <div class="strategy-matrix-ident__meta">
                <span class="meta-family">{{ row.methodFamily }}</span>
                <StatusBadge :status="row.reproductionStatus" size="sm" />
              </div>
            </div>
          </td>

          <!-- 10 Tickets Cell -->
          <td class="matrix-cell" data-testid="matrix-cell-10">
            <div v-if="row.cells[10]?.isAvailable" class="matrix-cell__content">
              <span class="matrix-cell__rank">{{ formatCellRank(row.cells[10]) }}</span>
              <span class="matrix-cell__rate">{{ formatCellHitRate(row.cells[10]) }}</span>
              <span
                class="matrix-cell__delta"
                :class="{
                  'matrix-cell__delta--pos': isPositiveDelta(row.cells[10]),
                  'matrix-cell__delta--neg': isNegativeDelta(row.cells[10]),
                }"
              >
                {{ formatCellDelta(row.cells[10]) }}
              </span>
            </div>
            <div v-else-if="row.cells[10]" class="matrix-cell__unranked">
              <span class="matrix-cell__unranked-text">{{ row.cells[10]?.unrankedReason ?? 'Unranked' }}</span>
            </div>
            <div v-else class="matrix-cell__unavailable">
              <span class="unavailable-label">Unavailable</span>
            </div>
          </td>

          <!-- 15 Tickets Cell -->
          <td class="matrix-cell" data-testid="matrix-cell-15">
            <div v-if="row.cells[15]?.isAvailable" class="matrix-cell__content">
              <span class="matrix-cell__rank">{{ formatCellRank(row.cells[15]) }}</span>
              <span class="matrix-cell__rate">{{ formatCellHitRate(row.cells[15]) }}</span>
              <span
                class="matrix-cell__delta"
                :class="{
                  'matrix-cell__delta--pos': isPositiveDelta(row.cells[15]),
                  'matrix-cell__delta--neg': isNegativeDelta(row.cells[15]),
                }"
              >
                {{ formatCellDelta(row.cells[15]) }}
              </span>
            </div>
            <div v-else-if="row.cells[15]" class="matrix-cell__unranked">
              <span class="matrix-cell__unranked-text">{{ row.cells[15]?.unrankedReason ?? 'Unranked' }}</span>
            </div>
            <div v-else class="matrix-cell__unavailable">
              <span class="unavailable-label">Unavailable</span>
            </div>
          </td>

          <!-- 20 Tickets Cell -->
          <td class="matrix-cell" data-testid="matrix-cell-20">
            <div v-if="row.cells[20]?.isAvailable" class="matrix-cell__content">
              <span class="matrix-cell__rank">{{ formatCellRank(row.cells[20]) }}</span>
              <span class="matrix-cell__rate">{{ formatCellHitRate(row.cells[20]) }}</span>
              <span
                class="matrix-cell__delta"
                :class="{
                  'matrix-cell__delta--pos': isPositiveDelta(row.cells[20]),
                  'matrix-cell__delta--neg': isNegativeDelta(row.cells[20]),
                }"
              >
                {{ formatCellDelta(row.cells[20]) }}
              </span>
            </div>
            <div v-else-if="row.cells[20]" class="matrix-cell__unranked">
              <span class="matrix-cell__unranked-text">{{ row.cells[20]?.unrankedReason ?? 'Unranked' }}</span>
            </div>
            <div v-else class="matrix-cell__unavailable">
              <span class="unavailable-label">Unavailable</span>
            </div>
          </td>
        </tr>
      </template>
    </DataTable>
  </div>
</template>

<style scoped>
.replay-overview-matrix {
  margin-top: 1rem;
}

.unavailable-matrix-banner {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.5rem;
  background: var(--color-surface-sunken, rgba(255, 255, 255, 0.03));
  border: 1px dashed var(--color-border-subtle, rgba(255, 255, 255, 0.15));
  border-radius: 8px;
  color: var(--color-text-muted, #94a3b8);
}

.unavailable-matrix-banner h4 {
  margin: 0 0 0.25rem 0;
  color: var(--color-text-primary, #f8fafc);
  font-size: 1rem;
}

.unavailable-matrix-banner p {
  margin: 0;
  font-size: 0.875rem;
}

.strategy-matrix-ident {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.strategy-matrix-ident__id {
  font-family: var(--font-mono, monospace);
  font-size: 0.825rem;
  font-weight: 600;
  color: var(--color-text-primary, #f8fafc);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.strategy-matrix-ident__meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--color-text-muted, #94a3b8);
}

.meta-family {
  background: var(--color-surface-raised, rgba(255, 255, 255, 0.06));
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
}

.matrix-cell {
  text-align: center;
  vertical-align: middle;
  padding: 0.75rem 0.5rem;
}

.matrix-cell__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
}

.matrix-cell__rank {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-accent, #38bdf8);
}

.matrix-cell__rate {
  font-family: var(--font-mono, monospace);
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--color-text-primary, #f8fafc);
}

.matrix-cell__delta {
  font-size: 0.75rem;
  font-family: var(--font-mono, monospace);
  color: var(--color-text-muted, #94a3b8);
}

.matrix-cell__delta--pos {
  color: var(--color-success, #4ade80);
}

.matrix-cell__delta--neg {
  color: var(--color-danger, #f87171);
}

.matrix-cell__unranked {
  font-size: 0.75rem;
  color: var(--color-text-muted, #94a3b8);
  font-style: italic;
}

.matrix-cell__unavailable {
  font-size: 0.75rem;
}

.unavailable-label {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  background: var(--color-surface-sunken, rgba(255, 255, 255, 0.04));
  color: var(--color-text-muted, #64748b);
  border: 1px solid var(--color-border-subtle, rgba(255, 255, 255, 0.08));
}
</style>
