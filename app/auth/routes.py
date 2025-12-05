from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from app.templates import templates
from fastapi.security import OAuth2PasswordRequestForm

from app.database import users_collection
from app.auth.security import verify_password, create_access_token, get_password_hash
from app.users.models import UserInDB

router = APIRouter()

# --- LOGIN ROUTES ---

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # 1. Check User
    user = await users_collection.find_one({"email": form_data.username})
    
    if not user or not verify_password(form_data.password, user["password_hash"]):
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid credentials"
        })

    # 2. Create Token
    # We include 'sub' (email), 'role', and 'id' in the token payload
    access_token = create_access_token(data={
        "sub": user["email"], 
        "role": user["role"],
        "id": str(user["_id"])
    })

    # 3. Set Cookie & Redirect
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True
    )
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

# --- REGISTER ROUTES ---

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    # 1. Validation
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request, "error": "Passwords do not match"
        })
    
    if await users_collection.find_one({"email": email}):
        return templates.TemplateResponse("register.html", {
            "request": request, "error": "Email already registered"
        })

    # 2. Create User
    new_user = UserInDB(
        email=email,
        password_hash=get_password_hash(password),
        role="PLAYER" # Default role
    )
    
    # Save to DB (exclude 'id' so Mongo generates it)
    await users_collection.insert_one(
        new_user.model_dump(by_alias=True, exclude={"id"})
    )

    # 3. Redirect to Login
    # We can pass a success message via URL param or just let them login
    return RedirectResponse(url="/auth/login?registered=true", status_code=status.HTTP_303_SEE_OTHER)