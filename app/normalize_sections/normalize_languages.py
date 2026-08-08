# file: app/normalize_sections/normalize_language.py
"""
Normalise les noms de langue vers le nom anglais canonique.

Pas de référentiel autoritaire équivalent à ISO 3166 pour les pays, donc
table d'alias curée plutôt qu'un lookup contre une lib externe. Couvre les
noms de langue en anglais, français, allemand, espagnol, italien, et les
codes ISO 639-1 courants -- pas seulement les langues déjà vues en base,
puisque de nouveaux CV peuvent introduire des langues absentes du jeu de
données actuel.
"""

import unicodedata


def _strip_accents(text: str) -> str:
    """Remove diacritics for accent-insensitive matching (e.g. 'Français' ~ 'Francais')."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _normalize_key(raw: str) -> str:
    return _strip_accents(raw.strip().lower())


_LANGUAGE_ALIASES: dict[str, str] = {
    # English
    "english": "English", "anglais": "English", "englisch": "English",
    "ingles": "English", "inglese": "English", "en": "English",

    # French
    "french": "French", "francais": "French", "franzosisch": "French",
    "frances": "French", "francese": "French", "fr": "French",

    # German
    "german": "German", "allemand": "German", "deutsch": "German",
    "aleman": "German", "tedesco": "German", "de": "German",

    # Spanish
    "spanish": "Spanish", "espagnol": "Spanish", "spanisch": "Spanish",
    "espanol": "Spanish", "spagnolo": "Spanish", "es": "Spanish",

    # Arabic
    "arabic": "Arabic", "arabe": "Arabic", "arabisch": "Arabic",
    "arabo": "Arabic", "ar": "Arabic",

    # Italian
    "italian": "Italian", "italien": "Italian", "italienisch": "Italian",
    "italiano": "Italian", "it": "Italian",

    # Portuguese
    "portuguese": "Portuguese", "portugais": "Portuguese",
    "portugiesisch": "Portuguese", "portugues": "Portuguese",
    "portoghese": "Portuguese", "pt": "Portuguese",

    # Russian
    "russian": "Russian", "russe": "Russian", "russisch": "Russian",
    "ruso": "Russian", "russo": "Russian", "ru": "Russian",

    # Chinese
    "chinese": "Chinese", "chinois": "Chinese", "chinesisch": "Chinese",
    "chino": "Chinese", "cinese": "Chinese", "zh": "Chinese",
    "mandarin": "Chinese",

    # Turkish
    "turkish": "Turkish", "turc": "Turkish", "turkisch": "Turkish",
    "turco": "Turkish", "tr": "Turkish",

    # Dutch
    "dutch": "Dutch", "neerlandais": "Dutch", "niederlandisch": "Dutch",
    "holandes": "Dutch", "olandese": "Dutch", "nl": "Dutch",
}


def normalize_language(raw: str) -> str | None:
    """
    Return the canonical (English) name for a raw language string, or None
    if it can't be confidently resolved. Accent- and case-insensitive.
    """
    if not raw or not raw.strip():
        return None

    key = _normalize_key(raw)
    return _LANGUAGE_ALIASES.get(key)