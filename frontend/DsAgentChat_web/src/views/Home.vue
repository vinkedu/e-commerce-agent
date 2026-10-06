<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import AppLayout from '../layouts/AppLayout.vue'
import ConversationSidebar from '../components/ConversationSidebar.vue'
import ChatView from '../components/ChatView.vue'
import RichChatInput from '../components/RichChatInput.vue'
import WelcomeHero from '../components/WelcomeHero.vue'
import SearchResultPanel from '../components/SearchResultPanel.vue'
import { useConversationStore } from '../stores/conversation'
import { ApiService } from '../services/api'
import { toLocalMsg } from '../utils/chatAdapter'
import type { LocalMsg, SearchResult } from '../types'

type Mode = 'standard' | 'reason' | 'search'

const convStore = useConversationStore()
const messages = ref<LocalMsg[]>([])
const isStreaming = ref(false)
const mode = ref<Mode>('standard')
const chatRef = ref<InstanceType<typeof ChatView> | null>(null)
const searchResults = ref<SearchResult[]>([])
const searchPanelVisible = ref(false)

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
  messages.value.push({ role: 'assistant', content: '', reasoning: '' })
  // 取回响应式代理元素（而非原始对象），后续流式 mutate 才能触发重渲染
  const assistant = messages.value[messages.value.length - 1]
  isStreaming.value = true

  try {
    const payload = [{ role: 'user' as const, content: text }]
    if (mode.value === 'search') {
      const reader = await ApiService.search(payload, convId)
      if (!reader) throw new Error('no reader')
      await handleSearchStream(reader, assistant)
    } else {
      const reader =
        mode.value === 'reason'
          ? await ApiService.reason(payload, convId)
          : await ApiService.chat(payload, convId)
      if (!reader) throw new Error('no reader')
      await ApiService.handleChatStream(reader, (chunk) => {
        if (chunk.type === 'think') assistant.reasoning = chunk.content
        else assistant.content = chunk.content
        nextTick(() => chatRef.value?.scrollToBottom())
      })
    }
  } catch {
    assistant.status = 'error'
    assistant.content = '回复出错，请重试'
  } finally {
    isStreaming.value = false
    convStore.loadUserConversations().catch(() => {})
  }
}

async function handleSearchStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  assistant: LocalMsg,
) {
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    for (const line of decoder.decode(value).split('\n')) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6).trim()
      if (raw === '[DONE]') continue
      try {
        const ev = JSON.parse(raw)
        if (ev.type === 'search_results' && Array.isArray(ev.results)) {
          searchResults.value = ev.results
          assistant.content = `🔍 已找到 ${ev.results.length} 条结果，点击右上角「查看搜索结果」`
        } else if (ev.type === 'direct_content' || ev.content) {
          assistant.content = ev.content ?? assistant.content
        }
      } catch {
        /* 非 JSON 行忽略 */
      }
      nextTick(() => chatRef.value?.scrollToBottom())
    }
  }
}

function onStop() {
  isStreaming.value = false
}

async function onSelect(id: number) {
  if (isStreaming.value) isStreaming.value = false // 中断旧流式
  try {
    await convStore.loadConversationMessages(id)
    messages.value = convStore.currentMessages.map(toLocalMsg)
  } catch {
    messages.value = []
  }
  searchPanelVisible.value = false
  searchResults.value = []
  mode.value = 'standard'
  nextTick(() => chatRef.value?.scrollToBottom())
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
      <div v-if="searchResults.length" class="chat-topbar">
        <t-button variant="outline" size="small" @click="searchPanelVisible = true">
          查看搜索结果（{{ searchResults.length }}）
        </t-button>
      </div>
      <ChatView
        ref="chatRef"
        :messages="messages"
        :is-streaming="isStreaming"
        @open-search-panel="searchPanelVisible = true"
      />
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
    <SearchResultPanel v-model:visible="searchPanelVisible" :results="searchResults" />
  </AppLayout>
</template>

<style scoped>
.chat-topbar {
  display: flex;
  justify-content: flex-end;
  padding: 8px 24px 0;
}
.bottom-input {
  padding: 12px 24px 20px;
  max-width: 820px;
  width: 100%;
  margin: 0 auto;
}
</style>

