import http
import json
import traceback

from src.common.exceptions.ApiErrorResponseModel import ApiErrorResponse
from src.common.exceptions.ExceptionsEnum import ExceptionsEnum


class ApiException(Exception):
    def __init__(
        self,
        status_code: int = None,
        message: str = None,
        error_response: ApiErrorResponse = None,
        exception: Exception = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_response = error_response
        self.stack_trace = None

        if exception is not None:
            self.stack_trace = "".join(
                traceback.format_exception(
                    type(exception), value=exception, tb=exception.__traceback__
                )
            )

    def __str__(self):
        return json.dumps(
            {
                "exception_name": str(self.__class__.__name__),
                "exception_msg": self.message,
                "exception_status_code": self.status_code,
                "exception_stack_trace": self.stack_trace,
            }
        )


class ApiNoDataAvailableException(ApiException):
    def __init__(
        self,
        status_code: int = http.HTTPStatus.NOT_FOUND,
        message: str = "No Data Found",
        error_response: ApiErrorResponse = None,
        exception: Exception = None,
    ):
        super().__init__(status_code, message, error_response, exception)

        if error_response is None:
            self.error_response = ApiErrorResponse(
                statusCode=ExceptionsEnum.NOT_FOUND.code,
                statusDescription=ExceptionsEnum.NOT_FOUND.description,
                fault={
                    "type": "NOT_FOUND",
                    "title": "No data available",
                    "moreInfo": "https://developer.cvshealth.com/common/error-codes",
                    "errors": [{"title": f"{message}", "type": "DATA_ERROR"}],
                },
            )
