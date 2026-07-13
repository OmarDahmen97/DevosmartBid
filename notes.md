\# Limitations connues et décisions techniques



\## Déduplication candidats

\- Clé primaire : email si présent et non vide

\- Fallback : `normalized\_name` (nom en minuscule, strip) stocké comme champ séparé — la recherche et le stockage utilisent la même clé normalisée pour éviter les collisions de casse

\- Bug corrigé : chercher directement sur `email: None` fusionnait tous les candidats sans email entre eux (Mongo matche `None` à `None`) — fix : fallback explicite sur nom dès que l'email est absent ou vide, jamais de recherche sur `None`

\- Pour la branche D2C (DM / DT et RC) : ni email ni téléphone disponibles sur la plupart des CV, et le nom extrait par le LLM est parfois réduit à des initiales (ex: "R.G"). Le nom du dossier candidat (fiable dans cette arborescence imposée par l'entreprise) devient la source de vérité prioritaire quand le nom extrait est absent ou trop court (≤3 caractères hors ponctuation)

\- Risque assumé : deux candidats homonymes sans email seront fusionnés à tort. Risque jugé faible sur la branche D2C (noms de dossier généralement uniques en RH), plus élevé sur CV externes génériques

\- Vérification de doublon (même fichier réuploadé) : comparaison sur `raw\_text` exact contre \*\*toutes\*\* les versions existantes d'un candidat, pas seulement la dernière (bug corrigé — comparer seulement à la dernière version ratait les doublons en alternance sur plusieurs fichiers)

\- Optimisation : le check de doublon se fait sur `raw\_text` juste après extraction, avant l'appel LLM — évite un appel API (coût, rate limit) sur un fichier déjà traité



\## Extraction PDF/DOCX/PPTX

\- PDF : texte de flux (`extract\_text`) + tables (`extract\_tables`) concaténés — risque de duplication de contenu si un tableau est aussi capturé par `extract\_text`, accepté (le LLM absorbe la redondance)

\- DOCX : paragraphes + tables extraits séparément puis concaténés (pas de préservation de l'ordre visuel réel du document)

\- PPTX : texte des zones de texte (`has\_text\_frame`) + tables (`has\_table`) — pas de risque de duplication, les deux types de shape sont mutuellement exclusifs

\- OCR non implémenté — CV scannés (image pure) ou attestations/certifications scannées produisent un texte vide avec warning, ou sont ignorés

\- Fichiers de verrouillage Office (`\~$\*.pptx`, `\~$\*.docx`) filtrés explicitement dans le parcours de dossiers — sinon `PermissionError` (fichier verrouillé pendant qu'Office a le vrai fichier ouvert)

\- Bug observé sur CV PPTX : concaténation de texte sans espace entre zones adjacentes (ex: "Master2021" au lieu de "Master 2021") — correction par regex en post-extraction (sépare lettre suivie de 4 chiffres)



\## Structure des sources de données (post-réception des vraies données entreprise)

Trois familles de CV distinctes, traitées séparément :

1\. \*\*D2C (DM, DT et RC)\*\* — template fixe entreprise, PPTX, structure connue à l'avance (nom/summary/formation/langues page 1, compétences page 2, missions détaillées ensuite). Souvent sans email/téléphone, nom parfois abrégé.

2\. \*\*CV Externe / EX-Devoteamers\*\* — pas de template, DOCX/PDF, variance totale de structure et de champs disponibles.

3\. \*\*Extraction cv.docx\*\* — fichier unique de 79 pages contenant plusieurs CV en tableaux + attestations/certifications scannées. Traité à part : nécessite une segmentation en CV individuels avant extraction, différent du reste du pipeline. Non traité pour l'instant.



Décision : le format du fichier et son origine (D2C vs externe) n'influencent jamais la structure de `CVSchema` — seulement (1) quel extracteur de texte utiliser, (2) comment résoudre l'identité du candidat, (3) éventuellement quel prompt LLM utiliser (voir plus bas). Le schema cible reste stable, la variance de source est absorbée en amont.



\## Prompts LLM

\- Un prompt générique pour les CV sans structure prévisible (CV externes)

\- Un prompt spécifique prévu pour le template D2C (structure connue à l'avance) — objectif : réduire la variance de sortie du LLM en lui donnant la structure exacte plutôt que de la lui faire deviner. Pas encore implémenté.

\- Le prompt doit lister le schéma JSON complet explicitement (pas de `...` en placeholder) — un prompt vague avec des placeholders a produit une dégradation de qualité sur d'autres champs que celui qu'on cherchait à corriger



\## LLM extraction (Groq vs local)

\- Rate limit gratuit Groq : 100k tokens/jour — peut bloquer un batch de test complet, observé en conditions réelles

\- Champs optionnels forcés par field\_validator (None -> \[] pour les listes, coercion de type pour years int->str) car le LLM ne respecte pas toujours le schéma, y compris sur Groq 70B

\- Testé Qwen2.5:7b en local (Ollama) : moins fiable que Groq 70B pour respecter le schéma (champs `null` sur des champs obligatoires, clés renommées comme `year` au lieu de `years`, `languages` retourné comme liste de strings au lieu d'objets). Utilisable seulement avec normalisation renforcée en amont de la validation.

\- Arbitrage Groq (API) vs Qwen (local) : Groq plus fiable techniquement, Qwen local seul argument réel est la confidentialité RGPD sur données candidats réelles — à confirmer avec l'encadrant de stage avant de trancher définitivement

\- Décision schema : tous les champs sont `Optional` sauf `CVSchema.name` (seul identifiant réellement nécessaire), suite à l'accumulation d'erreurs de validation sur des champs jugés à tort obligatoires (company, dates, description, level, technologies, responsibilities...)



\## Versioning

\- Détection de doublon : comparaison sur `raw\_text` exact (pas de fuzzy matching) contre toutes les versions existantes

\- Un même CV réuploadé = pas de nouvelle version, retour `duplicate` avec le numéro de version existant

\- Diff (M4) : comparaison au niveau champ (pas juste présence/absence) pour `experience` et `projects` — détecte une description modifiée sur un même poste/projet, pas seulement ajout/suppression. Comparaison insensible à la casse, casse originale préservée dans le résultat retourné.

\- Limitation connue : mêmes CV en plusieurs langues (FR/EN) ou plusieurs formats (PDF/DOCX) traités comme versions distinctes, pas fusionnés — choix assumé pour préserver la traçabilité de ce qui a été reçu, au prix d'un diff qui affichera un faux signal de changement massif entre une version et sa traduction

