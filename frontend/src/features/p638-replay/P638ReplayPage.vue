<script setup lang="ts">
import { p638Adapter } from '../replay-explorer/adapters/p638Adapter'
import ReplayExplorer from '../replay-explorer/ReplayExplorer.vue'
</script>

<template>
  <div class="p638-replay-page">
    <ReplayExplorer :adapter="p638Adapter" />
  </div>
</template>

<style scoped>
.p638-replay-page {
  width: 100%;
}
</style>
