<script setup lang="ts">
withDefaults(
  defineProps<{
    caption?: string
    loading?: boolean
    empty?: boolean
    emptyMessage?: string
    scrollable?: boolean
    minWidth?: string
  }>(),
  {
    caption: undefined,
    loading: false,
    empty: false,
    emptyMessage: 'No records to display.',
    scrollable: true,
    minWidth: '600px',
  },
)
</script>

<template>
  <div class="data-table-wrapper" :class="{ 'data-table-wrapper--scrollable': scrollable }">
    <table class="data-table" :style="{ minWidth: minWidth }">
      <caption v-if="caption || $slots.caption">
        <slot name="caption">{{ caption }}</slot>
      </caption>
      <thead v-if="$slots.head">
        <slot name="head" />
      </thead>
      <tbody v-if="loading">
        <tr>
          <td colspan="100" class="data-table__loading-cell">
            <div class="data-table__loading">
              <span class="spinner" aria-hidden="true" />
              <span>Loading data…</span>
            </div>
          </td>
        </tr>
      </tbody>
      <tbody v-else-if="empty">
        <tr>
          <td colspan="100" class="data-table__empty-cell">
            <slot name="empty">
              <p class="data-table__empty-text">{{ emptyMessage }}</p>
            </slot>
          </td>
        </tr>
      </tbody>
      <tbody v-else>
        <slot />
      </tbody>
      <tfoot v-if="$slots.foot">
        <slot name="foot" />
      </tfoot>
    </table>
    <div v-if="$slots.pagination" class="data-table__pagination">
      <slot name="pagination" />
    </div>
  </div>
</template>
