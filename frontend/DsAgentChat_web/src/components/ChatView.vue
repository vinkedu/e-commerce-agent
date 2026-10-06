<script setup lang="ts">
import { ref, computed } from 'vue'
import type { LocalMsg } from '../types'
import { toChatItems } from '../utils/chatAdapter'

const props = defineProps<{ messages: LocalMsg[]; isStreaming: boolean }>()
defineEmits<{ openSearchPanel: [] }>()

const chatRef = ref<{ scrollToBottom?: (p?: { behavior: 'auto' | 'smooth' }) => void } | null>(null)
const chatItems = computed(() => toChatItems(props.messages))

function scrollToBottom() {
  chatRef.value?.scrollToBottom?.({ behavior: 'smooth' })
}
defineExpose({ scrollToBottom })
</script>

<template>
  <t-chat
    ref="chatRef"
    :data="chatItems"
    layout="single"
    :clear-history="false"
    :is-stream-load="isStreaming"
    :auto-scroll="true"
    class="chat-view"
  />
</template>

<style scoped>
.chat-view {
  flex: 1;
  min-height: 0;
  width: 100%;
}
/* 消息内容居中成一列（与底部输入框同宽），滚动条仍在右缘 */
.chat-view :deep(.t-chat__list) > * {
  max-width: 820px;
  margin-left: auto;
  margin-right: auto;
}
</style>
