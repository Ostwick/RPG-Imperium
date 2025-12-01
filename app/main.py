from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.auth import routes as auth_routes
from app.characters import routes as character_routes
from app.campaigns import routes as campaign_routes
from app.wiki import routes as wiki_routes

app = FastAPI()

# Mount Static Files (CSS/JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include Routers
app.include_router(auth_routes.router, prefix="/auth", tags=["Auth"])
app.include_router(character_routes.router, tags=["Characters"])
app.include_router(campaign_routes.router, tags=["Campaigns"])
app.include_router(wiki_routes.router, tags=["Wiki"])

@app.get("/")
async def root():
    return {"message": "Empire RPG System is Live"}