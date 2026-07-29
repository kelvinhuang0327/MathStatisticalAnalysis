<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  queryStrategyEvidence,
  type StrategyEvidenceResponse,
} from '../../api/strategyEvidence'

type LoadState = 'loading' | 'ready' | 'empty' | 'error'

const response = ref<StrategyEvidenceResponse | null>(null)
const loadState = ref<LoadState>('loading')
const message = ref('')
const search = ref('')
let controller: AbortController | undefined
let generation = 0
let unmounted = false

const visibleItems = computed(() => {
  const items = response.value?.items ?? []
  const query = search.value.trim().toLocaleLowerCase()
  if (!query) return items
  return items.filter(
    (item) =>
      item.strategy_id.toLocaleLowerCase().includes(query) ||
      item.display_name.toLocaleLowerCase().includes(query),
  )
})

async function loadEvidence(): Promise<void> {
  controller?.abort()
  const requestController = new AbortController()
  controller = requestController
  const requestGeneration = ++generation
  loadState.value = 'loading'
  message.value = ''
  try {
    const result = await queryStrategyEvidence(requestController.signal)
    if (unmounted || requestGeneration !== generation) return
    response.value = result
    loadState.value = result.items.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (unmounted || requestGeneration !== generation || isAbort(error)) return
    response.value = null
    loadState.value = 'error'
    message.value = error instanceof Error ? error.message : 'Strategy Evidence could not load.'
  }
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

onMounted(loadEvidence)
onBeforeUnmount(() => {
  unmounted = true
  controller?.abort()
})
</script>

<template>
  <section class="workspace-page" aria-labelledby="strategy-evidence-title">
    <header class="page-heading">
      <div>
        <p class="eyebrow">Canonical availability · single source of truth</p>
        <h1 id="strategy-evidence-title">Strategy Evidence</h1>
        <p class="page-intro">
          Catalog identity, lifecycle metadata, adapter availability, and canonical evidence
          registration are shown independently. No lifecycle flag or replay result is converted
          into evidence, D3, or ranking.
        </p>
      </div>
      <div class="scope-card"><span>D3 value</span><strong>{{ response?.d3.value ?? '—' }}</strong><small>{{ response?.d3.status ?? 'loading' }}</small></div>
    </header>

    <p v-if="loadState === 'loading'" class="state-panel">Loading committed evidence registries…</p>
    <div v-else-if="loadState === 'error'" class="state-panel state-panel--error">
      <p>{{ message }}</p>
      <button class="button button--quiet" type="button" @click="loadEvidence">Retry</button>
    </div>
    <p v-else-if="loadState === 'empty'" class="state-panel">The Strategy Catalog is empty.</p>

    <template v-else-if="response">
      <div class="workspace-grid">
        <article class="panel">
          <p class="step-label">Best Strategy</p>
          <h2>{{ response.best_strategy.status }}</h2>
          <code>{{ response.best_strategy.reason }}</code>
          <p>No catalog order is presented as a ranking.</p>
        </article>
        <article class="panel">
          <p class="step-label">D3 SSOT</p>
          <h2>{{ response.d3.status }}</h2>
          <code>D3_VALUE: {{ response.d3.value }}</code>
          <p>Unavailable is never rendered as zero.</p>
        </article>
        <article class="panel">
          <p class="step-label">Strategy Combination Hit Rate</p>
          <h2>{{ response.strategy_combination_hit_rate.status }}</h2>
          <code>VALUE: {{ response.strategy_combination_hit_rate.value }}</code>
          <p>OWNER: {{ response.strategy_combination_hit_rate.owner }}</p>
        </article>
      </div>

      <label class="panel">
        <span>Filter by strategy identity or display name</span>
        <input v-model="search" type="search" maxlength="100" />
      </label>

      <p v-if="visibleItems.length === 0" class="state-panel">
        No strategy identity matches this filter.
      </p>
      <div v-else class="table-wrap">
        <table>
          <caption>Catalog identity and evidence availability</caption>
          <thead>
            <tr>
              <th>Identity</th><th>Catalog metadata</th><th>Adapter</th>
              <th>Registration</th><th>Definition</th><th>Verification</th><th>Reason</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in visibleItems" :key="`${item.strategy_id}-${item.strategy_version}-${item.replicate}`">
              <td>
                <strong>{{ item.strategy_id }}</strong>
                <small>version: {{ item.strategy_version }}</small>
                <small>replicate: {{ item.replicate }}</small>
              </td>
              <td>
                {{ item.display_name }}
                <small>{{ item.lifecycle_status }} · executable {{ item.executable ? 'YES' : 'NO' }}</small>
                <small>{{ item.supported_lottery_types.join(', ') }} · min {{ item.minimum_history }}</small>
                <small>{{ item.provenance.join(' · ') || 'No provenance declared' }}</small>
              </td>
              <td>{{ item.adapter_available ? 'AVAILABLE' : 'UNAVAILABLE' }}</td>
              <td>{{ item.registration_status }}</td>
              <td>{{ item.definition_status }}</td>
              <td>{{ item.verification_status }}</td>
              <td><code>{{ item.unavailable_reason_code ?? '—' }}</code></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>
