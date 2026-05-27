import platform
import subprocess
from typing import List, Optional

import psutil
from app.schemas.metrics import CpuInfo, RamInfo, DiskInfo, GpuInfo, ProcessInfo


class MonitorService:
    def get_cpu_info(self) -> CpuInfo:
        load = psutil.cpu_percent(interval=0.1)
        cores = psutil.cpu_count()
        freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0

        return CpuInfo(
            load_percent=load,
            core_count=cores,
            frequency_mhz=freq
        )

    def get_ram_info(self) -> RamInfo:
        mem = psutil.virtual_memory()
        return RamInfo(
            load_percent=mem.percent,
            used_gb=round(mem.used / (1024 ** 3), 2),
            total_gb=round(mem.total / (1024 ** 3), 2)
        )

    def get_disks_info(self) -> list[DiskInfo]:
        disks = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append(DiskInfo(
                    device=part.device,
                    mount_point=part.mountpoint,
                    used_percent=usage.percent,
                    total_gb=round(usage.total / (1024 ** 3), 2)
                ))
            except PermissionError:
                continue
        return disks

    def get_gpu_info(self) -> List[GpuInfo]:
        system = platform.system()
        gpus = self._get_base_gpus(system)
        return self._enrich_metrics(gpus, system)

    def _get_base_gpus(self, system: str) -> List[GpuInfo]:
        if system == "Windows":
            return self._get_gpus_windows()
        return self._get_gpus_linux()

    def _get_gpus_windows(self) -> List[GpuInfo]:
        try:
            cmd = [
                "powershell", "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterCompatibility | ConvertTo-Csv -NoTypeInformation"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
            lines = res.stdout.strip().split('\n')[1:]
            gpus = []
            for line in lines:
                if not line.strip():
                    continue
                parts = [p.strip('"') for p in line.split(',')]
                if len(parts) >= 2:
                    name, vendor_raw = parts[0], parts[1]
                else:
                    name = parts[0] if parts else "Unknown"
                    vendor_raw = "Unknown"
                
                vendor = "Unknown"
                vendor_lower = vendor_raw.lower()
                if "nvidia" in vendor_lower:
                    vendor = "NVIDIA"
                elif "amd" in vendor_lower or "advanced micro devices" in vendor_lower:
                    vendor = "AMD"
                elif "intel" in vendor_lower:
                    vendor = "Intel"
                
                gpus.append(GpuInfo(name=name, vendor=vendor))
            return gpus
        except Exception:
            return []

    def _get_gpus_linux(self) -> List[GpuInfo]:
        try:
            res = subprocess.run(["lspci", "-nn"], capture_output=True, text=True, check=True, timeout=5)
            gpus = []
            for line in res.stdout.splitlines():
                if "VGA compatible controller" in line or "3D controller" in line:
                    name = line.split(": ")[-1] if ": " in line else "Unknown"
                    vendor = "Unknown"
                    low = name.lower()
                    if "nvidia" in low:
                        vendor = "NVIDIA"
                    elif "amd" in low or "advanced micro devices" in low:
                        vendor = "AMD"
                    elif "intel" in low:
                        vendor = "Intel"
                    gpus.append(GpuInfo(name=name, vendor=vendor))
            return gpus
        except Exception:
            return []

    def _enrich_metrics(self, gpus: List[GpuInfo], system: str) -> List[GpuInfo]:
        if not gpus:
            return gpus

        nvidia_gpus = [g for g in gpus if g.vendor == "NVIDIA"]
        if nvidia_gpus:
            self._try_nvidia_metrics(nvidia_gpus)

        amd_gpus = [g for g in gpus if g.vendor == "AMD"]
        if amd_gpus:
            self._try_amd_metrics(amd_gpus, system)

        intel_gpus = [g for g in gpus if g.vendor == "Intel"]
        if intel_gpus:
            self._try_intel_metrics(intel_gpus, system)

        return gpus

    def _try_nvidia_metrics(self, gpus: List[GpuInfo]):
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, check=True
            )
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
            for i, line in enumerate(lines):
                if i < len(gpus):
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) == 4:
                        gpus[i].load_percent = float(parts[0])
                        gpus[i].memory_used_mb = float(parts[1])
                        gpus[i].memory_total_mb = float(parts[2])
                        temp = parts[3]
                        gpus[i].temperature_c = float(temp) if temp != "[Not Supported]" else None
                        gpus[i].metrics_available = True
        except Exception:
            pass

    def _try_amd_metrics(self, gpus: List[GpuInfo], system: str):
        if system != "Linux":
            return
        
        try:
            import json
            res = subprocess.run(
                ["rocm-smi", "--showuse", "--showmeminfo", "--showtemp", "--json"], 
                capture_output=True, text=True, timeout=5, check=True
            )
            data = json.loads(res.stdout)
            
            for idx, gpu_id in enumerate(data.get("Card series", {})):
                if idx < len(gpus):
                    card = data["Card series"][gpu_id]
                    gpus[idx].load_percent = float(card.get("GPU use (%)", 0))
                    gpus[idx].memory_used_mb = float(card.get("VRAM total used (MiB)", 0))
                    gpus[idx].memory_total_mb = float(card.get("VRAM total memory (MiB)", 0))
                    temp = card.get("Temperature (Sensor edge) (C)")
                    gpus[idx].temperature_c = float(temp) if temp else None
                    gpus[idx].metrics_available = True
        except Exception:
            self._try_amd_sysfs(gpus)

    def _try_amd_sysfs(self, gpus: List[GpuInfo]):
        import os
        drm_path = "/sys/class/drm"
        if not os.path.exists(drm_path):
            return
        
        amd_idx = 0
        for entry in sorted(os.listdir(drm_path)):
            if entry.startswith("card") and "-card" not in entry and amd_idx < len(gpus) and gpus[amd_idx].vendor == "AMD":
                dev_path = os.path.join(drm_path, entry, "device")
                try:
                    mem_used = int(open(os.path.join(dev_path, "mem_info_vram_used")).read().strip())
                    mem_total = int(open(os.path.join(dev_path, "mem_info_vram_total")).read().strip())
                    gpus[amd_idx].memory_used_mb = round(mem_used / (1024**2), 2)
                    gpus[amd_idx].memory_total_mb = round(mem_total / (1024**2), 2)
                    
                    cur_freq = int(open(os.path.join(dev_path, "pp_cur_freq")).read().strip().split()[0])
                    max_freq = int(open(os.path.join(dev_path, "pp_dpm_sclk")).read().strip().split()[-2])
                    if max_freq > 0:
                        gpus[amd_idx].load_percent = round((cur_freq / max_freq) * 100, 2)
                    
                    hwmon = next((d for d in os.listdir(dev_path) if d.startswith("hwmon")), None)
                    if hwmon:
                        temp_input = os.path.join(dev_path, hwmon, "temp1_input")
                        if os.path.exists(temp_input):
                            gpus[amd_idx].temperature_c = int(open(temp_input).read().strip()) / 1000
                    
                    gpus[amd_idx].metrics_available = True
                except Exception:
                    pass
                amd_idx += 1

    def _try_intel_metrics(self, gpus: List[GpuInfo], system: str):
        if system != "Linux":
            return
        
        try:
            import os
            drm_path = "/sys/class/drm"
            if not os.path.exists(drm_path):
                return
            
            intel_idx = 0
            for entry in sorted(os.listdir(drm_path)):
                if entry.startswith("card") and "-card" not in entry and intel_idx < len(gpus) and gpus[intel_idx].vendor == "Intel":
                    dev_path = os.path.join(drm_path, entry, "device")
                    try:
                        cur = int(open(os.path.join(dev_path, "gt_cur_freq_mhz")).read().strip())
                        max_ = int(open(os.path.join(dev_path, "gt_max_freq_mhz")).read().strip())
                        if max_ > 0:
                            gpus[intel_idx].load_percent = round((cur / max_) * 100, 2)
                        
                        vram = os.path.join(dev_path, "mem_info_vram_total")
                        if os.path.exists(vram):
                            total = int(open(vram).read().strip())
                            gpus[intel_idx].memory_total_mb = round(total / (1024**2), 2)
                        
                        gpus[intel_idx].metrics_available = True
                    except Exception:
                        pass
                    intel_idx += 1
        except Exception:
            pass

    def get_processes(self, name_filter: str = None, user_filter: str = None) -> list[ProcessInfo]:
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
            try:
                p_info = proc.info
                p_name = p_info['name'] or ""
                p_user = p_info['username'] or ""

                if name_filter and name_filter.lower() not in p_name.lower():
                    continue

                if user_filter and user_filter.lower() not in p_user.lower():
                    continue

                processes.append(ProcessInfo(
                    pid=p_info['pid'],
                    name=p_name,
                    cpu_percent=p_info['cpu_percent'] or 0.0,
                    memory_percent=p_info['memory_percent'] or 0.0,
                    user=p_user
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        processes.sort(key=lambda x: x.cpu_percent, reverse=True)
        return processes

    def kill_process(self, pid: int):
        if pid <= 100:
            raise ValueError("Cannot kill system process")

        try:
            p = psutil.Process(pid)
            p.terminate()
            return True
        except psutil.NoSuchProcess:
            return False