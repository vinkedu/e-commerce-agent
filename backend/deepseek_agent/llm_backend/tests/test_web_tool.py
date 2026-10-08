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


async def test_web_search_runs_sync_io_off_event_loop():
    # 同步阻塞 requests.get 必须在 executor 线程执行，不占事件循环(否则并发请求全卡死)
    import threading
    main_ident = threading.current_thread().ident
    captured = {}

    def fake(query):
        captured["ident"] = threading.current_thread().ident
        return "ok"

    with patch("app.lg_agent.tools.web_tools._raw_search", side_effect=fake):
        await web_search.ainvoke({"query": "x"})
    assert captured["ident"] != main_ident
