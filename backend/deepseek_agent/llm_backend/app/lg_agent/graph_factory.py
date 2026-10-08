from app.lg_agent.agent_loop import build_agent_loop
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(service="graph_factory")


def build_graph(mode: str | None = None, checkpointer=None):
    mode = mode or settings.LG_AGENT_MODE
    if mode == "loop":
        logger.info("Building agent-loop graph")
        return build_agent_loop(checkpointer=checkpointer)
    logger.info("Using legacy graph")
    from app.lg_agent.lg_builder import graph as legacy_graph
    return legacy_graph
