from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.lg_agent.tools.result import truncate_result
from app.core.logger import get_logger

logger = get_logger(service="kg_tools")

# Guarded import：node 工厂的 import 链会触发 vendored graphrag(含 faiss/torch)。
# 测试子集环境未装这些重依赖时降级为 None；测试通过 patch 本模块同名符号注入 mock。
# 生产(完整 requirements)下正常导入真实实现。
try:  # pragma: no cover - 依赖是否安装决定分支
    from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.cypher_tools.node import (
        create_cypher_query_node,
    )
except Exception as _e:  # noqa: BLE001
    logger.warning(f"create_cypher_query_node 延迟不可用(缺重依赖): {_e}")
    create_cypher_query_node = None


class CypherArgs(BaseModel):
    task: str = Field(..., description="要用 Cypher 回答的任务，如产品价格、库存、规格、订单、供应商等结构化查询")


def _records_text(result: dict) -> str:
    cyphers = result.get("cyphers") or []
    if not cyphers:
        return "无结果"
    return str(getattr(cyphers[0], "records", {}))


async def _query_product_graph(task: str) -> str:
    try:
        node = create_cypher_query_node()
        result = await node({"task": task})
        return truncate_result(_records_text(result))
    except Exception as e:
        logger.error(f"query_product_graph 失败: {e}")
        return f"工具出错: 商品图谱查询失败({e})"


query_product_graph = StructuredTool.from_function(
    coroutine=_query_product_graph,
    name="query_product_graph",
    description="如果用户问的是关于产品价格、库存、规格、订单、供应商等结构化信息，则使用这个工具生成 Cypher 查询",
    args_schema=CypherArgs,
)
