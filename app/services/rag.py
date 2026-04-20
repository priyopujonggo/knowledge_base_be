from google import genai
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.services.embeddings import search_similar_chunks

client = genai.Client(api_key=settings.GEMINI_API_KEY)

async def generate_answer(
    query: str,
    document_id: int,
    chat_history: list[dict],
    db: AsyncSession,
) -> str:
    # 1. Ambil chunks yang relevan
    relevant_chunks = await search_similar_chunks(
        query=query,
        document_id=document_id,
        db=db,
        top_k=5
    )

    if not relevant_chunks:
        return "Maaf, saya tidak menemukan informasi yang relevan di dokumen ini."

    # 2. Bangun context dari chunks
    context = "\n\n".join([chunk.content for chunk in relevant_chunks])

    # 3. Bangun chat history string
    history_text = ""
    for msg in chat_history[-6:]:  # ambil 6 pesan terakhir saja
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

    # 4. Bangun prompt
    prompt = f"""Kamu adalah asisten AI yang membantu menjawab pertanyaan berdasarkan dokumen yang diberikan.
Jawab pertanyaan HANYA berdasarkan konteks di bawah ini. Jika jawabannya tidak ada di konteks, katakan dengan jujur bahwa kamu tidak tahu.
Jawab dalam bahasa yang sama dengan pertanyaan user.

KONTEKS DARI DOKUMEN:
{context}

RIWAYAT PERCAKAPAN:
{history_text}

PERTANYAAN: {query}

JAWABAN:"""

    # 5. Generate jawaban
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )

    return response.text