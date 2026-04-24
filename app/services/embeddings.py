import os

from google import genai

DEFAULT_EMBEDDING_MODEL = "text-embedding-004"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def get_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL) -> str:
	return model_name


def generate_embeddings(chunks: list[str], model_name: str = DEFAULT_EMBEDDING_MODEL) -> list[list[float]]:
	if not chunks:
		return []

	embeddings: list[list[float]] = []
	for chunk in chunks:
		try:
			response = client.models.embed_content(
				model=model_name,
				contents=chunk,
			)
			embeddings.append(list(response.embeddings[0].values))
		except Exception:
			embeddings.append([])

	return embeddings


def embedding_dimension(model_name: str = DEFAULT_EMBEDDING_MODEL) -> int:
	try:
		response = client.models.embed_content(model=model_name, contents="dimension probe")
		embedding = list(response.embeddings[0].values)
		return len(embedding)
	except Exception:
		return 0
