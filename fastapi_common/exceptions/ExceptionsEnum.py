from enum import IntEnum


class ExceptionsEnum(IntEnum):
    """Exceptions, Status Code & Descriptions"""

    def __new__(cls, value, code, description=""):
        obj = int.__new__(cls, value)
        obj._value_ = value

        obj.code = code
        obj.description = description
        return obj

    INTERNAL_SERVER_ERROR = (
        500,
        "9999",
        "An Unexpected error  occurred while fulfilling this  request. Our engineers have been  notified. Please try again in some time.",
    )
    BAD_GATEWAY = (
        502,
        "9997",
        "An Unexpected error  occurred while fulfilling this  request. Our engineers have been  notified. Please try again in some time.",
    )
    SERVICE_UNAVAILABLE = (
        503,
        "5000",
        "An Unexpected error  occurred while fulfilling this  request. Our engineers have been  notified. Please try again in some time.",
    )
    GATEWAY_TIMEOUT = (
        504,
        "9985",
        "An Unexpected error  occurred while fulfilling this  request. Our engineers have been  notified. Please try again in some time.",
    )
    UNAUTHORIZED = (401, "1013", "Access Denied")
    FORBIDDEN = (403, "1402", "Forbidden")
    NOT_FOUND = (
        404,
        "5013",
        "The parameters you seem to have provided does not seem to be valid. Please refer the developer portal to ensure you are building to specifications.",
    )
