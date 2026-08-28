<script setup lang="ts">
import DataTable from '../../components/DataTable.vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionHeader from '../../components/SectionHeader.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type { D3MetricDefinitionInfo, StrategyCombinedItem } from './types'

const props = withDefaults(
  defineProps<{
    d3Status?: string
    d3Value?: string
    strategies?: StrategyCombinedItem[]
  }>(),
  {
    d3Status: 'RESERVED_UNAVAILABLE',
    d3Value: 'NOT_AVAILABLE',
    strategies: () => [],
  },
)

const d3Definition: D3MetricDefinitionInfo = {
  metricId: 'D3',
  metricVersion: 'v1',
  schemaId: 'lottolab.evidence.metric_definition',
  schemaVersion: '1.0.0',
  formulaStatus: 'RESERVED_UNAVAILABLE',
  direction: 'DESCRIPTIVE_ONLY',
  aggregation: 'NONE',
  sampleUnit: 'DRAWS',
  decimalScale: 4,
  roundingMode: 'ROUND_HALF_EVEN',
  unit: 'UNITLESS',
  definitionProse:
    'D3 is reserved for a future Owner-approved primary ranking metric. No formula, threshold, or ranking direction is committed by this task. Any result declaring VALUE_PRESENT against this definition is a METRIC_DEFINITION_FAILURE.',
  authorityPath: 'contracts/evidence/metric_definitions/d3.json',
}
</script>

<template>
  <div class="strategy-d3-workspace">
    <!-- D3 Authority Header Panel -->
    <article class="panel d3-authority-panel" aria-labelledby="d3-ssot-title">
      <div class="panel__heading">
        <div>
          <p class="step-label">Single Source of Truth · Metric Authority</p>
          <h2 id="d3-ssot-title">D3 Strategy Status & SSOT Definition</h2>
        </div>
        <div class="scope-card" aria-label="D3 SSOT status">
          <span>D3 SSOT Status</span>
          <strong>{{ d3Status }}</strong>
          <small>Value: {{ d3Value }} · Authority: {{ d3Definition.authorityPath }}</small>
        </div>
      </div>

      <p class="d3-intro">
        D3 serves as the canonical primary ranking authority for the strategy discovery platform.
        Per the committed schema contract, its formula and evaluation values remain explicitly reserved until an Owner-approved definition is ratified.
      </p>

      <!-- Authority Summary Metrics -->
      <div class="metrics-grid">
        <MetricCard
          label="D3 SSOT Status"
          :value="d3Status"
          subvalue="Formula status: RESERVED_UNAVAILABLE"
          variant="warning"
          badge="SSOT AUTHORITY"
          badge-variant="warning"
        />
        <MetricCard
          label="Canonical Value"
          :value="d3Value"
          subvalue="Unavailable is never rendered as 0"
          variant="default"
        />
        <MetricCard
          label="Metric Authority"
          :value="`${d3Definition.metricId} (${d3Definition.metricVersion})`"
          :subvalue="d3Definition.schemaId"
          variant="accent"
        />
        <MetricCard
          label="Direction & Aggregation"
          :value="d3Definition.direction"
          :subvalue="`Aggregation: ${d3Definition.aggregation} · Unit: ${d3Definition.unit}`"
          variant="default"
        />
      </div>
    </article>

    <!-- Authoritative Prose Block -->
    <div class="d3-prose-card" role="region" aria-labelledby="d3-prose-title">
      <div class="prose-header">
        <span class="prose-icon" aria-hidden="true">📜</span>
        <div>
          <h3 id="d3-prose-title" class="prose-title">Committed Definition Prose</h3>
          <code class="prose-source">{{ d3Definition.authorityPath }}</code>
        </div>
      </div>
      <blockquote class="prose-quote">
        "{{ d3Definition.definitionProse }}"
      </blockquote>
    </div>

    <!-- Strategy-Level D3 Evidence Status Table -->
    <SectionHeader
      title="Per-Strategy D3 Evaluation Status"
      eyebrow="Canonical Verification Gate"
      description="Strategy-by-strategy D3 availability, verification state, and empirical eligibility flags."
    />

    <DataTable
      caption="Per-Strategy D3 SSOT Verification"
      min-width="1000px"
    >
      <template #head>
        <tr>
          <th>Strategy</th>
          <th>Version</th>
          <th>Lifecycle</th>
          <th>D3 Status</th>
          <th>D3 Value</th>
          <th>Verification State</th>
          <th>Empirical Eligibility</th>
          <th>Authority Source</th>
          <th>Blocked / Unavailable Reason</th>
        </tr>
      </template>

      <tr
        v-for="strategy in strategies"
        :key="strategy.strategyId"
        class="data-row"
      >
        <td>
          <div class="strategy-cell">
            <strong class="strategy-name">{{ strategy.displayName }}</strong>
            <code class="strategy-id">{{ strategy.strategyId }}</code>
          </div>
        </td>
        <td>
          <span class="version-tag">{{ strategy.version }}</span>
        </td>
        <td>
          <StatusBadge :status="strategy.lifecycleStatus" size="sm" />
        </td>
        <td>
          <StatusBadge :status="d3Status" variant="warning" size="sm" />
        </td>
        <td class="font-mono">
          <span class="text-muted">{{ d3Value }}</span>
        </td>
        <td>
          <StatusBadge :status="strategy.verificationStatus" size="sm" />
        </td>
        <td>
          <StatusBadge :status="strategy.empiricalEligibility" size="sm" />
        </td>
        <td>
          <code class="source-path">{{ d3Definition.authorityPath }}</code>
        </td>
        <td>
          <span class="reason-text">
            {{ strategy.unavailableReasonCode ?? 'D3 metric definition formula is RESERVED_UNAVAILABLE.' }}
          </span>
        </td>
      </tr>
    </DataTable>
  </div>
</template>

<style scoped>
.strategy-d3-workspace {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.d3-authority-panel {
  padding: 24px;
}

.d3-intro {
  margin: 0 0 16px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
  max-width: 800px;
}

.d3-prose-card {
  padding: 20px 24px;
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(28, 20, 48, 0.75) 0%, rgba(13, 17, 28, 0.75) 100%);
  box-shadow: var(--shadow-sm);
}

.prose-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.prose-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.prose-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.prose-source {
  font-size: 11px;
  color: var(--text-accent);
  font-family: var(--font-mono);
}

.prose-quote {
  margin: 0;
  padding: 12px 16px;
  border-left: 3px solid var(--primary-color);
  background: rgba(10, 14, 24, 0.6);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  color: var(--text-primary);
  font-size: 13.5px;
  font-style: italic;
  line-height: 1.6;
}

.strategy-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.strategy-name {
  color: var(--text-primary);
  font-size: 13px;
}

.strategy-id {
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

.source-path {
  font-size: 10px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.reason-text {
  font-size: 11.5px;
  color: var(--text-secondary);
}

.text-muted {
  color: var(--text-tertiary);
}
</style>
