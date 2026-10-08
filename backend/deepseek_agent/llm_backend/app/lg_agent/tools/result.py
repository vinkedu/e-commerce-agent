MAX_TOOL_RESULT_CHARS = 4000


def truncate_result(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…(结果过长已截断)"
