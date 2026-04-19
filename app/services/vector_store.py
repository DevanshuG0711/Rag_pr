import os
from pathlib import Path
from uuid import NAMESPACE_URL
from uuid import uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import Distance
from qdrant_client.models import FieldCondition
from qdrant_client.models import Filter
from qdrant_client.models import MatchValue
from qdrant_client.models import PointStruct
from qdrant_client.models import VectorParams

COLLECTION_NAME = "documents"
QDRANT_LOCAL_PATH = Path("data/qdrant")

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
	global _client

	if _client is not None:
		return _client

	mode = os.getenv("QDRANT_MODE", "local").lower()

	if mode == "memory":
		_client = QdrantClient(":memory:")
	elif mode == "docker" or mode == "cloud":
		url = os.getenv("QDRANT_URL", "http://localhost:6333")
		api_key = os.getenv("QDRANT_API_KEY")
		_client = QdrantClient(url=url, api_key=api_key)
	else:
		QDRANT_LOCAL_PATH.mkdir(parents=True, exist_ok=True)
		_client = QdrantClient(path=str(QDRANT_LOCAL_PATH))

	return _client


def ensure_collection(vector_size: int, collection_name: str = COLLECTION_NAME) -> None:
	client = get_qdrant_client()

	if client.collection_exists(collection_name=collection_name):
		return

	client.create_collection(
		collection_name=collection_name,
		vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
	)


def store_chunk_embeddings(
	file_name: str,
	chunks: list[str],
	embeddings: list[list[float]],
	chunk_metadata: list[dict[str, object]] | None = None,
	collection_name: str = COLLECTION_NAME,
) -> list[str]:
	if len(chunks) != len(embeddings):
		raise ValueError("chunks and embeddings must have the same length")
	if chunk_metadata is not None and len(chunk_metadata) != len(chunks):
		raise ValueError("chunk_metadata and chunks must have the same length")
	if not embeddings:
		return []

	vector_size = len(embeddings[0])
	ensure_collection(vector_size=vector_size, collection_name=collection_name)

	points: list[PointStruct] = []
	point_ids: list[str] = []

	for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
		point_id = str(uuid5(NAMESPACE_URL, f"{collection_name}:{file_name}:{chunk_index}"))
		point_ids.append(point_id)

		payload = {
			"file_name": file_name,
			"chunk_index": chunk_index,
			"chunk_text": chunk,
		}

		if chunk_metadata is not None:
			meta = chunk_metadata[chunk_index]
			payload.update(
				{
					"name": meta.get("name"),
					"type": meta.get("type"),
					"start_line": meta.get("start_line"),
					"end_line": meta.get("end_line"),
					"docstring": meta.get("docstring") or "",
					"imports": meta.get("imports", []),
				}
			)

		points.append(
			PointStruct(
				id=point_id,
				vector=embedding,
				payload=payload,
			)
		)

	client = get_qdrant_client()
	client.upsert(collection_name=collection_name, points=points, wait=True)

	return point_ids


def search_similar_chunks(
	query_embedding: list[float],
	top_k: int = 5,
	collection_name: str = COLLECTION_NAME,
) -> list[dict[str, object]]:
	if top_k <= 0:
		raise ValueError("top_k must be greater than 0")

	client = get_qdrant_client()
	if not client.collection_exists(collection_name=collection_name):
		raise ValueError("No vectors found yet. Ingest a document first.")

	hits = client.search(
		collection_name=collection_name,
		query_vector=query_embedding,
		limit=top_k,
		with_payload=True,
	)

	results: list[dict[str, object]] = []
	for hit in hits:
		payload = hit.payload or {}
		results.append(
			{
				"id": str(hit.id),
				"score": float(hit.score),
				"file_name": payload.get("file_name"),
				"chunk_index": payload.get("chunk_index"),
				"chunk_text": payload.get("chunk_text"),
				"name": payload.get("name"),
				"type": payload.get("type"),
				"start_line": payload.get("start_line"),
				"end_line": payload.get("end_line"),
				"docstring": payload.get("docstring") or "",
				"imports": payload.get("imports", []),
			}
		)

	return results


def fetch_chunks_by_function_names(
	function_names: list[str],
	file_names: list[str] | None = None,
	collection_name: str = COLLECTION_NAME,
	limit_per_function: int = 10,
) -> list[dict[str, object]]:
	if not function_names:
		return []

	client = get_qdrant_client()
	if not client.collection_exists(collection_name=collection_name):
		return []

	normalized_functions = list(dict.fromkeys(str(name) for name in function_names if str(name).strip()))
	normalized_files = list(dict.fromkeys(str(name) for name in (file_names or []) if str(name).strip()))

	results: list[dict[str, object]] = []
	seen_ids: set[str] = set()

	for function_name in normalized_functions:
		filters = [FieldCondition(key="name", match=MatchValue(value=function_name))]

		if normalized_files:
			for file_name in normalized_files:
				points, _ = client.scroll(
					collection_name=collection_name,
					scroll_filter=Filter(
						must=[
							*filters,
							FieldCondition(key="file_name", match=MatchValue(value=file_name)),
						]
					),
					limit=limit_per_function,
					with_payload=True,
				)

				for point in points:
					point_id = str(point.id)
					if point_id in seen_ids:
						continue
					seen_ids.add(point_id)
					payload = point.payload or {}
					results.append(
						{
							"id": point_id,
							"score": 0.0,
							"file_name": payload.get("file_name"),
							"chunk_index": payload.get("chunk_index"),
							"chunk_text": payload.get("chunk_text"),
							"name": payload.get("name"),
							"type": payload.get("type"),
							"start_line": payload.get("start_line"),
							"end_line": payload.get("end_line"),
							"docstring": payload.get("docstring") or "",
							"imports": payload.get("imports", []),
						}
					)
		else:
			points, _ = client.scroll(
				collection_name=collection_name,
				scroll_filter=Filter(must=filters),
				limit=limit_per_function,
				with_payload=True,
			)

			for point in points:
				point_id = str(point.id)
				if point_id in seen_ids:
					continue
				seen_ids.add(point_id)
				payload = point.payload or {}
				results.append(
					{
						"id": point_id,
						"score": 0.0,
						"file_name": payload.get("file_name"),
						"chunk_index": payload.get("chunk_index"),
						"chunk_text": payload.get("chunk_text"),
						"name": payload.get("name"),
						"type": payload.get("type"),
						"start_line": payload.get("start_line"),
						"end_line": payload.get("end_line"),
						"docstring": payload.get("docstring") or "",
						"imports": payload.get("imports", []),
					}
				)

	return results


def _point_to_result(point: object, score: float = 0.0) -> dict[str, object]:
	payload = getattr(point, "payload", None) or {}
	return {
		"id": str(getattr(point, "id")),
		"score": float(score),
		"file_name": payload.get("file_name"),
		"chunk_index": payload.get("chunk_index"),
		"chunk_text": payload.get("chunk_text"),
		"name": payload.get("name"),
		"type": payload.get("type"),
		"start_line": payload.get("start_line"),
		"end_line": payload.get("end_line"),
		"docstring": payload.get("docstring") or "",
		"imports": payload.get("imports", []),
	}


def fetch_chunks_by_file(
	file_name: str,
	limit: int = 10,
	collection_name: str = COLLECTION_NAME,
) -> list[dict[str, object]]:
	if not file_name.strip() or limit <= 0:
		return []

	client = get_qdrant_client()
	if not client.collection_exists(collection_name=collection_name):
		return []

	points, _ = client.scroll(
		collection_name=collection_name,
		scroll_filter=Filter(
			must=[
				FieldCondition(key="file_name", match=MatchValue(value=file_name)),
			]
		),
		limit=limit,
		with_payload=True,
	)

	results = [_point_to_result(point) for point in points]
	results.sort(key=lambda item: int(item.get("chunk_index") or 0))
	return results


def fetch_all_chunks_by_file(
	file_name: str,
	collection_name: str = COLLECTION_NAME,
) -> list[dict[str, object]]:
	if not file_name.strip():
		return []

	client = get_qdrant_client()
	if not client.collection_exists(collection_name=collection_name):
		return []

	all_points: list[object] = []
	offset = None

	while True:
		points, offset = client.scroll(
			collection_name=collection_name,
			scroll_filter=Filter(
				must=[
					FieldCondition(key="file_name", match=MatchValue(value=file_name)),
				]
			),
			limit=256,
			with_payload=True,
			offset=offset,
		)

		if not points:
			break

		all_points.extend(points)
		if offset is None:
			break

	results: list[dict[str, object]] = []

	for point in all_points:
		payload = (getattr(point, "payload", None) or {})
		metadata: dict[str, object] = {}

		for key in ("name", "type", "start_line", "end_line", "docstring", "imports"):
			value = payload.get(key)
			if value is None:
				continue
			if key == "docstring" and not value:
				continue
			if key == "imports" and not value:
				continue
			metadata[key] = value

		results.append(
			{
				"id": str(getattr(point, "id")),
				"score": 0.0,
				"file_name": payload.get("file_name"),
				"chunk_text": payload.get("chunk_text"),
				"chunk_index": payload.get("chunk_index"),
				"metadata": metadata,
			}
		)

	results.sort(key=lambda item: int(item.get("chunk_index") or 0))
	return results


def search_similar_chunks_by_file(
	query_embedding: list[float],
	file_name: str,
	top_k: int = 5,
	collection_name: str = COLLECTION_NAME,
) -> list[dict[str, object]]:
	if top_k <= 0:
		raise ValueError("top_k must be greater than 0")
	if not file_name.strip():
		return []

	client = get_qdrant_client()
	if not client.collection_exists(collection_name=collection_name):
		return []

	hits = client.search(
		collection_name=collection_name,
		query_vector=query_embedding,
		query_filter=Filter(
			must=[
				FieldCondition(key="file_name", match=MatchValue(value=file_name)),
			]
		),
		limit=top_k,
		with_payload=True,
	)

	results: list[dict[str, object]] = []
	for hit in hits:
		results.append(
			{
				"id": str(hit.id),
				"score": float(hit.score),
				"file_name": (hit.payload or {}).get("file_name"),
				"chunk_index": (hit.payload or {}).get("chunk_index"),
				"chunk_text": (hit.payload or {}).get("chunk_text"),
				"name": (hit.payload or {}).get("name"),
				"type": (hit.payload or {}).get("type"),
				"start_line": (hit.payload or {}).get("start_line"),
				"end_line": (hit.payload or {}).get("end_line"),
				"docstring": (hit.payload or {}).get("docstring") or "",
				"imports": (hit.payload or {}).get("imports", []),
			}
		)

	return results
