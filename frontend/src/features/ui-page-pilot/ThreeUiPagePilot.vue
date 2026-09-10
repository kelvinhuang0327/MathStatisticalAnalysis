<script setup lang="ts">
import { ref } from 'vue'

import SectionHeader from '../../components/SectionHeader.vue'
import MetricCard from '../../components/MetricCard.vue'
import EmptyState from '../../components/EmptyState.vue'
import ErrorState from '../../components/ErrorState.vue'
import SkeletonLoader from '../../components/SkeletonLoader.vue'
import GradientPillButton from './GradientPillButton.vue'

type PilotState = 'ready' | 'loading' | 'empty' | 'error'

const pilotState = ref<PilotState>('ready')
const isRegenerating = ref(false)

const DEMO_METRICS = [
  { label: '示範指標 A', value: '42.0%', subvalue: '示範資料，非真實結果' },
  { label: '示範指標 B', value: '128', subvalue: '示範資料，非真實結果' },
  { label: '示範指標 C', value: '0.87', subvalue: '示範資料，非真實結果' },
]

function setState(next: PilotState): void {
  isRegenerating.value = false
  pilotState.value = next
}

function regenerate(): void {
  if (isRegenerating.value) return
  isRegenerating.value = true
  setTimeout(() => {
    isRegenerating.value = false
  }, 500)
}

function loadDemoData(): void {
  pilotState.value = 'ready'
}

function handleRetry(): void {
  pilotState.value = 'ready'
}
</script>

<template>
  <div class="pilot-page">
    <SectionHeader
      title="分析工作區導覽"
      eyebrow="開發預覽 · 僅供示範"
      description="這是開發環境限定的示範頁面，用於預覽元件與版面配置；所有數值皆為示範資料，並非真實分析結果。"
    />

    <div class="pilot-demo-switcher" role="group" aria-label="示範狀態切換">
      <button
        type="button"
        class="button button--quiet"
        data-testid="pilot-switch-ready"
        :class="{ 'is-active': pilotState === 'ready' }"
        :aria-pressed="pilotState === 'ready'"
        @click="setState('ready')"
      >
        就緒
      </button>
      <button
        type="button"
        class="button button--quiet"
        data-testid="pilot-switch-loading"
        :class="{ 'is-active': pilotState === 'loading' }"
        :aria-pressed="pilotState === 'loading'"
        @click="setState('loading')"
      >
        載入中
      </button>
      <button
        type="button"
        class="button button--quiet"
        data-testid="pilot-switch-empty"
        :class="{ 'is-active': pilotState === 'empty' }"
        :aria-pressed="pilotState === 'empty'"
        @click="setState('empty')"
      >
        無資料
      </button>
      <button
        type="button"
        class="button button--quiet"
        data-testid="pilot-switch-error"
        :class="{ 'is-active': pilotState === 'error' }"
        :aria-pressed="pilotState === 'error'"
        @click="setState('error')"
      >
        錯誤
      </button>
    </div>

    <section class="pilot-content">
      <template v-if="pilotState === 'loading'">
        <SkeletonLoader type="card" :rows="3" height="110px" />
      </template>

      <template v-else-if="pilotState === 'empty'">
        <EmptyState
          title="尚無示範資料"
          description="點擊下方按鈕載入示範分析資料（並非真實資料）。"
        >
          <GradientPillButton label="載入示範資料" @click="loadDemoData" />
        </EmptyState>
      </template>

      <template v-else-if="pilotState === 'error'">
        <ErrorState
          title="示範資料錯誤"
          message="示範資料載入失敗（模擬錯誤，並非真實系統錯誤）。"
          retry-label="重試"
          :retryable="true"
          @retry="handleRetry"
        />
      </template>

      <template v-else>
        <p class="pilot-demo-flag">⚠️ 以下皆為示範資料，非真實分析結果</p>
        <div class="pilot-metrics" data-testid="pilot-metrics">
          <MetricCard
            v-for="metric in DEMO_METRICS"
            :key="metric.label"
            :label="metric.label"
            :value="metric.value"
            :subvalue="metric.subvalue"
          />
        </div>
        <div class="pilot-actions">
          <GradientPillButton
            label="重新產生示範分析"
            loading-label="產生中…"
            :loading="isRegenerating"
            @click="regenerate"
          />
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.pilot-page {
  box-sizing: border-box;
  width: 100%;
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 20px 48px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.pilot-demo-switcher {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pilot-demo-switcher .is-active {
  border-color: var(--border-focus);
  color: var(--text-primary);
  background: rgba(139, 92, 246, 0.16);
}

.pilot-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.pilot-demo-flag {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.pilot-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  min-width: 0;
}

.pilot-actions {
  display: flex;
  justify-content: flex-start;
}

@media (max-width: 640px) {
  .pilot-page {
    padding: 20px 16px 32px;
  }

  .pilot-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
