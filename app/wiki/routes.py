from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from bson import ObjectId
from datetime import datetime

from app.database import db
from app.auth.dependencies import get_current_user, get_current_user_required
from app.wiki.models import WikiPage

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
wiki_collection = db["wiki"]

# --- 1. INDEX (Table of Contents) ---
@router.get("/wiki", response_class=HTMLResponse)
async def wiki_index(request: Request, user: dict = Depends(get_current_user)):
    # Fetch all pages
    pages = await wiki_collection.find().sort("title", 1).to_list(1000)
    
    # Group by Category manually
    # Structure: {"Factions": [page1, page2], "Rules": [page3]}
    library = {}
    for page in pages:
        cat = page.get("category", "Uncategorized")
        if cat not in library:
            library[cat] = []
        library[cat].append(page)
        
    # Sort categories alphabetically
    sorted_categories = dict(sorted(library.items()))

    return templates.TemplateResponse("wiki_index.html", {
        "request": request, 
        "user": user, 
        "library": sorted_categories
    })

# --- 2. CREATE PAGE (Form) - GM Only ---
@router.get("/wiki/new", response_class=HTMLResponse)
async def new_page_form(request: Request, user: dict = Depends(get_current_user_required)):
    if user["role"] != "GM": return RedirectResponse("/wiki", 303)
    return templates.TemplateResponse("wiki_form.html", {"request": request, "user": user, "page": None})

@router.post("/wiki/new")
async def create_page(
    title: str = Form(...),
    category: str = Form(...),
    content: str = Form(...),
    user: dict = Depends(get_current_user_required)
):
    if user["role"] != "GM": return RedirectResponse("/wiki", 303)
    
    new_page = WikiPage(title=title, category=category, content=content)
    await wiki_collection.insert_one(new_page.model_dump(by_alias=True, exclude={"id"}))
    
    return RedirectResponse("/wiki", status.HTTP_303_SEE_OTHER)

# --- 3. VIEW PAGE ---
@router.get("/wiki/{page_id}", response_class=HTMLResponse)
async def view_page(page_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(page_id): raise HTTPException(404)
    
    page = await wiki_collection.find_one({"_id": ObjectId(page_id)})
    if not page: raise HTTPException(404, "Page not found")
    
    return templates.TemplateResponse("wiki_page.html", {
        "request": request, 
        "user": user, 
        "page": page
    })

# --- 4. EDIT PAGE - GM Only ---
@router.get("/wiki/{page_id}/edit", response_class=HTMLResponse)
async def edit_page_form(page_id: str, request: Request, user: dict = Depends(get_current_user_required)):
    if user["role"] != "GM": return RedirectResponse("/wiki", 303)
    
    page = await wiki_collection.find_one({"_id": ObjectId(page_id)})
    return templates.TemplateResponse("wiki_form.html", {"request": request, "user": user, "page": page})

@router.post("/wiki/{page_id}/edit")
async def update_page(
    page_id: str,
    title: str = Form(...),
    category: str = Form(...),
    content: str = Form(...),
    user: dict = Depends(get_current_user_required)
):
    if user["role"] != "GM": return RedirectResponse("/wiki", 303)
    
    await wiki_collection.update_one(
        {"_id": ObjectId(page_id)},
        {"$set": {
            "title": title, 
            "category": category, 
            "content": content,
            "updated_at": datetime.utcnow()
        }}
    )
    return RedirectResponse(f"/wiki/{page_id}", status.HTTP_303_SEE_OTHER)

# --- 5. DELETE PAGE - GM Only ---
@router.post("/wiki/{page_id}/delete")
async def delete_page(page_id: str, user: dict = Depends(get_current_user_required)):
    if user["role"] != "GM": return RedirectResponse("/wiki", 303)
    await wiki_collection.delete_one({"_id": ObjectId(page_id)})
    return RedirectResponse("/wiki", status.HTTP_303_SEE_OTHER)