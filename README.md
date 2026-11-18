# Gemini Support Agent

An MVP customer-support assistant built with FastAPI, React, SQLite, and the official Google GenAI Python SDK.

## MVP capabilities

- Upload `.txt`, `.md`, and text-based `.pdf` knowledge-base documents
- Paragraph-aware chunking with overlap
- Gemini embeddings stored in a local SQLite-backed vector store
- Grounded Gemini answers with source citations
- Conversation history and follow-up questions
- Safe fallback when the knowledge base does not contain enough information

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
cd ..
uvicorn backend.app.main:app --reload --port 8000
```

Set `GEMINI_API_KEY` in `backend/.env` before starting the server.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and proxies API calls to the backend.

The API key stays server-side. The local vector store is intentionally simple for the MVP and can later be replaced by pgvector or ChromaDB without changing the API contract.

The code is separated into three top-level areas: `backend/` contains the HTTP API and persistence layer, `services/` contains Gemini, ingestion, and RAG logic, and `frontend/` contains the React client.

Demo accounts:

- `admin` / `admin123`
- `customer` / `customer123`

The admin and agent views are intended for portfolio demonstration. Change these credentials before sharing a public demo.
