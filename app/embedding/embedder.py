# file: app/embedding/embedder.py

from app.config import EMBEDDING_MODEL_NAME, EMBEDDING_MAX_SEQ_LENGTH, EMBEDDING_BATCH_SIZE
from sentence_transformers import SentenceTransformer


class Embedder:
    """
    Wrapper around the SBERT model. Loaded once at instantiation.
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        self.model = SentenceTransformer(model_name)
        self.model.max_seq_length = EMBEDDING_MAX_SEQ_LENGTH

    def embed_chunks(self, chunks: list[dict]) -> list[dict]:
        """
        Takes a list of chunks (output of build_chunks_for_candidate) and returns
        the same list, each chunk enriched with an "embedding" key (list[float]).
        """
        if not chunks:
            return []

        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.model.encode(
            texts,
            batch_size=EMBEDDING_BATCH_SIZE,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding.tolist()

        return chunks


# ---- process-wide singleton ----
#
# Every module that needs the SBERT model (main_usage, experience_similarity,
# etc.) must go through get_shared_embedder() rather than instantiating its
# own Embedder(). Each module previously rolled its own lazy-singleton, which
# meant the model got loaded twice (once per singleton) the first time both
# code paths were hit in the same process. Centralizing it here guarantees
# exactly one load per process, regardless of which module triggers it first.

_shared_embedder_instance = None


def get_shared_embedder(model_name: str = EMBEDDING_MODEL_NAME) -> Embedder:
    global _shared_embedder_instance
    if _shared_embedder_instance is None:
        print("[loading] SBERT (Embedder)...")
        _shared_embedder_instance = Embedder(model_name)
    return _shared_embedder_instance