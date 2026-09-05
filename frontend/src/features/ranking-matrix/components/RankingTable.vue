<script setup lang="ts">
import { computed } from 'vue'

import DataTable from '../../../components/DataTable.vue'
import StatusBadge from '../../../components/StatusBadge.vue'
import { getWarningMeta } from '../../../api/rankingMatrix'
import type {
  RankingRow,
  SortDirection,
  SortField,
} from '../types'

const props = defineProps<{
  rows: RankingRow[]
  selectedStrategyId: string | null
  sortField: SortField
  sortDirection: SortDirection
  isUserSorted: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'selectStrategy', strategy: RankingRow): void
  (e: 'sort', field: SortField): void
  (e: 'resetSort'): void
}>()

const isFormalRankUnavailable = computed(() => {
  return props.rows.length > 0 && props.rows.every((r) => r.officialRank === null)
})

const sortedRows = computed(() => {
  const list = [...props.rows]
  const field = props.sortField
  const direction = props.sortDirection

  list.sort((a, b) => {
    let comparison = 0
    switch (field) {
      case 'officialRank': {
        const rankA = a.officialRank ?? 999999
        const rankB = b.officialRank ?? 999999
        comparison = rankA - rankB
        if (comparison === 0) {
          comparison = a.strategyId.localeCompare(b.strategyId)
        }
        break
      }
      case 'officialAnyPrizeRate': {
        const rateA = a.officialAnyPrizeRate ?? -1
        const rateB = b.officialAnyPrizeRate ?? -1
        comparison = rateA - rateB
        break
      }
      case 'successes': {
        const succA = a.successes ?? -1
        const succB = b.successes ?? -1
        comparison = succA - succB
        break
      }
      case 'observations': {
        const obsA = a.observations ?? -1
        const obsB = b.observations ?? -1
        comparison = obsA - obsB
        break
      }
      case 'coverage': {
        const covA = a.coverage ?? -1
        const covB = b.coverage ?? -1
        comparison = covA - covB
        break
      }
      case 'baselineDelta': {
        const deltaA = a.baselineDelta ?? -999
        const deltaB = b.baselineDelta ?? -999
        comparison = deltaA - deltaB
        break
      }
      case 'strategyId': {
        comparison = a.displayName.localeCompare(b.displayName)
        break
      }
    }
    return direction === 'asc' ? comparison : -comparison
  })

  return list
})

function handleSort(field: SortField): void {
  emit('sort', field)
}

function handleRowClick(row: RankingRow): void {
  emit('selectStrategy', row)
}

function getSortIndicator(field: SortField): string {
  if (props.sortField !== field) return '↕'
  return props.sortDirection === 'asc' ? '▲' : '▼'
}

function getSortAria(field: SortField): 'ascending' | 'descending' | 'none' {
  if (props.sortField !== field) return 'none'
  return props.sortDirection === 'asc' ? 'ascending' : 'descending'
}

function getDeltaClass(delta: number | null): string {
  if (delta === null) return 'delta--null'
  if (delta > 0) return 'delta--positive'
  if (delta < 0) return 'delta--negative'
  return 'delta--neutral'
}

function getComparabilityBadgeType(status: string): 'success' | 'warning' | 'info' | 'neutral' {
  switch (status) {
    case 'COMPARABLE':
      return 'success'
    case 'NOT_HISTORICALLY_COMPARABLE':
      return 'warning'
    case 'LOW_SAMPLE_SIZE':
    case 'INSUFFICIENT_WINDOW':
      return 'warning'
    default:
      return 'neutral'
  }
}
</script>

<template>
  <div class="ranking-table-container">
    <!-- Sort Status & Reset Banner -->
    <div class="sort-status-bar" data-testid="sort-status-bar">
      <div class="sort-status-bar__info">
        <span class="sort-status-bar__label">排序模式：</span>
        <span
          v-if="!isUserSorted && isFormalRankUnavailable"
          class="sort-status-bar__badge sort-status-bar__badge--unranked"
          data-testid="badge-formal-rank-unavailable"
        >
          ℹ 正規指標可用；官方正式排名尚未發布 (Canonical metrics available; formal rank unavailable)
        </span>
        <span v-else-if="!isUserSorted" class="sort-status-bar__badge sort-status-bar__badge--official">
          ★ 官方正式排名 (Official Rank)
        </span>
        <span v-else class="sort-status-bar__badge sort-status-bar__badge--custom">
          ⚡ 自訂排序 (User Sort: {{ sortField }} {{ sortDirection.toUpperCase() }})
        </span>
      </div>
      <button
        v-if="isUserSorted"
        type="button"
        class="sort-reset-btn"
        data-testid="reset-official-rank-btn"
        @click="emit('resetSort')"
      >
        {{ isFormalRankUnavailable ? '↺ 恢復預設排序' : '↺ 恢復官方排名 (Reset to Official Rank)' }}
      </button>
    </div>

    <!-- Data Table -->
    <DataTable
      :loading="loading"
      :empty="sortedRows.length === 0"
      empty-message="查無符合條件的策略排名資料。"
      min-width="960px"
    >
      <template #head>
        <tr>
          <th
            scope="col"
            class="th-sortable th-rank"
            :aria-sort="getSortAria('officialRank')"
            data-testid="th-official-rank"
            @click="handleSort('officialRank')"
          >
            <span v-if="isFormalRankUnavailable">Rank (未發布) {{ getSortIndicator('officialRank') }}</span>
            <span v-else>Rank {{ getSortIndicator('officialRank') }}</span>
          </th>
          <th
            scope="col"
            class="th-sortable th-strategy"
            :aria-sort="getSortAria('strategyId')"
            data-testid="th-strategy"
            @click="handleSort('strategyId')"
          >
            <span>Strategy {{ getSortIndicator('strategyId') }}</span>
          </th>
          <th
            scope="col"
            class="th-sortable th-rate"
            :aria-sort="getSortAria('officialAnyPrizeRate')"
            data-testid="th-rate"
            @click="handleSort('officialAnyPrizeRate')"
          >
            <span>Official Any-Prize Rate {{ getSortIndicator('officialAnyPrizeRate') }}</span>
          </th>
          <th
            scope="col"
            class="th-sortable th-counts"
            :aria-sort="getSortAria('successes')"
            data-testid="th-successes"
            @click="handleSort('successes')"
          >
            <span>Successes / Observations {{ getSortIndicator('successes') }}</span>
          </th>
          <th
            scope="col"
            class="th-sortable th-coverage"
            :aria-sort="getSortAria('coverage')"
            data-testid="th-coverage"
            @click="handleSort('coverage')"
          >
            <span>Coverage {{ getSortIndicator('coverage') }}</span>
          </th>
          <th
            scope="col"
            class="th-sortable th-delta"
            :aria-sort="getSortAria('baselineDelta')"
            data-testid="th-baseline-delta"
            @click="handleSort('baselineDelta')"
          >
            <span>Baseline Delta {{ getSortIndicator('baselineDelta') }}</span>
          </th>
          <th scope="col" class="th-prize" data-testid="th-best-prize">
            <span>Best Official Prize</span>
          </th>
          <th scope="col" class="th-status" data-testid="th-comparability">
            <span>Comparability / Warnings</span>
          </th>
        </tr>
      </template>

      <tr
        v-for="row in sortedRows"
        :key="row.strategyId"
        class="ranking-row"
        :class="{ 'ranking-row--selected': row.strategyId === selectedStrategyId }"
        :data-testid="`ranking-row-${row.strategyId}`"
        @click="handleRowClick(row)"
      >
        <!-- Rank -->
        <td class="td-rank">
          <span v-if="row.officialRank !== null" class="rank-badge" :class="{ 'rank-badge--top3': row.officialRank <= 3 }">
            #{{ row.officialRank }}
          </span>
          <span v-else class="rank-badge rank-badge--unranked" title="未排名">
            —
          </span>
        </td>

        <!-- Strategy -->
        <td class="td-strategy">
          <div class="strategy-info">
            <strong class="strategy-name">{{ row.displayName }}</strong>
            <div class="strategy-meta">
              <span class="strategy-id">{{ row.strategyId }}</span>
              <span v-if="row.methodFamily" class="strategy-family">{{ row.methodFamily }}</span>
              <span class="strategy-lifecycle">{{ row.lifecycleStatus }}</span>
            </div>
          </div>
        </td>

        <!-- Official Any-Prize Rate -->
        <td class="td-rate">
          <span v-if="row.officialAnyPrizeRate !== null" class="rate-value">
            {{ row.officialAnyPrizeRateFormatted }}
          </span>
          <span v-else class="text-unavailable">
            {{ row.officialAnyPrizeRateFormatted }}
          </span>
        </td>

        <!-- Successes / Observations -->
        <td class="td-counts">
          <div v-if="row.successes !== null || row.observations !== null" class="counts-wrap">
            <span class="counts-main">
              {{ row.successes !== null ? row.successes : '—' }} / {{ row.observations !== null ? row.observations : '—' }}
            </span>
            <small class="counts-label">中獎期數 / 觀察期數</small>
          </div>
          <span v-else class="text-unavailable">Unavailable</span>
        </td>

        <!-- Coverage -->
        <td class="td-coverage">
          <div v-if="row.coverage !== null" class="coverage-wrap">
            <div class="coverage-bar-bg">
              <div
                class="coverage-bar-fill"
                :style="{ width: `${Math.min(100, Math.max(0, row.coverage * 100))}%` }"
              />
            </div>
            <span class="coverage-text">{{ row.coverageFormatted }}</span>
          </div>
          <span v-else class="text-unavailable">Unavailable</span>
        </td>

        <!-- Baseline Delta -->
        <td class="td-delta">
          <span :class="['delta-badge', getDeltaClass(row.baselineDelta)]">
            {{ row.baselineDeltaFormatted }}
          </span>
        </td>

        <!-- Best Official Prize -->
        <td class="td-prize">
          <span class="prize-pill">{{ row.bestOfficialPrize }}</span>
        </td>

        <!-- Comparability / Warnings -->
        <td class="td-status">
          <div class="status-cell-wrap">
            <StatusBadge
              :status="getComparabilityBadgeType(row.comparabilityStatus)"
              :label="row.comparabilityLabel"
              size="sm"
            />
            <div v-if="row.warningCodes.length > 0" class="warning-chips">
              <span
                v-for="code in row.warningCodes"
                :key="code"
                class="warning-chip"
                :title="getWarningMeta(code).description"
                :data-testid="`warning-chip-${code}`"
              >
                ⚠ {{ getWarningMeta(code).label }}
              </span>
            </div>
          </div>
        </td>
      </tr>
    </DataTable>
  </div>
</template>

<style scoped>
.ranking-table-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-3, 12px);
  width: 100%;
}

.sort-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  background: var(--bg-tertiary, #131927);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  border-radius: var(--radius-md, 10px);
  font-size: 0.85rem;
}

.sort-status-bar__info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sort-status-bar__label {
  color: var(--text-tertiary, #64748b);
}

.sort-status-bar__badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-sm, 6px);
  font-weight: 600;
  font-size: 0.8rem;
}

.sort-status-bar__badge--official {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.sort-status-bar__badge--custom {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.sort-status-bar__badge--unranked {
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.sort-reset-btn {
  background: rgba(56, 189, 248, 0.12);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.3);
  padding: 4px 10px;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.sort-reset-btn:hover {
  background: rgba(56, 189, 248, 0.22);
  border-color: #38bdf8;
}

.th-sortable {
  cursor: pointer;
  user-select: none;
  transition: color 0.15s ease;
}

.th-sortable:hover {
  color: var(--text-accent, #a78bfa);
}

.ranking-row {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.ranking-row:hover {
  background-color: var(--bg-card-hover, rgba(26, 34, 52, 0.85));
}

.ranking-row--selected {
  background-color: rgba(99, 102, 241, 0.18) !important;
  border-left: 3px solid var(--primary-color, #8b5cf6);
}

.td-rank {
  font-family: var(--font-mono, monospace);
  white-space: nowrap;
}

.rank-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  font-weight: 600;
}

.rank-badge--top3 {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(239, 68, 68, 0.25));
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.4);
}

.rank-badge--unranked {
  color: var(--text-tertiary, #64748b);
}

.strategy-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.strategy-name {
  color: var(--text-primary, #f8fafc);
  font-size: 0.9rem;
}

.strategy-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: var(--text-tertiary, #64748b);
  flex-wrap: wrap;
}

.strategy-id {
  font-family: var(--font-mono, monospace);
}

.strategy-family {
  background: rgba(255, 255, 255, 0.05);
  padding: 1px 4px;
  border-radius: 3px;
}

.strategy-lifecycle {
  background: rgba(99, 102, 241, 0.12);
  color: #a5b4fc;
  padding: 1px 4px;
  border-radius: 3px;
}

.rate-value {
  font-family: var(--font-mono, monospace);
  font-weight: 600;
  color: #38bdf8;
}

.counts-wrap {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.counts-main {
  font-family: var(--font-mono, monospace);
  font-size: 0.85rem;
}

.counts-label {
  font-size: 0.7rem;
  color: var(--text-tertiary, #64748b);
}

.coverage-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.coverage-bar-bg {
  width: 50px;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}

.coverage-bar-fill {
  height: 100%;
  background: #34d399;
  border-radius: 3px;
}

.coverage-text {
  font-family: var(--font-mono, monospace);
  font-size: 0.82rem;
}

.delta-badge {
  display: inline-block;
  font-family: var(--font-mono, monospace);
  font-weight: 600;
  font-size: 0.85rem;
  padding: 2px 6px;
  border-radius: 4px;
}

.delta--positive {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.delta--negative {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.delta--neutral {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-secondary, #94a3b8);
}

.delta--null {
  color: var(--text-tertiary, #64748b);
}

.prize-pill {
  font-size: 0.8rem;
  color: var(--text-secondary, #94a3b8);
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
}

.status-cell-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}

.warning-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.warning-chip {
  display: inline-flex;
  align-items: center;
  font-size: 0.72rem;
  padding: 1px 5px;
  background: rgba(245, 158, 11, 0.14);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 3px;
  cursor: help;
  white-space: nowrap;
}

.text-unavailable {
  color: var(--text-tertiary, #64748b);
  font-style: italic;
  font-size: 0.82rem;
}
</style>
