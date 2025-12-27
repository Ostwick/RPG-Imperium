import random
from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from app.templates import templates
from bson import ObjectId

from app.database import db, users_collection, characters_collection
from app.auth.dependencies import get_current_user
from app.campaigns.models import Campaign, CampaignMember, MemberStatus, MapPin, Combatant, EnemyTemplate
from app.game_rules import DIFFICULTY_LEVELS, calculate_derived_stats, get_game_actions

router = APIRouter()
campaigns_collection = db["campaigns"]
bestiary_collection = db["bestiary"]

# --- HELPER ---
async def get_campaign_helper(camp_id: str, user: dict):
    if not ObjectId.is_valid(camp_id): raise HTTPException(404)
    camp = await campaigns_collection.find_one({"_id": ObjectId(camp_id)})
    if not camp: raise HTTPException(404, "Campaign not found")
    
    is_gm = camp["gm_id"] == user["id"]
    return camp, is_gm

# --- ROUTES ---
@router.get("/campaigns", response_class=HTMLResponse)
async def list_campaigns(request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", status.HTTP_303_SEE_OTHER)

    my_campaigns = []
    if user["role"] == "GM":
        my_campaigns = await campaigns_collection.find({"gm_id": user["id"]}).to_list(100)
    
    participating_campaigns = await campaigns_collection.find({"members.user_id": user["id"]}).to_list(100)
    
    available_campaigns = await campaigns_collection.find({
        "gm_id": {"$ne": user["id"]},
        "members.user_id": {"$ne": user["id"]},
        "status": "Active"
    }).to_list(100)
    
    my_chars = await characters_collection.find({"user_id": ObjectId(user["id"])}).to_list(50)

    return templates.TemplateResponse("campaign_list.html", {
        "request": request, "user": user, 
        "my_campaigns": my_campaigns, 
        "participating_campaigns": participating_campaigns,
        "available_campaigns": available_campaigns,
        "my_chars": my_chars
    })

@router.post("/campaigns/new")
async def create_campaign(name: str = Form(...), user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    if user["role"] != "GM": return RedirectResponse("/campaigns", 303)

    new_camp = Campaign(name=name, gm_id=user["id"])
    await campaigns_collection.insert_one(new_camp.model_dump(by_alias=True, exclude={"id"}))
    return RedirectResponse("/campaigns", status.HTTP_303_SEE_OTHER)

@router.post("/campaigns/join")
async def join_campaign(camp_id: str = Form(...), char_id: str = Form(...), user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)

    char = await characters_collection.find_one({"_id": ObjectId(char_id)})
    camp = await campaigns_collection.find_one({"_id": ObjectId(camp_id), "members.character_id": char_id})
    if camp: return RedirectResponse("/campaigns?error=Already joined", 303)

    new_member = CampaignMember(user_id=user["id"], character_id=char_id, character_name=char["name"])
    await campaigns_collection.update_one({"_id": ObjectId(camp_id)}, {"$push": {"members": new_member.model_dump()}})
    return RedirectResponse("/campaigns?msg=Request sent", 303)

# --- GM DASHBOARD (THE SHIELD) ---
@router.get("/campaigns/{camp_id}/dashboard", response_class=HTMLResponse)
async def campaign_dashboard(camp_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    camp, is_gm = await get_campaign_helper(camp_id, user)
    
    if not is_gm: return RedirectResponse("/campaigns?error=Access Denied", 303)

    accepted_ids = [ObjectId(m["character_id"]) for m in camp["members"] if m["status"] == "Accepted"]
    party_chars = await characters_collection.find({"_id": {"$in": accepted_ids}}).to_list(100)
    
    total_speed = 0
    processed_party = []
    
    for char in party_chars:
        derived = await calculate_derived_stats(char)
        char["derived"] = derived 
        total_speed += derived["current_speed"]
        processed_party.append(char)
        
    avg_speed = int(total_speed / len(party_chars)) if party_chars else 100

    enemies_list = await bestiary_collection.find().to_list(100)

    actions = await get_game_actions()

    # Enrich combatants with ammo info (not persisted; for UI only)
    if camp.get("combat_active"):
        enriched = []
        ranged_types = {"Bow", "Crossbow", "Throwing"}
        for comb in camp.get("combatants", []):
            comb_copy = dict(comb)
            comb_copy["ammo_remaining"] = None
            comb_copy["is_ranged"] = False
            if comb.get("type") == "Player":
                char = await characters_collection.find_one({"_id": ObjectId(comb.get("id"))})
                if char:
                    equip = char.get("equipment", {}) or {}
                    # detect ranged weapon
                    weapon_type = None
                    weapon_slot = None
                    weapon_item = None
                    for slot in ("hand_main", "hand_off"):
                        w = equip.get(slot)
                        if w and w.get("weapon_type") in ranged_types and w.get("category") == "Weapon":
                            weapon_type = w.get("weapon_type")
                            weapon_slot = slot
                            weapon_item = w
                            break
                    if weapon_type in ranged_types:
                        comb_copy["is_ranged"] = True
                        ammo_qty = 0
                        if weapon_type == "Throwing":
                            if weapon_item:
                                ammo_qty = max(int(weapon_item.get("quantity", 0)), 0)
                        else:
                            for slot in ("hand_off", "hand_main"):
                                itm = equip.get(slot)
                                if itm and itm.get("category") == "Ammo":
                                    ammo_qty += max(int(itm.get("quantity", 0)), 0)
                        comb_copy["ammo_remaining"] = ammo_qty
            enriched.append(comb_copy)
        camp["combatants"] = enriched

    return templates.TemplateResponse("campaign_dashboard.html", {
        "request": request, "user": user, "campaign": camp,
        "party": processed_party,
        "party_speed": avg_speed,
        "actions": actions, "difficulty_levels": DIFFICULTY_LEVELS,
        "bestiary": enemies_list
    })

# --- GM ACTIONS: Accept/Reject ---
@router.post("/campaigns/{camp_id}/members/status")
async def update_member_status(
    camp_id: str, char_id: str = Form(...), new_status: str = Form(...), user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)

    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id), "members.character_id": char_id},
        {"$set": {"members.$.status": new_status}}
    )
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- ECONOMY: Transfer Gold ---
@router.post("/campaigns/{camp_id}/gold/transfer")
async def transfer_gold(
    camp_id: str, char_id: str = Form(...), amount: int = Form(...), user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)

    char = await characters_collection.find_one({"_id": ObjectId(char_id)})
    
    if amount > 0 and char["status"]["gold"] < amount:
        return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Insufficient gold", 303)
    elif amount < 0 and camp["party_gold"] < abs(amount):
        return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Treasury low", 303)

    await characters_collection.update_one({"_id": ObjectId(char_id)}, {"$inc": {"status.gold": -amount}})
    await campaigns_collection.update_one({"_id": ObjectId(camp_id)}, {"$inc": {"party_gold": amount}})
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- GM: Update Settings (Map, Upkeep) ---
@router.post("/campaigns/{camp_id}/settings")
async def update_settings(
    camp_id: str, map_url: str = Form(...), upkeep: int = Form(...), renown: int = Form(0), user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)

    await campaigns_collection.update_one({"_id": ObjectId(camp_id)}, {"$set": {"map_url": map_url, "upkeep_cost": upkeep, "renown": renown}})
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- ACTION: Pay Upkeep ---
@router.post("/campaigns/{camp_id}/gold/pay_upkeep")
async def pay_upkeep(camp_id: str, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)
    
    cost = camp.get("upkeep_cost", 0)
    if cost <= 0 or camp["party_gold"] < cost:
         return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Cannot pay upkeep", 303)

    await campaigns_collection.update_one({"_id": ObjectId(camp_id)}, {"$inc": {"party_gold": -cost}})
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard?msg=Upkeep Paid", 303)

# --- ACTION: Add Map Pin ---
@router.post("/campaigns/{camp_id}/map/pin")
async def add_map_pin(
    camp_id: str, x: float = Form(...), y: float = Form(...), label: str = Form(...), type: str = Form(...),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)
    
    new_pin = MapPin(x=x, y=y, label=label, type=type)
    await campaigns_collection.update_one({"_id": ObjectId(camp_id)}, {"$push": {"map_pins": new_pin.model_dump()}})
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- ACTION: Delete Map Pin ---
@router.post("/campaigns/{camp_id}/map/pin/delete")
async def delete_map_pin(camp_id: str, pin_id: str = Form(...), user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)
    
    await campaigns_collection.update_one({"_id": ObjectId(camp_id)}, {"$pull": {"map_pins": {"id": pin_id}}})
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- COMBAT: INITIALIZE ---
@router.post("/campaigns/{camp_id}/combat/start")
async def start_combat(
    camp_id: str,
    player_ids: list[str] = Form(...), # List of selected players
    enemy_ids: list[str] = Form(...),  # List of selected enemy templates
    user: dict = Depends(get_current_user)
):
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)

    combatants = []

    # 1. Add Players (Snapshot their current stats)
    for pid in player_ids:
        char = await characters_collection.find_one({"_id": ObjectId(pid)})
        derived = await calculate_derived_stats(char) # Get calculated stats
        
        c = Combatant(
            id=str(char["_id"]),
            name=char["name"],
            type="Player",
            hp_current=char["status"]["hp_current"],
            hp_max=char["status"]["hp_max"],
            stamina_current=char["status"]["stamina"],
            stamina_max=char["status"].get("stamina_max", 100) + 50,
            speed=derived["current_speed"],
            damage=derived["attack"],
            defense=derived["defense"],
            crit_bonus=derived["crit_bonus"]
        )
        combatants.append(c)

    # 2. Add Enemies (From Bestiary)
    for eid in enemy_ids:
        # Note: In a real form this might be a list of IDs including duplicates. 
        # For simplicity, we assume the GM selects "Bandit" 3 times if they want 3 bandits.
        enemy = await bestiary_collection.find_one({"_id": ObjectId(eid)})
        
        # We append a random ID suffix to handle multiple of same type
        unique_id = f"{eid}_{random.randint(1000,9999)}"
        
        c = Combatant(
            id=unique_id,
            name=enemy["name"],
            type="Enemy",
            hp_current=enemy["hp_max"],
            hp_max=enemy["hp_max"],
            stamina_current=enemy["stamina"],
            stamina_max=enemy["stamina"],
            speed=enemy["speed"],
            damage=enemy["damage"],
            defense=enemy["defense"],
            crit_bonus=enemy["crit_bonus"]
        )
        combatants.append(c)

    # Save Initial State
    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id)},
        {"$set": {
            "combat_active": True,
            "combatants": [c.model_dump() for c in combatants],
            "combat_log": ["Combat Started!"]
        }}
    )
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- COMBAT: NEXT TURN (The Speed Race) ---
@router.post("/campaigns/{camp_id}/combat/next")
async def next_turn(camp_id: str, user: dict = Depends(get_current_user)):
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)
    
    combatants = camp["combatants"]
    
    # 1. Check if anyone LIVING is ALREADY ready
    # We filter for HP > 0 before checking top AP
    living_combatants = [c for c in combatants if c["hp_current"] > 0]
    
    # If everyone is dead, we can't tick (or we just tick normally to let time pass? Let's just return)
    if not living_combatants:
        return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

    living_combatants.sort(key=lambda x: x["action_points"], reverse=True)
    
    # If the fastest living person is ready, stop ticking.
    if living_combatants[0]["action_points"] >= 100:
        return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

    # 2. THE RACE: Loop until a LIVING person hits 100
    winner_found = False
    ticks = 0
    
    # Safety break after 1000 ticks to prevent infinite loops if speeds are 0
    while not winner_found and ticks < 1000:
        ticks += 1
        for c in combatants:
            # Only charge AP for the living
            if c["hp_current"] > 0: 
                c["action_points"] += c["speed"]
                if c["action_points"] >= 100:
                    winner_found = True
    
    # Save State
    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id)},
        {"$set": {"combatants": combatants}}
    )
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- COMBAT: EXECUTE ACTION ---
@router.post("/campaigns/{camp_id}/combat/act")
async def combat_action(
    camp_id: str,
    actor_index: int = Form(...),
    target_index: int = Form(...),
    action_type: str = Form(...), # "Attack", "Wait", "Miss"
    bonus_dmg: int = Form(0),
    bonus_def: int = Form(0),
    is_crit: bool = Form(False),
    user: dict = Depends(get_current_user)
):
    camp, is_gm = await get_campaign_helper(camp_id, user)
    combatants = camp["combatants"]
    log = camp.get("combat_log", [])
    
    actor = combatants[actor_index]
    target = combatants[target_index]
    
    if actor["hp_current"] <= 0:
        return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Actor is unconscious!", 303)

    msg = ""

    # 1. Consume Stamina (Rule: 10 per action)
    stamina_cost = 10
    if actor["stamina_current"] >= stamina_cost:
        actor["stamina_current"] -= stamina_cost
    else:
        actor["stamina_current"] = 0
        # (Optional: Add "Exhausted" note to log if needed)

    # 2. Sync Stamina to Sheet (If Player)
    if actor["type"] == "Player":
        await characters_collection.update_one(
            {"_id": ObjectId(actor["id"])},
            {"$set": {"status.stamina": actor["stamina_current"]}}
        )

    # 3. Action Logic
    if action_type == "Wait":
        actor["action_points"] -= 50
        msg = f"{actor['name']} waits/hesitates."

    elif action_type == "Miss":
        actor["action_points"] -= 100
        msg = f"{actor['name']} attacks {target['name']} but MISSES!"

    elif action_type == "Attack":
        # --- Ammo handling for ranged weapons ---
        if actor["type"] == "Player":
            # Fetch latest character state to inspect equipped weapon/ammo
            actor_char = await characters_collection.find_one({"_id": ObjectId(actor["id"])} )
            if actor_char:
                equip = actor_char.get("equipment", {}) or {}
                ranged_types = {"Bow", "Crossbow", "Throwing"}

                # Identify if the equipped weapon is ranged
                weapon_type = None
                weapon_slot = None
                weapon_item = None
                for slot in ("hand_main", "hand_off"):
                    w = equip.get(slot)
                    if w and w.get("weapon_type") in ranged_types and w.get("category") == "Weapon":
                        weapon_type = w.get("weapon_type")
                        weapon_slot = slot
                        weapon_item = w
                        break

                if weapon_type in ranged_types:
                    if weapon_type == "Throwing":
                        # Throwing uses its own quantity on the equipped weapon item
                        if not weapon_item or weapon_item.get("quantity", 0) <= 0:
                            return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Out%20of%20ammo", 303)
                        dec_result = await characters_collection.update_one(
                            {
                                "_id": ObjectId(actor["id"]),
                                f"equipment.{weapon_slot}.id": weapon_item.get("id"),
                                f"equipment.{weapon_slot}.quantity": {"$gt": 0}
                            },
                            {"$inc": {f"equipment.{weapon_slot}.quantity": -1}}
                        )
                        if dec_result.modified_count == 0:
                            return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Out%20of%20ammo", 303)
                    else:
                        # Bows/Crossbows use separate Ammo category items
                        ammo_slot = None
                        ammo_item = None
                        for slot in ("hand_off", "hand_main"):
                            itm = equip.get(slot)
                            if itm and itm.get("category") == "Ammo":
                                ammo_slot = slot
                                ammo_item = itm
                                break

                        if not ammo_item or ammo_item.get("quantity", 0) <= 0:
                            return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Out%20of%20ammo", 303)

                        # Decrement ammo quantity in the equipped slot, guard against negatives
                        dec_result = await characters_collection.update_one(
                            {
                                "_id": ObjectId(actor["id"]),
                                f"equipment.{ammo_slot}.id": ammo_item.get("id"),
                                f"equipment.{ammo_slot}.quantity": {"$gt": 0}
                            },
                            {"$inc": {f"equipment.{ammo_slot}.quantity": -1}}
                        )
                        if dec_result.modified_count == 0:
                            return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Out%20of%20ammo", 303)

        raw_dmg = actor["damage"] + bonus_dmg
        multiplier = 1.0
        if is_crit:
            multiplier = 1.5 + (actor["crit_bonus"] / 100.0)
            msg += "CRITICAL! "
            
        # Calculate Def (Base + Bonus)
        total_def = target["defense"] + bonus_def
        
        final_dmg = int(raw_dmg * multiplier) - total_def
        if final_dmg < 0: final_dmg = 0
        
        target["hp_current"] -= final_dmg
         # --- DEATH LOGIC UPDATE ---
        if target["hp_current"] <= 0:
            target["hp_current"] = 0
            target["action_points"] = 0
            msg += f" {target['name']} is DOWN!"
        
        # Sync HP to Sheet (If Target is Player)
        if target["type"] == "Player":
            await characters_collection.update_one(
                {"_id": ObjectId(target["id"])},
                {"$set": {"status.hp_current": target["hp_current"]}}
            )
            
        actor["action_points"] -= 100
        msg += f"{actor['name']} hits {target['name']} for {final_dmg} damage."
        
        if target["hp_current"] == 0:
            msg += f" {target['name']} is DOWN!"

    # Log & Save
    log.insert(0, msg)
    if len(log) > 10: log.pop()

    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id)},
        {"$set": {"combatants": combatants, "combat_log": log}}
    )
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- COMBAT: END ---
@router.post("/campaigns/{camp_id}/combat/end")
async def end_combat(camp_id: str, user: dict = Depends(get_current_user)):
    camp, is_gm = await get_campaign_helper(camp_id, user)
    
    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id)},
        {"$set": {"combat_active": False, "combatants": []}}
    )
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)