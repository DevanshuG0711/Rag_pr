# Codebase Intelligence Engine

A production-oriented FastAPI system that transforms source files into searchable structural knowledge using AST parsing, vector retrieval, hybrid ranking, and call graph reasoning.

## Problem Statement

Traditional RAG systems treat code as plain text. This loses important structure such as function boundaries, line ranges, and call relationships, which are critical for answering engineering questions like:

- Which functions are involved in a flow?
- Where is a behavior implemented?
- What does a function depend on?

## Solution Overview

This project upgrades basic RAG into a Codebase Intelligence Engine by combining:

- AST-based chunking for Python files using tree-sitter
- Rich metadata extraction per chunk (function/class name, file, line range)
- Call graph extraction for function relationships
- Embeddings + Qdrant vector storage for semantic retrieval
- Hybrid search with Semantic + BM25 + RRF fusion
- Context building optimized for code understanding
- Flow-aware reasoning for dependency and call-path style queries
- Local answer generation by default, with optional LLM support

## Architecture

Step-by-step pipeline:

1. File Ingestion
- Upload TXT, PDF, or PY files through the ingest API.

2. Parsing and Chunking
- Python files are parsed with tree-sitter and split by function/class nodes.
- Non-code files use configurable text chunking with overlap.

3. Metadata and Call Graph Extraction
- For AST chunks, capture symbol name, type, file name, and line boundaries.
- Extract function-to-function call relationships.

4. Embedding Generation
- Generate vector embeddings for each chunk using sentence-transformers.

5. Vector Persistence
- Store vectors and payload metadata in Qdrant.

6. Hybrid Retrieval
- Run semantic retrieval from Qdrant.
- Run BM25 keyword ranking on candidate chunk text.
- Fuse both rankings using Reciprocal Rank Fusion (RRF).

7. Context Builder
- Build structured context with chunk numbering, file references, and code blocks.

8. Flow Reasoning Layer
- For flow/dependency queries, append derived call-flow relationships to context.

9. Answer Generation
- Prefer OpenAI generation when configured.
- Automatically fall back to robust local answer generation when LLM is unavailable.

## Features

- AST chunking for Python functions and classes
- Line-aware metadata extraction for precise grounding
- Call graph extraction and flow explanation support
- Embeddings with sentence-transformers
- Qdrant local, memory, and Docker modes
- Hybrid retrieval (Semantic + BM25 + RRF)
- Query-type aware retrieval depth
- Structured context formatting for better answer quality
- Local-first generation with optional LLM upgrade path

## Tech Stack

- Backend: FastAPI, Uvicorn, Pydantic
- Parsing: tree-sitter, tree-sitter-python
- Embeddings: sentence-transformers (all-MiniLM-L6-v2)
- Vector Database: Qdrant
- Document Parsing: pypdf
- Optional LLM: OpenAI API

## How It Works

Detailed execution flow:

1. Upload and Parse
- The ingest endpoint receives a file and routes logic by file extension.
- Python code is parsed into AST nodes (function_definition and class_definition).

2. Build Chunks and Metadata
- Each chunk stores:
  - chunk text
  - symbol name
  - symbol type (function/class)
  - file name
  - start and end lines
  - called functions for that symbol

3. Extract Call Graph
- A call graph map is generated as:
- function_name -> [called_function_1, called_function_2, ...]

4. Embed and Store
- Chunks are embedded and upserted into Qdrant with payload fields like file_name, chunk_index, and chunk_text.

5. Retrieve with Hybrid Search
- Semantic ranking returns nearest chunks by vector similarity.
- BM25 scores lexical relevance over retrieved chunk text.
- RRF merges both rankings into a single robust top-k list.

6. Build Context
- The system formats retrieved chunks into a deterministic context block:
- chunk id, file name, line info, and code.

7. Flow Query Enrichment
- If query intent contains terms such as flow, call, called by, or dependency:
- Additional Flow section is injected, generated from retrieved chunk call relationships.

8. Generate Answer
- If OPENAI_API_KEY is set, OpenAI response generation is used.
- Otherwise, local generation returns:
  - flow explanation for flow queries
  - keyword-grounded local summary for general queries

## Example Queries and Outputs

Example 1: Flow reasoning

Query:

~~~text
which function is called by login
~~~

Output:

~~~text
Flow Explanation:
login calls validate_user, log_event
validate_user calls db_check
~~~

Example 2: Code understanding

~~~text
How is user validation implemented?
~~~

Expected behavior:

- Retrieves relevant function chunks
- Includes file and line-grounded context
- Returns local or LLM-generated concise explanation

## Setup Instructions

1. Create and activate virtual environment

~~~bash
python3 -m venv .venv
source .venv/bin/activate
~~~

2. Install dependencies

~~~bash
pip install -r requirements.txt
~~~

3. Configure environment (optional)

~~~bash
cp .env.example .env
~~~

Optional variables:

- QDRANT_MODE=local | memory | docker
- QDRANT_URL=http://127.0.0.1:6333 (required for docker mode)
- OPENAI_API_KEY=your_api_key
- OPENAI_MODEL=gpt-4o-mini

4. Run the API

~~~bash
uvicorn app.main:app --reload --port 8000
~~~

5. Verify service

~~~bash
curl http://127.0.0.1:8000/health
~~~

6. Ingest code/document

~~~bash
curl -X POST "http://127.0.0.1:8000/api/ingest?chunk_size=120&overlap=20" \
  -F "file=@/absolute/path/to/file.py"
~~~

7. Run search

~~~bash
curl "http://127.0.0.1:8000/api/search?query=login%20flow&top_k=5"
~~~

8. Run full query pipeline

~~~bash
curl -X POST "http://127.0.0.1:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"which function is called by login","top_k":3}'
~~~

## Future Improvements

- Cross-file and class-method call graph resolution
- Language-agnostic AST adapters (JavaScript, Java, Go)
- Re-ranking with code-specialized cross-encoders
- Dependency graph and import graph integration
- Incremental indexing for large monorepos
- Evaluation suite with retrieval and answer quality metrics
- UI dashboard for exploration of code flows and evidence chunks