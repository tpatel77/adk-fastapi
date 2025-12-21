from typing import Dict, Any
from pydantic import BaseModel


class HttpResponse(BaseModel):
    """
    DTO for HTTP response payloads.
    """

    status_code: int
    headers: Dict[str, str]
    body: Any
