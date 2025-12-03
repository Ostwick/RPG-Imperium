from pydantic import BaseModel, Field, BeforeValidator
from typing import Optional, Annotated
from datetime import datetime
from bson import ObjectId

PyObjectId = Annotated[str, BeforeValidator(str)]

class WikiPage(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    title: str
    
    # NEW STRUCTURE
    group: str = "Uncategorized"        # Top level (e.g. "Codex of Rules")
    subcategory: str = "General"        # Second level (e.g. "Combat")
    
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True