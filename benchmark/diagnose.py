"""Script de diagnostic pour comprendre pourquoi le benchmark retourne F1=0."""
import inspect
from app.embedding.embedder import Embedder
from app.embedding.vector_store import VectorStore

store = VectorStore()
embedder = Embedder()

print("=" * 60)
print("DIAGNOSTIC BENCHMARK")
print("=" * 60)

# 1. SIGNATURE de search_section
print("[1] Signature de VectorStore.search_section():")
sig = inspect.signature(store.search_section)
print(f"    {sig}")
for name, param in sig.parameters.items():
    print(f"      - {name} (default={param.default})")

# 2. COMBIEN de chunks dans ChromaDB ?
print("[2] Nombre total de chunks dans ChromaDB:")
try:
    count = store.collection.count()
    print(f"    -> {count} chunks")
except Exception as e:
    print(f"    -> ERREUR: {e}")

# 3. LES CANDIDATS DU BENCHMARK SONT-ILS INDEXES ?
candidates = [
    "abdelkarim ben boubaker",
    "yasmine goubantini",
    "abbes taabouri", 
    "aziz belkhiria",
    "roua klai"
]

print("[3] Presence des candidats dans ChromaDB (filtrage par candidate_id):")
for cand in candidates:
    try:
        # ChromaDB get() avec where filter
        results = store.collection.get(where={"candidate_id": cand})
        n = len(results["ids"]) if results and "ids" in results else 0
        if n > 0:
            types = set(m.get("chunk_type", "?") for m in results.get("metadatas", []))
            print(f"    ✓ {cand}: {n} chunks (types: {types})")
        else:
            print(f"    ✗ {cand}: 0 chunks")
    except Exception as e:
        print(f"    ! {cand}: ERREUR - {e}")

# 4. TEST DE RECHERCHE SIMPLE
print("[4] Test de recherche simple (mission Smart Africa):")
mission_text = "Centre de Donnees Cloud Afrique Schema Directeur"
emb = embedder.model.encode(mission_text).tolist()
print(f"    Embedding genere (dim={len(emb)})")

# 4a. Test avec chunk_type
print("[4a] Avec chunk_type='summary':")
try:
    res = store.search_section(
        query_embedding=emb,
        candidate_id="abdelkarim ben boubaker",
        chunk_type="summary",
        distance_threshold=0.9,
        min_results=1,
        max_results=1
    )
    print(f"         -> {len(res)} resultat(s)")
    if res:
        print(f"            distance={res[0].get('distance')}")
        print(f"            text={res[0].get('text','')[:100]}...")
except Exception as e:
    print(f"         -> ERREUR: {type(e).__name__}: {e}")

# 4b. Test sans chunk_type (si le param s'appelle autrement)
print("[4b] Sans chunk_type (si la methode filtre differemment):")
try:
    # On essaie avec les arguments positionnels ou kwargs generiques
    res = store.search_section(
        query_embedding=emb,
        candidate_id="abdelkarim ben boubaker",
        distance_threshold=0.9,
        min_results=1,
        max_results=1
    )
    print(f"         -> {len(res)} resultat(s)")
    if res:
        print(f"            distance={res[0].get('distance')}")
except Exception as e:
    print(f"         -> ERREUR: {type(e).__name__}: {e}")

# 5. METADONNEES d'un chunk au hasard
print("[5] Exemple de metadonnees dans ChromaDB:")
try:
    sample = store.collection.get(limit=5)
    if sample and sample.get("metadatas") and len(sample["metadatas"]) > 0:
        for i, meta in enumerate(sample["metadatas"][:3]):
            print(f"    Chunk {i+1}: {meta}")
    else:
        print("    -> AUCUN chunk trouve dans ChromaDB!")
except Exception as e:
    print(f"    -> ERREUR: {e}")

print("" + "=" * 60)
print("FIN DU DIAGNOSTIC")
print("=" * 60)