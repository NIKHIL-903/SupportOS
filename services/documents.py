import io
import re
import uuid
from datetime import UTC, datetime

from fastapi import UploadFile
from pypdf import PdfReader

from backend.app.database import get_db, serialize_embedding
from services.gemini import GeminiService

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def extract_text(filename: str, raw_bytes: bytes) -> str:
    extension = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension == ".pdf":
        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    return raw_bytes.decode("utf-8", errors="replace")


def chunk_text(text: str, target_words: int = 180, overlap_words: int = 35) -> list[str]:
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for paragraph in paragraphs:
        words = paragraph.split()
        if current and current_words + len(words) > target_words:
            chunks.append(" ".join(current))
            current = " ".join(current).split()[-overlap_words:]
            current_words = len(current)
        current.extend(words)
        current_words += len(words)
    if current:
        chunks.append(" ".join(current))
    return chunks


async def ingest_document(upload: UploadFile, gemini: GeminiService) -> dict[str, object]:
    filename = upload.filename or "uploaded-document"
    extension = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only .txt, .md, and text-based .pdf files are supported")
    raw_bytes = await upload.read()
    if not raw_bytes:
        raise ValueError("The uploaded document is empty")
    text = extract_text(filename, raw_bytes).strip()
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No extractable text was found in the document")
    embeddings = gemini.embed(chunks)
    if len(embeddings) != len(chunks):
        raise RuntimeError("The embedding service returned an incomplete result")
    document_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    with get_db() as db:
        db.execute("INSERT INTO documents (id, filename, content_type, chunk_count, created_at) VALUES (?, ?, ?, ?, ?)", (document_id, filename, upload.content_type, len(chunks), created_at))
        db.executemany("INSERT INTO chunks (id, document_id, chunk_index, content, embedding) VALUES (?, ?, ?, ?, ?)", [(str(uuid.uuid4()), document_id, index, content, serialize_embedding(vector)) for index, (content, vector) in enumerate(zip(chunks, embeddings, strict=True))])
    return {"id": document_id, "filename": filename, "chunk_count": len(chunks), "created_at": created_at}
