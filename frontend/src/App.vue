<script setup lang="ts">
import StrategyCatalogPage from './features/strategy-catalog/StrategyCatalogPage.vue'
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <a class="brand" href="/" aria-label="LottoLab home">
        <span class="brand__mark">LL</span>
        <span>
          <strong>LottoLab</strong>
          <small>Statistical Analysis</small>
        </span>
      </a>
      <span class="environment-badge">Read-only catalog</span>
    </header>

    <main>
      <StrategyCatalogPage />
    </main>

    <footer class="app-footer">
      Metadata provenance is pinned to LotteryNew commit
      <code>520c3922a7c8</code>. No database is used by this request path.
    </footer>
  </div>
</template>
