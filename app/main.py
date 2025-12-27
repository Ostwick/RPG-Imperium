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
    {"name": "Ferrum", "x": 53.35, "y": 42.5, "description": "Armas, forjas e oficinas estatais.", "culture": "Imperial"},
    {"name": "Argentum", "x": 40.3, "y": 59.1, "description": "Moeda, bancos e casas de cunhagem.", "culture": "Imperial"},
    {"name": "Marchia Silvarum", "x": 32.9, "y": 38, "description": "Fronteira com Caelwyn.", "culture": "Imperial"},
    {"name": "Marchia Orientalis", "x": 60.2, "y": 35, "description": "Fronteira contra Kharuun.", "culture": "Imperial"},
    {"name": "Yarilus", "x": 45.75, "y": 54.5, "description": "Vilarejo produtor de grãos.", "culture": "Imperial"},
    {"name": "Ager Magnus", "x": 36.9, "y": 54.5, "description": "Vilarejo produtor de grãos.", "culture": "Imperial"},
    {"name": "Domus Trabium", "x": 38.3, "y": 48.7, "description": "Vilarejo produtor de madeira.", "culture": "Imperial"},
    {"name": "Silva Coronae", "x": 39.8, "y": 52.4, "description": "Vilarejo produtor de madeira.", "culture": "Imperial"},
    {"name": "Argentum Profundum", "x": 32.6, "y": 42, "description": "Vilarejo produtor de prata/ouro.", "culture": "Imperial"},
    {"name": "Vallis Argenti", "x": 34.3, "y": 45, "description": "Vilarejo produtor de prata/ouro.", "culture": "Imperial"},
    {"name": "Nummus Clarus", "x": 30.3, "y": 45.7, "description": "Vilarejo produtor de prata/ouro.", "culture": "Imperial"},
    {"name": "Argentum Lunae", "x": 43.6, "y": 45.5, "description": "Vilarejo produtor de prata/ouro.", "culture": "Imperial"},
    {"name": "Vena Alba", "x": 48.85, "y": 45.5, "description": "Vilarejo produtor de prata/ouro.", "culture": "Imperial"},
    {"name": "Custodia Nitens", "x": 48.8, "y": 42.7, "description": "Vilarejo produtor de prata/ouro.", "culture": "Imperial"}
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
