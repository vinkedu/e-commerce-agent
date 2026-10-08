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


async def test_brake_forces_final_answer_over_max():
    fake = FakeChatModel(responses=[AIMessage(content="被迫作答")])
    with patch.object(agent_loop, "get_agent_model", return_value=fake):
        state = AgentState(messages=[HumanMessage(content="x")], iteration=99)
        out = await agent_loop.agent_node(state, config={"configurable": {}})
        assert out["messages"][-1].content == "被迫作答"
        assert not getattr(out["messages"][-1], "tool_calls", None)  # 超限不再绑工具
