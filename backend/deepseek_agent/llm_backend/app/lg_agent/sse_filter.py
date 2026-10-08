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
    # 非答案的内部 LLM 调用必须打这些 tag，否则其 token 会被当答案泄漏给前端。
    # research_plan: legacy 子图内部；compress: 历史压缩中间件。
    suppressed_tags = {"research_plan", "compress"}
    if suppressed_tags & set((metadata or {}).get("tags", []) or []):
        return None
    return content
