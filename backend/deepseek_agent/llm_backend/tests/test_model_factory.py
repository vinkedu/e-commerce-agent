from unittest.mock import patch, MagicMock
from app.lg_agent.model_factory import get_agent_model
from app.lg_agent.scope_config import SCOPE_DESCRIPTION


def test_scope_is_single_source():
    assert "智能家居" in SCOPE_DESCRIPTION


def test_factory_deepseek_path():
    with patch("app.lg_agent.model_factory.ChatDeepSeek", return_value=MagicMock()) as m, \
         patch("app.lg_agent.model_factory.settings") as s:
        s.AGENT_SERVICE = "deepseek"
        s.DEEPSEEK_API_KEY = "k"
        s.DEEPSEEK_MODEL = "deepseek-chat"
        get_agent_model(tags=["agent"])
        assert m.called
