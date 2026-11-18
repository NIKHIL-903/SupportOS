import json
from typing import Any

from google import genai

from backend.app.config import get_settings


class GeminiService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.chat_model = settings.gemini_chat_model
        self.embedding_model = settings.gemini_embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.models.embed_content(model=self.embedding_model, contents=texts)
        return [list(item.values) for item in response.embeddings]

    def answer(self, question: str, context: str, history: list[dict[str, str]]) -> dict[str, Any]:
        history_text = "\n".join(f"{item['role'].upper()}: {item['content']}" for item in history) or "No previous conversation."
        prompt = f"""
You are a careful customer-support assistant.

Rules:
1. Answer only from the KNOWLEDGE BASE CONTEXT below.
2. Do not invent policies, prices, dates, steps, or account-specific facts.
3. If the context does not answer the question, set needs_human to true and say that a support agent should help.
4. Keep the answer concise and actionable.
5. Return ONLY valid JSON with exactly these fields:
   answer: string
   confidence: number between 0 and 1
   needs_human: boolean

CONVERSATION HISTORY:
{history_text}

KNOWLEDGE BASE CONTEXT:
{context}

<CUSTOMER QUESTION>
{question}
</CUSTOMER QUESTION>
"""
        response = self.client.models.generate_content(model=self.chat_model, contents=prompt, config={"temperature": 0.1, "response_mime_type": "application/json"})
        return self._parse_json(response.text or "")

    @staticmethod
    def _parse_json(raw_text: str) -> dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1]).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini returned an invalid structured response") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Gemini returned an unexpected response shape")
        return parsed
