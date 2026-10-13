from pydantic import BaseModel


class Insight(BaseModel):
    category: str
    severity: str
    message: str
