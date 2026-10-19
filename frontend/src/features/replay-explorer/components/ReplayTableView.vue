<script setup lang="ts">
import { computed, ref } from 'vue'

import DataTable from '../../../components/DataTable.vue'
import StatusBadge from '../../../components/StatusBadge.vue'
import type { GameCode, ReplayExplorerItem } from '../types'

const props = withDefaults(
  defineProps<{
    game: GameCode
    items: ReplayExplorerItem[]
    loading?: boolean
    selectedForCompare?: string[]
  }>(),
  {
    loading: false,
    selectedForCompare: () => [],
  },
)

const emit = defineEmits<{
  (e: 'inspect', item: ReplayExplorerItem): void
  (e: 'toggle-compare', strategyId: string): void
}>()

const PAGE_SIZE = 15
const currentPage = ref(1)
const sortField = ref<keyof ReplayExplorerItem>('rank')
const sortDirection = ref<'asc' | 'desc'>('asc')

function setSort(field: keyof ReplayExplorerItem): void {
  if (sortField.value === field) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDirection.value = 'asc'
  }
  currentPage.value = 1
}

const sortedItems = computed(() => {
  const list = [...props.items]
  const field = sortField.value
  const dir = sortDirection.value === 'asc' ? 1 : -1

  return list.sort((a, b) => {
    // Put unavailable items at the bottom when sorting by metrics
    if (a.isAvailable !== b.isAvailable) {
      return a.isAvailable ? -1 : 1
    }

    const valA = a[field]
    const valB = b[field]

    if (valA === null || valA === undefined) return 1
    if (valB === null || valB === undefined) return -1

    if (typeof valA === 'number' && typeof valB === 'number') {
      return (valA - valB) * dir
    }
    return String(valA).localeCompare(String(valB)) * dir
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(sortedItems.value.length / PAGE_SIZE)))

const paginatedItems = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return sortedItems.value.slice(start, start + PAGE_SIZE)
})

function prevPage(): void {
  if (currentPage.value > 1) currentPage.value--
}

function nextPage(): void {
  if (currentPage.value < totalPages.value) currentPage.value++
}

function isCompared(strategyId: string): boolean {
  return props.selectedForCompare.includes(strategyId)
}
</script>

<template>
  <div class="replay-table-view">
    <DataTable
      caption="Replay Explorer Results"
      :loading="loading"
      :empty="!loading && items.length === 0"
      empty-message="No replay records match the selected filters."
      min-width="960px"
    >
      <template #head>
        <tr>
          <th scope="col" class="th--sortable" @click="setSort('rank')">
            <span>Rank</span>
            <span v-if="sortField === 'rank'" class="sort-arrow">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
          </th>
          <th scope="col" class="th--sortable" @click="setSort('displayLabel')">
            <span>Strategy</span>
            <span v-if="sortField === 'displayLabel'" class="sort-arrow">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
          </th>
          <th scope="col">Version</th>
          <th scope="col" class="th--sortable" @click="setSort('ticketCount')">
            <span>Tickets</span>
            <span v-if="sortField === 'ticketCount'" class="sort-arrow">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
          </th>
          <th scope="col">Period / Run</th>
          <th scope="col" class="th--number">Evaluated Targets</th>
          <th scope="col" class="th--number">Winning Hits</th>
          <th scope="col" class="th--sortable th--number" @click="setSort('hitRate')">
            <span>Hit Rate</span>
            <span v-if="sortField === 'hitRate'" class="sort-arrow">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
          </th>
          <th v-if="game === 'B649'" scope="col" class="th--sortable th--number" @click="setSort('baselineDelta')">
            <span>Baseline Delta</span>
            <span v-if="sortField === 'baselineDelta'" class="sort-arrow">{{ sortDirection === 'asc' ? '▲' : '▼' }}</span>
          </th>
          <th scope="col">Best Hit</th>
          <th scope="col">Evidence</th>
          <th scope="col" class="th--actions">Actions</th>
        </tr>
      </template>

      <tr
        v-for="item in paginatedItems"
        :key="item.id"
        :class="{ 'row--unavailable': !item.isAvailable, 'row--compared': isCompared(item.strategyId) }"
      >
        <!-- Rank -->
        <td class="cell--rank">
          <span v-if="item.rank !== null" class="rank-badge" :class="{ 'rank-badge--top': item.rank <= 3 }">
            #{{ item.rank }}
          </span>
          <span v-else class="text-muted">—</span>
        </td>

        <!-- Strategy -->
        <td class="cell--strategy">
          <button
            type="button"
            class="strategy-link"
            :title="`Inspect ${item.displayLabel}`"
            @click="emit('inspect', item)"
          >
            <strong>{{ item.displayLabel }}</strong>
          </button>
          <div v-if="item.methodFamily" class="strategy-family text-muted">
            {{ item.methodFamily }}
          </div>
        </td>

        <!-- Version -->
        <td class="cell--version">
          <code>{{ item.strategyVersion }}</code>
        </td>

        <!-- Ticket Count -->
        <td class="cell--ticket">
          <span class="ticket-tag" :class="{ 'ticket-tag--unavailable': !item.isAvailable }">
            {{ item.ticketCount }}T
          </span>
        </td>

        <!-- Period / Run -->
        <td class="cell--period">
          <span class="period-badge">{{ item.periodLabel }}</span>
        </td>

        <!-- Evaluated Targets -->
        <td class="cell--number">
          <span v-if="item.evaluatedTargets !== null">{{ item.evaluatedTargets.toLocaleString() }}</span>
          <span v-else class="text-muted">—</span>
        </td>

        <!-- Winning Hits -->
        <td class="cell--number">
          <span v-if="item.winningTargets !== null">{{ item.winningTargets.toLocaleString() }}</span>
          <span v-else class="text-muted">—</span>
        </td>

        <!-- Hit Rate -->
        <td class="cell--number cell--rate">
          <strong v-if="item.hitRate !== null" class="hit-rate-val">{{ item.hitRateFormatted }}</strong>
          <span v-else class="unavailable-label">Unavailable</span>
        </td>

        <!-- Baseline Delta (B649) -->
        <td v-if="game === 'B649'" class="cell--number cell--delta">
          <span
            v-if="item.baselineDelta !== null"
            :class="{
              'delta--positive': item.baselineDelta > 0,
              'delta--negative': item.baselineDelta < 0,
              'delta--zero': item.baselineDelta === 0,
            }"
          >
            {{ item.baselineDeltaFormatted }}
          </span>
          <span v-else class="text-muted">—</span>
        </td>

        <!-- Best Hit -->
        <td class="cell--best-hit">
          <span v-if="item.isAvailable" class="best-hit-pill">{{ item.bestHit }}</span>
          <span v-else class="text-muted">—</span>
        </td>

        <!-- Evidence Status -->
        <td class="cell--evidence">
          <StatusBadge
            :status="item.evidenceStatus"
            :variant="
              item.evidenceStatus === 'DESCRIPTIVE LEADER' || item.evidenceStatus === 'PARETO FRONTIER'
                ? 'success'
                : item.evidenceStatus === 'LOW POWER' || item.evidenceStatus === 'LIMITED SAMPLE' || item.evidenceStatus === 'EXPLORATORY'
                  ? 'warning'
                  : item.evidenceStatus === 'EVIDENCE UNAVAILABLE'
                    ? 'neutral'
                    : 'info'
            "
          />
        </td>

        <!-- Actions -->
        <td class="cell--actions">
          <div class="action-buttons">
            <button
              type="button"
              class="button button--small button--quiet"
              :aria-pressed="isCompared(item.strategyId)"
              :class="{ 'button--active': isCompared(item.strategyId) }"
              @click="emit('toggle-compare', item.strategyId)"
            >
              {{ isCompared(item.strategyId) ? 'Comparing' : 'Compare' }}
            </button>
            <button
              type="button"
              class="button button--small button--primary"
              @click="emit('inspect', item)"
            >
              Inspect
            </button>
          </div>
        </td>
      </tr>

      <template #pagination>
        <div class="pagination-controls">
          <span class="pagination-info text-muted">
            Showing {{ (currentPage - 1) * PAGE_SIZE + 1 }}–{{
              Math.min(currentPage * PAGE_SIZE, sortedItems.length)
            }} of {{ sortedItems.length }} rows
          </span>
          <div class="pagination-buttons">
            <button
              type="button"
              class="button button--small button--quiet"
              :disabled="currentPage <= 1"
              @click="prevPage"
            >
              Previous
            </button>
            <span class="page-indicator">Page {{ currentPage }} / {{ totalPages }}</span>
            <button
              type="button"
              class="button button--small button--quiet"
              :disabled="currentPage >= totalPages"
              @click="nextPage"
            >
              Next
            </button>
          </div>
        </div>
      </template>
    </DataTable>
  </div>
</template>

<style scoped>
.replay-table-view {
  width: 100%;
}

.th--sortable {
  cursor: pointer;
  user-select: none;
}

.th--sortable:hover {
  color: var(--color-cyan-300, #67e8f9);
}

.sort-arrow {
  margin-left: 0.35rem;
  font-size: 0.75rem;
}

.th--number,
.cell--number {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.th--actions,
.cell--actions {
  text-align: right;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-gray-200, #e2e8f0);
}

.rank-badge--top {
  background: rgba(99, 102, 241, 0.2);
  color: var(--color-indigo-300, #a5b4fc);
  border: 1px solid rgba(99, 102, 241, 0.4);
}

.strategy-link {
  background: none;
  border: none;
  padding: 0;
  color: var(--color-cyan-400, #38bdf8);
  font-size: 0.9rem;
  text-align: left;
  cursor: pointer;
  text-decoration: underline;
  text-decoration-color: transparent;
  transition: text-decoration-color 0.15s ease;
}

.strategy-link:hover {
  text-decoration-color: var(--color-cyan-400, #38bdf8);
}

.strategy-family {
  font-size: 0.75rem;
  margin-top: 0.15rem;
}

.ticket-tag {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  background: rgba(6, 182, 212, 0.15);
  color: var(--color-cyan-300, #67e8f9);
  font-size: 0.8rem;
  font-weight: 600;
}

.ticket-tag--unavailable {
  background: rgba(148, 163, 184, 0.1);
  color: var(--color-gray-400, #94a3b8);
}

.period-badge {
  font-size: 0.8rem;
  color: var(--color-gray-300, #cbd5e1);
}

.hit-rate-val {
  color: var(--color-cyan-300, #67e8f9);
  font-size: 0.95rem;
}

.unavailable-label {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-red-400, #f87171);
  font-size: 0.75rem;
}

.delta--positive {
  color: var(--color-emerald-400, #34d399);
  font-weight: 600;
}

.delta--negative {
  color: var(--color-rose-400, #fb7185);
}

.delta--zero {
  color: var(--color-gray-400, #94a3b8);
}

.best-hit-pill {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
  font-size: 0.8rem;
  color: var(--color-gray-200, #e2e8f0);
}

.action-buttons {
  display: inline-flex;
  gap: 0.4rem;
  justify-content: flex-end;
}

.row--unavailable {
  opacity: 0.65;
}

.row--compared {
  background: rgba(99, 102, 241, 0.08);
}

.pagination-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.pagination-buttons {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.page-indicator {
  font-size: 0.85rem;
  color: var(--color-gray-300, #cbd5e1);
}

.text-muted {
  color: var(--color-gray-400, #94a3b8);
}
</style>
