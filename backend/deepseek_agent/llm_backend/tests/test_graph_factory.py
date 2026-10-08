import sys
import types
from unittest.mock import patch, MagicMock
from app.lg_agent.graph_factory import build_graph


def test_loop_mode_builds_agent_loop():
    with patch("app.lg_agent.graph_factory.build_agent_loop", return_value=MagicMock()) as b:
        build_graph(mode="loop")
        assert b.called


def test_legacy_mode_returns_existing_graph():
    # 测试子集未装 graphrag，真实 lg_builder 无法 import；注入 fake 模块验证 legacy 分支逻辑。
    fake_mod = types.ModuleType("app.lg_agent.lg_builder")
    fake_mod.graph = MagicMock()
    with patch("app.lg_agent.graph_factory.build_agent_loop") as b, \
         patch.dict(sys.modules, {"app.lg_agent.lg_builder": fake_mod}):
        g = build_graph(mode="legacy")
        assert not b.called
        assert g is not None
