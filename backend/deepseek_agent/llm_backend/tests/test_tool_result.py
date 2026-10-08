from app.lg_agent.tools.result import truncate_result, MAX_TOOL_RESULT_CHARS


def test_short_passthrough():
    assert truncate_result("hello") == "hello"


def test_long_truncated_with_notice():
    out = truncate_result("x" * (MAX_TOOL_RESULT_CHARS + 500))
    assert len(out) <= MAX_TOOL_RESULT_CHARS + 50
    assert "已截断" in out
