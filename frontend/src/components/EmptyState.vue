<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    description?: string
    icon?: string
  }>(),
  {
    title: 'No data available',
    description: 'There are no records matching your current filter or configuration.',
    icon: '📊',
  },
)
</script>

<template>
  <div class="empty-state">
    <div class="empty-state__icon" aria-hidden="true">{{ icon }}</div>
    <h3 class="empty-state__title">{{ title }}</h3>
    <p class="empty-state__desc">{{ description }}</p>
    <div v-if="$slots.default" class="empty-state__actions">
      <slot />
    </div>
  </div>
</template>
