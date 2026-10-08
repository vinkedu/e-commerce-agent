from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from app.lg_agent.middleware import ContextMiddleware
from app.lg_agent.model_factory import get_agent_model
from app.core.config import settings

_KEEP_RECENT = 6


class HistoryCompressionMiddleware(ContextMiddleware):
    def __init__(self, model=None):
        self._model = model

    async def before_model(self, messages, ctx):
        threshold = settings.HISTORY_COMPRESSION_THRESHOLD
        if len(messages) <= threshold:
            return messages
        head = [m for m in messages[:1] if getattr(m, "type", None) == "system"]
        body_start = len(head)
        split = len(messages) - _KEEP_RECENT
        # 不在 tool_call↔ToolMessage 之间切：切点若落在 ToolMessage 上，前移到其配对
        # AIMessage(tool_calls)，让整条 tool 链留在 recent，避免孤儿 ToolMessage 触发模型 400
        while split > body_start and isinstance(messages[split], ToolMessage):
            split -= 1
        recent = messages[split:]
        to_compress = messages[body_start:split]
        if not to_compress:
            return messages
        model = self._model or get_agent_model(tags=["compress"])
        text = "\n".join(f"{getattr(m,'type','?')}: {getattr(m,'content','')}" for m in to_compress)
        summary = await model.ainvoke(
            [SystemMessage(content="把以下客服对话历史压成要点摘要，保留用户关注的商品与结论："),
             HumanMessage(content=text)])
        return [*head, SystemMessage(content=f"[历史摘要] {summary.content}"), *recent]
