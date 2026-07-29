class ToolExecutionError(Exception):
    """Base error for expected failures while executing a NORA tool."""

    failure_category = "tool_execution_failed"