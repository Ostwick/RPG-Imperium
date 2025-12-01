from fastapi import Request, HTTPException, status, Depends
from jose import jwt, JWTError
from app.config import settings

async def get_current_user(request: Request):
    """
    Reads the 'access_token' cookie, decodes the JWT,
    and returns the user info (sub/email, role).
    """
    token = request.cookies.get("access_token")
    
    if not token:
        # If no cookie, redirect or error. 
        # For HTMX/Templates, returning None allows the route to decide (e.g., redirect to login)
        return None

    try:
        # The cookie value is "Bearer <token>", so we split it
        scheme, _, param = token.partition(" ")
        if scheme.lower() != "bearer":
            return None
            
        payload = jwt.decode(param, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        user_id: str = payload.get("id") # We will ensure login route puts this in token
        
        if username is None:
            return None
            
        return {"sub": username, "role": role, "id": user_id}
        
    except JWTError:
        return None

def get_current_user_required(user: dict = Depends(get_current_user)):
    """
    Enforces that a user MUST be logged in. 
    If not, raises 401 (which we can catch to redirect).
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user