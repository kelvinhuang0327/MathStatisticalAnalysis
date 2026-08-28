<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    count?: number
    countLabel?: string
  }>(),
  {
    title: undefined,
    count: undefined,
    countLabel: 'items',
  },
)
</script>

<template>
  <div class="filter-bar">
    <div v-if="title || count !== undefined" class="filter-bar__header">
      <h3 v-if="title" class="filter-bar__title">{{ title }}</h3>
      <span v-if="count !== undefined" class="filter-bar__count">
        {{ count }} {{ countLabel }}
      </span>
    </div>
    <div class="filter-bar__controls">
      <div class="filter-bar__inputs">
        <slot />
      </div>
      <div v-if="$slots.actions" class="filter-bar__actions">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>
