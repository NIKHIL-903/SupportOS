import uuid
from datetime import UTC, datetime

from backend.app.database import get_db


def create_ticket(conversation_id: str, subject: str) -> dict[str, object]:
    ticket_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    with get_db() as db:
        db.execute("INSERT INTO tickets (id, conversation_id, subject, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", (ticket_id, conversation_id, subject, now, now))
        row = db.execute("SELECT id, conversation_id, status, subject, created_at, updated_at FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return dict(row)


def get_ticket_for_conversation(conversation_id: str) -> dict[str, object] | None:
    with get_db() as db:
        row = db.execute("SELECT id, conversation_id, status, subject, created_at, updated_at FROM tickets WHERE conversation_id = ? AND status != 'resolved' ORDER BY created_at DESC LIMIT 1", (conversation_id,)).fetchone()
    return dict(row) if row else None


def list_tickets() -> list[dict[str, object]]:
    with get_db() as db:
        rows = db.execute("SELECT id, conversation_id, status, subject, created_at, updated_at FROM tickets ORDER BY updated_at DESC").fetchall()
    return [dict(row) for row in rows]


def update_ticket(ticket_id: str, status: str) -> dict[str, object] | None:
    now = datetime.now(UTC).isoformat()
    with get_db() as db:
        db.execute("UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?", (status, now, ticket_id))
        row = db.execute("SELECT id, conversation_id, status, subject, created_at, updated_at FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return dict(row) if row else None


def save_feedback(message_id: int, rating: int, comment: str | None) -> None:
    with get_db() as db:
        db.execute("INSERT INTO feedback (message_id, rating, comment, created_at) VALUES (?, ?, ?, ?)", (message_id, rating, comment, datetime.now(UTC).isoformat()))


def list_feedback() -> list[dict[str, object]]:
    with get_db() as db:
        rows = db.execute("SELECT f.id, f.message_id, f.rating, f.comment, f.created_at, m.content FROM feedback f JOIN messages m ON m.id = f.message_id ORDER BY f.created_at DESC").fetchall()
    return [dict(row) for row in rows]


def add_agent_message(conversation_id: str, content: str) -> int:
    with get_db() as db:
        cursor = db.execute("INSERT INTO messages (conversation_id, role, content, sources, created_at) VALUES (?, 'assistant', ?, '[]', ?)", (conversation_id, content, datetime.now(UTC).isoformat()))
        db.execute("UPDATE tickets SET status = 'in_progress', updated_at = ? WHERE conversation_id = ? AND status != 'resolved'", (datetime.now(UTC).isoformat(), conversation_id))
        return int(cursor.lastrowid)
