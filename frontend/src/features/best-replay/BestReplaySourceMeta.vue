<script setup lang="ts">
import { computed } from 'vue'

import type { BestReplayItem } from './types'

const props = defineProps<{ item: BestReplayItem }>()

const sourceIdentity = computed(() => {
  if (props.item.legacyMethodId) return `Source identity: ${props.item.legacyMethodId}`
  if (props.item.sourceRunId) return `Source run: ${props.item.sourceRunId}`
  return ''
})
</script>

<template>
  <small v-if="sourceIdentity" class="source-evidence">{{ sourceIdentity }}</small>
  <small v-if="item.sourceCompletedAt" class="source-evidence">
    Source completed: {{ item.sourceCompletedAt }}
  </small>
  <small v-if="item.sourceAsOfDate" class="source-evidence">
    Source as of: {{ item.sourceAsOfDate }}
  </small>
</template>

<style scoped>
.source-evidence {
  display: block;
  color: var(--text-muted, #64748b);
  font-size: 0.7rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
</style>
