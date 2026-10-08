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


# ---- predefined_query ----
try:  # pragma: no cover
    from app.lg_agent.kg_sub_graph.kg_neo4j_conn import get_neo4j_graph
    from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.predefined_cypher.node import (
        create_predefined_cypher_node,
    )
    from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.predefined_cypher.cypher_dict import (
        predefined_cypher_dict,
    )
except Exception as _e:  # noqa: BLE001
    logger.warning(f"predefined_query 依赖延迟不可用(缺重依赖): {_e}")
    get_neo4j_graph = None
    create_predefined_cypher_node = None
    predefined_cypher_dict = {}


class PredefinedArgs(BaseModel):
    query_name: str = Field(..., description="预置查询名，如 product_by_name/smart_lighting 等")
    query: str = Field(..., description="与 query_name 相同的预置查询键")
    parameters: dict = Field(default_factory=dict, description="查询参数，如 {'product_name': '台灯'}")


async def _predefined_query(query_name: str, query: str, parameters: dict) -> str:
    try:
        graph = get_neo4j_graph()
        node = create_predefined_cypher_node(graph=graph, predefined_cypher_dict=predefined_cypher_dict)
        result = await node({"task": query_name, "query_name": query_name,
                             "query_parameters": {"query": query, "parameters": parameters}, "steps": []})
        cyphers = result.get("cyphers") or []
        return truncate_result(str(getattr(cyphers[0], "records", "无结果")) if cyphers else "无结果")
    except Exception as e:
        logger.error(f"predefined_query 失败: {e}")
        return f"工具出错: 预置查询失败({e})"


predefined_query = StructuredTool.from_function(
    coroutine=_predefined_query,
    name="predefined_query",
    description="高频固定查询(产品/客户/订单/供应商/类别/评论/销售分析/智能家居)的确定性快路径",
    args_schema=PredefinedArgs,
)


# ---- search_knowledge_base (GraphRAG) ----
try:  # pragma: no cover
    from app.lg_agent.kg_sub_graph.agentic_rag_agents.components.customer_tools.node import (
        create_graphrag_query_node,
    )
except Exception as _e:  # noqa: BLE001
    logger.warning(f"create_graphrag_query_node 延迟不可用(缺重依赖): {_e}")
    create_graphrag_query_node = None


class KnowledgeArgs(BaseModel):
    task: str = Field(..., description="关于产品故障、售后、保修、维修、退换货、评价等非结构化问题")


async def _search_knowledge_base(task: str) -> str:
    try:
        node = create_graphrag_query_node()
        result = await node({"task": task})
        cyphers = result.get("cyphers") or []
        rec = getattr(cyphers[0], "records", {}) if cyphers else {}
        return truncate_result(str(rec.get("result", "无结果")))
    except Exception as e:
        logger.error(f"search_knowledge_base 失败: {e}")
        return f"工具出错: 知识库检索失败({e})"


search_knowledge_base = StructuredTool.from_function(
    coroutine=_search_knowledge_base,
    name="search_knowledge_base",
    description="如果用户问的是产品故障、售后、保修、维修、退换货、评价等问题，则使用这个工具检索知识库",
    args_schema=KnowledgeArgs,
)
