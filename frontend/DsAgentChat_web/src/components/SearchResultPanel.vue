<script setup lang="ts">
import type { SearchResult } from '../types'

defineProps<{ visible: boolean; results: SearchResult[] }>()
const emit = defineEmits<{ 'update:visible': [v: boolean] }>()
</script>

<template>
  <t-drawer
    :visible="visible"
    header="联网搜索结果"
    :footer="false"
    size="420px"
    @close="emit('update:visible', false)"
  >
    <div v-if="results.length === 0" class="empty">暂无结果</div>
    <ul v-else class="result-list">
      <li v-for="(r, i) in results" :key="i" class="result-item">
        <a :href="r.url" target="_blank" rel="noopener" class="r-title">{{ r.title }}</a>
        <p class="r-snippet">{{ r.snippet }}</p>
        <span class="r-source">{{ r.source || r.url }}</span>
      </li>
    </ul>
  </t-drawer>
</template>

<style scoped>
.empty {
  color: var(--td-text-color-placeholder);
  text-align: center;
  padding: 40px 0;
}
.result-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.result-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--td-component-stroke);
}
.r-title {
  color: var(--td-brand-color);
  font-weight: 500;
  text-decoration: none;
}
.r-title:hover {
  text-decoration: underline;
}
.r-snippet {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  margin: 6px 0;
}
.r-source {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}
</style>
