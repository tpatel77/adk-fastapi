from enum import Enum

"""CVS Log Events. Defines log level used for logging.
"""


class CvsEventEnum(Enum):
    # ENTRY log level is logged when a request is received but not yet processed.
    # Use this to log request information. This log level is recommended
    # for batch or long-running applications. It is not recommended for
    # HTTP requests where EXIT log level is better as it will have
    # request as well as response information.
    ENTRY = "ENTRY"
    # EXIT log level is logged when request is processed and before returning
    # the response to client. It will have all request and response
    # information along with any tags, metrics and stats. For error
    # response it will have error message and stacktrace.
    EXIT = "EXIT"
    # INFO log level is to log informational messages, typically used during
    # development. It will have all metadata like tags, metrics, stats,
    # request and response if available at time of logging. This log
    # level is NOT RECOMMENDED for production and is highly discouraged
    # to avoid redundant and unnecessary logs. EXIT logs should have
    # all the metadata needed in production.
    INFO = "INFO"
    # ERROR log level is used to independently log error information
    # along with stacktrace. Typical usage is to log outbound HTTP call
    # failures. Note: EXIT lot should have error information along with
    # stacktrace so ensure logs are not duplicated.
    ERROR = "ERROR"
    # SIGNAL log level is meant to log only text message to indicate an
    # event happened. It should not have any HTTP request, response or
    # error stacktrace or any of tags, metrics and stats. Use this to
    # indicate singular event message like "application started..",
    # "message received..." etc. without overhead of INFO log level.
    SIGNAL = "SIGNAL"
    DEBUG = "DEBUG"      # DEBUG log level for detailed debugging information.
    WARNING = "WARNING"  # WARNING log level for warning messages.
