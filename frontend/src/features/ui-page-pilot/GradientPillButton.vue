<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    label: string
    disabled?: boolean
    loading?: boolean
    loadingLabel?: string
  }>(),
  {
    disabled: false,
    loading: false,
    loadingLabel: undefined,
  },
)

const emit = defineEmits<{
  (e: 'click'): void
}>()

function handleClick(): void {
  // Guard explicitly rather than relying only on the native `disabled`
  // attribute: this is what actually makes "no duplicate emit while
  // loading" hold regardless of how the click was dispatched.
  if (props.disabled || props.loading) return
  emit('click')
}
</script>

<template>
  <button
    type="button"
    class="gradient-pill-button"
    :disabled="disabled || loading"
    :aria-busy="loading"
    @click="handleClick"
  >
    <span v-if="loading" class="gradient-pill-button__spinner" aria-hidden="true" />
    <span class="gradient-pill-button__label">{{ loading && loadingLabel ? loadingLabel : label }}</span>
    <svg
      v-if="!loading"
      class="gradient-pill-button__icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  </button>
</template>

<style scoped>
/*
 * Visual language adapted from MengTo/threeui @
 * 68802d5428071ada5c20db8094b1649e6bb770ed
 * src/shaders/neuform-isolated/sources/gradient-pill-button.html (MIT,
 * Copyright (c) 2026 Meng To): pill shape, layered soft elevation, a
 * gradient fill, and a thin gradient-toned ring border. Colors below are
 * this app's own design tokens, not the source's light-mode values. Full
 * provenance: threeui-vue-page/references/THREEUI_VUE_ADAPTATION.md in the
 * skill repository.
 */
.gradient-pill-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  border: none;
  border-radius: var(--radius-full);
  background: var(--gradient-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: -0.01em;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(124, 58, 237, 0.35);
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
}

.gradient-pill-button::before {
  content: '';
  position: absolute;
  inset: 0;
  padding: 1px;
  border-radius: inherit;
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.7),
    rgba(255, 255, 255, 0.05) 40%,
    rgba(0, 0, 0, 0.25)
  );
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.gradient-pill-button:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(124, 58, 237, 0.5);
}

.gradient-pill-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  box-shadow: none;
}

.gradient-pill-button:focus-visible {
  outline: 3px solid rgba(139, 92, 246, 0.45);
  outline-offset: 2px;
}

.gradient-pill-button__icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.gradient-pill-button__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: gradient-pill-button-spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes gradient-pill-button-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .gradient-pill-button,
  .gradient-pill-button__spinner {
    transition: none;
    animation-duration: 0.001ms;
  }
}
</style>
