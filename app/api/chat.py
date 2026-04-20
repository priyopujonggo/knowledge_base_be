from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.chat import Chat
from app.services.rag import generate_answer

router = APIRouter()

class ChatRequest(BaseModel):
    document_id: int
    message: str

class ChatResponse(BaseModel):
    answer: str
    chat_id: int

@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validasi dokumen milik user
    result = await db.execute(
        select(Document).where(
            Document.id == request.document_id,
            Document.owner_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")

    if not document.content:
        raise HTTPException(status_code=400, detail="Dokumen belum diproses")

    # Ambil atau buat chat session
    result = await db.execute(
        select(Chat).where(Chat.document_id == request.document_id)
    )
    chat = result.scalar_one_or_none()

    if not chat:
        chat = Chat(document_id=request.document_id, messages=[])
        db.add(chat)
        await db.commit()
        await db.refresh(chat)

    # Generate jawaban
    answer = await generate_answer(
        query=request.message,
        document_id=request.document_id,
        chat_history=chat.messages,
        db=db,
    )

    # Update chat history
    messages = list(chat.messages)
    messages.append({"role": "user", "content": request.message})
    messages.append({"role": "assistant", "content": answer})
    chat.messages = messages
    await db.commit()

    return {"answer": answer, "chat_id": chat.id}

@router.get("/{document_id}/history")
async def get_chat_history(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validasi dokumen
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")

    result = await db.execute(
        select(Chat).where(Chat.document_id == document_id)
    )
    chat = result.scalar_one_or_none()

    return {"messages": chat.messages if chat else []}