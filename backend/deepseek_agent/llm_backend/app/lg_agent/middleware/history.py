from langchain_core.messages import SystemMessage, HumanMessage
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
        recent = messages[-_KEEP_RECENT:]
        to_compress = messages[body_start:-_KEEP_RECENT]
        if not to_compress:
            return messages
        model = self._model or get_agent_model(tags=["compress"])
        text = "\n".join(f"{getattr(m,'type','?')}: {getattr(m,'content','')}" for m in to_compress)
        summary = await model.ainvoke(
            [SystemMessage(content="把以下客服对话历史压成要点摘要，保留用户关注的商品与结论："),
             HumanMessage(content=text)])
        return [*head, SystemMessage(content=f"[历史摘要] {summary.content}"), *recent]
