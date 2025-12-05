import json
import os
from app.config import settings

# Global dictionary to hold translations
_translations = {}

def load_translations(lang: str):
    """Loads the JSON file for the specific language."""
    global _translations
    
    # Path to your json file
    file_path = f"app/locales/{lang}.json"
    
    if not os.path.exists(file_path):
        print(f"Warning: Translation file {file_path} not found. Defaulting to keys.")
        _translations = {}
        return

    with open(file_path, "r", encoding="utf-8") as f:
        _translations = json.load(f)

def trans(text: str):
    """
    Looks up the text in the loaded dictionary. 
    If not found, returns the original text.
    """
    return _translations.get(text, text)

def trans_with_params(text: str, params: dict):
    """
    Lookup translation and replace placeholders like {actor}, {target}, {dmg}, etc.
    Params keys are interpolated via simple string replacement.
    """
    template = _translations.get(text, text)
    if not params:
        return template
    # simple, safe replacement
    for k, v in params.items():
        placeholder = "{" + k + "}"
        template = template.replace(placeholder, str(v))
    return template