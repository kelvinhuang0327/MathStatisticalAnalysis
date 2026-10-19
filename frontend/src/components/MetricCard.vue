<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string | number
    subvalue?: string
    badge?: string
    badgeVariant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'accent'
    variant?: 'default' | 'accent' | 'success' | 'warning' | 'danger' | 'info'
    icon?: string
  }>(),
  {
    subvalue: undefined,
    badge: undefined,
    badgeVariant: 'default',
    variant: 'default',
    icon: undefined,
  },
)
</script>

<template>
  <div class="metric-card" :class="`metric-card--${variant}`">
    <div class="metric-card__header">
      <span class="metric-card__label">{{ label }}</span>
      <span
        v-if="badge"
        class="metric-card__badge"
        :class="`metric-card__badge--${badgeVariant}`"
      >
        {{ badge }}
      </span>
      <span v-else-if="icon" class="metric-card__icon" aria-hidden="true">{{ icon }}</span>
    </div>
    <div class="metric-card__body">
      <strong class="metric-card__value">{{ value }}</strong>
      <small v-if="subvalue" class="metric-card__subvalue">{{ subvalue }}</small>
    </div>
    <div v-if="$slots.default" class="metric-card__extra">
      <slot />
    </div>
  </div>
</template>
