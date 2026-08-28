<script setup lang="ts">
import { t539Adapter } from '../replay-explorer/adapters/t539Adapter'
import ReplayExplorer from '../replay-explorer/ReplayExplorer.vue'
</script>

<template>
  <div class="t539-replay-page">
    <ReplayExplorer :adapter="t539Adapter" />
  </div>
</template>

<style scoped>
.t539-replay-page {
  width: 100%;
}
</style>
