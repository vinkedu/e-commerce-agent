from typing import Any, List


class ContextMiddleware:
    async def before_model(self, messages: List[Any], ctx: dict) -> List[Any]:
        return messages

    async def after_model(self, messages: List[Any], ctx: dict) -> List[Any]:
        return messages


async def run_before(middlewares, messages, ctx):
    for mw in middlewares:
        messages = await mw.before_model(messages, ctx)
    return messages


async def run_after(middlewares, messages, ctx):
    for mw in middlewares:
        messages = await mw.after_model(messages, ctx)
    return messages
