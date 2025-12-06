from app.database import db

# --- Rules of the Empire ---

# Collection Reference
skills_rules_collection = db["skills_rules"]

game_actions_collection = db["game_actions"]

ATTRIBUTES = ["Vigor", "Control", "Endurance", "Cunning", "Social", "Intelligence"]

# Which skills belong to which attribute
SKILL_CATEGORIES = {
    "Vigor": ["One-Handed", "Two-Handed", "Polearm"],
    "Control": ["Bow", "Crossbow", "Throwing"],
    "Endurance": ["Riding", "Athletics", "Smithing"],
    "Cunning": ["Scouting", "Tactics", "Roguery"],
    "Social": ["Charm", "Leadership", "Trade"],
    "Intelligence": ["Scholar", "Medicine", "Engineering"]
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
DEFAULT_GAME_ACTIONS = [
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

async def get_game_actions():
    docs = await game_actions_collection.find().to_list(1000)
    if not docs:
        # If DB has no actions, fall back to the defaults (do not auto-insert here)
        return DEFAULT_GAME_ACTIONS
    # Normalize: each doc may contain extra fields; ensure name+attribute present
    actions = []
    for d in docs:
        actions.append({"name": d.get("name", "Unnamed Action"), "attribute": d.get("attribute", "")})
    return actions

# --- Skill Tree Logic ---

def get_node_requirements(tier: int):
    return tier * 2

def generate_empty_tree():
    """Fallback if a skill isn't defined yet."""
    tree = []
    for i in range(1, 11):
        num_choices = 3 if i == 10 else 2
        choices = [{"id": f"c{c}", "name": "Placeholder", "description": "TBD"} for c in range(1, num_choices+1)]
        tree.append({"tier": i, "required_attribute_val": i*2, "choices": choices})
    return tree

async def get_skill_tree(skill_name: str):
    """Fetches the skill tree from MongoDB."""
    doc = await skills_rules_collection.find_one({"name": skill_name})
    if doc:
        return doc["tree"]
    
    # Fallback if not found (Empty Tree)
    return []

async def calculate_derived_stats(character: dict):
    stats = character.get("stats", {})
    equip = character.get("equipment", {})
    
    # 1. Base Stats
    base_load = 30.0
    total_damage = 0
    total_defense = 0
    base_speed_bonus = 0
    
    bonus_hp = 0
    bonus_stamina = 0
    total_crit_bonus = 50 

    # 2. Equipment Stats
    horse = equip.get("horse")
    horse_bonus = horse.get("carry_bonus_kg", 0) if horse else 0
    
    if equip.get("armor"): 
        total_defense += equip["armor"].get("defense", 0)
    
    equipped_types = []
    
    # Main Hand
    hm = equip.get("hand_main")
    if hm:
        total_damage += hm.get("damage", 0)
        if hm.get("category") == "Weapon": total_defense += hm.get("defense", 0)
        if hm.get("weapon_type"): equipped_types.append(hm["weapon_type"])
        if hm.get("category") == "Armor" or hm.get("weapon_type") == "Shield": equipped_types.append("Shield")

    # Off Hand
    ho = equip.get("hand_off")
    if ho:
        total_damage += ho.get("damage", 0)
        if ho.get("category") == "Weapon" or ho.get("weapon_type") == "Shield": total_defense += ho.get("defense", 0)
        if ho.get("weapon_type"): equipped_types.append(ho["weapon_type"])
        if ho.get("weapon_type") == "Shield": equipped_types.append("Shield")
    
    if horse: equipped_types.append("Horse")

    # 3. SKILL MODIFIERS (Async Loop)
    # Optimization: Fetch all needed trees in parallel or one by one. 
    # For MVP, one by one is fine, but strictly we should optimize later.
    
    for attr_name, attr_data in stats.items():
        for skill_name, skill_data in attr_data.get("skills", {}).items():
            unlocked_nodes = skill_data.get("nodes_unlocked", {})
            if not unlocked_nodes: continue

            # AWAIT the DB call
            tree_rules = await get_skill_tree(skill_name)

            for tier_str, choice_idx in unlocked_nodes.items():
                tier = int(tier_str)
                node_rule = next((n for n in tree_rules if n["tier"] == tier), None)
                
                if node_rule and 0 <= choice_idx < len(node_rule["choices"]):
                    choice = node_rule["choices"][choice_idx]
                    modifiers = choice.get("modifiers", [])
                    
                    for mod in modifiers:
                        condition = mod.get("condition", "always")
                        apply = False
                        
                        if condition == "always": apply = True
                        elif condition.startswith("equip:"):
                            req_type = condition.split(":")[1]
                            if req_type in equipped_types: apply = True
                        
                        if apply:
                            val = mod["value"]
                            stat = mod["stat"]
                            
                            if stat == "damage": total_damage += val
                            if stat == "defense": total_defense += val
                            if stat == "speed": base_speed_bonus += val # Add to MAX Speed
                            if stat == "max_load": base_load += val
                            if stat == "hp_max": bonus_hp += val
                            if stat == "stamina": bonus_stamina += val
                            if stat == "critical_damage": total_crit_bonus += val

    # 4. FINAL CALCULATIONS
    max_load = base_load + horse_bonus
    
    # Calculate Current Load
    inv_weight = sum([i["weight"] * i["quantity"] for i in character.get("inventory", [])])
    equip_weight = 0
    if equip.get("armor"): equip_weight += equip["armor"]["weight"]
    if hm: equip_weight += hm["weight"]
    if ho: equip_weight += ho["weight"]
    current_load = round(inv_weight + equip_weight, 1)

    # 5. SPEED & ENCUMBRANCE LOGIC
    # Base Speed is 100% + Skills (e.g. 105%)
    max_speed = 100 + base_speed_bonus
    
    # Calculate Ratio
    if max_load > 0:
        load_ratio = current_load / max_load
    else:
        load_ratio = 1.1 # Automatic overburden if max_load is 0

    # Apply Penalties
    speed_multiplier = 1.0
    
    if load_ratio <= 0.30:
        speed_multiplier = 1.0
    elif load_ratio <= 0.60:
        speed_multiplier = 0.8
    elif load_ratio <= 0.90:
        speed_multiplier = 0.6
    else:
        speed_multiplier = 0.4 # Over 90%
        
    current_speed = int(max_speed * speed_multiplier)

    return {
        "max_load": max_load,
        "current_load": current_load,
        "attack": total_damage,
        "defense": total_defense,
        "max_speed": max_speed,        # <--- For UI
        "current_speed": current_speed,# <--- Actual Speed
        "bonus_hp": bonus_hp,
        "bonus_stamina": bonus_stamina,
        "crit_bonus": total_crit_bonus
    }

def calculate_current_load(character: dict):
    inv_weight = sum([i["weight"] * i["quantity"] for i in character.get("inventory", [])])
    
    equip_weight = 0
    equip = character.get("equipment", {})
    
    if equip.get("armor"): equip_weight += equip["armor"]["weight"]
    if equip.get("hand_main"): equip_weight += equip["hand_main"]["weight"]
    if equip.get("hand_off"): equip_weight += equip["hand_off"]["weight"]
    
    return round(inv_weight + equip_weight, 1)