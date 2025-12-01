from pydantic import BaseModel, Field, BeforeValidator
from typing import List, Optional, Annotated
from enum import Enum
from bson import ObjectId

PyObjectId = Annotated[str, BeforeValidator(str)]

class CampaignStatus(str, Enum):
    ACTIVE = "Active"
    PAUSED = "Paused"
    ARCHIVED = "Archived"

class MemberStatus(str, Enum):
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"

class CampaignMember(BaseModel):
    user_id: str
    character_id: str
    character_name: str
    status: MemberStatus = MemberStatus.PENDING

class Campaign(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    gm_id: str
    name: str
    description: str = ""
    status: CampaignStatus = CampaignStatus.ACTIVE
    
    # Visuals
    map_url: Optional[str] = "https://i.imgur.com/7j8j8j8.png" # Default map
    
    # Party Economics
    party_gold: int = 0
    upkeep_cost: int = 0 # Daily/Weekly wages for the party (mercenaries etc)

    # Members
    members: List[CampaignMember] = []
    map_pins: List[MapPin] = []

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class MapPin(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    x: float  # Percentage (0-100)
    y: float  # Percentage (0-100)
    label: str # e.g., "Party", "Bandits"
    type: str = "Party" # Options: Party, Enemy, Location