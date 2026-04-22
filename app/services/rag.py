from google import genai
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from app.core.config import settings
from app.services.embeddings import search_similar_chunks

client = genai.Client(api_key=settings.GEMINI_API_KEY)

async def generate_answer(
    query: str,
    document_id: int,
    chat_history: list[dict],
    db: AsyncSession,
) -> str:
    relevant_chunks = await search_similar_chunks(
        query=query,
        document_id=document_id,
        db=db,
        top_k=5
    )

    if not relevant_chunks:
        return "Maaf, saya tidak menemukan informasi yang relevan di dokumen ini."

    context = "\n\n".join([chunk.content for chunk in relevant_chunks])

    history_text = ""
    for msg in chat_history[-6:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

    prompt = f"""Kamu adalah asisten AI yang membantu menjawab pertanyaan berdasarkan dokumen yang diberikan.
Jawab pertanyaan HANYA berdasarkan konteks di bawah ini. Jika jawabannya tidak ada di konteks, katakan dengan jujur bahwa kamu tidak tahu.
Jawab dalam bahasa yang sama dengan pertanyaan user.

KONTEKS DARI DOKUMEN:
{context}

RIWAYAT PERCAKAPAN:
{history_text}

PERTANYAAN: {query}

JAWABAN:"""

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )
    return response.text

async def generate_answer_stream(
    query: str,
    document_id: int,
    chat_history: list[dict],
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Streaming version dari generate_answer"""
    relevant_chunks = await search_similar_chunks(
        query=query,
        document_id=document_id,
        db=db,
        top_k=5
    )

    if not relevant_chunks:
        yield "Maaf, saya tidak menemukan informasi yang relevan di dokumen ini."
        return

    context = "\n\n".join([chunk.content for chunk in relevant_chunks])

    history_text = ""
    for msg in chat_history[-6:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

    prompt = f"""Kamu adalah asisten AI yang membantu menjawab pertanyaan berdasarkan dokumen yang diberikan.
Jawab pertanyaan HANYA berdasarkan konteks di bawah ini. Jika jawabannya tidak ada di konteks, katakan dengan jujur bahwa kamu tidak tahu.
Jawab dalam bahasa yang sama dengan pertanyaan user.

KONTEKS DARI DOKUMEN:
{context}

RIWAYAT PERCAKAPAN:
{history_text}

PERTANYAAN: {query}

JAWABAN:"""

    for chunk in client.models.generate_content_stream(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    ):
        if chunk.text:
            yield chunk.text