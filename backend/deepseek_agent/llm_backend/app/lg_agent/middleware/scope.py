from langchain_core.messages import SystemMessage
from app.lg_agent.middleware import ContextMiddleware
from app.lg_agent.scope_config import SCOPE_DESCRIPTION

_SCOPE_PROMPT = (
    "你是智能家居电商客服。以下是本店经营范围：\n" + SCOPE_DESCRIPTION +
    "\n对超出经营范围的【商品类】请求要礼貌拒绝(如：抱歉，我家暂时没有这方面的商品)；"
    "普通闲聊可正常回答。有需要时调用工具查询商品/知识库。"
)


class ScopeMiddleware(ContextMiddleware):
    async def before_model(self, messages, ctx):
        if messages and getattr(messages[0], "type", None) == "system":
            return messages
        return [SystemMessage(content=_SCOPE_PROMPT), *messages]
