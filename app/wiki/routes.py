from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from bson import ObjectId
from datetime import datetime

from app.database import db
from app.auth.dependencies import get_current_user
from app.wiki.models import WikiPage

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
wiki_collection = db["wiki"]

# --- 1. INDEX (Nested Grouping) ---
@router.get("/wiki", response_class=HTMLResponse)
async def wiki_index(request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    
    pages = await wiki_collection.find().sort("title", 1).to_list(1000)
    library = {}
    
    for page in pages:
        grp = page.get("group", "Uncategorized")
        sub = page.get("subcategory", page.get("category", "General"))
        if grp not in library: library[grp] = {}
        if sub not in library[grp]: library[grp][sub] = []
        library[grp][sub].append(page)
        
    return templates.TemplateResponse("wiki_index.html", {
        "request": request, "user": user, "library": dict(sorted(library.items()))
    })

# --- 2. CREATE PAGE ---
@router.get("/wiki/new", response_class=HTMLResponse)
async def new_page_form(request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    if user["role"] != "GM": return RedirectResponse("/wiki", 303)
    return templates.TemplateResponse("wiki_form.html", {"request": request, "user": user, "page": None})

@router.post("/wiki/new")
async def create_page(
    title: str = Form(...), group: str = Form(...), subcategory: str = Form(...), content: str = Form(...),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    if user["role"] != "GM": return RedirectResponse("/wiki", 303)
    
    new_page = WikiPage(title=title, group=group, subcategory=subcategory, content=content)
    await wiki_collection.insert_one(new_page.model_dump(by_alias=True, exclude={"id"}))
    return RedirectResponse("/wiki", 303)

# --- 3. VIEW PAGE ---
@router.get("/wiki/{page_id}", response_class=HTMLResponse)
async def view_page(page_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    if not ObjectId.is_valid(page_id): raise HTTPException(404)
    
    page = await wiki_collection.find_one({"_id": ObjectId(page_id)})
    if not page: raise HTTPException(404)
    
    return templates.TemplateResponse("wiki_page.html", {"request": request, "user": user, "page": page})

# --- 4. EDIT PAGE ---
@router.get("/wiki/{page_id}/edit", response_class=HTMLResponse)
async def edit_page_form(page_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    if user["role"] != "GM": return RedirectResponse("/wiki", 303)
    
    page = await wiki_collection.find_one({"_id": ObjectId(page_id)})
    return templates.TemplateResponse("wiki_form.html", {"request": request, "user": user, "page": page})

@router.post("/wiki/{page_id}/edit")
async def update_page(
    page_id: str, title: str = Form(...), group: str = Form(...), subcategory: str = Form(...), content: str = Form(...),
    user: dict = Depends(get_current_user)
):
    if not user: return RedirectResponse("/auth/login", 303)
    if user["role"] != "GM": return RedirectResponse("/wiki", 303)
    
    await wiki_collection.update_one(
        {"_id": ObjectId(page_id)},
        {"$set": {"title": title, "group": group, "subcategory": subcategory, "content": content, "updated_at": datetime.utcnow()}}
    )
    return RedirectResponse(f"/wiki/{page_id}", 303)

# --- 5. DELETE PAGE ---
@router.post("/wiki/{page_id}/delete")
async def delete_page(page_id: str, user: dict = Depends(get_current_user)):
    if not user: return RedirectResponse("/auth/login", 303)
    if user["role"] != "GM": return RedirectResponse("/wiki", 303)
    
    await wiki_collection.delete_one({"_id": ObjectId(page_id)})
    return RedirectResponse("/wiki", 303)