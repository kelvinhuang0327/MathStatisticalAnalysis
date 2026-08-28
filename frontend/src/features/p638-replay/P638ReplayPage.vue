<script setup lang="ts">
import { ref } from 'vue'

import P638HistoricalReplayPage from '../p638-historical-replay/P638HistoricalReplayPage.vue'
import P638StrategyAnalysisPage from '../p638-strategy-analysis/P638StrategyAnalysisPage.vue'
import SectionHeader from '../../components/SectionHeader.vue'

type Tab = 'replay' | 'analysis'
const activeTab = ref<Tab>('replay')
</script>

<template>
  <section class="workspace-page" aria-labelledby="p638-replay-title">
    <SectionHeader
      id="p638-replay-title"
      title="P638 Replay"
      eyebrow="Canonical Game Replay Explorer"
      description="Multi-strategy and multi-horizon replay explorer and historical strategy performance analysis for P638 (Power Lotto)."
    >
      <template #actions>
        <div class="tab-list" role="tablist" aria-label="P638 Replay Sections">
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeTab === 'replay', 'button--quiet': activeTab !== 'replay' }"
            :aria-pressed="activeTab === 'replay'"
            @click="activeTab = 'replay'"
          >
            Replay Explorer
          </button>
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeTab === 'analysis', 'button--quiet': activeTab !== 'analysis' }"
            :aria-pressed="activeTab === 'analysis'"
            @click="activeTab = 'analysis'"
          >
            Strategy Analysis
          </button>
        </div>
      </template>
    </SectionHeader>

    <div v-if="activeTab === 'replay'">
      <P638HistoricalReplayPage />
    </div>
    <div v-else>
      <P638StrategyAnalysisPage />
    </div>
  </section>
</template>
