"""Startup module for SF1 services - initializes token service."""
import logging
from src.common.util.LoggerUtil import LoggerUtil
from src.common.models.CvsEventEnum import CvsEventEnum
from src.qset.sf1.service.TokenService import get_token_service

logger = logging.getLogger(__name__)


async def initialize_sf1_services():
    """
    Initialize SF1 services on application startup.
    Starts the token service with automatic refresh.
    """
    LoggerUtil.logMessage(CvsEventEnum.ENTRY, "initialize_sf1_services")
    logger.info("Initializing SF1 services")
    
    try:
        token_service = get_token_service()
        
        logger.info("Fetching initial token")
        await token_service.get_token()
        
        # logger.info("Starting token auto-refresh")
        # await token_service.start_auto_refresh()
        
        logger.info("SF1 services initialized successfully")
        LoggerUtil.logMessage(CvsEventEnum.EXIT, "initialize_sf1_services completed")
        
    except Exception as e:
        logger.error(f"Failed to initialize SF1 services: {str(e)}", exc_info=True)
        LoggerUtil.logMessage(CvsEventEnum.ERROR, f"initialize_sf1_services failed: {str(e)}")
        raise


# async def shutdown_sf1_services():
#     """
#     Cleanup SF1 services on application shutdown.
#     Stops the token auto-refresh task.
#     """
#     logger.info("Shutting down SF1 services")
    
#     try:
#         token_service = get_token_service()
#         await token_service.stop_auto_refresh()
#         logger.info("SF1 services shutdown successfully")
        
#     except Exception as e:
#         logger.error(f"Error during SF1 services shutdown: {str(e)}", exc_info=True)
