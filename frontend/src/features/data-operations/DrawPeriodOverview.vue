<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import {
  listDraws,
  type IngestionRunLotteryType,
} from '../../api/drawData'

type PeriodLoadState = 'loading' | 'ready' | 'empty' | 'unavailable'

interface GamePeriodState {
  status: PeriodLoadState
  totalCount: number | null
  latestDrawNumber: string
  latestDrawDate: string
  error: string
}

interface LotteryGameConfig {
  lotteryType: IngestionRunLotteryType
  code: string
  name: string
}

const LOTTERY_GAMES: LotteryGameConfig[] = [
  { lotteryType: 'BIG_LOTTO', code: 'B649', name: 'Big Lotto' },
  { lotteryType: 'POWER_LOTTO', code: 'P638', name: 'Power Lotto' },
  { lotteryType: 'DAILY_539', code: 'T539', name: 'Daily 539' },
]

const gameStates = reactive<Record<IngestionRunLotteryType, GamePeriodState>>({
  BIG_LOTTO: {
    status: 'loading',
    totalCount: null,
    latestDrawNumber: '—',
    latestDrawDate: '—',
    error: '',
  },
  POWER_LOTTO: {
    status: 'loading',
    totalCount: null,
    latestDrawNumber: '—',
    latestDrawDate: '—',
    error: '',
  },
  DAILY_539: {
    status: 'loading',
    totalCount: null,
    latestDrawNumber: '—',
    latestDrawDate: '—',
    error: '',
  },
})

const controllers = new Map<IngestionRunLotteryType, AbortController>()
const requestSeq = new Map<IngestionRunLotteryType, number>()
let activeRefreshCount = 0
const isRefreshing = ref(false)
let unmounted = false

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

async function fetchGamePeriod(lotteryType: IngestionRunLotteryType): Promise<void> {
  controllers.get(lotteryType)?.abort()
  const controller = new AbortController()
  controllers.set(lotteryType, controller)

  const seq = (requestSeq.get(lotteryType) ?? 0) + 1
  requestSeq.set(lotteryType, seq)

  const state = gameStates[lotteryType]
  state.status = 'loading'
  state.error = ''

  try {
    const response = await listDraws(
      {
        lotteryType,
        drawNumber: '',
        dateFrom: '',
        dateTo: '',
        page: 1,
        pageSize: 1,
      },
      controller.signal,
    )

    if (unmounted || requestSeq.get(lotteryType) !== seq) return

    if (response.total_count === 0 || response.records.length === 0) {
      state.status = 'empty'
      state.totalCount = 0
      state.latestDrawNumber = '—'
      state.latestDrawDate = '—'
      state.error = ''
    } else {
      const latest = response.records[0]
      state.status = 'ready'
      state.totalCount = response.total_count
      state.latestDrawNumber = latest.draw_number
      state.latestDrawDate = latest.draw_date
      state.error = ''
    }
  } catch (error: unknown) {
    if (unmounted || requestSeq.get(lotteryType) !== seq || isAbort(error)) return

    state.status = 'unavailable'
    state.totalCount = null
    state.latestDrawNumber = '—'
    state.latestDrawDate = '—'
    state.error = error instanceof Error ? error.message : 'Draw data unavailable'
  } finally {
    if (controllers.get(lotteryType) === controller) {
      controllers.delete(lotteryType)
    }
  }
}

async function refreshAll(): Promise<void> {
  activeRefreshCount++
  isRefreshing.value = true
  try {
    await Promise.all(LOTTERY_GAMES.map((game) => fetchGamePeriod(game.lotteryType)))
  } finally {
    activeRefreshCount--
    if (activeRefreshCount <= 0) {
      activeRefreshCount = 0
      isRefreshing.value = false
    }
  }
}

defineExpose({
  fetchGamePeriod,
  refreshAll,
  gameStates,
})

function displayTotalCount(state: GamePeriodState): string {
  if (state.status === 'loading') return '—'
  if (state.status === 'unavailable') return 'Unavailable'
  if (state.totalCount !== null) return String(state.totalCount)
  return '—'
}

onMounted(() => {
  void refreshAll()
})

onBeforeUnmount(() => {
  unmounted = true
  for (const controller of controllers.values()) {
    controller.abort()
  }
  controllers.clear()
})
</script>

<template>
  <article class="panel period-overview-panel" data-testid="draw-period-overview" aria-labelledby="period-overview-heading">
    <div class="panel__heading">
      <div>
        <p class="step-label">Canonical Database Summary · 3 Games</p>
        <h2 id="period-overview-heading">Draw Period Overview</h2>
      </div>
      <div class="header-actions">
        <button
          type="button"
          class="button button--quiet"
          data-testid="refresh-overview"
          :aria-busy="isRefreshing"
          @click="refreshAll"
        >
          {{ isRefreshing ? 'Refreshing…' : 'Refresh overview' }}
        </button>
      </div>
    </div>

    <div class="period-cards-grid">
      <div
        v-for="game in LOTTERY_GAMES"
        :key="game.lotteryType"
        class="period-card"
        :class="`period-card--${gameStates[game.lotteryType].status}`"
        :data-testid="`period-card-${game.code}`"
        :aria-label="`${game.code} draw period summary`"
      >
        <div class="period-card__header">
          <div class="period-card__identity">
            <span class="period-card__badge-code" :data-testid="`code-${game.code}`">{{ game.code }}</span>
            <span class="period-card__name">{{ game.name }}</span>
          </div>
          <span
            class="period-status-badge"
            :class="`period-status-badge--${gameStates[game.lotteryType].status}`"
            :data-testid="`status-${game.code}`"
          >
            {{ gameStates[game.lotteryType].status.toUpperCase() }}
          </span>
        </div>

        <div class="period-card__body">
          <div class="period-stat">
            <span class="period-stat__label">Total Draws</span>
            <strong
              class="period-stat__value"
              :data-testid="`total-count-${game.code}`"
            >
              {{ displayTotalCount(gameStates[game.lotteryType]) }}
            </strong>
          </div>

          <div class="period-meta-grid">
            <div class="period-meta-item">
              <span class="period-meta-label">Latest Draw</span>
              <code
                class="period-meta-value draw-number"
                :data-testid="`latest-draw-${game.code}`"
              >
                {{ gameStates[game.lotteryType].latestDrawNumber }}
              </code>
            </div>
            <div class="period-meta-item">
              <span class="period-meta-label">Latest Date</span>
              <span
                class="period-meta-value draw-date"
                :data-testid="`latest-date-${game.code}`"
              >
                {{ gameStates[game.lotteryType].latestDrawDate }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="gameStates[game.lotteryType].status === 'unavailable'" class="period-card__footer">
          <small class="error-text" :data-testid="`error-${game.code}`">
            {{ gameStates[game.lotteryType].error || 'Draw data unavailable' }}
          </small>
          <button
            type="button"
            class="button button--quiet card-retry-btn"
            :data-testid="`retry-${game.code}`"
            @click="fetchGamePeriod(game.lotteryType)"
          >
            Retry
          </button>
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.period-overview-panel {
  margin-top: 24px;
}

.panel__heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.period-cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (max-width: 900px) {
  .period-cards-grid {
    grid-template-columns: 1fr;
  }
}

.period-card {
  background: var(--bg-card, rgba(18, 24, 38, 0.72));
  border: 1px solid var(--line, rgba(255, 255, 255, 0.1));
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: border-color 0.15s ease;
}

.period-card:hover {
  border-color: rgba(255, 255, 255, 0.2);
}

.period-card--ready {
  border-left: 3px solid var(--color-success, #10b981);
}

.period-card--empty {
  border-left: 3px solid var(--muted, #94a3b8);
}

.period-card--loading {
  border-left: 3px solid var(--color-info, #6366f1);
}

.period-card--unavailable {
  border-left: 3px solid var(--color-danger, #ef4444);
}

.period-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.period-card__identity {
  display: flex;
  align-items: center;
  gap: 8px;
}

.period-card__badge-code {
  font-family: var(--font-mono, monospace);
  font-weight: 700;
  font-size: 0.85rem;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--ink, #f8fafc);
}

.period-card__name {
  font-weight: 600;
  color: var(--ink, #f8fafc);
  font-size: 0.95rem;
}

.period-status-badge {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  padding: 2px 8px;
  border-radius: 12px;
}

.period-status-badge--ready {
  background: var(--color-success-bg, rgba(16, 185, 129, 0.14));
  color: var(--color-success, #10b981);
  border: 1px solid var(--color-success-border, rgba(16, 185, 129, 0.35));
}

.period-status-badge--empty {
  background: rgba(148, 163, 184, 0.14);
  color: var(--muted, #94a3b8);
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.period-status-badge--loading {
  background: var(--color-info-bg, rgba(99, 102, 241, 0.14));
  color: var(--color-info, #6366f1);
  border: 1px solid var(--color-info-border, rgba(99, 102, 241, 0.35));
}

.period-status-badge--unavailable {
  background: var(--color-danger-bg, rgba(239, 68, 68, 0.14));
  color: var(--color-danger, #ef4444);
  border: 1px solid var(--color-danger-border, rgba(239, 68, 68, 0.35));
}

.period-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.period-stat__label {
  font-size: 0.75rem;
  color: var(--muted, #94a3b8);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.period-stat__value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--ink, #f8fafc);
  line-height: 1.2;
}

.period-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--line, rgba(255, 255, 255, 0.08));
}

.period-meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.period-meta-label {
  font-size: 0.7rem;
  color: var(--muted, #94a3b8);
}

.period-meta-value {
  font-size: 0.875rem;
  color: var(--ink, #f8fafc);
  font-weight: 500;
}

.draw-number {
  font-family: var(--font-mono, monospace);
  font-weight: 600;
  color: var(--mint, #38bdf8);
}

.period-card__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--line, rgba(255, 255, 255, 0.08));
}

.error-text {
  color: var(--color-danger, #ef4444);
  font-size: 0.75rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.card-retry-btn {
  font-size: 0.75rem;
  padding: 2px 8px;
}
</style>
