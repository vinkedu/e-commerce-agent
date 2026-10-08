"""回归：loop 多轮续聊——第二轮须以追加 HumanMessage 方式进 messages，
而非 Command(resume=)（loop 无 interrupt，resume 会丢弃新问题）。固化 main.py 续聊分支依赖的图层行为。"""
from unittest.mock import patch
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from app.lg_agent import agent_loop
from tests.conftest import FakeChatModel


async def test_followup_question_enters_messages():
    saver = MemorySaver()
    cfg = {"configurable": {"thread_id": "t1"}}
    with patch.object(agent_loop, "get_agent_model",
                      return_value=FakeChatModel(responses=[AIMessage(content="答1"), AIMessage(content="答2")])):
        g = agent_loop.build_agent_loop(checkpointer=saver)
        await g.ainvoke({"messages": [HumanMessage(content="问题1")]}, config=cfg)
        await g.ainvoke({"messages": [HumanMessage(content="问题2")]}, config=cfg)
        st = await g.aget_state(cfg)
        texts = [getattr(m, "content", "") for m in st.values["messages"]]
        assert any("问题2" in t for t in texts), "追问必须进入对话历史"
        assert len(st.values["messages"]) == 4
