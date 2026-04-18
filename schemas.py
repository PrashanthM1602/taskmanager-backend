from pydantic import BaseModel
from datetime import datetime

class StickyCreate(BaseModel):
    title: str
    content: str
    color: str

class StickyResponse(BaseModel):
    id: int
    title: str
    content: str
    color: str
    created_at: datetime

    class Config:
        from_attributes = True