:::writing{variant=“standard” id=“83921”}

Codebase Assistant (RAG System)

A Retrieval-Augmented Generation (RAG) system that allows users to query documents (and later codebases) using natural language.

🚀 Features (Phase 0)
	•	Upload PDF/TXT documents
	•	Chunk and embed text
	•	Store embeddings in Qdrant (local vector DB)
	•	Retrieve relevant context
	•	Generate answers using LLM

🏗️ Tech Stack
	•	FastAPI (backend)
	•	Sentence Transformers (embeddings)
	•	Qdrant (vector database)
	•	PyPDF (document parsing)

📁 Project Structure
	•	app/api → API routes
	•	app/services → RAG pipeline
	•	app/models → schemas
	•	app/core → config
	•	data/ → storage


⚙️ Setup
pip install -r requirements.txt
uvicorn app.main:app --reload

📌 Roadmap
	•	Phase 0: Document RAG
	•	AST-based chunking
	•	Hybrid search (BM25 + vector)
	•	Call graph integration
	•	Evaluation (RAGAS)
	•	Frontend (React)
:::


<!-- Minimal FastAPI scaffold for a naive document RAG pipeline.

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
      uvicorn app.main:app --reload --port 8001 -->
