<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  B649_HISTORY_WINDOWS,
  B649_PREFIX_COUNTS,
  B649_REPRODUCTION_STATUSES,
  B649_SUCCESS_CRITERIA,
  B649RecordsRequestError,
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
  type B649HistoryWindow,
  type B649MultiTicketRecord,
  type B649MultiTicketRecordPage,
  type B649MultiTicketSummary,
  type B649PrefixCount,
  type B649ReproductionStatus,
  type B649SuccessCriterion,
} from '../../api/b649MultiTicketRecords'

type LoadState = 'loading' | 'ready' | 'error'
type QueryState = 'idle' | 'loading' | 'success' | 'empty' | 'unavailable' | 'error'

interface SubmittedSelection {
  prefixCount: B649PrefixCount
  window: B649HistoryWindow
  criterion: B649SuccessCriterion
  q?: string
  methodFamily?: string
  reproductionStatus?: B649ReproductionStatus
}

const PAGE_SIZE = 25

const summary = ref<B649MultiTicketSummary | null>(null)
const summaryState = ref<LoadState>('loading')
const summaryError = ref('')
const queryState = ref<QueryState>('idle')
const queryError = ref('')
const page = ref<B649MultiTicketRecordPage | null>(null)
const prefixCount = ref<B649PrefixCount | ''>('')
const windowKind = ref<B649HistoryWindow | ''>('')
const criterion = ref<B649SuccessCriterion | ''>('')
const search = ref('')
const methodFamily = ref('')
const reproductionStatus = ref<B649ReproductionStatus | ''>('')
const submittedSelection = ref<SubmittedSelection | null>(null)
let summaryController: AbortController | null = null
let recordsController: AbortController | null = null
let recordsGeneration = 0

const recordsAvailable = computed(() => summary.value?.records_available === true)
const canQuery = computed(
  () =>
    recordsAvailable.value &&
    prefixCount.value !== '' &&
    windowKind.value !== '' &&
    criterion.value !== '',
)
const displayedRange = computed(() => {
  if (!page.value || page.value.total === 0) return '0'
  const start = page.value.offset + 1
  const end = Math.min(page.value.offset + page.value.items.length, page.value.total)
  return `${start}–${end} / ${page.value.total}`
})
const hasPrevious = computed(() => (page.value?.offset ?? 0) > 0)
const hasNext = computed(
  () =>
    page.value !== null &&
    page.value.offset + page.value.items.length < page.value.total,
)

async function loadSummary(): Promise<void> {
  summaryController?.abort()
  summaryController = new AbortController()
  summaryState.value = 'loading'
  summaryError.value = ''
  try {
    const result = await fetchB649MultiTicketSummary(summaryController.signal)
    summary.value = result
    summaryState.value = 'ready'
    if (!result.records_available) {
      queryState.value = 'unavailable'
    } else if (queryState.value === 'unavailable' && page.value === null) {
      queryState.value = 'idle'
    }
  } catch (error) {
    if (isAbortError(error)) return
    summaryState.value = 'error'
    summaryError.value =
      error instanceof Error ? error.message : 'Research summary could not be loaded.'
  }
}

function currentSelection(): SubmittedSelection | null {
  if (
    prefixCount.value === '' ||
    windowKind.value === '' ||
    criterion.value === ''
  ) {
    return null
  }
  return {
    prefixCount: prefixCount.value,
    window: windowKind.value,
    criterion: criterion.value,
    q: search.value.trim() || undefined,
    methodFamily: methodFamily.value || undefined,
    reproductionStatus: reproductionStatus.value || undefined,
  }
}

async function submitQuery(): Promise<void> {
  const selection = currentSelection()
  if (selection === null || !recordsAvailable.value) return
  submittedSelection.value = selection
  await runQuery(selection, 0)
}

async function runQuery(
  selection: SubmittedSelection,
  offset: number,
): Promise<void> {
  recordsController?.abort()
  recordsController = new AbortController()
  const generation = ++recordsGeneration
  queryState.value = 'loading'
  queryError.value = ''
  try {
    const result = await fetchB649MultiTicketRecords(
      {
        ...selection,
        limit: PAGE_SIZE,
        offset,
      },
      recordsController.signal,
    )
    if (generation !== recordsGeneration) return
    page.value = result
    queryState.value = result.items.length === 0 ? 'empty' : 'success'
  } catch (error) {
    if (isAbortError(error) || generation !== recordsGeneration) return
    page.value = null
    if (
      error instanceof B649RecordsRequestError &&
      error.kind === 'UNAVAILABLE'
    ) {
      queryState.value = 'unavailable'
      queryError.value = error.message
      return
    }
    queryState.value = 'error'
    queryError.value =
      error instanceof Error ? error.message : 'Query could not be completed.'
  }
}

async function retryQuery(): Promise<void> {
  if (submittedSelection.value !== null) {
    await runQuery(submittedSelection.value, page.value?.offset ?? 0)
    return
  }
  await loadSummary()
}

async function previousPage(): Promise<void> {
  if (submittedSelection.value === null || page.value === null) return
  await runQuery(
    submittedSelection.value,
    Math.max(0, page.value.offset - PAGE_SIZE),
  )
}

async function nextPage(): Promise<void> {
  if (submittedSelection.value === null || page.value === null) return
  await runQuery(submittedSelection.value, page.value.offset + PAGE_SIZE)
}

function percentage(value: string | null): string {
  if (value === null) return '—'
  return `${(Number(value) * 100).toFixed(6)}%`
}

function signedPercentage(value: string | null): string {
  if (value === null) return '—'
  const percentageValue = Number(value) * 100
  const sign = percentageValue > 0 ? '+' : ''
  return `${sign}${percentageValue.toFixed(6)} pp`
}

function shortSha(value: string | null): string {
  return value === null ? '—' : `${value.slice(0, 12)}…`
}

function rankText(record: B649MultiTicketRecord): string {
  return record.rank === null ? record.unranked_reason ?? '—' : `#${record.rank}`
}

function officialRankText(record: B649MultiTicketRecord): string {
  return record.official_rank === null
    ? record.unranked_reason ?? '—'
    : `#${record.official_rank}`
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

onMounted(loadSummary)
onBeforeUnmount(() => {
  summaryController?.abort()
  recordsController?.abort()
  recordsGeneration += 1
})
</script>

<template>
  <section class="b649-records" aria-labelledby="b649-records-title">
    <header class="b649-records__heading">
      <div>
        <p class="eyebrow">B649 · checksum-pinned research</p>
        <h1 id="b649-records-title">B649 Multi-Ticket Historical Replay Data</h1>
        <p class="b649-records__intro">
          Read-only inspection of 221 formal strategy identities and completed aggregated backtest records. This page does not execute strategies, generate tickets, re-run backtests, or select top performers.
        </p>
      </div>
      <span class="readonly-badge">READ ONLY</span>
    </header>

    <div v-if="summaryState === 'loading'" class="records-state" role="status" aria-live="polite">
      Loading research summary…
    </div>
    <div v-else-if="summaryState === 'error'" class="records-state records-state--error" role="alert">
      <strong>Research summary could not be loaded</strong>
      <p>{{ summaryError }}</p>
      <button type="button" @click="loadSummary">Retry</button>
    </div>

    <template v-else-if="summary">
      <section class="research-progress" aria-labelledby="research-progress-title">
        <div class="research-progress__heading">
          <div>
            <p class="eyebrow">Formal disposition</p>
            <h2 id="research-progress-title">Full Strategy Research Progress</h2>
          </div>
          <code :title="summary.catalog_sha256">
            catalog {{ shortSha(summary.catalog_sha256) }}
          </code>
        </div>
        <dl class="research-progress__grid">
          <div>
            <dt>All Methods</dt>
            <dd>{{ summary.progress.total_strategy_count }}</dd>
          </div>
          <div>
            <dt>Reproduced & Backtested</dt>
            <dd>{{ summary.progress.backtested_count }}</dd>
          </div>
          <div>
            <dt>Formally Unexecutable</dt>
            <dd>{{ summary.progress.closed_count }}</dd>
          </div>
          <div>
            <dt>Duplicate Alias</dt>
            <dd>{{ summary.progress.duplicate_alias_count }}</dd>
          </div>
          <div>
            <dt>Pending Owner Decision</dt>
            <dd>{{ summary.progress.owner_decision_required_count }}</dd>
          </div>
          <div>
            <dt>Incomplete</dt>
            <dd>{{ summary.progress.uncompleted_count }}</dd>
          </div>
        </dl>
      </section>

      <aside class="research-disclaimer" role="note">
        Historical success rates, rankings, and random baseline differences are for descriptive research only and do not constitute future predictions, recommendations, deployment decisions, or prize guarantees.
      </aside>

      <form class="records-query" aria-labelledby="records-query-title" @submit.prevent="submitQuery">
        <div class="records-query__heading">
          <div>
            <p class="eyebrow">Explicit query</p>
            <h2 id="records-query-title">Query Parameters</h2>
          </div>
          <p>Ticket count, history window, and success criterion must be explicitly selected; no default winner is provided.</p>
        </div>
        <div class="records-query__grid">
          <label>
            <span>Ticket Count <strong aria-hidden="true">*</strong></span>
            <select v-model="prefixCount" name="prefix-count" required>
              <option value="" disabled>Select ticket count</option>
              <option v-for="value in B649_PREFIX_COUNTS" :key="value" :value="value">
                {{ value }} Tickets
              </option>
            </select>
          </label>
          <label>
            <span>History Window <strong aria-hidden="true">*</strong></span>
            <select v-model="windowKind" name="history-window" required>
              <option value="" disabled>Select window</option>
              <option v-for="value in B649_HISTORY_WINDOWS" :key="value" :value="value">
                {{ value }}
              </option>
            </select>
          </label>
          <label>
            <span>Success Criterion <strong aria-hidden="true">*</strong></span>
            <select v-model="criterion" name="success-criterion" required>
              <option value="" disabled>Select criterion</option>
              <option v-for="value in B649_SUCCESS_CRITERIA" :key="value" :value="value">
                {{ value }}
              </option>
            </select>
          </label>
          <label>
            <span>Strategy Search</span>
            <input
              v-model="search"
              name="strategy-search"
              type="search"
              maxlength="200"
              placeholder="Strategy ID, legacy method, or source"
            />
          </label>
          <label>
            <span>Method Family</span>
            <select v-model="methodFamily" name="method-family">
              <option value="">All families</option>
              <option v-for="family in summary.method_families" :key="family" :value="family">
                {{ family }}
              </option>
            </select>
          </label>
          <label>
            <span>Reproduction Status</span>
            <select v-model="reproductionStatus" name="reproduction-status">
              <option value="">All statuses</option>
              <option
                v-for="status in B649_REPRODUCTION_STATUSES"
                :key="status"
                :value="status"
              >
                {{ status }}
              </option>
            </select>
          </label>
        </div>
        <div class="records-query__actions">
          <p v-if="!recordsAvailable" role="status">
            Checksum-pinned aggregate projection is currently unavailable; query remains disabled.
          </p>
          <p v-else-if="!canQuery">Please select all three required query parameters.</p>
          <p v-else>Ready to query aggregate records with explicit parameters.</p>
          <button type="submit" :disabled="!canQuery || queryState === 'loading'">
            {{ queryState === 'loading' ? 'Querying…' : 'Query' }}
          </button>
        </div>
      </form>

      <div v-if="queryState === 'idle'" class="records-state" role="status">
        No query submitted yet. The page does not automatically select rankings, latest data, or top strategies.
      </div>
      <div v-else-if="queryState === 'loading'" class="records-state" role="status" aria-live="polite">
        Loading checksum-pinned aggregate records…
      </div>
      <div v-else-if="queryState === 'empty'" class="records-state" role="status">
        <strong>No matching strategies found</strong>
        <p>Adjust search text or filter criteria and click "Query" again.</p>
      </div>
      <div
        v-else-if="queryState === 'unavailable'"
        class="records-state records-state--warning"
        role="status"
      >
        <strong>Aggregate historical records are currently unavailable</strong>
        <p>{{ queryError || 'System could not locate a complete, checksum-pinned production projection.' }}</p>
        <button type="button" @click="retryQuery">Retry</button>
      </div>
      <div v-else-if="queryState === 'error'" class="records-state records-state--error" role="alert">
        <strong>Query Failed</strong>
        <p>{{ queryError }}</p>
        <button type="button" @click="retryQuery">Retry</button>
      </div>

      <section v-else-if="queryState === 'success' && page" class="records-results">
        <div class="records-results__heading">
          <div>
            <p class="eyebrow">Aggregate records only</p>
            <h2>Query Results</h2>
          </div>
          <p aria-live="polite">{{ displayedRange }}</p>
        </div>
        <div
          class="records-table-scroll"
          role="region"
          aria-label="B649 multi-ticket historical replay table, horizontally scrollable"
          tabindex="0"
        >
          <table class="records-table">
            <caption>
              Aggregated historical records; does not include draw-by-draw ordered-20, native tickets, or execution audit.
            </caption>
            <thead>
              <tr>
                <th scope="col">Strategy / Version</th>
                <th scope="col">Legacy Method ID</th>
                <th scope="col">Status</th>
                <th scope="col">Parameters</th>
                <th scope="col">Official Any-Prize Rank</th>
                <th scope="col">Official Win Rate</th>
                <th scope="col">Official Baseline</th>
                <th scope="col">Official Delta</th>
                <th scope="col">Secondary Rank / Reason</th>
                <th scope="col">Success / Valid Draws</th>
                <th scope="col">Secondary Rate</th>
                <th scope="col">Secondary Baseline</th>
                <th scope="col">Secondary Delta</th>
                <th scope="col">Coverage</th>
                <th scope="col">1st Prize</th>
                <th scope="col">2nd Prize</th>
                <th scope="col">3rd Prize</th>
                <th scope="col">4th Prize</th>
                <th scope="col">5th Prize</th>
                <th scope="col">6th Prize</th>
                <th scope="col">7th Prize</th>
                <th scope="col">General Prize</th>
                <th scope="col">No Prize</th>
                <th scope="col">report SHA-256</th>
                <th scope="col">catalog SHA-256</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in page.items" :key="record.strategy_id">
                <td>
                  <strong>{{ record.strategy_id }}</strong>
                  <small>{{ record.strategy_version }}</small>
                </td>
                <td>
                  <strong>{{ record.legacy_method_id }}</strong>
                  <small>{{ record.source_path }}</small>
                  <small>{{ record.method_family }}</small>
                </td>
                <td>
                  <span class="record-status">{{ record.reproduction_status }}</span>
                  <small v-if="record.duplicate_alias_target">
                    alias → {{ record.duplicate_alias_target }}
                  </small>
                </td>
                <td>
                  {{ record.prefix_count }} / {{ record.window }} / {{ record.criterion }}
                </td>
                <td>{{ officialRankText(record) }}</td>
                <td>{{ percentage(record.official_any_prize_rate) }}</td>
                <td>{{ percentage(record.official_random_baseline_probability) }}</td>
                <td>{{ signedPercentage(record.official_random_baseline_delta) }}</td>
                <td>{{ rankText(record) }}</td>
                <td>
                  <template v-if="record.success_count !== null">
                    {{ record.success_count }} / {{ record.effective_backtest_draw_count }}
                  </template>
                  <template v-else>—</template>
                </td>
                <td>{{ percentage(record.historical_success_rate) }}</td>
                <td>{{ percentage(record.random_baseline_success_rate) }}</td>
                <td>{{ signedPercentage(record.random_baseline_rate_difference) }}</td>
                <td>{{ percentage(record.coverage) }}</td>
                <td>{{ record.official_prize_counts?.first ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.second ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.third ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.fourth ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.fifth ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.sixth ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.seventh ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.general ?? '—' }}</td>
                <td>{{ record.no_prize_count ?? '—' }}</td>
                <td><code :title="record.report_sha256 ?? undefined">{{ shortSha(record.report_sha256) }}</code></td>
                <td><code :title="record.catalog_sha256">{{ shortSha(record.catalog_sha256) }}</code></td>
              </tr>
            </tbody>
          </table>
        </div>
        <nav class="records-pagination" aria-label="Query results pagination">
          <button type="button" :disabled="!hasPrevious" @click="previousPage">
            Previous
          </button>
          <span>{{ displayedRange }}</span>
          <button type="button" :disabled="!hasNext" @click="nextPage">
            Next
          </button>
        </nav>
      </section>
    </template>
  </section>
</template>
