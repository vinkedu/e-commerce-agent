from unittest.mock import patch, AsyncMock
from app.lg_agent.tools.kg_tools import search_knowledge_base


async def test_graphrag_ok():
    class _Rec:
        records = {"result": "保修期为一年"}
    fake_node = AsyncMock(return_value={"cyphers": [_Rec()], "steps": []})
    with patch("app.lg_agent.tools.kg_tools.create_graphrag_query_node", return_value=fake_node):
        out = await search_knowledge_base.ainvoke({"task": "台灯保修多久"})
        assert "保修" in out


async def test_graphrag_error():
    with patch("app.lg_agent.tools.kg_tools.create_graphrag_query_node", side_effect=RuntimeError("rag fail")):
        out = await search_knowledge_base.ainvoke({"task": "x"})
        assert "工具出错" in out
