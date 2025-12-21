import re
import time
import json
import socket
from datetime import datetime
from uuid import uuid4

from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from fastapi_common.config.app_config import get_application_config, Settings
from fastapi_common.config.app_constants import CONFIG_OPERATION_NAMES, CONFIG_RESOURCE_NAME, CONFIG_APP_VERSION, CONFIG_APP_NAME
from fastapi_common.models.resource_execution_stats import ResourceExecutionStats
from fastapi_common.service.logging import cvs_logger
from fastapi_common.service.logging.cvs_logger import CONFIG_EXCLUDED_ENDPOINTS
from fastapi_common.util.context_util import get_context

HEADER_CLIENT_REF_ID = "x-clientrefid"


def process_request_headers(request, res):
    """Process Request Headers"""
    for item in request.headers.keys():
        match item.lower():
            case "x-consumername" | "x-clientrefid":
                res.src = str(request.headers[item])
            case "x-customappname" | "x-appname" | "appname":
                res.appName = str(request.headers[item])
            case "x-archived-client-ip" | "x-real-ip":
                res.ipaddr = str(request.headers[item])
            case "x-grid" | "grid" | "x-correlationid" | "conversationId":
                res.grid = str(request.headers[item])
            case "x-channelname":
                res.chan = str(request.headers[item])
            case "x-sourcetype":
                res.lob = str(request.headers[item])
            case "x-devicetype":
                res.chPlat = str(request.headers[item])
            case "x-cat" | "cat":
                res.category = str(request.headers[item])
            case "x-experienceid":
                res.experienceId = str(request.headers[item])
            case "x-conversationid":
                res.sessionId = str(request.headers[item])
            case "x-dialog-flow-call-id":
                res.callId = str(request.headers[item])
                res.tags.update({'call_id': str(request.headers[item])})
            case _:
                continue
    return res


def build_operation_name(request: Request, config: Settings):
    """Build Operation Names"""
    operation_names: list[str] = config.get(CONFIG_OPERATION_NAMES)
    resource_name: str = config.get(CONFIG_RESOURCE_NAME)
    version_nbr: str = config.get(CONFIG_APP_VERSION)

    for operation in operation_names:
        if operation in str(request.url):
            return f"{resource_name}.{version_nbr}.{operation}"


async def pre_handle(request: Request) -> ResourceExecutionStats:
    """Pre Handle Request Context"""
    res: ResourceExecutionStats = ResourceExecutionStats()
    config = get_application_config()

    # Process Incoming Request Headers
    res = process_request_headers(request, res)
    res.grid = res.grid or f"ID-{str(uuid4()).replace('-', '')}"
    res.startTime = time.time()
    res.httpMethod = request.method or None
    res.backendUrl = request.url.path
    res.queryParam = None
    res.reqLength = request.__sizeof__()

    # extract from URL
    # URI format: /{microservices}/{app-name}/{resource-name}/v1/{operation} //NOSONAR
    res.appName = res.appName or config.get(CONFIG_APP_NAME, None)
    res.apiName = None
    res.opName = build_operation_name(request, config)

    # add request headers
    res.request_headers = __extract_x_header(dict(request.headers))
    return res


def __extract_x_header(headers):
    # Extract header name starting with 'x-'.
    # It is used to pass through to outbound HTTP API calls
    x_headers = {}
    for header_name, header_value in headers.items():
        if re.match(r"^x-", header_name, re.IGNORECASE):
            x_headers[header_name] = header_value

    return x_headers


async def post_handle(res: ResourceExecutionStats, response: Response):
    """Post Handle Request Context"""
    response_body = [section async for section in response.body_iterator]
    response.body_iterator = iterate_in_threadpool(iter(response_body))
    parsed_response = json.loads(response_body[0].decode())
    res.httpStatusCde = response.status_code

    if isinstance(parsed_response, list):
        if res.statusCde is None:
            res.statusCde = (parsed_response[0].get("statusCode")
                             or parsed_response[0].get("statusCde", "0000"))

    # If not already overridden from controller, set from response body
        if res.statusMsg is None:
            res.statusMsg = (parsed_response[0].get("statusDescription")
                             or parsed_response[0].get("statusDesc")
                             or parsed_response[0].get("statusMsg") or 'Success')

    else:
        # If not already overridden from controller, set from response body
        if res.statusCde is None:
            res.statusCde = (parsed_response.get("statusCode")
                            or parsed_response.get("statusCde", "0000"))

        # If not already overridden from controller, set from response body
        if res.statusMsg is None:
            res.statusMsg = (parsed_response.get("statusDescription")
                            or parsed_response.get("statusDesc")
                            or parsed_response.get("statusMsg") or 'Success')

    # If not already overridden from controller, set from response body
    if res.apiStatus is None:
        res.apiStatus = res.statusMsg or 'Success'

    res.endTime = time.time()
    res.respTime = round((res.endTime - res.startTime) * 1000, 2)

    # add pass-through headers
    if HEADER_CLIENT_REF_ID in res.request_headers and HEADER_CLIENT_REF_ID not in response.headers:
        response.headers[HEADER_CLIENT_REF_ID] = res.request_headers[HEADER_CLIENT_REF_ID]

    # add response headers
    res.response_headers = dict(response.headers)

    # add response body
    res.response = parsed_response

    return res


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Request Context Middleware"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # Pre-handle and set Request Context
        skip_request_url_path: list[str] = get_application_config().get(CONFIG_EXCLUDED_ENDPOINTS, ["health"])
        if request.url.__str__().split("/")[-1] not in skip_request_url_path:
            res: ResourceExecutionStats = await pre_handle(request)
            context_token = get_context().set(res)

            # TODO: Intercept and log request body
            # # read request body for logging
            # if logger_util.is_log_property_enabled('service.logging.log-request'):
            #     webhook_request = json.loads(await request.body())
            #     cvs_logger.add_functional_tags({'_request': webhook_request})
            #     # rebuild request as body has been read earlier
            #     request = Request(scope=request.scope, receive=request.receive)

            cvs_logger.entry("API_ENTRY")

        # Execute the Service
        response: Response = await call_next(request)

        # Post-handle and reset Request context
        if request.url.__str__().split("/")[-1] not in skip_request_url_path:
            res: ResourceExecutionStats = await post_handle(res, response)
            cvs_logger.exit("API_EXIT")
            get_context().reset(context_token)

        return response
