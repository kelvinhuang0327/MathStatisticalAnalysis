<script setup lang="ts">
import { computed, ref } from 'vue'

import type { CrossWindowData, CrossWindowPoint } from '../types'

const props = defineProps<{
  data: CrossWindowData | null
  loading?: boolean
}>()

const hoveredPoint = ref<{
  point: CrossWindowPoint
  x: number
  y: number
} | null>(null)

const CHART_WIDTH = 720
const CHART_HEIGHT = 280
const PADDING = { top: 30, right: 40, bottom: 50, left: 60 }
const PLOT_WIDTH = CHART_WIDTH - PADDING.left - PADDING.right
const PLOT_HEIGHT = CHART_HEIGHT - PADDING.top - PADDING.bottom

const chartBounds = computed(() => {
  let minY = 0
  let maxY = 0.5 // Default max 50%

  if (props.data) {
    for (const p of props.data.points) {
      if (p.officialAnyPrizeRate !== null) {
        if (p.officialAnyPrizeRate > maxY) maxY = p.officialAnyPrizeRate
      }
      if (p.baselineRate !== null) {
        if (p.baselineRate > maxY) maxY = p.baselineRate
      }
    }
  }

  // Add 15% headroom
  maxY = Math.min(1, maxY * 1.15)
  return { minY, maxY }
})

function getX(index: number, total: number): number {
  if (total <= 1) return PADDING.left + PLOT_WIDTH / 2
  return PADDING.left + (index / (total - 1)) * PLOT_WIDTH
}

function getY(value: number): number {
  const { minY, maxY } = chartBounds.value
  if (maxY === minY) return PADDING.top + PLOT_HEIGHT / 2
  const ratio = (value - minY) / (maxY - minY)
  return PADDING.top + (1 - ratio) * PLOT_HEIGHT
}

// Generate SVG polyline points
const strategyLinePoints = computed(() => {
  if (!props.data) return ''
  const pts: string[] = []
  props.data.points.forEach((p, idx) => {
    if (p.officialAnyPrizeRate !== null) {
      const x = getX(idx, props.data!.points.length)
      const y = getY(p.officialAnyPrizeRate)
      pts.push(`${x},${y}`)
    }
  })
  return pts.join(' ')
})

const baselineLinePoints = computed(() => {
  if (!props.data) return ''
  const pts: string[] = []
  props.data.points.forEach((p, idx) => {
    if (p.baselineRate !== null) {
      const x = getX(idx, props.data!.points.length)
      const y = getY(p.baselineRate)
      pts.push(`${x},${y}`)
    }
  })
  return pts.join(' ')
})

// Y-axis ticks (4 ticks)
const yTicks = computed(() => {
  const { minY, maxY } = chartBounds.value
  const count = 4
  const step = (maxY - minY) / count
  const ticks: { value: number; label: string; y: number }[] = []
  for (let i = 0; i <= count; i++) {
    const val = minY + step * i
    ticks.push({
      value: val,
      label: `${(val * 100).toFixed(1)}%`,
      y: getY(val),
    })
  }
  return ticks
})
</script>

<template>
  <div class="cross-window-chart" data-testid="cross-window-chart">
    <div class="chart-header">
      <div class="chart-title-wrap">
        <h4 class="chart-title">
          跨窗口穩定度比較圖 (Cross-Window Trend)
        </h4>
        <span v-if="data" class="chart-strategy-name">
          {{ data.displayName }} ({{ data.strategyId }}) · {{ data.ticketCount }} 注
        </span>
      </div>

      <!-- Legend -->
      <div class="chart-legend">
        <div class="legend-item">
          <span class="legend-dot legend-dot--strategy" />
          <span>策略官方成功率 (Official Any-Prize Rate)</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot legend-dot--baseline" />
          <span>隨機基準 (Random Baseline)</span>
        </div>
      </div>
    </div>

    <div v-if="loading" class="chart-loading">
      <span class="spinner" aria-hidden="true" />
      <span>載入跨窗口趨勢圖中…</span>
    </div>

    <div v-else-if="!data" class="chart-placeholder" data-testid="chart-placeholder">
      <p>請在上方排名表或矩陣中點選任一策略，即可查看其跨 FULL / 750 / 300 / 50 窗口之走勢與基準對比。</p>
    </div>

    <div v-else class="chart-svg-wrap">
      <svg
        :viewBox="`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`"
        class="chart-svg"
        role="img"
        aria-label="跨窗口成功率趨勢圖表"
      >
        <!-- Horizontal Grid Lines -->
        <g class="grid-lines">
          <line
            v-for="tick in yTicks"
            :key="tick.value"
            :x1="PADDING.left"
            :y1="tick.y"
            :x2="CHART_WIDTH - PADDING.right"
            :y2="tick.y"
            class="grid-line"
          />
        </g>

        <!-- Y Axis Labels -->
        <g class="y-labels">
          <text
            v-for="tick in yTicks"
            :key="tick.value"
            :x="PADDING.left - 10"
            :y="tick.y + 4"
            text-anchor="end"
            class="axis-label"
          >
            {{ tick.label }}
          </text>
        </g>

        <!-- Baseline Polyline (dashed) -->
        <polyline
          v-if="baselineLinePoints"
          :points="baselineLinePoints"
          class="line-baseline"
        />

        <!-- Strategy Polyline -->
        <polyline
          v-if="strategyLinePoints"
          :points="strategyLinePoints"
          class="line-strategy"
        />

        <!-- Baseline Points -->
        <g v-if="data" class="baseline-points">
          <circle
            v-for="(p, idx) in data.points"
            v-show="p.baselineRate !== null"
            :key="`b-${p.window}`"
            :cx="getX(idx, data.points.length)"
            :cy="getY(p.baselineRate ?? 0)"
            r="4"
            class="point-baseline"
          />
        </g>

        <!-- Strategy Points -->
        <g v-if="data" class="strategy-points">
          <g
            v-for="(p, idx) in data.points"
            :key="`s-${p.window}`"
          >
            <!-- Available Point -->
            <template v-if="p.officialAnyPrizeRate !== null">
              <circle
                :cx="getX(idx, data.points.length)"
                :cy="getY(p.officialAnyPrizeRate)"
                r="6"
                class="point-strategy"
                :class="{ 'point-strategy--active': hoveredPoint?.point.window === p.window }"
                @mouseenter="hoveredPoint = { point: p, x: getX(idx, data.points.length), y: getY(p.officialAnyPrizeRate) }"
                @mouseleave="hoveredPoint = null"
              />
              <!-- Value Text above Point -->
              <text
                :x="getX(idx, data.points.length)"
                :y="getY(p.officialAnyPrizeRate) - 10"
                text-anchor="middle"
                class="point-value-text"
              >
                {{ p.officialAnyPrizeRateFormatted }}
              </text>
            </template>

            <!-- Unavailable Point Indicator -->
            <template v-else>
              <circle
                :cx="getX(idx, data.points.length)"
                :cy="CHART_HEIGHT - PADDING.bottom"
                r="4"
                class="point-unavailable"
              />
              <text
                :x="getX(idx, data.points.length)"
                :y="CHART_HEIGHT - PADDING.bottom - 10"
                text-anchor="middle"
                class="unavailable-callout"
              >
                無資料
              </text>
            </template>
          </g>
        </g>

        <!-- X Axis Labels -->
        <g v-if="data" class="x-labels">
          <text
            v-for="(p, idx) in data.points"
            :key="p.window"
            :x="getX(idx, data.points.length)"
            :y="CHART_HEIGHT - PADDING.bottom + 22"
            text-anchor="middle"
            class="axis-label axis-label--x"
          >
            {{ p.windowLabel }}
          </text>
        </g>
      </svg>

      <!-- Tooltip Card -->
      <div
        v-if="hoveredPoint"
        class="chart-tooltip"
        :style="{
          left: `${(hoveredPoint.x / CHART_WIDTH) * 100}%`,
          top: `${(hoveredPoint.y / CHART_HEIGHT) * 100}%`,
        }"
      >
        <div class="tooltip-title">{{ hoveredPoint.point.windowLabel }} 窗口</div>
        <div class="tooltip-item">
          <span>官方排名：</span>
          <strong>#{{ hoveredPoint.point.officialRank ?? '—' }}</strong>
        </div>
        <div class="tooltip-item">
          <span>成功率：</span>
          <strong class="text-cyan">{{ hoveredPoint.point.officialAnyPrizeRateFormatted }}</strong>
        </div>
        <div v-if="hoveredPoint.point.baselineRate !== null" class="tooltip-item">
          <span>基準成功率：</span>
          <span>{{ hoveredPoint.point.baselineRateFormatted }}</span>
        </div>
        <div v-if="hoveredPoint.point.baselineDelta !== null" class="tooltip-item">
          <span>基準差異 (Delta)：</span>
          <strong :class="hoveredPoint.point.baselineDelta > 0 ? 'text-green' : 'text-red'">
            {{ hoveredPoint.point.baselineDeltaFormatted }}
          </strong>
        </div>
        <div v-if="hoveredPoint.point.observations !== null" class="tooltip-item">
          <span>觀察期數：</span>
          <span>{{ hoveredPoint.point.observations }} 期</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cross-window-chart {
  background: var(--bg-card, rgba(18, 24, 38, 0.72));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  border-radius: var(--radius-md, 10px);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 10px;
}

.chart-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chart-title {
  margin: 0;
  font-size: 0.95rem;
  color: var(--text-primary, #f8fafc);
  font-weight: 600;
}

.chart-strategy-name {
  font-size: 0.8rem;
  color: #38bdf8;
  font-family: var(--font-mono, monospace);
}

.chart-legend {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 0.78rem;
  color: var(--text-secondary, #94a3b8);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-dot--strategy {
  background: #38bdf8;
  box-shadow: 0 0 6px rgba(56, 189, 248, 0.6);
}

.legend-dot--baseline {
  background: #f472b6;
  border: 1px dashed #f472b6;
}

.chart-loading,
.chart-placeholder {
  padding: 40px;
  text-align: center;
  color: var(--text-secondary, #94a3b8);
  font-size: 0.85rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.chart-svg-wrap {
  position: relative;
  width: 100%;
}

.chart-svg {
  width: 100%;
  height: auto;
  overflow: visible;
}

.grid-line {
  stroke: rgba(255, 255, 255, 0.07);
  stroke-dasharray: 4 4;
}

.axis-label {
  fill: var(--text-tertiary, #64748b);
  font-size: 11px;
  font-family: var(--font-mono, monospace);
}

.axis-label--x {
  fill: var(--text-secondary, #94a3b8);
  font-weight: 600;
  font-size: 12px;
}

.line-baseline {
  fill: none;
  stroke: #f472b6;
  stroke-width: 2;
  stroke-dasharray: 5 4;
  opacity: 0.8;
}

.line-strategy {
  fill: none;
  stroke: #38bdf8;
  stroke-width: 3;
}

.point-baseline {
  fill: #f472b6;
  opacity: 0.8;
}

.point-strategy {
  fill: #0d111b;
  stroke: #38bdf8;
  stroke-width: 3;
  cursor: pointer;
  transition: r 0.15s ease, stroke-width 0.15s ease;
}

.point-strategy:hover,
.point-strategy--active {
  r: 8;
  fill: #38bdf8;
  stroke: #ffffff;
}

.point-value-text {
  fill: #38bdf8;
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  font-weight: 600;
}

.point-unavailable {
  fill: rgba(255, 255, 255, 0.2);
}

.unavailable-callout {
  fill: var(--text-tertiary, #64748b);
  font-size: 10px;
  font-style: italic;
}

.chart-tooltip {
  position: absolute;
  transform: translate(-50%, -120%);
  background: rgba(13, 17, 27, 0.95);
  border: 1px solid var(--border-hover, rgba(255, 255, 255, 0.22));
  border-radius: var(--radius-sm, 6px);
  padding: 8px 12px;
  font-size: 0.78rem;
  color: var(--text-primary, #f8fafc);
  pointer-events: none;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  gap: 3px;
  white-space: nowrap;
  z-index: 10;
}

.tooltip-title {
  font-weight: 700;
  color: #a5b4fc;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 3px;
  margin-bottom: 2px;
}

.tooltip-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.text-cyan {
  color: #38bdf8;
}

.text-green {
  color: #34d399;
}

.text-red {
  color: #f87171;
}
</style>
