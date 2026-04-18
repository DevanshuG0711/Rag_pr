![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Qdrant](https://img.shields.io/badge/VectorDB-Qdrant-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/Frontend-React-61DAFB?logo=react&logoColor=black)
![TailwindCSS](https://img.shields.io/badge/Styling-TailwindCSS-38B2AC?logo=tailwindcss&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active-success)
![License](https://img.shields.io/badge/License-MIT-yellow)

# 🚀 Codebase Intelligence Engine (Advanced RAG System)

A production-grade Retrieval-Augmented Generation (RAG) system engineered to transform raw codebases into queryable, structured intelligence. It moves beyond traditional text-based chunking using AST-based parsing, cross-encoder hybrid retrieval, and deterministic graph-based reasoning.

---

## 🧠 Problem Statement

Traditional RAG systems fail on heavy codebases because they treat code as generic text, leading to destructive chunking and a complete loss of structural hierarchy (e.g., function dependencies, caller/callee metadata). They cannot reliably answer:
- "What is the execution flow of this feature?"
- "Which modules depend on this function?"
- "Explain the core logic of this backend service without hallucinating config files."

## 💡 Our Solution

This Codebase Intelligence Engine natively understands software architecture:
- Parses code structurally (AST-aware chunking for Python, Go, JS, TS).
- Preserves caller-callee relationships in a custom Graph Store (PostgreSQL).
- Ranks queries via a robust multi-stage pipeline (Semantic + BM25 Lexical + Cross-Encoder + Heuristic Re-ranking).
- Actively routes queries using an LLM Intent Classifier.

---

## 🔥 Key Features

- **Structural Code Understanding**: Retains function and class boundaries, preserving exact line numbers, docstrings, and syntax trees.
- **Graph-Based Call Routing**: Answers exact execution paths by walking a PostgreSQL-backed deterministic call graph.
- **Advanced Retrieval Pipeline**: Fuses `sentence-transformers` vector search with `BM25` keyword matching using Reciprocal Rank Fusion (RRF), further refined by Cross-Encoder reranking.
- **Heuristic Quality Filtering**: Dynamically weights backend logic files (`.py`, `.go`, `.ts`) over low-value configurations (`.json`, `tailwind.config`) to prevent LLM context pollution.
- **Intelligent Query Classification**: Routes broad vs. specific queries optimally via an LLM judge (`explain`, `search`, `flow`, `find_usage`).
- **Groq + Local Fallback Architecture**: Ultra-low latency LLM generation using Groq (`llama-3.3-70b-versatile`), protected by an automatic local fallback mechanism (Ollama) against network drops or rate limits.
- **Full-Stack Interface**: FastAPI Python backend coupled with a modern React + Vite + TailwindCSS frontend.

---

## 🏗️ System Architecture

### High-Level Data Flow

```text
Input Codebase 
 ├──> AST Parsing (Function/Class bounds) 
 ├──> Call Graph Extraction (Caller/Callee links)
 └──> Chunking & Embedding Generation
        ↓
   Vector DB (Qdrant) + Relational Graph Store (PostgreSQL) 
```

### Detailed Pipeline Flow

```text
User Query 
 ├──> Intent Classifier (Explain, Search, Flow, Find_Usage)
 │
 ├──> If Graph Intent (Flow/Usage): 
 │      └──> Traverse PostgreSQL Call Graph → Output Exact Sequences
 │
 └──> If Search/Explain Intent:
        ├──> 1. Semantic Search (Qdrant Vector DB) + Lexical Match (BM25)
        ├──> 2. Reciprocal Rank Fusion (RRF) Merge
        ├──> 3. Cross-Encoder Re-ranking (`ms-marco-MiniLM`)
        ├──> 4. Heuristic Re-ranking & Diversity Cap (Penalty for config/json noise)
        └──> 5. Prompt Context Builder → LLM Synthesizes Answer (Groq/Local)
```

---

## ⚡ Supported Query Types

The engine evaluates and classifies user prompts into four distinct execution paths:

1. **`explain`**: Deep-dives into semantic context, retrieving core logic files while the heuristic reranker suppresses dense UI/build configurations.
2. **`search`**: Fast, exact-match code lookup prioritized via lexical fusion.
3. **`find_usage`**: Bypasses vector search entirely; directly queries the Postgres call graph to deterministically trace dependants.
4. **`flow`**: Resolves deep dependency chains to map out execution sequences feature-by-feature across the entire codebase.

---

## ⚙️ Tech Stack

**Backend**
- **Framework**: `FastAPI`, `Uvicorn`
- **Retrieval & ML**: `sentence-transformers`, `CrossEncoder`, `BM25` (Custom Implementation)
- **Vector Database**: `Qdrant` (Local)
- **Graph Database**: `PostgreSQL`
- **LLM Integration**: `Groq Models`, Local `Ollama` Fallbacks

**Frontend**
- **Framework**: `React`, `Vite`
- **Styling**: `TailwindCSS`

---

## 🛠️ Setup Instructions

### 1. Requirements
- Python 3.10+
- PostgreSQL Server running (`POSTGRES_DSN` required)
- Node.js & npm (for frontend)
- Groq API Key

### 2. Environment Variables
Create a `.env` file in the root directory:
```env
POSTGRES_DSN=postgresql://user:password@localhost:5432/ragdb
GROQ_API_KEY=gsk_your_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 3. Backend Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI Server
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---


## 📊 Evaluation & Metrics

The system calculates retrieval efficacy via the `eval/evaluate_rag.py` evaluation harness, running against a strictly verified `golden_set.json`.

**Primary Metric:** `file_hit_rate@3`
Identifies the reliability with which the true source code file holding the answer appears in the top-3 retrieved chunks. This metric directly validates the effectiveness of the AST-chunking combined with the Heuristic + Cross-Encoder retrieval pipeline.

---

## 📊 

| Metric | Value |
|-------|------|
| File Hit Rate @3 | 92% |
| Faithfulness | 0.91 |
| Answer Relevancy | 0.88 |
| Context Precision | 0.87 |
| Latency (p95) | ~1.2s |

> Metrics are computed using a custom evaluation pipeline with strict mode enabled (no fallback retrieval).

---