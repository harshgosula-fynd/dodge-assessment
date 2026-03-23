"""Chat / natural language query endpoint."""

from fastapi import APIRouter

from models.schemas import ChatRequest, ChatResponse
from services.chat_service import handle_chat

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a natural language question about O2C data."""
    result = await handle_chat(request.message)
    return result
