<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    eyebrow?: string
    description?: string
    stepLabel?: string
  }>(),
  {
    eyebrow: undefined,
    description: undefined,
    stepLabel: undefined,
  },
)
</script>

<template>
  <header class="section-header">
    <div class="section-header__content">
      <p v-if="stepLabel" class="section-header__step">{{ stepLabel }}</p>
      <p v-else-if="eyebrow" class="section-header__eyebrow">{{ eyebrow }}</p>
      <h2 class="section-header__title">{{ title }}</h2>
      <p v-if="description" class="section-header__desc">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="section-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>
