"""Mock embeddings model — would download from HF at every cold start.

The HF download is the slow step. This deployment lacks a model_cache block,
so weights are pulled fresh from huggingface.co on every replica boot.
"""

from sentence_transformers import SentenceTransformer

MODEL_REPO = "sentence-transformers/all-mpnet-base-v2"  # ~420MB


class Model:
    def load(self):
        self._model = SentenceTransformer(MODEL_REPO)

    def predict(self, model_input: dict) -> dict:
        text = model_input.get("text", "")
        emb = self._model.encode(text).tolist()
        return {"embedding": emb}
