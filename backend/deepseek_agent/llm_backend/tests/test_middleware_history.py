from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
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


def _has_orphan_tool_message(messages) -> bool:
    """存在一个 ToolMessage，其前面没有带 tool_calls 的 AIMessage → 孤儿(会被模型 400)。"""
    seen_tool_call = False
    for m in messages:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            seen_tool_call = True
        if isinstance(m, ToolMessage):
            if not seen_tool_call:
                return True
    return False


async def test_compression_does_not_orphan_tool_message():
    from langchain_core.messages import ToolMessage
    mw = HistoryCompressionMiddleware(model=FakeChatModel(responses=[AIMessage(content="摘要")]))
    # 构造：切点(-6)恰好落在 ToolMessage 上，其配对 AIMessage(tool_calls) 在待压缩段
    msgs = (
        [SystemMessage(content="sys")]
        + [HumanMessage(content=f"q{i}") for i in range(6)]
        + [AIMessage(content="", tool_calls=[{"name": "web_search", "args": {}, "id": "1"}])]
        + [ToolMessage(content="结果", tool_call_id="1")]
        + [HumanMessage(content=f"r{i}") for i in range(5)]
    )
    out = await mw.before_model(msgs, {})
    assert not _has_orphan_tool_message(out), "压缩后不得留下孤儿 ToolMessage"
