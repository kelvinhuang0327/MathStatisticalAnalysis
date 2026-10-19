<script setup lang="ts">
import SectionHeader from '../../components/SectionHeader.vue'
import MetricCard from '../../components/MetricCard.vue'
</script>

<template>
  <section class="workspace-page" aria-labelledby="future-modules-title">
    <SectionHeader
      id="future-modules-title"
      title="Future Modules"
      eyebrow="Extensibility & Roadmap"
      description="LottoLab quantitative research system extensions and upcoming analytical modules."
    >
      <template #actions>
        <span class="status-badge status-badge--neutral">DEVELOPMENT ROADMAP</span>
      </template>
    </SectionHeader>

    <div class="metrics-grid">
      <MetricCard
        label="Automated Exploration"
        value="AutoML"
        subvalue="Genetic strategy mutation & feature discovery"
        variant="accent"
      />
      <MetricCard
        label="Ensemble Engine"
        value="Unified"
        subvalue="Multi-strategy cross-validation blending"
      />
      <MetricCard
        label="Live Zone Split"
        value="Target Contract"
        subvalue="Zone-based partition evaluation"
      />
      <MetricCard
        label="Data Governance"
        value="Audit SSOT"
        subvalue="Immutable draw snapshots & checksum registries"
        variant="success"
      />
    </div>

    <article class="panel" style="margin-top: 24px">
      <div class="panel__heading">
        <div>
          <p class="step-label">Modular Architecture</p>
          <h2>Standardized Extensibility Pipeline</h2>
        </div>
      </div>
      <p class="page-intro" style="margin-top: 12px">
        All subsequent quantitative modules follow the strict lifecycle: Idea → Simulation → Backtest →
        Validation → Genetic Evolution → Ensemble → Re-evaluate. Future modules connect seamlessly
        without altering the core application shell.
      </p>
    </article>
  </section>
</template>
