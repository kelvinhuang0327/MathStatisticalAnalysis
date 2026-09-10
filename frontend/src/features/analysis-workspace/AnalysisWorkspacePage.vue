<script setup lang="ts">
import SectionHeader from '../../components/SectionHeader.vue'

const workspaceDestinations = [
  {
    href: '#/data-operations',
    label: 'Data Operations',
    category: 'Data',
    description: '匯入、預覽與檢視資料操作記錄。',
    tone: 'violet',
  },
  {
    href: '#/history',
    label: 'History',
    category: 'History',
    description: '瀏覽開獎歷史與 ingestion history。',
    tone: 'cyan',
  },
  {
    href: '#/best-replay',
    label: 'Best Replay',
    category: 'Replay',
    description: '前往既有的最佳回放分析工作區。',
    tone: 'pink',
  },
  {
    href: '#/replay-overview',
    label: 'Replay Overview',
    category: 'Replay',
    description: '檢視所有策略的回放總覽與比較。',
    tone: 'violet',
  },
  {
    href: '#/strategy-intelligence',
    label: 'Strategy Intelligence',
    category: 'Strategies',
    description: '查看策略註冊、描述性資料與證據入口。',
    tone: 'cyan',
  },
  {
    href: '#/b649-replay',
    label: 'B649 Replay',
    category: 'B649',
    description: '前往 B649 歷史回放、紀錄與排名頁面。',
    tone: 'pink',
  },
  {
    href: '#/p638-replay',
    label: 'P638 Replay',
    category: 'P638',
    description: '前往 P638 歷史回放與研究證據頁面。',
    tone: 'violet',
  },
  {
    href: '#/t539-replay',
    label: 'T539 Replay',
    category: 'T539',
    description: '前往 T539 回放、排名與 coverage 頁面。',
    tone: 'cyan',
  },
  {
    href: '#/future-modules',
    label: 'Future Modules',
    category: 'Roadmap',
    description: '查看現有的模組延伸與研究路線圖。',
    tone: 'pink',
  },
] as const
</script>

<template>
  <section class="analysis-workspace-page" aria-labelledby="analysis-workspace-title">
    <SectionHeader
      id="analysis-workspace-title"
      title="分析工作區導覽"
      eyebrow="Analysis Workspace"
      description="從單一入口前往 LottoLab 現有的資料、歷史、回放與策略研究區塊。"
    >
      <template #actions>
        <span class="status-badge status-badge--accent">NAVIGATION HUB</span>
      </template>
    </SectionHeader>

    <article class="analysis-workspace-hero panel">
      <div class="analysis-workspace-hero__glow" aria-hidden="true" />
      <div class="analysis-workspace-hero__content">
        <p class="analysis-workspace-hero__eyebrow">Product sections</p>
        <h2>從既有工作區開始</h2>
        <p>
          這個入口只負責導覽，不產生新的分析結果；請選擇一個產品區塊以繼續目前的研究流程。
        </p>
      </div>
      <span class="analysis-workspace-hero__mark" aria-hidden="true">LL</span>
    </article>

    <nav class="analysis-workspace-nav" aria-label="Analysis workspace destinations">
      <ul class="analysis-workspace-grid">
        <li v-for="destination in workspaceDestinations" :key="destination.href">
          <a
            class="analysis-workspace-card"
            :class="`analysis-workspace-card--${destination.tone}`"
            :href="destination.href"
            data-testid="workspace-destination"
          >
            <span class="analysis-workspace-card__topline">
              <span class="analysis-workspace-card__category">{{ destination.category }}</span>
              <svg
                class="analysis-workspace-card__arrow"
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
            </span>
            <h2>{{ destination.label }}</h2>
            <p>{{ destination.description }}</p>
            <span class="analysis-workspace-card__action">
              Open section
              <span aria-hidden="true">→</span>
            </span>
          </a>
        </li>
      </ul>
    </nav>
  </section>
</template>

<style scoped>
/*
 * Visual language reference: MengTo/threeui @
 * 68802d5428071ada5c20db8094b1649e6bb770ed,
 * src/shaders/neuform-isolated/sources/gradient-pill-button.html, MIT
 * (Copyright (c) 2026 Meng To). This production page keeps the source's
 * pill, gradient, ring, and soft-elevation vocabulary as visual inspiration
 * only; all markup and CSS below are native Vue code using LottoLab tokens.
 * License record: threeui-vue-page/references/THREEUI_VUE_ADAPTATION.md.
 */
.analysis-workspace-page {
  width: min(1180px, calc(100% - 40px));
  margin: 0 auto;
  padding: 40px 0 56px;
}

.analysis-workspace-hero {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  min-height: 176px;
  margin-bottom: 24px;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(124, 58, 237, 0.17), transparent 48%),
    var(--gradient-card);
}

.analysis-workspace-hero__content {
  position: relative;
  z-index: 1;
  max-width: 760px;
}

.analysis-workspace-hero__eyebrow {
  margin: 0 0 8px;
  color: var(--text-accent);
  font: 700 11px/1 var(--font-mono);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.analysis-workspace-hero h2 {
  margin: 0 0 10px;
  color: var(--text-primary);
  font-size: clamp(22px, 3vw, 32px);
  letter-spacing: -0.03em;
}

.analysis-workspace-hero p:last-child {
  max-width: 680px;
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.analysis-workspace-hero__glow {
  position: absolute;
  width: 260px;
  height: 260px;
  right: 8%;
  bottom: -170px;
  border-radius: 50%;
  background: var(--gradient-glow);
  filter: blur(4px);
}

.analysis-workspace-hero__mark {
  position: relative;
  display: grid;
  width: 92px;
  height: 92px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: var(--radius-xl);
  background: var(--gradient-primary);
  color: #fff;
  font: 800 24px/1 var(--font-mono);
  box-shadow: var(--shadow-glow);
}

.analysis-workspace-nav {
  min-width: 0;
}

.analysis-workspace-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.analysis-workspace-card {
  position: relative;
  display: flex;
  min-height: 214px;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  background: var(--bg-card);
  color: var(--text-primary);
  text-decoration: none;
  box-shadow: var(--shadow-sm);
  isolation: isolate;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.analysis-workspace-card::after {
  position: absolute;
  inset: 0;
  z-index: -1;
  content: '';
  background: var(--gradient-card);
  opacity: 0.58;
  transition: opacity 0.2s ease;
}

.analysis-workspace-card:hover {
  transform: translateY(-3px);
  border-color: var(--border-hover);
  box-shadow: var(--shadow-md);
}

.analysis-workspace-card:hover::after {
  opacity: 0.95;
}

.analysis-workspace-card:focus-visible {
  outline: 3px solid rgba(139, 92, 246, 0.58);
  outline-offset: 3px;
}

.analysis-workspace-card--violet {
  --workspace-card-accent: var(--text-accent);
  --workspace-card-glow: rgba(139, 92, 246, 0.15);
}

.analysis-workspace-card--cyan {
  --workspace-card-accent: var(--text-cyan);
  --workspace-card-glow: rgba(56, 189, 248, 0.13);
}

.analysis-workspace-card--pink {
  --workspace-card-accent: var(--accent-color);
  --workspace-card-glow: rgba(219, 39, 119, 0.13);
}

.analysis-workspace-card::before {
  position: absolute;
  inset: 0;
  z-index: -1;
  content: '';
  background: radial-gradient(circle at 100% 0, var(--workspace-card-glow), transparent 42%);
  pointer-events: none;
}

.analysis-workspace-card__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.analysis-workspace-card__category {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 5px 10px;
  border: 1px solid color-mix(in srgb, var(--workspace-card-accent) 42%, transparent);
  border-radius: var(--radius-full);
  background: color-mix(in srgb, var(--workspace-card-accent) 12%, transparent);
  color: var(--workspace-card-accent);
  font: 700 10px/1 var(--font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.analysis-workspace-card__arrow {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
  color: var(--workspace-card-accent);
  transition: transform 0.2s ease;
}

.analysis-workspace-card:hover .analysis-workspace-card__arrow {
  transform: translateX(3px);
}

.analysis-workspace-card h2 {
  margin: 24px 0 8px;
  font-size: clamp(18px, 2vw, 22px);
  letter-spacing: -0.025em;
}

.analysis-workspace-card p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.analysis-workspace-card__action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: auto;
  padding-top: 20px;
  color: var(--workspace-card-accent);
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 960px) {
  .analysis-workspace-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .analysis-workspace-page {
    width: calc(100% - 32px);
    padding: 24px 0 40px;
  }

  .analysis-workspace-hero {
    align-items: flex-start;
    flex-direction: column;
    gap: 20px;
    padding: 20px;
  }

  .analysis-workspace-hero__mark {
    width: 64px;
    height: 64px;
    border-radius: var(--radius-lg);
    font-size: 18px;
  }

  .analysis-workspace-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .analysis-workspace-card,
  .analysis-workspace-card__arrow {
    transition: none;
  }
}
</style>
