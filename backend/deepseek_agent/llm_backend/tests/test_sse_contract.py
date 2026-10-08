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
