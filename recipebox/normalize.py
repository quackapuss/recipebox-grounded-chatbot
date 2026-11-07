"""Conservative normalization. Originals are never overwritten."""
import re
import unicodedata
from fractions import Fraction
from functools import lru_cache

VERSION = "1.0"
FRACTIONS = {"½": " 1/2", "¼": " 1/4", "¾": " 3/4", "⅓": " 1/3", "⅔": " 2/3", "⅛": " 1/8", "⅜": " 3/8", "⅝": " 5/8", "⅞": " 7/8"}
UNITS = {
    "g": ("mass_g", 1), "gram": ("mass_g", 1), "grams": ("mass_g", 1),
    "kg": ("mass_g", 1000), "kilogram": ("mass_g", 1000),
    "oz": ("mass_g", 28.349523125), "ounce": ("mass_g", 28.349523125), "ounces": ("mass_g", 28.349523125),
    "lb": ("mass_g", 453.59237), "pound": ("mass_g", 453.59237), "pounds": ("mass_g", 453.59237),
    "ml": ("volume_ml", 1), "milliliter": ("volume_ml", 1), "l": ("volume_ml", 1000), "liter": ("volume_ml", 1000),
    "cup": ("volume_ml", 236.5882365), "cups": ("volume_ml", 236.5882365),
    "tbsp": ("volume_ml", 14.7867648), "tablespoon": ("volume_ml", 14.7867648), "tablespoons": ("volume_ml", 14.7867648),
    "tsp": ("volume_ml", 4.9289216), "teaspoon": ("volume_ml", 4.9289216), "teaspoons": ("volume_ml", 4.9289216),
}
SINGULAR = {"eggs": "egg", "onions": "onion", "tomatoes": "tomato", "potatoes": "potato", "bananas": "banana", "peanuts": "peanut", "cloves": "clove", "almonds": "almond", "walnuts": "walnut", "cashews": "cashew", "mushrooms": "mushroom", "carrots": "carrot", "apples": "apple", "scallions": "scallion", "chillies": "chili", "chilies": "chili", "peppers": "pepper", "lentils": "lentil", "beans": "bean", "chickpeas": "chickpea", "raisins": "raisin", "oats": "oat", "lemons": "lemon", "limes": "lime", "whites": "white", "yolks": "yolk"}
PREP = r"\b(?:finely|coarsely|freshly|roughly|thinly|fresh|large|small|medium|chopped|diced|minced|sliced|peeled|crushed|grated|shredded|melted|softened|beaten|divided|optional|ripe|very|about|approximately|whole|boneless|skinless)\b"


def clean(text):
    for a, b in FRACTIONS.items():
        text = str(text).replace(a, b)
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = text.replace("advertisement", "").replace("\u00a0", " ")
    text = re.sub(r"\b(?:tbsps?|tbls?)\b", "tablespoon", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical(line):
    text = clean(line)
    if not text or text in {"ingredients", "for the sauce:", "for the filling:"}:
        return ""
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.split(r"[,;]", text)[0]
    text = re.sub(r"^\s*[\d\s./\-–]+", "", text)
    unit_words = "|".join(sorted(UNITS, key=len, reverse=True))
    text = re.sub(r"^(?:(?:" + unit_words + r"|cloves?|cans?|packages?|pinch|dash|bunch|sprigs?|slices?)\b\.?\s*(?:of\s+)?)+", "", text)
    text = re.sub(PREP, " ", text)
    text = re.sub(r"\b(?:to taste|as needed|for serving|for garnish|plus more.*|or more.*)\b", "", text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text).replace("-", " ")
    words = [SINGULAR.get(w, w) for w in text.split()]
    text = " ".join(words).strip()
    aliases = {"scallion": "green onion", "spring onion": "green onion", "caster sugar": "superfine sugar", "bicarbonate of soda": "baking soda", "plain flour": "all purpose flour", "all purpose flour": "all purpose flour", "extra virgin olive oil": "olive oil", "kosher salt": "salt", "sea salt": "salt", "unsalted butter": "butter", "salted butter": "butter", "ground black pepper": "black pepper", "ground pepper": "black pepper", "granulated sugar": "sugar", "white sugar": "sugar"}
    return aliases.get(text, text)


@lru_cache(maxsize=512)
def term_pattern(term):
    name = canonical(term)
    return re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)") if name else None


def contains(key, term):
    """Whole-token phrase family predicate; garlic also matches garlic powder."""
    pattern = term_pattern(term)
    return bool(pattern.search(key)) if pattern else False


def steps(instructions):
    """Nonempty newline paragraphs; sentence boundaries when only one paragraph."""
    paragraphs = [x.strip() for x in str(instructions or "").splitlines() if x.strip()]
    if len(paragraphs) > 1:
        return paragraphs
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", paragraphs[0]) if s.strip()] if paragraphs else []


def quantity(line):
    """Return (dimension, value), only for unambiguous simple leading quantities."""
    text = clean(line)
    if re.match(r"^\d+(?:\s+\d+/\d+)?\s*(?:-|–|to)\s*\d", text) or re.search(r"\([^)]*\)", text):
        return None
    m = re.match(r"^(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s+([a-z]+)?", text)
    if not m:
        return None
    amount = sum(float(Fraction(p)) for p in m[1].split())
    unit = m[2] or ""
    if unit in UNITS:
        dim, factor = UNITS[unit]
        return dim, amount * factor
    # Counts are reliable only for these explicitly countable forms.
    if unit in {"egg", "eggs", "onion", "onions", "tomato", "tomatoes", "banana", "bananas"}:
        return "count", amount
    return None


# This is a text screen, not certification of absence, labels, or cross-contact.
GROUPS = {
    "dairy": ["milk", "cream", "butter", "cheese", "yogurt", "yoghurt", "whey", "casein", "ghee", "buttermilk", "parmesan", "mozzarella", "cheddar", "ricotta", "mascarpone", "feta", "paneer", "pecorino", "brie", "gouda", "gruyere", "gruyère", "fontina", "asiago", "provolone", "half and half", "half-and-half"],
    "egg": ["egg", "eggs", "mayonnaise", "meringue", "albumen"],
    "peanut": ["peanut", "peanuts", "groundnut", "groundnuts", "arachis"],
}
GROUP_PATTERNS = {key: re.compile(r"(?<!\w)(?:"+"|".join(re.escape(t) for t in terms)+r")(?!\w)") for key, terms in GROUPS.items()}


def violations(ingredients, excluded):
    found = []
    for restriction in excluded:
        restriction = canonical(restriction)
        pattern = GROUP_PATTERNS.get(restriction) or term_pattern(restriction)
        for raw in ingredients:
            line = clean(raw)
            # Explicit plant products are not evidence of dairy, but other dairy
            # on the same line is still checked.
            if restriction == "dairy":
                line = re.sub(r"\b(?:coconut|almond|soy|soya|oat|rice|cashew)\s+(?:milk|cream|butter)\b", "plant product", line)
                line = re.sub(r"\b(?:cocoa|peanut|almond|cashew)\s+butter\b", "plant product", line)
                line = re.sub(r"\bcream of tartar\b", "tartar", line)
            if pattern and pattern.search(line):
                found.append({"restriction": restriction, "ingredient": raw})
    return found
