from langchain_core.messages import HumanMessage, SystemMessage
from app.lg_agent.middleware import run_before
from app.lg_agent.middleware.scope import ScopeMiddleware


async def test_scope_injects_system_once():
    msgs = [HumanMessage(content="有没有智能台灯")]
    out = await run_before([ScopeMiddleware()], msgs, {})
    assert isinstance(out[0], SystemMessage)
    assert "智能家居" in out[0].content
