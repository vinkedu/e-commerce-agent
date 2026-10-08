from unittest.mock import patch, AsyncMock
from app.lg_agent.tools.kg_tools import query_product_graph


async def test_cypher_tool_ok():
    class _Rec:
        records = {"result": [{"name": "小米台灯", "price": 99}]}
    fake_node = AsyncMock(return_value={"cyphers": [_Rec()], "steps": ["x"]})
    with patch("app.lg_agent.tools.kg_tools.create_cypher_query_node", return_value=fake_node):
        out = await query_product_graph.ainvoke({"task": "小米台灯多少钱"})
        assert "小米台灯" in out


async def test_cypher_tool_error_becomes_message():
    with patch("app.lg_agent.tools.kg_tools.create_cypher_query_node",
               side_effect=RuntimeError("neo4j down")):
        out = await query_product_graph.ainvoke({"task": "x"})
        assert "工具出错" in out
