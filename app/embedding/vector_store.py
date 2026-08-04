
import chromadb
from chromadb.config import Settings
from app.config import CHROMA_PERSIST_PATH, CHROMA_COLLECTION_NAME


class VectorStore:
    """
    Wrapper around a local ChromaDB collection for CV chunk indexing and search.
    """

    def __init__(self, persist_path: str = CHROMA_PERSIST_PATH, collection_name: str = CHROMA_COLLECTION_NAME):
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )


    def delete_candidate_chunks(self, candidate_id: str, version_number: int = None) -> None:
        """
        Delete all chunks for a candidate (optionally scoped to one version) before re-indexing,
        to avoid leaving orphaned chunks from a previous chunking configuration (e.g. different
        part_index counts after a max_tokens change).
        """
        conditions = [{"candidate_id": candidate_id}]
        if version_number is not None:
            conditions.append({"version_number": version_number})
        where_filter = conditions[0] if len(conditions) == 1 else {"$and": conditions}

        self.collection.delete(where=where_filter)    

    def index_chunks(self, chunks: list[dict]) -> None:
        """
        Upsert a list of embedded chunks (output of embedder.embed_chunks) into the collection.
        Each chunk must already have "text", "metadata", and "embedding" keys.
        """
        if not chunks:
            return

        ids = [self._build_id(chunk["metadata"]) for chunk in chunks]
        documents = [chunk["text"] for chunk in chunks]
        embeddings = [chunk["embedding"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(self, query_embedding: list[float], top_k: int = 5, candidate_id: str = None) -> dict:
        """
        Search the collection with a precomputed query embedding.
        If candidate_id is provided, restrict the search to that candidate's chunks (Pass B).
        Otherwise, search across all candidates (Pass A).
        """
        where_filter = {"candidate_id": candidate_id} if candidate_id else None

        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
        )
    
    def search_section(
    self,
    query_embedding: list[float],
    chunk_types: str | list[str],
    candidate_id: str = None,
    version_number: int = None,  # NEW — temporary filter to test single-version search
    distance_threshold: float = 0.4,
    min_results: int = 1,
    max_results: int = 5,
    ) -> list[dict]:
        """
        Search the best matching chunks of a given chunk_type.
        ...
        """
        if isinstance(chunk_types, str):
            chunk_types = [chunk_types]

        type_condition = (
            {"chunk_type": chunk_types[0]} if len(chunk_types) == 1
            else {"chunk_type": {"$in": chunk_types}}
        )

        conditions = [type_condition]
        if candidate_id:
            conditions.append({"candidate_id": candidate_id})
        if version_number is not None:
            conditions.append({"version_number": version_number})
        where_filter = conditions[0] if len(conditions) == 1 else {"$and": conditions}

        pool_size = max(max_results * 3, min_results * 3)

        raw = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=pool_size,
            where=where_filter,
        )

        combined = [
            {"id": raw["ids"][0][i], "distance": raw["distances"][0][i],
            "metadata": raw["metadatas"][0][i], "text": raw["documents"][0][i]}
            for i in range(len(raw["ids"][0]))
        ]
        combined.sort(key=lambda x: x["distance"])

        passing = [r for r in combined if r["distance"] <= distance_threshold]

        if len(passing) < min_results:
            return combined[:min_results]

        return passing[:max_results]
    
    def search_multiple_sections(
        self,
        query_embedding: list[float],
        chunk_types: list[str],
        candidate_id: str = None,
        distance_threshold: float = 0.3,
        min_results: int = 1,
        max_results: int = 1,
    ) -> list[dict]:
        """
        Run one independent search_section call per chunk_type, guaranteeing
        coverage of every requested type (unlike passing a list directly to
        search_section, which merges them into a single ranked search).
        """
        all_results = []
        for chunk_type in chunk_types:
            results = self.search_section(
                query_embedding,
                chunk_types=chunk_type,
                candidate_id=candidate_id,
                distance_threshold=distance_threshold,
                min_results=min_results,
                max_results=max_results,
            )
            all_results.extend(results)
        return all_results

    @staticmethod
    def _build_id(metadata: dict) -> str:
        """Build a unique, stable chunk ID from its metadata."""
        base = f"{metadata['candidate_id']}_v{metadata['version_number']}_{metadata['chunk_type']}"

        if metadata["chunk_type"] == "experience":
            return f"{base}_{metadata['experience_index']}_{metadata['part_index']}"
        elif metadata["chunk_type"] == "project":
            return f"{base}_{metadata['project_index']}_{metadata['part_index']}"

        return f"{base}_{metadata['part_index']}"