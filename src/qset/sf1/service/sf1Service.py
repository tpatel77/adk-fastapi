"""SF1 Service - Business logic for sending PA answers to CVS API."""
import json
import httpx
import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException
from src.common.util.LoggerUtil import LoggerUtil
from src.common.models.CvsEventEnum import CvsEventEnum
from src.qset.sf1.service.TokenService import get_token_service

logger = logging.getLogger(__name__)


class SF1Service:
    """Service class for SF1 operations."""
    
    CVS_API_URL = "https://internal-sit1-apix.cvshealth.com/specialty/experience/v2/load"
    CVS_API_KEY = "GA7kxYzA6nVBClyBmsGlGxzHdxglmjJj"
    CVS_EXPERIENCE_ID = "4764da8b-4247-4b67-8418-473e078110ee"
    CVS_ROUTE = "splgwe"
    CVS_GRID = "bvcopay-test50"
    
    @staticmethod
    async def post_pa_answers_to_sf1(
        pa_answers: Dict[str, Any],
        source_reference_id: str = "tejas-testsf2"
    ) -> Dict[str, Any]:
        """
        Send PA answers to CVS Specialty Experience API.
        
        Parameters:
        - pa_answers: Dictionary containing PA answers data
        - bearer_token: OAuth2 bearer token (optional, will auto-generate if not provided)
        - source_reference_id: Unique reference ID for tracking
        
        Returns:
        - Dictionary containing CVS API response details
        
        Raises:
        - HTTPException: If the API call fails
        """
        LoggerUtil.logMessage(
            CvsEventEnum.ENTRY, f"SF1Service.post_pa_answers_to_sf1 source={source_reference_id}"
        )
        logger.info(f"Sending PA answers to CVS API with source_reference_id: {source_reference_id}")
        
        token_service = get_token_service()
        bearer_token = await token_service.get_token()
        logger.debug("Successfully retrieved token from TokenService")
        payload = {
            "data": {
                "event": {
                    "eventName": "PRUDENT_RX_PATIENT_PRE_IMPLEMENT_INBOUND_EVENT",
                    "sourceReferenceId": source_reference_id,
                    "source": "PRUDENTRX",
                    "content": json.dumps(pa_answers),
                    "contentType": "json"
                }
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "x-experienceId": SF1Service.CVS_EXPERIENCE_ID,
            "x-route": SF1Service.CVS_ROUTE,
            "x-grid": SF1Service.CVS_GRID,
            "x-api-key": SF1Service.CVS_API_KEY,
            "x-clientrefid": SF1Service.CVS_GRID,
            "Authorization": f"Bearer {bearer_token}"
        }
        
        try:
            logger.debug(f"Making POST request to {SF1Service.CVS_API_URL}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    SF1Service.CVS_API_URL,
                    json=payload,
                    headers=headers
                )
                
                logger.info(f"CVS API response status: {response.status_code}")
                
                result = {
                    "status_code": response.status_code,
                    "cvs_response": response.json() if response.status_code == 200 else response.text,
                    "source_reference_id": source_reference_id,
                    "success": response.status_code == 200
                }
                
                if response.status_code == 200:
                    logger.info(f"Successfully sent PA answers to CVS API for {source_reference_id}")
                else:
                    logger.warning(f"CVS API returned non-200 status: {response.status_code}")
                
                LoggerUtil.logMessage(
                    CvsEventEnum.EXIT,
                    f"SF1Service.post_pa_answers_to_sf1 completed status={response.status_code}"
                )
                return result
                
        except httpx.TimeoutException as e:
            error_msg = f"CVS API request timed out: {str(e)}"
            logger.error(error_msg, exc_info=True)
            LoggerUtil.logMessage(CvsEventEnum.ERROR, error_msg)
            raise HTTPException(status_code=504, detail=error_msg)
        
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to CVS API: {str(e)}"
            logger.error(error_msg, exc_info=True)
            LoggerUtil.logMessage(CvsEventEnum.ERROR, error_msg)
            raise HTTPException(status_code=502, detail=error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error calling CVS API: {str(e)}"
            logger.error(error_msg, exc_info=True)
            LoggerUtil.logMessage(CvsEventEnum.ERROR, error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        finally:
            LoggerUtil.logMessage(CvsEventEnum.EXIT, "SF1Service.post_pa_answers_to_sf1 finished")
