from typing import Optional

from pydantic import BaseModel


class ResourceExecutionStats(BaseModel):
    src: Optional[str] = None
    ipaddr: Optional[str] = None
    chan: Optional[str] = None
    chPlat: Optional[str] = None
    cat: Optional[str] = None

    # Application Name
    # App Name. Extracted from URL:
    # /microservices/{app-name}/{api-name}/{version}/{operation}
    appName: Optional[str] = None
    # Api Name. Extracted from URL:
    # /microservices/{app-name}/{api-name}/{version}/{operation}
    apiName: Optional[str] = None
    # Operation name. Extracted from URL:
    # /microservices/{app-name}/{api-name}/{version}/{operation}
    # Operation is set as {method}.{version}
    opName: Optional[str] = None
    grid: Optional[str] = None
    experienceId: Optional[str] = None
    # Start Time
    startTime: Optional[float] = None
    # End Time
    endTime: Optional[float] = None

    # ---- Request information ----

    # Http Method
    httpMethod: Optional[str] = None
    # URL
    backendUrl: Optional[str] = None
    # Query Parameters
    queryParam: Optional[str] = None
    request: Optional[object] = None
    request_headers: Optional[dict] = None
    reqLength: Optional[int] = None

    # ---- Response information ----
    response: Optional[object] = None
    response_headers: Optional[dict] = None

    # Http Status Code
    httpStatusCde: Optional[int] = None

    # Http Status Message
    httpStatusMsg: Optional[str] = None

    # Status code of the current transaction if one is available
    statusCde: Optional[str] = None

    # Status message of the current transaction if one is available
    statusMsg: Optional[str] = None

    # API status - actual backend status instead of template response
    apiStatus: Optional[str] = None

    #  Overall response time of a given transaction milliseconds or granular recommended
    respTime: Optional[float] = None

    # TODO: Add exception trace
    # stack trace
    #stackTrace: Optional = None

    # Use this field to track Api metrics, example patient_cnt = 2.
    # In this example patient_cnt is the Key and 2 is value.
    metrics: dict = {}

    # Use this field to track Api tags ,
    # example patient_type = “LOGGED_IN/GUEST“ . In this example patient_type is the key and  “LOGGED_IN“ is value
    tags: dict = {}

    # Use this field to track Api Method Execution Stats
    # example getPatientInfo=250ms . In this example getPatientInfo is the key and  “250ms“ is value
    methodStats: dict = {}

    callId: Optional[str] = None
    sessionId: Optional[str] = None
    storeId: Optional[str] = None
    requestId: Optional[str] = None

    # Workflow output placeholder
    workflow_outputs: dict = {}
    # Exit Construct placeholder
    exit_construct: dict = {}
    
    logs: dict = {}

    debug: dict = {}

    # Flag to indicate if the checkpointing is enabled for this request
    checkpoint_enabled_node: bool = False
