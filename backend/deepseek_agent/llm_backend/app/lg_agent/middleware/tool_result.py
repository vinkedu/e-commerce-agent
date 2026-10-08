from langchain_core.messages import ToolMessage
from app.lg_agent.middleware import ContextMiddleware
from app.lg_agent.tools.result import truncate_result


class ToolResultMiddleware(ContextMiddleware):
    async def after_model(self, messages, ctx):
        for m in messages:
            if isinstance(m, ToolMessage) and isinstance(m.content, str):
                m.content = truncate_result(m.content)
        return messages
