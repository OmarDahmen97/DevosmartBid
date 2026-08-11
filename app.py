# file: cv-platform-ui-test/app.py
"""
Front de test minimal (Streamlit) pour valider le flux complet de l'API
CV Platform, sans investir dans un vrai front React tout de suite.

Prerequis :
    pip install streamlit requests

Lancement (l'API FastAPI doit tourner en parallele sur :8000) :
    streamlit run app.py
"""

import json
import requests
import streamlit as st
import os

API_BASE = os.getenv("BACKEND_URL") or "http://127.0.0.1:8000"

st.set_page_config(page_title="CV Platform - Test", layout="wide")
st.title("CV Platform — Test de flux & Génération CV")

# ---------------------------------------------------------------------------
# Etat partage entre onglets
# ---------------------------------------------------------------------------
if "selected_candidates" not in st.session_state:
    # dict[candidate_id] = {"name": ..., "email": ..., "source": "matching"|"search"}
    st.session_state.selected_candidates = {}

if "shared_mission_text" not in st.session_state:
    st.session_state.shared_mission_text = ""

# Stocke les selections d'experiences/projets personnalisees par candidat
# dict[candidate_id] = {"exp_indices": list[int], "proj_indices": list[int]}
if "candidate_selections" not in st.session_state:
    st.session_state.candidate_selections = {}

# Stocke le dernier CV JSON adapte genere par candidat
if "generated_cvs" not in st.session_state:
    st.session_state.generated_cvs = {}


def add_candidate(candidate_id: str, name: str, email: str, source: str) -> None:
    st.session_state.selected_candidates[candidate_id] = {
        "name": name, "email": email, "source": source,
    }


def remove_candidate(candidate_id: str) -> None:
    st.session_state.selected_candidates.pop(candidate_id, None)
    st.session_state.candidate_selections.pop(candidate_id, None)
    st.session_state.generated_cvs.pop(candidate_id, None)


tab_upload, tab_match, tab_experiences, tab_generate = st.tabs(
    ["1. Upload CV", "2. Matching mission", "3. Expériences candidat", "4. Génération CV final"]
)

# ---------------------------------------------------------------------------
# Onglet 1 -- Upload
# ---------------------------------------------------------------------------
with tab_upload:
    st.subheader("Uploader un ou plusieurs CV")
    uploaded_files = st.file_uploader(
        "Fichiers CV (pdf, docx, pptx)",
        type=["pdf", "docx", "pptx"],
        accept_multiple_files=True,
    )

    if st.button("Envoyer", key="upload_btn"):
        if not uploaded_files:
            st.warning("Sélectionne au moins un fichier.")
        else:
            files_payload = [
                ("files", (f.name, f.getvalue(), f.type)) for f in uploaded_files
            ]
            with st.spinner("Extraction + stockage + merge en cours..."):
                response = requests.post(f"{API_BASE}/cv/upload", files=files_payload)

            if response.status_code == 200:
                results = response.json().get("results", [])
                st.success(f"{len(results)} fichier(s) traité(s).")

                STATUS_LABELS = {
                    "new_candidate": "🆕 Nouveau candidat",
                    "new_version": "➕ Nouvelle version",
                    "duplicate": "🔁 Doublon (déjà en base)",
                }

                for r in results:
                    if "error" in r:
                        st.error(f"**{r['filename']}** — Erreur : {r['error']}")
                        continue

                    status_label = STATUS_LABELS.get(r.get("status"), r.get("status", "?"))

                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{r.get('name', '?')}**  \n`{r['filename']}`")
                            st.caption(f"candidate_id: `{r['candidate_id']}`")
                        with col2:
                            st.markdown(status_label)
                            st.caption(f"version {r.get('version', '?')}")

                        info_cols = st.columns(3)
                        info_cols[0].metric("Email", r.get("email") or "—")
                        info_cols[1].metric("Version", r.get("version", "—"))
                        info_cols[2].metric(
                            "Expériences (après merge)",
                            r.get("experience_count_after_merge", 0),
                        )
            else:
                st.error(f"Erreur {response.status_code}")
                st.text(response.text)

# ---------------------------------------------------------------------------
# Onglet 2 -- Mission matching + selection + recherche complementaire
# ---------------------------------------------------------------------------
with tab_match:
    st.subheader("Rechercher les candidats pertinents pour une mission")
    mission_text = st.text_area(
        "Description de la mission", height=150, key="mission_match",
        value=st.session_state.shared_mission_text,
    )
    st.session_state.shared_mission_text = mission_text

    if st.button("Lancer le matching", key="match_btn"):
        if not mission_text.strip():
            st.warning("Entre une description de mission.")
        else:
            with st.spinner("Scan de tous les candidats en cours (peut prendre du temps)..."):
                response = requests.post(
                    f"{API_BASE}/candidates/match",
                    json={"mission_text": mission_text},
                )

            if response.status_code == 200:
                st.session_state.last_match_results = response.json().get("candidates", [])
            else:
                st.error(f"Erreur {response.status_code}")
                st.text(response.text)

    match_results = st.session_state.get("last_match_results", [])
    if match_results:
        st.markdown(f"**{len(match_results)} candidat(s) trouvé(s) par le matching**")
        for c in match_results:
            cid = c["candidate_id"]
            already_selected = cid in st.session_state.selected_candidates
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"**{c['name']}** — score {c['avg_score']}% — `{cid}`")
            with col2:
                checked = st.checkbox(
                    "Garder", value=already_selected, key=f"match_check_{cid}"
                )
            if checked and not already_selected:
                add_candidate(cid, c["name"], c.get("email"), source="matching")
            elif not checked and already_selected and st.session_state.selected_candidates.get(cid, {}).get("source") == "matching":
                remove_candidate(cid)

    st.divider()

    # -----------------------------------------------------------------
    # Recherche complémentaire
    # -----------------------------------------------------------------
    st.markdown("### Ajouter des candidats non trouvés par le matching")

    search_tab_name, search_tab_country, search_tab_skills = st.tabs(
        ["Par nom", "Par pays", "Par compétence"]
    )

    # --- Recherche par nom ---
    with search_tab_name:
        name_query = st.text_input("Nom du candidat (recherche partielle)", key="search_name_input")
        if st.button("Rechercher", key="search_name_btn"):
            if name_query.strip():
                resp = requests.get(f"{API_BASE}/candidates", params={"name": name_query})
                if resp.status_code == 200:
                    st.session_state.name_search_results = resp.json().get("candidates", [])
                else:
                    st.error(f"Erreur {resp.status_code}")

        for c in st.session_state.get("name_search_results", []):
            cid = c["candidate_id"]
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"{c['name']} — {c.get('email') or '—'} — `{cid}`")
            with col2:
                disabled = cid in st.session_state.selected_candidates
                if st.button("Ajouter", key=f"add_name_{cid}", disabled=disabled):
                    add_candidate(cid, c["name"], c.get("email"), source="search")
                    st.rerun()

    # --- Recherche par pays ---
    with search_tab_country:
        if "country_options" not in st.session_state:
            resp = requests.get(f"{API_BASE}/candidates/options/countries")
            if resp.status_code == 200:
                st.session_state.country_options = resp.json().get("countries", [])
            else:
                st.session_state.country_options = []

        selected_countries = st.multiselect(
            "Pays", options=st.session_state.country_options, key="search_country_select"
        )
        if st.button("Rechercher", key="search_country_btn"):
            if selected_countries:
                resp = requests.post(
                    f"{API_BASE}/candidates/search-advanced",
                    json={"countries": selected_countries, "limit": 50},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.country_search_results = data.get("results", data.get("candidates", []))
                else:
                    st.error(f"Erreur {resp.status_code}")

        for c in st.session_state.get("country_search_results", []):
            cid = c.get("candidate_id") or c.get("_id")
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"{c.get('name', '?')} — {c.get('email') or '—'} — `{cid}`")
            with col2:
                disabled = cid in st.session_state.selected_candidates
                if st.button("Ajouter", key=f"add_country_{cid}", disabled=disabled):
                    add_candidate(cid, c.get("name", "?"), c.get("email"), source="search")
                    st.rerun()

    # --- Recherche par compétence ---
    with search_tab_skills:
        skill_query = st.text_input(
            "Tape le début d'une compétence (ex: pyth, sap...)", key="search_skill_input"
        )

        suggestions = []
        if skill_query.strip():
            resp = requests.get(
                f"{API_BASE}/candidates/suggest/skills",
                params={"q": skill_query, "limit": 10},
            )
            if resp.status_code == 200:
                suggestions = resp.json().get("suggestions", [])

        chosen_skill = None
        if suggestions:
            chosen_skill = st.selectbox("Suggestions", options=suggestions, key="skill_suggest_select")
        elif skill_query.strip():
            st.caption("Aucune suggestion pour cette saisie.")

        if st.button("Rechercher", key="search_skill_btn", disabled=not chosen_skill):
            resp = requests.post(
                f"{API_BASE}/candidates/search-advanced",
                json={"skills": [chosen_skill], "limit": 50},
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.skill_search_results = data.get("results", data.get("candidates", []))
            else:
                st.error(f"Erreur {resp.status_code}")

        for c in st.session_state.get("skill_search_results", []):
            cid = c.get("candidate_id") or c.get("_id")
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"{c.get('name', '?')} — {c.get('email') or '—'} — `{cid}`")
            with col2:
                disabled = cid in st.session_state.selected_candidates
                if st.button("Ajouter", key=f"add_skill_{cid}", disabled=disabled):
                    add_candidate(cid, c.get("name", "?"), c.get("email"), source="search")
                    st.rerun()

    st.divider()

    # -----------------------------------------------------------------
    # Sélection consolidée
    # -----------------------------------------------------------------
    st.markdown(f"### Sélection actuelle ({len(st.session_state.selected_candidates)})")
    if not st.session_state.selected_candidates:
        st.caption("Aucun candidat sélectionné pour l'instant.")
    else:
        for cid, info in list(st.session_state.selected_candidates.items()):
            col1, col2 = st.columns([5, 1])
            with col1:
                source_badge = "🎯 matching" if info["source"] == "matching" else "🔍 recherche"
                st.write(f"{info['name']} — {source_badge} — `{cid}`")
            with col2:
                if st.button("Retirer", key=f"remove_{cid}"):
                    remove_candidate(cid)
                    st.rerun()

# ---------------------------------------------------------------------------
# Onglet 3 -- Sélection des expériences & projets BRUTS (Non réécrits)
# ---------------------------------------------------------------------------
with tab_experiences:
    st.subheader("Sélectionner les expériences/projets à inclure")
    st.caption("ℹ️ Les éléments affichés ci-dessous sont au format original (brut). La réécriture et l'adaptation par LLM se feront uniquement à l'étape 4 pour les éléments cochés.")

    selected = st.session_state.selected_candidates
    if not selected:
        st.info("Aucun candidat sélectionné. Va dans l'onglet 2 pour en choisir.")
    else:
        options = {f"{info['name']} ({cid})": cid for cid, info in selected.items()}
        picked_label = st.selectbox("Candidat", options=list(options.keys()), key="exp_candidate_select")
        candidate_id_input = options[picked_label]

        mission_text_2 = st.text_area(
            "Description de la mission (pour le calcul du score)", height=100, key="mission_exp",
            value=st.session_state.shared_mission_text,
        )
        st.session_state.shared_mission_text = mission_text_2

        if st.button("Charger les expériences", key="exp_btn"):
            if not mission_text_2.strip():
                st.warning("Renseigne la mission.")
            else:
                with st.spinner("Calcul de la similarité en cours..."):
                    response = requests.post(
                        f"{API_BASE}/cv/{candidate_id_input}/experiences-ranked",
                        json={"mission_text": mission_text_2},
                    )

                if response.status_code == 200:
                    st.session_state[f"ranked_{candidate_id_input}"] = response.json()
                else:
                    st.error(f"Erreur {response.status_code}")
                    st.text(response.text)

        ranked_data = st.session_state.get(f"ranked_{candidate_id_input}")
        if ranked_data:
            st.write("---")
            st.markdown("### Expériences")
            selected_exp_indices = []
            for exp in ranked_data.get("experiences", []):
                item = exp["item"]
                idx = exp["experience_index"]
                is_auto = exp.get("auto_selected", False)

                # Ajout explicite du tag "Auto-sélectionnée" si auto_selected est True
                auto_tag = " | 🤖 **[Auto-sélectionnée]**" if is_auto else ""
                label = f"[{exp['score']}%]{auto_tag} **{item.get('title', '?')}** chez {item.get('company', '?')} ({item.get('start_date', '')} - {item.get('end_date', '')})"
                
                chk = st.checkbox(label, value=is_auto, key=f"exp_{candidate_id_input}_{idx}")
                if chk:
                    selected_exp_indices.append(idx)
                
                # Affichage des données brutes (non reformulées)
                if item.get("description"):
                    st.caption(f"📝 *Description originale :* {item['description']}")

            st.markdown("### Projets")
            selected_proj_indices = []
            for proj in ranked_data.get("projects", []):
                item = proj["item"]
                idx = proj["project_index"]
                is_auto = proj.get("auto_selected", False)

                auto_tag = " | 🤖 **[Auto-sélectionné]**" if is_auto else ""
                label = f"[{proj['score']}%]{auto_tag} **{item.get('name', '?')}**"
                
                chk = st.checkbox(label, value=is_auto, key=f"proj_{candidate_id_input}_{idx}")
                if chk:
                    selected_proj_indices.append(idx)
                
                if item.get("description"):
                    st.caption(f"📝 *Description originale :* {item['description']}")

            # Enregistrer la sélection
            st.session_state.candidate_selections[candidate_id_input] = {
                "exp_indices": selected_exp_indices,
                "proj_indices": selected_proj_indices,
            }

            st.success(
                f"Sélection enregistrée pour **{selected[candidate_id_input]['name']}** : "
                f"{len(selected_exp_indices)} expérience(s) et {len(selected_proj_indices)} projet(s)."
            )

# ---------------------------------------------------------------------------
# Onglet 4 -- Génération et Reformulation du CV final (Gemini LLM)
# ---------------------------------------------------------------------------
with tab_generate:
    st.subheader("Génération et adaptation LLM du CV final")

    selected = st.session_state.selected_candidates
    if not selected:
        st.info("Aucun candidat sélectionné. Sélectionne au moins un candidat dans l'onglet 2.")
    else:
        col_cand, col_lang = st.columns([3, 1])
        with col_cand:
            options = {f"{info['name']} ({cid})": cid for cid, info in selected.items()}
            picked_label = st.selectbox("Candidat à générer", options=list(options.keys()), key="gen_candidate_select")
            candidate_id_gen = options[picked_label]
        with col_lang:
            target_lang = st.selectbox("Langue du CV", ["French", "English", "Spanish"], index=0, key="gen_lang_select")

        mission_text_gen = st.text_area(
            "Mission de référence pour la réécriture et le ciblage",
            height=120,
            key="mission_gen",
            value=st.session_state.shared_mission_text,
        )

        user_sel = st.session_state.candidate_selections.get(candidate_id_gen)
        if user_sel:
            st.info(
                f"Utilisation de la sélection personnalisée : {len(user_sel['exp_indices'])} expérience(s), "
                f"{len(user_sel['proj_indices'])} projet(s)."
            )
        else:
            st.caption("Avis : Aucune sélection manuelle dans l'onglet 3. La sélection automatique par pertinence sémantique sera appliquée.")

        if st.button("🚀 Générer et réécrire le CV avec Gemini", key="gen_cv_btn"):
            if not mission_text_gen.strip():
                st.warning("Veuillez renseigner le texte de la mission.")
            else:
                payload = {
                    "mission_text": mission_text_gen,
                    "target_language": target_lang,
                }
                if user_sel:
                    payload["selected_experience_indices"] = user_sel["exp_indices"]
                    payload["selected_project_indices"] = user_sel["proj_indices"]

                with st.spinner("Réécriture et adaptation des expériences sélectionnées via Gemini..."):
                    resp = requests.post(
                        f"{API_BASE}/cv/{candidate_id_gen}/adapted-json",
                        json=payload,
                    )

                if resp.status_code == 200:
                    cv_result = resp.json().get("cv_json", {})
                    st.session_state.generated_cvs[candidate_id_gen] = cv_result
                    st.success("CV généré et reformulé avec succès !")
                else:
                    st.error(f"Erreur {resp.status_code}")
                    st.text(resp.text)

        # Affichage du résultat généré et reformulé
        cv_data = st.session_state.generated_cvs.get(candidate_id_gen)
        if cv_data:
            st.divider()
            cand_name = selected[candidate_id_gen]["name"]
            st.markdown(f"### 📄 CV Adapté & Reformulé — {cand_name}")

            # Bouton de téléchargement du JSON
            json_str = json.dumps(cv_data, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Télécharger le CV (JSON)",
                data=json_str,
                file_name=f"CV_{cand_name.replace(' ', '_')}_adapte.json",
                mime="application/json",
            )

            # Prévisualisation des sections reformulées
            if cv_data.get("summary"):
                st.markdown("#### Résumé")
                st.write(cv_data["summary"])

            if cv_data.get("experience"):
                st.markdown("#### Expériences Professionnelles Reformulées")
                for exp in cv_data["experience"]:
                    with st.expander(f"💼 {exp.get('title', 'Titre non spécifié')} — {exp.get('company', '')}"):
                        st.caption(f"Période: {exp.get('start_date', '')} - {exp.get('end_date', '')} | Lieu: {exp.get('location', '')}")
                        if exp.get("description"):
                            st.write(f"**Description adaptées :** {exp['description']}")
                        if exp.get("responsibilities"):
                            st.write("**Responsabilités adaptées :**")
                            for resp_item in exp["responsibilities"]:
                                st.write(f"- {resp_item}")

            if cv_data.get("projects"):
                st.markdown("#### Projets Reformulés")
                for proj in cv_data["projects"]:
                    with st.expander(f"🚀 {proj.get('name', 'Projet')}"):
                        if proj.get("description"):
                            st.write(proj["description"])

            with st.expander("🔍 Voir le JSON brut"):
                st.json(cv_data)