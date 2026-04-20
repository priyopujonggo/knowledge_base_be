from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.core.deps import get_current_user


router = APIRouter()

# Setup OAuth
config = Config(environ={
    "GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": settings.GOOGLE_CLIENT_SECRET,
    "GITHUB_CLIENT_ID": settings.GITHUB_CLIENT_ID,
    "GITHUB_CLIENT_SECRET": settings.GITHUB_CLIENT_SECRET,
})

oauth = OAuth(config)

oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="github",
    client_id=settings.GITHUB_CLIENT_ID,
    client_secret=settings.GITHUB_CLIENT_SECRET,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)

# ── Google ──────────────────────────────────────────
@router.get("/google")
async def login_google(request: Request):
    redirect_uri = "http://127.0.0.1:8000/api/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")

    result = await db.execute(select(User).where(User.google_id == str(user_info["sub"])))
    user = result.scalar_one_or_none()

    if not user:
        # Cek apakah email sudah ada
        result = await db.execute(select(User).where(User.email == user_info["email"]))
        user = result.scalar_one_or_none()

        if user:
            # Link google ke existing user
            user.google_id = str(user_info["sub"])
            user.avatar_url = user_info.get("picture")
        else:
            # Buat user baru
            user = User(
                email=user_info["email"],
                username=user_info.get("name"),
                google_id=str(user_info["sub"]),
                avatar_url=user_info.get("picture"),
            )
            db.add(user)

        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?token={access_token}")

# ── GitHub ──────────────────────────────────────────
@router.get("/github")
async def login_github(request: Request):
    redirect_uri = "http://127.0.0.1:8000/api/auth/github/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)

@router.get("/github/callback")
async def github_callback(request: Request, db: AsyncSession = Depends(get_db)):
    token = await oauth.github.authorize_access_token(request)
    resp = await oauth.github.get("user", token=token)
    user_info = resp.json()

    # GitHub tidak selalu return email, ambil dari endpoint emails
    email = user_info.get("email")
    if not email:
        resp_email = await oauth.github.get("user/emails", token=token)
        emails = resp_email.json()
        primary = next((e for e in emails if e.get("primary")), None)
        email = primary["email"] if primary else None

    if not email:
        raise HTTPException(status_code=400, detail="Email tidak ditemukan dari GitHub")

    result = await db.execute(select(User).where(User.github_id == str(user_info["id"])))
    user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            user.github_id = str(user_info["id"])
            user.avatar_url = user_info.get("avatar_url")
        else:
            user = User(
                email=email,
                username=user_info.get("login"),
                github_id=str(user_info["id"]),
                avatar_url=user_info.get("avatar_url"),
            )
            db.add(user)

        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?token={access_token}")

# ── Me ──────────────────────────────────────────────
@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "avatar_url": current_user.avatar_url
    }