from pydantic import BaseModel, Field, BeforeValidator
from typing import List, Optional, Dict, Annotated
from bson import ObjectId
from enum import Enum

PyObjectId = Annotated[str, BeforeValidator(str)]

# --- Items & Inventory ---
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

class InventoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    name: str
    description: Optional[str] = None
    quantity: int = 1
    weight: float = 0.0
    category: ItemCategory = ItemCategory.GENERAL
    
    # Combat Stats
    weapon_type: WeaponType = WeaponType.NONE
    damage: int = 0
    defense: int = 0
    
    # Logic Flags
    is_two_handed: bool = False
    carry_bonus_kg: float = 0.0 # For Horses or Bags

# --- Equipment (New Structure) ---
class Equipment(BaseModel):
    armor: Optional[InventoryItem] = None
    horse: Optional[InventoryItem] = None
    
    # Two-Slot System
    hand_main: Optional[InventoryItem] = None
    hand_off: Optional[InventoryItem] = None

# --- Attributes & Skills ---
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

# --- Status ---
class Status(BaseModel):
    hp_current: int = 100
    hp_max: int = 100
    stamina: int = 100
    speed: int = 100
    gold: int = 0
    
    # Derived Stats (Not stored, but calculated, keeping here for schema if needed)
    current_load: float = 0.0 
    max_load: float = 30.0

class Points(BaseModel):
    attribute_points: int = 0
    skill_points: int = 0

# --- Main Character ---
class CharacterBase(BaseModel):
    name: str
    class_archetype: str
    public_bio: str = ""
    private_notes: Optional[str] = ""

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

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True