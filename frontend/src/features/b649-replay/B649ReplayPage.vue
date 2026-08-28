<script setup lang="ts">
import { ref } from 'vue'

import B649MultiTicketRecordsPage from '../b649-multi-ticket-records/B649MultiTicketRecordsPage.vue'
import B649OwnerRankingPage from '../b649-owner-ranking/B649OwnerRankingPage.vue'
import SectionHeader from '../../components/SectionHeader.vue'

type Tab = 'records' | 'ranking'
const activeTab = ref<Tab>('records')
</script>

<template>
  <section class="workspace-page" aria-labelledby="b649-replay-title">
    <SectionHeader
      id="b649-replay-title"
      title="B649 Replay"
      eyebrow="Canonical Game Replay Explorer"
      description="Multi-strategy, multi-ticket-count, and multi-horizon replay explorer and historical records for B649."
    >
      <template #actions>
        <div class="tab-list" role="tablist" aria-label="B649 Replay Sections">
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeTab === 'records', 'button--quiet': activeTab !== 'records' }"
            :aria-pressed="activeTab === 'records'"
            @click="activeTab = 'records'"
          >
            Multi-Ticket Records
          </button>
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeTab === 'ranking', 'button--quiet': activeTab !== 'ranking' }"
            :aria-pressed="activeTab === 'ranking'"
            @click="activeTab = 'ranking'"
          >
            Owner Ranking
          </button>
        </div>
      </template>
    </SectionHeader>

    <div v-if="activeTab === 'records'">
      <B649MultiTicketRecordsPage />
    </div>
    <div v-else>
      <B649OwnerRankingPage />
    </div>
  </section>
</template>
