import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError, HTTPException
from pydantic import ValidationError
from fastapi_common.config.app_config import get_application_config
from fastapi_common.controller import health_controller
from fastapi_common.exceptions.api_exceptions import ApiException
from fastapi_common.exceptions.workflow_exceptions import WorkflowException
from fastapi_common.exceptions.exceptions_enum import ExceptionsEnum
from fastapi_common.exceptions.exceptions_util import (
    validation_exception_handler,
    api_exception_handler,
    workflow_exception_handler,
    generic_exception_handler,
)
from fastapi_common.middleware.request_context_middleware import RequestContextMiddleware

logger = logging.getLogger(__name__)
config = get_application_config()


def bootstrap_util() -> FastAPI:
    """Boot Strap Util"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Startup and Shutdown life cycle hooks"""
        
        try:
            # Start Kafka consumer if configured
            if hasattr(app.state, 'kafka_listener'):
                print("=== Starting Kafka consumer... ===")
                await app.state.kafka_listener.start_consumer()
                print("=== Kafka consumer started successfully ===")

            yield
        finally:
            # Stop Kafka consumer if running
            if hasattr(app.state, 'kafka_listener') and app.state.kafka_listener.consumer_manager:
                print("=== Stopping Kafka consumer... ===")
                await app.state.kafka_listener.stop_consumer()
                print("=== Kafka consumer stopped ===")

            logger.info(f"{config.get('info.app.name')} shutdown successfully")

    # Create FastAPI app
    app = FastAPI(lifespan=lifespan)

    # Include Health Check Router
    app.include_router(health_controller.router)

    # Custom Middlewares
    app.add_middleware(RequestContextMiddleware)

    # Exception Handlers Which are controlled by Fast Api
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, generic_exception_handler)
    app.add_exception_handler(ExceptionsEnum.INTERNAL_SERVER_ERROR.value, generic_exception_handler)
    app.add_exception_handler(ExceptionsEnum.BAD_GATEWAY.value, generic_exception_handler)
    app.add_exception_handler(ExceptionsEnum.SERVICE_UNAVAILABLE.value, generic_exception_handler)
    app.add_exception_handler(ExceptionsEnum.GATEWAY_TIMEOUT.value, generic_exception_handler)
    app.add_exception_handler(ExceptionsEnum.UNAUTHORIZED.value, generic_exception_handler)
    app.add_exception_handler(ExceptionsEnum.FORBIDDEN.value, generic_exception_handler)
    app.add_exception_handler(ExceptionsEnum.NOT_FOUND.value, generic_exception_handler)
    
    # Checked Exception Handlers Which are controlled by developers
    app.add_exception_handler(ApiException, api_exception_handler)
    app.add_exception_handler(WorkflowException, workflow_exception_handler)
    
    # Add handlers for specific workflow error status codes
    app.add_exception_handler(ExceptionsEnum.WORKFLOW_VALIDATION_ERROR,
        lambda request, exc: workflow_exception_handler(request, WorkflowException.throw(ExceptionsEnum.WORKFLOW_VALIDATION_ERROR)))
    app.add_exception_handler(ExceptionsEnum.WORKFLOW_CONFIGURATION_ERROR,
        lambda request, exc: workflow_exception_handler(request, WorkflowException.throw(ExceptionsEnum.WORKFLOW_CONFIGURATION_ERROR)))
    app.add_exception_handler(ExceptionsEnum.WORKFLOW_EXECUTION_ERROR,
        lambda request, exc: workflow_exception_handler(request, WorkflowException.throw(ExceptionsEnum.WORKFLOW_EXECUTION_ERROR)))
    
    return app