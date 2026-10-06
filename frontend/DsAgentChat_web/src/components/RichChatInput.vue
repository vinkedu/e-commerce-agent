<script setup lang="ts">
import { ref } from 'vue'

type Mode = 'standard' | 'reason' | 'search'
const props = defineProps<{ loading: boolean; mode: Mode }>()
const emit = defineEmits<{ send: [text: string]; stop: []; 'update:mode': [m: Mode] }>()

const draft = ref('')
const MODE_LABEL: Record<Mode, string> = {
  standard: '标准',
  reason: '深度推理',
  search: '联网搜索',
}
const modeOptions = [
  { content: '标准', value: 'standard' },
  { content: '深度推理', value: 'reason' },
  { content: '联网搜索', value: 'search' },
]

function onSend(value: string) {
  const t = (value ?? draft.value).trim()
  if (!t || props.loading) return
  emit('send', t)
  draft.value = ''
}
function onStop() {
  emit('stop')
}
function pickMode(data: { value: string | number }) {
  emit('update:mode', data.value as Mode)
}
</script>

<template>
  <t-chat-sender
    v-model="draft"
    :loading="loading"
    placeholder="输入消息，Enter 发送"
    class="rich-input"
    @send="onSend"
    @stop="onStop"
  >
    <template #suffix>
      <t-dropdown :options="modeOptions" :min-column-width="120" @click="pickMode">
        <t-button variant="text" size="small">{{ MODE_LABEL[mode] }} ▾</t-button>
      </t-dropdown>
    </template>
  </t-chat-sender>
</template>

<style scoped>
.rich-input {
  width: 100%;
}
</style>
