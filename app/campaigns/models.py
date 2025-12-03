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
    map_url: Optional[str] = "https://as1.ftcdn.net/v2/jpg/01/03/31/54/1000_F_103315491_VoWra2L0y84ZeExgO3Tcmf4EPDjxy2jJ.jpg" # Default map
    
    # Party Economics
    party_gold: int = 0
    upkeep_cost: int = 0 # Daily/Weekly wages for the party (mercenaries etc)

    # Members
    members: List[CampaignMember] = []
    map_pins: List[MapPin] = []

    # Active Combat Data
    combat_active: bool = False
    combatants: List[Combatant] = []
    combat_log: List[str] = []

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class MapPin(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    x: float  # Percentage (0-100)
    y: float  # Percentage (0-100)
    label: str # e.g., "Party", "Bandits"
    type: str = "Party" # Options: Party, Enemy, Location

# --- BESTIARY (Templates) ---
class EnemyTemplate(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str
    hp_max: int
    stamina: int
    speed: int
    damage: int
    defense: int
    crit_bonus: int # %

# --- COMBAT STATE ---
class Combatant(BaseModel):
    id: str
    name: str
    type: str
    hp_current: int
    hp_max: int
    stamina_current: int = 0
    stamina_max: int = 0
    speed: int
    action_points: float = 0.0
    
    # Combat Stats
    damage: int
    defense: int
    crit_bonus: int