<script setup lang="ts">
import { computed } from 'vue'

import DataTable from '../../components/DataTable.vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionHeader from '../../components/SectionHeader.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type { PortfolioGameEvidenceRow, StrategyCombinedItem } from './types'

const props = withDefaults(
  defineProps<{
    combinationStatus?: string
    combinationValue?: string
    combinationOwner?: string
    strategies?: StrategyCombinedItem[]
  }>(),
  {
    combinationStatus: 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE',
    combinationValue: 'NOT_AVAILABLE',
    combinationOwner: 'ACTIVE_MULTITICKET_AGENT',
    strategies: () => [],
  },
)

const canonicalGames: PortfolioGameEvidenceRow[] = [
  {
    game: 'B649',
    gameName: 'Big Lotto 6/49',
    portfolioId: null,
    includedStrategies: [],
    portfolioSize: null,
    evaluatedTargets: null,
    unionHitRate: null,
    bestComparator: null,
    marginalContribution: null,
    diversityMetric: null,
    horizon: null,
    evidenceStatus: 'EVIDENCE UNAVAILABLE',
    reasonCode: 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE',
  },
  {
    game: 'P638',
    gameName: 'Power Lotto 6/38',
    portfolioId: null,
    includedStrategies: [],
    portfolioSize: null,
    evaluatedTargets: null,
    unionHitRate: null,
    bestComparator: null,
    marginalContribution: null,
    diversityMetric: null,
    horizon: null,
    evidenceStatus: 'EVIDENCE UNAVAILABLE',
    reasonCode: 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE',
  },
  {
    game: 'T539',
    gameName: 'Daily Cash 5/39',
    portfolioId: null,
    includedStrategies: [],
    portfolioSize: null,
    evaluatedTargets: null,
    unionHitRate: null,
    bestComparator: null,
    marginalContribution: null,
    diversityMetric: null,
    horizon: null,
    evidenceStatus: 'EVIDENCE UNAVAILABLE',
    reasonCode: 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE',
  },
]

const totalCandidateStrategies = computed(() => props.strategies.length)
</script>

<template>
  <div class="strategy-portfolio-workspace">
    <!-- Top Status & Governance Banner -->
    <div class="portfolio-governance-panel">
      <div class="governance-header">
        <div>
          <p class="step-label">Strategy Combination Hit Rate · Evidence Boundary</p>
          <h2>Combination & Portfolio Evidence Status</h2>
          <p class="governance-desc">
            Multi-strategy combination evaluation answers: <em>"What is known about combining strategies?"</em>.
            Currently, no canonical portfolio hit rate has been registered in the evidence registry.
          </p>
        </div>
        <div class="scope-card" aria-label="Portfolio evidence status">
          <span>Combination status</span>
          <strong>{{ combinationStatus }}</strong>
          <small>Value: {{ combinationValue }} · Owner: {{ combinationOwner }}</small>
        </div>
      </div>

      <div class="metrics-grid">
        <MetricCard
          label="Portfolio Hit Rate"
          value="UNAVAILABLE"
          subvalue="No registered combination metrics"
          variant="warning"
          badge="NOT_AVAILABLE"
          badge-variant="warning"
        />
        <MetricCard
          label="Active Governance"
          :value="combinationOwner"
          subvalue="Active multi-ticket research scope"
          variant="default"
        />
        <MetricCard
          label="Evaluated Portfolios"
          value="0"
          subvalue="0 registered combination artifacts"
          variant="default"
        />
        <MetricCard
          label="Candidate Pool"
          :value="totalCandidateStrategies"
          subvalue="Individual catalog strategies"
          variant="accent"
        />
      </div>
    </div>

    <!-- Research Protocol Guard Banner -->
    <div class="research-guard-banner" role="note">
      <span class="guard-icon" aria-hidden="true">🔒</span>
      <div class="guard-content">
        <strong>Strict Quantitative Guard:</strong>
        Combinatorial and multi-strategy hit rates cannot be derived from isolated single-strategy summary numbers.
        No portfolio optimization formula or oracle selector is synthesized without frozen canonical artifacts.
        Missing portfolio metrics are displayed explicitly as <code>UNAVAILABLE</code> rather than zero.
      </div>
    </div>

    <!-- Game-by-Game Canonical Evidence Grid -->
    <SectionHeader
      title="Canonical Game Evidence Status"
      eyebrow="Game-Specific Breakdown"
      description="Portfolio hit rate and combination evidence availability across canonical supported lottery games."
    />

    <DataTable
      caption="Portfolio Evidence Availability by Game"
      min-width="1000px"
    >
      <template #head>
        <tr>
          <th>Game</th>
          <th>Portfolio ID</th>
          <th>Included Strategies</th>
          <th>Size</th>
          <th>Evaluated Targets</th>
          <th>Union Hit Rate</th>
          <th>Best Comparator</th>
          <th>Marginal Contribution</th>
          <th>Diversity Metric</th>
          <th>Evidence Status</th>
        </tr>
      </template>

      <tr v-for="row in canonicalGames" :key="row.game" class="data-row">
        <td>
          <div class="game-cell">
            <span class="game-tag">{{ row.game }}</span>
            <small class="game-full-name">{{ row.gameName }}</small>
          </div>
        </td>
        <td>
          <span class="text-muted">{{ row.portfolioId ?? 'None' }}</span>
        </td>
        <td>
          <span class="text-muted">
            {{ row.includedStrategies.length ? row.includedStrategies.join(', ') : 'None registered' }}
          </span>
        </td>
        <td class="font-mono">
          <span class="text-muted">{{ row.portfolioSize ?? '—' }}</span>
        </td>
        <td class="font-mono">
          <span class="text-muted">{{ row.evaluatedTargets ?? '—' }}</span>
        </td>
        <td class="font-mono">
          <strong class="text-muted">{{ row.unionHitRate ?? 'UNAVAILABLE' }}</strong>
        </td>
        <td class="font-mono">
          <span class="text-muted">{{ row.bestComparator ?? 'UNAVAILABLE' }}</span>
        </td>
        <td class="font-mono">
          <span class="text-muted">{{ row.marginalContribution ?? 'UNAVAILABLE' }}</span>
        </td>
        <td class="font-mono">
          <span class="text-muted">{{ row.diversityMetric ?? 'UNAVAILABLE' }}</span>
        </td>
        <td>
          <div class="status-cell">
            <StatusBadge :status="row.evidenceStatus" variant="warning" size="sm" />
            <code class="status-reason">{{ row.reasonCode }}</code>
          </div>
        </td>
      </tr>
    </DataTable>

    <!-- Detailed Evidence Registry Explanatory Section -->
    <article class="panel registry-details-panel">
      <div class="panel__heading">
        <p class="step-label">Evidence Registry Specification</p>
        <h3>Why is Portfolio Hit Rate Unavailable?</h3>
      </div>
      <div class="registry-reasons">
        <div class="reason-card">
          <h4>01 · Canonical Evidence Registry is Empty</h4>
          <p>
            The committed evidence registry (<code>contracts/evidence/canonical_evidence_registry.json</code>)
            currently contains zero registered multi-strategy combination artifacts.
          </p>
        </div>
        <div class="reason-card">
          <h4>02 · No Optimization Policy Synthesis</h4>
          <p>
            The system forbids generating unverified optimization policies or computing heuristic combinations
            without frozen ranking artifacts.
          </p>
        </div>
        <div class="reason-card">
          <h4>03 · Replay History is Non-Ex-Ante</h4>
          <p>
            Post-hoc replay ranking artifacts are descriptive historical records and are not converted into forward
            portfolio hit-rate claims.
          </p>
        </div>
      </div>
    </article>
  </div>
</template>

<style scoped>
.strategy-portfolio-workspace {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.portfolio-governance-panel {
  padding: 24px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  background: var(--bg-card);
  backdrop-filter: blur(18px);
  box-shadow: var(--shadow-md);
}

.governance-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}

.governance-header h2 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
}

.governance-desc {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.5;
  max-width: 720px;
}

.research-guard-banner {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 20px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(35, 20, 50, 0.7) 0%, rgba(13, 17, 28, 0.7) 100%);
  border: 1px solid rgba(139, 92, 246, 0.3);
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.55;
}

.guard-icon {
  font-size: 20px;
  flex-shrink: 0;
  margin-top: 1px;
}

.guard-content strong {
  color: var(--text-primary);
  display: inline;
  margin-right: 4px;
}

.guard-content code {
  color: var(--text-accent);
}

.game-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.game-tag {
  display: inline-block;
  padding: 3px 6px;
  border-radius: var(--radius-sm);
  background: rgba(56, 189, 248, 0.12);
  border: 1px solid rgba(56, 189, 248, 0.25);
  color: #38bdf8;
  font: 700 10.5px/1 var(--font-mono);
  width: fit-content;
}

.game-full-name {
  color: var(--text-secondary);
  font-size: 11px;
}

.status-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-reason {
  font-size: 9.5px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}

.registry-details-panel {
  margin-top: 8px;
}

.registry-reasons {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.reason-card {
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: rgba(12, 17, 28, 0.6);
}

.reason-card h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.reason-card p {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.reason-card code {
  color: var(--text-accent);
}

.text-muted {
  color: var(--text-tertiary);
}
</style>
