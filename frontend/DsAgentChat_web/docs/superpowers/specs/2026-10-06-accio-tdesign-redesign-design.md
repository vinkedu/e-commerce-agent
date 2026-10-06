# AssistGen 前端 Accio 风格重构设计（TDesign Chat）

> 日期：2026-10-06
> 范围：**子项目一 = 地基层 + Home 主聊天页**。电商页、登录页后续各自独立 spec，复用同一地基。
> 状态：设计待评审

## 1. 背景与目标

### 1.1 问题
现有前端 `frontend/DsAgentChat_web` 是深色极客风聊天应用，`Home.vue` 单文件 3362 行、技术债明显（孤儿 `Sidebar.vue`、未用的 `DOMPurify`、死代码 `handleSubmit`、双 axios 栈、`v-html` 无 XSS 清洗）。目标是改成 **Accio Work 风格**（浅色 + 绿色品牌色、两栏布局、welcome 居中大输入框、富输入框），并用腾讯 **TDesign Chat**（`@tdesign-vue-next/chat@0.7.0`）接管对话渲染与输入。

### 1.2 四项设计基准（已与用户确认）
1. **范围**：三页全改，拆成 Home → 电商 → 登录 三个子项目，本 spec 只做 Home + 地基。
2. **配色**：浅色 + 绿色品牌色，重写全部深色 CSS，TDesign 主色由蓝改绿。
3. **还原程度**：学 Accio 外壳 + 核心交互（两栏/welcome 居中大输入框/富输入框），现有三模式（chat/reason/search）映射成「标准∨」模式下拉，**不做**场景 Tab 与电商选品工作流。
4. **功能取舍**：保留能跑的（三模式聊天、搜索结果面板、会话历史增删改、think 渲染），丢弃死代码。

### 1.3 成功标准
- Home 页呈现 Accio 风格：浅色绿调、左侧栏（Logo + 导航 + 任务历史 + 用户信息）、右主区（welcome 居中大输入框 / 对话态消息流 + 底部富输入框）。
- 三模式经「标准∨」下拉切换，流式输出、思维链折叠、联网搜索结果面板均正常。
- 会话历史增删改可用。
- `npm run build` 与 `npm run type-check` 通过。
- 死代码（孤儿 Sidebar、遗留 api/index.ts + api/conversation.ts、未用依赖）清除。

## 2. 架构分层

重构只换「渲染层」，不碰「数据层」。`services/`、`stores/` 保持不动——它们是正常工作的业务逻辑，与 UI 无关。TDesign Chat 只接管 messages 渲染和输入框，数据来源仍走原 service。这是「最小影响」原则的直接体现，也是风险最低的路径。

```
视图层    Home.vue（用 AppLayout 包裹）
  │
组件层    AppLayout + ConversationSidebar + ChatView + RichChatInput + SearchResultPanel + WelcomeHero
  │
状态层    stores/conversation.ts + stores/user.ts        ← 不动
服务层    services/api.ts (ApiService + AuthService)       ← 不动
         services/axios.ts                                ← 不动
```

### 2.1 依赖安装
```
tdesign-vue-next@^1          # 基础组件库（peer dep，提供 Button/Avatar/Dropdown/Textarea 等）
@tdesign-vue-next/chat@0.7.0 # AI 聊天组件（自带 marked/highlight.js/clipboard/zod 等）
```
Home 重构后移除：`markdown-it`、`@types/markdown-it`、`marked`、`dompurify`、`@types/dompurify`（登录/电商页清理后再从 package.json 统一删，避免中途其他页面还在引用）。

### 2.2 全局注册（main.ts）
```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

import TDesign from 'tdesign-vue-next'
import 'tdesign-vue-next/es/style/index.css'
import TDesignChat from '@tdesign-vue-next/chat'
import '@tdesign-vue-next/chat/es/style/index.css'
import './styles/theme-accio.css'   // 绿色品牌 token 覆盖（必须在 TDesign 样式之后）

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(TDesign)
app.use(TDesignChat)
app.mount('#app')
```

### 2.3 地基层新增/修改文件
| 文件 | 动作 | 职责 |
|---|---|---|
| `src/main.ts` | 改 | 注册 TDesign + Chat + 主题 |
| `src/layouts/AppLayout.vue` | 新增 | 两栏外壳：左侧栏 slot + 右主区 slot |
| `src/styles/theme-accio.css` | 新增 | 覆盖 TDesign CSS 变量（主色蓝→绿）、强制浅色 |
| `index.html` | 改 | title 保持 AssistGen；移除深色 body 背景（若有） |

### 2.4 孤儿与死代码清理（本次 Home 范围内）
删除：
- `src/components/Sidebar.vue`（孤儿，跳转不存在的 `/chat/:id`，走遗留 axios）
- `src/api/index.ts` + `src/api/conversation.ts`（遗留裸 axios 栈，仅被孤儿 Sidebar 引用）

新的 `ConversationSidebar.vue` 直接用 `conversationStore`，不碰遗留那套。
`MessageBox.vue` **保留**（Login.vue 在用，属登录页子项目）。

## 3. 组件拆分

把 3362 行的 `Home.vue` 拆成聚焦组件，每个单一职责、通过明确接口通信、可独立理解。

### 3.1 AppLayout.vue（地基，三页复用）
- **职责**：两栏骨架。左 `aside`（固定宽，可折叠）+ 右 `main`（flex 填充）。
- **接口**：具名插槽 `#sidebar`、`#default`（主区）。无业务逻辑。
- **依赖**：无（纯布局 + 主题变量）。

### 3.2 ConversationSidebar.vue
- **职责**：Accio 风左侧栏——顶部 Logo「AssistGen」+ 折叠按钮；主导航（新会话按钮）；「任务历史」= 会话列表（时间戳）；底部用户信息（头像 + 名字）。
- **接口（props/emit）**（定死，不两可）：
  - 读 `conversationStore.conversations` / `currentConversationId`、`userStore.username`
  - **重命名/删除/新建直接调 `conversationStore` 对应 action**（store action 内已含列表刷新，无需 Home 中转）
  - **仅 emit `select(id)`**：由 Home 响应——加载该会话消息并同步进本地 `messages`（见 §4.2.1），因为切换会话要重置流式态、关闭搜索面板等页面级副作用，必须由编排层 Home 处理
- **交互**：重命名用 `t-dialog` + `t-input`；删除用 `t-popconfirm`；取代原 Home 内联的 modal/confirm。
- **依赖**：`conversationStore`、`userStore`、TDesign Button/Dialog/Popconfirm/Avatar。

### 3.3 ChatView.vue
- **职责**：对话态消息渲染区。包 `<t-chat>`，用 `data` 驱动，`layout="single"`（Accio 是单侧通栏块，非左右气泡），`isStreamLoad` 控制流式骨架。
- **接口**：
  - props：`messages: TdChatItemMeta[]`、`isStreaming: boolean`
  - 通过 ref 暴露/调用 `<t-chat>` 实例的 `scrollToBottom()`
  - 思维链用 `reasoning` slot → `<t-chat-reasoning>`；操作栏用 `<t-chat-action>`（复制/重新生成）
  - 联网搜索结果：assistant 消息 content 内嵌「点击查看结果」触发器 → emit `openSearchPanel(results)`
- **依赖**：`@tdesign-vue-next/chat`。

### 3.4 RichChatInput.vue
- **职责**：Accio 风富输入框。包 `<t-chat-sender>`，`loading` 绑流式状态，`onSend`/`onStop` 回调。
- **接口**：
  - props：`loading: boolean`、`mode: 'standard'|'reason'|'search'`
  - emit `send(text)`、`stop`、`update:mode`
  - `suffix` 插槽放：模式下拉（`t-dropdown`「标准∨」映射 chat/reason/search）、发送/停止按钮
  - `footerPrefix` 插槽放：`+`、插件入口（占位，后端无则 disabled + tooltip 说明）
- **依赖**：`@tdesign-vue-next/chat`、TDesign Dropdown/Button。

### 3.5 WelcomeHero.vue
- **职责**：welcome 态（无消息时）——居中助手介绍（头像 + 「AssistGen 助手」+ 一句话简介）+ 居中大号 `RichChatInput`。有消息后隐藏，输入框移到底部。
- **接口**：props `visible: boolean`；复用 `RichChatInput`（同一组件，容器定位不同）。

### 3.6 SearchResultPanel.vue
- **职责**：联网搜索结果右侧抽屉面板（TDesign Chat 无内置，保留自定义）。用 `t-drawer` 承载，列表 + 展开 + 详情二级。
- **接口**：props `visible`、`results: SearchResult[]`、`selected`；emit `close`、`select(result)`。
- **依赖**：TDesign Drawer/List，`types/index.ts` 的 `SearchResult`。

### 3.7 Home.vue（重构后，瘦身为编排层）
- **职责**：组装上述组件 + 持有页面级状态与业务编排（sendMessage、流式驱动、模式状态、搜索事件解析）。目标行数：< 400 行（script + template）。
- **结构**：
```
<AppLayout>
  <template #sidebar><ConversationSidebar .../></template>
  <WelcomeHero v-if="messages.length===0" .../>
  <ChatView v-else :messages :is-streaming />
  <RichChatInput v-model:mode @send @stop />   <!-- welcome 态内嵌于 Hero -->
  <SearchResultPanel v-model:visible :results />
</AppLayout>
```

## 4. 数据流与状态

### 4.1 消息数据模型适配（关键集成点）
> ✅ **已装包核对（Task 1，权威来源 `@tdesign/ai-chat-engine/dist/index.d.mts` + `@tdesign-vue-next/chat/es/type.d.ts`）**：content **确为内容块数组 `{type,data}`，不是字符串**；`TdChatItemMeta` **没有 `reasoning` 字段**（之前设计有误）。

TDesign Chat 的 `<t-chat>` 吃 `data: TdChatItemMeta[]`（真实签名）：
```ts
interface TdChatItemMeta {
  avatar?: string
  name?: string
  role?: ChatMessageRole                               // 'user' | 'assistant' | 'system'
  datetime?: string
  content?: AIMessageContent[] | UserMessageContent[]  // 内容块数组（无字符串重载）
  status?: ChatMessageStatus                           // 'pending'|'streaming'|'complete'|'stop'|'error'
}
```
内容块（`ChatBaseContent<T, TData> = { type: T; data: TData; status?; id?; strategy?; ext? }`）：
```ts
type TextContent     = { type: 'text';     data: string }
type MarkdownContent = { type: 'markdown'; data: string }
type ThinkingContent = { type: 'thinking'; data: { text?: string; title?: string } }
type SearchContent   = { type: 'search';   data: { title?: string; references?: ReferenceItem[] } }
// ReferenceItem = { title; url?; content?; site?; icon?; type?; date? }
```
现有 Home 的消息是 `{ role, content: string, thinking?: string }`。需要**适配函数** `toChatItems(messages): TdChatItemMeta[]`，把本地消息映射成 TDesign 块数组格式：
- 用户消息 → `content: [{ type:'text', data: m.content }]`
- 助手消息 → `content: [ ...(reasoning ? [{type:'thinking', data:{text: reasoning}}] : []), { type:'markdown', data: m.content } ]`
- `status` 用 `'error'` 标错误态；流式途中可用 `'streaming'`。

> 影响：Task 2 适配器按上述块数组实现（**非**字符串直填、**非** `reasoning: true` 布尔）。思维链不再走 `reasoning` slot，改由 `thinking` 内容块原生渲染（见 §4.4）。

### 4.1.1 本地 messages 与 store.currentMessages 的分工（定死）
- Home 持有本地 `messages = ref<LocalMsg[]>`，**作为渲染与流式写入的唯一数据源**（流式逐字追加需高频 mutate，走本地 ref 最直接）。
- `conversationStore.currentMessages` 仅用于**从后端拉取的历史**。切换会话时（见下）把它一次性映射进本地 `messages`，之后流式只动本地 `messages`，不回写 store。
- 职责边界：store 管「会话列表 + 持久化历史」，本地 `messages` 管「当前对话的实时渲染」。

### 4.2.1 切换/加载历史会话
Home 响应侧栏的 `select(id)`：
```
onSelectConversation(id):
  1. 若正在流式：中断（见停止逻辑）
  2. await conversationStore.loadConversationMessages(id)   // 填充 store.currentMessages
  3. messages.value = store.currentMessages.map(toLocalMsg)  // 同步进本地渲染源
  4. 关闭 SearchResultPanel、清 searchResults、mode 回 'standard'
  5. nextTick → chatRef.scrollToBottom()
```

### 4.2 流式驱动
保留 `ApiService.handleChatStream(reader, onChunk)` 不变。改动在 Home 的编排：
```
sendMessage(text):
  1. 确保 conversationId（无则 conversationStore.createNewConversation()）
  2. messages.push({ role:'user', content:text })
  3. isStreaming = true
  4. 按 mode 选接口：
     - standard → ApiService.chat(msgs, convId)
     - reason   → ApiService.reason(msgs, convId)
     - search   → ApiService.search(msgs, convId)  → 走 handleSearch 分支
  5. messages.push({ role:'assistant', content:'', reasoning:... })  // 空助手占位
  6. handleChatStream(reader, onChunk):
       chunk.type==='think'    → 写入当前助手消息的 reasoning 内容
       chunk.type==='response' → 写入当前助手消息的 content
     每次更新后 chatRef.scrollToBottom()
  7. 结束：isStreaming=false；conversationStore.loadUserConversations() 刷新列表
```

### 4.3 模式状态收敛
现有 `isDeepThinking` + `isSearching` 两个互斥布尔 → 收敛成单一 `mode = ref<'standard'|'reason'|'search'>('standard')`，由「标准∨」下拉驱动。消除两布尔互斥的隐患。

### 4.4 思维链渲染
> ✅ 已核对：`<t-chat>` 的 `reasoning` 是**自定义渲染函数(TNode)**，不是布尔开关；思维链的原生渲染靠 **`thinking` 内容块**（`{type:'thinking', data:{text}}`），由 `<t-chat>` 默认内容渲染成折叠面板。

深度推理模式：`chunk.type==='think'` 的内容写进本地消息的 `reasoning` 字段，适配器把它转成助手消息 content 数组里的 `thinking` 块（排在 `markdown` 块之前）。**删除**原来的 `### 思考过程 + ---` 字符串拼接 hack 和 `renderMessage` 的 split 解析。

### 4.5 联网搜索
`handleSearch` 解析 JSON 事件（`search_start`/`search_results`/`direct_content`）的逻辑保留，但：
- 结果存入 `searchResults: SearchResult[]`
- 助手消息 content 内渲染「🔍 点击查看 N 条结果」触发块
- 点击 → `SearchResultPanel` 抽屉打开（`t-drawer`），取代原内联面板

### 4.6 Markdown 与 XSS
TDesign Chat 的 `<t-chat-content>` 内置 marked 引擎渲染 markdown，并自带清理。**删除** `v-html` + markdown-it + 手搓 renderMessage。这顺带修掉现有「DOMPurify 装了没用、v-html 无清理」的 XSS 隐患。

## 5. 主题（绿色品牌色）

TDesign 用 CSS 变量定义品牌色阶 `--td-brand-color-1..10`，默认蓝。Accio 主色是绿。`theme-accio.css` 覆盖这组变量即可全局换色，无需改组件。

```css
/* src/styles/theme-accio.css —— 必须在 TDesign 样式之后引入 */
:root {
  /* 绿色品牌色阶（基准 --td-brand-color = 7 档主色，近 Accio 的绿 #07c160 系） */
  --td-brand-color-1:  #e3f9eb;
  --td-brand-color-2:  #c4f0d3;
  --td-brand-color-3:  #93e3b0;
  --td-brand-color-4:  #5fd38b;
  --td-brand-color-5:  #34c171;
  --td-brand-color-6:  #16b162;   /* hover */
  --td-brand-color-7:  #07a452;   /* 主色 brand */
  --td-brand-color-8:  #059148;
  --td-brand-color-9:  #047a3d;
  --td-brand-color-10: #036330;
  --td-brand-color: var(--td-brand-color-7);
  --td-brand-color-hover: var(--td-brand-color-6);
  --td-brand-color-active: var(--td-brand-color-8);
  --td-brand-color-focus: var(--td-brand-color-2);
  --td-brand-color-light: var(--td-brand-color-1);
}
```
> 具体色值在实现期对照 Accio 截图微调（取色自截图里的发送按钮/激活标签绿）。
- **强制浅色**：移除 `App.vue` 里 `#app` / `.loading-screen` 的深色背景；`userStore.theme` 默认 `'light'`，`toggleTheme` 保留但本子项目不接深色（深色留给「深浅双主题」若未来需要）。
- 侧栏背景用极浅灰 `--td-bg-color-container`，主区白 `--td-bg-color-page`，细线 `--td-component-stroke`。

## 6. 错误处理
- **流式异常**：`handleChatStream` catch → 当前助手消息 `status='error'`，`<t-chat-item>` 以 error 变体渲染，content 显示「回复出错，请重试」。
- **401**：`services/axios.ts` 拦截器已处理（清 token + 跳 login），不变。`ApiService` 的 fetch 分支（chat/reason/search）需补 `response.status===401` 时同样跳转（现有 fetch 分支未处理 401，是潜在缺口，本次顺带补）。
- **缺 conversationId**：sendMessage 前确保已创建，失败则 toast（`MessagePlugin.error`）提示，不发送。
- **缺 user_id**：`localStorage.user_id` 缺失 → 跳 login（现有 ApiService 直接抛错，改为优雅跳转）。

## 7. 测试与验证
项目当前**无测试框架**。本次不引入 Vitest（YAGNI，纯 UI 重构，收益低于成本），改为：
1. `npm run type-check`（vue-tsc）通过——保证类型契合，尤其 TDesign Chat 的 props/消息模型。
2. `npm run build` 通过。
3. `npm run dev` 手动验证清单：
   - [ ] welcome 态居中大输入框显示，浅色绿调
   - [ ] 发消息 → 流式输出逐字渲染 + 自动滚动
   - [ ] 「标准∨」切 深度推理 → 思维链折叠面板正常
   - [ ] 「标准∨」切 联网搜索 → 结果触发块 + 抽屉面板
   - [ ] 会话历史：新建 / 切换 / 重命名 / 删除
   - [ ] markdown 渲染正常，无 XSS（`<script>` 被转义/清理）
   - [ ] 刷新保持登录态，401 跳登录

> 若装包后发现 TDesign Chat 运行时行为与 tarball 类型推断不符（slot 名、事件 payload），以运行时为准修正，并回填本 spec。

## 8. 风险
| 风险 | 应对 |
|---|---|
| TDesign Chat API 仅从 tarball `.d.ts` 确认，未跑过运行时 | 实现第一步装包 + 跑最小 demo 冒烟，验证 `<t-chat>`/`<t-chat-sender>`/`<t-chat-reasoning>` 的 slot 与事件；偏差即修正 spec |
| `AIMessageContent`/`UserMessageContent` 内容块结构未定 | 装包后查 `@tdesign/web-components-chat` 的 `.d.ts`；适配函数以此为准 |
| 联网搜索无内置 UI，需自定义嵌入 | 用 content 自定义触发块 + `t-drawer`，与 `<t-chat>` 解耦 |
| 绿色色阶与 Accio 不完全一致 | 对照截图取色微调，非阻塞 |
| 构建产物需手动拷到后端 static | 遵 readme：`npm run build` 后 `dist/` → `backend/deepseek_agent/llm_backend/static` |

## 9. 实施顺序（供 writing-plans 细化）
1. **地基**：装依赖 → main.ts 注册 → theme-accio.css → 跑最小 `<t-chat>` demo 冒烟（验证 API）。
2. **AppLayout** + **ConversationSidebar**（接 conversationStore）。
3. **ChatView**（`<t-chat>` + reasoning + action）+ 适配函数。
4. **RichChatInput**（sender + 模式下拉）+ **WelcomeHero**。
5. **Home.vue 编排**：接线 sendMessage/流式/模式/搜索；**SearchResultPanel**。
6. 删死代码（Sidebar.vue、api/index.ts、api/conversation.ts）。
7. `type-check` + `build` + 手动验证清单。

## 10. 不在本 spec 范围
- 电商客服页（EcommerceService.vue）重构 —— 子项目二，独立 spec。
- 登录注册页（Login.vue）重构 —— 子项目三，独立 spec。
- RAG 知识库问答接通（现为死按钮，本次仅移除死按钮，不接通）。
- 深色主题适配。
- 从 package.json 删除 markdown-it/marked/dompurify（待三页都不引用后统一删）。




