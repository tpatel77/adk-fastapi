import copy
import datetime
import logging
import traceback
import socket

from fastapi_common.config.app_config import get_application_config
from fastapi_common.models.cvs_event_enum import CvsEventEnum
from fastapi_common.models.log_message import LogMessage
from fastapi_common.models.resource_execution_stats import ResourceExecutionStats
from fastapi_common.util.context_util import get_request_execution_ctx

CONFIG_LOG_ENABLED = "service.logging.enabled"
CONFIG_LOG_REQUEST_HEADERS = "service.logging.log-request-headers"
CONFIG_LOG_RESPONSE_HEADERS = "service.logging.log-response-headers"
CONFIG_LOG_REQUEST = "service.logging.log-request"
CONFIG_LOG_RESPONSE = "service.logging.log-response"
CONFIG_LOG_ON_SUCCESS = "service.logging.log-on-success"
CONFIG_LOG_ON_ERROR = "service.logging.log-on-error"
CONFIG_EXCLUDED_ENDPOINTS = "service.logging.excluded-endpoints"
CONFIG_LOG_IGNORE_EVENTS = "service.logging.ignore-events"

logger = logging.getLogger("cvs_event_logger")
config = get_application_config()
hostname = socket.gethostname()


def add_functional_tags(tags: dict):
    """
    Add Functional Tags
    """
    ctx = get_request_execution_ctx()
    if ctx is not None:
        if ctx.tags is None:
            ctx.tags = tags
        else:
            # Merge incoming tags, appending to arrays when existing value is a list
            incoming = tags or {}
            for k, v in incoming.items():
                if k in ctx.tags and isinstance(ctx.tags.get(k), list):
                    if isinstance(v, list):
                        ctx.tags[k].extend(v)
                    elif v is not None:
                        ctx.tags[k].append(v)
                    # if v is None, skip appending
                else:
                    ctx.tags[k] = v
    pass

def add_functional_metrics(metrics: dict):
    """
    Add functional metrics to the request execution context.

    Args:
        metrics (dict): A dictionary of metrics to add.

    Raises:
        ValueError: If the metrics argument is not a dictionary.
    """
    ctx = get_request_execution_ctx()
    if ctx is not None:
        if ctx.metrics is None:
            ctx.metrics = metrics
        else:
            # Merge incoming tags, appending to arrays when existing value is a list
            incoming = metrics or {}
            for k, v in incoming.items():
                if k in ctx.metrics and isinstance(ctx.metrics.get(k), list):
                    if isinstance(v, list):
                        ctx.metrics[k].extend(v)
                    elif v is not None:
                        ctx.metrics[k].append(v)
                    # if v is None, skip appending
                else:
                    ctx.metrics[k] = v
    pass
            
def entry(log_message: str):
    if __is_log_enabled(CvsEventEnum.ENTRY) is True:
        log(build_log_message(CvsEventEnum.ENTRY, log_message))


def exit(log_message: str):
    if __is_log_enabled(CvsEventEnum.EXIT) is True:
        log(build_log_message(CvsEventEnum.EXIT, log_message))


def info(log_message: str):
    if __is_log_enabled(CvsEventEnum.INFO) is True:
        log(build_log_message(CvsEventEnum.INFO, log_message))


def error(log_message: str):
    if __is_log_enabled(CvsEventEnum.ERROR) is True:
        log(build_log_message(CvsEventEnum.ERROR, log_message))


def error(log_message: str, exception: Exception = None):
    if __is_log_enabled(CvsEventEnum.ERROR) is True:
        log(build_log_message(CvsEventEnum.ERROR, log_message, exception))


def signal(log_message: str):
    if __is_log_enabled(CvsEventEnum.SIGNAL) is True:
        log(build_log_message(CvsEventEnum.SIGNAL, log_message))


def debug(log_message: str):
    if __is_log_enabled(CvsEventEnum.DEBUG) is True:
        log(build_log_message(CvsEventEnum.DEBUG, log_message))

def warning(log_message: str):
    if __is_log_enabled(CvsEventEnum.WARNING) is True:
        log(build_log_message(CvsEventEnum.WARNING, log_message))


def log(log_message: LogMessage):
    if log_message and log_message.CVSEVENT and __is_log_enabled(log_message.CVSEVENT):
        test = log_message.model_dump_json(exclude_unset=True, exclude_none=True)
        logger.info(test)


def build_log_message(event: CvsEventEnum, log_message: str, exception: Exception = None):
    res: ResourceExecutionStats | None = get_request_execution_ctx()
    if res is None:
        res = ResourceExecutionStats()

    m: LogMessage = default_log_message()
    m.desc = log_message
    m.CVSEVENT = event

    # Do not add tags in SIGNAL event
    if event != CvsEventEnum.SIGNAL:
        m.methodStats = res.methodStats
        m.metrics = res.metrics
        m.tags = res.tags

        if __is_log_property_enabled(CONFIG_LOG_REQUEST) and res.request is not None:
            m.tags.update({"_request": res.request})

        if __is_log_property_enabled(CONFIG_LOG_REQUEST_HEADERS) and res.request_headers is not None:
            m.tags.update({"_request_headers": res.request_headers})

    # For EXIT or ERROR events only
    if event == CvsEventEnum.EXIT or event == CvsEventEnum.ERROR:
        if __is_log_property_enabled(CONFIG_LOG_RESPONSE) and res.response is not None:
            m.tags.update({"_response": res.response})

        if __is_log_property_enabled(CONFIG_LOG_RESPONSE_HEADERS) and res.response_headers is not None:
            m.tags.update({"_response_headers": res.response_headers})

        if res.endTime is not None:
            m.endTime = datetime.datetime.fromtimestamp(res.endTime).isoformat()
        else: 
            m.endTime = res.endTime

        m.respTime = res.respTime
        

        m.httpStatusCde = res.httpStatusCde
        m.httpStatusMsg = res.httpStatusMsg

        # status or error
        m.statusCde = res.statusCde
        m.statusMsg = res.statusMsg
        m.apiStatus = res.apiStatus

        # if exception is available
        if exception is not None:
            m.stackTrace = traceback.format_exception(exception.__context__)

    return m


def default_log_message():
    res: ResourceExecutionStats | None = get_request_execution_ctx()
    if res is None:
        res = ResourceExecutionStats()
    m = LogMessage()
    # logging info
    m.grid = res.grid
    m.experienceId = res.experienceId
    m.hostname = hostname
    m.instance = hostname
    # m.step = res.step

    # application
    m.appName = res.appName
    m.name = res.apiName
    m.opName = res.opName
    if res.startTime is not None:
        m.startTime = datetime.datetime.fromtimestamp(res.startTime).isoformat()
    else:
        m.startTime = res.startTime
    m.httpMethod = res.httpMethod
    m.backendUrl = res.backendUrl
    return m


def __is_log_enabled(event: CvsEventEnum):
    log_enabled = config.get(CONFIG_LOG_ENABLED, False)
    if log_enabled is False:
        """Logs are disabled"""
        return False

    log_events = config.get(CONFIG_LOG_IGNORE_EVENTS, [])
    if len(log_events) == 0 or event.value not in log_events:
        """log event type is enabled"""
        return True

    # Default not enabled
    return False


def __is_log_property_enabled(p: str):
    value = config.get(p)
    if value is None:
        return False
    elif isinstance(value, bool):
        return value.__bool__()
    elif value.lower() == 'true':
        return True
    else:
        return False


def log_deep_copy(obj):
    """
    Creates deep copy of the object for logging. Returns None on error
    """
    try:
        return copy.deepcopy(obj)
    except Exception as e:
        # return null on error
        return None

