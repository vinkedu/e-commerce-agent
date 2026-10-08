from typing import Any, List
from langchain_core.messages import AIMessage
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio")


class _StructuredRunnable:
    def __init__(self, value: Any):
        self._value = value

    async def ainvoke(self, *_a, **_k):
        return self._value


class FakeChatModel:
    """脚本化假模型：按序弹出 responses；支持 bind_tools / with_structured_output。"""

    def __init__(self, responses: List[AIMessage] | None = None, structured: Any = None):
        self._responses = list(responses or [])
        self._structured = structured

    def bind_tools(self, _tools, **_k):
        return self

    def with_structured_output(self, _schema, **_k):
        return _StructuredRunnable(self._structured)

    async def ainvoke(self, *_a, **_k):
        return self._responses.pop(0) if self._responses else AIMessage(content="")
