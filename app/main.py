from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from app.auth import routes as auth_routes
from app.characters import routes as character_routes
from app.campaigns import routes as campaign_routes
from app.wiki import routes as wiki_routes
from app.auth.dependencies import get_current_user
from app.core.i18n import load_translations
from app.templates import templates
from app.config import settings

app = FastAPI()

load_translations(settings.LANGUAGE)

# City Pins for World Map
CITY_PINS = [
    {"name": "Imperium", "x": 39.3, "y": 43, "description": "Trono imperial, Senado e Patriarcado.", "culture": "Imperial"},
    {"name": "Yarilus", "x": 45.5, "y": 55, "description": "Vilarejo produtor de grãos.", "culture": "Imperial"}
]

# Mount Static Files (CSS/JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include Routers
app.include_router(auth_routes.router, prefix="/auth", tags=["Auth"])
app.include_router(character_routes.router, tags=["Characters"])
app.include_router(campaign_routes.router, tags=["Campaigns"])
app.include_router(wiki_routes.router, tags=["Wiki"])

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {"request": request, "user": user})


@app.get("/map", response_class=HTMLResponse)
async def world_map(request: Request, user: dict = Depends(get_current_user)):
    map_image_url = "/static/img/Maltania.png"
    return templates.TemplateResponse(
        "map_overview.html",
        {
            "request": request,
            "user": user,
            "map_image_url": map_image_url,
            "city_pins": CITY_PINS,
        },
    )

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("app/static/favicon.ico")
