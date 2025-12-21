from enum import Enum


class CvsEventEnum(Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    INFO = "INFO"
    ERROR = "ERROR"
    DEBUG = "DEBUG"

    def __str__(self):
        return self.value
