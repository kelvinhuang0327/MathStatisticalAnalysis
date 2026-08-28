<script setup lang="ts">
import { computed, ref } from 'vue'

import DataTable from '../../components/DataTable.vue'
import EmptyState from '../../components/EmptyState.vue'
import FilterBar from '../../components/FilterBar.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type {
  EvidenceStatusFilter,
  ExecutableFilter,
  GameFilter,
  LifecycleFilter,
  StrategyCombinedItem,
  ViewMode,
} from './types'

const props = defineProps<{
  items: StrategyCombinedItem[]
  totalCount: number
  executableCount: number
  metadataOnlyCount: number
  lifecycleCounts: Record<string, number>
  unavailableReasons: string[]
}>()

const searchQuery = ref('')
const selectedGame = ref<GameFilter>('ALL')
const selectedLifecycle = ref<LifecycleFilter>('ALL')
const selectedExecutable = ref<ExecutableFilter>('')
const selectedEvidenceStatus = ref<EvidenceStatusFilter>('ALL')
const viewMode = ref<ViewMode>('table')

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

    <!-- Query Summary & Evidence Availability Banner -->
    <div class="overview-meta-grid">
      <section class="panel summary-box" aria-labelledby="query-summary-title">
        <div class="panel__heading">
          <p class="step-label">Catalog Summary</p>
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
      description="No strategies are registered in the canonical strategy catalog."
    />

    <!-- Main Content: Table View -->
    <template v-else-if="viewMode === 'table'">
      <DataTable
        caption="Canonical Strategy Catalog & Evidence Status"
        min-width="1100px"
      >
        <template #head>
          <tr>
            <th>Strategy</th>
            <th>Version</th>
            <th>Games</th>
            <th>Lifecycle</th>
            <th>Execution</th>
            <th>Empirical Eligibility</th>
            <th>Evidence Status</th>
            <th>Verification</th>
            <th>Provenance</th>
          </tr>
        </template>

        <tr v-for="strategy in filteredItems" :key="strategy.strategyId" class="data-row">
          <td>
            <div class="strategy-identity">
              <strong class="strategy-display-name">{{ strategy.displayName }}</strong>
              <code class="strategy-id-code">{{ strategy.strategyId }}</code>
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
          </dl>

          <p class="strategy-card__guard">
            <span class="guard-dot" aria-hidden="true">●</span>
            {{
              strategy.executable
                ? 'Descriptor marked executable; no unvalidated execution triggered.'
                : 'Descriptor exposes metadata only; no execution control available.'
            }}
          </p>

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
</style>
