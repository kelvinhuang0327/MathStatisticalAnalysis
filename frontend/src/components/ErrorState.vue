<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    message: string
    retryable?: boolean
    retryLabel?: string
  }>(),
  {
    title: 'An error occurred',
    retryable: true,
    retryLabel: 'Retry',
  },
)

const emit = defineEmits<{
  (e: 'retry'): void
}>()
</script>

<template>
  <div class="error-state" role="alert">
    <div class="error-state__icon" aria-hidden="true">⚠️</div>
    <div class="error-state__content">
      <h3 class="error-state__title">{{ title }}</h3>
      <p class="error-state__message">{{ message }}</p>
    </div>
    <div v-if="retryable || $slots.actions" class="error-state__actions">
      <button
        v-if="retryable"
        type="button"
        class="button button--danger"
        @click="emit('retry')"
      >
        {{ retryLabel }}
      </button>
      <slot name="actions" />
    </div>
  </div>
</template>
