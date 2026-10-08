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


def route_entry(state: AgentState) -> Literal["agent", "image", "file"]:
    # image/file 由 main.py 预置到 state.router；默认走 agent 回环
    router = getattr(state, "router", None)
    rtype = router.get("type") if isinstance(router, dict) else None
    if rtype == "image":
        return "image"
    if rtype == "file":
        return "file"
    return "agent"


async def image_node(state: AgentState, *, config: RunnableConfig):
    from app.lg_agent.lg_builder import create_image_query  # 惰性复用现有视觉逻辑
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
