import http
import traceback
from typing import Union

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError, HTTPException
from pydantic import ValidationError
from fastapi_common.exceptions.workflow_exceptions import WorkflowException
from starlette.requests import Request
from starlette.responses import JSONResponse

from fastapi_common.exceptions.api_error_response_model import ApiErrorResponse
from fastapi_common.exceptions.api_exceptions import (
    ApiNoDataAvailableException,
    ApiException,
)
from fastapi_common.exceptions.exceptions_enum import ExceptionsEnum
from fastapi_common.service.logging import cvs_logger
from fastapi_common.util.hasher_util import Hasher


def process_exception(exc_enum: ExceptionsEnum, exc: HTTPException) -> JSONResponse:
    """Utility Method to process Exception"""
    exception = Exception(exc)
    api_exception = ApiException(
        status_code=exc_enum.value,
        exception=exception,
        message=getattr(exc, "detail", None),
        error_response=ApiErrorResponse(statusCode=exc_enum.code, statusDescription=exc_enum.description),
    )
    cvs_logger.error(log_message=api_exception.__str__())
    return JSONResponse(
        status_code=exc_enum.value,
        content=jsonable_encoder(api_exception.error_response),
    )

def process_workflow_exception(exc_enum: ExceptionsEnum, exc: HTTPException) -> JSONResponse:
    """Utility Method to process Exception"""
    exception = Exception(exc)
    api_exception = WorkflowException(
        status_code=exc_enum.value,
        exception=exception,
        message=getattr(exc, "detail", None),
        error_response=ApiErrorResponse(statusCode=exc_enum.code, statusDescription=exc_enum.description),
    )
    cvs_logger.error(log_message=api_exception.__str__())
    return JSONResponse(
        status_code=exc_enum.value,
        content=jsonable_encoder(api_exception.error_response),
    )


# Pydantic Thrown Error -> FAST API Error
def validation_exception_handler(request: Request, exc: Union[RequestValidationError, ValidationError]) -> JSONResponse:

    error_trace = "".join(traceback.format_exception(type(exc), value=exc, tb=exc.__traceback__))

    cvs_logger.error(log_message=error_trace)
    """Request Validation Exception Handler"""
    # Same Error [{'loc': ('body', 'lastName'), 'msg': 'ensure this value has at least 3 characters',
    # 'type': 'value_error.any_str.min_length', 'ctx': {'limit_value': 3}}]
    for error in exc.errors():
        # Hasher is just a utility function to safely return value with null keys
        errorHash = Hasher(error)
        if exc.__class__.__name__ == "ValidationError":
            error_field: str = errorHash.get("loc")[0]
        else:
            error_field: str = errorHash.get("loc")[1]

        apiErrorResponse: ApiErrorResponse = ApiErrorResponse(
            statusCode="5004",
            statusDescription="Please see errors array or refer the " "developer portal to ensure you are " "building to specifications",
            fault={
                "type": "REQUIRED_FIELD_MISSING",
                "title": "missing/incorrect input request",
                "moreInfo": "https://developer.cvshealth.com/common/error-codes",
                "errors": [
                    {
                        "title": f"{error_field} is missing/incorrect",
                        "field": f"{error_field}",
                        "type": "KEY_MISSING_IN_REQUEST",
                    }
                ],
            },
        )
        json_encoded_api_response = jsonable_encoder(apiErrorResponse)
        return JSONResponse(status_code=http.HTTPStatus.BAD_REQUEST, content=json_encoded_api_response)


# Business Errors -> Checked Exceptions
def api_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
    """Api Not Found Exception Handler"""
    cvs_logger.error(log_message=exc.__str__())
    json_encoded_api_response = jsonable_encoder(exc.error_response)
    return JSONResponse(status_code=exc.status_code, content=json_encoded_api_response)

def workflow_exception_handler(request: Request, exc: WorkflowException) -> JSONResponse:
    """Workflow Exception Handler"""
    # Get source info (where exception was raised)
    source_info = exc.source_info
    
    # Get error source (where the actual error occurred)
    error_source = exc._get_error_source_info()
    
    # Build log message with both sources
    log_lines = [
        f"WorkflowException: {exc.message}",
        f"Status: {exc.status_code} | Code: {exc.error_code}",
        f"Raised at: {source_info.get('file', 'unknown')}:{source_info.get('line', '?')} in {source_info.get('class', '')}.{source_info.get('function', '')}()"
    ]
    
    # Add error source if available
    if error_source:
        log_lines.append(
            f"Error source: {error_source.get('file', 'unknown')}:{error_source.get('line', '?')} "
            f"in {error_source.get('class', '')}.{error_source.get('function', '')}()"
        )
    
    # Add details if present
    if exc.details:
        log_lines.append(f"Details: {exc.details}")
    
    # Add stack trace if available
    if exc.stack_trace:
        log_lines.append(f"Stack Trace:\n{exc.stack_trace}")
    
    # Log the complete message
    cvs_logger.error(log_message="\n".join(log_lines))
    
    error_response = exc.to_api_error()
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error_response)
    )

# System Error -> Fast API Error
def generic_exception_handler(request: Request, exc: Union[HTTPException, int]) -> JSONResponse:
    """Generic Exception Handler"""
    try:
        if not exc or not exc.status_code:
            status_code = 500
        else:
            status_code = exc.status_code
    except Exception:
        status_code = 500
    match status_code:
        case 500:
            exc_enum = ExceptionsEnum.INTERNAL_SERVER_ERROR
            return process_exception(exc_enum, exc)

        case 502:
            exc_enum = ExceptionsEnum.BAD_GATEWAY
            return process_exception(exc_enum, exc)

        case 503:
            exc_enum = ExceptionsEnum.SERVICE_UNAVAILABLE
            return process_exception(exc_enum, exc)

        case 504:
            exc_enum = ExceptionsEnum.GATEWAY_TIMEOUT
            return process_exception(exc_enum, exc)

        case 505:
            exc_enum = ExceptionsEnum.WORKFLOW_VALIDATION_ERROR
            return process_workflow_exception(exc_enum, exc)

        case 506:
            exc_enum = ExceptionsEnum.WORKFLOW_CONFIGURATION_ERROR
            return process_workflow_exception(exc_enum, exc)

        case 507:
            exc_enum = ExceptionsEnum.WORKFLOW_EXECUTION_ERROR
            return process_workflow_exception(exc_enum, exc)

        case 401:
            exc_enum = ExceptionsEnum.UNAUTHORIZED
            return process_exception(exc_enum, exc)

        case 403:
            exc_enum = ExceptionsEnum.FORBIDDEN
            return process_exception(exc_enum, exc)

        case 404:
            api_exception = ApiNoDataAvailableException(exception=Exception(exc))
            return api_exception_handler(request=request, exc=api_exception)

        case _:
            exc_enum = ExceptionsEnum.INTERNAL_SERVER_ERROR
            return process_exception(exc_enum, exc)
    pass
