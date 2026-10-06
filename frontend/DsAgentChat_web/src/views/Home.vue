<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import AppLayout from '../layouts/AppLayout.vue'
import ConversationSidebar from '../components/ConversationSidebar.vue'
import ChatView from '../components/ChatView.vue'
import RichChatInput from '../components/RichChatInput.vue'
import WelcomeHero from '../components/WelcomeHero.vue'
import { useConversationStore } from '../stores/conversation'
import { ApiService } from '../services/api'
import type { LocalMsg } from '../types'

type Mode = 'standard' | 'reason' | 'search'

const convStore = useConversationStore()
const messages = ref<LocalMsg[]>([])
const isStreaming = ref(false)
const mode = ref<Mode>('standard')
const chatRef = ref<InstanceType<typeof ChatView> | null>(null)

onMounted(() => {
  convStore.loadUserConversations().catch(() => {})
})

async function ensureConversation(): Promise<number> {
  if (convStore.currentConversationId) return convStore.currentConversationId
  return await convStore.createNewConversation()
}

async function onSend(text: string) {
  if (!text.trim() || isStreaming.value) return
  let convId: number
  try {
    convId = await ensureConversation()
  } catch {
    return
  }

  messages.value.push({ role: 'user', content: text })
  const assistant: LocalMsg = { role: 'assistant', content: '', reasoning: '' }
  messages.value.push(assistant)
  isStreaming.value = true

  try {
    const payload = [{ role: 'user' as const, content: text }]
    const reader = await ApiService.chat(payload, convId)
    if (!reader) throw new Error('no reader')
    await ApiService.handleChatStream(reader, (chunk) => {
      if (chunk.type === 'think') assistant.reasoning = chunk.content
      else assistant.content = chunk.content
      nextTick(() => chatRef.value?.scrollToBottom())
    })
  } catch {
    assistant.status = 'error'
    assistant.content = '回复出错，请重试'
  } finally {
    isStreaming.value = false
    convStore.loadUserConversations().catch(() => {})
  }
}

function onStop() {
  isStreaming.value = false
}

function onSelect(_id: number) {
  /* Task 13 接入历史加载 */
}
</script>

<template>
  <AppLayout>
    <template #sidebar>
      <ConversationSidebar @select="onSelect" />
    </template>
    <WelcomeHero
      v-if="messages.length === 0"
      :loading="isStreaming"
      :mode="mode"
      @send="onSend"
      @stop="onStop"
      @update:mode="(m: Mode) => (mode = m)"
    />
    <template v-else>
      <ChatView ref="chatRef" :messages="messages" :is-streaming="isStreaming" />
      <div class="bottom-input">
        <RichChatInput
          :loading="isStreaming"
          :mode="mode"
          @send="onSend"
          @stop="onStop"
          @update:mode="(m: Mode) => (mode = m)"
        />
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
.bottom-input {
  padding: 12px 24px 20px;
  max-width: 820px;
  width: 100%;
  margin: 0 auto;
}
</style>

