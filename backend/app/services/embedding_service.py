from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384

_model = None

def get_model():
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model

def embed(text: str) -> list[float]:
    model = get_model()
    embeddings = list(model.embed([text]))
    return embeddings[0].tolist()