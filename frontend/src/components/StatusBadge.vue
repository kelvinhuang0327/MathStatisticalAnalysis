<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    status: string
    variant?: 'auto' | 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'accent'
    size?: 'sm' | 'md'
    dot?: boolean
  }>(),
  {
    variant: 'auto',
    size: 'sm',
    dot: true,
  },
)

const resolvedVariant = computed(() => {
  if (props.variant !== 'auto') return props.variant
  const s = props.status.toUpperCase()
  if (['VALID', 'SUCCESS', 'IMPORTED', 'ACCEPTED', 'COMPLETE', 'ONLINE', 'READY', 'BACKTESTED'].includes(s)) {
    return 'success'
  }
  if (['PARTIAL', 'PARTIAL_SUCCESS', 'DUPLICATE', 'OBSERVATION', 'WARNING', 'RECENT_MOVER'].includes(s)) {
    return 'warning'
  }
  if (['FAILED', 'CONFLICTED', 'CONFLICT', 'ERROR', 'INVALID', 'REJECTED', 'CLOSED_UNEXECUTABLE'].includes(s)) {
    return 'danger'
  }
  if (['READING', 'PREVIEWING', 'COMMITTING', 'RUNNING'].includes(s)) {
    return 'info'
  }
  return 'neutral'
})
</script>

<template>
  <span
    class="status-badge"
    :class="[`status-badge--${resolvedVariant}`, `status-badge--${size}`]"
    :data-testid="`status-badge-${status.toLowerCase().replace(/[^a-z0-9]/g, '-')}`"
  >
    <span v-if="dot" class="status-badge__dot" aria-hidden="true" />
    <span class="status-badge__label">{{ status }}</span>
  </span>
</template>
