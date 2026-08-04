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
        Takes a list of chunks (output of build_chunks_for_version) and returns
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