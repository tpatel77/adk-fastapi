"""Main Application Entry Point - Integration Test"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.common.util.BootstrapUtil import bootstrap_util
from src.qset.api import router as qset_router
from src.qset.sf1.startup import initialize_sf1_services
import logging
from src.common.config.AppConfig import get_application_config

print("Starting......")
logger = logging.getLogger(__name__)
config = get_application_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    logger.info("Application startup initiated")
    await initialize_sf1_services()
    logger.info("Application startup completed")
    yield
    # logger.info("Application shutdown initiated")
    # await shutdown_sf1_services()
    # logger.info("Application shutdown completed")


app = FastAPI(
    title="PA Automation Service",
    description="Prior Authorization automation service for integration testing",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/spl-domain-py-pa-automation/docs",
)

# BootStraps the Main Application
app: FastAPI = bootstrap_util(app)
app.include_router(qset_router.router)
