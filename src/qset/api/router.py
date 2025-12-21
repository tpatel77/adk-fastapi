"""Test API Router - PA automation endpoints."""
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException
from src.common.config.AppConfig import get_application_config
from src.common.util.LoggerUtil import LoggerUtil
from src.common.models.CvsEventEnum import CvsEventEnum
from src.qset.sf1.service.sf1Service import SF1Service


config = get_application_config()
router = APIRouter(prefix=f"{config.get('info.app.context-path')}/v1", tags=["PA Automation"])


@router.post("/paAutomation")
async def pa_automation(
    request_payload: Dict[str, Any] = Body(..., description="PA automation payload including qset")
):
    """
    Accept a PA automation request payload that includes EHR context and Q-Set responses,
    and forward it to CVS SF1.
    """
    try:
        if "qset" not in request_payload:
            raise HTTPException(status_code=400, detail="Missing required 'qset' field in payload")
        if "ehr" not in request_payload:
            raise HTTPException(status_code=400, detail="Missing required 'ehr' field in payload")

        source_reference_id = get_source_reference_id(request_payload)

        LoggerUtil.logMessage(
            CvsEventEnum.ENTRY,
            f"/paAutomation invoked source_reference_id={source_reference_id}",
        )
        response = await SF1Service.post_pa_answers_to_sf1(
            pa_answers=request_payload,
            source_reference_id=source_reference_id,
        )
        LoggerUtil.logMessage(
            CvsEventEnum.EXIT,
            f"/paAutomation completed status_code={response.get('status_code')}",
        )
        return response
    except HTTPException:
        LoggerUtil.logMessage(CvsEventEnum.ERROR, "/paAutomation propagating HTTPException")
        raise
    except Exception as e:
        LoggerUtil.logMessage(CvsEventEnum.ERROR, f"/paAutomation unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to call SF1 service: {str(e)}")


def get_source_reference_id(payload: Dict[str, Any]) -> str:
    """
    Build the source reference id from the request payload.
    Format: pa-{patientId}-{rxNumber}-{patientDispenseId}
    """
    patient_id = payload.get("patientId") or payload.get("patientid")
    rx_number = payload.get("rxNumber") or payload.get("rxnumber")
    dispense_id = (
        payload.get("patientDispenseId")
        or payload.get("dispenseId")
        or payload.get("despenseId")
    )

    if not all([patient_id, rx_number, dispense_id]):
        raise HTTPException(
            status_code=400,
            detail="Missing identifiers to build source reference id "
            "(patientId, rxNumber, patientDispenseId)",
        )

    return f"pa-{patient_id}-{rx_number}-{dispense_id}"

