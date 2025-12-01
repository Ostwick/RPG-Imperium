from fastapi import APIRouter, Depends, Request, Form, status, HTTPException, Body
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from bson import ObjectId

from app.database import characters_collection, users_collection
from app.auth.dependencies import get_current_user
from app.characters.models import (
    CharacterCreate, CharacterInDB, AttributesBlock, 
    AttributeData, SkillData, Status, Points, Equipment,
    Fief, FiefType
)
from app.game_rules import SKILL_CATEGORIES, GENERIC_SKILL_TREE
from app.game_rules import calculate_derived_stats, calculate_current_load
from app.characters.models import ItemCategory, InventoryItem

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# --- HELPER: Get Character & Check Owner ---
async def get_character_helper(char_id: str, user: dict):
    if not ObjectId.is_valid(char_id):
        raise HTTPException(404, "Invalid ID")
    
    char = await characters_collection.find_one({"_id": ObjectId(char_id)})
    if not char:
        raise HTTPException(404, "Character not found")
        
    is_owner = str(char["user_id"]) == user["id"]
    is_gm = user["role"] == "GM"
    
    if not (is_owner or is_gm):
        raise HTTPException(403, "Permission denied")
        
    return char, is_owner, is_gm

# --- ROUTES ---

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login")
    
    query = {} if user["role"] == "GM" else {"user_id": ObjectId(user["id"])}
    characters = await characters_collection.find(query).to_list(100)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "user": user, "characters": characters
    })

@router.get("/characters/new", response_class=HTMLResponse)
async def create_form(request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login")
    return templates.TemplateResponse("character_create.html", {"request": request})

@router.post("/characters/new")
async def create_character(
    name: str = Form(...),
    archetype: str = Form(...),
    bio: str = Form(...),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login")
    
    # Initialize Structure
    def build_attr(cat):
        skills = {s: SkillData() for s in SKILL_CATEGORIES[cat]}
        return AttributeData(value=1, skills=skills) # Start at 1

    stats_block = AttributesBlock(
        Vigor=build_attr("Vigor"),
        Control=build_attr("Control"),
        Endurance=build_attr("Endurance"),
        Cunning=build_attr("Cunning"),
        Social=build_attr("Social"),
        Intelligence=build_attr("Intelligence"),
    )

    new_char = {
        "user_id": ObjectId(user["id"]),
        "name": name,
        "class_archetype": archetype,
        "public_bio": bio,
        "private_notes": "",
        "stats": stats_block.model_dump(),
        "status": Status().model_dump(),
        "points": Points(attribute_points=0, skill_points=0).model_dump(), # GM must give points
        "inventory": [],
        "equipment": Equipment().model_dump()
    }
    
    await characters_collection.insert_one(new_char)
    return RedirectResponse("/dashboard", status.HTTP_303_SEE_OTHER)

@router.get("/characters/{char_id}", response_class=HTMLResponse)
async def view_sheet(char_id: str, request: Request, user: dict = Depends(get_current_user)):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    
    # Calculate Dynamic Stats
    current_load = calculate_current_load(char)
    derived = calculate_derived_stats(char)
    
    return templates.TemplateResponse("character_sheet.html", {
        "request": request, "user": user, "character": char, 
        "is_owner": is_owner, "is_gm": is_gm,
        "current_load": current_load,
        "max_load": derived["max_load"],
        "attack": derived["attack"],
        "defense": derived["defense"]
    })

# --- SKILL TREE VIEW ---
@router.get("/characters/{char_id}/skills/{attribute}/{skill_name}", response_class=HTMLResponse)
async def view_skill_tree(
    char_id: str, attribute: str, skill_name: str, 
    request: Request, user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    
    # Get current Attribute Value (Need it for requirements)
    attr_val = char["stats"][attribute]["value"]
    
    # Get current unlocked nodes
    # Structure: {"1": 0, "2": 1}
    unlocked = char["stats"][attribute]["skills"][skill_name]["nodes_unlocked"]
    
    return templates.TemplateResponse("skill_tree.html", {
        "request": request, "user": user, "character": char,
        "attribute": attribute, "skill_name": skill_name,
        "attr_val": attr_val,
        "unlocked": unlocked,
        "tree_structure": GENERIC_SKILL_TREE # Passing the generic rules
    })

# --- ACTION: Unlock Skill Node ---
@router.post("/characters/{char_id}/skills/unlock")
async def unlock_node(
    char_id: str, 
    attribute: str = Form(...),
    skill: str = Form(...),
    tier: int = Form(...),
    choice_index: int = Form(...),
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)

    # Error Helper
    def redirect_error(msg):
        url = f"/characters/{char_id}/skills/{attribute}/{skill}?error={msg}"
        return RedirectResponse(url, status.HTTP_303_SEE_OTHER)
    
    # 1. Check Points
    if char["points"]["skill_points"] < 1 and not is_gm:
        return redirect_error("Not enough skill points available.")
        
    # 2. Check Attribute Requirement
    attr_val = char["stats"][attribute]["value"]
    req_val = tier * 2
    if attr_val < req_val:
        return redirect_error(f"Attribute {attribute} too low. Need {req_val}, have {attr_val}.")
        
    # 3. Check Previous Tier (Optional, usually strict trees require previous)
    # For now, let's assume they must click in order, frontend enforces visuals.

    # Update DB
    key = f"stats.{attribute}.skills.{skill}.nodes_unlocked.{tier}"
    
    update_ops = {
        "$set": {key: choice_index}
    }
    
    # Deduct Point (if not GM override, but usually GM plays by rules too)
    if not is_gm: # Or maybe GM wants to deduct? Let's deduct for everyone for now.
        update_ops["$inc"] = {"points.skill_points": -1}

    await characters_collection.update_one({"_id": char["_id"]}, update_ops)
    
    return RedirectResponse(
        f"/characters/{char_id}/skills/{attribute}/{skill}", 
        status.HTTP_303_SEE_OTHER
    )

# --- ACTION: Update Attributes (The Reset/Save Logic) ---
@router.post("/characters/{char_id}/attributes/save")
async def save_attributes(
    char_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    form = await request.form()
    
    # Extract new values
    new_stats = {}
    total_cost = 0
    available_points = char["points"]["attribute_points"]
    update_data = {}

    # Error Helper
    def redirect_error(msg):
        return RedirectResponse(f"/characters/{char_id}?error={msg}", status.HTTP_303_SEE_OTHER)
    
    for attr in ["Vigor", "Control", "Endurance", "Cunning", "Social", "Intelligence"]:
        old_val = char["stats"][attr]["value"]
        try:
            new_val = int(form.get(attr, old_val))
        except ValueError:
            return redirect_error("Invalid number provided.")
        
        if new_val < old_val:
            return redirect_error(f"Cannot lower {attr} below current value.")
            
        cost = new_val - old_val
        total_cost += cost
        
        if cost > 0:
            update_data[f"stats.{attr}.value"] = new_val

    if total_cost > available_points:
        return redirect_error(f"Not enough points! You tried to spend {total_cost}, but only have {available_points}.")
    
    if total_cost > 0:
        update_data["points.attribute_points"] = available_points - total_cost
        await characters_collection.update_one({"_id": char["_id"]}, {"$set": update_data})
        
    return RedirectResponse(f"/characters/{char_id}", status.HTTP_303_SEE_OTHER)

@router.post("/characters/{char_id}/notes")
async def save_notes(
    char_id: str,
    notes: str = Form(...),
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    # Only Owner/GM can save
    await characters_collection.update_one(
        {"_id": char["_id"]},
        {"$set": {"private_notes": notes}}
    )
    return RedirectResponse(f"/characters/{char_id}", status.HTTP_303_SEE_OTHER)

# --- ACTION: Add Item (GM ONLY) ---
@router.post("/characters/{char_id}/inventory/add")
async def add_item(
    char_id: str,
    name: str = Form(...),
    weight: float = Form(...),
    qty: int = Form(...),
    category: str = Form(...),
    
    # New Fields for stats
    weapon_type: str = Form("None"),
    damage: int = Form(0),
    defense: int = Form(0),
    carry_bonus: float = Form(0.0),
    is_two_handed: bool = Form(False),
    
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    
    # 1. Permission Check
    if not is_gm:
        return RedirectResponse(f"/characters/{char_id}?error=Only the GM can grant items.", 303)

    # 2. Weight Check
    current_load = calculate_current_load(char)
    derived = calculate_derived_stats(char)
    max_load = derived["max_load"]
    
    # Calculate weight of new stack
    added_weight = weight * qty
    
    if (current_load + added_weight) > max_load:
         return RedirectResponse(f"/characters/{char_id}?error=Overburdened! Max weight is {max_load}kg.", 303)

    new_item = InventoryItem(
        name=name, weight=weight, quantity=qty, category=category,
        weapon_type=weapon_type, damage=damage, defense=defense,
        carry_bonus_kg=carry_bonus, is_two_handed=is_two_handed
    )
    
    await characters_collection.update_one(
        {"_id": char["_id"]},
        {"$push": {"inventory": new_item.model_dump()}}
    )
    return RedirectResponse(f"/characters/{char_id}", status.HTTP_303_SEE_OTHER)

# --- ACTION: Delete Item (GM ONLY) ---
@router.post("/characters/{char_id}/inventory/delete")
async def delete_item(
    char_id: str,
    item_id: str = Form(...),
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    
    if not is_gm:
        return RedirectResponse(f"/characters/{char_id}?error=Only GM can remove items.", 303)
    
    await characters_collection.update_one(
        {"_id": char["_id"]},
        {"$pull": {"inventory": {"id": item_id}}}
    )
    return RedirectResponse(f"/characters/{char_id}", status.HTTP_303_SEE_OTHER)

# --- ACTION: Equip Item (Updated Logic) ---
@router.post("/characters/{char_id}/equip")
async def equip_item(
    char_id: str,
    item_id: str = Form(...),
    slot: str = Form(...), # "main", "off", "armor", "horse"
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    
    item = next((i for i in char["inventory"] if i["id"] == item_id), None)
    if not item: return RedirectResponse(f"/characters/{char_id}?error=Item not found", 303)

    update_ops = { "$pull": {"inventory": {"id": item_id}} }
    
    # LOGIC MATRIX
    if item["category"] == "Armor":
        if char["equipment"]["armor"]: return RedirectResponse(f"/characters/{char_id}?error=Armor slot full", 303)
        update_ops["$set"] = {"equipment.armor": item}

    elif item["category"] == "Horse":
        if char["equipment"]["horse"]: return RedirectResponse(f"/characters/{char_id}?error=Horse slot full", 303)
        update_ops["$set"] = {"equipment.horse": item}
        
    elif item["category"] in ["Weapon", "Ammo"]:
        # Hand Logic
        if slot == "main":
            if char["equipment"]["hand_main"]: 
                return RedirectResponse(f"/characters/{char_id}?error=Main hand full", 303)
            
            update_ops["$set"] = {"equipment.hand_main": item}
            
            # If Two-Handed, Off-hand must be empty
            if item.get("is_two_handed", False):
                if char["equipment"]["hand_off"]:
                    return RedirectResponse(f"/characters/{char_id}?error=Cannot equip Two-Handed weapon while holding something in off-hand.", 303)
        
        elif slot == "off":
            if char["equipment"]["hand_off"]:
                 return RedirectResponse(f"/characters/{char_id}?error=Off hand full", 303)
            
            # Check if Main Hand has a Two-Handed weapon
            main = char["equipment"].get("hand_main")
            if main and main.get("is_two_handed", False):
                return RedirectResponse(f"/characters/{char_id}?error=Main hand is holding a two-handed weapon.", 303)
            
            update_ops["$set"] = {"equipment.hand_off": item}
            
    else:
        return RedirectResponse(f"/characters/{char_id}?error=Unknown category", 303)

    await characters_collection.update_one({"_id": char["_id"]}, update_ops)
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Unequip Item (Updated) ---
@router.post("/characters/{char_id}/unequip")
async def unequip_item(
    char_id: str,
    slot: str = Form(...), # "main", "off", "armor", "horse"
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    
    db_field = f"equipment.{slot}"
    if slot == "main": db_field = "equipment.hand_main"
    if slot == "off": db_field = "equipment.hand_off"
    
    # Get item to move back to inventory
    item = char["equipment"].get(slot) if slot in ["armor", "horse"] else char["equipment"].get(f"hand_{slot}")
    
    if not item: return RedirectResponse(f"/characters/{char_id}", 303)
    
    await characters_collection.update_one(
        {"_id": char["_id"]},
        {
            "$set": {db_field: None},
            "$push": {"inventory": item}
        }
    )
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Update Character Image ---
@router.post("/characters/{char_id}/image")
async def update_image(
    char_id: str,
    image_url: str = Form(...),
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    # Allow Owner or GM
    await characters_collection.update_one(
        {"_id": char["_id"]},
        {"$set": {"image_url": image_url}}
    )
    return RedirectResponse(f"/characters/{char_id}", status.HTTP_303_SEE_OTHER)

# --- ACTION: Update Gold Manually (GM/Owner) ---
@router.post("/characters/{char_id}/gold/update")
async def update_gold(
    char_id: str,
    amount: int = Form(...), # The new total, or we could do delta. Let's do New Total.
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    # Typically only GM edits gold directly, or system rules. Let's allow GM only for raw edit.
    if not is_gm:
         return RedirectResponse(f"/characters/{char_id}?error=Only GM can adjust gold directly.", 303)

    await characters_collection.update_one(
        {"_id": char["_id"]},
        {"$set": {"status.gold": amount}}
    )
    return RedirectResponse(f"/characters/{char_id}", status.HTTP_303_SEE_OTHER)

# --- ACTION: Add Fief (GM Only) ---
@router.post("/characters/{char_id}/fiefs/add")
async def add_fief(
    char_id: str,
    name: str = Form(...),
    type: str = Form(...),
    income: int = Form(...),
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    if not is_gm: return RedirectResponse(f"/characters/{char_id}?error=GM Only", 303)
    
    new_fief = Fief(name=name, type=type, income=income)
    
    await characters_collection.update_one(
        {"_id": char["_id"]},
        {"$push": {"fiefs": new_fief.model_dump()}}
    )
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Collect Income (Pay) ---
@router.post("/characters/{char_id}/fiefs/collect")
async def collect_fief(
    char_id: str,
    fief_id: str = Form(...),
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    if not is_gm: return RedirectResponse(f"/characters/{char_id}?error=GM Only", 303)
    
    # Find the fief to get income amount
    # (In Mongo we have to search the array)
    fief = next((f for f in char.get("fiefs", []) if f["id"] == fief_id), None)
    if not fief: return RedirectResponse(f"/characters/{char_id}?error=Fief not found", 303)
    
    # Add to Gold
    await characters_collection.update_one(
        {"_id": char["_id"]},
        {"$inc": {"status.gold": fief["income"]}}
    )
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Delete Fief ---
@router.post("/characters/{char_id}/fiefs/delete")
async def delete_fief(
    char_id: str,
    fief_id: str = Form(...),
    user: dict = Depends(get_current_user)
):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    if not is_gm: return RedirectResponse(f"/characters/{char_id}?error=GM Only", 303)
    
    await characters_collection.update_one(
        {"_id": char["_id"]},
        {"$pull": {"fiefs": {"id": fief_id}}}
    )
    return RedirectResponse(f"/characters/{char_id}", 303)