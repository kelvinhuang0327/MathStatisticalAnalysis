<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  LIFECYCLE_STATUSES,
  LOTTERY_TYPES,
  queryStrategyOverview,
  type LifecycleStatus,
  type LotteryType,
  type StrategyOverviewFilters,
  type StrategyOverviewItem,
  type StrategyOverviewResponse,
} from '../../api/strategies'

type LoadState = 'loading' | 'ready' | 'filtered-empty' | 'catalog-empty' | 'error'
type ExecutableFilter = '' | 'true' | 'false'

const overview = ref<StrategyOverviewResponse | null>(null)
const loadState = ref<LoadState>('loading')
const errorMessage = ref('')
const searchQuery = ref('')
const lotteryType = ref<LotteryType | ''>('')
const lifecycleStatus = ref<LifecycleStatus | ''>('')
const executable = ref<ExecutableFilter>('')
let requestController: AbortController | undefined
let requestGeneration = 0
let isMounted = false

const hasActiveFilters = computed(
  () =>
    searchQuery.value.trim().length > 0 ||
    lotteryType.value !== '' ||
    lifecycleStatus.value !== '' ||
    executable.value !== '',
)

function currentFilters(): StrategyOverviewFilters {
  const filters: StrategyOverviewFilters = {}
  const query = searchQuery.value.trim()
  if (query) filters.q = query
  if (lotteryType.value) filters.lottery_type = lotteryType.value
  if (lifecycleStatus.value) filters.lifecycle_status = lifecycleStatus.value
  if (executable.value) filters.executable = executable.value === 'true'
  return filters
}

function isExecutable(strategy: StrategyOverviewItem): boolean {
  return strategy.lifecycle_status === 'ONLINE' && strategy.executable
}

function executionLabel(strategy: StrategyOverviewItem): string {
  return isExecutable(strategy) ? 'Executable' : 'Metadata only'
}

function loadResultState(response: StrategyOverviewResponse): LoadState {
  if (response.summary.total > 0) return 'ready'
  return hasActiveFilters.value ? 'filtered-empty' : 'catalog-empty'
}

async function loadStrategyOverview(): Promise<void> {
  const generation = ++requestGeneration
  requestController?.abort()
  const controller = new AbortController()
  requestController = controller
  overview.value = null
  loadState.value = 'loading'
  errorMessage.value = ''

  try {
    const response = await queryStrategyOverview(currentFilters(), controller.signal)
    if (!isMounted || generation !== requestGeneration || controller.signal.aborted) return
    overview.value = response
    loadState.value = loadResultState(response)
  } catch (error: unknown) {
    if (!isMounted || generation !== requestGeneration || controller.signal.aborted) return
    errorMessage.value =
      error instanceof Error ? error.message : 'Unable to load Strategy Overview'
    loadState.value = 'error'
  }
}

function resetFilters(): void {
  searchQuery.value = ''
  lotteryType.value = ''
  lifecycleStatus.value = ''
  executable.value = ''
  void loadStrategyOverview()
}

onMounted(() => {
  isMounted = true
  void loadStrategyOverview()
})
onBeforeUnmount(() => {
  isMounted = false
  requestGeneration += 1
  requestController?.abort()
})
</script>

<template>
  <section class="catalog" aria-labelledby="strategy-catalog-title">
    <header class="catalog__heading">
      <div>
        <p class="eyebrow">P600F · DB-free metadata query</p>
        <h1 id="strategy-catalog-title">Strategy Overview</h1>
        <p class="catalog__intro">
          Query canonical strategy descriptors and their provenance. Results retain catalog
          declaration order and do not imply measured quality.
        </p>
      </div>
      <div class="catalog__scope" aria-label="Strategy query result count">
        <span>Query result</span>
        <strong>{{ overview?.summary.total ?? '—' }}</strong>
        <small>strategies</small>
      </div>
    </header>

    <section class="strategy-filters" aria-labelledby="strategy-filter-title">
      <div class="strategy-filters__heading">
        <div>
          <p class="eyebrow">Descriptor filters</p>
          <h2 id="strategy-filter-title">Narrow the canonical catalog</h2>
        </div>
        <p>All supplied filters use AND semantics.</p>
      </div>
      <form class="strategy-filter-grid" @submit.prevent="loadStrategyOverview">
        <label>
          <span>Strategy ID or display name</span>
          <input
            v-model="searchQuery"
            name="q"
            type="search"
            maxlength="100"
            autocomplete="off"
            placeholder="Search metadata"
          />
        </label>
        <label>
          <span>Lottery type</span>
          <select v-model="lotteryType" name="lottery_type" @change="loadStrategyOverview">
            <option value="">All lottery types</option>
            <option v-for="kind in LOTTERY_TYPES" :key="kind" :value="kind">{{ kind }}</option>
          </select>
        </label>
        <label>
          <span>Lifecycle</span>
          <select
            v-model="lifecycleStatus"
            name="lifecycle_status"
            @change="loadStrategyOverview"
          >
            <option value="">All lifecycle states</option>
            <option v-for="status in LIFECYCLE_STATUSES" :key="status" :value="status">
              {{ status }}
            </option>
          </select>
        </label>
        <label>
          <span>Execution metadata</span>
          <select v-model="executable" name="executable" @change="loadStrategyOverview">
            <option value="">All descriptors</option>
            <option value="true">Executable</option>
            <option value="false">Metadata only</option>
          </select>
        </label>
        <div class="strategy-filter-actions">
          <button class="strategy-filter-submit" type="submit">Search metadata</button>
          <button class="strategy-filter-reset" type="button" @click="resetFilters">
            Reset filters
          </button>
        </div>
      </form>
    </section>

    <div class="catalog__status" aria-live="polite">
      <p v-if="loadState === 'loading'" class="state-panel">Loading Strategy Overview…</p>
      <div v-else-if="loadState === 'error'" class="state-panel state-panel--error">
        <p>{{ errorMessage }}</p>
        <button class="catalog__retry" type="button" @click="loadStrategyOverview">Retry</button>
      </div>
      <p v-else-if="loadState === 'filtered-empty'" class="state-panel">
        No strategies match the current filters.
      </p>
      <p v-else-if="loadState === 'catalog-empty'" class="state-panel">
        No strategies are available in the canonical Strategy Catalog.
      </p>
    </div>

    <template v-if="overview && loadState !== 'loading' && loadState !== 'error'">
      <section class="strategy-summary" aria-labelledby="strategy-summary-title">
        <div class="strategy-summary__heading">
          <p class="eyebrow">Returned-result summary</p>
          <h2 id="strategy-summary-title">Descriptor counts</h2>
        </div>
        <dl class="strategy-summary__metrics">
          <div>
            <dt>Total</dt>
            <dd>{{ overview.summary.total }}</dd>
          </div>
          <div>
            <dt>Executable</dt>
            <dd>{{ overview.summary.executable_count }}</dd>
          </div>
          <div>
            <dt>Metadata only</dt>
            <dd>{{ overview.summary.metadata_only_count }}</dd>
          </div>
        </dl>
        <ul class="lifecycle-summary" aria-label="Lifecycle summary">
          <li v-for="status in LIFECYCLE_STATUSES" :key="status">
            <span>{{ status }}</span>
            <strong>{{ overview.summary.lifecycle_counts[status] ?? 0 }}</strong>
          </li>
        </ul>
      </section>

      <aside class="evidence-panel" aria-labelledby="strategy-evidence-title">
        <div>
          <p class="eyebrow">Evidence availability</p>
          <h2 id="strategy-evidence-title">Measured strategy evidence is unavailable</h2>
        </div>
        <ul>
          <li>No canonical evaluation metrics are currently registered.</li>
          <li>D3 status is not yet available.</li>
          <li>Best-strategy ranking is not yet available.</li>
          <li>Metadata lifecycle or execution status must not be interpreted as quality.</li>
        </ul>
        <div class="evidence-panel__reasons" aria-label="Unavailability reason codes">
          <code
            v-for="reason in overview.capabilities.unavailable_reason_codes"
            :key="reason"
          >
            {{ reason }}
          </code>
        </div>
      </aside>
    </template>

    <ul v-if="overview && loadState === 'ready'" class="strategy-grid" aria-label="Strategies">
      <li v-for="strategy in overview.items" :key="strategy.strategy_id" class="strategy-card">
        <div class="strategy-card__topline">
          <span class="lifecycle-badge">{{ strategy.lifecycle_status }}</span>
          <span
            class="execution-badge"
            :class="{ 'execution-badge--enabled': isExecutable(strategy) }"
          >
            {{ executionLabel(strategy) }}
          </span>
        </div>

        <div class="strategy-card__identity">
          <h2>{{ strategy.display_name }}</h2>
          <code>{{ strategy.strategy_id }}</code>
        </div>

        <dl class="strategy-card__facts">
          <div>
            <dt>Version</dt>
            <dd>{{ strategy.version }}</dd>
          </div>
          <div>
            <dt>Lottery types</dt>
            <dd>{{ strategy.supported_lottery_types.join(', ') }}</dd>
          </div>
          <div>
            <dt>Minimum history</dt>
            <dd>{{ strategy.minimum_history }} draw</dd>
          </div>
          <div>
            <dt>Execution availability</dt>
            <dd>{{ isExecutable(strategy) ? 'Available' : 'Unavailable' }}</dd>
          </div>
        </dl>

        <p class="strategy-card__guard">
          <span aria-hidden="true">●</span>
          {{
            isExecutable(strategy)
              ? 'The canonical descriptor marks this strategy executable.'
              : 'This descriptor exposes metadata only; no execution control is available.'
          }}
        </p>

        <details class="strategy-card__provenance">
          <summary>Provenance ({{ strategy.provenance.length }})</summary>
          <ul>
            <li v-for="source in strategy.provenance" :key="source">
              <code>{{ source }}</code>
            </li>
          </ul>
        </details>
      </li>
    </ul>
  </section>
</template>
