from pathlib import Path
import subprocess
import tempfile

from fastapi import APIRouter
from fastapi import File
from fastapi import HTTPException
from fastapi import Query
from fastapi import UploadFile

from app.services.chunking import chunk_text
from app.services.embeddings import DEFAULT_EMBEDDING_MODEL
from app.services.embeddings import embedding_dimension
from app.services.embeddings import generate_embeddings
from app.services.ingest import extract_code_chunks
from app.services.ingest import extract_text
from app.services.ingest import extract_python_chunks_and_graph
from app.services.call_graph_store import upsert_call_graph
from app.models.schemas import QueryRequest
from app.models.schemas import QueryResponse
from app.services.rag import run_rag_pipeline
from app.services.vector_store import COLLECTION_NAME
from app.services.vector_store import search_similar_chunks
from app.services.vector_store import store_chunk_embeddings

router = APIRouter(prefix="/api")
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SUPPORTED_REPO_EXTENSIONS = {".py", ".js", ".ts", ".go"}


@router.post("/ingest")
async def ingest_document(
	file: UploadFile = File(...),
	chunk_size: int = Query(default=500, ge=1),
	overlap: int = Query(default=50, ge=0),
) -> dict[str, object]:
	file_bytes = await file.read()

	if not file_bytes:
		raise HTTPException(status_code=400, detail="Empty file uploaded")

	file_name = file.filename or "uploaded_file"
	file_path = UPLOAD_DIR / file_name
	file_path.write_bytes(file_bytes)

	try:
		text = extract_text(file_name=file_name, file_bytes=file_bytes)
		chunk_metadata: list[dict[str, object]] = []
		call_graph: dict[str, list[str]] = {}
		lowered = file_name.lower()

		if lowered.endswith(".py"):
			chunks, chunk_metadata, call_graph = extract_python_chunks_and_graph(
				code=text,
				file_name=file_name,
			)
		elif lowered.endswith((".js", ".ts", ".go")):
			chunks, chunk_metadata = extract_code_chunks(
				code=text,
				file_name=file_name,
			)
			if not chunks:
				chunks = chunk_text(text=text, chunk_size=chunk_size, overlap=overlap)
		else:
			chunks = chunk_text(text=text, chunk_size=chunk_size, overlap=overlap)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc

	try:
		embeddings = generate_embeddings(chunks=chunks)
	except Exception as exc:
		raise HTTPException(status_code=500, detail="Failed to generate embeddings") from exc

	call_graph_rows_upserted = 0
	if call_graph:
		print("CALL GRAPH:", call_graph)
		try:
			print("before upsert_call_graph")
			call_graph_rows_upserted = upsert_call_graph(file_name=file_name, call_graph=call_graph)
			print("after upsert_call_graph")
		except Exception as exc:
			raise HTTPException(status_code=500, detail="Failed to store call graph") from exc

	try:
		point_ids = store_chunk_embeddings(
			file_name=file_name,
			chunks=chunks,
			embeddings=embeddings,
			chunk_metadata=chunk_metadata if chunk_metadata else None,
		)
	except Exception as exc:
		raise HTTPException(status_code=500, detail="Failed to store vectors") from exc

	return {
		"filename": file_name,
		"characters": len(text),
		"chunk_size": chunk_size,
		"overlap": overlap,
		"chunk_count": len(chunks),
		"chunks": chunks,
		"chunk_metadata": chunk_metadata,
		"call_graph": call_graph,
		"embedding_model": DEFAULT_EMBEDDING_MODEL,
		"embedding_dimension": embedding_dimension(),
		"embedding_count": len(embeddings),
		"embeddings": embeddings,
		"collection": COLLECTION_NAME,
		"stored_count": len(point_ids),
		"point_ids": point_ids,
		"call_graph_rows_upserted": call_graph_rows_upserted,
		"text": text,
	}


@router.post("/index_repo")
def index_repository(payload: dict[str, str]) -> dict[str, str]:
	repo_url = str(payload.get("repo_url") or "").strip()
	if not repo_url:
		raise HTTPException(status_code=400, detail="repo_url must not be empty")
	if not repo_url.startswith(("http://", "https://")):
		raise HTTPException(status_code=400, detail="Invalid repository URL")

	try:
		with tempfile.TemporaryDirectory(prefix="repo_index_") as tmp_dir:
			repo_dir = Path(tmp_dir) / "repo"
			clone_result = subprocess.run(
				["git", "clone", "--depth", "1", repo_url, str(repo_dir)],
				capture_output=True,
				text=True,
				check=False,
			)

			if clone_result.returncode != 0:
				error_text = (clone_result.stderr or clone_result.stdout or "").strip()
				raise HTTPException(
					status_code=400,
					detail=f"Failed to clone repository: {error_text or 'git clone failed'}",
				)

			source_files = [
				path
				for path in repo_dir.rglob("*")
				if path.is_file() and path.suffix.lower() in SUPPORTED_REPO_EXTENSIONS
			]

			for file_path in source_files:
				relative_name = str(file_path.relative_to(repo_dir))
				try:
					file_bytes = file_path.read_bytes()
					try:
						text = file_bytes.decode("utf-8")
					except UnicodeDecodeError:
						text = file_bytes.decode("latin-1")
				except Exception as exc:
					raise HTTPException(
						status_code=500,
						detail=f"Failed to read file during indexing: {relative_name}",
					) from exc

				chunk_metadata: list[dict[str, object]] = []
				call_graph: dict[str, list[str]] = {}
				lowered = file_path.suffix.lower()

				if lowered == ".py":
					chunks, chunk_metadata, call_graph = extract_python_chunks_and_graph(
						code=text,
						file_name=relative_name,
					)
				else:
					chunks, chunk_metadata = extract_code_chunks(
						code=text,
						file_name=relative_name,
					)
					if not chunks:
						chunks = chunk_text(text=text, chunk_size=500, overlap=50)

				if not chunks:
					continue

				try:
					embeddings = generate_embeddings(chunks=chunks)
				except Exception as exc:
					raise HTTPException(
						status_code=500,
						detail=f"Failed to generate embeddings for {relative_name}",
					) from exc

				if call_graph:
					try:
						upsert_call_graph(file_name=relative_name, call_graph=call_graph)
					except Exception as exc:
						raise HTTPException(
							status_code=500,
							detail=f"Failed to store call graph for {relative_name}",
						) from exc

				try:
					store_chunk_embeddings(
						file_name=relative_name,
						chunks=chunks,
						embeddings=embeddings,
						chunk_metadata=chunk_metadata if chunk_metadata else None,
					)
				except Exception as exc:
					raise HTTPException(
						status_code=500,
						detail=f"Failed to store vectors for {relative_name}",
					) from exc
	except HTTPException:
		raise
	except Exception as exc:
		raise HTTPException(status_code=500, detail="Repository indexing failed") from exc

	return {"message": "Repository indexed successfully"}


@router.get("/search")
def search_chunks(query: str, top_k: int = Query(default=5, ge=1)) -> dict[str, object]:
	if not query.strip():
		raise HTTPException(status_code=400, detail="query must not be empty")

	try:
		query_embedding = generate_embeddings(chunks=[query])[0]
		results = search_similar_chunks(query_embedding=query_embedding, top_k=top_k)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=500, detail="Failed to search vectors") from exc

	return {
		"query": query,
		"top_k": top_k,
		"collection": COLLECTION_NAME,
		"results": results,
	}



@router.post("/query", response_model=QueryResponse)
def query_rag(payload: QueryRequest) -> QueryResponse:
	if not payload.query.strip():
		raise HTTPException(status_code=400, detail="query must not be empty")

	try:
		answer, retrieved_chunks = run_rag_pipeline(
			query=payload.query,
			top_k=payload.top_k,
		)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=500, detail="Failed to run RAG query") from exc

	return QueryResponse(
		query=payload.query,
		answer=answer,
		retrieved_chunks=retrieved_chunks,
	)
