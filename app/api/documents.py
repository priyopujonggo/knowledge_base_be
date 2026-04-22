import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.document import Document
from app.schemas.document import DocumentResponse, DocumentListResponse
from pypdf import PdfReader
from app.services.embeddings import process_document_embeddings
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks
import io

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/markdown": "md",
}

async def read_file_content(file_path: str, file_type: str) -> str:
    """Extract text content dari file"""
    async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return await f.read()

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validasi file type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type tidak didukung. Gunakan: PDF, TXT, MD"
        )

    # Validasi file size
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File terlalu besar. Maksimal 10MB"
        )

    # Simpan file
    file_type = ALLOWED_TYPES[file.content_type]
    file_name = f"{uuid.uuid4()}.{file_type}"
    user_upload_dir = os.path.join(settings.UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_upload_dir, exist_ok=True)
    file_path = os.path.join(user_upload_dir, file_name)

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Extract content untuk non-PDF dulu (PDF butuh library tambahan)
    text_content = None
    if file_type in ("txt", "md"):
        text_content = content.decode("utf-8", errors="ignore")
    elif file_type == "pdf":
        try:
            pdf = PdfReader(io.BytesIO(content))
            text_content = "\n".join(
                page.extract_text() for page in pdf.pages if page.extract_text()
            )
        except Exception:
            text_content = None

    # Simpan ke database
    document = Document(
        title=file.filename,
        file_path=file_path,
        file_type=file_type,
        content=text_content,
        owner_id=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Proses embedding di background
    if text_content:
        background_tasks.add_task(
            process_embedding_background,
            document.id,
            text_content
        )

    return document

async def process_embedding_background(document_id: int, content: str):
    """Background task untuk proses embedding"""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await process_document_embeddings(document_id, content, db)
        except Exception as e:
            import logging
            logging.error(f"Error processing embeddings for document {document_id}: {e}")

@router.get("/", response_model=DocumentListResponse)
async def get_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Document)
        .where(Document.owner_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    return {"documents": documents, "total": len(documents)}

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    return document

@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")

    # Hapus file fisik
    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    await db.execute(delete(Document).where(Document.id == document_id))
    await db.commit()

    return {"message": "Dokumen berhasil dihapus"}