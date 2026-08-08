# file: app/normalize_sections/__init__.py
"""
app/normalize_sections

Package regroupant les normaliseurs de valeurs par section (pays, langues,
et futures sections). Chaque normaliseur vit dans son propre sous-module ;
ce fichier ne fait que ré-exporter les fonctions les plus utilisées pour
garder les imports courts côté appelants.
"""

from app.normalize_sections.normalize_languages import normalize_language
from app.normalize_sections.normalize_countries import normalize_country_name

__all__ = ["normalize_language", "normalize_country_name"]