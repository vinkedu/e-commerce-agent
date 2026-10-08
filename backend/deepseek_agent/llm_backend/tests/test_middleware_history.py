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
