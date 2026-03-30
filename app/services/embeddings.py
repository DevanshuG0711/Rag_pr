from sentence_transformers import SentenceTransformer

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def get_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL) -> SentenceTransformer:
	global _model

	if _model is None:
		_model = SentenceTransformer(model_name)

	return _model


def generate_embeddings(chunks: list[str], model_name: str = DEFAULT_EMBEDDING_MODEL) -> list[list[float]]:
	if not chunks:
		return []

	model = get_embedding_model(model_name=model_name)
	vectors = model.encode(chunks, normalize_embeddings=True)
	return vectors.tolist()


def embedding_dimension(model_name: str = DEFAULT_EMBEDDING_MODEL) -> int:
	model = get_embedding_model(model_name=model_name)
	return model.get_sentence_embedding_dimension()
