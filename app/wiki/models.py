from pydantic import BaseModel, Field, BeforeValidator
from typing import Optional, Annotated
from bson import ObjectId
from datetime import datetime

PyObjectId = Annotated[str, BeforeValidator(str)]

class WikiPage(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    title: str
    category: str  # e.g. "Core Rules", "Factions", "History"
    content: str   # Main text content
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True