# RPG-Imperium

Small FastAPI-based tabletop RPG management system:
- Player character sheets, equipment and inventory
- GM campaign dashboard with map pins, party management and simple combat simulator
- In-app wiki/archives
- MongoDB-backed persistence and Jinja2 templates for UI

License: MIT (see LICENSE)

Quick start (development)
1. Create a Python virtualenv and install dependencies:
   - python -m venv .venv
   - .venv\Scripts\activate (Windows) or source .venv/bin/activate (mac/linux)
   - pip install -r requirements.txt
   If a requirements file is not present, ensure at least: fastapi, uvicorn, jinja2, pymongo, python-jose (or jwt library used), passlib[bcrypt]

2. Set required environment variables (examples):
   - MONGODB_URI=mongodb://localhost:27017/rpg_imperium
   - SECRET_KEY=your_jwt_secret_key
   - (any other settings your app expects)

3. Run the app:
   - uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

4. Open the UI:
   - http://localhost:8000/auth/login
   - Use /auth/register to create accounts (default role may be PLAYER) — to create a GM account you can either seed the DB directly or promote a user in Mongo.

High-level project layout
- app/
  - main.py                 - FastAPI app and router mounting
  - auth/                   - authentication routes, security utilities and dependencies
  - characters/             - character creation, sheet, inventory, equipment and GM actions
  - campaigns/              - campaign management, GM dashboard, combat simulation
  - wiki/                   - wiki routes and templates
  - templates/              - Jinja2 templates (base.html, dashboard, character sheets, etc.)
  - static/                 - static assets (css/js/images)
  - database.py             - DB connection & collection helpers
  - models/*.py             - pydantic models used across the app
  - game_rules.py           - game logic helpers (derived stats, skill trees, constants)

Important runtime notes
- Database: the app uses MongoDB collections (users, characters, campaigns, wiki, bestiary). Ensure MONGODB_URI points to a running Mongo instance.
- Authentication: uses JWT stored in an HttpOnly cookie named `access_token`. SECRET_KEY must match whatever auth/security expects in your code.
- Roles: two main roles appear in the app — GM (game master) and PLAYER. Many GM actions are gated by role checks in routes.
- Creating a GM: registration endpoint sets a default role (check app/auth/routes.py). To make a GM, either:
  - Promote a user document in Mongo (`role` field -> "GM"), or
  - Add a seeded user via a small script that writes a user with role "GM" and a hashed password.

Developer tips
- Templates: templates rely on specific context variables (user, character, campaign). Inspect corresponding route handlers to see required keys when iterating or rendering.
- Static files: mounted at /static; include any client JS used by templates (e.g., campaign.js referenced in templates).
- Defensive checks: many routes redirect unauthenticated users to /auth/login and return URL errors via query params (e.g., ?error=...).

Contributing
- Fork, create a feature branch, add tests where applicable, open a PR.
- Keep UI changes in templates and static; business logic in routes / game_rules to keep separation.

Troubleshooting
- If templates render blank or values missing, check the route that calls TemplateResponse for the expected context keys.
- If Mongo operations fail, confirm MONGODB_URI and collection names match those referenced in app.* modules.

Acknowledgements
- Project structure and aesthetics reflect a parchment / archives theme intended for tabletop campaigns.

Internationalization (i18n)
- The app uses a simple JSON-based translation loader (app/core/i18n.py) and a Jinja filter named trans.
- Translation files live in app/locales/ (e.g. app/locales/pt_BR.json).
- To add or change translations:
  1. Open the target JSON file and add keys/values like: "Dashboard": "Painel"
  2. Restart the FastAPI process (translations are loaded at startup via load_translations).
  3. Use the filter in templates: {{ 'Dashboard' | trans }} or in templates inside HTML.
- The translations are loaded by app.core.i18n.load_translations(settings.LANGUAGE). Ensure settings.LANGUAGE matches the locale filename.

Adding new translatable strings
- Update your template to wrap visible labels: <a href="/dashboard">{{ 'Dashboard' | trans }}</a>
- Add the key to the appropriate JSON file in app/locales/.
- Restart the app and verify the UI.