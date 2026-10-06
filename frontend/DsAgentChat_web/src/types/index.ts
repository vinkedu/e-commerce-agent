// 创建类型定义文件
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  isSearching?: boolean
}

export interface ChatHistory {
  id: number
  title: string
  time: Date
  messages: ChatMessage[]
}

export interface SearchResult {
  title: string
  url: string
  snippet: string
  date?: string
  source?: string
  isExpanded?: boolean
}

// 本地渲染/流式写入的消息模型（Home 的唯一实时数据源）
export interface LocalMsg {
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  status?: '' | 'error'
} 