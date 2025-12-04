from pydantic import BaseModel, Field, BeforeValidator
from typing import List, Optional, Dict, Annotated
from enum import Enum
from bson import ObjectId

PyObjectId = Annotated[str, BeforeValidator(str)]

# --- 1. ENUMS & SUB-MODELS (MUST BE AT THE TOP) ---

class ItemCategory(str, Enum):
    GENERAL = "General"
    WEAPON = "Weapon"
    ARMOR = "Armor"
    HORSE = "Horse"
    AMMO = "Ammo"

class WeaponType(str, Enum):
    NONE = "None"
    ONE_HANDED = "One-Handed"
    TWO_HANDED = "Two-Handed"
    POLEARM = "Polearm"
    BOW = "Bow"
    CROSSBOW = "Crossbow"
    THROWING = "Throwing"
    SHIELD = "Shield"

# --- FIEF MODELS (Move these here!) ---
class FiefType(str, Enum):
    CARAVAN = "Caravan"
    WORKSHOP = "Workshop"
    SHIP = "Trade Ship"
    VILLAGE = "Village"
    CITY = "City"
    CASTLE = "Castle"

class Fief(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    name: str
    type: FiefType
    income: int

# --- INVENTORY ITEMS ---
class InventoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    name: str
    description: Optional[str] = None
    quantity: int = 1
    weight: float = 0.0
    category: ItemCategory = ItemCategory.GENERAL
    weapon_type: WeaponType = WeaponType.NONE
    damage: int = 0
    defense: int = 0
    is_two_handed: bool = False
    carry_bonus_kg: float = 0.0

class Equipment(BaseModel):
    armor: Optional[InventoryItem] = None
    horse: Optional[InventoryItem] = None
    hand_main: Optional[InventoryItem] = None
    hand_off: Optional[InventoryItem] = None

# --- SKILLS & ATTRIBUTES ---
class SkillData(BaseModel):
    nodes_unlocked: Dict[str, int] = {}

class AttributeData(BaseModel):
    value: int = 1
    skills: Dict[str, SkillData]

class AttributesBlock(BaseModel):
    Vigor: AttributeData
    Control: AttributeData
    Endurance: AttributeData
    Cunning: AttributeData
    Social: AttributeData
    Intelligence: AttributeData

# --- STATUS ---
class Status(BaseModel):
    level: int = 1
    hp_current: int = 100
    hp_max: int = 100
    stamina: int = 100
    speed: int = 100
    gold: int = 0
    current_load: float = 0.0 
    max_load: float = 30.0

class Points(BaseModel):
    attribute_points: int = 0
    skill_points: int = 0

# --- MAIN CHARACTER MODELS ---
class CharacterBase(BaseModel):
    name: str
    class_archetype: str
    culture: str = "Imperial"
    public_bio: str = ""
    private_notes: Optional[str] = ""
    image_url: Optional[str] = "https://i.imgur.com/62jO8iC.png"

class CharacterCreate(CharacterBase):
    pass

class CharacterInDB(CharacterBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    
    stats: AttributesBlock
    status: Status
    points: Points = Field(default_factory=Points)
    
    inventory: List[InventoryItem] = []
    equipment: Equipment = Field(default_factory=Equipment)
    
    # NOW THIS WILL WORK because Fief is defined above
    fiefs: List[Fief] = [] 

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True