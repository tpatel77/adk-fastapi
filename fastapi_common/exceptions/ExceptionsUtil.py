import http
import traceback
from typing import Union

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError, HTTPException
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.common.exceptions.ApiErrorResponseModel import ApiErrorResponse
from src.common.exceptions.ApiExceptions import (
    ApiNoDataAvailableException,
    ApiException,
)
from src.common.exceptions.ExceptionsEnum import ExceptionsEnum
from src.common.models.CvsEventEnum import CvsEventEnum
from src.common.util.LoggerUtil import LoggerUtil
from src.common.util.hasher_util import Hasher


def process_exception(exc_enum: ExceptionsEnum, exc: HTTPException) -> JSONResponse:
    """Utility Method to process Exception"""
    exception = Exception(exc)
    api_exception = ApiException(
        status_code=exc_enum.value,
        exception=exception,
        message=getattr(exc, "detail", str(exc)),
        error_response=ApiErrorResponse(
            statusCode=exc_enum.code, statusDescription=exc_enum.description
        ),
    )
    LoggerUtil.logMessage(event=CvsEventEnum.ERROR, message=api_exception.__str__())
    return JSONResponse(
        status_code=exc_enum.value,
        content=jsonable_encoder(api_exception.error_response),
    )


# Pydantic Thrown Error -> FAST API Error
def validation_exception_handler(
    request: Request, exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:

    error_trace = "".join(
        traceback.format_exception(type(exc), value=exc, tb=exc.__traceback__)
    )

    LoggerUtil.logMessage(CvsEventEnum.ERROR, f"validation_exception_handler --> {error_trace}")
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
            statusDescription="Please see errors array or refer the "
            "developer portal to ensure you are "
            "building to specifications",
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
        return JSONResponse(
            status_code=http.HTTPStatus.BAD_REQUEST, content=json_encoded_api_response
        )


# Business Errors -> Checked Exceptions
def api_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
    """Api Not Found Exception Handler"""
    LoggerUtil.logMessage(CvsEventEnum.ERROR, f"api_exception_handler --> {exc.__str__()}")
    json_encoded_api_response = jsonable_encoder(exc.error_response)
    return JSONResponse(status_code=exc.status_code, content=json_encoded_api_response)


# System Error -> Fast API Error
def generic_exception_handler(
    request: Request, exc: Union[HTTPException, int]
) -> JSONResponse:
    """Generic Exception Handler"""
    # Some native exceptions (e.g., TypeError) do not have `status_code` – default to 500
    status_code = getattr(exc, "status_code", 500)
    if status_code == 500:
        exc_enum = ExceptionsEnum.INTERNAL_SERVER_ERROR
        return process_exception(exc_enum, exc)

    elif status_code == 502:
        exc_enum = ExceptionsEnum.BAD_GATEWAY
        return process_exception(exc_enum, exc)

    elif status_code == 503:
        exc_enum = ExceptionsEnum.SERVICE_UNAVAILABLE
        return process_exception(exc_enum, exc)

    elif status_code == 504:
        exc_enum = ExceptionsEnum.GATEWAY_TIMEOUT
        return process_exception(exc_enum, exc)

    elif status_code == 401:
        exc_enum = ExceptionsEnum.UNAUTHORIZED
        return process_exception(exc_enum, exc)

    elif status_code == 403:
        exc_enum = ExceptionsEnum.FORBIDDEN
        return process_exception(exc_enum, exc)

    elif status_code == 404:
        api_exception = ApiNoDataAvailableException(exception=Exception(exc))
        return api_exception_handler(request=request, exc=api_exception)

    else:
        exc_enum = ExceptionsEnum.INTERNAL_SERVER_ERROR
        return process_exception(exc_enum, exc)
