from fastapi.templating import Jinja2Templates
from app.core.i18n import trans, trans_with_params

# Create a single instance
templates = Jinja2Templates(directory="app/templates")

# Register the filters globally
templates.env.filters["trans"] = trans
# transp: translate with params dict
templates.env.filters["transp"] = lambda key, params={}: trans_with_params(key, params)