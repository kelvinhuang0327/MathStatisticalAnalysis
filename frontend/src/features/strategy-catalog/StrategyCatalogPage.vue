<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { listStrategies, type StrategyView } from '../../api/strategies'

type LoadState = 'loading' | 'ready' | 'empty' | 'error'

const strategies = ref<StrategyView[]>([])
const loadState = ref<LoadState>('loading')
const errorMessage = ref('')
let requestController: AbortController | undefined

function isExecutable(strategy: StrategyView): boolean {
  return strategy.lifecycle_status === 'ONLINE' && strategy.executable
}

function executionLabel(strategy: StrategyView): string {
  return isExecutable(strategy) ? 'Executable' : 'Metadata only'
}

async function loadStrategyCatalog(): Promise<void> {
  requestController?.abort()
  requestController = new AbortController()
  loadState.value = 'loading'
  errorMessage.value = ''
  try {
    strategies.value = await listStrategies(requestController.signal)
    loadState.value = strategies.value.length === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load Strategy Catalog'
    loadState.value = 'error'
  }
}

onMounted(loadStrategyCatalog)
onBeforeUnmount(() => requestController?.abort())
</script>

<template>
  <section class="catalog" aria-labelledby="strategy-catalog-title">
    <header class="catalog__heading">
      <div>
        <p class="eyebrow">P600B · read-only pilot</p>
        <h1 id="strategy-catalog-title">Strategy Catalog</h1>
        <p class="catalog__intro">
          Pinned lifecycle metadata for the first LottoLab migration slice. Prediction and
          generation controls are intentionally unavailable.
        </p>
      </div>
      <div class="catalog__scope" aria-label="Catalog scope">
        <span>BIG_LOTTO</span>
        <strong>{{ loadState === 'loading' || loadState === 'error' ? '—' : strategies.length }}</strong>
        <small>strategies</small>
      </div>
    </header>

    <div class="catalog__status" aria-live="polite">
      <p v-if="loadState === 'loading'" class="state-panel">Loading catalog metadata…</p>
      <div v-else-if="loadState === 'error'" class="state-panel state-panel--error">
        <p>{{ errorMessage }}</p>
        <button class="catalog__retry" type="button" @click="loadStrategyCatalog">Retry</button>
      </div>
      <p v-else-if="loadState === 'empty'" class="state-panel">
        No strategies are available in this catalog slice.
      </p>
    </div>

    <ul v-if="loadState === 'ready'" class="strategy-grid" aria-label="Migrated strategies">
      <li v-for="strategy in strategies" :key="strategy.strategy_id" class="strategy-card">
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
            <dt>Lottery</dt>
            <dd>{{ strategy.supported_lottery_types.join(', ') }}</dd>
          </div>
          <div>
            <dt>Minimum history</dt>
            <dd>{{ strategy.minimum_history }} draw</dd>
          </div>
          <div>
            <dt>Execution</dt>
            <dd>{{ isExecutable(strategy) ? 'Enabled' : 'Unavailable' }}</dd>
          </div>
        </dl>

        <p class="strategy-card__guard">
          <span aria-hidden="true">●</span>
          OBSERVATION entries cannot be loaded by the executable registry.
        </p>
      </li>
    </ul>
  </section>
</template>
