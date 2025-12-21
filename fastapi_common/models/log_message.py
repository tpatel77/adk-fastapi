from typing import Optional

from pydantic import BaseModel, Field

from fastapi_common.models.cvs_event_enum import CvsEventEnum


class LogMessage(BaseModel):
    # CvsEvent
    CVSEVENT: CvsEventEnum = None

    # Originator
    transId: Optional[str] = None
    glbDigitId: Optional[str] = None
    ipaddr: Optional[str] = None
    pid: Optional[str] = None
    uid: Optional[str] = None
    # Incoming/calling client app name, examples include ICE, CVS, CARE MARK, MVP etc
    src: Optional[str] = None
    # line of business
    lob: Optional[str] = None
    cat: Optional[str] = None
    chan: Optional[str] = None
    chPlat: Optional[str] = None

    # Hostname
    hostname: str = ""

    # Instance
    instance: Optional[str] = None

    # global reference id
    grid: str = ""

    # Experience Id
    experienceId: str = ""

    # Application Name
    appName: str = ""

    # Application or service's name that wrote this log
    # Ex: AuthenticateUser, getPrescriptions etc
    name: str = ""

    # Sub Operation Name
    opName: str = ""

    #  A specific step within a flow Eg: validate_cc
    step: Optional[str] = None

    # Human-readable description of the event,
    # Eg: desc=“source code unavailable, cannot change the world”
    desc: str = ""

    # Start Time
    startTime: Optional[str] = None

    # End Time
    endTime: Optional[str] = None

    # Http Method
    httpMethod: str = ""

    # URL
    backendUrl: str = ""

    # Request Length
    reqLength: int = 0

    # Http Status Code
    httpStatusCde: int = 0

    # Http Status Message
    httpStatusMsg: str = ""

    # Response Length
    respLength: Optional[int] = None

    # Status code of the current transaction if one is available
    statusCde: str = ""

    # Status message of the current transaction if one is available
    statusMsg: str = ""

    # API status - actual backend status instead of template response
    apiStatus: str = ""

    #  Overall response time of a given transaction milliseconds or granular recommended
    respTime: float = 0

    # stack trace
    stackTrace: dict = {}

    # Use this field to track Api metrics, example patient_cnt = 2.
    # In this example patient_cnt is the Key and 2 is value.
    metrics: dict = {}

    # Use this field to track Api tags ,
    # example patient_type = LOGGED_IN/GUEST . In this example patient_type is the key and  LOGGED_IN is value
    tags: dict = {}

    # Use this field to track Api Method Execution Stats
    # example getPatientInfo=250ms . In this example getPatientInfo is the key and  “250ms“ is value
    methodStats: dict = {}

