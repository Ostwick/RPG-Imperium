# --- Rules of the Empire ---

ATTRIBUTES = ["Vigor", "Control", "Endurance", "Cunning", "Social", "Intelligence"]

# Which skills belong to which attribute
SKILL_CATEGORIES = {
    "Vigor": ["One-Handed", "Two-Handed", "Polearm"],
    "Control": ["Bow", "Crossbow", "Throwing"],
    "Endurance": ["Riding", "Athletics", "Smithing"],
    "Cunning": ["Scouting", "Tactics", "Roguery"],
    "Social": ["Charm", "Leadership", "Trade"],
    "Intelligence": ["Steward", "Medicine", "Engineering"]
}

# Calculated Stats Base Values
BASE_STATS = {
    "hp": 100,
    "stamina": 100,
    "speed": 100, # Percentage
    "carry_weight_base": 30.0 # Kg
}

# --- DIFFICULTY RULES ---
DIFFICULTY_LEVELS = {
    1: 2,   # Trivial (Fail only on 1)
    2: 5,   # Easy
    3: 10,  # Medium
    4: 15,  # Hard
    5: 20   # Legendary (Only Nat 20)
}

# --- STANDARD ACTIONS DATABASE ---
# This populates the dropdown in the simulator
GAME_ACTIONS = [
    {"name": "Push/Lift Heavy Object", "attribute": "Vigor"},
    {"name": "Intimidate", "attribute": "Vigor"},
    {"name": "Shoot Target (Long Range)", "attribute": "Control"},
    {"name": "Pick Lock", "attribute": "Cunning"},
    {"name": "Spot Ambush", "attribute": "Cunning"},
    {"name": "Tactical Analysis", "attribute": "Cunning"},
    {"name": "Ride Difficult Mount", "attribute": "Endurance"},
    {"name": "Forced March", "attribute": "Endurance"},
    {"name": "Persuade Noble", "attribute": "Social"},
    {"name": "Barter Prices", "attribute": "Social"},
    {"name": "Rally Troops", "attribute": "Social"},
    {"name": "Treat Wounds", "attribute": "Intelligence"},
    {"name": "Engineer Siege Engine", "attribute": "Intelligence"},
]

# --- Skill Tree Logic ---

def get_node_requirements(tier: int):
    """
    Returns the Attribute Value required to unlock this tier.
    Tier 1 requires Attribute 2.
    Tier 10 requires Attribute 20.
    Formula: Tier * 2
    """
    return tier * 2

def generate_empty_tree():
    """
    Generates the 10-node structure.
    Nodes 1-9: 2 Choices.
    Node 10: 3 Choices.
    """
    tree = []
    for i in range(1, 11):
        num_choices = 3 if i == 10 else 2
        choices = []
        for c in range(1, num_choices + 1):
            choices.append({
                "id": f"choice_{c}",
                "name": f"Technique {chr(64+c)}", # Generates "Technique A", "Technique B"
                "description": "Effect placeholder."
            })
        
        tree.append({
            "tier": i,
            "required_attribute_val": get_node_requirements(i),
            "choices": choices
        })
    return tree

# For MVP, every skill uses the generic tree. 
# Later, you can do: SKILL_TREES["One-Handed"] = [ ... specific data ... ]
GENERIC_SKILL_TREE = generate_empty_tree()

def calculate_derived_stats(character: dict):
    """
    Calculates Max Load, Attack, Defense based on stats and equipment.
    """
    stats = character.get("stats", {})
    equip = character.get("equipment", {})
    
    # 1. Max Load Calculation
    # Base 30kg + Horse Bonus + (Attributes logic can be added here later)
    base_load = 30.0
    horse_bonus = equip.get("horse", {}).get("carry_bonus_kg", 0) if equip.get("horse") else 0
    
    # Example: Endurance could add weight? 
    # endurance_bonus = stats["Endurance"]["value"] * 2
    
    max_load = base_load + horse_bonus

    # 2. Combat Stats
    total_damage = 0
    total_defense = 0
    
    # Armor
    if equip.get("armor"):
        total_defense += equip["armor"].get("defense", 0)
        
    # Main Hand
    if equip.get("hand_main"):
        total_damage += equip["hand_main"].get("damage", 0)
        total_defense += equip["hand_main"].get("defense", 0) # Shields in main hand?

    # Off Hand
    if equip.get("hand_off"):
        total_damage += equip["hand_off"].get("damage", 0) # Dual wielding?
        total_defense += equip["hand_off"].get("defense", 0) # Shields

    return {
        "max_load": max_load,
        "attack": total_damage,
        "defense": total_defense
    }

def calculate_current_load(character: dict):
    """
    Sum of Inventory Weight + Equipped Armor/Weapons.
    Horses do NOT count towards weight (they carry themselves).
    """
    inv_weight = sum([i["weight"] * i["quantity"] for i in character.get("inventory", [])])
    
    equip_weight = 0
    equip = character.get("equipment", {})
    
    if equip.get("armor"): equip_weight += equip["armor"]["weight"]
    if equip.get("hand_main"): equip_weight += equip["hand_main"]["weight"]
    if equip.get("hand_off"): equip_weight += equip["hand_off"]["weight"]
    
    return round(inv_weight + equip_weight, 1)