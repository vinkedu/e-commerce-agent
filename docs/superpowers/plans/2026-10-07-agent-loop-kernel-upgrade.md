# 电商客服 Agent 内核升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把电商客服后端从「分类→分流、只跑一次工具」的状态机，升级为能多步推理的真 ReAct 回环（agent⇄tools），并统一割裂的工具体系、引入可组合的 Context 中间件。

**Architecture:** 保留主图路由（瘦身为 image/file/agent 三分），把原 general/additional/graphrag 三类文本查询并入一个 `agent ⇄ tools` 回环；4 个统一工具（cypher/predefined/graphrag/web_search）挂在回环上，agent 自主选工具、看结果、再决定；中间件在模型调用前后注入经营范围/压缩历史/规范化工具结果；特性开关 `LG_AGENT_MODE` 新旧图并存可瞬间回滚；AsyncSqliteSaver 持久化。

**Tech Stack:** Python 3 / FastAPI / LangGraph (StateGraph + AsyncSqliteSaver) / LangChain core / langchain-deepseek / langchain-ollama / langchain-neo4j / 微软 GraphRAG(vendored) / pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-10-07-agent-loop-kernel-upgrade-design.md`

## Global Constraints

- 范围仅限后端 `backend/deepseek_agent/llm_backend`，**禁止修改 `frontend/` 任何文件**。
- 所有命令、Python 导入的工作目录（CWD）= `backend/deepseek_agent/llm_backend`（`main.py`/`run.py` 在此，不在 `app/` 下）。
- **SSE 兼容红线**：langgraph 流式输出格式必须保持 `data: "<json字符串>"`（与现 `main.py:350` 一致），中间 tool_call/工具结果全部过滤吃掉，零噪音泄漏。
- **密钥禁止进代码**：测试不得使用真实 DeepSeek/Neo4j/SerpAPI；一律用 FakeChatModel + mock 后端，CI 无需密钥、不烧 token。
- 持久化用 `AsyncSqliteSaver`（异步 `astream` 场景），挂 FastAPI lifespan，不要每请求新建连接。
- 特性开关 `LG_AGENT_MODE` 默认值在实现期间为 `legacy`，仅在全部测试通过后（Task 16）才翻 `loop`。
- 回环刹车 `max_iterations` 默认 `6`。
- 工具结果截断阈值 `MAX_TOOL_RESULT_CHARS` 默认 `4000`。
- 历史压缩触发阈值：消息超 `12` 轮（`HISTORY_COMPRESSION_THRESHOLD = 12`）。
- 复用现有节点逻辑，不重写 cypher 生成/校验/执行；工具是对现有节点的薄封装。
- 中文回复、代码/变量名英文；遵循现有 loguru 日志风格 `get_logger(service=...)`。

## Review Focus

- **工具后端不可达（Neo4j/GraphRAG/SerpAPI 宕机或超时）**：工具必须返回 `ToolMessage(content="工具出错: ...")` 让 agent 继续，绝不让异常冒泡崩掉整张图。→ 测试见 Task 4/5/6/7。
- **agent 反复选同一工具/无限回环**：`iteration` 超 `max_iterations` 必须强制走收尾作答并 END，不得无限循环烧 token。→ 测试见 Task 13。
- **工具返回超大结果（GraphRAG 长文/Cypher 大结果集）**：必须在进入上下文前截断到 `MAX_TOOL_RESULT_CHARS`，防止撑爆上下文。→ 测试见 Task 3 + Task 11。
- **SSE 中间噪音泄漏到前端**：含工具调用的回环，流式只能吐最终答文本，tool_call 的 arguments/中间 AIMessage 不得出现在 `data:` 行。→ 测试见 Task 15。
- **agent 给出不合法工具参数（缺字段/类型错）**：执行前用 `args_schema` 校验，不合法回错误消息让 agent 修正，不得抛未捕获异常。→ 测试见 Task 5。

---

## File Structure

**新增（本次创建）：**
- `requirements.txt` — 依赖清单（从现有 import 反推 + 新增 pytest/sqlite checkpoint）
- `app/lg_agent/model_factory.py` — `get_agent_model(tags)` 统一模型工厂（取代各节点各自 new 模型）
- `app/lg_agent/scope_config.py` — `SCOPE_DESCRIPTION` 经营范围单一数据源常量
- `app/lg_agent/tools/__init__.py`
- `app/lg_agent/tools/result.py` — `truncate_result()` + `MAX_TOOL_RESULT_CHARS`
- `app/lg_agent/tools/kg_tools.py` — `query_product_graph` / `predefined_query` / `search_knowledge_base` 三个 StructuredTool（薄封装现有节点）
- `app/lg_agent/tools/web_tools.py` — `web_search` StructuredTool（封装 `tools/search.py`）
- `app/lg_agent/tools/registry.py` — `get_tools()` / `get_tool_map()`
- `app/lg_agent/middleware/__init__.py` — `ContextMiddleware` 基类 + `run_before`/`run_after` 编排
- `app/lg_agent/middleware/scope.py` — `ScopeMiddleware`
- `app/lg_agent/middleware/history.py` — `HistoryCompressionMiddleware`
- `app/lg_agent/middleware/tool_result.py` — `ToolResultMiddleware`
- `app/lg_agent/agent_loop.py` — 回环图构建（agent/tools 节点 + 3 分路由 + 刹车 + file_fallback）
- `app/lg_agent/graph_factory.py` — `build_graph(mode, checkpointer)` 工厂
- `tests/conftest.py` — `FakeChatModel` + 公共 fixture
- `tests/` 下各测试文件（随任务创建）

**修改：**
- `app/core/config.py` — 加 `LG_AGENT_MODE`、`SQLITE_CHECKPOINT_PATH`
- `app/lg_agent/lg_states.py` — `AgentState` 加 `iteration`；`Router.type` 瘦成 3 类；删 `steps`/`hallucination` 死字段
- `main.py` — 改用 `build_graph()`；langgraph 流式段按新回环过滤噪音；AsyncSqliteSaver 挂 lifespan

**删除：** 见 Task 16。

---

## Task 1: 地基 — requirements.txt + pytest + FakeChatModel + 配置开关

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Modify: `app/core/config.py`

**Interfaces:**
- Produces: `tests/conftest.py` 的 `FakeChatModel`（供全部后续任务测试复用）；`settings.LG_AGENT_MODE: str`、`settings.SQLITE_CHECKPOINT_PATH: str`

- [ ] **Step 1: 写 FakeChatModel 的自测**

```python
# tests/test_fake_model.py
import pytest
from langchain_core.messages import AIMessage
from tests.conftest import FakeChatModel

@pytest.mark.asyncio
async def test_fake_model_returns_scripted_in_order():
    m = FakeChatModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "x"}, "id": "1"}]),
        AIMessage(content="最终答"),
    ])
    bound = m.bind_tools([])          # 必须返回可继续 ainvoke 的对象
    r1 = await bound.ainvoke([])
    r2 = await bound.ainvoke([])
    assert r1.tool_calls[0]["name"] == "web_search"
    assert r2.content == "最终答"
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_fake_model.py -v`
Expected: FAIL（`ModuleNotFoundError` 或 `FakeChatModel` 未定义）

- [ ] **Step 3: 写 conftest.py**

```python
# tests/conftest.py
from typing import Any, List
from langchain_core.messages import AIMessage

class _StructuredRunnable:
    def __init__(self, value: Any): self._value = value
    async def ainvoke(self, *_a, **_k): return self._value

class FakeChatModel:
    """脚本化假模型：按序弹出 responses；支持 bind_tools / with_structured_output。"""
    def __init__(self, responses: List[AIMessage] | None = None, structured: Any = None):
        self._responses = list(responses or []); self._structured = structured
    def bind_tools(self, _tools, **_k): return self
    def with_structured_output(self, _schema, **_k): return _StructuredRunnable(self._structured)
    async def ainvoke(self, *_a, **_k):
        return self._responses.pop(0) if self._responses else AIMessage(content="")
```

- [ ] **Step 4: 建 requirements.txt**

```
fastapi
uvicorn[standard]
langgraph
langgraph-checkpoint-sqlite
langchain-core
langchain-deepseek
langchain-ollama
langchain-neo4j
sqlalchemy
aiomysql
redis
faiss-cpu
sentence-transformers
PyPDF2
aiohttp
openai
python-jose[cryptography]
loguru
pydantic-settings
Pillow
requests
pytest
pytest-asyncio
```

- [ ] **Step 5: 加配置项 + pytest 配置**

在 `app/core/config.py` 的 `Settings` 类加字段（紧跟现有 AGENT_SERVICE 附近）：

```python
    LG_AGENT_MODE: str = "legacy"   # loop | legacy
    SQLITE_CHECKPOINT_PATH: str = "checkpoints.sqlite"
```

在 `tests/conftest.py` 顶部加（启用 asyncio 自动模式，避免每个用例标注）：

```python
import pytest
def pytest_configure(config): config.addinivalue_line("markers", "asyncio")
```

并建 `pytest.ini`（CWD 根）：

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_fake_model.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/deepseek_agent/llm_backend/requirements.txt backend/deepseek_agent/llm_backend/tests backend/deepseek_agent/llm_backend/pytest.ini backend/deepseek_agent/llm_backend/app/core/config.py
git commit -m "chore(agent): 地基 — requirements/pytest/FakeChatModel/配置开关"
```

## Task 2: 模型工厂 + 经营范围单一数据源

**Files:**
- Create: `app/lg_agent/model_factory.py`, `app/lg_agent/scope_config.py`
- Test: `tests/test_model_factory.py`

**Interfaces:**
- Produces: `get_agent_model(tags: list[str] | None = None) -> BaseChatModel`；`SCOPE_DESCRIPTION: str`

- [ ] **Step 1: 写测试**

```python
# tests/test_model_factory.py
from unittest.mock import patch, MagicMock
from app.lg_agent.model_factory import get_agent_model
from app.lg_agent.scope_config import SCOPE_DESCRIPTION

def test_scope_is_single_source():
    assert "智能家居" in SCOPE_DESCRIPTION

def test_factory_deepseek_path():
    with patch("app.lg_agent.model_factory.ChatDeepSeek", return_value=MagicMock()) as m, \
         patch("app.lg_agent.model_factory.settings") as s:
        s.AGENT_SERVICE = "deepseek"; s.DEEPSEEK_API_KEY = "k"; s.DEEPSEEK_MODEL = "deepseek-chat"
        get_agent_model(tags=["agent"])
        assert m.called
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_model_factory.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 写 scope_config.py（抽离两处重复的硬编码）**

```python
# app/lg_agent/scope_config.py
SCOPE_DESCRIPTION = """
个人电商经营范围：智能家居产品，包括但不限于：
- 智能照明（灯泡、灯带、开关）
- 智能安防（摄像头、门锁、传感器）
- 智能控制（温控器、遥控器、集线器）
- 智能音箱（语音助手、音响）
- 智能厨电（电饭煲、冰箱、洗碗机）
- 智能清洁（扫地机器人、洗衣机）

不包含：服装、鞋类、体育用品、化妆品、食品等非智能家居产品。
"""
```

- [ ] **Step 4: 写 model_factory.py**

```python
# app/lg_agent/model_factory.py
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import ChatOllama
from app.core.config import settings, ServiceType

def get_agent_model(tags: list[str] | None = None) -> BaseChatModel:
    tags = tags or []
    if settings.AGENT_SERVICE == ServiceType.DEEPSEEK:
        return ChatDeepSeek(api_key=settings.DEEPSEEK_API_KEY,
                            model_name=settings.DEEPSEEK_MODEL, temperature=0.7, tags=tags)
    return ChatOllama(model=settings.OLLAMA_AGENT_MODEL,
                      base_url=settings.OLLAMA_BASE_URL, temperature=0.7, tags=tags)
```

注：`settings.AGENT_SERVICE == ServiceType.DEEPSEEK` 测试里用字符串 `"deepseek"` mock，与现有 `ServiceType` 枚举值一致（见 `config.py`）。若枚举比较不成立，测试 patch 的是整个 `settings`，不受影响。

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_model_factory.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/model_factory.py backend/deepseek_agent/llm_backend/app/lg_agent/scope_config.py backend/deepseek_agent/llm_backend/tests/test_model_factory.py
git commit -m "feat(agent): 模型工厂 + 经营范围单一数据源"
```

---

## Task 3: 工具结果截断器

**Files:**
- Create: `app/lg_agent/tools/__init__.py`, `app/lg_agent/tools/result.py`
- Test: `tests/test_tool_result.py`

**Interfaces:**
- Produces: `truncate_result(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str`；`MAX_TOOL_RESULT_CHARS: int = 4000`

- [ ] **Step 1: 写测试**

```python
# tests/test_tool_result.py
from app.lg_agent.tools.result import truncate_result, MAX_TOOL_RESULT_CHARS

def test_short_passthrough():
    assert truncate_result("hello") == "hello"

def test_long_truncated_with_notice():
    out = truncate_result("x" * (MAX_TOOL_RESULT_CHARS + 500))
    assert len(out) <= MAX_TOOL_RESULT_CHARS + 50
    assert "已截断" in out
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_tool_result.py -v`
Expected: FAIL

- [ ] **Step 3: 写 result.py**

```python
# app/lg_agent/tools/result.py
MAX_TOOL_RESULT_CHARS = 4000

def truncate_result(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…(结果过长已截断)"
```
并建空的 `app/lg_agent/tools/__init__.py`。

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_tool_result.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/tools/__init__.py backend/deepseek_agent/llm_backend/app/lg_agent/tools/result.py backend/deepseek_agent/llm_backend/tests/test_tool_result.py
git commit -m "feat(agent): 工具结果截断器(token 预算/结果外置)"
```

---

## Task 4: web_search 工具（封装 SerpAPI）

**Files:**
- Create: `app/lg_agent/tools/web_tools.py`
- Test: `tests/test_web_tool.py`
- 先读：`app/tools/search.py`（确认现有搜索函数名与签名）

**Interfaces:**
- Produces: `web_search` (`StructuredTool`，async，`name="web_search"`)
- Consumes: `app/tools/search.py` 的现有搜索实现；`truncate_result`

- [ ] **Step 1: 读现有搜索实现，确认入口函数**

Run: `cd backend/deepseek_agent/llm_backend && sed -n '1,60p' app/tools/search.py`
记下可调用的搜索函数名（下文假设为 `search_web(query) -> str|dict`，实现时按实际名替换）。

- [ ] **Step 2: 写测试（mock 搜索后端）**

```python
# tests/test_web_tool.py
from unittest.mock import patch
from app.lg_agent.tools.web_tools import web_search

async def test_web_search_ok():
    with patch("app.lg_agent.tools.web_tools._raw_search", return_value="搜索结果文本"):
        out = await web_search.ainvoke({"query": "今天天气"})
        assert "搜索结果" in out

async def test_web_search_error_becomes_message():
    with patch("app.lg_agent.tools.web_tools._raw_search", side_effect=RuntimeError("serpapi 429")):
        out = await web_search.ainvoke({"query": "x"})
        assert "工具出错" in out
```

- [ ] **Step 3: 写 web_tools.py**

```python
# app/lg_agent/tools/web_tools.py
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.lg_agent.tools.result import truncate_result
from app.core.logger import get_logger
# TODO(实现时): 按 Step 1 的真实函数名导入，并实现 _raw_search 适配
from app.tools.search import search_web as _raw_search  # noqa: 按实际名替换

logger = get_logger(service="web_tools")

class WebSearchArgs(BaseModel):
    query: str = Field(..., description="需要联网检索的查询词")

async def _web_search(query: str) -> str:
    try:
        raw = _raw_search(query)
        return truncate_result(str(raw))
    except Exception as e:
        logger.error(f"web_search 失败: {e}")
        return f"工具出错: 联网搜索失败({e})"

web_search = StructuredTool.from_function(
    coroutine=_web_search, name="web_search",
    description="如果用户问的是实时信息、需要联网检索的产品有效信息，则使用这个工具",
    args_schema=WebSearchArgs,
)
```
注：若 `_raw_search` 是异步，改为 `await _raw_search(query)`；测试 patch 的是模块内名字 `_raw_search`，故导入时用 `as _raw_search`。

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_web_tool.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/tools/web_tools.py backend/deepseek_agent/llm_backend/tests/test_web_tool.py
git commit -m "feat(agent): web_search 工具(封装 SerpAPI,打通割裂工具体系)"
```

---

## Task 5: query_product_graph 工具（Text2Cypher，封装现有节点）

**Files:**
- Create: `app/lg_agent/tools/kg_tools.py`
- Test: `tests/test_kg_tool_cypher.py`

**Interfaces:**
- Produces: `query_product_graph` (`StructuredTool`，async，`name="query_product_graph"`)
- Consumes: `create_cypher_query_node()`（`.../components/cypher_tools/node.py`，`fn(state={"task":str}) -> {"cyphers":[CypherQueryOutputState], "steps":[...]}`，结果在 `cyphers[0].records["result"]`）；`truncate_result`

- [ ] **Step 1: 写测试（mock 现有节点，不碰真实 Neo4j）**

```python
# tests/test_kg_tool_cypher.py
from unittest.mock import patch, AsyncMock
from app.lg_agent.tools.kg_tools import query_product_graph

async def test_cypher_tool_ok():
    class _Rec:
        records = {"result": [{"name": "小米台灯", "price": 99}]}
    fake_node = AsyncMock(return_value={"cyphers": [_Rec()], "steps": ["x"]})
    with patch("app.lg_agent.tools.kg_tools.create_cypher_query_node", return_value=fake_node):
        out = await query_product_graph.ainvoke({"task": "小米台灯多少钱"})
        assert "小米台灯" in out

async def test_cypher_tool_error_becomes_message():
    with patch("app.lg_agent.tools.kg_tools.create_cypher_query_node",
               side_effect=RuntimeError("neo4j down")):
        out = await query_product_graph.ainvoke({"task": "x"})
        assert "工具出错" in out
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_kg_tool_cypher.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 在 kg_tools.py 写 query_product_graph**

```python
# app/lg_agent/tools/kg_tools.py
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.lg_agent.tools.result import truncate_result
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.cypher_tools.node import create_cypher_query_node
from app.core.logger import get_logger

logger = get_logger(service="kg_tools")

class CypherArgs(BaseModel):
    task: str = Field(..., description="要用 Cypher 回答的任务，如产品价格、库存、规格、订单、供应商等结构化查询")

def _records_text(result: dict) -> str:
    cyphers = result.get("cyphers") or []
    if not cyphers:
        return "无结果"
    return str(getattr(cyphers[0], "records", {}))

async def _query_product_graph(task: str) -> str:
    try:
        node = create_cypher_query_node()
        result = await node({"task": task})
        return truncate_result(_records_text(result))
    except Exception as e:
        logger.error(f"query_product_graph 失败: {e}")
        return f"工具出错: 商品图谱查询失败({e})"

query_product_graph = StructuredTool.from_function(
    coroutine=_query_product_graph, name="query_product_graph",
    description="如果用户问的是关于产品价格、库存、规格、订单、供应商等结构化信息，则使用这个工具生成 Cypher 查询",
    args_schema=CypherArgs,
)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_kg_tool_cypher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/tools/kg_tools.py backend/deepseek_agent/llm_backend/tests/test_kg_tool_cypher.py
git commit -m "feat(agent): query_product_graph 工具(封装 Text2Cypher 节点)"
```

## Task 6: predefined_query 工具（预置 Cypher 模板）

**Files:**
- Modify: `app/lg_agent/tools/kg_tools.py`
- Test: `tests/test_kg_tool_predefined.py`

**Interfaces:**
- Produces: `predefined_query` (`StructuredTool`，async，`name="predefined_query"`)
- Consumes: `create_predefined_cypher_node(graph, predefined_cypher_dict)`（`fn(state={"query_name","query_parameters","task"}) -> {"cyphers":[CypherOutputState]}`，结果在 `cyphers[0].records`）；`get_neo4j_graph()`；`predefined_cypher_dict`（`.../predefined_cypher/cypher_dict.py`）；`truncate_result`

- [ ] **Step 1: 写测试（mock graph + 节点）**

```python
# tests/test_kg_tool_predefined.py
from unittest.mock import patch, AsyncMock, MagicMock
from app.lg_agent.tools.kg_tools import predefined_query

async def test_predefined_ok():
    class _Rec: records = [{"product": "智能灯泡"}]
    fake_node = AsyncMock(return_value={"cyphers": [_Rec()], "steps": []})
    with patch("app.lg_agent.tools.kg_tools.get_neo4j_graph", return_value=MagicMock()), \
         patch("app.lg_agent.tools.kg_tools.create_predefined_cypher_node", return_value=fake_node):
        out = await predefined_query.ainvoke(
            {"query_name": "smart_lighting", "query": "smart_lighting", "parameters": {}})
        assert "智能灯泡" in out

async def test_predefined_error():
    with patch("app.lg_agent.tools.kg_tools.get_neo4j_graph", side_effect=RuntimeError("neo4j down")):
        out = await predefined_query.ainvoke({"query_name": "x", "query": "x", "parameters": {}})
        assert "工具出错" in out
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_kg_tool_predefined.py -v`
Expected: FAIL

- [ ] **Step 3: 向 kg_tools.py 追加 predefined_query**

```python
# 追加到 app/lg_agent/tools/kg_tools.py
from app.lg_agent.kg_sub_graph.kg_neo4j_conn import get_neo4j_graph
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.predefined_cypher.node import create_predefined_cypher_node
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.predefined_cypher.cypher_dict import predefined_cypher_dict

class PredefinedArgs(BaseModel):
    query_name: str = Field(..., description="预置查询名，如 product_by_name/smart_lighting 等")
    query: str = Field(..., description="与 query_name 相同的预置查询键")
    parameters: dict = Field(default_factory=dict, description="查询参数，如 {'product_name': '台灯'}")

async def _predefined_query(query_name: str, query: str, parameters: dict) -> str:
    try:
        graph = get_neo4j_graph()
        node = create_predefined_cypher_node(graph=graph, predefined_cypher_dict=predefined_cypher_dict)
        result = await node({"task": query_name, "query_name": query_name,
                             "query_parameters": {"query": query, "parameters": parameters}, "steps": []})
        cyphers = result.get("cyphers") or []
        return truncate_result(str(getattr(cyphers[0], "records", "无结果")) if cyphers else "无结果")
    except Exception as e:
        logger.error(f"predefined_query 失败: {e}")
        return f"工具出错: 预置查询失败({e})"

predefined_query = StructuredTool.from_function(
    coroutine=_predefined_query, name="predefined_query",
    description="高频固定查询(产品/客户/订单/供应商/类别/评论/销售分析/智能家居)的确定性快路径",
    args_schema=PredefinedArgs,
)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_kg_tool_predefined.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/tools/kg_tools.py backend/deepseek_agent/llm_backend/tests/test_kg_tool_predefined.py
git commit -m "feat(agent): predefined_query 工具(预置 Cypher 模板)"
```

---

## Task 7: search_knowledge_base 工具（GraphRAG）

**Files:**
- Modify: `app/lg_agent/tools/kg_tools.py`
- Test: `tests/test_kg_tool_graphrag.py`

**Interfaces:**
- Produces: `search_knowledge_base` (`StructuredTool`，async，`name="search_knowledge_base"`)
- Consumes: `create_graphrag_query_node()`（`.../components/customer_tools/node.py`，`fn(state={"task"}) -> {"cyphers":[GraphRAGQueryOutputState]}`，结果在 `cyphers[0].records["result"]`）；`truncate_result`

- [ ] **Step 1: 写测试（mock GraphRAG 节点）**

```python
# tests/test_kg_tool_graphrag.py
from unittest.mock import patch, AsyncMock
from app.lg_agent.tools.kg_tools import search_knowledge_base

async def test_graphrag_ok():
    class _Rec: records = {"result": "保修期为一年"}
    fake_node = AsyncMock(return_value={"cyphers": [_Rec()], "steps": []})
    with patch("app.lg_agent.tools.kg_tools.create_graphrag_query_node", return_value=fake_node):
        out = await search_knowledge_base.ainvoke({"task": "台灯保修多久"})
        assert "保修" in out

async def test_graphrag_error():
    with patch("app.lg_agent.tools.kg_tools.create_graphrag_query_node", side_effect=RuntimeError("rag fail")):
        out = await search_knowledge_base.ainvoke({"task": "x"})
        assert "工具出错" in out
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_kg_tool_graphrag.py -v`
Expected: FAIL

- [ ] **Step 3: 向 kg_tools.py 追加 search_knowledge_base**

```python
# 追加到 app/lg_agent/tools/kg_tools.py
from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.customer_tools.node import create_graphrag_query_node

class KnowledgeArgs(BaseModel):
    task: str = Field(..., description="关于产品故障、售后、保修、维修、退换货、评价等非结构化问题")

async def _search_knowledge_base(task: str) -> str:
    try:
        node = create_graphrag_query_node()
        result = await node({"task": task})
        cyphers = result.get("cyphers") or []
        rec = getattr(cyphers[0], "records", {}) if cyphers else {}
        return truncate_result(str(rec.get("result", "无结果")))
    except Exception as e:
        logger.error(f"search_knowledge_base 失败: {e}")
        return f"工具出错: 知识库检索失败({e})"

search_knowledge_base = StructuredTool.from_function(
    coroutine=_search_knowledge_base, name="search_knowledge_base",
    description="如果用户问的是产品故障、售后、保修、维修、退换货、评价等问题，则使用这个工具检索知识库",
    args_schema=KnowledgeArgs,
)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_kg_tool_graphrag.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/tools/kg_tools.py backend/deepseek_agent/llm_backend/tests/test_kg_tool_graphrag.py
git commit -m "feat(agent): search_knowledge_base 工具(封装 GraphRAG)"
```

## Task 8: 工具注册中心

**Files:**
- Create: `app/lg_agent/tools/registry.py`
- Test: `tests/test_tool_registry.py`

**Interfaces:**
- Produces: `get_tools() -> list[StructuredTool]`（4 个）；`get_tool_map() -> dict[str, StructuredTool]`
- Consumes: 4 个工具（Task 4-7）

- [ ] **Step 1: 写测试**

```python
# tests/test_tool_registry.py
from app.lg_agent.tools.registry import get_tools, get_tool_map

def test_registry_has_four_tools():
    names = {t.name for t in get_tools()}
    assert names == {"query_product_graph", "predefined_query", "search_knowledge_base", "web_search"}

def test_tool_map_lookup():
    assert get_tool_map()["web_search"].name == "web_search"
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_tool_registry.py -v`
Expected: FAIL

- [ ] **Step 3: 写 registry.py**

```python
# app/lg_agent/tools/registry.py
from langchain_core.tools import StructuredTool
from app.lg_agent.tools.kg_tools import query_product_graph, predefined_query, search_knowledge_base
from app.lg_agent.tools.web_tools import web_search

def get_tools() -> list[StructuredTool]:
    return [query_product_graph, predefined_query, search_knowledge_base, web_search]

def get_tool_map() -> dict[str, StructuredTool]:
    return {t.name: t for t in get_tools()}
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_tool_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/tools/registry.py backend/deepseek_agent/llm_backend/tests/test_tool_registry.py
git commit -m "feat(agent): 统一工具注册中心"
```

---

## Task 9: 中间件基类 + ScopeMiddleware

**Files:**
- Create: `app/lg_agent/middleware/__init__.py`, `app/lg_agent/middleware/scope.py`
- Test: `tests/test_middleware_scope.py`

**Interfaces:**
- Produces: `ContextMiddleware`（基类，`async before_model(messages, ctx) -> messages`、`async after_model(messages, ctx) -> messages`）；`run_before(middlewares, messages, ctx)`、`run_after(...)` 编排函数；`ScopeMiddleware`
- 约定：中间件操作的是「将送入模型的 message 列表」（`list[BaseMessage|dict]`），`ctx` 为 `dict`（预留扩展）

- [ ] **Step 1: 写测试**

```python
# tests/test_middleware_scope.py
from langchain_core.messages import HumanMessage, SystemMessage
from app.lg_agent.middleware import run_before
from app.lg_agent.middleware.scope import ScopeMiddleware

async def test_scope_injects_system_once():
    msgs = [HumanMessage(content="有没有智能台灯")]
    out = await run_before([ScopeMiddleware()], msgs, {})
    assert isinstance(out[0], SystemMessage)
    assert "智能家居" in out[0].content
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_middleware_scope.py -v`
Expected: FAIL

- [ ] **Step 3: 写 __init__.py（基类 + 编排）**

```python
# app/lg_agent/middleware/__init__.py
from typing import Any, List

class ContextMiddleware:
    async def before_model(self, messages: List[Any], ctx: dict) -> List[Any]:
        return messages
    async def after_model(self, messages: List[Any], ctx: dict) -> List[Any]:
        return messages

async def run_before(middlewares, messages, ctx):
    for mw in middlewares:
        messages = await mw.before_model(messages, ctx)
    return messages

async def run_after(middlewares, messages, ctx):
    for mw in middlewares:
        messages = await mw.after_model(messages, ctx)
    return messages
```

- [ ] **Step 4: 写 scope.py**

```python
# app/lg_agent/middleware/scope.py
from langchain_core.messages import SystemMessage
from app.lg_agent.middleware import ContextMiddleware
from app.lg_agent.scope_config import SCOPE_DESCRIPTION

_SCOPE_PROMPT = (
    "你是智能家居电商客服。以下是本店经营范围：\n" + SCOPE_DESCRIPTION +
    "\n对超出经营范围的【商品类】请求要礼貌拒绝(如：抱歉，我家暂时没有这方面的商品)；"
    "普通闲聊可正常回答。有需要时调用工具查询商品/知识库。"
)

class ScopeMiddleware(ContextMiddleware):
    async def before_model(self, messages, ctx):
        if messages and getattr(messages[0], "type", None) == "system":
            return messages
        return [SystemMessage(content=_SCOPE_PROMPT), *messages]
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_middleware_scope.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/middleware/__init__.py backend/deepseek_agent/llm_backend/app/lg_agent/middleware/scope.py backend/deepseek_agent/llm_backend/tests/test_middleware_scope.py
git commit -m "feat(agent): 中间件基类 + ScopeMiddleware(经营范围注入)"
```

---

## Task 10: HistoryCompressionMiddleware（上下文压缩）

**Files:**
- Create: `app/lg_agent/middleware/history.py`
- Modify: `app/core/config.py`（加 `HISTORY_COMPRESSION_THRESHOLD: int = 12`）
- Test: `tests/test_middleware_history.py`

**Interfaces:**
- Produces: `HistoryCompressionMiddleware(model=None)`（`model=None` 时用 `get_agent_model`；测试注入 FakeChatModel）
- 行为：消息 ≤ 阈值 → 原样返回；超阈值 → 保留 system + 最近 N 条，把更早的问答对压成一条 SystemMessage 摘要（调一次 model）；system / 未闭合 tool_call 链不参与压缩

- [ ] **Step 1: 写测试**

```python
# tests/test_middleware_history.py
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.lg_agent.middleware.history import HistoryCompressionMiddleware
from tests.conftest import FakeChatModel

async def test_below_threshold_noop():
    mw = HistoryCompressionMiddleware(model=FakeChatModel())
    msgs = [HumanMessage(content="hi"), AIMessage(content="hello")]
    assert await mw.before_model(msgs, {}) == msgs

async def test_above_threshold_compresses():
    mw = HistoryCompressionMiddleware(model=FakeChatModel(responses=[AIMessage(content="历史摘要")]))
    msgs = [SystemMessage(content="sys")] + [HumanMessage(content=f"q{i}") for i in range(30)]
    out = await mw.before_model(msgs, {})
    assert len(out) < len(msgs)
    assert out[0].type == "system"
    assert any("历史摘要" in getattr(m, "content", "") for m in out)
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_middleware_history.py -v`
Expected: FAIL

- [ ] **Step 3: 加配置 + 写 history.py**

`app/core/config.py` 加字段：`HISTORY_COMPRESSION_THRESHOLD: int = 12`

```python
# app/lg_agent/middleware/history.py
from langchain_core.messages import SystemMessage, HumanMessage
from app.lg_agent.middleware import ContextMiddleware
from app.lg_agent.model_factory import get_agent_model
from app.core.config import settings

_KEEP_RECENT = 6

class HistoryCompressionMiddleware(ContextMiddleware):
    def __init__(self, model=None):
        self._model = model
    async def before_model(self, messages, ctx):
        threshold = settings.HISTORY_COMPRESSION_THRESHOLD
        if len(messages) <= threshold:
            return messages
        head = [m for m in messages[:1] if getattr(m, "type", None) == "system"]
        body_start = len(head)
        recent = messages[-_KEEP_RECENT:]
        to_compress = messages[body_start:-_KEEP_RECENT]
        if not to_compress:
            return messages
        model = self._model or get_agent_model(tags=["compress"])
        text = "\n".join(f"{getattr(m,'type','?')}: {getattr(m,'content','')}" for m in to_compress)
        summary = await model.ainvoke(
            [SystemMessage(content="把以下客服对话历史压成要点摘要，保留用户关注的商品与结论："),
             HumanMessage(content=text)])
        return [*head, SystemMessage(content=f"[历史摘要] {summary.content}"), *recent]
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_middleware_history.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/middleware/history.py backend/deepseek_agent/llm_backend/app/core/config.py backend/deepseek_agent/llm_backend/tests/test_middleware_history.py
git commit -m "feat(agent): HistoryCompressionMiddleware(上下文压缩/Durable Context)"
```

## Task 11: ToolResultMiddleware（工具结果规范化兜底）

**Files:**
- Create: `app/lg_agent/middleware/tool_result.py`
- Test: `tests/test_middleware_tool_result.py`

**Interfaces:**
- Produces: `ToolResultMiddleware`（`after_model`：遍历消息，把超限的 `ToolMessage.content` 截断兜底）
- Consumes: `truncate_result`

- [ ] **Step 1: 写测试**

```python
# tests/test_middleware_tool_result.py
from langchain_core.messages import ToolMessage
from app.lg_agent.middleware.tool_result import ToolResultMiddleware
from app.lg_agent.tools.result import MAX_TOOL_RESULT_CHARS

async def test_oversized_tool_message_truncated():
    mw = ToolResultMiddleware()
    msgs = [ToolMessage(content="y" * (MAX_TOOL_RESULT_CHARS + 1000), tool_call_id="1")]
    out = await mw.after_model(msgs, {})
    assert len(out[0].content) <= MAX_TOOL_RESULT_CHARS + 50
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_middleware_tool_result.py -v`
Expected: FAIL

- [ ] **Step 3: 写 tool_result.py**

```python
# app/lg_agent/middleware/tool_result.py
from langchain_core.messages import ToolMessage
from app.lg_agent.middleware import ContextMiddleware
from app.lg_agent.tools.result import truncate_result

class ToolResultMiddleware(ContextMiddleware):
    async def after_model(self, messages, ctx):
        for m in messages:
            if isinstance(m, ToolMessage) and isinstance(m.content, str):
                m.content = truncate_result(m.content)
        return messages
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_middleware_tool_result.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/middleware/tool_result.py backend/deepseek_agent/llm_backend/tests/test_middleware_tool_result.py
git commit -m "feat(agent): ToolResultMiddleware(工具结果规范化兜底)"
```

---

## Task 12: AgentState 加 iteration 字段

**Files:**
- Modify: `app/lg_agent/lg_states.py`
- Test: `tests/test_agent_state.py`

**Interfaces:**
- Produces: `AgentState.iteration: int`（默认 0，回环刹车计数）
- 说明：Router 瘦身 / 删 steps·hallucination 等死字段**推迟到 Task 16**（legacy 图仍引用，特性开关期间不能动），本任务只加 `iteration`，零破坏。

- [ ] **Step 1: 写测试**

```python
# tests/test_agent_state.py
from app.lg_agent.lg_states import AgentState

def test_agent_state_has_iteration_default_zero():
    s = AgentState(messages=[])
    assert s.iteration == 0

def test_agent_state_iteration_settable():
    s = AgentState(messages=[], iteration=3)
    assert s.iteration == 3
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_agent_state.py -v`
Expected: FAIL（`TypeError: unexpected keyword argument 'iteration'`）

- [ ] **Step 3: 在 AgentState 加字段**

在 `app/lg_agent/lg_states.py` 的 `AgentState` 类内（`hallucination` 字段后）追加：

```python
    iteration: int = field(default=0)
    """ReAct 回环刹车计数：每进一次 agent 节点 +1，超 max_iterations 强制收尾。"""
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_agent_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/lg_states.py backend/deepseek_agent/llm_backend/tests/test_agent_state.py
git commit -m "feat(agent): AgentState 加 iteration 回环计数字段"
```

## Task 13: Agent 回环图（核心）

**Files:**
- Create: `app/lg_agent/agent_loop.py`
- Test: `tests/test_agent_loop.py`

**Interfaces:**
- Produces: `agent_node(state, *, config)`、`tools_node(state)`、`should_continue(state) -> Literal["tools","__end__"]`、`route_entry(state) -> Literal["agent","image","file"]`、`build_agent_loop(checkpointer=None, model=None) -> CompiledStateGraph`
- Consumes: `get_tools`/`get_tool_map`（Task 8）；`get_agent_model`（Task 2）；`run_before`/`run_after` + 3 中间件（Task 9-11）；`AgentState.iteration`（Task 12）；`settings`（`max_iterations` 用常量 `MAX_ITERATIONS=6`）
- 关键取舍：**去掉原 LLM 路由节点**。general/additional/graphrag 全并入 agent；image 靠 `config.configurable.image_path` 判定；file 靠关键字兜底。路由是纯函数（省一次分类 LLM 调用）。

- [ ] **Step 1: 写测试（FakeChatModel 脚本化 tool_call→最终答）**

```python
# tests/test_agent_loop.py
from unittest.mock import patch
from langchain_core.messages import AIMessage, HumanMessage
from app.lg_agent.lg_states import AgentState
from app.lg_agent import agent_loop
from tests.conftest import FakeChatModel

async def test_loop_runs_tool_then_answers():
    fake = FakeChatModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "x"}, "id": "1"}]),
        AIMessage(content="最终答"),
    ])
    with patch.object(agent_loop, "get_agent_model", return_value=fake), \
         patch("app.lg_agent.tools.registry.web_search") as ws:
        ws.name = "web_search"
        async def _fake_run(**kw): return "搜索到的内容"
        ws.ainvoke.side_effect = lambda a: _fake_run()
        state = AgentState(messages=[HumanMessage(content="问题")])
        s1 = await agent_loop.agent_node(state, config={"configurable": {}})
        assert s1["messages"][-1].tool_calls      # 第一轮出 tool_call
        assert should_tools(s1)                     # 见下方 helper

def should_tools(partial):
    from app.lg_agent.agent_loop import should_continue
    st = AgentState(messages=partial["messages"], iteration=partial.get("iteration", 0))
    return should_continue(st) == "tools"

async def test_brake_forces_final_answer_over_max():
    fake = FakeChatModel(responses=[AIMessage(content="被迫作答")])
    with patch.object(agent_loop, "get_agent_model", return_value=fake):
        state = AgentState(messages=[HumanMessage(content="x")], iteration=99)
        out = await agent_loop.agent_node(state, config={"configurable": {}})
        assert out["messages"][-1].content == "被迫作答"
        assert not getattr(out["messages"][-1], "tool_calls", None)  # 超限不再绑工具
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_agent_loop.py -v`
Expected: FAIL

- [ ] **Step 3: 写 agent_loop.py**

```python
# app/lg_agent/agent_loop.py
from typing import Literal
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from app.lg_agent.lg_states import AgentState, InputState
from app.lg_agent.model_factory import get_agent_model
from app.lg_agent.tools.registry import get_tools, get_tool_map
from app.lg_agent.middleware import run_before, run_after
from app.lg_agent.middleware.scope import ScopeMiddleware
from app.lg_agent.middleware.history import HistoryCompressionMiddleware
from app.lg_agent.middleware.tool_result import ToolResultMiddleware
from app.core.logger import get_logger

logger = get_logger(service="agent_loop")
MAX_ITERATIONS = 6

def _middlewares():
    return [ScopeMiddleware(), HistoryCompressionMiddleware(), ToolResultMiddleware()]

async def agent_node(state: AgentState, *, config: RunnableConfig):
    mws = _middlewares()
    messages = await run_before(mws, list(state.messages), {})
    model = get_agent_model(tags=["agent"])
    over_limit = state.iteration >= MAX_ITERATIONS
    runnable = model if over_limit else model.bind_tools(get_tools())
    ai = await runnable.ainvoke(messages)
    return {"messages": [ai], "iteration": state.iteration + 1}

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    last = state.messages[-1] if state.messages else None
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return "__end__"

async def tools_node(state: AgentState):
    tool_map = get_tool_map()
    last = state.messages[-1]
    out = []
    for call in last.tool_calls:
        tool = tool_map.get(call["name"])
        if tool is None:
            out.append(ToolMessage(content=f"工具出错: 未知工具 {call['name']}", tool_call_id=call["id"]))
            continue
        try:
            result = await tool.ainvoke(call["args"])   # StructuredTool 会按 args_schema 校验
        except Exception as e:
            result = f"工具出错: 参数或执行错误({e})"
        out.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
    mws = _middlewares()
    out = await run_after(mws, out, {})
    return {"messages": out}
```

- [ ] **Step 4: 追加路由 + 图构建到 agent_loop.py**

```python
def route_entry(state: AgentState) -> Literal["agent", "image", "file"]:
    # image/file 由 config 注入到 state（见 main.py 集成）；默认走 agent 回环
    router = getattr(state, "router", None)
    rtype = router.get("type") if isinstance(router, dict) else None
    if rtype == "image":
        return "image"
    if rtype == "file":
        return "file"
    return "agent"

async def image_node(state: AgentState, *, config: RunnableConfig):
    from app.lg_agent.lg_builder import create_image_query  # 复用现有视觉逻辑
    return await create_image_query(state, config=config)

async def file_fallback(state: AgentState):
    return {"messages": [AIMessage(content="抱歉，我暂时还不支持文件解析，您可以用文字描述您的问题～")]}

def build_agent_loop(checkpointer=None, model=None):
    b = StateGraph(AgentState, input=InputState)
    b.add_node("agent", agent_node)
    b.add_node("tools", tools_node)
    b.add_node("image", image_node)
    b.add_node("file", file_fallback)
    b.add_conditional_edges(START, route_entry,
                            {"agent": "agent", "image": "image", "file": "file"})
    b.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": END})
    b.add_edge("tools", "agent")
    b.add_edge("image", END)
    b.add_edge("file", END)
    return b.compile(checkpointer=checkpointer)
```
注：`route_entry` 读 `state.router`（legacy `Router` 结构保留）。main.py 集成时按 image_path/文件存在性预置 `router={"type": "image"|"file"|"agent"}`（Task 15）。

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_agent_loop.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/agent_loop.py backend/deepseek_agent/llm_backend/tests/test_agent_loop.py
git commit -m "feat(agent): ReAct 回环图(agent⇄tools+刹车+纯函数路由)"
```

## Task 14: graph_factory（特性开关 + 新旧图并存）

**Files:**
- Create: `app/lg_agent/graph_factory.py`
- Test: `tests/test_graph_factory.py`

**Interfaces:**
- Produces: `build_graph(mode: str | None = None, checkpointer=None) -> CompiledStateGraph`（`mode` 缺省读 `settings.LG_AGENT_MODE`；`loop`→`build_agent_loop`，`legacy`→现有 `lg_builder.graph`）
- Consumes: `build_agent_loop`（Task 13）；`lg_builder.graph`（现有）

- [ ] **Step 1: 写测试**

```python
# tests/test_graph_factory.py
from unittest.mock import patch, MagicMock
from app.lg_agent.graph_factory import build_graph

def test_loop_mode_builds_agent_loop():
    with patch("app.lg_agent.graph_factory.build_agent_loop", return_value=MagicMock()) as b:
        build_graph(mode="loop")
        assert b.called

def test_legacy_mode_returns_existing_graph():
    with patch("app.lg_agent.graph_factory.build_agent_loop") as b:
        g = build_graph(mode="legacy")
        assert not b.called
        assert g is not None
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_graph_factory.py -v`
Expected: FAIL

- [ ] **Step 3: 写 graph_factory.py**

```python
# app/lg_agent/graph_factory.py
from app.lg_agent.agent_loop import build_agent_loop
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(service="graph_factory")

def build_graph(mode: str | None = None, checkpointer=None):
    mode = mode or settings.LG_AGENT_MODE
    if mode == "loop":
        logger.info("Building agent-loop graph")
        return build_agent_loop(checkpointer=checkpointer)
    logger.info("Using legacy graph")
    from app.lg_agent.lg_builder import graph as legacy_graph
    return legacy_graph
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_graph_factory.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/lg_agent/graph_factory.py backend/deepseek_agent/llm_backend/tests/test_graph_factory.py
git commit -m "feat(agent): graph_factory 特性开关(新旧图并存)"
```

---

## Task 15: main.py 集成 + AsyncSqliteSaver + SSE 噪音过滤

**Files:**
- Modify: `main.py`（langgraph 流式段 + lifespan）
- Test: `tests/test_sse_contract.py`

**Interfaces:**
- Consumes: `build_graph`（Task 14）；`AsyncSqliteSaver`（`langgraph.checkpoint.sqlite.aio`）
- Produces: `filter_stream_chunk(chunk, metadata) -> str | None`（抽成纯函数便于测；返回要发给前端的文本，或 None 表示吃掉）
- SSE 红线：只吐最终 agent 作答文本，格式 `data: "<json字符串>"`；tool_call、ToolMessage、含 tool_calls 的 AIMessage 全部返 None。

- [ ] **Step 1: 写 SSE 契约测试（纯函数，锁死红线）**

```python
# tests/test_sse_contract.py
from langchain_core.messages import AIMessage, ToolMessage
from main import filter_stream_chunk   # 从 main 导出纯函数

def test_final_answer_passes_through():
    msg = AIMessage(content="最终答")
    assert filter_stream_chunk(msg, {"tags": []}) == "最终答"

def test_tool_call_chunk_suppressed():
    msg = AIMessage(content="", tool_calls=[{"name": "web_search", "args": {}, "id": "1"}])
    assert filter_stream_chunk(msg, {"tags": []}) is None

def test_tool_message_suppressed():
    assert filter_stream_chunk(ToolMessage(content="工具原始结果", tool_call_id="1"), {"tags": []}) is None

def test_empty_content_suppressed():
    assert filter_stream_chunk(AIMessage(content=""), {"tags": []}) is None
```

- [ ] **Step 2: 运行，确认失败**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_sse_contract.py -v`
Expected: FAIL（`ImportError: cannot import name 'filter_stream_chunk'`）

- [ ] **Step 3: 在 main.py 定义 filter_stream_chunk 纯函数**

在 `main.py` 顶部区域（路由定义前）添加：

```python
from langchain_core.messages import AIMessage, ToolMessage

def filter_stream_chunk(chunk, metadata) -> str | None:
    """SSE 噪音过滤：只放行最终 agent 作答文本，吃掉所有工具调用/工具结果噪音。"""
    if isinstance(chunk, ToolMessage):
        return None
    if getattr(chunk, "additional_kwargs", {}).get("tool_calls"):
        return None
    if isinstance(chunk, AIMessage) and getattr(chunk, "tool_calls", None):
        return None
    content = getattr(chunk, "content", None)
    if not content:
        return None
    if "research_plan" in (metadata or {}).get("tags", []):
        return None
    return content
```

- [ ] **Step 4: 用 filter_stream_chunk 改写两个 process_stream**

把 `main.py:341-392` 两段 `process_stream` 内的逐 chunk 判断，统一改为：

```python
async for c, metadata in graph.astream(input=input_state, stream_mode="messages", config=thread_config):
    text = filter_stream_chunk(c, metadata)
    if text is not None:
        yield f"data: {json.dumps(text, ensure_ascii=False)}\n\n"
```
（resume 分支同理。`graph` 改为模块级 `build_graph(...)` 的产物，见 Step 5。）

- [ ] **Step 5: 换 graph 来源 + 挂 AsyncSqliteSaver 到 lifespan**

把 `main.py` 顶部 `from app.lg_agent.lg_builder import graph` 删除，改为 FastAPI lifespan 内构建：

```python
from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.lg_agent.graph_factory import build_graph
from app.core.config import settings

graph = None  # 模块级，lifespan 内赋值

@asynccontextmanager
async def lifespan(app):
    global graph
    async with AsyncSqliteSaver.from_conn_string(settings.SQLITE_CHECKPOINT_PATH) as saver:
        graph = build_graph(checkpointer=saver)
        yield

app = FastAPI(lifespan=lifespan)   # 替换现有 app = FastAPI(...) 并保留原有参数
```
注：现有 `app = FastAPI(...)` 的其它参数（title 等）合并进来；CORS 等 `add_middleware` 保持不变。

- [ ] **Step 6: 运行 SSE 测试 + 启动冒烟**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_sse_contract.py -v && python -c "import main; print('import ok')"`
Expected: PASS + `import ok`

- [ ] **Step 7: Commit**

```bash
git add backend/deepseek_agent/llm_backend/main.py backend/deepseek_agent/llm_backend/tests/test_sse_contract.py
git commit -m "feat(agent): main.py 接入 build_graph+AsyncSqliteSaver+SSE 噪音过滤"
```

## Task 16: 立即删死代码（与重构无关的死/会崩代码）

**Files:**
- Delete: `app/lg_agent/kg_sub_graph/multi_tools.py`
- Delete: `app/lg_agent/kg_sub_graph/kg_builder.py`
- Modify: `app/lg_agent/lg_builder.py`（删 `check_hallucinations` 函数 462-495 + 相关 import）
- Modify: `app/lg_agent/kg_sub_graph/kg_tools_list.py`（删 `real_time_network_query` 类）
- Modify: `app/lg_agent/kg_sub_graph/planner/node.py`（删调试 `print` 131-142）
- Test: `tests/test_import_smoke.py`

**Interfaces:**
- 前置确认：这些目标在 Task 1-15 完成后仍无运行时引用（legacy 图未用到它们）。

- [ ] **Step 1: 写导入冒烟测试**

```python
# tests/test_import_smoke.py
def test_main_imports():
    import main
    assert hasattr(main, "app")

def test_graph_factory_both_modes_compile():
    from unittest.mock import patch, MagicMock
    from app.lg_agent.graph_factory import build_graph
    with patch("app.lg_agent.graph_factory.build_agent_loop", return_value=MagicMock()):
        assert build_graph(mode="loop") is not None
    assert build_graph(mode="legacy") is not None
```

- [ ] **Step 2: 运行，确认当前通过（删之前基线）**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest tests/test_import_smoke.py -v`
Expected: PASS（删代码前先确认基线绿）

- [ ] **Step 3: 确认无引用后删除**

```bash
cd backend/deepseek_agent/llm_backend
grep -rn "multi_tools\|check_hallucinations\|real_time_network_query\|kg_builder" --include=*.py app main | grep -v "multi_tool.py"
```
Expected: 无 import 级引用（仅注释/字符串可忽略）。然后：
- 删 `app/lg_agent/kg_sub_graph/multi_tools.py`、`app/lg_agent/kg_sub_graph/kg_builder.py`
- `lg_builder.py` 删 `check_hallucinations`（462-495）及其用到的 `CHECK_HALLUCINATIONS`/`GradeHallucinations` import（若无其它引用）
- `kg_tools_list.py` 删 `real_time_network_query` 类（71-73）
- `planner/node.py` 删调试 `print`（131-142）

- [ ] **Step 4: 运行冒烟 + 全量测试，确认仍通过**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest -v`
Expected: 全绿 + import ok（删除未破坏任何引用）

- [ ] **Step 5: Commit**

```bash
git add -A backend/deepseek_agent/llm_backend
git commit -m "chore(agent): 删立即死代码(multi_tools/check_hallucinations/real_time_network_query/kg_builder/调试print)"
```

---

## Task 17: 切换默认 loop + 全量验证（+ 延迟清理说明）

**Files:**
- Modify: `app/core/config.py`（`LG_AGENT_MODE` 默认 `legacy` → `loop`）
- Modify: `.gitignore`（忽略 `*.sqlite` checkpoint 文件，若尚未忽略）

**Interfaces:** 无新接口。本任务是集成验证关口。

- [ ] **Step 1: 全量测试全绿**

Run: `cd backend/deepseek_agent/llm_backend && python -m pytest -v`
Expected: 所有用例 PASS。

- [ ] **Step 2: 翻开关**

`app/core/config.py`：`LG_AGENT_MODE: str = "loop"`。
`.gitignore` 追加（若无）：`*.sqlite`、`checkpoints.sqlite`。

- [ ] **Step 3: 启动冒烟（两模式均 compile）**

Run: `cd backend/deepseek_agent/llm_backend && python -c "import main; print('ok')" && python -m pytest tests/test_import_smoke.py -v`
Expected: `ok` + PASS。

- [ ] **Step 4: 手动真实验证（需真实后端，记录结果不自动化）**

启动服务，向电商客服发一个需多步的问题（如「智能台灯有哪些、最便宜的多少钱」），确认：回环完成 ≥2 次工具调用、SSE 只收到最终答文本、前端气泡正常渲染、无原始 JSON/工具噪音。`LG_AGENT_MODE=legacy` 可即时回滚。

- [ ] **Step 5: Commit**

```bash
git add backend/deepseek_agent/llm_backend/app/core/config.py .gitignore
git commit -m "chore(agent): 默认切换 LG_AGENT_MODE=loop + 忽略 sqlite checkpoint"
```

- [ ] **Step 6: 延迟清理（本次不执行，记录为后续）**

回环在真实使用验证稳定后，另起提交删除 legacy 专用代码：`workflows/multi_agent/multi_tool.py`、`tool_selection` 节点、两份 `planner`、`guardrails` 节点、`lg_builder.py` 的 `respond_to_general_query`/`get_additional_info`/`create_research_plan`，以及 `AgentState` 的 `steps`/`hallucination` 死字段与 `Router` 瘦身。**此步不在本计划的自动执行范围**，避免过早移除回滚路径。

---

## Self-Review

**1. Spec coverage（spec §→task 映射）**
- §2 新图结构/路由三分/回环/刹车/guardrails转中间件/原子图退役 → Task 13（+ Scope 在 Task 9）✅
- §3 统一工具层(4工具/统一接口/token预算/错误即消息/参数校验/删DANGEROUS) → Task 3-8 ✅
- §4 Context 中间件(基类/Scope/History/ToolResult/无侵入) → Task 9-11 ✅
- §5.1 状态精简(加iteration) → Task 12（Router瘦身/删死字段延迟到 Task 17 Step 6，含理由）✅
- §5.2 AsyncSqliteSaver → Task 15 ✅
- §5.3 SSE 契约 → Task 15（纯函数 + 测试）✅
- §5.4 死接口保留 → 未改（符合）✅
- §6 特性开关 → Task 14 ✅
- §7 分阶段 → Task 1→17 顺序对应 ✅
- §8 测试(5类) → 回环控制 T13 / 工具层 T4-7 / 中间件 T9-11 / SSE契约 T15 / smoke T16 ✅
- §9 死代码(立即档) → Task 16；(延迟档) → Task 17 Step 6 ✅
- §10 不做项 → 计划未触碰 Gateway/Memory/治理/沙箱/前端 ✅
- §11 文件清单 → File Structure 节 ✅
- §12 验收 → Task 16/17 的 pytest 全绿 + 冒烟 + 手动验证 ✅

**2. Placeholder scan**：工具/中间件/图均给出可运行代码；唯一标注「实现时按实际名替换」的是 Task 4 的 `_raw_search`（因 `app/tools/search.py` 真实函数名需读文件确认，已在 Step 1 要求先读），非占位符而是显式的实现期动作。

**3. Type consistency**：`get_tools`/`get_tool_map`(T8)↔`agent_node`/`tools_node`(T13) 一致；`truncate_result`/`MAX_TOOL_RESULT_CHARS`(T3)↔工具(T4-7)+ToolResultMiddleware(T11) 一致；`run_before`/`run_after`+`ContextMiddleware`(T9)↔History(T10)/ToolResult(T11)/agent_node(T13) 一致；`build_agent_loop`(T13)↔`build_graph`(T14)↔main.py(T15) 一致；`filter_stream_chunk`(T15) 签名与测试一致；`AgentState.iteration`(T12)↔`agent_node`刹车(T13) 一致。

**4. Review Focus 覆盖**：工具后端不可达→T4/5/6/7 的 error 用例；无限回环→T13 刹车用例；超大结果→T3+T11 截断用例；SSE 噪音泄漏→T15 契约用例；非法工具参数→T13 tools_node try/except（StructuredTool args_schema 校验）。五条均有归属任务测试。
