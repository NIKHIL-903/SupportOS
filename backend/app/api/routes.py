import json
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile, Depends

from backend.app.auth import CurrentUser, get_current_user, require_admin, require_staff, login
from backend.app.database import get_db
from backend.app.schemas import (
    AgentReplyRequest,
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    ConversationSummary,
    DocumentResponse,
    EvaluationResult,
    FeedbackRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RetrievalResult,
    Source,
    TicketResponse,
    TicketStatusRequest,
)
from services.documents import ingest_document
from services.gemini import GeminiService
from services.rag import answer_question, conversation_exists, create_conversation, retrieve
from services.support import add_agent_message, list_feedback, list_tickets, save_feedback, update_ticket

router = APIRouter(prefix="/api")
gemini = GeminiService()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/login", response_model=LoginResponse)
def auth_login(request: LoginRequest) -> LoginResponse:
    result = login(request.username, request.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return LoginResponse(**result)


@router.get("/auth/me", response_model=LoginResponse)
def auth_me(user: CurrentUser = Depends(get_current_user)) -> LoginResponse:
    return LoginResponse(token="", username=user.username, role=user.role)


@router.post("/documents", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), _: CurrentUser = Depends(require_admin)) -> DocumentResponse:
    try:
        result = await ingest_document(file, gemini)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Document processing failed: {exc}") from exc
    return DocumentResponse(**result)


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(_: CurrentUser = Depends(require_staff)) -> list[DocumentResponse]:
    with get_db() as db:
        rows = db.execute("SELECT id, filename, chunk_count, created_at FROM documents ORDER BY created_at DESC").fetchall()
    return [DocumentResponse(**dict(row)) for row in rows]


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, _: CurrentUser = Depends(require_admin)) -> dict[str, str]:
    with get_db() as db:
        cursor = db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}


@router.post("/conversations", response_model=ConversationSummary)
def new_conversation(_: CurrentUser = Depends(get_current_user)) -> ConversationSummary:
    conversation_id = create_conversation()
    with get_db() as db:
        row = db.execute("SELECT id, created_at FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return ConversationSummary(id=row["id"], created_at=datetime.fromisoformat(row["created_at"]))


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def read_conversation(conversation_id: str, _: CurrentUser = Depends(get_current_user)) -> ConversationResponse:
    with get_db() as db:
        conversation = db.execute("SELECT id, created_at FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        rows = db.execute(
            "SELECT role, content, sources, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
    messages = [
        MessageResponse(
            role=row["role"],
            content=row["content"],
            sources=[Source(**source) for source in json.loads(row["sources"])],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]
    return ConversationResponse(
        id=conversation["id"],
        created_at=datetime.fromisoformat(conversation["created_at"]),
        messages=messages,
    )


@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
def send_message(conversation_id: str, request: ChatRequest, _: CurrentUser = Depends(get_current_user)) -> ChatResponse:
    if not conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        result = answer_question(conversation_id, request.message, gemini)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc
    return ChatResponse(conversation_id=conversation_id, **result)


@router.post("/conversations/{conversation_id}/feedback")
def add_feedback(conversation_id: str, request: FeedbackRequest, _: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    with get_db() as db:
        row = db.execute("SELECT id FROM messages WHERE conversation_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1", (conversation_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No assistant message found")
    save_feedback(row["id"], request.rating, request.comment)
    return {"status": "saved"}


@router.get("/tickets", response_model=list[TicketResponse])
def tickets(_: CurrentUser = Depends(require_staff)) -> list[TicketResponse]:
    return [TicketResponse(**ticket) for ticket in list_tickets()]


@router.patch("/tickets/{ticket_id}", response_model=TicketResponse)
def ticket_status(ticket_id: str, request: TicketStatusRequest, _: CurrentUser = Depends(require_staff)) -> TicketResponse:
    ticket = update_ticket(ticket_id, request.status)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketResponse(**ticket)


@router.post("/tickets/{ticket_id}/reply")
def ticket_reply(ticket_id: str, request: AgentReplyRequest, _: CurrentUser = Depends(require_staff)) -> dict[str, object]:
    with get_db() as db:
        ticket = db.execute("SELECT conversation_id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    message_id = add_agent_message(ticket["conversation_id"], request.content)
    return {"message_id": message_id, "status": "sent"}


@router.get("/feedback")
def feedback(_: CurrentUser = Depends(require_staff)) -> list[dict[str, object]]:
    return list_feedback()


@router.post("/retrieval/search", response_model=list[RetrievalResult])
def retrieval_search(request: ChatRequest, _: CurrentUser = Depends(require_staff)) -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id=str(item["chunk_id"]),
            document_id=str(item["document_id"]),
            filename=str(item["filename"]),
            excerpt=str(item["content"])[:500],
            score=round(float(item["score"]), 4),
            vector_score=round(float(item["vector_score"]), 4),
            keyword_score=round(float(item["keyword_score"]), 4),
        )
        for item in retrieve(request.message, gemini)
    ]


@router.post("/evaluation/run", response_model=list[EvaluationResult])
def run_evaluation(_: CurrentUser = Depends(require_staff)) -> list[EvaluationResult]:
    try:
        with open("evaluation/questions.json", encoding="utf-8") as file:
            cases = json.load(file)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation dataset not found")
    results = []
    for case in cases:
        matches = retrieve(case["question"], gemini)
        filenames = list(dict.fromkeys(str(item["filename"]) for item in matches))
        results.append(EvaluationResult(question=case["question"], expected_filename=case["expected_filename"], retrieved_filenames=filenames, passed=case["expected_filename"] in filenames[:3]))
    return results
