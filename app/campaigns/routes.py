
from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from bson import ObjectId

from app.database import db, users_collection, characters_collection
from app.auth.dependencies import get_current_user
from app.campaigns.models import Campaign, CampaignMember, MemberStatus, MapPin
from app.game_rules import GAME_ACTIONS, DIFFICULTY_LEVELS

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
campaigns_collection = db["campaigns"]

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
    # 1. AUTH CHECK: Redirect if not logged in
    if not user:
        return RedirectResponse("/auth/login", status.HTTP_303_SEE_OTHER)

    # 2. Campaigns I GM (Only if GM)
    my_campaigns = []
    if user["role"] == "GM":
        my_campaigns = await campaigns_collection.find({"gm_id": user["id"]}).to_list(100)
    
    # 3. Campaigns I am participating in (As a Player)
    participating_campaigns = await campaigns_collection.find({
        "members.user_id": user["id"]
    }).to_list(100)
    
    # 4. Available to Join
    available_campaigns = await campaigns_collection.find({
        "gm_id": {"$ne": user["id"]},
        "members.user_id": {"$ne": user["id"]},
        "status": "Active"
    }).to_list(100)
    
    # Get user's characters
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
    # BLOCK LOGIC: Only GMs can create
    if user["role"] != "GM":
        return RedirectResponse("/campaigns?error=Only GMs can create campaigns", status.HTTP_303_SEE_OTHER)

    new_camp = Campaign(name=name, gm_id=user["id"])
    await campaigns_collection.insert_one(new_camp.model_dump(by_alias=True, exclude={"id"}))
    return RedirectResponse("/campaigns", status.HTTP_303_SEE_OTHER)

@router.post("/campaigns/join")
async def join_campaign(
    camp_id: str = Form(...), 
    char_id: str = Form(...),
    user: dict = Depends(get_current_user)
):
    # Get Character Name for display
    char = await characters_collection.find_one({"_id": ObjectId(char_id)})
    
    # Check if already in
    camp = await campaigns_collection.find_one({
        "_id": ObjectId(camp_id), 
        "members.character_id": char_id
    })
    if camp:
        return RedirectResponse("/campaigns?error=Character already in campaign", 303)

    new_member = CampaignMember(
        user_id=user["id"], 
        character_id=char_id, 
        character_name=char["name"]
    )
    
    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id)},
        {"$push": {"members": new_member.model_dump()}}
    )
    return RedirectResponse("/campaigns?msg=Request sent", 303)

# --- GM DASHBOARD (THE SHIELD) ---
@router.get("/campaigns/{camp_id}/dashboard", response_class=HTMLResponse)
async def campaign_dashboard(camp_id: str, request: Request, user: dict = Depends(get_current_user)):
    camp, is_gm = await get_campaign_helper(camp_id, user)
    
    if not is_gm:
        return RedirectResponse("/campaigns?error=Access Denied", 303)

    # Fetch full Character details for accepted members (for the grid)
    accepted_ids = [ObjectId(m["character_id"]) for m in camp["members"] if m["status"] == "Accepted"]
    party_chars = await characters_collection.find({"_id": {"$in": accepted_ids}}).to_list(100)
    
    return templates.TemplateResponse("campaign_dashboard.html", {
        "request": request, "user": user, "campaign": camp,
        "party": party_chars,
        "actions": GAME_ACTIONS, # For the simulator
        "difficulty_levels": DIFFICULTY_LEVELS
    })

# --- GM ACTIONS: Accept/Reject ---
@router.post("/campaigns/{camp_id}/members/status")
async def update_member_status(
    camp_id: str, 
    char_id: str = Form(...), 
    new_status: str = Form(...),
    user: dict = Depends(get_current_user)
):
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
    camp_id: str,
    char_id: str = Form(...),
    amount: int = Form(...), # Positive = Char to Party. Negative = Party to Char.
    user: dict = Depends(get_current_user)
):
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)

    char = await characters_collection.find_one({"_id": ObjectId(char_id)})
    
    # Validation
    if amount > 0: # Taking from Char
        if char["status"]["gold"] < amount:
            return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Character has insufficient gold", 303)
    else: # Giving to Char (amount is negative)
        if camp["party_gold"] < abs(amount):
            return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Party treasury is too low", 303)

    # Execute Transaction
    # 1. Update Char
    await characters_collection.update_one(
        {"_id": ObjectId(char_id)},
        {"$inc": {"status.gold": -amount}} 
    )
    # 2. Update Campaign
    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id)},
        {"$inc": {"party_gold": amount}}
    )
    
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- GM: Update Settings (Map, Upkeep) ---
@router.post("/campaigns/{camp_id}/settings")
async def update_settings(
    camp_id: str,
    map_url: str = Form(...),
    upkeep: int = Form(...),
    user: dict = Depends(get_current_user)
):
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)

    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id)},
        {"$set": {"map_url": map_url, "upkeep_cost": upkeep}}
    )
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- ACTION: Pay Upkeep ---
@router.post("/campaigns/{camp_id}/gold/pay_upkeep")
async def pay_upkeep(camp_id: str, user: dict = Depends(get_current_user)):
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)
    
    cost = camp.get("upkeep_cost", 0)
    
    # 1. Validation
    if cost <= 0:
        return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=No upkeep cost set", 303)

    if camp["party_gold"] < cost:
         return RedirectResponse(f"/campaigns/{camp_id}/dashboard?error=Not enough gold in treasury", 303)

    # 2. Deduct Gold
    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id)},
        {"$inc": {"party_gold": -cost}}
    )
    
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard?msg=Upkeep Paid", 303)

# --- ACTION: Add Map Pin ---
@router.post("/campaigns/{camp_id}/map/pin")
async def add_map_pin(
    camp_id: str,
    x: float = Form(...),
    y: float = Form(...),
    label: str = Form(...),
    type: str = Form(...),
    user: dict = Depends(get_current_user)
):
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)
    
    new_pin = MapPin(x=x, y=y, label=label, type=type)
    
    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id)},
        {"$push": {"map_pins": new_pin.model_dump()}}
    )
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)

# --- ACTION: Delete Map Pin ---
@router.post("/campaigns/{camp_id}/map/pin/delete")
async def delete_map_pin(
    camp_id: str,
    pin_id: str = Form(...),
    user: dict = Depends(get_current_user)
):
    camp, is_gm = await get_campaign_helper(camp_id, user)
    if not is_gm: return RedirectResponse("/", 303)
    
    await campaigns_collection.update_one(
        {"_id": ObjectId(camp_id)},
        {"$pull": {"map_pins": {"id": pin_id}}}
    )
    return RedirectResponse(f"/campaigns/{camp_id}/dashboard", 303)