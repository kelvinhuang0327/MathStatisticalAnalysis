<script setup lang="ts">
import { computed } from 'vue'

export type BallVariant =
  | 'main'
  | 'special'
  | 'hit'
  | 'miss'
  | 'selected'
  | 'disabled'
  | 'MAIN'
  | 'SPECIAL'
  | 'HIT'
  | 'MISS'
  | 'SELECTED'
  | 'DISABLED'

export type BallSize = 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    value: number | string
    variant?: BallVariant
    isSpecial?: boolean
    isHit?: boolean
    isSelected?: boolean
    isDisabled?: boolean
    size?: BallSize
    subtext?: string
    ariaLabel?: string
  }>(),
  {
    variant: 'main',
    isSpecial: false,
    isHit: false,
    isSelected: false,
    isDisabled: false,
    size: 'md',
    subtext: undefined,
    ariaLabel: undefined,
  },
)

const normalizedVariant = computed(() => {
  const v = props.variant.toLowerCase()
  if (props.isDisabled || v === 'disabled') return 'disabled'
  if (props.isSelected || v === 'selected') return 'selected'
  if (props.isHit || v === 'hit') return 'hit'
  if (v === 'miss') return 'miss'
  if (props.isSpecial || v === 'special') return 'special'
  return 'main'
})

const isSpecialBase = computed(() => {
  const v = props.variant.toLowerCase()
  return props.isSpecial || v === 'special'
})

const accessibleLabel = computed(() => {
  if (props.ariaLabel) return props.ariaLabel
  const typeStr = isSpecialBase.value ? 'Special Number' : 'Number'
  const state = normalizedVariant.value
  const stateStr =
    state === 'hit'
      ? ' (Hit)'
      : state === 'miss'
        ? ' (Miss)'
        : state === 'selected'
          ? ' (Selected)'
          : state === 'disabled'
            ? ' (Unavailable)'
            : ''
  return `${typeStr} ${props.value}${stateStr}`
})

const formattedValue = computed(() => {
  return String(props.value)
})
</script>

<template>
  <div
    class="lottery-number-ball number-chip"
    :class="[
      `ball--${normalizedVariant}`,
      `ball--size-${size}`,
      { 'ball--special-base': isSpecialBase },
    ]"
    :aria-label="accessibleLabel"
    :aria-disabled="normalizedVariant === 'disabled' ? 'true' : undefined"
    :data-state="normalizedVariant"
    role="img"
    :data-testid="`lottery-ball-${value}`"
  >
    <!-- Soft 3D lighting reflection -->
    <span class="ball__shine" aria-hidden="true" />

    <!-- Hit / Win indicator dot / badge if hit -->
    <span v-if="normalizedVariant === 'hit'" class="ball__hit-badge" aria-hidden="true">★</span>

    <!-- Miss indicator keeps the state legible without relying on color alone -->
    <span v-if="normalizedVariant === 'miss'" class="ball__miss-badge" aria-hidden="true">×</span>

    <!-- Value text -->
    <span class="ball__value">{{ formattedValue }}</span>

    <!-- Optional subtext / badge (e.g. Z2) -->
    <span v-if="subtext" class="ball__subtext">{{ subtext }}</span>
  </div>
</template>

<style scoped>
.lottery-number-ball {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 0;
  font-family: var(--font-primary, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  font-weight: 900;
  color: #ffffff;
  border-radius: var(--radius-md, 10px);
  user-select: none;
  flex-shrink: 0;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-sizing: border-box;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
  font-variant-numeric: tabular-nums;
}

/* 3D specular highlight effect matching legacy donor */
.ball__shine {
  position: absolute;
  top: 12%;
  left: 20%;
  width: 36%;
  height: 24%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.55), transparent 70%);
  border-radius: 50%;
  filter: blur(2px);
  pointer-events: none;
}

/* Sizes */
.ball--size-sm {
  width: 30px;
  height: 30px;
  font-size: 13px;
  border-radius: var(--radius-sm, 6px);
}

.ball--size-md {
  width: 40px;
  height: 40px;
  font-size: 17px;
  border-radius: var(--radius-md, 9px);
}

.ball--size-lg {
  width: 56px;
  height: 56px;
  font-size: 24px;
  border-radius: var(--radius-lg, 12px);
}

/* MAIN Style: Blue / Periwinkle → Violet Gradient with blue-violet glow */
.ball--main {
  background: var(--gradient-secondary, linear-gradient(135deg, #3b82f6 0%, #7c3aed 100%));
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.4),
    0 0 12px rgba(59, 130, 246, 0.35),
    inset 0 1px 2px rgba(255, 255, 255, 0.35),
    inset 0 -1px 2px rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.ball--main:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow:
    0 8px 18px rgba(0, 0, 0, 0.5),
    0 0 20px rgba(124, 58, 237, 0.55),
    inset 0 1px 3px rgba(255, 255, 255, 0.45);
}

/* SPECIAL Style: Violet → Magenta / Pink Gradient with pink-purple glow */
.ball--special,
.ball--special-base {
  background: var(--gradient-accent, linear-gradient(135deg, #9333ea 0%, #db2777 100%));
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.4),
    0 0 14px rgba(219, 39, 119, 0.45),
    inset 0 1px 2px rgba(255, 255, 255, 0.35),
    inset 0 -1px 2px rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.ball--special:hover,
.ball--special-base:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow:
    0 8px 18px rgba(0, 0, 0, 0.5),
    0 0 22px rgba(236, 72, 153, 0.65),
    inset 0 1px 3px rgba(255, 255, 255, 0.45);
}

/* HIT Style: Preserves main/special identity with bright glowing border & star badge */
.ball--hit {
  border: 2px solid #38bdf8;
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.5),
    0 0 20px rgba(56, 189, 248, 0.6),
    inset 0 1px 3px rgba(255, 255, 255, 0.45);
  animation: hitPulse 2.5s ease-in-out infinite;
}

.ball--hit:not(.ball--special-base) {
  background: var(--gradient-secondary, linear-gradient(135deg, #2563eb 0%, #7c3aed 100%));
}

.ball--hit.ball--special-base {
  background: linear-gradient(135deg, #9333ea 0%, #e11d48 100%);
  border-color: #f472b6;
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.5),
    0 0 20px rgba(244, 114, 182, 0.65),
    inset 0 1px 3px rgba(255, 255, 255, 0.45);
}

.ball__hit-badge {
  position: absolute;
  top: -5px;
  right: -5px;
  font-size: 10px;
  color: #fef08a;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.8));
}

.ball__miss-badge {
  position: absolute;
  right: 3px;
  bottom: 2px;
  color: #e2e8f0;
  font-size: 11px;
  font-weight: 900;
  line-height: 1;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8);
}

@keyframes hitPulse {
  0%, 100% {
    box-shadow:
      0 4px 14px rgba(0, 0, 0, 0.5),
      0 0 14px rgba(56, 189, 248, 0.45);
  }
  50% {
    box-shadow:
      0 6px 20px rgba(0, 0, 0, 0.6),
      0 0 24px rgba(56, 189, 248, 0.8);
  }
}

/* MISS Style: Retains shape, lower saturation and opacity */
.ball--miss {
  background: linear-gradient(135deg, rgba(71, 85, 105, 0.6) 0%, rgba(51, 65, 85, 0.6) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  opacity: 0.45;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
  color: #94a3b8;
}

.ball--miss:hover {
  opacity: 0.75;
  transform: none;
}

/* SELECTED Style: Distinct focus/selection ring */
.ball--selected {
  outline: 3px solid #ec4899;
  outline-offset: 2px;
  box-shadow:
    0 0 16px rgba(236, 72, 153, 0.6),
    0 4px 12px rgba(0, 0, 0, 0.4);
}

.ball--selected:not(.ball--special-base) {
  background: var(--gradient-secondary, linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%));
}

/* DISABLED Style: Low opacity and grayscale */
.ball--disabled {
  opacity: 0.35;
  filter: grayscale(80%);
  cursor: not-allowed;
  box-shadow: none;
  border: 1px dashed rgba(255, 255, 255, 0.15);
}

.ball__value {
  line-height: 1;
  position: relative;
  z-index: 1;
}

.ball__subtext {
  font-size: 8.5px;
  font-weight: 700;
  color: #e2e8f0;
  text-transform: uppercase;
  margin-top: 1px;
  line-height: 1;
}

@media (prefers-reduced-motion: reduce) {
  .lottery-number-ball,
  .ball--hit {
    animation: none;
    transition: none;
  }
}
</style>
