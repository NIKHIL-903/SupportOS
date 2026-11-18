import json
import math
import re
import uuid
from datetime import UTC, datetime

from backend.app.config import get_settings
from backend.app.database import deserialize_embedding, get_db
from services.gemini import GeminiService
from services.support import create_ticket, get_ticket_for_conversation


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def keyword_similarity(question: str, content: str) -> float:
    query_terms = set(re.findall(r"[a-z0-9_-]+", question.lower()))
    content_terms = set(re.findall(r"[a-z0-9_-]+", content.lower()))
    if not query_terms:
        return 0.0
    return len(query_terms & content_terms) / len(query_terms)


def retrieve(question: str, gemini: GeminiService) -> list[dict[str, object]]:
    query_vector = gemini.embed([question])[0]
    with get_db() as db:
        rows = db.execute("SELECT c.id, c.document_id, c.content, c.embedding, d.filename FROM chunks c JOIN documents d ON d.id = c.document_id").fetchall()
    scored = []
    for row in rows:
        vector_score = max(0.0, cosine_similarity(query_vector, deserialize_embedding(row["embedding"])))
        keyword_score = keyword_similarity(question, row["content"])
        scored.append({
            "chunk_id": row["id"],
            "document_id": row["document_id"],
            "filename": row["filename"],
            "content": row["content"],
            "vector_score": vector_score,
            "keyword_score": keyword_score,
            "score": (vector_score * 0.7) + (keyword_score * 0.3),
        })
    return sorted(scored, key=lambda item: float(item["score"]), reverse=True)[: get_settings().top_k]


def create_conversation() -> str:
    conversation_id = str(uuid.uuid4())
    with get_db() as db:
        db.execute("INSERT INTO conversations (id, created_at) VALUES (?, ?)", (conversation_id, datetime.now(UTC).isoformat()))
    return conversation_id


def conversation_exists(conversation_id: str) -> bool:
    with get_db() as db:
        return db.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone() is not None


def get_history(conversation_id: str) -> list[dict[str, str]]:
    with get_db() as db:
        rows = db.execute("SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?", (conversation_id, get_settings().max_history_messages)).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def save_message(conversation_id: str, role: str, content: str, sources: list[dict[str, object]] | None = None) -> int:
    with get_db() as db:
        cursor = db.execute("INSERT INTO messages (conversation_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?)", (conversation_id, role, content, json.dumps(sources or []), datetime.now(UTC).isoformat()))
        return int(cursor.lastrowid)


def answer_question(conversation_id: str, question: str, gemini: GeminiService) -> dict[str, object]:
    settings = get_settings()
    matches = retrieve(question, gemini)
    strong_matches = [item for item in matches if float(item["score"]) >= settings.min_retrieval_score]
    if not strong_matches:
        answer = "I could not find enough information in the knowledge base to answer that reliably. A support agent should help with this request."
        save_message(conversation_id, "user", question)
        message_id = save_message(conversation_id, "assistant", answer)
        ticket = get_ticket_for_conversation(conversation_id) or create_ticket(conversation_id, question[:80])
        return {"message_id": message_id, "ticket_id": ticket["id"], "answer": answer, "sources": [], "needs_human": True, "confidence": 0.0}
    context = "\n\n".join(f"SOURCE {index}: {item['filename']}\n{item['content']}" for index, item in enumerate(strong_matches, start=1))
    generated = gemini.answer(question, context, get_history(conversation_id))
    confidence = max(0.0, min(1.0, float(generated.get("confidence", 0.0))))
    needs_human = bool(generated.get("needs_human", False)) or confidence < 0.55
    answer = str(generated.get("answer", "I need a support agent to help with that."))
    sources = [{"document_id": item["document_id"], "filename": item["filename"], "chunk_id": item["chunk_id"], "excerpt": str(item["content"])[:280], "score": round(float(item["score"]), 4)} for item in strong_matches]
    if needs_human and "support agent" not in answer.lower():
        answer += "\n\nA support agent should review this request before you rely on it."
    save_message(conversation_id, "user", question)
    message_id = save_message(conversation_id, "assistant", answer, sources)
    ticket_id = None
    if needs_human:
        ticket = get_ticket_for_conversation(conversation_id) or create_ticket(conversation_id, question[:80])
        ticket_id = str(ticket["id"])
    return {"message_id": message_id, "ticket_id": ticket_id, "answer": answer, "sources": sources, "needs_human": needs_human, "confidence": confidence}
