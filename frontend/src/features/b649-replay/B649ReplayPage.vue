<script setup lang="ts">
import { b649Adapter } from '../replay-explorer/adapters/b649Adapter'
import ReplayExplorer from '../replay-explorer/ReplayExplorer.vue'
</script>

<template>
  <div class="b649-replay-page">
    <ReplayExplorer :adapter="b649Adapter" />
  </div>
</template>

<style scoped>
.b649-replay-page {
  width: 100%;
}
</style>
