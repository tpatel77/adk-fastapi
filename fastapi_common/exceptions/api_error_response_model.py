from typing import List, Optional

from pydantic import BaseModel, Field


class Error(BaseModel):
    """Error Model"""

    type: Optional[str] = None
    title: Optional[str] = None
    field: Optional[str] = None


class Fault(BaseModel):
    """ "FAULT Model"""

    type: Optional[str] = None
    title: Optional[str] = None
    moreInfo: Optional[str] = None
    errors: Optional[List[Error]] = None


class ApiErrorResponse(BaseModel):
    """Api Error Response Model"""

    statusCode: str = Field(min_length=4, max_length=4)
    statusDescription: str = Field(min_length=5, max_length=150)
    fault: Optional[Fault] = None
