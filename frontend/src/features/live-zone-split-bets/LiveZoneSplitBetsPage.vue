<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import {
  generateLiveZoneSplitBets,
  isValidNumBets,
  LiveZoneSplitBetsRequestError,
  MAX_NUM_BETS,
  MIN_NUM_BETS,
  type LiveZoneSplitBetsResponse,
} from '../../api/liveZoneSplitBets'

const numBetsInput = ref(3)
const pending = ref(false)
const result = ref<LiveZoneSplitBetsResponse | null>(null)
const errorMessage = ref('')

let controller: AbortController | undefined
let generation = 0
let unmounted = false

const numBetsIsValid = computed(() => isValidNumBets(numBetsInput.value))

const applicationStatusCopy = computed<{ headline: string; message: string } | null>(() => {
  if (!result.value || result.value.status === 'OK') return null
  switch (result.value.status) {
    case 'INVALID_REQUEST':
      return {
        headline: 'Request rejected',
        message: 'The requested number of bets was rejected as invalid.',
      }
    case 'INVALID_OUTPUT':
      return {
        headline: 'Invalid result',
        message: 'The strategy produced an invalid result, so no bets were generated.',
      }
    case 'EXECUTION_ERROR':
      return {
        headline: 'Execution failed',
        message: 'Bet generation failed due to an internal execution error.',
      }
  }
})

function isAbort(error: unknown): boolean {
  return (
    (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
  )
}

async function generate(): Promise<void> {
  if (!numBetsIsValid.value) return

  controller?.abort()
  const currentGeneration = ++generation
  const currentController = new AbortController()
  controller = currentController
  pending.value = true
  errorMessage.value = ''
  result.value = null

  try {
    const response = await generateLiveZoneSplitBets(numBetsInput.value, currentController.signal)
    if (unmounted || currentGeneration !== generation) return
    result.value = response
  } catch (error) {
    if (isAbort(error)) return
    if (unmounted || currentGeneration !== generation) return
    result.value = null
    errorMessage.value =
      error instanceof LiveZoneSplitBetsRequestError
        ? error.message
        : 'Live Zone Split request failed.'
  } finally {
    if (!unmounted && currentGeneration === generation) {
      pending.value = false
      if (controller === currentController) controller = undefined
    }
  }
}

onBeforeUnmount(() => {
  unmounted = true
  controller?.abort()
})
</script>

<template>
  <div class="workspace-page">
    <div class="page-heading">
      <div>
        <h1 id="live-zone-split-bets-title">Live Zone Split Bets</h1>
        <p class="page-intro">
          Generates one or more Live Zone Split bets from the merged target API contract. This is
          a target-contract-only view; it makes no claim of legacy LotteryNew consumer parity.
        </p>
      </div>
    </div>

    <div class="panel">
      <div class="panel__heading">
        <h2>Generate</h2>
      </div>
      <form @submit.prevent="generate">
        <div class="filter-grid">
          <label>
            <span>Number of bets</span>
            <input
              v-model.number="numBetsInput"
              type="number"
              name="num_bets"
              :min="MIN_NUM_BETS"
              :max="MAX_NUM_BETS"
              step="1"
            />
          </label>
        </div>
        <div class="filter-actions">
          <button
            type="submit"
            class="button button--primary"
            :disabled="pending || !numBetsIsValid"
          >
            {{ pending ? 'Generating…' : 'Generate' }}
          </button>
        </div>
      </form>
    </div>

    <div class="status-region">
      <p v-if="pending">Generating Live Zone Split bets…</p>

      <div v-else-if="errorMessage" class="state-panel state-panel--error">
        <p>{{ errorMessage }}</p>
      </div>

      <div v-else-if="applicationStatusCopy" class="state-panel state-panel--warning">
        <strong>{{ applicationStatusCopy.headline }}</strong>
        <p>{{ applicationStatusCopy.message }}</p>
        <p v-if="result?.reason_code">Reason code: {{ result.reason_code }}</p>
      </div>

      <div v-else-if="result && result.status === 'OK'" class="panel">
        <div class="panel__heading">
          <h2>Primary bet</h2>
        </div>
        <div class="number-chips primary-bet">
          <span v-for="number in result.bets![0]" :key="number" class="number-chip">
            {{ number }}
          </span>
        </div>

        <dl class="metric-grid">
          <div>
            <dt>Coverage rate</dt>
            <dd>{{ (result.coverage_rate! * 100).toFixed(1) }}%</dd>
          </div>
          <div>
            <dt>Total unique numbers</dt>
            <dd>{{ result.total_unique_numbers }}</dd>
          </div>
          <div>
            <dt>Method</dt>
            <dd>{{ result.method }}</dd>
          </div>
          <div>
            <dt>Philosophy</dt>
            <dd>{{ result.philosophy }}</dd>
          </div>
        </dl>

        <div class="panel__heading">
          <h2>All bets</h2>
        </div>
        <ul class="plain-list all-bets">
          <li v-for="(bet, index) in result.bets" :key="index">
            <div class="number-chips">
              <span v-for="number in bet" :key="number" class="number-chip">{{ number }}</span>
            </div>
          </li>
        </ul>
      </div>

      <p v-else class="empty-copy">No bets have been generated yet.</p>
    </div>
  </div>
</template>
