from unittest.mock import patch, AsyncMock, MagicMock
from app.lg_agent.tools.kg_tools import predefined_query


async def test_predefined_ok():
    class _Rec:
        records = [{"product": "智能灯泡"}]
    fake_node = AsyncMock(return_value={"cyphers": [_Rec()], "steps": []})
    with patch("app.lg_agent.tools.kg_tools.get_neo4j_graph", return_value=MagicMock()), \
         patch("app.lg_agent.tools.kg_tools.create_predefined_cypher_node", return_value=fake_node):
        out = await predefined_query.ainvoke(
            {"query_name": "smart_lighting", "query": "smart_lighting", "parameters": {}})
        assert "智能灯泡" in out


async def test_predefined_error():
    with patch("app.lg_agent.tools.kg_tools.get_neo4j_graph", side_effect=RuntimeError("neo4j down")):
        out = await predefined_query.ainvoke({"query_name": "x", "query": "x", "parameters": {}})
        assert "工具出错" in out
