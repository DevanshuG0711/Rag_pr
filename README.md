![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Qdrant](https://img.shields.io/badge/VectorDB-Qdrant-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql&logoColor=white)
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

<!-- ## 📁 Project Structure

app/
 ├── api/            # Routes
 ├── services/       # Core logic (RAG, search, call graph)
 ├── models/         # Schemas
 ├── main.py         # Entry point -->

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

### Some more Features
- OpenAI integration
- Local LLM support via Ollama
- Intelligent fallback system
- Flow detection in code

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

## 🔍 Why AST-Based Chunking Beats Naive Chunking

### ❌ Problem with Naive Chunking

Traditional RAG systems split code using fixed-size chunks (e.g., 50 lines).  
This approach treats code as plain text and ignores its structure.

Issues:
- Breaks functions across chunks
- Loses logical boundaries
- Retrieval often returns incomplete or irrelevant code

Example (Naive Chunking):
Chunk 1:
-def login():
-validate_user()

Chunk 2:
-create_session()

Here, the function is split incorrectly, leading to poor understanding.

---

### ✅ Our Approach: AST-Based Chunking

We use **tree-sitter** to parse code into an Abstract Syntax Tree (AST).  
Each function or class is extracted as a complete, self-contained chunk.

Benefits:
- Preserves function/class boundaries
- Maintains structural integrity
- Enables precise and meaningful retrieval

Example (AST Chunking):
def login():
validate_user()
create_session()

---

### 📊 Comparison

| Feature | Naive Chunking | AST Chunking |
|--------|---------------|-------------|
| Structure Awareness | ❌ No | ✅ Yes |
| Function Boundaries | ❌ Broken | ✅ Preserved |
| Retrieval Accuracy | Low | High |
| Code Understanding | Weak | Strong |

---

### 📈 Results

In our evaluation, AST-based chunking significantly improved retrieval accuracy compared to naive chunking.

This demonstrates that understanding code structure is critical for building reliable code intelligence systems.

---

## ✅ Golden Set Evaluation (File Hit Rate@3)


We evaluate retrieval quality using a golden dataset and report **file hit rate@3**.

Latest run:
- total_queries: 15
- hits_at_3: 14
- file_hit_rate@3: **0.9333**

Run it locally:

~~~bash
python eval/evaluate_rag.py
~~~

Notes:
- The evaluator uses `run_rag_pipeline(query)` first.
- If a query path returns no chunks (for example flow/find_usage answer branches), it falls back to retrieval-only chunk fetch for fair file-hit measurement.

---

## ✅ RAGAS Evaluation

For answer-quality evaluation, run the RAGAS script:

~~~bash
python eval/evaluate_ragas.py
~~~

This reports average scores for:
- faithfulness
- answer_relevancy
- context_precision

Optional flags:
- `--limit N` to evaluate only first N queries
- `--top-k N` to pass top-k to `run_rag_pipeline`

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