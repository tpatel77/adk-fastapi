import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class ResourceExecutionStats:
    # Event Information
    CVSEVENT: str = field(default=None)
    grid: str = field(default=None)
    desc: str = field(default=None)

    # Additional Data
    metrics: Optional[Dict] = field(default_factory=dict)
    tags: Optional[Dict] = field(default_factory=dict)
    methodStats: Optional[Dict] = field(default_factory=dict)

    # Status Information
    statusCde: str = field(default="")
    statusMsg: str = field(default="")
    httpStatusCde: Optional[int] = field(default=200)
    httpStatusMsg: str = field(default=None)

    # Request Information
    httpMethod: str = field(default="POST")
    reqLength: Optional[int] = field(default=16)
    respLength: Optional[int] = field(default=None)

    # Time Information
    startTime: str = field(default_factory=lambda: datetime.now().isoformat())
    endTime: str = field(default=None)

    # Application Information
    appName: str = field(default="spl-domain-py-pa-automation")

    @property
    def __dict__(self):
        """Get a python dictionary"""
        d = {
            "CVSEVENT": self.CVSEVENT,
            "grid": self.grid,
            "desc": self.desc
        }
        # Add remaining fields
        remaining = {
            "metrics": self.metrics or {},
            "tags": self.tags or {},
            "methodStats": self.methodStats or {},
            "statusCde": self.statusCde or "",
            "statusMsg": self.statusMsg or "",
            "httpStatusCde": self.httpStatusCde,
            "httpMethod": self.httpMethod,
            "reqLength": self.reqLength,
            "startTime": self.startTime,
            "appName": self.appName
        }
        d.update({k: v for k, v in remaining.items() if v is not None})
        return d

    @property
    def json(self):
        """Get the json formatted string"""
        return json.dumps(self.__dict__)
