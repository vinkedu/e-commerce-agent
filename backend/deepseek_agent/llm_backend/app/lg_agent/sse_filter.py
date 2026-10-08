"""SSE 噪音过滤：只放行最终 agent 作答文本，吃掉所有工具调用/工具结果噪音。

独立轻量模块（不依赖重服务），便于单测与 main.py 复用，严守「不改前端」契约。
"""
from langchain_core.messages import AIMessage, ToolMessage


def filter_stream_chunk(chunk, metadata) -> str | None:
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
