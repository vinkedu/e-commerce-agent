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
    :is-stream-load="isStreaming"
    :auto-scroll="true"
    class="chat-view"
  />
</template>

<style scoped>
.chat-view {
  height: 100%;
  width: 100%;
}
</style>
