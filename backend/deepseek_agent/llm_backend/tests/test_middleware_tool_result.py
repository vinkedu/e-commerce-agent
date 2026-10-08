from langchain_core.messages import ToolMessage
from app.lg_agent.middleware.tool_result import ToolResultMiddleware
from app.lg_agent.tools.result import MAX_TOOL_RESULT_CHARS


async def test_oversized_tool_message_truncated():
    mw = ToolResultMiddleware()
    msgs = [ToolMessage(content="y" * (MAX_TOOL_RESULT_CHARS + 1000), tool_call_id="1")]
    out = await mw.after_model(msgs, {})
    assert len(out[0].content) <= MAX_TOOL_RESULT_CHARS + 50
