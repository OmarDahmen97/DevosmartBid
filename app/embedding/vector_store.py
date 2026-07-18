
import chromadb
from chromadb.config import Settings


class VectorStore:
    """
    Wrapper around a local ChromaDB collection for CV chunk indexing and search.
    """

    def __init__(self, persist_path: str = "./chroma_data", collection_name: str = "cv_chunks"):
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

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

    @staticmethod
    def _build_id(metadata: dict) -> str:
        """Build a unique, stable chunk ID from its metadata."""
        base = f"{metadata['candidate_id']}_v{metadata['version_number']}_{metadata['chunk_type']}"

        if metadata["chunk_type"] == "experience":
            return f"{base}_{metadata['experience_index']}_{metadata['part_index']}"
        elif metadata["chunk_type"] == "project":
            return f"{base}_{metadata['project_index']}_{metadata['part_index']}"

        return f"{base}_{metadata['part_index']}"