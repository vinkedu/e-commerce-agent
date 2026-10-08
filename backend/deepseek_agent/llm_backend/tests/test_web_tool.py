from unittest.mock import patch
from app.lg_agent.tools.web_tools import web_search


async def test_web_search_ok():
    with patch("app.lg_agent.tools.web_tools._raw_search", return_value="搜索结果文本"):
        out = await web_search.ainvoke({"query": "今天天气"})
        assert "搜索结果" in out


async def test_web_search_error_becomes_message():
    with patch("app.lg_agent.tools.web_tools._raw_search", side_effect=RuntimeError("serpapi 429")):
        out = await web_search.ainvoke({"query": "x"})
        assert "工具出错" in out
