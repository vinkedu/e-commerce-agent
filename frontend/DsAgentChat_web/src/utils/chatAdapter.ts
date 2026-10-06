import type { LocalMsg } from '../types'
import type { Message } from '../services/api'
import type { TdChatItemMeta, AIMessageContent } from '@tdesign-vue-next/chat'

/**
 * 本地消息 → TDesign Chat 的 data 项。
 *
 * 关键事实（Task 1 装包核对，权威来源 @tdesign/ai-chat-engine 的 .d.ts）：
 * - content 是「内容块数组」，不是字符串。
 * - 助手思维链用 { type:'thinking', data:{ text } } 块，排在 markdown 块之前，
 *   由 <t-chat> 原生渲染成折叠面板（TdChatItemMeta 没有 reasoning 字段）。
 * - 用户消息用 { type:'text' }，助手正文用 { type:'markdown' }（走内置 marked + 清理）。
 */
export function toChatItems(msgs: LocalMsg[]): TdChatItemMeta[] {
  return msgs.map((m): TdChatItemMeta => {
    if (m.role === 'user') {
      return {
        role: 'user',
        name: '我',
        content: [{ type: 'text', data: m.content }],
      }
    }
    const content: AIMessageContent[] = []
    if (m.reasoning) {
      content.push({ type: 'thinking', data: { title: '思考过程', text: m.reasoning } })
    }
    // 错误态用「内容块级」status（item 级 status 会触发 chat-list 的优先级 bug，
    // 任何真值 item.status 都被判成 'pending' → 整条渲染成骨架条）。
    content.push({
      type: 'markdown',
      data: m.content,
      status: m.status === 'error' ? 'error' : undefined,
    })
    // 注意：不设 item 级 status，否则 completed 消息也会被当 pending 显示骨架。
    return {
      role: 'assistant',
      name: 'AssistGen 助手',
      content,
    }
  })
}

/**
 * 后端历史 Message → 本地 LocalMsg。
 * sender 映射 role；message_type==='think' 的历史消息归入 reasoning。
 */
export function toLocalMsg(m: Message): LocalMsg {
  const role: LocalMsg['role'] = m.sender === 'user' ? 'user' : 'assistant'
  if (role === 'assistant' && m.message_type === 'think') {
    return { role, content: '', reasoning: m.content }
  }
  return { role, content: m.content }
}
