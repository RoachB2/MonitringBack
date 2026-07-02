from pydantic import BaseModel, Field
from typing import List, Optional

class CpuInfo(BaseModel):
    load_percent: float
    core_count: int
    frequency_mhz: float
    temperature_c: float = 0.0
    used_percent: float = 0.0
    total_gb: float = 0.0

class RamInfo(BaseModel):
    load_percent: float
    used_gb: float
    total_gb: float

class DiskPartitionInfo(BaseModel):
    """Информация о конкретном разделе/томе внутри физического диска"""
    device: str
    mount_point: str
    used_percent: float
    total_gb: float

class DiskInfo(BaseModel):
    """Информация о физическом диске"""
    device: str
    model_name: str  # Основная точка монтирования (первая из списка)
    temperature_c: Optional[float] = 0.0
    used_percent: float
    total_gb: float
    internals: List[DiskPartitionInfo] = []

class GpuInfo(BaseModel):
    name: str
    vendor: str
    load_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    temperature_c: Optional[float] = None
    metrics_available: bool = Field(
        default=False,
        description="True if real metrics were successfully retrieved"
    )

class ProcessInfo(BaseModel):
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    user: str

class DashboardResponse(BaseModel):
    cpu: CpuInfo
    ram: RamInfo
    disks: List[DiskInfo]
    gpus: List[GpuInfo] = []