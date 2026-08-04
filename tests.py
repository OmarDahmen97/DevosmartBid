import spacy
from app.extraction.pdf_extractor import extract_text_from_pdf

# Charger le modèle
nlp = spacy.load("en_cv_info_extr")

# Exemple de CV
resume_text = extract_text_from_pdf(r"C:\Users\mehdi\OneDrive\Bureau\Papiers\CV pour stage d'ete 4eme_translated_eng.pdf")

# Analyse du CV
doc = nlp(resume_text)

# Affichage des entités détectées
print("\n=== Extracted Entities ===\n")

for ent in doc.ents:
    print(f"{ent.label_:20} -> {ent.text}")

print(f"\nTotal entities found: {len(doc.ents)}")