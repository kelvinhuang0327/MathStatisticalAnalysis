<script setup lang="ts">
import { computed, ref } from 'vue'

import EmptyState from '../../../components/EmptyState.vue'
import type { GameCode, TrendSeries } from '../types'

const props = withDefaults(
  defineProps<{
    game: GameCode
    series: TrendSeries[]
    supportsTrend: boolean
    trendUnavailableReason?: string
    loading?: boolean
  }>(),
  {
    loading: false,
    trendUnavailableReason: 'This game does not expose canonical time-series or multi-window trend evidence.',
  },
)

const hoveredPoint = ref<{
  seriesLabel: string
  xLabel: string
  yFormatted: string
  tooltipText?: string
  x: number
  y: number
} | null>(null)

// Color palette for multiple series
const SERIES_COLORS = [
  '#38bdf8', // Cyan
  '#818cf8', // Indigo
  '#f472b6', // Pink
  '#34d399', // Emerald
]

// Filter series with at least 1 point with valid yValue
const activeSeries = computed(() => {
  return props.series.filter((s) => s.points.some((p) => p.yValue !== null))
})

// Collect all unique X labels
const allXLabels = computed(() => {
  const labels: string[] = []
  for (const s of activeSeries.value) {
    for (const p of s.points) {
      if (!labels.includes(p.xLabel)) {
        labels.push(p.xLabel)
      }
    }
  }
  return labels
})

// Calculate chart bounds
const chartBounds = computed(() => {
  let minY = Infinity
  let maxY = -Infinity

  for (const s of activeSeries.value) {
    for (const p of s.points) {
      if (p.yValue !== null) {
        if (p.yValue < minY) minY = p.yValue
        if (p.yValue > maxY) maxY = p.yValue
      }
    }
  }

  if (minY === Infinity) return { minY: 0, maxY: 1 }
  // Add 10% padding
  const padding = (maxY - minY) * 0.1 || 0.05
  return {
    minY: Math.max(0, minY - padding),
    maxY: maxY + padding,
  }
})

// Chart dimensions
const CHART_WIDTH = 760
const CHART_HEIGHT = 320
const PADDING = { top: 30, right: 40, bottom: 50, left: 60 }
const PLOT_WIDTH = CHART_WIDTH - PADDING.left - PADDING.right
const PLOT_HEIGHT = CHART_HEIGHT - PADDING.top - PADDING.bottom

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

// Generate SVG paths for each series
const renderedSeries = computed(() => {
  const xLabels = allXLabels.value
  return activeSeries.value.map((s, sIndex) => {
    const color = SERIES_COLORS[sIndex % SERIES_COLORS.length]!
    const validPoints: Array<{ x: number; y: number; point: typeof s.points[0] }> = []

    for (const p of s.points) {
      const xIdx = xLabels.indexOf(p.xLabel)
      if (xIdx >= 0 && p.yValue !== null) {
        validPoints.push({
          x: getX(xIdx, xLabels.length),
          y: getY(p.yValue),
          point: p,
        })
      }
    }

    const pathData = validPoints.reduce((acc, curr, idx) => {
      return idx === 0 ? `M ${curr.x} ${curr.y}` : `${acc} L ${curr.x} ${curr.y}`
    }, '')

    return {
      strategyId: s.strategyId,
      strategyLabel: s.strategyLabel,
      color,
      pathData,
      points: validPoints,
    }
  })
})

const yAxisTicks = computed(() => {
  const { minY, maxY } = chartBounds.value
  const count = 5
  const ticks = []
  for (let i = 0; i <= count; i++) {
    const val = minY + (i / count) * (maxY - minY)
    ticks.push({
      y: getY(val),
      label: `${(val * 100).toFixed(1)}%`,
    })
  }
  return ticks
})
</script>

<template>
  <div class="replay-trend-view">
    <!-- Explicit Unavailable Banner if trend not supported -->
    <div v-if="!supportsTrend" class="trend-unavailable-banner">
      <EmptyState
        title="TREND EVIDENCE UNAVAILABLE"
        :description="trendUnavailableReason"
      />
    </div>

    <div v-else-if="loading" class="trend-loading">
      <span class="spinner" aria-hidden="true" />
      <span>Loading trend time-series…</span>
    </div>

    <div v-else-if="activeSeries.length === 0" class="trend-empty">
      <EmptyState
        title="No Trend Data"
        description="Select up to 4 strategies with available replay history to visualize performance trends."
      />
    </div>

    <!-- Active Chart Container -->
    <div v-else class="chart-container">
      <div class="chart-header">
        <div>
          <h4 class="chart-title">
            <template v-if="game === 'B649'">Historical Multi-Horizon Progression (Full → 50 Draws)</template>
            <template v-else-if="game === 'P638'">Chronological Draw Hit Progression</template>
            <template v-else>Hit Distribution Progression</template>
          </h4>
          <p class="chart-subtitle text-muted">
            <template v-if="game === 'B649'">Observed success rate across canonical validation windows.</template>
            <template v-else>Empirical cumulative hit rate across chronological draws.</template>
          </p>
        </div>

        <!-- Series Legend -->
        <div class="chart-legend">
          <div
            v-for="s in renderedSeries"
            :key="s.strategyId"
            class="legend-item"
          >
            <span class="legend-swatch" :style="{ background: s.color }" />
            <span class="legend-name">{{ s.strategyLabel }}</span>
          </div>
        </div>
      </div>

      <!-- SVG Chart -->
      <div class="svg-wrapper">
        <svg
          :viewBox="`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`"
          class="trend-svg"
          aria-label="Replay Trend Performance Chart"
        >
          <!-- Grid Lines (Y-Axis) -->
          <g class="grid-lines">
            <line
              v-for="(tick, idx) in yAxisTicks"
              :key="idx"
              :x1="PADDING.left"
              :y1="tick.y"
              :x2="CHART_WIDTH - PADDING.right"
              :y2="tick.y"
              class="grid-line"
            />
          </g>

          <!-- Y-Axis Labels -->
          <g class="axis-labels y-labels">
            <text
              v-for="(tick, idx) in yAxisTicks"
              :key="idx"
              :x="PADDING.left - 10"
              :y="tick.y + 4"
              text-anchor="end"
              class="axis-text"
            >
              {{ tick.label }}
            </text>
          </g>

          <!-- X-Axis Labels -->
          <g class="axis-labels x-labels">
            <text
              v-for="(label, idx) in allXLabels"
              :key="idx"
              :x="getX(idx, allXLabels.length)"
              :y="CHART_HEIGHT - 15"
              text-anchor="middle"
              class="axis-text"
            >
              {{ label }}
            </text>
          </g>

          <!-- Series Paths -->
          <g class="series-paths">
            <path
              v-for="s in renderedSeries"
              :key="s.strategyId"
              :d="s.pathData"
              :stroke="s.color"
              stroke-width="3"
              fill="none"
              class="series-line"
            />
          </g>

          <!-- Series Points -->
          <g class="series-points">
            <template v-for="s in renderedSeries" :key="s.strategyId">
              <circle
                v-for="(p, pIdx) in s.points"
                :key="pIdx"
                :cx="p.x"
                :cy="p.y"
                r="5"
                :fill="s.color"
                class="series-point"
                @mouseenter="
                  hoveredPoint = {
                    seriesLabel: s.strategyLabel,
                    xLabel: p.point.xLabel,
                    yFormatted: p.point.yFormatted,
                    tooltipText: p.point.tooltipText,
                    x: p.x,
                    y: p.y,
                  }
                "
                @mouseleave="hoveredPoint = null"
              />
            </template>
          </g>
        </svg>

        <!-- Hover Tooltip -->
        <div
          v-if="hoveredPoint"
          class="chart-tooltip"
          :style="{
            left: `${(hoveredPoint.x / CHART_WIDTH) * 100}%`,
            top: `${(hoveredPoint.y / CHART_HEIGHT) * 100}%`,
          }"
        >
          <strong>{{ hoveredPoint.seriesLabel }}</strong>
          <span class="tooltip-val">{{ hoveredPoint.tooltipText || `${hoveredPoint.xLabel}: ${hoveredPoint.yFormatted}` }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.replay-trend-view {
  width: 100%;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 1.5rem;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.chart-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--color-gray-100, #f1f5f9);
}

.chart-subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
}

.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  background: rgba(0, 0, 0, 0.2);
  padding: 0.5rem 0.85rem;
  border-radius: 6px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: var(--color-gray-200, #e2e8f0);
}

.legend-swatch {
  width: 12px;
  height: 4px;
  border-radius: 2px;
}

.svg-wrapper {
  position: relative;
  width: 100%;
}

.trend-svg {
  width: 100%;
  height: auto;
  overflow: visible;
}

.grid-line {
  stroke: rgba(255, 255, 255, 0.06);
  stroke-dasharray: 4 4;
}

.axis-text {
  fill: var(--color-gray-400, #94a3b8);
  font-size: 11px;
}

.series-line {
  stroke-linejoin: round;
  stroke-linecap: round;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.4));
}

.series-point {
  cursor: pointer;
  stroke: #0f172a;
  stroke-width: 2;
  transition: r 0.15s ease;
}

.series-point:hover {
  r: 8;
}

.chart-tooltip {
  position: absolute;
  transform: translate(-50%, -120%);
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  color: #fff;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  white-space: nowrap;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.tooltip-val {
  color: var(--color-cyan-300, #67e8f9);
}

.trend-loading,
.trend-empty {
  padding: 3rem 1rem;
  text-align: center;
  color: var(--color-gray-400, #94a3b8);
}

.text-muted {
  color: var(--color-gray-400, #94a3b8);
}
</style>
