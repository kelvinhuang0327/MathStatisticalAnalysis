<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

import {
  getP638MultiWindowSuccessWindows,
  getT539MultiWindowSuccessWindows,
  MultiWindowSuccessWindowsRequestError,
  type MultiWindowRequestErrorKind,
  type P638MultiWindowSuccessWindowsResponse,
  type T539MultiWindowSuccessWindowsResponse,
} from '../../api/multiWindowSuccessWindows'

type Lottery = 'P638' | 'T539'
type State =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'empty'
  | 'not-configured'
  | 'not-found'
  | 'invalid-request'
  | 'unavailable'
  | 'http-error'
  | 'malformed'
type Response = P638MultiWindowSuccessWindowsResponse | T539MultiWindowSuccessWindowsResponse

const props = defineProps<{
  lottery: Lottery
  runId: string
}>()

const state = ref<State>('idle')
const result = ref<Response | null>(null)
const message = ref('')
const errorCode = ref<string | null>(null)
const errorStatus = ref<number | null>(null)

let controller: AbortController | undefined
let generation = 0

async function load(): Promise<void> {
  controller?.abort()
  const currentController = new AbortController()
  controller = currentController
  const currentGeneration = ++generation
  const runId = props.runId
  const lottery = props.lottery
  result.value = null
  message.value = ''
  errorCode.value = null
  errorStatus.value = null

  if (!runId) {
    state.value = 'idle'
    return
  }

  state.value = 'loading'
  try {
    const response =
      lottery === 'P638'
        ? await getP638MultiWindowSuccessWindows(runId, currentController.signal)
        : await getT539MultiWindowSuccessWindows(runId, currentController.signal)
    if (currentGeneration !== generation || props.runId !== runId || props.lottery !== lottery) return
    result.value = response
    state.value = response.rows.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (
      currentGeneration !== generation ||
      isAbort(error) ||
      props.runId !== runId ||
      props.lottery !== lottery
    ) {
      return
    }
    result.value = null
    state.value = mapErrorState(error)
    message.value = error instanceof Error ? error.message : 'Multi-window success windows could not load.'
    if (error instanceof MultiWindowSuccessWindowsRequestError) {
      errorCode.value = error.errorCode
      errorStatus.value = error.status || null
    }
  }
}

function mapErrorState(error: unknown): State {
  if (error instanceof MultiWindowSuccessWindowsRequestError) {
    if (
      error.kind === 'UNAVAILABLE' &&
      error.status >= 400 &&
      error.status !== 503
    ) {
      return 'http-error'
    }
    const states: Record<MultiWindowRequestErrorKind, State> = {
      NOT_CONFIGURED: 'not-configured',
      NOT_FOUND: 'not-found',
      INVALID_REQUEST: 'invalid-request',
      UNAVAILABLE: 'unavailable',
      MALFORMED_RESPONSE: 'malformed',
    }
    return states[error.kind]
  }
  return 'unavailable'
}

function formatExact(value: { decimal_18: string; numerator: string; denominator: string } | null): string {
  return value === null
    ? 'Unavailable (null)'
    : `${value.decimal_18} (${value.numerator}/${value.denominator})`
}

function formatCount(value: number): string {
  return value.toLocaleString()
}

function formatOptionalCount(value: number | null | undefined): string {
  return value === null || value === undefined ? 'Not provided by API' : formatCount(value)
}

function targetBoundary(date: string | null | undefined, id: string | null | undefined): string {
  const parts = [date, id].filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
  return parts.length ? parts.join(' · ') : 'Not provided by API'
}

function sourceValue(value: string | null | undefined): string {
  return typeof value === 'string' && value.trim().length > 0
    ? value
    : 'Not provided by API'
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

watch(() => [props.lottery, props.runId] as const, () => void load(), { immediate: true })

onBeforeUnmount(() => {
  generation += 1
  controller?.abort()
})
</script>

<template>
  <section
    class="panel"
    :aria-labelledby="`${lottery.toLowerCase()}-multi-window-success-title`"
    :data-testid="`${lottery.toLowerCase()}-multi-window-success-panel`"
  >
    <div class="panel__heading">
      <div>
        <p class="step-label">Read-only run evidence</p>
        <h2 :id="`${lottery.toLowerCase()}-multi-window-success-title`">Multi-window success windows</h2>
      </div>
      <button
        class="button button--quiet"
        type="button"
        :data-testid="`${lottery.toLowerCase()}-multi-window-refresh`"
        :disabled="state === 'loading' || !runId"
        @click="load"
      >
        Refresh
      </button>
    </div>
    <p class="panel__note">
      Selected run <code>{{ runId || '—' }}</code>. Target and ticket fractions, window identity, null
      probabilities, adjusted p-values, and evidence status are shown from the API response.
    </p>

    <p v-if="state === 'idle'" class="state-panel">Select a run to load its multi-window results.</p>
    <p v-else-if="state === 'loading'" class="state-panel" aria-live="polite">
      Loading multi-window results for {{ runId }}…
    </p>
    <p v-else-if="state === 'empty'" class="state-panel" data-testid="multi-window-empty">
      API query: SUCCESS_EMPTY · No multi-window success-window rows are available for this run.
    </p>
    <div
      v-else-if="state !== 'ready'"
      class="state-panel"
      :class="state === 'not-configured' ? 'state-panel--warning' : 'state-panel--error'"
      role="status"
      aria-live="polite"
      :data-testid="`${lottery.toLowerCase()}-multi-window-error-${errorStatus ?? 'response'}`"
    >
      <p v-if="state === 'not-found'">HTTP_ERROR · HTTP 404: no multi-window results were found for this run.</p>
      <p v-else-if="state === 'invalid-request'">HTTP_ERROR · HTTP 422: the multi-window request was rejected.</p>
      <p v-else-if="state === 'not-configured'">
        SOURCE_NOT_CONFIGURED · HTTP 503: the Historical Results source is not configured.
      </p>
      <p v-else-if="state === 'unavailable'">
        API_UNAVAILABLE{{ errorStatus ? ' · HTTP ' + errorStatus : '' }}: multi-window results could not load.
      </p>
      <p v-else-if="state === 'http-error'">
        HTTP_ERROR · HTTP {{ errorStatus }}: the multi-window request failed.
      </p>
      <p v-else>Multi-window API response was malformed.</p>
      <p v-if="message">{{ message }}</p>
      <p v-if="errorCode">Error code: <code>{{ errorCode }}</code></p>
      <button
        class="button button--quiet"
        type="button"
        :data-testid="`${lottery.toLowerCase()}-multi-window-retry`"
        @click="load"
      >
        Retry
      </button>
    </div>

    <template v-else-if="result">
      <p class="table-note" data-testid="multi-window-query-success">
        API query: SUCCESS_WITH_DATA · {{ result.lottery_type }} · {{ result.rows.length }} rows ·
        evidence {{ result.evidence_status }} · run status {{ result.status }}
      </p>
      <dl class="source-facts" aria-label="Multi-window source identity">
        <div><dt>Event</dt><dd>{{ sourceValue(result.event) }}</dd></div>
        <div><dt>Source SHA-256</dt><dd><code>{{ sourceValue(result.source_sha256) }}</code></dd></div>
        <div><dt>Source commit</dt><dd><code>{{ sourceValue(result.source_commit) }}</code></dd></div>
        <div>
          <dt>Strategy-set fingerprint</dt>
          <dd><code>{{ sourceValue(result.strategy_set_fingerprint) }}</code></dd>
        </div>
        <div><dt>Source authority</dt><dd>{{ sourceValue(result.source_authority) }}</dd></div>
        <div><dt>Official evaluator</dt><dd>{{ sourceValue(result.null_contract.official_evaluator) }}</dd></div>
        <div><dt>Prize-rule version</dt><dd>{{ sourceValue(result.null_contract.prize_rule_version) }}</dd></div>
        <div>
          <dt>Prize-rule source SHA-256</dt>
          <dd><code>{{ sourceValue(result.null_contract.prize_rule_source_sha256) }}</code></dd>
        </div>
      </dl>
      <p class="panel__note">
        OFFICIAL_ANY_PRIZE means at least one ticket receives an official prize. Target success rates
        and ticket success rates are separate API events and denominators; each row retains its own
        strategy and window kind/role.
      </p>
      <div class="table-wrap">
        <table>
          <caption>
            Event {{ result.event }}. Exact fractions, source counts, and null values are preserved from the API;
            window identities are not combined.
          </caption>
          <thead>
            <tr>
              <th>Strategy / tickets</th>
              <th>Window kind / role</th>
              <th>Target success rate</th>
              <th>Ticket success rate</th>
              <th>Null baseline</th>
              <th>Adjusted p-value</th>
              <th>Evidence status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in result.rows"
              :key="`${row.strategy_id}:${row.strategy_version}:${row.native_ticket_count}:${row.window_kind}:${row.window_role}`"
            >
              <td>
                <strong>{{ row.strategy_id }}</strong>
                <small>{{ row.strategy_version }}</small>
                <small>native_ticket_count: {{ formatCount(row.native_ticket_count) }}</small>
                <small>status: {{ row.status }}</small>
              </td>
              <td>
                <strong>{{ row.window_kind }}</strong>
                <small>{{ row.window_role }}</small>
                <small>
                  Target span: {{ targetBoundary(row.first_target_date, row.first_target_id) }} →
                  {{ targetBoundary(row.last_target_date, row.last_target_id) }}
                </small>
                <small>
                  Source targets: {{ formatCount(row.source_target_count) }} · requested targets:
                  {{ formatOptionalCount(row.requested_target_count) }}
                </small>
              </td>
              <td>
                <span>{{ formatExact(row.observed_winning_target_rate) }}</span>
                <small>
                  {{ formatCount(row.observed_winning_target_count) }} winning targets ·
                  {{ formatCount(row.actual_target_count) }} actual targets
                </small>
              </td>
              <td>
                <span>{{ formatExact(row.observed_ticket_winning_rate) }}</span>
                <small>
                  {{ formatCount(row.observed_winning_ticket_count) }} winning tickets ·
                  {{ formatCount(row.observed_ticket_count) }} observed tickets
                </small>
              </td>
              <td>
                <span>Single ticket: {{ formatExact(row.null_single_ticket_probability) }}</span>
                <small>Portfolio: {{ formatExact(row.null_portfolio_probability) }}</small>
              </td>
              <td>{{ formatExact(row.by_adjusted_p_value) }}</td>
              <td>{{ row.evidence_status }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>
