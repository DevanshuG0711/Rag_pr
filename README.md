<!-- # Codebase Intelligence Engine

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
- UI dashboard for exploration of code flows and evidence chunks -->




![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Qdrant](https://img.shields.io/badge/VectorDB-Qdrant-red)
![Status](https://img.shields.io/badge/Status-Active-success)
![License](https://img.shields.io/badge/License-MIT-yellow)






# 🚀 Codebase Intelligence Engine

A production-grade system that transforms raw codebases into queryable, structured intelligence using AST parsing, hybrid retrieval, and call graph reasoning.

---

## 🧠 Problem Statement

Understanding large codebases is hard.

Traditional approaches:
- Treat code as plain text ❌
- Lose structure (functions, classes, relationships)
- Cannot answer:
  - "What is the flow of this feature?"
  - "Which functions are involved?"
  - "What does this function depend on?"

---

## 💡 Solution

This project evolves RAG into a Codebase Intelligence Engine that:

- Understands code structure (AST)
- Captures function relationships (call graph)
- Retrieves using hybrid ranking (semantic + keyword)
- Performs flow-aware reasoning

---

## 📁 Project Structure

app/
 ├── api/            # Routes
 ├── services/       # Core logic (RAG, search, call graph)
 ├── models/         # Schemas
 ├── main.py         # Entry point

## 🏗️ Architecture

Code Input  
↓  
AST Parsing (tree-sitter)  
↓  
Chunking (function/class level)  
↓  
Metadata + Call Graph Extraction  
↓  
Embeddings (sentence-transformers)  
↓  
Vector DB (Qdrant)  
↓  
Hybrid Retrieval (Semantic + BM25 + RRF)  
↓  
Context Builder  
↓  
Flow Reasoning Layer  
↓  
Answer Generator (Local / LLM)  
↓  
Final Output  

---

## 🔥 Key Features

### Structural Understanding
- AST-based chunking (functions/classes)
- Line-aware metadata (start/end lines)
- Symbol-level indexing

### Call Graph Reasoning
- Extracts function dependencies
- Answers flow-based queries
- Enables code reasoning, not just search

### Hybrid Retrieval Engine
- Semantic search (embeddings)
- BM25 keyword ranking
- Reciprocal Rank Fusion (RRF)

Result: high-precision + high-recall retrieval

### Context-Aware Answering
- Structured context formatting
- Flow injection for dependency queries
- Local fallback + optional LLM

---

## ⚙️ Tech Stack

Backend: FastAPI, Uvicorn  
Parsing: tree-sitter  
Embeddings: sentence-transformers  
Vector DB: Qdrant  
Ranking: BM25 + RRF  
Docs: pypdf  
Optional LLM: OpenAI  

---

## 🔌 API Endpoints

- POST /api/ingest → Upload file and index
- GET /api/search → Retrieve relevant chunks
- POST /api/query → Full RAG pipeline (final answer)

## ⚡ How It Works (Deep Dive)

1. Parsing & Chunking  
Python files → AST nodes  
Each function/class becomes a chunk  

2. Metadata Extraction  
Each chunk stores:
- function/class name  
- file name  
- line range  
- called functions  

3. Call Graph Extraction  
login → validate_user, log_event  
validate_user → db_check  

4. Embedding & Storage  
Convert chunks → vectors  
Store in Qdrant with metadata  

5. Hybrid Retrieval  
Semantic similarity (meaning)  
BM25 (keywords)  
RRF (ranking fusion)  

6. Context Building  

=== Context ===  

[Chunk 1]  
File: test.py  
Lines: 1–5  
Code: def login()...  

7. Flow Reasoning Layer 🔥  
Triggered for queries like:
flow, calls, dependency  

Adds:  

Flow:  
login calls validate_user, log_event  
validate_user calls db_check  

8. Answer Generation  
OpenAI (if available)  
Otherwise local intelligent summarization  

---

## 📌 Example

Query:

which function is called by login

Output:

Flow Explanation:
login calls validate_user, log_event
validate_user calls db_check

---

## 🚀 Setup

python3 -m venv .venv  
source .venv/bin/activate  
pip install -r requirements.txt  

---

## Run

uvicorn app.main:app --reload --port 8000  

---

## Test

curl -X POST http://127.0.0.1:8000/api/query \
-H "Content-Type: application/json" \
-d '{"query":"login flow","top_k":3}'

---

## 🔮 Future Improvements

- Cross-file call graph resolution  
- Multi-language support (JS, Java, Go)  
- Graph DB (Neo4j) integration  
- Repo-level indexing  
- UI for visualizing code flows  
- Evaluation metrics (precision/recall)  

---

## 🧠 What Makes This Special

This is not just a RAG system.

It combines:
- Structure (AST)
- Search (Hybrid retrieval)
- Reasoning (Call graph)

Result:
A system that can understand code, not just search it.