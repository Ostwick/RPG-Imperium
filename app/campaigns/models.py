from pydantic import BaseModel, Field, BeforeValidator
from typing import List, Optional, Annotated
from enum import Enum
from bson import ObjectId

PyObjectId = Annotated[str, BeforeValidator(str)]

# --- 1. ENUMS (Define these first) ---
class CampaignStatus(str, Enum):
    ACTIVE = "Active"
    PAUSED = "Paused"
    ARCHIVED = "Archived"

class MemberStatus(str, Enum):
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"

# --- 2. SUB-MODELS (Define these before Campaign) ---

class EnemyTemplate(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str
    hp_max: int
    stamina: int
    speed: int
    damage: int
    defense: int
    crit_bonus: int

class Combatant(BaseModel):
    id: str
    name: str
    type: str # "Player" or "Enemy"
    
    # HP
    hp_current: int
    hp_max: int
    
    # STAMINA
    stamina_current: int = 0
    stamina_max: int = 0
    
    speed: int
    action_points: float = 0.0
    
    # Stats
    damage: int
    defense: int
    crit_bonus: int

class MapPin(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    x: float
    y: float
    label: str
    type: str = "Party" # Party, Enemy, Location

class CampaignMember(BaseModel):
    user_id: str
    character_id: str
    character_name: str
    status: MemberStatus = MemberStatus.PENDING

# --- 3. MAIN MODEL (Defined last, using the models above) ---

class Campaign(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    gm_id: str
    name: str
    description: str = ""
    status: CampaignStatus = CampaignStatus.ACTIVE
    
    # Visuals
    map_url: Optional[str] = "https://i.imgur.com/7j8j8j8.png"
    
    # Economy
    party_gold: int = 0
    upkeep_cost: int = 0

    # Lists of Sub-Models
    members: List[CampaignMember] = []
    map_pins: List[MapPin] = []        # <--- Now valid because MapPin is defined above
    
    # Combat State
    combat_active: bool = False
    combatants: List[Combatant] = []   # <--- Now valid because Combatant is defined above
    combat_log: List[str] = []

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True