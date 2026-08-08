# file: app/normalize_sections/normalize_countries.py
"""
Normalise les noms de pays vers le nom court officiel ISO 3166 (pycountry),
en évitant tout matching fuzzy risqué -- deux pays distincts peuvent avoir
des noms très proches (ex: Republic of the Congo vs Democratic Republic of
Congo sont deux pays différents, pas des variantes du même nom).

Stratégie, dans l'ordre :
  1. lookup exact insensible à la casse sur les noms ISO (common_name,
     name, official_name) via pycountry
  2. fallback sur un petit dictionnaire d'alias manuels pour les formulations
     que pycountry ne reconnaît pas telles quelles
  3. tout ce qui reste non résolu retourne None -- jamais résolu par un
     "au petit bonheur" fuzzy
"""

import pycountry

# Alias manuels pour les formulations que pycountry ne résout pas par lookup
# exact (variantes de style rédactionnel, pas des pays différents).
MANUAL_ALIASES = {
    "islamic republic of mauritania": "Mauritania",
    "republic of cameroon": "Cameroon",
    "republic of chad": "Chad",
    "republic of mali": "Mali",
    "union of the comoros": "Comoros",
    "democratic republic of congo": "Congo, The Democratic Republic of the",
    "democratic republic of the congo": "Congo, The Democratic Republic of the",
    "republic of the congo": "Congo",
}


def normalize_country_name(raw: str) -> str | None:
    """
    Return the canonical ISO short name for a raw country string, or None
    if it can't be confidently resolved.
    """
    if not raw or not raw.strip():
        return None

    key = raw.strip().lower()

    if key in MANUAL_ALIASES:
        return MANUAL_ALIASES[key]

    # Exact, case-insensitive lookup against pycountry's known name fields
    try:
        match = pycountry.countries.lookup(raw)
        return match.name
    except LookupError:
        return None