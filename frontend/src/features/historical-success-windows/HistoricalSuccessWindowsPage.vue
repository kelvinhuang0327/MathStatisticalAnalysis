<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  getHistoricalSuccessStabilityMatrix,
  getHistoricalSuccessWindows,
  HISTORICAL_SUCCESS_CRITERIA,
  HISTORICAL_SUCCESS_PREFIX_COUNTS,
  HistoricalSuccessWindowsRequestError,
  listHistoricalRuns,
  listHistoricalSuccessWindows,
  type HistoricalRun,
  type HistoricalRunPage,
  type HistoricalSuccessCriterion,
  type HistoricalSuccessPrefixCount,
  type HistoricalSuccessStabilityMatrix,
  type HistoricalSuccessWindowPage,
  type HistoricalSuccessWindowResult,
} from '../../api/historicalSuccessWindows'

type RunsState = 'loading' | 'ready' | 'empty' | 'not-configured' | 'unavailable' | 'error'
type AnalysisState =
  | 'idle'
  | 'selected'
  | 'loading'
  | 'ready'
  | 'empty'
  | 'not-found'
  | 'invalid'
  | 'unavailable'
  | 'malformed'
  | 'error'
type DetailState = 'closed' | 'loading' | 'ready' | 'not-found' | 'invalid' | 'unavailable' | 'malformed' | 'error'
type MatrixState = 'idle' | 'selected' | 'loading' | 'ready' | 'partial' | 'error'
type MatrixSelection = HistoricalSuccessWindowResult
type MatrixOutcome = {
  selection: MatrixSelection
  matrix: HistoricalSuccessStabilityMatrix | null
  error: string
}
type MatrixCell = HistoricalSuccessStabilityMatrix['cells'][number]

const RUN_LIMIT = 10
const RESULT_LIMIT = 20

const runsState = ref<RunsState>('loading')
const runsPage = ref<HistoricalRunPage | null>(null)
const runsError = ref('')
const selectedImportIdentity = ref('')
const selectedRun = ref<HistoricalRun | null>(null)
const prefixCount = ref<HistoricalSuccessPrefixCount>(1)
const criterion = ref<HistoricalSuccessCriterion>('M3_PLUS')
const analysisState = ref<AnalysisState>('idle')
const resultPage = ref<HistoricalSuccessWindowPage | null>(null)
const analysisError = ref('')
const detailState = ref<DetailState>('closed')
const detail = ref<HistoricalSuccessWindowResult | null>(null)
const detailError = ref('')
const copiedIdentity = ref(false)
const matrixSelections = ref<MatrixSelection[]>([])
const matrixState = ref<MatrixState>('idle')
const matrixResults = ref<MatrixOutcome[]>([])

let mounted = false
let runsGeneration = 0
let analysisGeneration = 0
let detailGeneration = 0
let matrixGeneration = 0
let runsController: AbortController | undefined
let analysisController: AbortController | undefined
let detailController: AbortController | undefined
let matrixController: AbortController | undefined

const selectedRunMissingFromPage = computed(
  () =>
    selectedRun.value !== null &&
    !runsPage.value?.items.some(
      (run) => run.import_identity_sha256 === selectedRun.value?.import_identity_sha256,
    ),
)
const canRunPrevious = computed(() => (runsPage.value?.offset ?? 0) > 0)
const canRunNext = computed(() => {
  const page = runsPage.value
  return page !== null && page.offset + page.items.length < page.total_count
})
const canResultPrevious = computed(() => (resultPage.value?.offset ?? 0) > 0)
const canResultNext = computed(() => {
  const page = resultPage.value
  return page !== null && page.offset + page.items.length < page.total_count
})
const matrixSelectionLimitReached = computed(() => matrixSelections.value.length >= 4)

function errorMessage(error: unknown): string {
  return error instanceof HistoricalSuccessWindowsRequestError
    ? error.message
    : 'The historical research request failed.'
}

function analysisErrorState(error: unknown): AnalysisState {
  if (!(error instanceof HistoricalSuccessWindowsRequestError)) return 'error'
  if (error.kind === 'NOT_FOUND') return 'not-found'
  if (error.kind === 'INVALID_REQUEST') return 'invalid'
  if (error.kind === 'MALFORMED_RESPONSE') return 'malformed'
  return 'unavailable'
}

function detailErrorState(error: unknown): DetailState {
  const mapped = analysisErrorState(error)
  if (mapped === 'not-found' || mapped === 'invalid' || mapped === 'unavailable' || mapped === 'malformed') {
    return mapped
  }
  return 'error'
}

async function loadRuns(offset = 0): Promise<void> {
  const generation = ++runsGeneration
  runsController?.abort()
  const controller = new AbortController()
  runsController = controller
  runsState.value = 'loading'
  runsError.value = ''
  try {
    const page = await listHistoricalRuns({ limit: RUN_LIMIT, offset }, controller.signal)
    if (!mounted || generation !== runsGeneration || controller.signal.aborted) return
    runsPage.value = page
    runsState.value = page.total_count === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== runsGeneration || controller.signal.aborted) return
    runsPage.value = null
    runsError.value = errorMessage(error)
    if (
      error instanceof HistoricalSuccessWindowsRequestError &&
      error.kind === 'NOT_CONFIGURED'
    ) {
      runsState.value = 'not-configured'
    } else if (
      error instanceof HistoricalSuccessWindowsRequestError &&
      (error.kind === 'UNAVAILABLE' || error.kind === 'MALFORMED_RESPONSE')
    ) {
      runsState.value = 'unavailable'
    } else {
      runsState.value = 'error'
    }
  }
}

function clearAnalysis(): void {
  analysisGeneration += 1
  analysisController?.abort()
  detailGeneration += 1
  detailController?.abort()
  resultPage.value = null
  detail.value = null
  detailState.value = 'closed'
  analysisError.value = ''
  detailError.value = ''
  analysisState.value = selectedRun.value === null ? 'idle' : 'selected'
}

function matrixIdentity(item: MatrixSelection): string {
  return [
    item.strategy.strategy_id,
    item.strategy.strategy_version,
    String(item.strategy.replicate),
  ].join('\u0000')
}

function isMatrixSelected(item: MatrixSelection): boolean {
  const identity = matrixIdentity(item)
  return matrixSelections.value.some((selected) => matrixIdentity(selected) === identity)
}

function clearMatrix(clearSelections: boolean): void {
  matrixGeneration += 1
  matrixController?.abort()
  matrixResults.value = []
  if (clearSelections) matrixSelections.value = []
  matrixState.value =
    !clearSelections && matrixSelections.value.length > 0 ? 'selected' : 'idle'
}

function toggleMatrixSelection(item: MatrixSelection, event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  const identity = matrixIdentity(item)
  if (checked) {
    if (
      matrixSelections.value.length >= 4 ||
      matrixSelections.value.some((selected) => matrixIdentity(selected) === identity)
    ) {
      ;(event.target as HTMLInputElement).checked = isMatrixSelected(item)
      return
    }
    matrixSelections.value = [...matrixSelections.value, item]
  } else {
    matrixSelections.value = matrixSelections.value.filter(
      (selected) => matrixIdentity(selected) !== identity,
    )
  }
  clearMatrix(false)
}

function chooseRun(): void {
  const selected = runsPage.value?.items.find(
    (run) => run.import_identity_sha256 === selectedImportIdentity.value,
  )
  if (selected !== undefined) selectedRun.value = selected
  if (selectedImportIdentity.value === '') selectedRun.value = null
  copiedIdentity.value = false
  clearAnalysis()
  clearMatrix(true)
}

function controlsChanged(): void {
  clearAnalysis()
}

async function compareSelectedMatrices(): Promise<void> {
  const run = selectedRun.value
  const selections = [...matrixSelections.value]
  if (run === null || selections.length < 1 || selections.length > 4) return
  const generation = ++matrixGeneration
  matrixController?.abort()
  const controller = new AbortController()
  matrixController = controller
  matrixResults.value = []
  matrixState.value = 'loading'
  const outcomes = await Promise.all(
    selections.map(async (selection): Promise<MatrixOutcome> => {
      try {
        const matrix = await getHistoricalSuccessStabilityMatrix(
          {
            import_identity_sha256: run.import_identity_sha256,
            strategy_id: selection.strategy.strategy_id,
            strategy_version: selection.strategy.strategy_version,
            replicate: selection.strategy.replicate,
          },
          controller.signal,
        )
        return { selection, matrix, error: '' }
      } catch (error: unknown) {
        return { selection, matrix: null, error: errorMessage(error) }
      }
    }),
  )
  if (!mounted || generation !== matrixGeneration || controller.signal.aborted) return
  matrixResults.value = outcomes
  const successes = outcomes.filter((outcome) => outcome.matrix !== null).length
  matrixState.value =
    successes === outcomes.length ? 'ready' : successes > 0 ? 'partial' : 'error'
}

async function loadResults(offset: number): Promise<void> {
  const run = selectedRun.value
  if (run === null) return
  const selectedPrefix = prefixCount.value
  const selectedCriterion = criterion.value
  const generation = ++analysisGeneration
  analysisController?.abort()
  detailGeneration += 1
  detailController?.abort()
  detail.value = null
  detailState.value = 'closed'
  const controller = new AbortController()
  analysisController = controller
  resultPage.value = null
  analysisState.value = 'loading'
  analysisError.value = ''
  try {
    const page = await listHistoricalSuccessWindows(
      {
        import_identity_sha256: run.import_identity_sha256,
        prefix_count: selectedPrefix,
        criterion: selectedCriterion,
        limit: RESULT_LIMIT,
        offset,
      },
      controller.signal,
    )
    if (!mounted || generation !== analysisGeneration || controller.signal.aborted) return
    resultPage.value = page
    analysisState.value = page.total_count === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== analysisGeneration || controller.signal.aborted) return
    analysisError.value = errorMessage(error)
    analysisState.value = analysisErrorState(error)
  }
}

async function inspectStrategy(item: HistoricalSuccessWindowResult): Promise<void> {
  const run = selectedRun.value
  if (run === null) return
  const generation = ++detailGeneration
  detailController?.abort()
  const controller = new AbortController()
  detailController = controller
  detail.value = null
  detailState.value = 'loading'
  detailError.value = ''
  try {
    const response = await getHistoricalSuccessWindows(
      {
        import_identity_sha256: run.import_identity_sha256,
        strategy_id: item.strategy.strategy_id,
        strategy_version: item.strategy.strategy_version,
        replicate: item.strategy.replicate,
        prefix_count: prefixCount.value,
        criterion: criterion.value,
      },
      controller.signal,
    )
    if (!mounted || generation !== detailGeneration || controller.signal.aborted) return
    detail.value = response
    detailState.value = 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== detailGeneration || controller.signal.aborted) return
    detailError.value = errorMessage(error)
    detailState.value = detailErrorState(error)
  }
}

async function copyImportIdentity(): Promise<void> {
  const run = selectedRun.value
  if (run === null || navigator.clipboard === undefined) return
  await navigator.clipboard.writeText(run.import_identity_sha256)
  copiedIdentity.value = true
}

function exactRate(item: HistoricalSuccessWindowResult['windows'][number]): string {
  return item.success_rate.available
    ? `${item.success_rate.numerator} / ${item.success_rate.denominator}`
    : 'Unavailable (0 / 0)'
}

function targetLabel(target: HistoricalSuccessWindowResult['windows'][number]['first_target']): string {
  return `${target.draw_date} · #${target.draw_number}`
}

function matrixCell(
  matrix: HistoricalSuccessStabilityMatrix,
  criterionIdentity: HistoricalSuccessCriterion,
  prefix: HistoricalSuccessPrefixCount,
): MatrixCell {
  const criterionIndex = HISTORICAL_SUCCESS_CRITERIA.indexOf(criterionIdentity)
  const prefixIndex = HISTORICAL_SUCCESS_PREFIX_COUNTS.indexOf(prefix)
  return matrix.cells[criterionIndex * HISTORICAL_SUCCESS_PREFIX_COUNTS.length + prefixIndex]!
}

function matrixRate(
  rate: MatrixCell['windows'][number]['success_rate'],
): string {
  return rate.available
    ? `${rate.numerator} / ${rate.denominator}`
    : 'Unavailable (0 / 0)'
}

function matrixDelta(
  comparison: MatrixCell['comparisons'][number],
): string {
  return comparison.delta.available
    ? `${comparison.delta.numerator} / ${comparison.delta.denominator}`
    : 'Unavailable (0 / 0)'
}

onMounted(() => {
  mounted = true
  void loadRuns()
})
onBeforeUnmount(() => {
  mounted = false
  runsGeneration += 1
  analysisGeneration += 1
  detailGeneration += 1
  matrixGeneration += 1
  runsController?.abort()
  analysisController?.abort()
  detailController?.abort()
  matrixController?.abort()
})
</script>

<template>
  <section class="historical-workspace" aria-labelledby="historical-success-title">
    <header class="historical-heading">
      <div>
        <p class="eyebrow">Persisted evidence · explicit source selection</p>
        <h1 id="historical-success-title">Historical Success Windows</h1>
        <p class="historical-intro">
          Inspect descriptive results from one completed Historical Results import. This workspace
          does not rank, promote, predict, or choose a strategy.
        </p>
      </div>
      <div class="research-guard" aria-label="Research interpretation">
        <span>Interpretation</span>
        <strong>Reference only</strong>
        <small>Exact persisted evidence</small>
      </div>
    </header>

    <section class="research-panel" aria-labelledby="source-selection-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">1 · Source</p>
          <h2 id="source-selection-title">Choose one completed import</h2>
        </div>
        <div v-if="runsPage" class="panel-heading__actions">
          <div class="page-count">
            {{ runsPage.offset + 1 }}–{{ Math.min(runsPage.offset + runsPage.items.length, runsPage.total_count) }}
            of {{ runsPage.total_count }}
          </div>
          <button class="button button--quiet refresh-runs" type="button" @click="loadRuns(runsPage.offset)">
            Refresh runs
          </button>
        </div>
      </div>

      <p v-if="runsState === 'loading'" class="research-state">Loading persisted run metadata…</p>
      <div v-else-if="runsState === 'not-configured'" class="research-state research-state--notice">
        <strong>Historical database configuration required.</strong>
        <span>Set <code>LOTTOLAB_HISTORICAL_RESULTS_DB</code> to one existing database and restart the local runtime.</span>
        <button class="button button--quiet" type="button" @click="loadRuns()">Retry</button>
      </div>
      <div v-else-if="runsState === 'empty'" class="research-state">
        <strong>No completed Historical Results runs are available.</strong>
        <button class="button button--quiet" type="button" @click="loadRuns()">Reload</button>
      </div>
      <div v-else-if="runsState === 'unavailable' || runsState === 'error'" class="research-state research-state--error">
        <strong>{{ runsError }}</strong>
        <button class="button button--quiet" type="button" @click="loadRuns()">Retry</button>
      </div>

      <template v-if="runsState === 'ready' && runsPage">
        <label class="source-selector">
          <span>Completed run — no run is selected automatically</span>
          <select v-model="selectedImportIdentity" name="historical-run" @change="chooseRun">
            <option value="">Select an exact persisted run</option>
            <option
              v-if="selectedRunMissingFromPage && selectedRun"
              :value="selectedRun.import_identity_sha256"
            >
              {{ selectedRun.dataset_identity }} · {{ selectedRun.completed_at }}
            </option>
            <option
              v-for="run in runsPage.items"
              :key="run.import_identity_sha256"
              :value="run.import_identity_sha256"
            >
              {{ run.dataset_identity }} · {{ run.lottery_type }} · {{ run.completed_at }}
            </option>
          </select>
        </label>

        <nav class="research-pagination" aria-label="Historical run pages">
          <button
            class="button button--quiet"
            type="button"
            :disabled="!canRunPrevious"
            @click="loadRuns(Math.max(0, (runsPage?.offset ?? 0) - RUN_LIMIT))"
          >
            Previous
          </button>
          <button
            class="button button--quiet"
            type="button"
            :disabled="!canRunNext"
            @click="loadRuns((runsPage?.offset ?? 0) + RUN_LIMIT)"
          >
            Next
          </button>
        </nav>
      </template>

      <dl v-if="selectedRun" class="source-facts">
        <div><dt>Dataset</dt><dd>{{ selectedRun.dataset_identity }}</dd></div>
        <div><dt>Lottery</dt><dd>{{ selectedRun.lottery_type }}</dd></div>
        <div><dt>Completed</dt><dd>{{ selectedRun.completed_at }}</dd></div>
        <div><dt>Source repository</dt><dd>{{ selectedRun.source_repository }}</dd></div>
        <div><dt>Source commit</dt><dd><code>{{ selectedRun.source_commit_oid }}</code></dd></div>
        <div class="source-facts__identity">
          <dt>Exact import SHA-256</dt>
          <dd>
            <code>{{ selectedRun.import_identity_sha256 }}</code>
            <button class="copy-button" type="button" @click="copyImportIdentity">
              {{ copiedIdentity ? 'Copied' : 'Copy' }}
            </button>
          </dd>
        </div>
      </dl>
    </section>

    <section class="research-panel" aria-labelledby="analysis-controls-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">2 · Evaluation identity</p>
          <h2 id="analysis-controls-title">Choose prefix and criterion</h2>
        </div>
        <span class="explicit-action-note">Analyze is always explicit</span>
      </div>
      <form class="analysis-controls" @submit.prevent="loadResults(0)">
        <label>
          <span>Prefix count</span>
          <select v-model.number="prefixCount" name="prefix-count" @change="controlsChanged">
            <option v-for="value in HISTORICAL_SUCCESS_PREFIX_COUNTS" :key="value" :value="value">
              {{ value }}
            </option>
          </select>
        </label>
        <label>
          <span>Success criterion</span>
          <select v-model="criterion" name="criterion" @change="controlsChanged">
            <option v-for="value in HISTORICAL_SUCCESS_CRITERIA" :key="value" :value="value">
              {{ value }}
            </option>
          </select>
        </label>
        <button
          class="button button--primary"
          type="submit"
          :disabled="selectedRun === null || analysisState === 'loading'"
        >
          Analyze selected run
        </button>
      </form>
      <p v-if="selectedRun === null" class="research-state">Select a run before analysis.</p>
      <p v-else-if="analysisState === 'selected'" class="research-state">
        Run selected. No analysis request has been made yet.
      </p>
    </section>

    <section class="research-results" aria-labelledby="historical-results-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">3 · Descriptive windows</p>
          <h2 id="historical-results-title">Exact strategy identities</h2>
        </div>
        <div v-if="resultPage" class="page-count">{{ resultPage.total_count }} identities</div>
      </div>

      <p v-if="analysisState === 'idle' || analysisState === 'selected'" class="research-state">
        Results remain empty until Analyze is activated.
      </p>
      <p v-else-if="analysisState === 'loading'" class="research-state">Loading exact persisted windows…</p>
      <div v-else-if="analysisState === 'empty'" class="research-state">
        <strong>This exact import contains zero strategy identities.</strong>
      </div>
      <div
        v-else-if="['not-found', 'invalid', 'unavailable', 'malformed', 'error'].includes(analysisState)"
        class="research-state research-state--error"
      >
        <strong>{{ analysisError }}</strong>
        <button class="button button--quiet" type="button" @click="loadResults(resultPage?.offset ?? 0)">Retry</button>
      </div>

      <ol v-if="analysisState === 'ready' && resultPage" class="strategy-window-list">
        <li v-for="item in resultPage.items" :key="`${item.strategy.strategy_id}:${item.strategy.strategy_version}:${item.strategy.replicate}`" class="strategy-window-card">
          <header class="strategy-window-card__header">
            <div>
              <span class="identity-kind">{{ item.strategy.identity_kind }}</span>
              <h3>{{ item.strategy.strategy_id }}</h3>
              <code>{{ item.strategy.strategy_version }} · replicate {{ item.strategy.replicate }}</code>
            </div>
            <div class="strategy-window-card__actions">
              <label class="matrix-selector">
                <input
                  class="matrix-select"
                  type="checkbox"
                  :checked="isMatrixSelected(item)"
                  :disabled="!isMatrixSelected(item) && matrixSelectionLimitReached"
                  :aria-label="`Select ${item.strategy.strategy_id} ${item.strategy.strategy_version} replicate ${item.strategy.replicate} for stability matrix comparison`"
                  @change="toggleMatrixSelection(item, $event)"
                >
                Select matrix
              </label>
              <button class="button button--quiet inspect-button" type="button" @click="inspectStrategy(item)">
                Inspect exact identity
              </button>
            </div>
          </header>

          <dl class="identity-facts">
            <div><dt>Effective ID</dt><dd>{{ item.strategy.effective_strategy_id }}</dd></div>
            <div><dt>Governance</dt><dd>{{ item.strategy.governance_status }}</dd></div>
            <div><dt>Alias target</dt><dd>{{ item.strategy.alias_of_strategy_id ?? 'None' }}</dd></div>
            <div><dt>Equivalence group</dt><dd>{{ item.strategy.equivalence_group ?? 'None' }}</dd></div>
            <div><dt>Source observations</dt><dd>{{ item.source_observation_count }}</dd></div>
            <div><dt>Observation status</dt><dd>{{ item.source_observation_count === 0 ? 'ZERO OBSERVATIONS' : item.status }}</dd></div>
          </dl>

          <p v-if="item.windows.length === 0" class="zero-observation">
            This exact identity is retained with zero observations; no window is fabricated.
          </p>
          <div v-else class="window-grid">
            <article v-for="window in item.windows" :key="window.window_kind" class="window-card">
              <header>
                <div><span>{{ window.window_kind }}</span><strong>{{ window.window_role }}</strong></div>
                <code>{{ window.requested_draw_count ?? 'all' }} draws</code>
              </header>
              <p class="exact-rate">{{ exactRate(window) }}</p>
              <dl>
                <div><dt>Evaluation</dt><dd>{{ window.evaluation_status }}</dd></div>
                <div><dt>Evidence</dt><dd>{{ window.evidence_status }}</dd></div>
                <div><dt>Source</dt><dd>{{ window.source_draw_count }}</dd></div>
                <div><dt>Eligible</dt><dd>{{ window.eligible_draw_count }}</dd></div>
                <div><dt>Excluded</dt><dd>{{ window.excluded_draw_count }}</dd></div>
                <div><dt>Success</dt><dd>{{ window.success_count }}</dd></div>
                <div><dt>Failure</dt><dd>{{ window.failure_count }}</dd></div>
                <div><dt>Available</dt><dd>{{ window.success_rate.available ? 'YES' : 'NO' }}</dd></div>
              </dl>
              <footer>
                <span>First target · {{ targetLabel(window.first_target) }}</span>
                <span>Last target · {{ targetLabel(window.last_target) }}</span>
              </footer>
            </article>
          </div>
        </li>
      </ol>

      <nav v-if="resultPage && analysisState === 'ready'" class="research-pagination" aria-label="Historical Success Window pages">
        <button class="button button--quiet" type="button" :disabled="!canResultPrevious" @click="loadResults(Math.max(0, resultPage.offset - RESULT_LIMIT))">Previous</button>
        <span>Offset {{ resultPage.offset }} · limit {{ resultPage.limit }}</span>
        <button class="button button--quiet" type="button" :disabled="!canResultNext" @click="loadResults(resultPage.offset + RESULT_LIMIT)">Next</button>
      </nav>
    </section>

    <section class="research-results matrix-comparison" aria-labelledby="matrix-comparison-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">4 · Manual stability comparison</p>
          <h2 id="matrix-comparison-title">Exact strategy stability matrices</h2>
        </div>
        <button
          class="button button--primary matrix-compare"
          type="button"
          :disabled="selectedRun === null || matrixSelections.length === 0"
          @click="compareSelectedMatrices"
        >
          Compare selected stability matrices
        </button>
      </div>

      <p v-if="selectedRun === null" class="research-state">
        Select a run before choosing stability matrices.
      </p>
      <p v-else-if="matrixSelections.length === 0" class="research-state">
        Select one to four exact strategy identities. No matrix request runs on selection.
      </p>
      <p v-else-if="matrixState === 'selected'" class="research-state">
        {{ matrixSelections.length }} exact {{ matrixSelections.length === 1 ? 'identity' : 'identities' }} selected in manual order.
      </p>
      <p v-if="matrixSelectionLimitReached" class="research-state research-state--notice selection-limit">
        Selection limit reached: four exact identities.
      </p>
      <p v-if="matrixState === 'loading'" class="research-state">
        Loading {{ matrixSelections.length }} exact stability {{ matrixSelections.length === 1 ? 'matrix' : 'matrices' }}…
      </p>
      <div v-if="matrixState === 'partial'" class="research-state research-state--notice">
        <strong>Some exact matrices are unavailable; successful results remain visible.</strong>
        <button class="button button--quiet matrix-retry" type="button" @click="compareSelectedMatrices">Retry all</button>
      </div>
      <div v-if="matrixState === 'error'" class="research-state research-state--error">
        <strong>All selected matrix requests failed with sanitized errors.</strong>
        <button class="button button--quiet matrix-retry" type="button" @click="compareSelectedMatrices">Retry all</button>
      </div>

      <ol v-if="matrixResults.length > 0" class="matrix-result-list">
        <li
          v-for="outcome in matrixResults"
          :key="matrixIdentity(outcome.selection)"
          class="matrix-result-card"
        >
          <header>
            <div>
              <span class="identity-kind">{{ outcome.selection.strategy.identity_kind }}</span>
              <h3>{{ outcome.selection.strategy.strategy_id }}</h3>
              <code>
                {{ outcome.selection.strategy.strategy_version }} · replicate
                {{ outcome.selection.strategy.replicate }}
              </code>
            </div>
          </header>
          <div v-if="outcome.matrix">
            <dl class="identity-facts matrix-identity-facts">
              <div><dt>Effective ID</dt><dd>{{ outcome.matrix.strategy.effective_strategy_id }}</dd></div>
              <div><dt>Identity kind</dt><dd>{{ outcome.matrix.strategy.identity_kind }}</dd></div>
              <div><dt>Governance</dt><dd>{{ outcome.matrix.strategy.governance_status }}</dd></div>
              <div><dt>Alias target</dt><dd>{{ outcome.matrix.strategy.alias_of_strategy_id ?? 'None' }}</dd></div>
              <div><dt>Equivalence group</dt><dd>{{ outcome.matrix.strategy.equivalence_group ?? 'None' }}</dd></div>
              <div><dt>Source observations</dt><dd>{{ outcome.matrix.source_observation_count }}</dd></div>
            </dl>
            <p v-if="outcome.matrix.source_observation_count === 0" class="zero-observation">
              Zero-observation matrix: all 64 canonical cells remain visible without fabricated rates.
            </p>
            <div class="matrix-table-scroll">
              <table class="stability-matrix">
                <caption>
                  Exact descriptive rates and signed arithmetic deltas for
                  {{ outcome.matrix.strategy.strategy_id }}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Criterion</th>
                    <th v-for="prefix in HISTORICAL_SUCCESS_PREFIX_COUNTS" :key="prefix" scope="col">
                      Prefix {{ prefix }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="criterionIdentity in HISTORICAL_SUCCESS_CRITERIA" :key="criterionIdentity">
                    <th scope="row">{{ criterionIdentity }}</th>
                    <td v-for="prefix in HISTORICAL_SUCCESS_PREFIX_COUNTS" :key="prefix">
                      <template v-if="matrixCell(outcome.matrix, criterionIdentity, prefix).windows.length === 0">
                        <span class="matrix-unavailable">NO_OBSERVATIONS · rates unavailable</span>
                      </template>
                      <details v-else class="matrix-cell-detail">
                        <summary>Exact values</summary>
                        <dl>
                          <div
                            v-for="window in matrixCell(outcome.matrix, criterionIdentity, prefix).windows"
                            :key="window.window_kind"
                          >
                            <dt>{{ window.window_kind }}</dt>
                            <dd>{{ matrixRate(window.success_rate) }}</dd>
                          </div>
                          <div
                            v-for="comparison in matrixCell(outcome.matrix, criterionIdentity, prefix).comparisons"
                            :key="comparison.comparison_kind"
                          >
                            <dt>{{ comparison.comparison_kind }}</dt>
                            <dd>
                              {{ matrixDelta(comparison) }} · {{ comparison.relation }}
                            </dd>
                          </div>
                        </dl>
                      </details>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="research-state research-state--error matrix-item-error">
            <strong>{{ outcome.error }}</strong>
          </div>
        </li>
      </ol>
    </section>

    <aside v-if="detailState !== 'closed'" class="detail-panel" aria-labelledby="exact-detail-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">Exact endpoint response</p>
          <h2 id="exact-detail-title">Strategy inspection</h2>
        </div>
        <button class="button button--quiet" type="button" @click="detailState = 'closed'; detail = null">Close</button>
      </div>
      <p v-if="detailState === 'loading'" class="research-state">Loading exact strategy identity…</p>
      <div v-else-if="detailState === 'ready' && detail" class="detail-content">
        <h3>{{ detail.strategy.strategy_id }}</h3>
        <p><code>{{ detail.strategy.strategy_version }} · replicate {{ detail.strategy.replicate }}</code></p>
        <p>{{ detail.status }} · {{ detail.source_observation_count }} source observations</p>
        <ol>
          <li v-for="window in detail.windows" :key="window.window_kind">
            <strong>{{ window.window_kind }} / {{ window.window_role }}</strong>
            <span>{{ exactRate(window) }}</span>
          </li>
        </ol>
      </div>
      <div v-else class="research-state research-state--error">
        <strong>{{ detailError }}</strong>
      </div>
    </aside>
  </section>
</template>

<style scoped>
.historical-workspace { padding: 64px 0 92px; }
.historical-heading { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 48px; align-items: end; margin-bottom: 36px; }
.historical-intro { max-width: 760px; margin-bottom: 0; color: var(--muted); font-size: 16px; line-height: 1.7; }
.research-guard { display: grid; min-width: 190px; padding: 18px; border: 1px solid rgb(242 197 114 / 34%); border-radius: 18px; background: rgb(42 34 19 / 42%); }
.research-guard span, .research-guard small, .step-label, .page-count, .explicit-action-note { color: var(--muted); font: 500 10px/1.3 'SFMono-Regular', Consolas, monospace; letter-spacing: .08em; text-transform: uppercase; }
.research-guard strong { margin: 13px 0 8px; color: var(--amber); font: 600 16px/1.2 'SFMono-Regular', Consolas, monospace; }
.research-panel, .research-results, .detail-panel { margin-bottom: 20px; padding: 26px; border: 1px solid var(--line); border-radius: 22px; background: linear-gradient(145deg, rgb(18 35 31 / 94%), rgb(10 23 20 / 96%)); box-shadow: 0 22px 60px rgb(0 0 0 / 16%); }
.panel-heading { display: flex; gap: 18px; align-items: center; justify-content: space-between; margin-bottom: 22px; }
.panel-heading__actions { display: flex; gap: 12px; align-items: center; }
.panel-heading h2 { margin-bottom: 0; color: var(--ink); font-size: 22px; letter-spacing: -.025em; }
.step-label { margin-bottom: 9px; color: var(--mint); }
.source-selector, .analysis-controls label { display: grid; gap: 8px; color: var(--muted); font-size: 11px; letter-spacing: .05em; text-transform: uppercase; }
.source-selector select, .analysis-controls select { width: 100%; min-height: 46px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 11px; background: #081512; color: var(--ink); }
.research-pagination { display: flex; gap: 10px; align-items: center; justify-content: flex-end; margin-top: 16px; color: var(--muted); font-size: 11px; }
.source-facts, .identity-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; overflow: hidden; margin: 22px 0 0; border: 1px solid var(--line); border-radius: 14px; background: var(--line); }
.source-facts div, .identity-facts div { min-width: 0; padding: 14px; background: var(--surface); }
.source-facts dt, .source-facts dd, .identity-facts dt, .identity-facts dd { margin: 0; }
.source-facts dt, .identity-facts dt { color: var(--muted); font-size: 9px; letter-spacing: .08em; text-transform: uppercase; }
.source-facts dd, .identity-facts dd { margin-top: 8px; color: var(--ink); font-size: 12px; overflow-wrap: anywhere; }
.source-facts__identity { grid-column: 1 / -1; }
.source-facts__identity dd { display: flex; gap: 12px; align-items: center; justify-content: space-between; }
.copy-button { padding: 6px 9px; border: 1px solid var(--line); border-radius: 8px; background: transparent; color: var(--mint); cursor: pointer; }
.analysis-controls { display: grid; grid-template-columns: minmax(130px, .5fr) minmax(240px, 1fr) auto; gap: 14px; align-items: end; }
.research-state { display: flex; gap: 14px; align-items: center; justify-content: space-between; margin: 0; padding: 20px; border: 1px solid var(--line); border-radius: 14px; background: rgb(6 17 14 / 58%); color: var(--muted); line-height: 1.5; }
.research-state--notice { border-color: rgb(242 197 114 / 36%); color: var(--amber); }
.research-state--error { border-color: rgb(255 154 141 / 42%); color: var(--danger); }
.strategy-window-list { display: grid; gap: 18px; margin: 0; padding: 0; list-style: none; }
.strategy-window-card { padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: rgb(7 18 15 / 62%); }
.strategy-window-card__header, .window-card header, .window-card footer { display: flex; gap: 14px; align-items: center; justify-content: space-between; }
.strategy-window-card__actions { display: flex; gap: 10px; align-items: center; }
.matrix-selector { display: inline-flex; gap: 8px; align-items: center; color: var(--muted); font-size: 11px; }
.matrix-selector input { accent-color: var(--mint); }
.strategy-window-card h3 { margin: 7px 0; color: var(--ink); font-size: 20px; overflow-wrap: anywhere; }
.identity-kind { color: var(--amber); font: 500 9px/1 'SFMono-Regular', Consolas, monospace; letter-spacing: .08em; }
.inspect-button { flex: 0 0 auto; }
.window-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }
.window-card { padding: 16px; border: 1px solid var(--line); border-radius: 14px; background: var(--surface); }
.window-card header span, .window-card header strong { display: block; }
.window-card header span { color: var(--mint); font: 600 11px/1.2 'SFMono-Regular', Consolas, monospace; }
.window-card header strong { margin-top: 5px; color: var(--muted); font-size: 9px; letter-spacing: .06em; }
.window-card header code { color: var(--muted); font-size: 10px; }
.exact-rate { margin: 18px 0; color: var(--ink); font: 650 28px/1 'SFMono-Regular', Consolas, monospace; }
.window-card dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; overflow: hidden; margin: 0; border: 1px solid var(--line); border-radius: 10px; background: var(--line); }
.window-card dl div { padding: 9px; background: #0a1714; }
.window-card dt, .window-card dd { margin: 0; }
.window-card dt { color: var(--muted); font-size: 8px; text-transform: uppercase; }
.window-card dd { margin-top: 5px; color: var(--ink); font: 500 10px/1.3 'SFMono-Regular', Consolas, monospace; overflow-wrap: anywhere; }
.window-card footer { align-items: flex-start; flex-direction: column; margin-top: 14px; color: var(--muted); font-size: 10px; }
.zero-observation { margin: 18px 0 0; padding: 14px; border: 1px dashed var(--line); border-radius: 12px; color: var(--muted); }
.matrix-result-list { display: grid; gap: 20px; margin: 20px 0 0; padding: 0; list-style: none; }
.matrix-result-card { padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: rgb(7 18 15 / 62%); }
.matrix-result-card h3 { margin: 7px 0; color: var(--ink); overflow-wrap: anywhere; }
.matrix-table-scroll { overflow-x: auto; margin-top: 18px; }
.stability-matrix { width: 100%; min-width: 1120px; border-collapse: collapse; color: var(--ink); font-size: 11px; }
.stability-matrix caption { padding: 0 0 12px; color: var(--muted); text-align: left; }
.stability-matrix th, .stability-matrix td { padding: 10px; border: 1px solid var(--line); vertical-align: top; }
.stability-matrix th { background: #0a1714; color: var(--mint); text-align: left; }
.matrix-cell-detail summary { color: var(--muted); cursor: pointer; }
.matrix-cell-detail dl { display: grid; gap: 7px; margin: 10px 0 0; }
.matrix-cell-detail dl div { display: grid; gap: 2px; }
.matrix-cell-detail dt { color: var(--muted); font-size: 8px; overflow-wrap: anywhere; }
.matrix-cell-detail dd { margin: 0; color: var(--ink); font: 500 10px/1.3 'SFMono-Regular', Consolas, monospace; }
.matrix-unavailable { color: var(--muted); font-size: 9px; line-height: 1.4; }
.matrix-item-error { margin-top: 16px; }
.detail-panel { border-color: rgb(121 227 178 / 38%); }
.detail-content h3 { margin-bottom: 6px; color: var(--ink); }
.detail-content { color: var(--muted); }
.detail-content ol { display: grid; gap: 8px; padding: 0; list-style: none; }
.detail-content li { display: flex; gap: 16px; justify-content: space-between; padding: 12px; border: 1px solid var(--line); border-radius: 10px; }
.detail-content li strong { color: var(--ink); }
@media (max-width: 900px) {
  .historical-heading, .analysis-controls { grid-template-columns: 1fr; }
  .research-guard { min-width: 0; }
  .source-facts, .identity-facts, .window-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 620px) {
  .source-facts, .identity-facts, .window-grid, .window-card dl { grid-template-columns: 1fr; }
  .panel-heading, .strategy-window-card__header, .strategy-window-card__actions, .research-state { align-items: flex-start; flex-direction: column; }
  .source-facts__identity { grid-column: auto; }
  .source-facts__identity dd { align-items: flex-start; flex-direction: column; }
}
</style>
