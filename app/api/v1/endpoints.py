import time
from datetime import timedelta, datetime, timezone

import psutil
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text


from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.schemas.metrics import DashboardResponse

from app.services.monitor import MonitorService
from app.core.security import create_access_token, verify_password, create_refresh_token, get_current_access_payload, get_current_refresh_payload
from typing import Optional
router = APIRouter()
monitor_service = MonitorService()

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
# Эндпоинт для логина (получения токена)
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token_data = {"sub": user.username, "role": user.role}
    token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    return {
        "access_token": token,
        "refresh_token":refresh_token,
        "token_type": "bearer",
        "expires_in": timedelta(microseconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES)}

# Обновление токена
@router.post("/refresh")
async def refresh(payload: dict = Depends(get_current_refresh_payload)):
    user_id = payload.get("sub")
    new_access = create_access_token(data={"sub": user_id, "role": payload.get("role")})
    new_refresh = create_refresh_token(data={"sub": user_id})
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer"
    }

@router.post("/logout")
async def logout(refresh_token: str = Form(...)):
    return {"message": "Logged out successfully"}

@router.get("/healthcheck")
async def healthcheck(db: AsyncSession = Depends(get_db)):
    start_time = time.perf_counter()
    server_time = datetime.now(timezone.utc)
    db_latency = 0
    db_stat = "unknown"
    try:
        await db.execute(text("SELECT 1"))
        db_latency = round((time.perf_counter() - start_time) * 1000, 2)
        db_stat = "connected"
    except Exception as e:
        db_status = f"disconnected: {str(e)}"
    processing_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return {
        "status": "ok" if db_stat == "connected" else "degraded",
        "server_time": server_time,
        "processing_time_ms": processing_time_ms,
        "database": {
            "status": db_stat,
            "latency_ms": db_latency
        }
    }

# Дашборд
@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(user = Depends(get_current_access_payload)):
    return DashboardResponse(
        cpu=monitor_service.get_cpu_info(),
        ram=monitor_service.get_ram_info(),
        disks=monitor_service.get_disks_info(),
        gpus=monitor_service.get_gpu_info()
    )

# Процессы
@router.get("/processes")
async def get_processes(name: Optional[str] = None,
    user: Optional[str] = None,
    token_payload = Depends(get_current_access_payload)):
    return monitor_service.get_processes(name_filter=name, user_filter=user)

async def get_current_admin(user = Depends(get_current_access_payload)):
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Action requires admin privileges")
    return user

# Убить процесс
@router.post("/process/{pid}/kill")
@router.post("/process/{pid}/kill")
async def kill_process(pid: int, user=Depends(get_current_admin)):
    try:
        if monitor_service.kill_process(pid):
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Process not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except psutil.AccessDenied:  # Ловим конкретную ошибку psutil
        raise HTTPException(status_code=403, detail="Permission denied (psutil error)")