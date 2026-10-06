<script setup lang="ts">
// 两栏外壳（三页复用）：左侧栏插槽 + 主区默认插槽。
defineProps<{ sidebarCollapsed?: boolean }>()
</script>

<template>
  <div class="app-layout">
    <aside class="app-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <slot name="sidebar" />
    </aside>
    <main class="app-main">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  background: var(--td-bg-color-page);
}
.app-sidebar {
  width: 260px;
  flex-shrink: 0;
  height: 100%;
  background: var(--td-bg-color-container);
  border-right: 1px solid var(--td-component-stroke);
  transition: width 0.2s ease;
  overflow: hidden;
}
.app-sidebar.collapsed {
  width: 0;
  border-right: none;
}
.app-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}
</style>
