import psutil
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.schemas.metrics import DashboardResponse
from app.services import monitor
from app.services.monitor import MonitorService
from app.core.security import verify_token, create_access_token, verify_password
from typing import Optional
router = APIRouter()
monitor_service = MonitorService()

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
# Эндпоинт для логина (получения токена)
@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")


    token = create_access_token(data={"sub": user.username, "role": user.role})

    return {"access_token": token, "token_type": "bearer"}

# Дашборд
@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(user = Depends(verify_token)):
    return DashboardResponse(
        cpu=monitor_service.get_cpu_info(),
        ram=monitor_service.get_ram_info(),
        disks=monitor_service.get_disks_info(),
        gpus=monitor_service.get_gpu_info()
    )

# Процессы
@router.get("/processes")
def get_processes(name: Optional[str] = None,
    user: Optional[str] = None,
    token_payload = Depends(verify_token)):
    return monitor_service.get_processes(name_filter=name, user_filter=user)

async def get_current_admin(user = Depends(verify_token)):
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Action requires admin privileges")
    return user

# Убить процесс
@router.post("/process/{pid}/kill")
@router.post("/process/{pid}/kill")
def kill_process(pid: int, user=Depends(get_current_admin)):
    try:
        if monitor_service.kill_process(pid):
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Process not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except psutil.AccessDenied:  # Ловим конкретную ошибку psutil
        raise HTTPException(status_code=403, detail="Permission denied (psutil error)")