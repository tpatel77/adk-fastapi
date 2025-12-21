from contextvars import ContextVar

from fastapi_common.models.resource_execution_stats import ResourceExecutionStats

RESOURCE_EXECUTION_CONTEXT = "res"

_request_ctx: ContextVar[ResourceExecutionStats] = ContextVar(RESOURCE_EXECUTION_CONTEXT, default=None)
context_token: any


def get_request_execution_ctx() -> ResourceExecutionStats:
    """Get Request Execution"""
    return _request_ctx.get()


def get_context() -> ContextVar[ResourceExecutionStats]:
    """Get Request Execution"""
    return _request_ctx
