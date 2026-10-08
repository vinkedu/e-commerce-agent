from langchain_core.tools import StructuredTool
from app.lg_agent.tools.kg_tools import query_product_graph, predefined_query, search_knowledge_base
from app.lg_agent.tools.web_tools import web_search


def get_tools() -> list[StructuredTool]:
    return [query_product_graph, predefined_query, search_knowledge_base, web_search]


def get_tool_map() -> dict[str, StructuredTool]:
    return {t.name: t for t in get_tools()}
