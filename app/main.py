from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.auth import routes as auth_routes
from app.characters import routes as character_routes

app = FastAPI()

# Mount Static Files (CSS/JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include Routers
app.include_router(auth_routes.router, prefix="/auth", tags=["Auth"])
app.include_router(character_routes.router, tags=["Characters"])

@app.get("/")
async def root():
    return {"message": "Empire RPG System is Live"}