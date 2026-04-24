import os

import google.generativeai as genai

DEFAULT_EMBEDDING_MODEL = "models/embedding-001"

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def get_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL) -> str:
	return model_name


def generate_embeddings(chunks: list[str], model_name: str = DEFAULT_EMBEDDING_MODEL) -> list[list[float]]:
	if not chunks:
		return []

	embeddings: list[list[float]] = []
	for chunk in chunks:
		try:
			response = genai.embed_content(
				model=model_name,
				content=chunk,
			)
			embeddings.append(list(response.get("embedding", [])))
		except Exception:
			embeddings.append([])

	return embeddings


def embedding_dimension(model_name: str = DEFAULT_EMBEDDING_MODEL) -> int:
	try:
		response = genai.embed_content(model=model_name, content="dimension probe")
		embedding = list(response.get("embedding", []))
		return len(embedding)
	except Exception:
		return 0
