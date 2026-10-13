from datetime import datetime, timezone
from app.schemas.audit import AuditLog


class AuditService:
    def log(self, audit_id: str, endpoint: str, request: str, response: str) -> AuditLog:
        return AuditLog(
            audit_id=audit_id,
            endpoint=endpoint,
            request_payload=request,
            response_payload=response,
            created_at=datetime.now(timezone.utc),
        )
