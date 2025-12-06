from fastapi.templating import Jinja2Templates
from app.core.i18n import trans, trans_with_params

# Create a single instance
templates = Jinja2Templates(directory="app/templates")

# Register the filters globally
templates.env.filters["trans"] = trans
# transp: translate with params dict
templates.env.filters["transp"] = lambda key, params={}: trans_with_params(key, params)


def int_to_roman(num: int) -> str:
	"""Convert an integer to a Roman numeral (1..3999)."""
	if not isinstance(num, int) or num <= 0:
		return str(num)
	vals = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
	syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
	res = []
	i = 0
	while num > 0 and i < len(vals):
		count = num // vals[i]
		res.append(syms[i] * count)
		num -= vals[i] * count
		i += 1
	return "".join(res)


templates.env.filters["roman"] = int_to_roman