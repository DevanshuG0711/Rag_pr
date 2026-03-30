# Phase 0 RAG

Minimal FastAPI scaffold for a naive document RAG pipeline.

## Run

1. Create and activate virtual environment:
   python3 -m venv .venv
   source .venv/bin/activate

2. Install dependencies:
   pip install -r requirements.txt

3. Start server:
   uvicorn app.main:app --reload

   Alternative (also works):
   uvicorn main:app --reload

4. Health check:
   GET http://127.0.0.1:8000/health

5. Root check:
   GET http://127.0.0.1:8000/

## Troubleshooting

- Use `uvicorn`, not `unicorn`.
- If you see "Address already in use", port 8000 is occupied.
   - Either stop the existing process, or run on another port:
      uvicorn app.main:app --reload --port 8001


## Current Status
- [x] FastAPI setup
- [x] Document ingestion (PDF/TXT)
- [x] Chunking
- [x] Embeddings
- [x] Vector storage (Qdrant)
- [x] Basic vector search (top-k)
- [ ] RAG pipeline

## Test Chunking

Use the ingestion endpoint with chunking query params:

curl -X POST "http://127.0.0.1:8000/api/ingest?chunk_size=100&overlap=20" \
   -F "file=@/path/to/file.txt"

Response fields include:
- chunk_size
- overlap
- chunk_count
- chunks

## Test Embeddings

Use the same endpoint. It now generates one embedding per chunk:

curl -X POST "http://127.0.0.1:8000/api/ingest?chunk_size=100&overlap=20" \
   -F "file=@/path/to/file.txt"

Response fields include:
- embedding_model
- embedding_dimension
- embedding_count
- embeddings

Note: the first request may take longer because the sentence-transformers model is downloaded and loaded.

## Qdrant Local Run Options

Default mode is embedded local Qdrant (no Docker needed):
- vectors are stored under `data/qdrant`
- no extra process required

Optional in-memory mode (for quick tests):

export QDRANT_MODE=memory

Optional Docker mode:

docker run -p 6333:6333 -v $(pwd)/data/qdrant:/qdrant/storage qdrant/qdrant
export QDRANT_MODE=docker
export QDRANT_URL=http://127.0.0.1:6333

## Test Vector Store And Search

1. Ingest a file (stores chunks + embeddings in Qdrant):

curl -X POST "http://127.0.0.1:8000/api/ingest?chunk_size=120&overlap=20" \
   -F "file=@/path/to/file.txt"

Check response fields:
- collection
- stored_count
- point_ids

2. Run similarity search (top-k):

curl "http://127.0.0.1:8000/api/search?query=your%20question&top_k=3"

Search response includes:
- score
- file_name
- chunk_index
- chunk_text