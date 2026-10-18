from collections.abc import Sequence
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from composerai_midi import Music21MidiModel
from composerai_store import LocalProjectStore

from composerai_backend.lead import LeadDeps, run_lead
from composerai_backend.settings import Settings


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    prompt: str
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str


app = FastAPI()


def _history(messages: Sequence[ChatMessage]) -> list[ModelMessage]:
    history: list[ModelMessage] = []
    for message in messages:
        if message.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=message.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=message.content)]))
    return history


@app.post("/api/chat")
async def chat(body: ChatRequest) -> ChatResponse:
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be blank")
    settings = Settings()
    deps = LeadDeps(
        store=LocalProjectStore(settings.project_root),
        midi=Music21MidiModel(),
        project=settings.project_name,
    )
    reply = await run_lead(
        body.prompt,
        deps,
        model=settings.model,
        message_history=_history(body.messages),
    )
    return ChatResponse(reply=reply)
