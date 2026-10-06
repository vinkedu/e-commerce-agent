# AssistGen Home 页 Accio 风格重构实现计划（TDesign Chat）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Home 主聊天页从 3362 行深色巨石重构为 Accio Work 风格（浅色 + 绿色、两栏布局、welcome 居中大输入框、富输入框），对话渲染与输入改用 TDesign Chat 组件，拆成聚焦组件，并清除死代码。

**Architecture:** 只换「渲染层」，不碰「数据层」。`services/`、`stores/` 原样保留（仅 api.ts 补 401 处理）。`<t-chat>` 系列接管 messages 渲染与输入框；Home 瘦身为编排层，持有本地 `messages` ref 作为流式/渲染唯一数据源，store 只管会话列表与历史持久化。

**Tech Stack:** Vue 3.3 `<script setup lang="ts">`、Pinia 2、vue-router 4、TypeScript 5、Vite 5、`tdesign-vue-next@^1`、`@tdesign-vue-next/chat@0.7.0`。

**Spec:** `docs/superpowers/specs/2026-10-06-accio-tdesign-redesign-design.md`（计划论据以该 spec 为准，执行者需同时阅读）。

## Global Constraints

- 技术栈版本：Vue `^3.3.11`、TypeScript `^5.2.2`、Vite `^5.0.8`（现有，不升级）。
- 新增依赖精确值：`tdesign-vue-next@^1`、`@tdesign-vue-next/chat@0.7.0`（peer 要求 `tdesign-vue-next>=1` + `vue>=3.1.0`，已满足）。
- 配色：浅色 + 绿色品牌色；主色基准 `--td-brand-color = #07a452` 系（实现期对照 Accio 截图取色微调）。
- 不动 `src/stores/`、`src/services/axios.ts`；`src/services/api.ts` 仅允许「补 401 处理 + user_id 缺失优雅跳转」，不改其余逻辑。
- 本次范围仅 **Home + 地基**；**不**删除 package.json 的 `markdown-it`/`marked`/`dompurify`（待三页都不引用后统一删）。
- 验证手段 = `npm run type-check`（vue-tsc）+ `npm run build` + 手动验证清单。**项目无测试框架，本计划不引入**（spec §7 已决策）。
- 构建部署：`npm run build` 后把 `dist/` 拷到 `backend/deepseek_agent/llm_backend/static`（遵 readme，手动，不依赖 git push）。
- 组件全局名：`TChat` / `TChatItem` / `TChatContent` / `TChatSender` / `TChatReasoning` / `TChatAction` / `TChatLoading`（已注册，模板直接用，无需 import）。

## Review Focus

- **流式竞态**：流式进行中切换会话或再次发送 → 旧 reader 未中断会污染新消息。Task 10 的 sendMessage 用 `isStreaming` 锁 + `stopDisabled`，Task 13 切换前先中断。
- **空输入**：空串/纯空格发送 → 必须拦截不发。Task 10 sendMessage 首步 `trim()` 判空。
- **XSS**：markdown 含 `<script>`/恶意 HTML → 必须被 TDesign `<t-chat-content>` 清理，不执行、不裸注入。Task 10 Step 2 手动验证（需完整发送流程）。
- **流式中断/401**：流式途中 401 或网络断 → 渲染错误态而非永久 loading。Task 9 补 fetch 分支 401，Task 10 `handleChatStream` catch → 消息 `status='error'`。
- **超长内容**：长会话历史 / 超长单条消息 → 自动滚动与渲染不卡。Task 5 用 `<t-chat>` 的 `autoScroll` + 实例 `scrollToBottom()`。

---

## 前置：本地 git 检查点（仅本地 commit，绝不 push）

本计划每个 task 结束用本地 `git commit` 做回滚检查点。若 workspace 尚未初始化 git，执行者在开工前于**用户指定的层级**执行一次 `git init`（层级由用户在计划评审时确认：workspace 根 `d:\Agent\code\code` 或 frontend 子目录）。所有命令路径以 frontend 目录 `d:\Agent\code\code\frontend\DsAgentChat_web` 为基准。

---

### Task 1: 地基 — 装依赖 + 注册 TDesign + 绿色主题 + API 冒烟验证

**Files:**
- Modify: `package.json`（加 2 个依赖）
- Modify: `src/main.ts`（注册 TDesign + Chat + 主题）
- Create: `src/styles/theme-accio.css`（绿色 token + 强制浅色）
- Modify: `src/App.vue`（移除深色背景）
- Modify: `index.html`（移除深色 body 背景，若有）
- Create: `src/views/_SmokeChat.vue`（临时冒烟组件，Task 结束前删除）
- Modify: `src/router/index.ts`（临时加 `/smoke` 路由，Task 结束前删除）

**Interfaces:**
- Produces: 全局可用的 `<t-chat>` / `<t-chat-sender>` / `<t-chat-reasoning>` 等组件；绿色主题生效；**冒烟验证产出的事实**（写入 spec §4.1 的内容块结构、slot 名、事件 payload），供 Task 2/5/6 依赖。

- [ ] **Step 1: 安装依赖**

```bash
npm install tdesign-vue-next@^1 @tdesign-vue-next/chat@0.7.0
```
Expected: `package.json` dependencies 新增两项，`npm ls @tdesign-vue-next/chat` 显示 0.7.0。

- [ ] **Step 2: 写绿色主题文件**

`src/styles/theme-accio.css`：
```css
/* 覆盖 TDesign 品牌色阶为绿色；必须在 TDesign 样式之后引入 */
:root {
  --td-brand-color-1:  #e3f9eb;
  --td-brand-color-2:  #c4f0d3;
  --td-brand-color-3:  #93e3b0;
  --td-brand-color-4:  #5fd38b;
  --td-brand-color-5:  #34c171;
  --td-brand-color-6:  #16b162;
  --td-brand-color-7:  #07a452;
  --td-brand-color-8:  #059148;
  --td-brand-color-9:  #047a3d;
  --td-brand-color-10: #036330;
  --td-brand-color: var(--td-brand-color-7);
  --td-brand-color-hover: var(--td-brand-color-6);
  --td-brand-color-active: var(--td-brand-color-8);
  --td-brand-color-focus: var(--td-brand-color-2);
  --td-brand-color-light: var(--td-brand-color-1);
}
html, body, #app { background: var(--td-bg-color-page, #fff); color: var(--td-text-color-primary, #000); }
```

- [ ] **Step 3: 改 main.ts 注册**

`src/main.ts` 全文替换为：
```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

import TDesign from 'tdesign-vue-next'
import 'tdesign-vue-next/es/style/index.css'
import TDesignChat from '@tdesign-vue-next/chat'
import '@tdesign-vue-next/chat/es/style/index.css'
import './styles/theme-accio.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(TDesign)
app.use(TDesignChat)
app.mount('#app')
```

- [ ] **Step 4: 移除 App.vue 深色背景**

`src/App.vue` 的 `<style>` 里把 `.loading-screen { background: #1e1e1e }` 改为 `background: var(--td-bg-color-page, #fff)`；`#app` 保留字体设置，不设深色背景。

- [ ] **Step 5: 写冒烟组件验证真实 API**

`src/views/_SmokeChat.vue`：
```vue
<script setup lang="ts">
import { ref } from 'vue'
const data = ref([
  { role: 'user', content: '你好' },
  { role: 'assistant', content: '## 标题\n- 列表项\n```js\nconsole.log(1)\n```', reasoning: true },
])
const loading = ref(false)
function onSend(v: string) { console.log('send:', v) }
</script>
<template>
  <div style="height:100vh;display:flex;flex-direction:column">
    <t-chat :data="data" layout="single" style="flex:1" />
    <t-chat-sender :loading="loading" placeholder="输入…" @send="onSend" />
  </div>
</template>
```

- [ ] **Step 6: 临时挂路由并跑 dev 验证**

`src/router/index.ts` routes 临时加：`{ path: '/smoke', name: 'smoke', component: () => import('../views/_SmokeChat.vue') }`。
Run: `npm run dev`，浏览器开 `http://localhost:3000/smoke`。
**验证并记录事实**（写进 spec §4.1 的 ⚠️ 注记处）：
  1. `<t-chat>` 的 `data` 项 content 用「纯字符串」能否渲染？还是必须 `AIMessageContent[]` 内容块数组？
  2. markdown（标题/列表/代码块）是否自动渲染高亮？
  3. `reasoning: true` 是否出现折叠面板？
  4. `<t-chat-sender>` 的 `@send` 事件 payload 是不是 `(value, context)`？
  5. 控制台有无组件未注册 / 样式缺失报错。

- [ ] **Step 7: 删除冒烟脚手架**

删除 `src/views/_SmokeChat.vue`，撤销 `src/router/index.ts` 的 `/smoke` 路由。

- [ ] **Step 8: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): 地基-注册 TDesign Chat + 绿色主题 + API 冒烟验证"
```
Expected: type-check 无错；若冒烟发现 API 与 spec 推断不符，先更新 spec §4.1 再提交。

---

### Task 2: 消息适配层 chatAdapter.ts

**Files:**
- Create: `src/utils/chatAdapter.ts`
- Modify: `src/types/index.ts`（加 `LocalMsg` 类型）

**Interfaces:**
- Consumes: Task 1 冒烟确认的内容块结构。
- Produces:
  - `type LocalMsg = { role: 'user'|'assistant'; content: string; reasoning?: string; status?: ''|'error' }`
  - `toChatItems(msgs: LocalMsg[]): TdChatItemMeta[]`（本地 → TDesign）
  - `toLocalMsg(m: Message): LocalMsg`（store 历史 Message → 本地；`Message.sender` 映射 `role`，`message_type==='think'` 归入 reasoning）

- [ ] **Step 1: 定义 LocalMsg 类型**

`src/types/index.ts` 追加：
```ts
export interface LocalMsg {
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  status?: '' | 'error'
}
```

- [ ] **Step 2: 写适配函数**

`src/utils/chatAdapter.ts`（content 块形态以 Task 1 冒烟结论为准，下方按「字符串直填」基线写，若冒烟证明需内容块数组则改为 `[{ type:'text', data: m.content }]`）：
```ts
import type { LocalMsg } from '../types'
import type { Message } from '../services/api'
import type { TdChatItemMeta } from '@tdesign-vue-next/chat'

export function toChatItems(msgs: LocalMsg[]): TdChatItemMeta[] {
  return msgs.map((m) => ({
    role: m.role,
    content: m.content,
    reasoning: m.reasoning ? true : undefined,
    status: m.status || undefined,
    name: m.role === 'user' ? '我' : 'AssistGen 助手',
  })) as TdChatItemMeta[]
}

export function toLocalMsg(m: Message): LocalMsg {
  return {
    role: m.sender === 'user' ? 'user' : 'assistant',
    content: m.content,
  }
}
```

- [ ] **Step 3: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): 消息适配层 chatAdapter + LocalMsg 类型"
```
Expected: type-check 无错。若 `TdChatItemMeta` 的 content 字段类型拒绝字符串，依 Task 1 结论改为内容块数组并重跑。

### Task 3: AppLayout.vue 两栏外壳（地基，三页复用）

**Files:**
- Create: `src/layouts/AppLayout.vue`

**Interfaces:**
- Produces: 具名插槽 `#sidebar`（左栏）+ `#default`（主区）；prop `sidebarCollapsed?: boolean`（默认 false）。

- [ ] **Step 1: 写 AppLayout 组件**

`src/layouts/AppLayout.vue`：
```vue
<script setup lang="ts">
defineProps<{ sidebarCollapsed?: boolean }>()
</script>
<template>
  <div class="app-layout">
    <aside class="app-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <slot name="sidebar" />
    </aside>
    <main class="app-main">
      <slot />
    </main>
  </div>
</template>
<style scoped>
.app-layout { display: flex; height: 100vh; background: var(--td-bg-color-page); }
.app-sidebar {
  width: 260px; flex-shrink: 0; height: 100%;
  background: var(--td-bg-color-container);
  border-right: 1px solid var(--td-component-stroke);
  transition: width .2s ease; overflow: hidden;
}
.app-sidebar.collapsed { width: 0; border-right: none; }
.app-main { flex: 1; min-width: 0; display: flex; flex-direction: column; height: 100%; }
</style>
```

- [ ] **Step 2: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): AppLayout 两栏外壳"
```
Expected: type-check 无错。

---

### Task 4: ConversationSidebar.vue 会话侧栏

**Files:**
- Create: `src/components/ConversationSidebar.vue`

**Interfaces:**
- Consumes: `useConversationStore`（`conversations`/`currentConversationId`/`createNewConversation`/`deleteConversation`/`updateConversationName`/`loadUserConversations`）、`useUserStore`（`username`）、`AuthService.logout`。
- Produces: emit `select(id: number)`（切换会话，由 Home 处理副作用）；新建/删除/重命名**直接调 store action**。

- [ ] **Step 1: 写组件 script**

`src/components/ConversationSidebar.vue` 的 `<script setup lang="ts">`：
```ts
import { ref, onMounted } from 'vue'
import { useConversationStore } from '../stores/conversation'
import { useUserStore } from '../stores/user'
import { AuthService } from '../services/api'

const emit = defineEmits<{ select: [id: number] }>()
const convStore = useConversationStore()
const userStore = useUserStore()

const renameVisible = ref(false)
const renameId = ref<number | null>(null)
const renameText = ref('')

onMounted(() => { convStore.loadUserConversations() })

async function onNew() {
  const id = await convStore.createNewConversation()
  if (id) emit('select', id)
}
function openRename(id: number, cur: string) {
  renameId.value = id; renameText.value = cur || ''; renameVisible.value = true
}
async function confirmRename() {
  if (renameId.value && renameText.value.trim())
    await convStore.updateConversationName(renameId.value, renameText.value.trim())
  renameVisible.value = false
}
async function onDelete(id: number) { await convStore.deleteConversation(id) }
function onLogout() { AuthService.logout() }
```

- [ ] **Step 2: 写组件模板**

```vue
<template>
  <div class="conv-sidebar">
    <div class="conv-head">
      <span class="logo">AssistGen</span>
    </div>
    <t-button theme="primary" block @click="onNew" class="new-btn">+ 新会话</t-button>
    <div class="conv-section-title">任务历史</div>
    <ul class="conv-list">
      <li v-for="c in convStore.conversations" :key="c.id"
          :class="{ active: c.id === convStore.currentConversationId }"
          @click="emit('select', c.id)">
        <span class="conv-title">{{ c.title || '新会话' }}</span>
        <span class="conv-actions" @click.stop>
          <t-button variant="text" size="small" @click="openRename(c.id, c.title)">改名</t-button>
          <t-popconfirm content="确定删除该会话？" @confirm="onDelete(c.id)">
            <t-button variant="text" size="small" theme="danger">删除</t-button>
          </t-popconfirm>
        </span>
      </li>
    </ul>
    <div class="conv-foot">
      <t-avatar size="small">{{ (userStore.username || 'U').charAt(0) }}</t-avatar>
      <span class="uname">{{ userStore.username || '用户' }}</span>
      <t-button variant="text" size="small" @click="onLogout">退出</t-button>
    </div>
    <t-dialog v-model:visible="renameVisible" header="重命名会话" @confirm="confirmRename">
      <t-input v-model="renameText" placeholder="输入会话名称" />
    </t-dialog>
  </div>
</template>
```

- [ ] **Step 3: 写样式**

```vue
<style scoped>
.conv-sidebar { display: flex; flex-direction: column; height: 100%; padding: 12px; box-sizing: border-box; }
.conv-head { display: flex; align-items: center; padding: 8px 4px 16px; }
.logo { font-size: 18px; font-weight: 600; color: var(--td-text-color-primary); }
.new-btn { margin-bottom: 16px; }
.conv-section-title { font-size: 12px; color: var(--td-text-color-placeholder); padding: 4px; }
.conv-list { list-style: none; margin: 0; padding: 0; flex: 1; overflow-y: auto; }
.conv-list li { display: flex; align-items: center; justify-content: space-between;
  padding: 8px; border-radius: 6px; cursor: pointer; }
.conv-list li:hover { background: var(--td-bg-color-container-hover); }
.conv-list li.active { background: var(--td-brand-color-light); }
.conv-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.conv-actions { display: none; }
.conv-list li:hover .conv-actions { display: inline-flex; }
.conv-foot { display: flex; align-items: center; gap: 8px; padding-top: 12px;
  border-top: 1px solid var(--td-component-stroke); }
.uname { flex: 1; font-size: 14px; }
</style>
```

- [ ] **Step 4: dev 验证 + type-check + 提交**

Run: `npm run dev`（临时在 Home 或 smoke 路由挂载验证渲染；若 Home 尚未改，可临时在 `_SmokeChat` 恢复验证后再删）。确认：列表渲染、新建、改名弹窗、删除确认、退出登录可点。
```bash
npm run type-check
git add -A && git commit -m "feat(home): ConversationSidebar 会话侧栏"
```

---

### Task 5: ChatView.vue 对话渲染区

**Files:**
- Create: `src/components/ChatView.vue`

**Interfaces:**
- Consumes: `toChatItems`（Task 2）、`LocalMsg`（Task 2）、`<t-chat>`/`<t-chat-reasoning>`/`<t-chat-action>`。
- Produces: props `messages: LocalMsg[]`、`isStreaming: boolean`；暴露方法 `scrollToBottom()`（转调 `<t-chat>` 实例）；emit `openSearchPanel()`（搜索触发块点击，Task 12 接线）。

- [ ] **Step 1: 写组件 script**

`src/components/ChatView.vue` 的 `<script setup lang="ts">`：
```ts
import { ref } from 'vue'
import type { LocalMsg } from '../types'
import { toChatItems } from '../utils/chatAdapter'

const props = defineProps<{ messages: LocalMsg[]; isStreaming: boolean }>()
defineEmits<{ openSearchPanel: [] }>()

const chatRef = ref<any>(null)
function scrollToBottom() { chatRef.value?.scrollToBottom?.({ behavior: 'smooth' }) }
defineExpose({ scrollToBottom })
```
> `chatItems` 用 computed 包裹 `toChatItems(props.messages)`（在 script 内加 `import { computed } from 'vue'` 与 `const chatItems = computed(() => toChatItems(props.messages))`）。

- [ ] **Step 2: 写组件模板**

```vue
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
.chat-view { height: 100%; width: 100%; }
</style>
```
> 若 Task 1 冒烟证明 reasoning / action 需要显式 slot，在此补 `<template #reasoning="{ item }">…</template>` 与 `<template #actions>…</template>`；否则依赖 `<t-chat>` 默认渲染。以冒烟结论为准。

- [ ] **Step 3: XSS 手动验证（dev）**

临时在父组件传入 `messages=[{role:'assistant', content:'<script>alert(1)<\/script> <img src=x onerror=alert(2)> **bold**'}]`，`npm run dev` 确认：脚本不执行、`<img onerror>` 不触发、`**bold**` 正常加粗。验证后撤销临时数据。

- [ ] **Step 4: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): ChatView 对话渲染区 + XSS 验证"
```

### Task 6: RichChatInput.vue 富输入框

**Files:**
- Create: `src/components/RichChatInput.vue`

**Interfaces:**
- Consumes: `<t-chat-sender>`、TDesign `t-dropdown`/`t-button`。
- Produces: props `loading: boolean`、`mode: 'standard'|'reason'|'search'`；emit `send(text: string)`、`stop`、`update:mode(m)`。

- [ ] **Step 1: 写组件 script**

`src/components/RichChatInput.vue` 的 `<script setup lang="ts">`：
```ts
import { ref } from 'vue'
type Mode = 'standard' | 'reason' | 'search'
const props = defineProps<{ loading: boolean; mode: Mode }>()
const emit = defineEmits<{ send: [text: string]; stop: []; 'update:mode': [m: Mode] }>()

const draft = ref('')
const MODE_LABEL: Record<Mode, string> = { standard: '标准', reason: '深度推理', search: '联网搜索' }

function onSend(value: string) {
  const t = (value ?? draft.value).trim()
  if (!t || props.loading) return
  emit('send', t); draft.value = ''
}
function onStop() { emit('stop') }
function pickMode(m: Mode) { emit('update:mode', m) }
```

- [ ] **Step 2: 写组件模板**

```vue
<template>
  <t-chat-sender
    v-model="draft"
    :loading="loading"
    placeholder="输入消息，Enter 发送"
    @send="onSend"
    @stop="onStop"
    class="rich-input"
  >
    <template #suffix>
      <t-dropdown :min-column-width="120">
        <t-button variant="text" size="small">{{ MODE_LABEL[mode] }} ▾</t-button>
        <t-dropdown-menu>
          <t-dropdown-item @click="pickMode('standard')">标准</t-dropdown-item>
          <t-dropdown-item @click="pickMode('reason')">深度推理</t-dropdown-item>
          <t-dropdown-item @click="pickMode('search')">联网搜索</t-dropdown-item>
        </t-dropdown-menu>
      </t-dropdown>
    </template>
  </t-chat-sender>
</template>
<style scoped>
.rich-input { width: 100%; }
</style>
```
> slot 名 `#suffix` / `#footerPrefix` 与 `@send` payload 以 Task 1 冒烟结论为准。若 `@send` 不透传 value，改用 `v-model` 的 `draft` 取值（onSend 已兼容两者）。

- [ ] **Step 3: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): RichChatInput 富输入框 + 模式下拉"
```

---

### Task 7: WelcomeHero.vue 欢迎态

**Files:**
- Create: `src/components/WelcomeHero.vue`

**Interfaces:**
- Consumes: `RichChatInput`（Task 6）、TDesign `t-avatar`。
- Produces: props `loading: boolean`、`mode: Mode`；emit `send(text)`、`stop`、`update:mode(m)`（全部透传给内部 RichChatInput）。

- [ ] **Step 1: 写组件**

`src/components/WelcomeHero.vue`：
```vue
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
        :loading="loading" :mode="mode"
        @send="(t) => emit('send', t)"
        @stop="() => emit('stop')"
        @update:mode="(m) => emit('update:mode', m)"
      />
    </div>
  </div>
</template>
<style scoped>
.welcome-hero { flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 24px; padding: 24px; }
.hero-head { text-align: center; }
.hero-title { font-size: 22px; font-weight: 600; margin-top: 12px; color: var(--td-text-color-primary); }
.hero-sub { font-size: 14px; color: var(--td-text-color-secondary); margin-top: 4px; }
.hero-input { width: 100%; max-width: 720px; }
</style>
```

- [ ] **Step 2: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): WelcomeHero 欢迎态居中大输入框"
```

---

### Task 8: SearchResultPanel.vue 搜索结果抽屉

**Files:**
- Create: `src/components/SearchResultPanel.vue`

**Interfaces:**
- Consumes: `SearchResult`（`src/types/index.ts` 已有）、TDesign `t-drawer`。
- Produces: props `visible: boolean`、`results: SearchResult[]`；emit `update:visible(v: boolean)`。

- [ ] **Step 1: 写组件**

`src/components/SearchResultPanel.vue`：
```vue
<script setup lang="ts">
import type { SearchResult } from '../types'
defineProps<{ visible: boolean; results: SearchResult[] }>()
const emit = defineEmits<{ 'update:visible': [v: boolean] }>()
</script>
<template>
  <t-drawer
    :visible="visible" header="联网搜索结果" :footer="false" size="420px"
    @close="emit('update:visible', false)"
  >
    <div v-if="results.length === 0" class="empty">暂无结果</div>
    <ul v-else class="result-list">
      <li v-for="(r, i) in results" :key="i" class="result-item">
        <a :href="r.url" target="_blank" rel="noopener" class="r-title">{{ r.title }}</a>
        <p class="r-snippet">{{ r.snippet }}</p>
        <span class="r-source">{{ r.source || r.url }}</span>
      </li>
    </ul>
  </t-drawer>
</template>
<style scoped>
.empty { color: var(--td-text-color-placeholder); text-align: center; padding: 40px 0; }
.result-list { list-style: none; margin: 0; padding: 0; }
.result-item { padding: 12px 0; border-bottom: 1px solid var(--td-component-stroke); }
.r-title { color: var(--td-brand-color); font-weight: 500; text-decoration: none; }
.r-title:hover { text-decoration: underline; }
.r-snippet { font-size: 13px; color: var(--td-text-color-secondary); margin: 6px 0; }
.r-source { font-size: 12px; color: var(--td-text-color-placeholder); }
</style>
```

- [ ] **Step 2: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): SearchResultPanel 搜索结果抽屉"
```

---

### Task 9: api.ts 补 401 处理 + user_id 缺失优雅跳转

**Files:**
- Modify: `src/services/api.ts`（`ApiService` 的 fetch 分支：createConversation/chat/reason/search/getUserConversations/getConversationMessages）

**Interfaces:**
- Produces: 私有静态助手 `requireUserId(): string`（缺失则跳 login 并抛）、`checkAuth(response: Response): void`（401 清 token + 跳 login）。

- [ ] **Step 1: 加两个私有助手**

在 `ApiService` 类内加（`import router from '../router'` 已存在于文件顶部）：
```ts
private static requireUserId(): string {
  const id = localStorage.getItem('user_id')
  if (!id) { localStorage.removeItem('token'); router.push('/login'); throw new Error('No user_id') }
  return id
}
private static checkAuth(response: Response): void {
  if (response.status === 401) { localStorage.removeItem('token'); router.push('/login') }
}
```

- [ ] **Step 2: 在各 fetch 分支接线**

在 `chat`/`reason`/`search`/`createConversation` 里，把 `localStorage.getItem('user_id')` 取值改为 `this.requireUserId()`；在每个 `const response = await fetch(...)` 之后、`if (!response.ok)` 之前插入 `this.checkAuth(response)`。其余逻辑不变。

- [ ] **Step 3: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "fix(api): fetch 分支补 401 跳转 + user_id 缺失优雅处理"
```

### Task 10: Home.vue 编排 — 外壳 + 标准聊天垂直切片

**Files:**
- Modify: `src/views/Home.vue`（整体重写为编排层，目标 < 400 行）

**Interfaces:**
- Consumes: `AppLayout`/`ConversationSidebar`/`ChatView`/`RichChatInput`/`WelcomeHero`（Task 3-7）、`useConversationStore`、`ApiService.chat`/`handleChatStream`、`LocalMsg`。
- Produces: 可用的标准聊天页（welcome → 发送 → 流式 → 对话态）。reason/search 留 Task 11/12。

- [ ] **Step 1: 写 Home script（标准聊天）**

`src/views/Home.vue` 的 `<script setup lang="ts">`：
```ts
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

onMounted(() => { convStore.loadUserConversations() })

async function ensureConversation(): Promise<number> {
  if (convStore.currentConversationId) return convStore.currentConversationId
  return await convStore.createNewConversation()
}

async function onSend(text: string) {
  if (!text.trim() || isStreaming.value) return
  const convId = await ensureConversation()
  messages.value.push({ role: 'user', content: text })
  const assistant: LocalMsg = { role: 'assistant', content: '', reasoning: '' }
  messages.value.push(assistant)
  isStreaming.value = true
  try {
    const reader = await ApiService.chat([{ role: 'user', content: text }], convId)
    if (!reader) throw new Error('no reader')
    await ApiService.handleChatStream(reader, (chunk) => {
      if (chunk.type === 'think') assistant.reasoning = chunk.content
      else assistant.content = chunk.content
      nextTick(() => chatRef.value?.scrollToBottom())
    })
  } catch (e) {
    assistant.status = 'error'; assistant.content = '回复出错，请重试'
  } finally {
    isStreaming.value = false
    convStore.loadUserConversations()
  }
}
function onStop() { isStreaming.value = false }
function onSelect(_id: number) { /* Task 13 接入历史加载 */ }
```

- [ ] **Step 2: 写 Home 模板 + 样式**

```vue
<template>
  <AppLayout>
    <template #sidebar>
      <ConversationSidebar @select="onSelect" />
    </template>
    <WelcomeHero
      v-if="messages.length === 0"
      :loading="isStreaming" :mode="mode"
      @send="onSend" @stop="onStop" @update:mode="(m) => mode = m"
    />
    <template v-else>
      <ChatView ref="chatRef" :messages="messages" :is-streaming="isStreaming" />
      <div class="bottom-input">
        <RichChatInput
          :loading="isStreaming" :mode="mode"
          @send="onSend" @stop="onStop" @update:mode="(m) => mode = m"
        />
      </div>
    </template>
  </AppLayout>
</template>
<style scoped>
.bottom-input { padding: 12px 24px 20px; max-width: 820px; width: 100%; margin: 0 auto; }
</style>
```

- [ ] **Step 3: dev 验证清单**

Run: `npm run dev`，登录后验证：
  - [ ] welcome 态居中大输入框，浅色绿调
  - [ ] 发消息 → 流式逐字渲染 + 自动滚动，结束后输入框解锁
  - [ ] 空串/纯空格发送被拦截
  - [ ] 流式中发送按钮锁定（isStreaming）
  - [ ] XSS：发含 `<script>` 的消息，助手回显不执行脚本
  - [ ] 发送后侧栏会话列表刷新

- [ ] **Step 4: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): Home 编排层-外壳+标准聊天垂直切片"
```

---

### Task 11: 接入深度推理模式

**Files:**
- Modify: `src/views/Home.vue`（`onSend` 按 mode 选接口）
- Modify: `src/components/ChatView.vue`（若冒烟证明 reasoning 需显式 slot）

**Interfaces:**
- Consumes: `ApiService.reason`、`<t-chat-reasoning>`。
- Produces: reason 模式下 think 内容渲染为折叠思维链面板。

- [ ] **Step 1: onSend 按 mode 选 reader**

把 Task 10 的 `const reader = await ApiService.chat(...)` 一行替换为：
```ts
const payload = [{ role: 'user' as const, content: text }]
const reader = mode.value === 'reason'
  ? await ApiService.reason(payload, convId)
  : await ApiService.chat(payload, convId)
// search 分支在 Task 12 接入
```
`handleChatStream` 的 `chunk.type==='think' → assistant.reasoning` 已在 Task 10 写好；`toChatItems` 对有 reasoning 的消息已置 `reasoning: true`。

- [ ] **Step 2: 如需显式 reasoning slot 则补 ChatView**

若 Task 1 冒烟证明 `reasoning:true` 不自动出折叠面板，在 `ChatView.vue` 的 `<t-chat>` 内加：
```vue
<template #reasoning="{ item }">
  <t-chat-reasoning v-if="item.reasoning">
    <template #header>思考过程</template>
    {{ item.__reasoningText }}
  </t-chat-reasoning>
</template>
```
并在 `toChatItems` 中把 reasoning 文本挂到可取字段（依冒烟确定的字段名）。若自动渲染则跳过本步，在提交信息注明。

- [ ] **Step 3: dev 验证**

`npm run dev` → 切「深度推理」→ 发消息，确认思维链折叠面板出现、可展开/收起、与正文分块。

- [ ] **Step 4: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): 接入深度推理模式-思维链折叠面板"
```

---

### Task 12: 接入联网搜索模式 + 结果抽屉

**Files:**
- Modify: `src/views/Home.vue`（search 分支 + 事件解析 + 面板状态）
- Modify: `src/components/ChatView.vue`（搜索触发块点击 → emit openSearchPanel）

**Interfaces:**
- Consumes: `ApiService.search`、`SearchResultPanel`（Task 8）、`SearchResult`。
- Produces: search 模式结果触发块 + 抽屉面板。

- [ ] **Step 1: Home 加搜索状态与解析**

`<script setup>` 顶部加：
```ts
import SearchResultPanel from '../components/SearchResultPanel.vue'
import type { SearchResult } from '../types'
const searchResults = ref<SearchResult[]>([])
const searchPanelVisible = ref(false)

async function handleSearchStream(reader: ReadableStreamDefaultReader<Uint8Array>, assistant: LocalMsg) {
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read(); if (done) break
    for (const line of decoder.decode(value).split('\n')) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6).trim(); if (raw === '[DONE]') continue
      try {
        const ev = JSON.parse(raw)
        if (ev.type === 'search_results' && Array.isArray(ev.results)) {
          searchResults.value = ev.results
          assistant.content = `🔍 已找到 ${ev.results.length} 条结果，点击查看`
        } else if (ev.type === 'direct_content' || ev.content) {
          assistant.content = ev.content ?? assistant.content
        }
      } catch { /* 非 JSON 行忽略 */ }
      nextTick(() => chatRef.value?.scrollToBottom())
    }
  }
}
```

- [ ] **Step 2: onSend 接 search 分支**

把 Task 11 的 reader 选择块改为三分支，并在 search 时走 `handleSearchStream` 而非 `handleChatStream`：
```ts
if (mode.value === 'search') {
  const reader = await ApiService.search(payload, convId)
  if (!reader) throw new Error('no reader')
  await handleSearchStream(reader, assistant)
} else {
  const reader = mode.value === 'reason'
    ? await ApiService.reason(payload, convId)
    : await ApiService.chat(payload, convId)
  if (!reader) throw new Error('no reader')
  await ApiService.handleChatStream(reader, (chunk) => {
    if (chunk.type === 'think') assistant.reasoning = chunk.content
    else assistant.content = chunk.content
    nextTick(() => chatRef.value?.scrollToBottom())
  })
}
```
（替换掉 Task 10/11 原来的单 reader 调用；外层 try/catch/finally 不变。）

- [ ] **Step 3: 触发块点击 → 打开抽屉**

模板里 `ChatView` 加监听、挂面板：
```vue
<ChatView ref="chatRef" :messages="messages" :is-streaming="isStreaming"
          @open-search-panel="searchPanelVisible = true" />
...
<SearchResultPanel v-model:visible="searchPanelVisible" :results="searchResults" />
```
`ChatView.vue` 中对 assistant content 的搜索触发块绑定点击 emit `openSearchPanel`（实现方式依 Task 1 冒烟确定的 content 自定义渲染能力：优先用 `<t-chat>` 的 `content` slot 自定义；若不支持则在消息下方附一个 `t-link` 触发）。

- [ ] **Step 4: dev 验证**

`npm run dev` → 切「联网搜索」→ 发消息，确认「已找到 N 条结果」触发块出现，点击打开抽屉，链接新标签打开。

- [ ] **Step 5: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): 接入联网搜索模式 + 结果抽屉面板"
```

---

### Task 13: 会话历史切换（onSelect 接线 + 流式竞态保护）

**Files:**
- Modify: `src/views/Home.vue`（`onSelect` 实现）

**Interfaces:**
- Consumes: `convStore.loadConversationMessages`、`toLocalMsg`（Task 2）。
- Produces: 点击侧栏会话 → 加载历史进本地 messages，切换前中断流式。

- [ ] **Step 1: 实现 onSelect**

替换 Task 10 的 `onSelect` stub：
```ts
import { toLocalMsg } from '../utils/chatAdapter'

async function onSelect(id: number) {
  if (isStreaming.value) isStreaming.value = false   // 中断旧流式
  await convStore.loadConversationMessages(id)
  messages.value = convStore.currentMessages.map(toLocalMsg)
  searchPanelVisible.value = false
  searchResults.value = []
  mode.value = 'standard'
  nextTick(() => chatRef.value?.scrollToBottom())
}
```

- [ ] **Step 2: dev 验证**

`npm run dev` → 建两个会话各发消息 → 点击历史会话，确认历史正确加载；流式途中点另一会话，确认旧流不污染新会话。

- [ ] **Step 3: type-check + 提交**

```bash
npm run type-check
git add -A && git commit -m "feat(home): 会话历史切换 + 流式竞态保护"
```

---

### Task 14: 清死代码 + 最终构建验证

**Files:**
- Delete: `src/components/Sidebar.vue`、`src/api/index.ts`、`src/api/conversation.ts`

**Interfaces:**
- Produces: 无死代码；`type-check` + `build` 通过。

- [ ] **Step 1: 确认无引用后删除**

```bash
grep -rn "components/Sidebar\|api/conversation\|from '../api'\|from './api'" src/ || echo "无引用，可安全删除"
```
确认无引用后删除三个文件（`src/components/Sidebar.vue`、`src/api/index.ts`、`src/api/conversation.ts`）。`MessageBox.vue` 保留（Login 在用）。

- [ ] **Step 2: type-check + build**

```bash
npm run type-check && npm run build
```
Expected: 均通过，`dist/` 生成。

- [ ] **Step 3: 全量手动验证清单**

`npm run dev` 跑完整清单（spec §7）：welcome 态 / 流式 / 深度推理折叠 / 联网搜索抽屉 / 会话增删改切换 / markdown 无 XSS / 刷新保持登录 / 401 跳登录。

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "chore(home): 清除死代码(Sidebar/api 遗留栈) + 最终构建验证"
```

- [ ] **Step 5: 部署（需用户确认，涉及后端目录）**

构建产物拷到后端 static（遵 readme）。此步写文件到 `backend/`，执行前向用户确认：
```bash
# 示例，路径以实际为准
cp -r dist/* ../../backend/deepseek_agent/llm_backend/static/
```

---

## 完成标准

全部 14 task 的 checkbox 勾完、`type-check` + `build` 通过、§7 手动清单全绿后，Home 页达成 Accio 浅绿风格 + 三模式聊天 + 会话历史，死代码清除。电商页、登录页为后续独立子项目。



