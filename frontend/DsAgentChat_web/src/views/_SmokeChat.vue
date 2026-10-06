<script setup lang="ts">
// 临时冒烟组件：验证 TDesign Chat 真实 API（内容块数组 / 主题 / 发送）。Task 1 结束后删除。
import { ref } from 'vue'
import type { TdChatItemMeta } from '@tdesign-vue-next/chat'

const data = ref<TdChatItemMeta[]>([
  {
    role: 'user',
    name: '我',
    content: [{ type: 'text', data: '帮我写一个 Hello World，并解释一下。' }],
  },
  {
    role: 'assistant',
    name: 'AssistGen 助手',
    content: [
      { type: 'thinking', data: { title: '思考过程', text: '用户想要一个最小示例，用 JS 演示最直接。' } },
      {
        type: 'markdown',
        data: '## Hello World\n\n```js\nconsole.log("Hello World")\n```\n\n- 这是**最小**示例\n- 用 `console.log` 输出',
      },
    ],
    status: 'complete',
  },
])

const loading = ref(false)
function onSend(value: string) {
  if (!value.trim()) return
  data.value.push({ role: 'user', name: '我', content: [{ type: 'text', data: value }] })
  loading.value = true
  setTimeout(() => {
    data.value.push({
      role: 'assistant',
      name: 'AssistGen 助手',
      content: [{ type: 'markdown', data: `收到：${value}` }],
      status: 'complete',
    })
    loading.value = false
  }, 600)
}
</script>

<template>
  <div class="smoke-wrap">
    <div class="smoke-head">TDesign Chat 冒烟（绿色主题）</div>
    <t-chat :data="data" layout="single" :is-stream-load="loading" class="smoke-chat" />
    <t-chat-sender
      :loading="loading"
      placeholder="输入消息，Enter 发送…"
      class="smoke-sender"
      @send="onSend"
    />
  </div>
</template>

<style scoped>
.smoke-wrap {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 860px;
  margin: 0 auto;
  padding: 16px;
  box-sizing: border-box;
}
.smoke-head {
  font-size: 16px;
  font-weight: 600;
  color: var(--td-brand-color);
  padding: 8px 0;
}
.smoke-chat {
  flex: 1;
  min-height: 0;
}
.smoke-sender {
  margin-top: 12px;
}
</style>
