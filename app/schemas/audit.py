from datetime import datetime
from pydantic import BaseModel


class AuditLog(BaseModel):
    audit_id: str
    endpoint: str
    request_payload: str
    response_payload: str
    created_at: datetime
