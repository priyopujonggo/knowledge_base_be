from pydantic import BaseModel
from datetime import datetime

class DocumentResponse(BaseModel):
    id: int
    title: str
    file_type: str
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int