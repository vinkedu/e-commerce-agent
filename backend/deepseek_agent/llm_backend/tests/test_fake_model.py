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
