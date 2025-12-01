from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm

from app.database import users_collection
from app.auth.security import verify_password, create_access_token, get_password_hash
from app.users.models import UserCreate, UserInDB

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 1. Show Login Page (GET)
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# 2. Process Login (POST)
@router.post("/login")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Find user by email
    user = await users_collection.find_one({"email": form_data.username})
    
    if not user or not verify_password(form_data.password, user["password_hash"]):
        # Return login page with error message
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid credentials"
        })

    # Create JWT Token
    access_token = create_access_token(data={"sub": user["email"], "role": user["role"]})

    # Create Response (Redirect to Dashboard)
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    # Set Cookie (HttpOnly = JavaScript cannot read it, safer)
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True
    )
    return response

# 3. Register User (Quick MVP helper)
@router.post("/register")
async def register(user_data: UserCreate):
    # Check if exists
    if await users_collection.find_one({"email": user_data.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password and save
    new_user = UserInDB(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password)
    )
    
    await users_collection.insert_one(new_user.model_dump(by_alias=True, exclude={"id"}))
    return {"msg": "User created successfully"}