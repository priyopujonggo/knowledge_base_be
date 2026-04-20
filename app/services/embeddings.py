from google import genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from app.core.config import settings
from app.models.embedding import DocumentChunk

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

async def generate_embedding(text: str) -> list[float]:
    result = client.models.embed_content(
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=text,
    )
    return result.embeddings[0].values

async def process_document_embeddings(
    document_id: int,
    content: str,
    db: AsyncSession
) -> None:
    # Hapus chunks lama kalau ada
    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )

    chunks = chunk_text(content)

    for index, chunk in enumerate(chunks):
        embedding = await generate_embedding(chunk)
        doc_chunk = DocumentChunk(
            document_id=document_id,
            content=chunk,
            embedding=embedding,
            chunk_index=index,
        )
        db.add(doc_chunk)

    await db.commit()

async def search_similar_chunks(
    query: str,
    document_id: int,
    db: AsyncSession,
    top_k: int = 5
) -> list[DocumentChunk]:
    result = client.models.embed_content(
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=query,
    )
    query_embedding = result.embeddings[0].values

    from sqlalchemy import select
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return result.scalars().all()