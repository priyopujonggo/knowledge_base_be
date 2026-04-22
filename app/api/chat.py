from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.chat import Chat
from app.services.rag import generate_answer, generate_answer_stream

router = APIRouter()

class ChatRequest(BaseModel):
    document_id: int
    message: str

class ChatResponse(BaseModel):
    answer: str
    chat_id: int

async def get_or_create_chat(document_id: int, db: AsyncSession) -> Chat:
    result = await db.execute(
        select(Chat).where(Chat.document_id == document_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        chat = Chat(document_id=document_id, messages=[])
        db.add(chat)
        await db.commit()
        await db.refresh(chat)
    return chat

async def validate_document(document_id: int, user_id: int, db: AsyncSession) -> Document:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == user_id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    if not document.content:
        raise HTTPException(status_code=400, detail="Dokumen belum diproses")
    return document

@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_document(request.document_id, current_user.id, db)
    chat = await get_or_create_chat(request.document_id, db)

    answer = await generate_answer(
        query=request.message,
        document_id=request.document_id,
        chat_history=chat.messages,
        db=db,
    )

    messages = list(chat.messages)
    messages.append({"role": "user", "content": request.message})
    messages.append({"role": "assistant", "content": answer})
    chat.messages = messages
    await db.commit()

    return {"answer": answer, "chat_id": chat.id}

@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Streaming chat endpoint — response muncul kata per kata"""
    await validate_document(request.document_id, current_user.id, db)
    chat = await get_or_create_chat(request.document_id, db)

    full_answer = []

    async def stream_generator():
        async for chunk in generate_answer_stream(
            query=request.message,
            document_id=request.document_id,
            chat_history=chat.messages,
            db=db,
        ):
            full_answer.append(chunk)
            yield f"data: {chunk}\n\n"

        # Simpan ke history setelah streaming selesai
        messages = list(chat.messages)
        messages.append({"role": "user", "content": request.message})
        messages.append({"role": "assistant", "content": "".join(full_answer)})
        chat.messages = messages
        await db.commit()
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

@router.get("/{document_id}/history")
async def get_chat_history(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_document(document_id, current_user.id, db)
    result = await db.execute(
        select(Chat).where(Chat.document_id == document_id)
    )
    chat = result.scalar_one_or_none()
    return {"messages": chat.messages if chat else []}

@router.delete("/{document_id}/history")
async def clear_chat_history(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await validate_document(document_id, current_user.id, db)
    result = await db.execute(
        select(Chat).where(Chat.document_id == document_id)
    )
    chat = result.scalar_one_or_none()
    if chat:
        chat.messages = []
        await db.commit()
    return {"message": "Chat history berhasil dihapus"}