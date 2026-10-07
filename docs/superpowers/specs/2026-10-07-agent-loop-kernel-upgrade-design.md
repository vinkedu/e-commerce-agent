# 电商客服 Agent 内核升级设计（DeerFlow 内核理念 · 选择性增强）

- 日期：2026-10-07
- 范围：后端 `backend/deepseek_agent/llm_backend`，不碰前端
- 路线：甲·内核升级 → 方案 B+（合并路由）
- 三个机制：真 Agent Loop（ReAct 回环）+ 统一工具层 + Context 中间件
- 对标 DeerFlow：Runtime(Agent Loop) / Tools(统一工具+预算+结果外置) / Context(调用前装配·调用后裁决·无侵入)

## 1. 背景与目标

### 1.1 现状（事实画像）

当前后端是「电商智能客服」：FastAPI + LangGraph + Neo4j(Text2Cypher) + 微软 GraphRAG(vendored) + DeepSeek/Ollama 双模型。核心问题：**它不是 agent，是「分类→分流」状态机**。

- 主图（`app/lg_agent/lg_builder.py:503-517`）：`START → analyze_and_route_query → route_query` 条件边 → 5 个终端节点，全部直接 END，**零回边**。
- KG 子图（`.../workflows/multi_agent/multi_tool.py:146-162`）：`guardrails → planner(拆成互不依赖并行子任务) → fan-out → tool_selection(每子任务只选一个工具) → 工具跑一次 → summarize → final_answer`。**每个子任务只调一次工具，无「看结果再决定」的回环**（`edges.py:61` map-reduce 证实）。
- 两套割裂工具体系：`services/search_service.py` 用 OpenAI function-calling(web 搜索)；KG 子图用 Pydantic schema(`kg_sub_graph/kg_tools_list.py`)。工具名与执行节点还对不齐（`tool_selection/node.py:84-120` 靠 else 兜底）。
- 上下文零处理：各节点 `[{system}] + state.messages` 全量拼接，历史无限增长；经营范围描述硬编码且两处重复（`lg_builder.py:187-197` 与 `426-436` 逐字复制）。
- 持久化：主图 `MemorySaver()` 纯内存重启即丢；子图 `.compile()` 没传 checkpointer（`multi_tool.py:164`），子图状态根本不持久。
- 存在明显死代码/会崩代码（见 §9）。

### 1.2 目标

把「只跑一次工具」的分流状态机，升级为能多步推理的真 ReAct 回环，让客服能完成「查商品 → 比价 → 查库存 → 给建议」这类连续推理；同时统一割裂的工具体系、引入可组合的上下文中间件。严守「选择性增强、低风险、每步可跑、不碰前端」。

### 1.3 非目标（YAGNI）

- 不做 Gateway/Run 生命周期重写。
- 不做 Working/Long-term Memory（本次中间件只上 Scope）。
- 不做治理（接口鉴权、token 预算上限、审计日志）、不做沙箱、不做 HITL 中断。
- 不碰前端；`/api/chat`、`/api/search` 两条链路保持原样。

## 2. 新图结构（主图 + ReAct 回环）

### 2.1 路由三分

`Router.type` 从 5 类（general-query / additional-query / graphrag-query / image-query / file-query）压成 3 类：

- `image`：有图片，走视觉模型（保留原 `create_image_query` 逻辑）。
- `file`：文件查询（仍是 stub，但改为优雅回「暂不支持文件」，不再返回 None 导致图崩）。
- `agent`：其余全部并入回环。原 general / additional / graphrag 三类文本查询合并——闲聊时 agent 不调工具直接答，商品问题时 agent 自主决定调工具。

路由步骤本身保留（一次便宜的分类）。

### 2.2 回环

```
START → route ┬→ "image" → create_image_query → END
              ├→ "file"  → file_fallback       → END
              └→ "agent" → ┌──────────────────────────┐
                           │   agent  ⇄  tools (回环)   │
                           └──────────────────────────┘
```

- `agent` 节点：绑定统一工具（§3），LLM 决定「调工具 or 直接答」。
- `tools` 节点：执行 agent 选中的工具，结果作为 `ToolMessage` 回填，再回 `agent`。
- 条件边：`agent` 输出含 `tool_calls` → `tools`；否则 → `END`。`tools` → `agent`。

### 2.3 防失控（回环刹车）

`AgentState` 加 `iteration: int`。`tools → agent` 每轮 +1。超过 `max_iterations`（默认 6）时，强制走「用现有信息作答」收尾——给 agent 一个不带工具的最后一轮，产出最终答后 END。对标 DeerFlow 的 `continuation_count` 上限。

### 2.4 guardrails（经营范围）转中间件

不再是独立 LLM 节点。经营范围描述由 `ScopeMiddleware`（§4）注入 agent system 上下文，agent 据此礼貌拒绝超范围**商品类**请求，不误伤闲聊。替代原独立 LLM guardrails 节点，省一次 LLM 调用。

### 2.5 原子图退役复用

`create_research_plan` + `multi_tool.py` + planner 的「拆互不依赖并行子任务」那套不再用于主链路（与 ReAct 回环理念冲突）。工具执行逻辑（cypher 生成/校验/执行、predefined、graphrag）**保留并复用**，改为挂在回环上（§3）。

## 3. 统一工具层

新建 `app/lg_agent/tools/registry.py`——所有工具统一成 LangChain `StructuredTool`，一处注册，`agent` 绑定与 `tools` 执行都从这里取。取代散在 `services/function_tools.py` + `kg_sub_graph/kg_tools_list.py` 两处的局面。

### 3.1 四个工具（复用现有能力，重新包装）

| 工具名 | 职责 | 复用现有代码 | 触发场景 |
|---|---|---|---|
| `query_product_graph` | Text2Cypher：生成→校验→执行 Cypher | `components/cypher_tools/node.py` | 价格/库存/规格/订单/供应商等结构化查询 |
| `predefined_query` | 执行预置 Cypher 模板(~30条) | `components/predefined_cypher` + `cypher_dict.py` | 高频固定查询，确定性快路径 |
| `search_knowledge_base` | GraphRAG 非结构化检索 | `components/customer_tools/node.py` 的 `GraphRAGAPI` | 故障/售后/保修/维修/退换货/评价 |
| `web_search` | SerpAPI 实时联网 | `tools/search.py` | 实时信息（打通原本割裂的两套工具） |

### 3.2 关键设计

1. **统一接口**：每工具 = `{name, description, args_schema(Pydantic), async func}`。描述词复用 `kg_tools_list.py` 已有的中文描述。agent 靠描述自主选工具，**删掉 `tool_selection` 那个专门的 LLM 选工具节点**（回环里 agent 自己选，省一次 LLM 调用）。
2. **Token 预算 + 结果外置**：工具返回超阈值（默认 ~4000 字符）截断 + 附「结果过长已截断」提示。回环稳定多轮的前提。对标 DeerFlow「结果外置」。
3. **错误即消息，不即崩**：工具异常 → 包成 `ToolMessage(content="工具出错: ...")` 回填，agent 可换工具/改参重试。用 agent 推理恢复了被注释掉的 cypher 校验纠错回环（`single_agent/text2cypher.py:82-87`），不再靠硬编码的边。
4. **参数校验**：执行前用 `args_schema` 校验 agent 给的参数，不合法回错误消息让 agent 修正。
5. **删 DANGEROUS 开关**：`attempt_cypher_execution_on_final_attempt`（源码自标 "THIS MAY BE DANGEROUS"，校验失败仍强行执行 Cypher）直接删除，由第 3 点替代。

## 4. Context 中间件

新建 `app/lg_agent/middleware/`，统一接口：

```python
class ContextMiddleware:
    async def before_model(self, state) -> state   # 调用前：装配
    async def after_model(self, state) -> state     # 调用后：裁决
```

`agent` 节点按注册顺序跑 `before_model` → 调模型 → `after_model`。加新中间件 = 加一个类并注册，不改回环本身（无侵入）。

### 4.1 本次落地三件套

1. **`ScopeMiddleware`（经营范围注入）** — `before_model`：经营范围描述抽成**单一数据源**（消灭两处重复），注入 agent system 上下文。即 §2.4 的落点。
2. **`HistoryCompressionMiddleware`（上下文压缩）** — `before_model`：消息超阈值（默认超 ~12 轮才触发）时，把更早历史压成一段摘要，触发时调一次 LLM。system 提示、经营范围、未完成的 tool_call 链**不参与压缩**，只压久远问答对。对标 DeerFlow「Durable Context」。
3. **`ToolResultMiddleware`（工具结果规范化）** — `after_model`：兜底 §3.2 的 token 预算/结果外置（即便某工具忘了截断，这里保证不超限），整理工具原始结果为 agent 易消费格式。

### 4.2 边界

权限/脱敏/预算治理、Memory 注入本次不做，但接口预留——未来加 `AuthMiddleware`/`MemoryMiddleware` 即新增一个类，不动现有代码。

## 5. 状态与持久化 + SSE 事件契约

### 5.1 状态（AgentState）精简

- **加** `iteration: int`（回环刹车计数）。
- **瘦** `Router.type`：5 类 → 3 类（`image`/`file`/`agent`）。
- **删死字段**：`steps`、`hallucination`（`check_hallucinations` 退役）、对不存在的 `state.documents`/`state.config` 的引用（`lg_builder.py:108,483` 本就是 bug）。
- `messages` 保持 `add_messages` reducer——正是回环要的 Human/AI(tool_calls)/Tool/AI 累积结构。

### 5.2 持久化：SqliteSaver（已定）

- 决定：**采用 SqliteSaver**（落本地 `.sqlite` 文件，跨重启可续），一步到位落实 Durable Context。配置项 `.env` 加 sqlite 文件路径。
- 实现注意：主链路是 `graph.astream`（异步），须用 `AsyncSqliteSaver`（`langgraph-checkpoint-sqlite` 包），并以 async context manager 方式在应用生命周期内持有连接（挂 FastAPI lifespan，不要每请求新建）。
- 子图并入主图后 = 只剩一张图、一个 checkpointer，「子图状态丢失」问题自动消失。`thread_id = conversation_id` 机制保留。

### 5.3 SSE 事件契约（兼容红线，已定）

前端 `EcommerceService.vue:447` 的 `handleChatStream` **只认 `data: "<文本>"`**：去 `data: ` 前缀、去引号、反转义 `\n`、拼接，不解析结构化事件。

**本次采用（严守不改前端）**：回环只流式吐**最终 agent 作答**的 token，格式仍是 `data: "<json字符串>"`（与 `main.py:350` 一致）。中间 tool_call、工具结果等**全部按 tag 过滤吃掉，零噪音泄漏**。前端一行不用改，行为与现在一致，仅答案质量因多步推理而提升。

**明确不做**：DeerFlow 式「Tool Progress」过程气泡（需配套改前端解析）。记入未来扩展。

### 5.4 死接口

`/api/langgraph/resume`（`main.py:408`）与中断检测（`main.py:358-363`）——无节点真正触发 `interrupt()`，本是死逻辑。本次回环不引入 HITL，端点**保留不动**（避免前端潜在引用断裂），不作为重点。

## 6. 迁移策略 + 特性开关

核心风险：换主图可能搞坏现在能跑的电商客服。对策——**特性开关，新旧图并存，可瞬间回滚**。

- `.env` 加 `LG_AGENT_MODE = loop | legacy`（默认先 `legacy`，测试通过后翻 `loop`）。
- `main.py` 现在 `from app.lg_agent.lg_builder import graph`（模块级单例）。改为启动时调工厂 `build_graph()`，按开关返回新回环图或旧图。
- 旧图代码迁移期间原样保留 → 出问题改一个 `.env` 字段即时回滚。待 `loop` 真实验证稳定，再删旧路径（§9 延迟档）。

## 7. 分阶段落地（每阶段可独立跑、可验证）

1. **地基**：生成 `requirements.txt`（现零依赖清单）；引入 `pytest`+`pytest-asyncio`；建 `SqliteSaver`；建 `build_graph()` 工厂骨架（先只返回旧图，不改行为）。
2. **工具层**：`tools/registry.py` + 4 个统一工具（复用现有逻辑）。可单测，不接图。
3. **中间件**：`middleware/` 三件套（Scope/History/ToolResult）。可单测。
4. **回环**：新 `agent ⇄ tools` 图 + 3 分路由 + iteration 刹车，挂上阶段 2、3 产物。开关仍默认 legacy。
5. **切换**：测试全绿 → `LG_AGENT_MODE=loop` 设为默认 → 真实验证。
6. **清理**：删延迟死代码（§9 延迟档）。

## 8. 测试（本次引入测试框架）

- 栈：`pytest` + `pytest-asyncio`。**不碰真实 DeepSeek/Neo4j/SerpAPI**——用 `FakeChatModel`（脚本化返回「先 tool_call，再最终答」）+ mock 工具后端。CI 无需密钥、不烧 token。
- 必测用例：
  1. **回环控制**：iteration 递增；超 `max_iterations` 刹车触发；无 tool_call 时正常退出。
  2. **工具层**：每工具参数校验 + 执行；异常 → `ToolMessage` 不崩；结果超限截断。
  3. **中间件**：Scope 注入经营范围；History 超阈值触发压缩；ToolResult 兜底截断。
  4. **SSE 契约（兼容保证，必须有）**：给定一次含工具调用的回环，断言只吐最终答文本 `data: "<text>"`、零 tool_call 噪音泄漏。守住「不改前端」。
  5. **端到端 smoke**：脚本化 LLM 跑通一轮「问 → 选工具 → 看结果 → 作答」。
- 验证口径（Python 无前端式 build）：`pytest` 全绿 + 启动冒烟（`python -c "from main import app"` 不报错 + 图能 compile）。

## 9. 死代码清理（两档）

**立即删（与重构无关，现在就是死的/会崩的）**：
- `kg_sub_graph/multi_tools.py`（565 行重复版，引用未定义变量，一跑必 `NameError`）
- `check_hallucinations`（`lg_builder.py:462-495`，从未入图 + 引用不存在的 `state.documents`）
- `kg_sub_graph/kg_builder.py`（0 字节空文件）
- `real_time_network_query` schema（`kg_tools_list.py:71`，有定义无实现，被 `web_search` 取代）
- 残留调试 `print`（`planner/node.py:131-142` 等）
- 确认无引用后：`ps_genai_agents` 空壳、`agent.py`/`agent_cooking_assistant.py`（Studio 测试入口）

**延迟删（回环验证通过后，阶段 6）**：
- `multi_tool.py`（真用的 165 行版）、`tool_selection` 节点、两份 `planner`、`guardrails` 节点、`lg_builder.py` 的 `respond_to_general_query`/`get_additional_info`/`create_research_plan`——全被回环取代。

## 10. 明确不做（守住选择性增强）

- 不做 Gateway/Run 生命周期重写（路线乙）。
- 不做 Working/Long-term Memory（本次中间件只上 Scope）。
- 不做治理（接口鉴权、token 预算上限、审计）、沙箱、HITL 中断。
- 不碰前端。
- `/api/chat`、`/api/search` 两条链路保持原样。
- `file-query` 仍是 stub，仅做最小修复：优雅回「暂不支持文件」，不再返回 None 导致图崩。

## 11. 受影响文件清单（预估）

**新增**：
- `app/lg_agent/graph_factory.py`（`build_graph()` 工厂 + 开关）
- `app/lg_agent/agent_loop.py`（回环图：agent/tools 节点 + 3 分路由 + 刹车）
- `app/lg_agent/tools/registry.py`（统一工具注册 + 4 个 StructuredTool）
- `app/lg_agent/middleware/__init__.py` + `scope.py` + `history.py` + `tool_result.py`
- `app/lg_agent/scope_config.py`（经营范围单一数据源常量；供 `ScopeMiddleware` 引用，消灭 `lg_builder.py:187-197` 与 `426-436` 两处重复）
- `tests/`（pytest 用例 + FakeChatModel + conftest）
- `requirements.txt`

**修改**：
- `main.py`（改用 `build_graph()`；langgraph 流式段按新回环过滤噪音）
- `app/lg_agent/lg_states.py`（AgentState 加 iteration、Router 瘦身、删死字段）
- `app/core/config.py`（加 `LG_AGENT_MODE`、sqlite 路径配置）

**删除**：见 §9。

## 12. 验收标准

- `pytest` 全绿（§8 五类用例齐全）。
- 启动冒烟通过：`python -c "from main import app"` 无异常，`build_graph()` 两种模式均能 compile。
- `LG_AGENT_MODE=loop` 下，电商客服多轮问答可完成一次含 ≥2 次工具调用的连续推理。
- SSE 输出格式与现网一致（`data: "<text>"`），前端零改动即可正常渲染。
- `LG_AGENT_MODE=legacy` 可即时回滚到旧行为。
