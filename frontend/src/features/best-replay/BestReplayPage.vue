<script setup lang="ts">
import SectionHeader from '../../components/SectionHeader.vue'
import MetricCard from '../../components/MetricCard.vue'
</script>

<template>
  <section class="workspace-page" aria-labelledby="best-replay-title">
    <SectionHeader
      id="best-replay-title"
      title="Best Replay"
      eyebrow="Multi-ticket horizon ranking"
      description="Strategy ranking and ticket performance comparison across 1–20 tickets and short, medium, long, and full evaluation horizons."
    >
      <template #actions>
        <span class="status-badge status-badge--neutral">READ-ONLY CONTRACT</span>
      </template>
    </SectionHeader>

    <div class="metrics-grid">
      <MetricCard
        label="Ticket Horizons"
        value="1 – 20"
        subvalue="Configurable ticket counts"
        variant="accent"
      />
      <MetricCard
        label="Evaluation Windows"
        value="4 Windows"
        subvalue="Short (50) · Medium (300) · Long (750) · Full"
      />
      <MetricCard
        label="Ranking Model"
        value="SSOT"
        subvalue="Evidence-based ranking without metric synthesis"
      />
      <MetricCard
        label="Evidence Guard"
        value="Active"
        subvalue="Strict out-of-sample statistical validation"
        variant="success"
      />
    </div>

    <article class="panel" style="margin-top: 24px">
      <div class="panel__heading">
        <div>
          <p class="step-label">Architecture Contract</p>
          <h2>Planned Multi-Horizon Best Replay Engine</h2>
        </div>
      </div>
      <p class="page-intro" style="margin-top: 12px">
        Best Replay analyzes multi-ticket strategies (1 to 20 tickets) across distinct observation
        windows (recent 50, recent 300, recent 750, and full history). It incorporates official prize
        distributions, evidence strength warnings, and random-baseline lifts.
      </p>
      <div class="notice-row" style="margin-top: 16px">
        <span>
          Future module preview: Underlying ranking algorithms and multi-horizon replay matrices
          will be connected in upcoming releases under strict statistical validation guidelines.
        </span>
      </div>
    </article>
  </section>
</template>
