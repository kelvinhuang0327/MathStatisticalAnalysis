<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: 'card' | 'table' | 'text'
    rows?: number
    height?: string
  }>(),
  {
    type: 'card',
    rows: 3,
    height: undefined,
  },
)
</script>

<template>
  <div class="skeleton-loader" :class="`skeleton-loader--${type}`" aria-busy="true" aria-label="Loading content">
    <template v-if="type === 'card'">
      <div v-for="i in rows" :key="i" class="skeleton-card" :style="{ height: height }">
        <div class="skeleton-shimmer" />
      </div>
    </template>
    <template v-else-if="type === 'table'">
      <div v-for="i in rows" :key="i" class="skeleton-row" :style="{ height: height || '40px' }">
        <div class="skeleton-shimmer" />
      </div>
    </template>
    <template v-else>
      <div v-for="i in rows" :key="i" class="skeleton-text" :style="{ height: height || '18px' }">
        <div class="skeleton-shimmer" />
      </div>
    </template>
  </div>
</template>
