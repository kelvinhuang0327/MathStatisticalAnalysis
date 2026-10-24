<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import DataTable from '../../components/DataTable.vue'
import EmptyState from '../../components/EmptyState.vue'
import FilterBar from '../../components/FilterBar.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import { lotteryTypeDisplayLabel } from '../../utils/lotteryDisplayLabel'
import type { LotteryType } from '../../api/strategies'
import type {
  EvidenceStatusFilter,
  ExecutableFilter,
  GameFilter,
  LifecycleFilter,
  StrategyCombinedItem,
  ViewMode,
} from './types'

const props = withDefaults(
  defineProps<{
    items: StrategyCombinedItem[]
    totalCount: number
    executableCount: number
    metadataOnlyCount: number
    lifecycleCounts: Record<string, number>
    unavailableReasons: string[]
    selectedLotteryType?: LotteryType
    bestStrategyStatus?: string
    bestStrategyReason?: string
  }>(),
  {
    selectedLotteryType: 'BIG_LOTTO',
    bestStrategyStatus: 'UNAVAILABLE',
    bestStrategyReason: 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE',
  },
)

const currentGameCode = computed(() => lotteryTypeDisplayLabel(props.selectedLotteryType))

const currentGameFullName = computed(() => {
  switch (props.selectedLotteryType) {
    case 'BIG_LOTTO':
      return 'Big Lotto 6/49'
    case 'POWER_LOTTO':
      return 'Power Lotto 6/38'
    case 'DAILY_539':
      return 'Daily Cash 5/39'
  }
})

const searchQuery = ref('')
const selectedGame = ref<GameFilter>('ALL')
const selectedLifecycle = ref<LifecycleFilter>('ALL')
const selectedExecutable = ref<ExecutableFilter>('')
const selectedEvidenceStatus = ref<EvidenceStatusFilter>('ALL')
const viewMode = ref<ViewMode>('table')
const selectedStrategyId = ref<string | null>(null)

const hasActiveFilters = computed(
  () =>
    searchQuery.value.trim().length > 0 ||
    selectedGame.value !== 'ALL' ||
    selectedLifecycle.value !== 'ALL' ||
    selectedExecutable.value !== '' ||
    selectedEvidenceStatus.value !== 'ALL',
)

const filteredItems = computed<StrategyCombinedItem[]>(() => {
  let list = props.items

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(
      (item) =>
        item.strategyId.toLowerCase().includes(q) ||
        item.displayName.toLowerCase().includes(q),
    )
  }

  if (selectedGame.value !== 'ALL') {
    list = list.filter((item) => item.gameLabels.includes(selectedGame.value))
  }

  if (selectedLifecycle.value !== 'ALL') {
    list = list.filter((item) => item.lifecycleStatus === selectedLifecycle.value)
  }

  if (selectedExecutable.value !== '') {
    const isExec = selectedExecutable.value === 'true'
    list = list.filter((item) => item.executable === isExec)
  }

  if (selectedEvidenceStatus.value !== 'ALL') {
    if (selectedEvidenceStatus.value === 'REGISTERED') {
      list = list.filter((item) => item.registrationStatus === 'CANONICAL_EVIDENCE_REGISTERED')
    } else if (selectedEvidenceStatus.value === 'MISSING') {
      list = list.filter((item) => item.registrationStatus !== 'CANONICAL_EVIDENCE_REGISTERED')
    }
  }

  return list
})

const activeQueryConditions = computed(() => {
  const conditions: string[] = []
  const query = searchQuery.value.trim()

  if (query) conditions.push(`Search: ${query}`)
  if (selectedGame.value !== 'ALL') conditions.push(`Game: ${selectedGame.value}`)
  if (selectedLifecycle.value !== 'ALL') conditions.push(`Lifecycle: ${selectedLifecycle.value}`)
  if (selectedExecutable.value !== '') {
    conditions.push(`Execution: ${selectedExecutable.value === 'true' ? 'Executable' : 'Metadata only'}`)
  }
  if (selectedEvidenceStatus.value !== 'ALL') {
    conditions.push(
      `Evidence: ${selectedEvidenceStatus.value === 'REGISTERED' ? 'Canonical Registered' : 'Evidence Missing'}`,
    )
  }

  return conditions
})

const selectedStrategy = computed(() =>
  filteredItems.value.find((item) => item.strategyId === selectedStrategyId.value),
)

watch(
  () => props.selectedLotteryType,
  () => {
    selectedStrategyId.value = null
  },
)

function openStrategyDetails(strategy: StrategyCombinedItem): void {
  selectedStrategyId.value = strategy.strategyId
}

function returnToResults(): void {
  selectedStrategyId.value = null
}

function resetFilters(): void {
  searchQuery.value = ''
  selectedGame.value = 'ALL'
  selectedLifecycle.value = 'ALL'
  selectedExecutable.value = ''
  selectedEvidenceStatus.value = 'ALL'
}
</script>

<template>
  <div class="strategy-overview-workspace">
    <!-- Filter Bar -->
    <FilterBar
      title="Strategy Catalog & Descriptors"
      :count="filteredItems.length"
      count-label="strategies"
    >
      <template #default>
        <!-- Search Input -->
        <div class="control-field control-field--grow">
          <label for="strategy-search" class="control-label">Search Strategy</label>
          <input
            id="strategy-search"
            v-model="searchQuery"
            type="search"
            maxlength="100"
            autocomplete="off"
            placeholder="Search by ID or name…"
            class="text-input"
          />
        </div>

        <!-- Game Selector -->
        <div class="control-field">
          <label for="game-filter" class="control-label">Game</label>
          <select id="game-filter" v-model="selectedGame" class="select-input">
            <option value="ALL">All Games</option>
            <option value="B649">B649 (Big Lotto)</option>
            <option value="P638">P638 (Power Lotto)</option>
            <option value="T539">T539 (Daily Cash)</option>
          </select>
        </div>

        <!-- Lifecycle Status Filter -->
        <div class="control-field">
          <label for="lifecycle-filter" class="control-label">Lifecycle</label>
          <select id="lifecycle-filter" v-model="selectedLifecycle" class="select-input">
            <option value="ALL">All Lifecycle States</option>
            <option value="IDEA">IDEA</option>
            <option value="OBSERVATION">OBSERVATION</option>
            <option value="ONLINE">ONLINE</option>
            <option value="REJECTED">REJECTED</option>
            <option value="RETIRED">RETIRED</option>
          </select>
        </div>

        <!-- Executable Filter -->
        <div class="control-field">
          <label for="executable-filter" class="control-label">Execution</label>
          <select id="executable-filter" v-model="selectedExecutable" class="select-input">
            <option value="">All Descriptors</option>
            <option value="true">Executable</option>
            <option value="false">Metadata only</option>
          </select>
        </div>

        <!-- Evidence Status Filter -->
        <div class="control-field">
          <label for="evidence-filter" class="control-label">Evidence</label>
          <select id="evidence-filter" v-model="selectedEvidenceStatus" class="select-input">
            <option value="ALL">All Evidence States</option>
            <option value="REGISTERED">Canonical Registered</option>
            <option value="MISSING">Evidence Missing</option>
          </select>
        </div>
      </template>

      <template #actions>
        <div class="overview-actions">
          <button
            v-if="hasActiveFilters"
            type="button"
            class="button button--quiet"
            @click="resetFilters"
          >
            Reset filters
          </button>
          <div class="view-switch" role="group" aria-label="View format">
            <button
              type="button"
              class="button button--sm"
              :class="{ 'button--primary': viewMode === 'table', 'button--quiet': viewMode !== 'table' }"
              :aria-pressed="viewMode === 'table'"
              @click="viewMode = 'table'"
            >
              Table
            </button>
            <button
              type="button"
              class="button button--sm"
              :class="{ 'button--primary': viewMode === 'cards', 'button--quiet': viewMode !== 'cards' }"
              :aria-pressed="viewMode === 'cards'"
              @click="viewMode = 'cards'"
            >
              Cards
            </button>
          </div>
        </div>
      </template>
    </FilterBar>

    <div
      class="query-context"
      role="status"
      aria-live="polite"
      aria-label="Current strategy query"
      data-testid="strategy-query-context"
    >
      <div>
        <strong>Catalog scope: {{ currentGameCode }}</strong>
        <span v-if="activeQueryConditions.length"> · {{ activeQueryConditions.join(' · ') }}</span>
        <span v-else> · All filters</span>
      </div>
      <span>{{ filteredItems.length }} of {{ items.length }} strategies match</span>
    </div>

    <!-- Best Strategy Overview Panel -->
    <section class="panel best-strategy-panel" aria-labelledby="best-strategy-overview-title">
      <div class="panel__heading">
        <div>
          <p class="step-label">Strategy Evidence · Boundary</p>
          <h3 id="best-strategy-overview-title">Registry-wide Best Strategy Evidence Boundary</h3>
        </div>
        <div class="scope-card" aria-label="Best strategy evidence status">
          <span>Registry-wide Best Strategy Scope</span>
          <strong>{{ bestStrategyStatus }}</strong>
          <small>Reason: {{ bestStrategyReason }}</small>
        </div>
      </div>

      <div class="best-strategy-content">
        <div class="best-strategy-alert" role="status">
          <span class="alert-icon" aria-hidden="true">🛡️</span>
          <div>
            <strong class="alert-headline">Best Strategy Evidence: {{ bestStrategyStatus }}</strong>
            <p class="alert-text">
              Registry-wide Best Strategy Evidence Boundary: Status {{ bestStrategyStatus }} (Reason: {{ bestStrategyReason }}). The upstream evidence registry publishes a single registry-wide boundary without game-specific or individual best-strategy records.
            </p>
          </div>
        </div>

        <div class="best-strategy-context">
          <span class="context-label">Selected Catalog Context:</span>
          <span class="game-tag">{{ currentGameCode }}</span>
          <span class="game-full-name">{{ currentGameFullName }}</span>
          <span class="context-desc">
            Catalog context only ({{ filteredItems.length }} candidate strategies). Best strategy evidence is registry-wide and not evaluated per game.
          </span>
        </div>

        <ul class="best-strategy-guards">
          <li><strong>Registry-wide Authority:</strong> Upstream best_strategy evidence is registry-wide; game selection provides catalog filtering context only and does not establish game-specific ranking evidence.</li>
          <li><strong>No Catalog Deduction:</strong> Strategies are not selected as "best" based on catalog registration order or metadata declaration.</li>
          <li><strong>No Lifecycle Inference:</strong> Descriptors marked <code>ONLINE</code> or <code>OBSERVATION</code> are not assumed to have empirical superiority without registered evidence.</li>
          <li><strong>No Replay Conflation:</strong> Descriptive historical replay rankings are not treated as canonical forward best-strategy evidence.</li>
        </ul>
      </div>
    </section>

    <!-- Query Summary & Evidence Availability Banner -->
    <div class="overview-meta-grid">
      <section class="panel summary-box" aria-labelledby="query-summary-title">
        <div class="panel__heading">
          <p class="step-label">Catalog Summary · {{ currentGameCode }}</p>
          <h3 id="query-summary-title">Descriptor Breakdown</h3>
        </div>
        <dl class="summary-counts">
          <div class="count-card">
            <dt>Matching Total</dt>
            <dd>{{ filteredItems.length }}</dd>
          </div>
          <div class="count-card">
            <dt>Executable</dt>
            <dd>{{ filteredItems.filter((i) => i.executable).length }}</dd>
          </div>
          <div class="count-card">
            <dt>Metadata Only</dt>
            <dd>{{ filteredItems.filter((i) => !i.executable).length }}</dd>
          </div>
        </dl>
        <ul class="lifecycle-chips" aria-label="Lifecycle breakdown">
          <li v-for="(count, status) in lifecycleCounts" :key="status" class="lifecycle-chip">
            <span class="chip-label">{{ status }}</span>
            <strong class="chip-count">{{ count }}</strong>
          </li>
        </ul>
      </section>

      <aside class="panel evidence-box" aria-labelledby="evidence-availability-title">
        <div class="panel__heading">
          <p class="step-label">Evidence Verification Safeguard</p>
          <h3 id="evidence-availability-title">Measured Evidence Unavailable</h3>
        </div>
        <ul class="evidence-points">
          <li>No canonical evaluation metrics are currently registered for catalog descriptors.</li>
          <li>D3 primary ranking metric is reserved and uncomputed across all strategies.</li>
          <li>No "best" strategy is inferred from metadata lifecycle order.</li>
          <li>Empirical eligibility requires verified out-of-sample evidence.</li>
        </ul>
        <div class="reason-badges" aria-label="Unavailability reason codes">
          <code v-for="reason in unavailableReasons" :key="reason" class="reason-code">
            {{ reason }}
          </code>
        </div>
      </aside>
    </div>

    <!-- Empty State: Filtered -->
    <EmptyState
      v-if="filteredItems.length === 0 && items.length > 0"
      title="No matching strategies"
      description="No strategies match the active search and descriptor filters."
    >
      <button type="button" class="button button--primary" @click="resetFilters">
        Reset filters
      </button>
    </EmptyState>

    <!-- Empty State: Catalog Empty -->
    <EmptyState
      v-else-if="items.length === 0"
      title="Strategy Catalog is empty"
      description="No strategies are registered in the canonical strategy catalog for this game."
    />

    <section
      v-else-if="selectedStrategy"
      class="panel strategy-detail"
      aria-labelledby="strategy-detail-title"
      data-testid="strategy-detail"
    >
      <header class="strategy-detail__header">
        <div>
          <p class="step-label">Strategy details · {{ currentGameCode }}</p>
          <h3 id="strategy-detail-title">{{ selectedStrategy.displayName }}</h3>
          <code class="strategy-id-code">{{ selectedStrategy.strategyId }}</code>
        </div>
        <button
          type="button"
          class="button button--quiet"
          data-testid="strategy-detail-return"
          @click="returnToResults"
        >
          Back to results
        </button>
      </header>

      <p class="strategy-detail__context">
        Returning preserves this catalog scope and query:
        {{ activeQueryConditions.length ? activeQueryConditions.join(' · ') : 'All filters' }}.
      </p>

      <div class="strategy-detail__grid">
        <section class="strategy-detail__section" aria-labelledby="strategy-descriptor-title">
          <h4 id="strategy-descriptor-title">Strategy descriptor</h4>
          <dl>
            <div><dt>Version</dt><dd>{{ selectedStrategy.version }}</dd></div>
            <div><dt>Supported games</dt><dd>{{ selectedStrategy.gameLabels.join(', ') }}</dd></div>
            <div><dt>Lifecycle</dt><dd>{{ selectedStrategy.lifecycleStatus }}</dd></div>
            <div><dt>Execution</dt><dd>{{ selectedStrategy.executable ? 'Executable' : 'Metadata only' }}</dd></div>
            <div><dt>Minimum history</dt><dd>{{ selectedStrategy.minimumHistory }} draws</dd></div>
          </dl>
        </section>

        <section class="strategy-detail__section" aria-labelledby="strategy-evidence-title">
          <h4 id="strategy-evidence-title">Evidence and availability</h4>
          <dl>
            <div><dt>Empirical eligibility</dt><dd>{{ selectedStrategy.empiricalEligibility }}</dd></div>
            <div><dt>Evidence status</dt><dd>{{ selectedStrategy.evidenceStatus }}</dd></div>
            <div><dt>Registration</dt><dd>{{ selectedStrategy.registrationStatus }}</dd></div>
            <div><dt>Definition</dt><dd>{{ selectedStrategy.definitionStatus }}</dd></div>
            <div><dt>Verification</dt><dd>{{ selectedStrategy.verificationStatus }}</dd></div>
            <div><dt>Adapter</dt><dd>{{ selectedStrategy.adapterAvailable ? 'Available' : 'Unavailable' }}</dd></div>
            <div>
              <dt>Unavailable reason</dt>
              <dd>{{ selectedStrategy.unavailableReasonCode ?? 'None' }}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section class="strategy-detail__section strategy-detail__sources" aria-labelledby="strategy-sources-title">
        <h4 id="strategy-sources-title">Provenance</h4>
        <ul v-if="selectedStrategy.provenance.length" class="provenance-list">
          <li v-for="source in selectedStrategy.provenance" :key="source"><code>{{ source }}</code></li>
        </ul>
        <p v-else class="text-muted">No provenance sources are recorded.</p>
      </section>
    </section>

    <!-- Main Content: Table View -->
    <template v-else-if="viewMode === 'table'">
      <DataTable
        caption="Canonical Strategy Catalog & Evidence Status"
        min-width="1200px"
      >
        <template #head>
          <tr>
            <th>Strategy</th>
            <th>Version</th>
            <th>Games</th>
            <th>Lifecycle</th>
            <th>Execution</th>
            <th>Min History</th>
            <th>Empirical Eligibility</th>
            <th>Evidence Status</th>
            <th>Verification</th>
            <th>Unavailable Reason</th>
            <th>Provenance</th>
          </tr>
        </template>

        <tr v-for="strategy in filteredItems" :key="strategy.strategyId" class="data-row">
          <td>
            <div class="strategy-identity">
              <strong class="strategy-display-name">{{ strategy.displayName }}</strong>
              <code class="strategy-id-code">{{ strategy.strategyId }}</code>
              <button
                type="button"
                class="button button--quiet button--sm strategy-details-action"
                :data-testid="`strategy-details-${strategy.strategyId}`"
                @click="openStrategyDetails(strategy)"
              >
                Details
              </button>
            </div>
          </td>
          <td>
            <span class="version-tag">{{ strategy.version }}</span>
          </td>
          <td>
            <div class="game-tags">
              <span v-for="game in strategy.gameLabels" :key="game" class="game-tag">
                {{ game }}
              </span>
            </div>
          </td>
          <td>
            <StatusBadge :status="strategy.lifecycleStatus" size="sm" />
          </td>
          <td>
            <StatusBadge
              :status="strategy.executable ? 'EXECUTABLE' : 'METADATA ONLY'"
              :variant="strategy.executable ? 'success' : 'neutral'"
              size="sm"
            />
          </td>
          <td class="font-mono">
            <span>{{ strategy.minimumHistory }} draws</span>
          </td>
          <td>
            <StatusBadge
              :status="strategy.empiricalEligibility"
              :variant="strategy.empiricalEligibility === 'EMPIRICAL ELIGIBLE' ? 'success' : 'neutral'"
              size="sm"
            />
          </td>
          <td>
            <StatusBadge
              :status="strategy.evidenceStatus"
              :variant="strategy.evidenceStatus === 'CANONICAL EVIDENCE REGISTERED' ? 'success' : 'neutral'"
              size="sm"
            />
          </td>
          <td>
            <StatusBadge
              :status="strategy.verificationStatus"
              :variant="strategy.verificationStatus === 'EVIDENCE_VERIFIED' ? 'success' : 'neutral'"
              size="sm"
            />
          </td>
          <td>
            <code v-if="strategy.unavailableReasonCode" class="reason-code-inline">
              {{ strategy.unavailableReasonCode }}
            </code>
            <span v-else class="text-muted">—</span>
          </td>
          <td>
            <details v-if="strategy.provenance.length" class="provenance-details">
              <summary>Sources ({{ strategy.provenance.length }})</summary>
              <ul class="provenance-list">
                <li v-for="source in strategy.provenance" :key="source">
                  <code>{{ source }}</code>
                </li>
              </ul>
            </details>
            <span v-else class="text-muted">—</span>
          </td>
        </tr>
      </DataTable>
    </template>

    <!-- Main Content: Card Grid View -->
    <template v-else-if="viewMode === 'cards'">
      <ul class="strategy-card-grid" aria-label="Strategy Cards">
        <li
          v-for="strategy in filteredItems"
          :key="strategy.strategyId"
          class="strategy-card"
        >
          <div class="strategy-card__header">
            <div class="card-badges">
              <StatusBadge :status="strategy.lifecycleStatus" size="sm" />
              <StatusBadge
                :status="strategy.executable ? 'EXECUTABLE' : 'METADATA ONLY'"
                :variant="strategy.executable ? 'success' : 'neutral'"
                size="sm"
              />
            </div>
            <span class="version-tag">{{ strategy.version }}</span>
          </div>

          <div class="strategy-card__body">
            <h4 class="card-title">{{ strategy.displayName }}</h4>
            <code class="strategy-id-code">{{ strategy.strategyId }}</code>
          </div>

          <dl class="strategy-card__details">
            <div>
              <dt>Games</dt>
              <dd>{{ strategy.gameLabels.join(', ') }}</dd>
            </div>
            <div>
              <dt>Min History</dt>
              <dd>{{ strategy.minimumHistory }} draws</dd>
            </div>
            <div>
              <dt>Eligibility</dt>
              <dd>{{ strategy.empiricalEligibility }}</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>{{ strategy.evidenceStatus }}</dd>
            </div>
            <div>
              <dt>Verification</dt>
              <dd>{{ strategy.verificationStatus }}</dd>
            </div>
            <div>
              <dt>Unavailable Reason</dt>
              <dd class="font-mono text-truncate">{{ strategy.unavailableReasonCode ?? 'None' }}</dd>
            </div>
          </dl>

          <p class="strategy-card__guard">
            <span class="guard-dot" aria-hidden="true">●</span>
            {{
              strategy.executable
                ? 'Descriptor marked executable; no unvalidated execution triggered.'
                : 'Descriptor exposes metadata only; no execution control available.'
            }}
          </p>

          <button
            type="button"
            class="button button--quiet button--sm strategy-details-action"
            :data-testid="`strategy-details-${strategy.strategyId}`"
            @click="openStrategyDetails(strategy)"
          >
            View strategy details
          </button>

          <details v-if="strategy.provenance.length" class="provenance-details">
            <summary>Provenance ({{ strategy.provenance.length }})</summary>
            <ul class="provenance-list">
              <li v-for="source in strategy.provenance" :key="source">
                <code>{{ source }}</code>
              </li>
            </ul>
          </details>
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.query-context {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 12px 0 20px;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: rgba(12, 17, 28, 0.55);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.query-context strong {
  color: var(--text-primary);
}

.query-context > span {
  flex-shrink: 0;
  color: var(--text-primary);
  font-weight: 700;
}

.strategy-detail {
  padding: 20px;
}

.strategy-detail__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.strategy-detail__header h3 {
  margin: 4px 0;
  color: var(--text-primary);
}

.strategy-detail__context {
  margin: 16px 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.strategy-detail__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.strategy-detail__section {
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: rgba(12, 17, 28, 0.5);
}

.strategy-detail__section h4 {
  margin: 0 0 12px;
  color: var(--text-primary);
  font-size: 13px;
}

.strategy-detail__section dl {
  display: grid;
  gap: 10px;
  margin: 0;
}

.strategy-detail__section dl > div {
  display: grid;
  grid-template-columns: minmax(130px, 0.8fr) minmax(0, 1.2fr);
  gap: 12px;
}

.strategy-detail__section dt {
  color: var(--text-tertiary);
  font-size: 11px;
}

.strategy-detail__section dd {
  margin: 0;
  overflow-wrap: anywhere;
  color: var(--text-secondary);
  font-size: 12px;
}

.strategy-detail__sources {
  margin-top: 16px;
}

.strategy-details-action {
  margin-top: 8px;
}

.strategy-overview-workspace {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.control-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 160px;
}

.control-field--grow {
  flex: 1;
  min-width: 220px;
}

.control-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.text-input,
.select-input {
  min-height: 40px;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-input);
  color: var(--text-primary);
  outline: none;
}

.overview-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.view-switch {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(13, 17, 27, 0.7);
  padding: 3px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.overview-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.summary-counts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin: 0 0 16px;
}

.count-card {
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: rgba(12, 17, 28, 0.7);
}

.count-card dt {
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.count-card dd {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.lifecycle-chips {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.lifecycle-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.04);
  font-size: 11px;
}

.chip-label {
  color: var(--text-secondary);
}

.chip-count {
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.evidence-points {
  margin: 0 0 14px;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 1.6;
}

.reason-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.reason-code {
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  font-size: 11px;
  font-family: var(--font-mono);
}

.strategy-identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.strategy-display-name {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
}

.strategy-id-code {
  color: var(--text-accent);
  font-size: 11px;
  font-family: var(--font-mono);
}

.version-tag {
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
  font: 700 10.5px/1 var(--font-mono);
}

.game-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.game-tag {
  padding: 3px 6px;
  border-radius: var(--radius-sm);
  background: rgba(56, 189, 248, 0.12);
  border: 1px solid rgba(56, 189, 248, 0.25);
  color: #38bdf8;
  font: 700 10px/1 var(--font-mono);
}

.provenance-details {
  font-size: 11px;
}

.provenance-details summary {
  cursor: pointer;
  color: var(--text-accent);
  user-select: none;
}

.provenance-list {
  list-style: none;
  padding: 4px 0 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.provenance-list code {
  color: var(--text-secondary);
  font-size: 10px;
  word-break: break-all;
}

/* Strategy Card Grid */
.strategy-card-grid {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.strategy-card {
  padding: 18px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  backdrop-filter: blur(16px);
  display: flex;
  flex-direction: column;
  gap: 14px;
  transition: all 0.2s ease;
}

.strategy-card:hover {
  border-color: var(--border-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.strategy-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card-badges {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.strategy-card__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.strategy-card__details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 0;
  padding: 10px;
  border-radius: var(--radius-md);
  background: rgba(12, 17, 28, 0.6);
  font-size: 11.5px;
}

.strategy-card__details dt {
  color: var(--text-secondary);
  font-weight: 600;
}

.strategy-card__details dd {
  margin: 0;
  color: var(--text-primary);
  font-weight: 700;
  text-align: right;
}

.strategy-card__guard {
  margin: 0;
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.4;
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.guard-dot {
  color: var(--text-accent);
  font-size: 8px;
  margin-top: 3px;
}

@media (max-width: 900px) {
  .overview-meta-grid {
    grid-template-columns: 1fr;
  }
}

.best-strategy-panel {
  padding: 20px;
  border: 1px solid rgba(234, 179, 8, 0.25);
  background: linear-gradient(135deg, rgba(35, 26, 12, 0.7) 0%, rgba(13, 17, 28, 0.7) 100%);
}

.best-strategy-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.best-strategy-alert {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.3);
}

.alert-icon {
  font-size: 18px;
  flex-shrink: 0;
  margin-top: 1px;
}

.alert-headline {
  display: block;
  font-size: 12.5px;
  font-weight: 700;
  color: #fde047;
  margin-bottom: 2px;
  letter-spacing: 0.03em;
}

.alert-text {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.45;
}

.best-strategy-guards {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.best-strategy-guards strong {
  color: var(--text-primary);
}

.best-strategy-guards code {
  color: var(--text-accent);
}

.reason-code-inline {
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.25);
  color: #fca5a5;
  font-size: 10px;
  font-family: var(--font-mono);
  display: inline-block;
}

.text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.best-strategy-context {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: rgba(12, 17, 28, 0.5);
  border: 1px solid var(--border-color);
  font-size: 11.5px;
  flex-wrap: wrap;
}

.context-label {
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-secondary);
  font-size: 10.5px;
}

.context-desc {
  color: var(--text-tertiary);
  font-size: 11px;
}

.game-full-name {
  color: var(--text-secondary);
  font-size: 11px;
}

@media (max-width: 720px) {
  .query-context,
  .strategy-detail__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .strategy-detail__grid {
    grid-template-columns: 1fr;
  }
}
</style>
