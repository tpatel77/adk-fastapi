import http
import inspect
import json
import os
import traceback
from typing import Optional, Dict, Any, Type, TypeVar, Union, List, Tuple

from fastapi_common.exceptions.api_error_response_model import ApiErrorResponse, Error, Fault
from fastapi_common.exceptions.exceptions_enum import ExceptionsEnum

T = TypeVar('T', bound='WorkflowException')


class WorkflowException(Exception):
    """Base exception class for workflow-related errors.
    
    This class provides a flexible way to create and handle workflow exceptions
    with consistent error formatting and easy integration with FastAPI.
    """
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "WORKFLOW_ERROR",
        error_type: str = "WORKFLOW_ERROR",
        details: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
        errors: Optional[List[Error]] = None,
        frame_depth: int = 1
    ):
        """Initialize a new WorkflowException.
        
        Args:
            message: Human-readable error message
            status_code: HTTP status code (default: 500)
            error_code: Application-specific error code (default: "WORKFLOW_ERROR")
            error_type: Type/category of error (default: "WORKFLOW_ERROR")
            details: Additional error details (default: None)
            exception: Original exception that caused this error (default: None)
            errors: List of Error objects for detailed validation errors (default: None)
            frame_depth: Stack frame depth to capture (default: 1, caller's frame)
        """
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.error_type = error_type
        self.details = details or {}
        self.exception = exception
        self.errors = errors or []
        self.stack_trace = None
        self.source_info = self._get_source_info(frame_depth + 1)  # +1 to account for this method call

        if exception is not None:
            self.stack_trace = "".join(
                traceback.format_exception(
                    type(exception),
                    value=exception,
                    tb=exception.__traceback__
                )
            )
        super().__init__(self.message)
        
    def _get_source_info(self, frame_depth: int = 1) -> Dict[str, str]:
        """Get source code location information.
        
        Args:
            frame_depth: Stack frame depth to capture (1 = caller of this method)
            
        Returns:
            Dict containing source file, line number, and function name
        """
        try:
            # Get the frame at the specified depth
            frame = inspect.currentframe()
            for _ in range(frame_depth + 1):  # +1 to account for this method call
                if frame is None:
                    break
                frame = frame.f_back
                
            if frame is None:
                return {}
                
            # Extract source information
            filename = os.path.basename(frame.f_code.co_filename)
            lineno = frame.f_lineno
            function = frame.f_code.co_name
            
            # Try to get class name if available
            class_name = None
            if 'self' in frame.f_locals:
                class_name = frame.f_locals['self'].__class__.__name__
            
            return {
                'file': filename,
                'line': str(lineno),
                'function': function,
                'class': class_name
            }
        except Exception:
            # Fail silently - source info is helpful but not critical
            return {}
        finally:
            # Avoid reference cycles (important for garbage collection)
            del frame
            
    def _get_error_source_info(self) -> Dict[str, str]:
        """Get the actual source of the error from the exception's traceback."""
        if not self.exception:
            return {}
            
        try:
            # Get the innermost frame from the traceback
            tb = self.exception.__traceback__
            while tb.tb_next:
                tb = tb.tb_next
                
            frame = tb.tb_frame
            filename = os.path.basename(frame.f_code.co_filename)
            
            # Try to get class name if available
            class_name = None
            if 'self' in frame.f_locals:
                class_name = frame.f_locals['self'].__class__.__name__
                
            return {
                'file': filename,
                'line': str(tb.tb_lineno),
                'function': frame.f_code.co_name,
                'class': class_name
            }
        except Exception:
            return {}

    def to_api_error(self) -> Dict[str, Any]:
        """Convert the exception to the API error response format.
        
        Returns:
            Dict containing the error response in the standard API format
        """
        fault = {
            "type": self.error_type,
            "title": self.message,
        }
        
        # Add field if available from errors
        if self.errors and self.errors[0].field:
            fault["field"] = self.errors[0].field
            
        # Add any additional details (except source info)
        if self.details:
            # Filter out any internal debug fields
            debug_fields = {'file', 'line', 'function', 'class'}
            filtered_details = {k: v for k, v in self.details.items() 
                             if k.lower() not in debug_fields}
            fault.update(filtered_details)
            
        return {
            "statusCode": self.error_code,
            "statusDescription": self.description if hasattr(self, 'description') else self.message,
            "fault": fault
        }

    @classmethod
    def throw(
        cls: Type[T],
        exc_enum: ExceptionsEnum,
        message: Optional[str] = None,
        field: Optional[str] = None,
        error_type: Optional[str] = None,
        **details: Any
    ) -> T:
        """Create a WorkflowException from an exception enum.
        
        Args:
            exc_enum: The exception enum to create from
            message: Optional custom message (defaults to enum description)
            field: Optional field name for validation errors
            error_type: Optional custom error type
            **details: Additional details to include in the error
            
        Returns:
            A new WorkflowException instance
        """
        # Create error object if field is provided
        errors = []
        if field:
            errors.append(Error(
                type=error_type or exc_enum.name,
                field=field,
                title=message or exc_enum.description
            ))
        
        # Create exception instance
        exc = cls(
            message=message or exc_enum.description,
            status_code=int(exc_enum.value),
            error_code=exc_enum.code,
            error_type=error_type or exc_enum.name,
            details=details,
            errors=errors or None
        )
        
        # Store the original description from enum
        exc.description = exc_enum.description
        return exc

    def __str__(self) -> str:
        """String representation for logging purposes.
        
        This includes all debug information but doesn't affect the API response.
        """
        # Get error source (where the actual error occurred)
        error_source = self._get_error_source_info()
        
        log_data = {
            "error": self.error_type,
            "message": self.message,
            "status_code": self.status_code,
            "error_code": self.error_code,
            "raised_at": {
                "file": self.source_info.get('file', 'unknown'),
                "line": self.source_info.get('line', 'unknown'),
                "function": self.source_info.get('function', 'unknown'),
                "class": self.source_info.get('class')
            },
            "error_source": {
                "file": error_source.get('file', 'unknown'),
                "line": error_source.get('line', 'unknown'),
                "function": error_source.get('function', 'unknown'),
                "class": error_source.get('class')
            } if error_source else None
        }
        
        # Add details if present (excluding any sensitive data)
        if self.details:
            log_data["details"] = {k: v for k, v in self.details.items() 
                                 if not k.lower().startswith(('password', 'secret', 'token'))}
        
        # Add errors if present
        if self.errors:
            log_data["errors"] = [error.dict() for error in self.errors]
        
        # Add stack trace if available
        if self.stack_trace:
            log_data["stack_trace"] = self.stack_trace
            
        return json.dumps(log_data, default=str, indent=2)

    @classmethod
    def create_validation_error(
        cls,
        field: str,
        message: str,
        error_type: str = "VALIDATION_ERROR",
        **details: Any
    ) -> 'WorkflowException':
        """Create a validation error with field and message."""
        return cls(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            error_type=error_type,
            details=details,
            errors=[Error(type=error_type, field=field, title=message)]
        )


class WorkflowNoDataAvailableException(WorkflowException):
    """Exception raised when no data is found for a workflow."""
    
    def __init__(
        self,
        message: str = "No data available",
        status_code: int = http.HTTPStatus.NOT_FOUND,
        **kwargs: Any
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code="NO_DATA_AVAILABLE",
            error_type="DATA_NOT_FOUND",
            **kwargs
        )

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
