# 登录页 + 电商页 Accio 绿色化重构计划

**Goal:** 把 Login、EcommerceService 两页统一到 Home 已建的「浅色 + 绿色 + TDesign」视觉语言。登录页重写为绿色 TDesign 登录卡片;电商页深度重构成绿色商城门面 + 客服浮窗 TDesign 化(消除 v-html XSS)。

**Architecture:** 只换渲染层,不碰数据层。复用 Home 已建的主题([theme-accio.css](../../src/styles/theme-accio.css))、chatAdapter、ChatView。`AuthService`/`ApiService` 逻辑不改(除把电商页直连 URL 改相对路径)。

**Tech Stack:** 同 Home —— Vue 3.3 `<script setup>`、TDesign `tdesign-vue-next` + `@tdesign-vue-next/chat`、TS 5.4.5、Vite 5。

**验证:** 每个 Task 跑全量 `npm run type-check`(读完整输出,不按文件名 grep)+ 阶段末 `npm run build`。无测试框架不引入。本地 commit 做检查点,不自动 push。

**已定小决策:**
- MessageBox 换成 TDesign(`t-dialog`/`DialogPlugin`),重构后删除 [MessageBox.vue](../../src/components/MessageBox.vue)(仅 Login 在用)。
- 微信登录按钮保留为样式占位(逻辑本就是 TODO,不删不接)。
- 电商页 `http://localhost:8000/api/langgraph/query` → 相对 `/api/langgraph/query`(走 vite 代理 + 生产同源)。
- 用户协议/隐私/微信登录的 TODO 保持 TODO,不扩范围。

---

## Task 1: Login 页重写为绿色 TDesign 卡片

**Files:** Modify `src/views/Login.vue`

- [ ] Step 1: 模板改用 TDesign 表单组件
  - `t-form` + `t-form-item` + `t-input`(email/password）+ 注册态加 username/confirmPassword。
  - 提交 `t-button theme="primary" block`;登录/注册切换用文字链接或 `t-tabs`。
  - agreement 用 `t-checkbox`;协议/隐私链接保留 `@click.prevent` TODO。
  - 微信登录保留为 `t-button variant="outline"` 占位 + 图标。
  - 卡片容器:浅色 `--td-bg-color-container`、圆角、阴影;整页浅色底,居中。
- [ ] Step 2: 校验改用 TDesign 规则或保留现有 regex
  - 保留现有 `validateRules`(username/email/password 正则)与 isFormValid 逻辑;接到 `t-form` 的 rules 或继续手动校验 + `t-input` 的 status/tips 显示错误。
  - 保留 handleSubmit 的 register/login 分支、错误映射(401→邮箱或密码错误、detail 数组→字段错误)。
- [ ] Step 3: 成功提示换 TDesign
  - 注册成功用 `DialogPlugin.confirm` 或 `MessagePlugin.success` 替代 MessageBox;`@confirm` 回到登录态并清表单。
- [ ] Step 4: `npm run type-check`(全量)→ 本地 commit。

## Task 2: 删除 MessageBox

**Files:** Delete `src/components/MessageBox.vue`

- [ ] Step 1: 确认仅 Login 引用且已移除 → 删除文件。
- [ ] Step 2: `npm run type-check`(全量)→ commit。

## Task 3: 电商页客服浮窗 TDesign 化 + 消除 XSS

**Files:** Modify `src/views/EcommerceService.vue`

- [ ] Step 1: 浮窗聊天区换 TDesign
  - 客服消息列表改用 `<t-chat>` + chatAdapter（复用 Home）或 `t-chat` 直填块数组;删除 `v-html` + 手搓 `renderMessage`(消除 XSS，markdown 走 TDesign 内置清理)。
  - 保留图片消息展示(imageUrl → 内容块或自定义渲染)。
  - 输入区换 `t-input` + 发送/上传按钮(TDesign 图标)。
- [ ] Step 2: 直连 URL 改相对路径
  - 两处 `http://localhost:8000/api/langgraph/query` → `/api/langgraph/query`。其余 FormData/SSE/会话 ID 逻辑不变。
- [ ] Step 3: `npm run type-check`(全量)→ commit。

## Task 4: 电商门面绿色化重构

**Files:** Modify `src/views/EcommerceService.vue`（样式 + 结构）

- [ ] Step 1: 配色 token 化
  - 红色系 `#ff4d4f` → 绿色品牌 token（`--td-brand-color` 系）;灰阶改 TDesign 文本/边框 token。
- [ ] Step 2: 门面 accio 调性
  - 头部/导航/搜索框/商品卡片用圆角 + 留白 + 绿色点缀;商品卡 hover 阴影;浮动客服按钮绿色。
  - 保留商品 mock 数据与结构语义(推荐/热销),只改观感。
- [ ] Step 3: `npm run type-check` + `npm run build`（全量）→ commit。

## Task 5: 全分支自审 + 验收

- [ ] Step 1: 自审两页集成点（表单校验边界、客服流式响应式代理、图片上传、SSE 解析、相对 URL 代理）。
- [ ] Step 2: 临时预览路由（本地）给用户目视登录页 + 电商页;确认后撤。
- [ ] Step 3: 修自审发现的问题 → commit。

---

## 完成标准
Login、EcommerceService 两页达成浅绿 Accio 风格 + TDesign 组件化,客服浮窗消除 v-html XSS,电商直连 URL 走相对代理;type-check 0 错 + build 通过;MessageBox 死码删除。push 等用户指示。
