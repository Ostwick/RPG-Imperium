from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from app.templates import templates
from bson import ObjectId

from app.database import characters_collection, users_collection
from app.auth.dependencies import get_current_user
from app.characters.models import (
    CharacterCreate, CharacterInDB, AttributesBlock, 
    AttributeData, SkillData, Status, Points, Equipment,
    Fief, FiefType, ItemCategory, InventoryItem
)
from app.game_rules import SKILL_CATEGORIES, get_skill_tree, calculate_derived_stats

router = APIRouter()

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
    if not user: return RedirectResponse("/auth/login", status.HTTP_303_SEE_OTHER)
    
    query = {} if user["role"] == "GM" else {"user_id": ObjectId(user["id"])}
    characters = await characters_collection.find(query).to_list(100)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "user": user, "characters": characters
    })

@router.get("/characters/new", response_class=HTMLResponse)
async def create_form(request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("character_create.html", {"request": request, "user": user})

@router.post("/characters/new")
async def create_character(
    name: str = Form(...),
    archetype: str = Form(...),
    culture: str = Form(...),
    bio: str = Form(...),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", status.HTTP_303_SEE_OTHER)
    
    def build_attr(cat):
        skills = {s: SkillData() for s in SKILL_CATEGORIES[cat]}
        return AttributeData(value=1, skills=skills)

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
        "culture": culture,
        "public_bio": bio,
        "private_notes": "",
        "stats": stats_block.model_dump(),
        "status": Status(level=1).model_dump(),
        "points": Points(attribute_points=2, skill_points=1).model_dump(),
        "inventory": [],
        "equipment": Equipment().model_dump(),
        "fiefs": [],
        "image_url": "https://cdn-icons-png.flaticon.com/512/53/53625.png"
    }
    
    await characters_collection.insert_one(new_char)
    return RedirectResponse("/dashboard", status.HTTP_303_SEE_OTHER)

@router.get("/characters/{char_id}", response_class=HTMLResponse)
async def view_sheet(char_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", status.HTTP_303_SEE_OTHER)
    
    if not ObjectId.is_valid(char_id):
        raise HTTPException(404, "Invalid ID")

    # 1. Fetch Character
    char = await characters_collection.find_one({"_id": ObjectId(char_id)})
    if not char:
        raise HTTPException(404, "Character not found")

    # 2. Permissions
    is_owner = str(char["user_id"]) == user["id"]
    is_gm = user["role"] == "GM"
    
    # 3. Privacy
    if not (is_owner or is_gm):
        char["private_notes"] = "" 

    # 4. Calculate Stats (Async)
    derived = await calculate_derived_stats(char)
    
    # 5. Auto-Update Max Stats in DB if changed
    final_max_hp = 100 + derived["bonus_hp"]
    final_max_stamina = 100 + derived["bonus_stamina"]
    
    if char["status"]["hp_max"] != final_max_hp:
        if is_owner or is_gm:
            await characters_collection.update_one({"_id": char["_id"]}, {"$set": {"status.hp_max": final_max_hp}})
        char["status"]["hp_max"] = final_max_hp

    return templates.TemplateResponse("character_sheet.html", {
        "request": request, 
        "user": user, 
        "character": char, 
        "is_owner": is_owner, 
        "is_gm": is_gm,
        "current_load": derived["current_load"],
        "max_load": derived["max_load"],
        "attack": derived["attack"],
        "defense": derived["defense"],
        "crit_bonus": derived["crit_bonus"],
        "max_stamina": final_max_stamina,
        "speed": derived["current_speed"],  # The calculated speed (e.g. 80)
        "max_speed": derived["max_speed"]   # The potential speed (e.g. 100) <--- THIS WAS MISSING
    })


# --- SKILL TREE VIEW ---
@router.get("/characters/{char_id}/skills/{attribute}/{skill_name}", response_class=HTMLResponse)
async def view_skill_tree(
    char_id: str, attribute: str, skill_name: str, 
    request: Request, user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", status.HTTP_303_SEE_OTHER)
    
    # 1. Fetch Character Manually (To avoid the Helper's auto-403 error)
    if not ObjectId.is_valid(char_id): raise HTTPException(404, "Invalid ID")
    char = await characters_collection.find_one({"_id": ObjectId(char_id)})
    if not char: raise HTTPException(404, "Character not found")

    is_owner = str(char["user_id"]) == user["id"]
    is_gm = user["role"] == "GM"

    # 2. Soft Redirect if Permission Denied
    if not (is_owner or is_gm):
        return RedirectResponse(f"/characters/{char_id}?error=Only the owner can manage skills.", status.HTTP_303_SEE_OTHER)
    
    # 3. Load Tree Data
    attr_val = char["stats"][attribute]["value"]
    unlocked = char["stats"][attribute]["skills"][skill_name]["nodes_unlocked"]
    tree_data = await get_skill_tree(skill_name)

    return templates.TemplateResponse("skill_tree.html", {
        "request": request, "user": user, "character": char,
        "attribute": attribute, "skill_name": skill_name,
        "attr_val": attr_val, "unlocked": unlocked, "tree_structure": tree_data
    })

# --- ACTION: Unlock Skill Node ---
@router.post("/characters/{char_id}/skills/unlock")
async def unlock_node(
    char_id: str, attribute: str = Form(...), skill: str = Form(...), tier: int = Form(...), choice_index: int = Form(...),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    
    def redirect_error(msg):
        return RedirectResponse(f"/characters/{char_id}/skills/{attribute}/{skill}?error={msg}", 303)

    if char["points"]["skill_points"] < 1 and not is_gm:
        return redirect_error("Not enough skill points.")
        
    attr_val = char["stats"][attribute]["value"]
    req_val = tier * 2
    if attr_val < req_val:
        return redirect_error(f"Attribute too low. Need {req_val}.")

    key = f"stats.{attribute}.skills.{skill}.nodes_unlocked.{tier}"
    update_ops = {
        "$set": {key: choice_index},
        "$inc": {"points.skill_points": -1} # <--- CHANGED: Deduct points for everyone (including GM)
    }

    await characters_collection.update_one({"_id": char["_id"]}, update_ops)
    return RedirectResponse(f"/characters/{char_id}/skills/{attribute}/{skill}", 303)

# --- ACTION: Update Attributes (The Reset/Save Logic) ---
@router.post("/characters/{char_id}/attributes/save")
async def save_attributes(char_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    form = await request.form()
    
    update_data = {}
    total_cost = 0
    available_points = char["points"]["attribute_points"]

    for attr in ["Vigor", "Control", "Endurance", "Cunning", "Social", "Intelligence"]:
        old_val = char["stats"][attr]["value"]
        new_val = int(form.get(attr, old_val))
        cost = new_val - old_val
        total_cost += cost
        if cost > 0: update_data[f"stats.{attr}.value"] = new_val

    if total_cost > available_points: return RedirectResponse(f"/characters/{char_id}?error=Not enough points", 303)
    
    if total_cost > 0:
        update_data["points.attribute_points"] = available_points - total_cost
        await characters_collection.update_one({"_id": char["_id"]}, {"$set": update_data})
        
    return RedirectResponse(f"/characters/{char_id}", 303)

@router.post("/characters/{char_id}/notes")
async def save_notes(char_id: str, notes: str = Form(...), user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    await characters_collection.update_one({"_id": char["_id"]}, {"$set": {"private_notes": notes}})
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Add Item (GM ONLY) ---
@router.post("/characters/{char_id}/inventory/add")
async def add_item(
    char_id: str, name: str = Form(...), weight: float = Form(...), qty: int = Form(...), category: str = Form(...),
    weapon_type: str = Form("None"), damage: int = Form(0), defense: int = Form(0), carry_bonus: float = Form(0.0), is_two_handed: bool = Form(False),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    if not is_gm: return RedirectResponse(f"/characters/{char_id}?error=GM Only", 303)

    # 1. Calculate Stats (Async)
    derived = await calculate_derived_stats(char)
    
    # 2. Check Weight Limit
    # We use the 'current_load' and 'max_load' returned by the calculator
    if (derived["current_load"] + (weight * qty)) > derived["max_load"]:
         return RedirectResponse(f"/characters/{char_id}?error=Overburdened! Max load is {derived['max_load']}kg.", 303)

    # 3. Create and Save Item
    new_item = InventoryItem(
        name=name, weight=weight, quantity=qty, category=category, 
        weapon_type=weapon_type, damage=damage, defense=defense, 
        carry_bonus_kg=carry_bonus, is_two_handed=is_two_handed
    )
    
    await characters_collection.update_one(
        {"_id": char["_id"]}, 
        {"$push": {"inventory": new_item.model_dump()}}
    )
    
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Delete Item (GM ONLY) ---
@router.post("/characters/{char_id}/inventory/delete")
async def delete_item(char_id: str, item_id: str = Form(...), user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    if not is_gm: return RedirectResponse(f"/characters/{char_id}?error=GM Only", 303)
    
    await characters_collection.update_one({"_id": char["_id"]}, {"$pull": {"inventory": {"id": item_id}}})
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Equip Item (Updated Logic) ---
@router.post("/characters/{char_id}/equip")
async def equip_item(char_id: str, item_id: str = Form(...), slot: str = Form(...), user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    
    item = next((i for i in char["inventory"] if i["id"] == item_id), None)
    if not item: return RedirectResponse(f"/characters/{char_id}?error=Item not found", 303)

    update_ops = { "$pull": {"inventory": {"id": item_id}} }
    
    if item["category"] == "Armor":
        if char["equipment"]["armor"]: return RedirectResponse(f"/characters/{char_id}?error=Slot full", 303)
        update_ops["$set"] = {"equipment.armor": item}
    elif item["category"] == "Horse":
        if char["equipment"]["horse"]: return RedirectResponse(f"/characters/{char_id}?error=Slot full", 303)
        update_ops["$set"] = {"equipment.horse": item}
    elif item["category"] in ["Weapon", "Ammo"]:
        if slot == "main":
            if char["equipment"]["hand_main"]: return RedirectResponse(f"/characters/{char_id}?error=Main hand full", 303)
            update_ops["$set"] = {"equipment.hand_main": item}
            if item.get("is_two_handed", False):
                if char["equipment"]["hand_off"]: return RedirectResponse(f"/characters/{char_id}?error=Hands full", 303)
        elif slot == "off":
            if char["equipment"]["hand_off"]: return RedirectResponse(f"/characters/{char_id}?error=Off hand full", 303)
            main = char["equipment"].get("hand_main")
            if main and main.get("is_two_handed", False): return RedirectResponse(f"/characters/{char_id}?error=Main hand busy", 303)
            update_ops["$set"] = {"equipment.hand_off": item}

    await characters_collection.update_one({"_id": char["_id"]}, update_ops)
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Unequip Item (Updated) ---
@router.post("/characters/{char_id}/unequip")
async def unequip_item(char_id: str, slot: str = Form(...), user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    
    db_field = f"equipment.{slot}"
    if slot == "main": db_field = "equipment.hand_main"
    if slot == "off": db_field = "equipment.hand_off"
    
    item = char["equipment"].get(slot) if slot in ["armor", "horse"] else char["equipment"].get(f"hand_{slot}")
    if not item: return RedirectResponse(f"/characters/{char_id}", 303)
    
    await characters_collection.update_one({"_id": char["_id"]}, {"$set": {db_field: None}, "$push": {"inventory": item}})
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Update Character Image ---
@router.post("/characters/{char_id}/image")
async def update_image(
    char_id: str,
    image_url: str = Form(...),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    await characters_collection.update_one({"_id": char["_id"]}, {"$set": {"image_url": image_url}})
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Update Gold Manually (GM/Owner) ---
@router.post("/characters/{char_id}/gold/update")
async def update_gold(
    char_id: str,
    amount: int = Form(...),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    if not is_gm: return RedirectResponse(f"/characters/{char_id}", 303)

    await characters_collection.update_one({"_id": char["_id"]}, {"$set": {"status.gold": amount}})
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Add Fief (GM Only) ---
@router.post("/characters/{char_id}/fiefs/add")
async def add_fief(
    char_id: str, name: str = Form(...), type: str = Form(...), income: int = Form(...),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    if not is_gm: return RedirectResponse(f"/characters/{char_id}", 303)
    
    new_fief = Fief(name=name, type=type, income=income)
    await characters_collection.update_one({"_id": char["_id"]}, {"$push": {"fiefs": new_fief.model_dump()}})
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Collect Income (Pay) ---
@router.post("/characters/{char_id}/fiefs/collect")
async def collect_fief(char_id: str, fief_id: str = Form(...), user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    if not is_gm: return RedirectResponse(f"/characters/{char_id}", 303)
    
    fief = next((f for f in char.get("fiefs", []) if f["id"] == fief_id), None)
    if fief:
        await characters_collection.update_one({"_id": char["_id"]}, {"$inc": {"status.gold": fief["income"]}})
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Delete Fief ---
@router.post("/characters/{char_id}/fiefs/delete")
async def delete_fief(char_id: str, fief_id: str = Form(...), user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    if not is_gm: return RedirectResponse(f"/characters/{char_id}", 303)
    
    await characters_collection.update_one({"_id": char["_id"]}, {"$pull": {"fiefs": {"id": fief_id}}})
    return RedirectResponse(f"/characters/{char_id}", 303)

# --- ACTION: Update Current Status (GM Edit) ---
@router.post("/characters/{char_id}/status/update")
async def update_status(
    char_id: str,
    hp_current: int = Form(...),
    stamina_current: int = Form(...),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", status.HTTP_303_SEE_OTHER)
    
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    if not is_gm: return RedirectResponse(f"/characters/{char_id}", 303)

    await characters_collection.update_one(
        {"_id": char["_id"]},
        {"$set": {
            "status.hp_current": hp_current,
            "status.stamina": stamina_current
        }}
    )
    return RedirectResponse(f"/characters/{char_id}", status.HTTP_303_SEE_OTHER)

# --- ACTION: Level Up (GM Only) ---
@router.post("/characters/{char_id}/levelup")
async def level_up(char_id: str, user: dict = Depends(get_current_user)):
    char, is_owner, is_gm = await get_character_helper(char_id, user)
    
    # 1. Permission & Validation
    if not is_gm: 
        return RedirectResponse(f"/characters/{char_id}", 303)
    
    current_level = char["status"].get("level", 1)
    
    if current_level >= 20:
        return RedirectResponse(f"/characters/{char_id}?error=Max level reached!", 303)

    # 2. Apply Updates
    # Level +1, Attr +2, Skill +1
    await characters_collection.update_one(
        {"_id": char["_id"]},
        {
            "$inc": {
                "status.level": 1,
                "points.attribute_points": 2,
                "points.skill_points": 1
            }
        }
    )
    
    return RedirectResponse(f"/characters/{char_id}?msg=Level Up!", 303)