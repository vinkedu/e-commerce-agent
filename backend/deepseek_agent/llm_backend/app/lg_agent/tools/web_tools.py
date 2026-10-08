from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.lg_agent.tools.result import truncate_result
from app.core.logger import get_logger

logger = get_logger(service="web_tools")


def _raw_search(query: str):
    """惰性包装现有 SearchTool（SerpAPI）。放函数内 import 避免启动期强依赖 SERPAPI_KEY。"""
    from app.tools.search import SearchTool
    return SearchTool().search(query)


class WebSearchArgs(BaseModel):
    query: str = Field(..., description="需要联网检索的查询词")


async def _web_search(query: str) -> str:
    try:
        raw = _raw_search(query)
        return truncate_result(str(raw))
    except Exception as e:
        logger.error(f"web_search 失败: {e}")
        return f"工具出错: 联网搜索失败({e})"


web_search = StructuredTool.from_function(
    coroutine=_web_search,
    name="web_search",
    description="如果用户问的是实时信息、需要联网检索的产品有效信息，则使用这个工具",
    args_schema=WebSearchArgs,
)
