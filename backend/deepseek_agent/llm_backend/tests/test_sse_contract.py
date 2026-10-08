from langchain_core.messages import AIMessage, ToolMessage
from app.lg_agent.sse_filter import filter_stream_chunk


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


def test_compress_tagged_chunk_suppressed():
    # 历史压缩用的内部 LLM(tag=compress)输出不得当作答案泄漏给前端
    msg = AIMessage(content="[历史摘要] 用户关注智能台灯")
    assert filter_stream_chunk(msg, {"tags": ["compress"]}) is None
