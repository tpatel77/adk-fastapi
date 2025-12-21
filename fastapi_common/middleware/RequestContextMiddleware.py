import json
from datetime import datetime
from uuid import uuid4

from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.common.config.AppConfig import get_application_config, Settings
from src.common.models.CvsEventEnum import CvsEventEnum
from src.common.models.ResourceExecutionStats import ResourceExecutionStats
from src.common.util.context_util import get_context
from src.common.util.LoggerUtil import LoggerUtil

CONFIG_APP_NAME = "info.app.name"
CONFIG_OPERATION_NAMES = "info.app.operationNames"
CONFIG_RESOURCE_NAME = "info.app.resourceName"
CONFIG_VERSION_NUMBER = "info.app.version"


def processRequestHeaders(request, res):
    """Process Request Headers"""
    for item in request.headers.keys():
        key = item.lower()
        if key in ("x-consumername", "x-clientrefid"):
            res.src = str(request.headers[item])
        elif key in ("x-customappname", "x-appname", "appname"):
            res.appName = str(request.headers[item])
        elif key in ("x-grid", "grid", "x-correlationid"):
            res.grid = str(request.headers[item])
        elif key == "x-channelname":
            res.chan = str(request.headers[item])
        elif key == "x-sourcetype":
            res.lob = str(request.headers[item])
        elif key == "x-devicetype":
            res.chPlat = str(request.headers[item])
        elif key in ("x-cat", "cat"):
            res.category = str(request.headers[item])
        elif key == "x-experienceid":
            res.experienceId = str(request.headers[item])
        else:
            continue
    return res


def buildOperationName(request: Request, config: Settings):
    """Build Operation Names"""
    operationNames: list[str] = config.get(CONFIG_OPERATION_NAMES)
    resourceName: str = config.get(CONFIG_RESOURCE_NAME)
    versionNbr: str = config.get(CONFIG_VERSION_NUMBER)

    for operation in operationNames:
        if operation in str(request.url):
            return f"{resourceName}.{versionNbr}.{operation}"
    pass


async def pre_handle(request: Request) -> ResourceExecutionStats:
    """Pre Handle Request Context"""
    res: ResourceExecutionStats = ResourceExecutionStats()
    config = get_application_config()

    # Process Incoming Request Headers
    res = processRequestHeaders(request, res)
    res.grid = res.grid or f"ID-{str(uuid4()).replace('-', '')}"
    res.appName = res.appName or config.get(CONFIG_APP_NAME, None)
    res.startTime = datetime.now().isoformat()
    res.httpMethod = request.method or None
    res.opName = buildOperationName(request, config)
    res.reqLength = request.__sizeof__()
    return res


# async def post_handle(res: ResourceExecutionStats, response: Response):
#     """Post Handle Request Context"""
#     response_body = [section async for section in response.body_iterator]
#     response.body_iterator = iterate_in_threadpool(iter(response_body))
#     parsed_response = json.loads(response_body[0].decode())
#     res.httpStatusCde = response.status_code
#     res.statusCde = parsed_response.get("statusCode", "")
#     res.statusMsg = parsed_response.get("statusDescription", "")
#     res.endTime = datetime.now().isoformat()
#     res.respTime = (
#         datetime.fromisoformat(res.endTime) - datetime.fromisoformat(res.startTime)
#     ).microseconds / 1000
#     return res
from starlette.concurrency import iterate_in_threadpool
import json


async def post_handle(res: ResourceExecutionStats, response: Response):
    """Post Handle Request Context"""

    # Read the body from the async iterator
    response_body = b"".join([section async for section in response.body_iterator])

    # Restore the body for future use (since it gets consumed)
    response.body_iterator = iterate_in_threadpool(iter([response_body]))

    # Try parsing the JSON response
    try:
        parsed_response = json.loads(response_body.decode()) if response_body else {}
    except json.JSONDecodeError:
        parsed_response = {}  # Handle cases where the response is not JSON

    # Ensure parsed_response is a dictionary before accessing `.get()`
    if isinstance(parsed_response, dict):
        res.statusCde = parsed_response.get("statusCode", "")
        res.statusMsg = parsed_response.get("statusDescription", "")
    elif (
        isinstance(parsed_response, list) and parsed_response
    ):  # If it's a list, take the first element (if available)
        first_item = parsed_response[0]
        res.statusCde = (
            first_item.get("statusCode", "") if isinstance(first_item, dict) else ""
        )
        res.statusMsg = (
            first_item.get("statusDescription", "")
            if isinstance(first_item, dict)
            else ""
        )
    else:
        res.statusCde = ""
        res.statusMsg = ""

    res.httpStatusCde = response.status_code
    res.endTime = datetime.now().isoformat()
    res.respTime = (
        datetime.fromisoformat(res.endTime) - datetime.fromisoformat(res.startTime)
    ).microseconds / 1000

    return res


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Request Context Middleware"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # Pre-handle and set Request Context
        skipRequestUrlPath: list[str] = ["health"]
        if request.url.__str__().split("/")[-1] not in skipRequestUrlPath:
            res: ResourceExecutionStats = await pre_handle(request)
            context_token = get_context().set(res)
            request.state.grid = res.grid
            LoggerUtil.logMessage(CvsEventEnum.ENTRY, "Entry")

        # Execute the Service
        response: Response = await call_next(request)

        # Post-handle and reset Request context
        if request.url.__str__().split("/")[-1] not in skipRequestUrlPath:
            res: ResourceExecutionStats = await post_handle(res, response)
            LoggerUtil.logMessage(CvsEventEnum.EXIT, "EXIT")
            get_context().reset(context_token)

        return response
