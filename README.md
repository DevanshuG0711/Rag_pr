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
- [ ] Chunking
- [ ] Embeddings
- [ ] Vector search
- [ ] RAG pipeline