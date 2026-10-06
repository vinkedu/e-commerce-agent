<script setup lang="ts">
import RichChatInput from './RichChatInput.vue'

type Mode = 'standard' | 'reason' | 'search'
defineProps<{ loading: boolean; mode: Mode }>()
const emit = defineEmits<{ send: [text: string]; stop: []; 'update:mode': [m: Mode] }>()
</script>

<template>
  <div class="welcome-hero">
    <div class="hero-head">
      <t-avatar size="48px" shape="circle">A</t-avatar>
      <div class="hero-title">AssistGen 助手</div>
      <div class="hero-sub">处理各类问题，支持深度推理与联网搜索</div>
    </div>
    <div class="hero-input">
      <RichChatInput
        :loading="loading"
        :mode="mode"
        @send="(t: string) => emit('send', t)"
        @stop="() => emit('stop')"
        @update:mode="(m: Mode) => emit('update:mode', m)"
      />
    </div>
  </div>
</template>

<style scoped>
.welcome-hero {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
  padding: 24px;
}
.hero-head {
  text-align: center;
}
.hero-title {
  font-size: 22px;
  font-weight: 600;
  margin-top: 12px;
  color: var(--td-text-color-primary);
}
.hero-sub {
  font-size: 14px;
  color: var(--td-text-color-secondary);
  margin-top: 4px;
}
.hero-input {
  width: 100%;
  max-width: 720px;
}
</style>
