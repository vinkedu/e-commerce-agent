import sys
import types
from unittest.mock import patch, MagicMock


def test_agent_loop_compiles():
    """loop 图真实编译（image_node 的 lg_builder import 是惰性的，无需 graphrag）。"""
    from app.lg_agent.agent_loop import build_agent_loop
    assert build_agent_loop() is not None


def test_sse_filter_importable():
    from app.lg_agent.sse_filter import filter_stream_chunk
    assert callable(filter_stream_chunk)


def test_graph_factory_both_modes():
    from app.lg_agent.graph_factory import build_graph
    with patch("app.lg_agent.graph_factory.build_agent_loop", return_value=MagicMock()):
        assert build_graph(mode="loop") is not None
    # legacy 真实 lg_builder 需 graphrag（测试子集未装），注入 fake 验证分支
    fake_mod = types.ModuleType("app.lg_agent.lg_builder")
    fake_mod.graph = MagicMock()
    with patch.dict(sys.modules, {"app.lg_agent.lg_builder": fake_mod}):
        assert build_graph(mode="legacy") is not None
