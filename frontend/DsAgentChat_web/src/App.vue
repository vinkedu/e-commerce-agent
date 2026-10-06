<script setup lang="ts">
</script>

<template>
  <router-view></router-view>
</template>

<style>
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Microsoft YaHei', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.loading-screen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--td-bg-color-page, #f3f5f7);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--td-brand-color-2, #c4f0d3);
  border-top-color: var(--td-brand-color, #07a452);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style> 