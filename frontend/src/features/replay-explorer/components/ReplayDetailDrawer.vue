<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import StatusBadge from '../../../components/StatusBadge.vue'
import type { GameCode, ReplayExplorerAdapter, ReplayExplorerItem, TargetDetailRecord } from '../types'

const props = defineProps<{
  isOpen: boolean
  item: ReplayExplorerItem | null
  game: GameCode
  adapter?: ReplayExplorerAdapter
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const targets = ref<TargetDetailRecord[]>([])
const targetsLoading = ref(false)
const targetsError = ref('')
let abortController: AbortController | undefined

// Watch item changes to lazy load target list if supported
watch(
  () => props.item,
  (newItem) => {
    targets.value = []
    targetsError.value = ''
    if (newItem && props.adapter?.supportsTargetInspection && props.adapter.loadTargetList) {
      void loadTargets(newItem)
    }
  },
  { immediate: true },
)

async function loadTargets(targetItem: ReplayExplorerItem): Promise<void> {
  if (!props.adapter?.loadTargetList) return
  abortController?.abort()
  const controller = new AbortController()
  abortController = controller

  targetsLoading.value = true
  targetsError.value = ''

  try {
    const list = await props.adapter.loadTargetList(
      targetItem.strategyId,
      targetItem.periodKey,
      targetItem.ticketCount,
      controller.signal,
    )
    targets.value = list
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') return
    targetsError.value = 'Failed to load target-level replay details.'
  } finally {
    targetsLoading.value = false
  }
}

// Handle ESC key to close drawer
function handleKeyDown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && props.isOpen) {
    emit('close')
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  abortController?.abort()
})

const drawerTitle = computed(() => props.item?.displayLabel || 'Strategy Details')
</script>

<template>
  <div
    v-if="isOpen && item"
    class="drawer-backdrop"
    role="dialog"
    aria-modal="true"
    :aria-label="drawerTitle"
    @click.self="emit('close')"
  >
    <div class="drawer-panel" tabindex="-1">
      <!-- Drawer Header -->
      <div class="drawer-header">
        <div class="header-titles">
          <span class="game-badge">{{ game }} Replay Inspection</span>
          <h3 class="strategy-title">{{ item.displayLabel }}</h3>
          <div class="header-meta">
            <code>Version: {{ item.strategyVersion }}</code>
            <span v-if="item.methodFamily" class="meta-family">Family: {{ item.methodFamily }}</span>
            <span class="meta-ticket">{{ item.ticketCount }} Tickets</span>
          </div>
        </div>
        <button
          type="button"
          class="close-button"
          aria-label="Close details"
          @click="emit('close')"
        >
          ✕
        </button>
      </div>

      <!-- Drawer Body -->
      <div class="drawer-body">
        <!-- Evidence Status Box -->
        <div class="evidence-box">
          <div class="evidence-status-header">
            <StatusBadge
              :status="item.evidenceStatus"
              :variant="
                item.evidenceStatus === 'DESCRIPTIVE LEADER' || item.evidenceStatus === 'PARETO FRONTIER'
                  ? 'success'
                  : item.evidenceStatus === 'LOW POWER' || item.evidenceStatus === 'LIMITED SAMPLE'
                    ? 'warning'
                    : 'neutral'
              "
            />
            <span v-if="item.rank !== null" class="rank-tag">Official Rank: #{{ item.rank }}</span>
          </div>
          <p class="evidence-notes text-muted">{{ item.notes }}</p>
        </div>

        <!-- Metrics Overview Grid -->
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label text-muted">Winning Hit Rate</span>
            <strong class="metric-val text-cyan">{{ item.hitRateFormatted }}</strong>
          </div>

          <div v-if="game === 'B649'" class="metric-card">
            <span class="metric-label text-muted">Baseline Delta</span>
            <strong
              class="metric-val"
              :class="{
                'text-emerald': item.baselineDelta !== null && item.baselineDelta > 0,
                'text-rose': item.baselineDelta !== null && item.baselineDelta < 0,
              }"
            >
              {{ item.baselineDeltaFormatted }}
            </strong>
          </div>

          <div class="metric-card">
            <span class="metric-label text-muted">Evaluated Targets</span>
            <strong class="metric-val">{{ item.evaluatedTargets !== null ? item.evaluatedTargets.toLocaleString() : '—' }}</strong>
          </div>

          <div class="metric-card">
            <span class="metric-label text-muted">Winning Targets</span>
            <strong class="metric-val">{{ item.winningTargets !== null ? item.winningTargets.toLocaleString() : '—' }}</strong>
          </div>

          <div class="metric-card">
            <span class="metric-label text-muted">Period / Horizon</span>
            <strong class="metric-val">{{ item.periodLabel }}</strong>
          </div>

          <div class="metric-card">
            <span class="metric-label text-muted">Best Hit Level</span>
            <strong class="metric-val text-amber">{{ item.bestHit }}</strong>
          </div>
        </div>

        <!-- Prize Distribution Section (if present) -->
        <div v-if="item.prizeCounts" class="section-card">
          <h4 class="section-heading">Prize Tier Breakdown</h4>
          <div class="prize-grid">
            <div class="prize-item">
              <span class="prize-name">1st Prize (Jackpot)</span>
              <strong class="prize-count">{{ item.prizeCounts.first }}</strong>
            </div>
            <div class="prize-item">
              <span class="prize-name">2nd Prize</span>
              <strong class="prize-count">{{ item.prizeCounts.second }}</strong>
            </div>
            <div class="prize-item">
              <span class="prize-name">3rd Prize</span>
              <strong class="prize-count">{{ item.prizeCounts.third }}</strong>
            </div>
            <div class="prize-item">
              <span class="prize-name">4th Prize</span>
              <strong class="prize-count">{{ item.prizeCounts.fourth }}</strong>
            </div>
            <div class="prize-item">
              <span class="prize-name">5th Prize</span>
              <strong class="prize-count">{{ item.prizeCounts.fifth }}</strong>
            </div>
            <div v-if="item.prizeCounts.sixth !== undefined" class="prize-item">
              <span class="prize-name">6th Prize</span>
              <strong class="prize-count">{{ item.prizeCounts.sixth }}</strong>
            </div>
            <div v-if="item.prizeCounts.seventh !== undefined" class="prize-item">
              <span class="prize-name">7th Prize</span>
              <strong class="prize-count">{{ item.prizeCounts.seventh }}</strong>
            </div>
          </div>
        </div>

        <!-- Target-Level Replay Inspection (P638 / T539) -->
        <div v-if="adapter?.supportsTargetInspection" class="section-card">
          <div class="section-header-row">
            <h4 class="section-heading">Target-Level Draw Replay Evidence</h4>
            <span v-if="targets.length > 0" class="badge-count">{{ targets.length }} draws</span>
          </div>

          <div v-if="targetsLoading" class="loading-box">
            <span class="spinner" aria-hidden="true" />
            <span>Loading target details…</span>
          </div>

          <div v-else-if="targetsError" class="error-box">
            <span>{{ targetsError }}</span>
          </div>

          <div v-else-if="targets.length === 0" class="empty-box text-muted">
            No target-level draws recorded for this strategy.
          </div>

          <!-- Target list table -->
          <div v-else class="targets-table-wrapper">
            <table class="targets-table">
              <thead>
                <tr>
                  <th>Draw</th>
                  <th>Predicted Numbers</th>
                  <th>Actual Numbers</th>
                  <th>Hits</th>
                  <th>Prize Tier</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in targets.slice(0, 50)" :key="t.targetId">
                  <td>
                    <strong>#{{ t.drawNumberOrId }}</strong>
                  </td>
                  <td>
                    <template v-if="Array.isArray(t.predictedNumbers)">
                      <span class="number-chips">
                        <span v-for="(n, idx) in t.predictedNumbers" :key="idx" class="num-chip">{{ n }}</span>
                      </span>
                    </template>
                    <template v-else>
                      <span class="number-chips">
                        <span v-for="(n, idx) in t.predictedNumbers.zone1" :key="idx" class="num-chip">{{ n }}</span>
                        <span v-if="t.predictedNumbers.zone2" class="num-chip num-chip--special">Z2: {{ t.predictedNumbers.zone2 }}</span>
                      </span>
                    </template>
                  </td>
                  <td>
                    <template v-if="Array.isArray(t.actualNumbers)">
                      <span class="number-chips">
                        <span v-for="(n, idx) in t.actualNumbers" :key="idx" class="num-chip num-chip--actual">{{ n }}</span>
                      </span>
                    </template>
                    <template v-else>
                      <span class="number-chips">
                        <span v-for="(n, idx) in t.actualNumbers.zone1" :key="idx" class="num-chip num-chip--actual">{{ n }}</span>
                        <span v-if="t.actualNumbers.zone2" class="num-chip num-chip--special">Z2: {{ t.actualNumbers.zone2 }}</span>
                      </span>
                    </template>
                  </td>
                  <td>
                    <span class="hits-tag" :class="{ 'hits-tag--win': t.hitsCount >= 3 }">
                      {{ t.hitsCount }} Hits
                    </span>
                  </td>
                  <td>
                    <span v-if="t.prizeTier" class="prize-tag">{{ t.prizeTier }}</span>
                    <span v-else class="text-muted">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Strategy Metadata / Provenance -->
        <div class="section-card">
          <h4 class="section-heading">Strategy Provenance & Parameters</h4>
          <div class="details-list">
            <div class="detail-item">
              <span class="detail-k text-muted">Strategy ID</span>
              <span class="detail-v"><code>{{ item.strategyId }}</code></span>
            </div>
            <div class="detail-item">
              <span class="detail-k text-muted">Execution Status</span>
              <span class="detail-v">{{ item.status }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-k text-muted">Canonical Game Code</span>
              <span class="detail-v"><code>{{ game }}</code></span>
            </div>
            <div v-if="item.unrankedReason" class="detail-item">
              <span class="detail-k text-muted">Unranked Reason</span>
              <span class="detail-v">{{ item.unrankedReason }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}

.drawer-panel {
  width: 100%;
  max-width: 640px;
  height: 100%;
  background: #0f172a;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

.drawer-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: #111827;
}

.game-badge {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-cyan-400, #38bdf8);
  margin-bottom: 0.25rem;
}

.strategy-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #fff;
  word-break: break-word;
}

.header-meta {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.4rem;
  font-size: 0.8rem;
  color: var(--color-gray-400, #94a3b8);
  flex-wrap: wrap;
}

.meta-ticket {
  background: rgba(6, 182, 212, 0.15);
  color: var(--color-cyan-300, #67e8f9);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
}

.close-button {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--color-gray-300, #cbd5e1);
  font-size: 1rem;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.drawer-body {
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.evidence-box {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 1rem;
}

.evidence-status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.rank-tag {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-indigo-300, #a5b4fc);
}

.evidence-notes {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.4;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
}

.metric-card {
  background: rgba(30, 41, 59, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.metric-label {
  font-size: 0.75rem;
}

.metric-val {
  font-size: 1.1rem;
  color: #fff;
}

.text-cyan {
  color: var(--color-cyan-300, #67e8f9);
}

.text-emerald {
  color: var(--color-emerald-400, #34d399);
}

.text-rose {
  color: var(--color-rose-400, #fb7185);
}

.text-amber {
  color: var(--color-amber-400, #fbbf24);
}

.section-card {
  background: rgba(30, 41, 59, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 1.25rem;
}

.section-heading {
  margin: 0 0 0.85rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-gray-200, #e2e8f0);
}

.section-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.85rem;
}

.badge-count {
  font-size: 0.75rem;
  background: rgba(255, 255, 255, 0.1);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  color: var(--color-gray-300, #cbd5e1);
}

.prize-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.5rem;
}

.prize-item {
  background: rgba(15, 23, 42, 0.6);
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.prize-name {
  font-size: 0.75rem;
  color: var(--color-gray-400, #94a3b8);
}

.prize-count {
  font-size: 1rem;
  color: #fff;
}

.targets-table-wrapper {
  max-height: 280px;
  overflow-y: auto;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
}

.targets-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.targets-table th,
.targets-table td {
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  text-align: left;
}

.targets-table th {
  background: #111827;
  position: sticky;
  top: 0;
  z-index: 1;
}

.number-chips {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.2rem;
}

.num-chip {
  display: inline-block;
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
  background: rgba(6, 182, 212, 0.15);
  color: var(--color-cyan-300, #67e8f9);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.num-chip--actual {
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-gray-200, #e2e8f0);
}

.num-chip--special {
  background: rgba(244, 114, 182, 0.15);
  color: var(--color-pink-300, #f472b6);
}

.hits-tag {
  font-weight: 600;
  color: var(--color-gray-300, #cbd5e1);
}

.hits-tag--win {
  color: var(--color-emerald-400, #34d399);
}

.prize-tag {
  background: rgba(251, 191, 36, 0.15);
  color: var(--color-amber-300, #fcd34d);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
}

.details-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.loading-box,
.empty-box,
.error-box {
  padding: 1.5rem;
  text-align: center;
  font-size: 0.85rem;
}

.error-box {
  color: var(--color-rose-400, #fb7185);
}

.text-muted {
  color: var(--color-gray-400, #94a3b8);
}
</style>
