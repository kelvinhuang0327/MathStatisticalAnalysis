<script setup lang="ts">
import { ref } from 'vue'

import StrategyCatalogPage from '../strategy-catalog/StrategyCatalogPage.vue'
import StrategyEvidencePage from '../strategy-evidence/StrategyEvidencePage.vue'
import SectionHeader from '../../components/SectionHeader.vue'

type Tab = 'overview' | 'portfolio' | 'd3'

const activeTab = ref<Tab>('overview')
</script>

<template>
  <section class="workspace-page" aria-labelledby="strategy-intelligence-title">
    <SectionHeader
      id="strategy-intelligence-title"
      title="Strategy Intelligence"
      eyebrow="Quantitative Strategy Discovery & Validation"
      description="Unified strategy catalog, portfolio hit rate evaluation, and canonical D3 Single Source of Truth validation gates."
    >
      <template #actions>
        <div class="tab-list" role="tablist" aria-label="Strategy Intelligence Sections">
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeTab === 'overview', 'button--quiet': activeTab !== 'overview' }"
            :aria-pressed="activeTab === 'overview'"
            @click="activeTab = 'overview'"
          >
            Overview
          </button>
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeTab === 'portfolio', 'button--quiet': activeTab !== 'portfolio' }"
            :aria-pressed="activeTab === 'portfolio'"
            @click="activeTab = 'portfolio'"
          >
            Portfolio Hit Rate
          </button>
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeTab === 'd3', 'button--quiet': activeTab !== 'd3' }"
            :aria-pressed="activeTab === 'd3'"
            @click="activeTab = 'd3'"
          >
            D3 SSOT
          </button>
        </div>
      </template>
    </SectionHeader>

    <div v-if="activeTab === 'overview'">
      <StrategyCatalogPage />
    </div>
    <div v-else-if="activeTab === 'portfolio'">
      <StrategyEvidencePage />
    </div>
    <div v-else-if="activeTab === 'd3'">
      <StrategyEvidencePage />
    </div>
  </section>
</template>
