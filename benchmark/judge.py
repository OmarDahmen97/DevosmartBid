# benchmark/judge.py
from typing import List, Dict, Any


def judge_chunk_relevance(
    mission_text: str,
    chunk_text: str,
    chunk_type: str,
    candidate_label: str
) -> bool:
    """
    Juge si un chunk retourné par Chroma est pertinent pour la mission.
    Version naïve (mots-clés) — à remplacer par un LLM judge quand le benchmark grossit.
    """
    mission_lower = mission_text.lower()
    chunk_lower = chunk_text.lower()
    
    # Pour les non-match, tout retour est un faux positif
    if candidate_label == "non_match":
        return False
    
    # Heuristique : au moins 2 mots significatifs communs
    mission_words = set(mission_lower.split())
    chunk_words = set(chunk_lower.split())
    
    stopwords = {
        "le", "la", "de", "et", "un", "une", "pour", "du", "des", "est", "a",
        "the", "and", "of", "to", "in", "for", "on", "with", "as", "by",
        "les", "des", "et", "du", "une", "un", "en", "au", "aux", "ce", "cet",
        "ces", "son", "sa", "ses", "leur", "leurs", "notre", "nos", "votre",
        "vos", "mon", "ma", "mes", "ton", "ta", "tes", "je", "tu", "il", "elle",
        "nous", "vous", "ils", "elles", "me", "te", "se", "lui", "leur", "y",
        "en", "qui", "que", "quoi", "dont", "ou", "est", "sont", "été", "être",
        "avoir", "faire", "plus", "moins", "très", "trop", "peu", "tout", "tous",
        "toute", "toutes", "autre", "autres", "même", "mêmes", "tel", "tels",
        "telle", "telles", "ainsi", "alors", "aussi", "donc", "or", "ni", "car",
        "mais", "si", "que", "quand", "comme", "où", "dont", "ceci", "cela",
        "celui", "celle", "ceux", "celles", "ici", "là", "voici", "voilà",
        "déjà", "encore", "toujours", "jamais", "maintenant", "avant", "après",
        "hier", "aujourd", "demain", "ici", "là", "partout", "ailleurs",
        "chez", "vers", "sous", "sur", "dans", "par", "avec", "sans", "contre",
        "entre", "parmi", "durant", "pendant", "depuis", "jusqu", "après",
        "avant", "derrière", "devant", "près", "loin", "dessus", "dessous",
        "dedans", "dehors", "alentour"
    }
    
    common = mission_words & chunk_words
    common = {w for w in common if w not in stopwords and len(w) > 2}
    
    return len(common) >= 2