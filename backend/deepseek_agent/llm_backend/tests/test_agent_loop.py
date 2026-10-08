from unittest.mock import patch
from langchain_core.messages import AIMessage, HumanMessage
from app.lg_agent.lg_states import AgentState
from app.lg_agent import agent_loop
from tests.conftest import FakeChatModel


def should_tools(partial):
    from app.lg_agent.agent_loop import should_continue
    st = AgentState(messages=partial["messages"], iteration=partial.get("iteration", 0))
    return should_continue(st) == "tools"


async def test_loop_runs_tool_then_answers():
    fake = FakeChatModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "x"}, "id": "1"}]),
        AIMessage(content="最终答"),
    ])
    with patch.object(agent_loop, "get_agent_model", return_value=fake):
        state = AgentState(messages=[HumanMessage(content="问题")])
        s1 = await agent_loop.agent_node(state, config={"configurable": {}})
        assert s1["messages"][-1].tool_calls      # 第一轮出 tool_call
        assert should_tools(s1)


def test_route_entry_image_from_config():
    # 图片经 config.configurable.image_path 传入（main.py 现状），应路由到 image 分支
    from app.lg_agent.agent_loop import route_entry
    st = AgentState(messages=[])
    assert route_entry(st, {"configurable": {"image_path": "/tmp/a.jpg"}}) == "image"
    assert route_entry(st, {"configurable": {}}) == "agent"
    assert route_entry(st, None) == "agent"


async def test_agent_node_model_failure_degrades_gracefully():
    # 模型调用抛错(如上下文格式 400 / 服务 500)时，agent_node 必须降级为道歉消息，不冒泡崩图
    class _BoomModel:
        def bind_tools(self, *_a, **_k):
            return self
        async def ainvoke(self, *_a, **_k):
            raise RuntimeError("llm 500")
    with patch.object(agent_loop, "get_agent_model", return_value=_BoomModel()):
        state = AgentState(messages=[HumanMessage(content="x")])
        out = await agent_loop.agent_node(state, config={"configurable": {}})
        last = out["messages"][-1]
        assert not getattr(last, "tool_calls", None)
        assert ("抱歉" in last.content) or ("出错" in last.content)


async def test_brake_forces_final_answer_over_max():
    fake = FakeChatModel(responses=[AIMessage(content="被迫作答")])
    with patch.object(agent_loop, "get_agent_model", return_value=fake):
        state = AgentState(messages=[HumanMessage(content="x")], iteration=99)
        out = await agent_loop.agent_node(state, config={"configurable": {}})
        assert out["messages"][-1].content == "被迫作答"
        assert not getattr(out["messages"][-1], "tool_calls", None)  # 超限不再绑工具
