from app.lg_agent.tools.registry import get_tools, get_tool_map


def test_registry_has_four_tools():
    names = {t.name for t in get_tools()}
    assert names == {"query_product_graph", "predefined_query", "search_knowledge_base", "web_search"}


def test_tool_map_lookup():
    assert get_tool_map()["web_search"].name == "web_search"
