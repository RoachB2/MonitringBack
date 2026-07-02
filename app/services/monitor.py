import platform
import subprocess
from typing import List, Optional
import psutil
from app.schemas.metrics import CpuInfo, RamInfo, DiskInfo, DiskPartitionInfo, GpuInfo, ProcessInfo


class MonitorService:
    def get_cpu_info(self) -> CpuInfo:
        load = psutil.cpu_percent(interval=0.1)
        cores = psutil.cpu_count()
        freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0

        # Чтение температуры CPU
        temp = 0.0
        try:
            sensors = psutil.sensors_temperatures()
            if sensors:
                for name, entries in sensors.items():
                    for entry in entries:
                        if 'cpu' in entry.label.lower() or 'core' in entry.label.lower() or 'package' in entry.label.lower():
                            temp = float(entry.current)
                            break
                    if temp > 0:
                        break

                if temp == 0.0 and sensors:
                    for entries in sensors.values():
                        if entries:
                            temp = float(entries[0].current)
                            break
        except Exception:
            temp = 0.0

        return CpuInfo(
            load_percent=load,
            core_count=cores,
            frequency_mhz=freq,
            temperature_c=round(temp, 1)
        )

    def get_ram_info(self) -> RamInfo:
        mem = psutil.virtual_memory()
        return RamInfo(
            load_percent=mem.percent,
            used_gb=round(mem.used / (1024 ** 3), 2),
            total_gb=round(mem.total / (1024 ** 3), 2)
        )

    def get_disks_info(self) -> list[DiskInfo]:
        """Получение информации по физическим дискам"""
        system = platform.system()

        if system == "Windows":
            return self._get_physical_disks_windows()
        elif system == "Darwin":  # macOS
            return self._get_physical_disks_macos()
        else:  # Linux
            return self._get_physical_disks_linux()

    def _get_physical_disks_macos(self) -> list[DiskInfo]:
        """Получение физических дисков на macOS с группировкой по APFS"""
        import re

        try:
            # Шаг 1: Парсим diskutil list для построения карты соответствий
            result = subprocess.run(
                ['diskutil', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return self._fallback_macos_disks()

            # Строим карту: какой том -> какой физический диск
            partition_to_physical = {}
            physical_disk_info = {}  # disk0 -> {size_bytes, name}

            lines = result.stdout.split('\n')
            current_physical = None
            current_container = None

            i = 0
            while i < len(lines):
                line = lines[i]

                # Ищем физические диски: /dev/disk0 (internal, physical):
                phys_match = re.match(r'^(/dev/(disk\d+))\s+\(.*physical\)', line)
                if phys_match:
                    current_physical = phys_match.group(2)  # disk0
                    current_container = None

                    # Получаем размер физического диска
                    size_bytes = self._parse_disk_size(lines, i)
                    name = self._get_disk_name_macos(current_physical)
                    physical_disk_info[current_physical] = {
                        'size_bytes': size_bytes,
                        'name': name
                    }
                    i += 1
                    continue

                # Ищем синтетические диски (APFS Container): /dev/disk3 (synthesized):
                synth_match = re.match(r'^(/dev/(disk\d+))\s+\(synthesized\)', line)
                if synth_match:
                    current_container = synth_match.group(2)  # disk3
                    i += 1
                    continue

                # Ищем строку "Physical Store disk0s2" внутри synthesized диска
                if current_container and 'Physical Store' in line:
                    store_match = re.search(r'Physical Store\s+(disk\d+)s?\d*', line)
                    if store_match and current_physical:
                        pass
                    i += 1
                    continue

                # Ищем разделы внутри диска
                part_match = re.search(r'(disk\d+)s(\d+)', line)
                if part_match:
                    partition_name = part_match.group(0)  # disk3s1
                    base_disk = part_match.group(1)  # disk3

                    if current_container == base_disk and current_physical:
                        partition_to_physical[partition_name] = current_physical
                    elif base_disk == current_physical:
                        partition_to_physical[partition_name] = current_physical

                i += 1

            # Шаг 2: Собираем данные о смонтированных томах
            physical_disks = {}

            skip_mounts = {
                '/System/Volumes/VM',
                '/System/Volumes/Preboot',
                '/System/Volumes/Update',
                '/System/Volumes/xarts',
                '/System/Volumes/iSCPreboot',
                '/System/Volumes/Hardware',
            }

            partitions = psutil.disk_partitions(all=False)

            for part in partitions:
                if 'AppTranslocation' in part.mountpoint:
                    continue

                dev_match = re.search(r'(disk\d+)s(\d+)', part.device)
                if not dev_match:
                    continue

                partition_name = dev_match.group(0)
                physical_disk = partition_to_physical.get(partition_name)

                if not physical_disk:
                    base = dev_match.group(1)
                    if base == 'disk3':
                        physical_disk = 'disk0'
                    elif base == 'disk1':
                        physical_disk = 'disk0'
                    else:
                        continue

                try:
                    usage = psutil.disk_usage(part.mountpoint)
                except:
                    continue

                if physical_disk not in physical_disks:
                    physical_disks[physical_disk] = {
                        'mount_points': [],
                        'internals': [],
                        'used_bytes': 0,
                        'total_bytes': physical_disk_info.get(physical_disk, {}).get('size_bytes', 0),
                        'name': physical_disk_info.get(physical_disk, {}).get('name', physical_disk)
                    }

                if part.mountpoint not in physical_disks[physical_disk]['mount_points']:
                    if not any(part.mountpoint.startswith(skip) for skip in skip_mounts):
                        physical_disks[physical_disk]['mount_points'].append(part.mountpoint)

                total_gb = round(usage.total / (1024 ** 3), 2)
                used_percent = round(usage.percent, 1)

                partition_info = DiskPartitionInfo(
                    device=part.device,
                    mount_point=part.mountpoint,
                    used_percent=used_percent,
                    total_gb=total_gb
                )

                if not any(p.device == part.device for p in physical_disks[physical_disk]['internals']):
                    physical_disks[physical_disk]['internals'].append(partition_info)

                physical_disks[physical_disk]['used_bytes'] = max(
                    physical_disks[physical_disk]['used_bytes'],
                    usage.used
                )

            # Шаг 3: Формируем результат
            result = []
            for phys_disk, info in physical_disks.items():
                total_bytes = info['total_bytes']
                used_bytes = info['used_bytes']

                if total_bytes == 0:
                    for part in psutil.disk_partitions():
                        dev_match = re.search(r'(disk\d+)s(\d+)', part.device)
                        if dev_match and partition_to_physical.get(dev_match.group(0)) == phys_disk:
                            try:
                                usage = psutil.disk_usage(part.mountpoint)
                                total_bytes = max(total_bytes, usage.total)
                            except:
                                pass

                total_gb = round(total_bytes / (1024 ** 3), 2)
                used_percent = round((used_bytes / total_bytes * 100) if total_bytes > 0 else 0, 1)

                # Используем model_name
                model_name = info['name'] if info['name'] else f"/dev/{phys_disk}"

                result.append(DiskInfo(
                    device=f"/dev/{phys_disk}",
                    model_name=model_name,
                    temperature_c=0.0,
                    used_percent=used_percent,
                    total_gb=total_gb,
                    internals=info['internals']
                ))

            return result if result else self._fallback_macos_disks()

        except Exception as e:
            print(f"Error getting macOS disks: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_macos_disks()

    def _parse_disk_size(self, lines: list, start_idx: int) -> int:
        """Парсит размер диска из вывода diskutil"""
        import re
        for i in range(start_idx, min(start_idx + 20, len(lines))):
            if 'Disk Size' in lines[i] or 'Total Size' in lines[i]:
                match = re.search(r'\((\d+)\s*Bytes?\)', lines[i])
                if match:
                    return int(match.group(1))
        return 0

    def _get_disk_name_macos(self, disk_name: str) -> str:
        """Получение модели диска"""
        try:
            result = subprocess.run(
                ['diskutil', 'info', f'/dev/{disk_name}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Device / Media Name' in line:
                        return line.split(':', 1)[1].strip()
        except:
            pass
        return disk_name

    def _fallback_macos_disks(self) -> list[DiskInfo]:
        """Упрощенный fallback - группируем по базовому диску с internals"""
        import re

        disks = {}
        skip_mounts = [
            '/System/Volumes/VM', '/System/Volumes/Preboot',
            '/System/Volumes/Update', '/System/Volumes/xarts',
            '/System/Volumes/iSCPreboot', '/System/Volumes/Hardware',
            '/private/var/folders'
        ]

        for part in psutil.disk_partitions():
            if 'AppTranslocation' in part.mountpoint:
                continue

            match = re.search(r'(disk\d+)', part.device)
            if not match:
                continue

            base = match.group(1)
            if base == 'disk3':
                phys = 'disk0'
            elif base == 'disk1':
                phys = 'disk0'
            else:
                phys = base

            try:
                usage = psutil.disk_usage(part.mountpoint)

                if phys not in disks:
                    # Получаем имя модели диска
                    model_name = self._get_disk_name_macos(phys)
                    disks[phys] = {
                        'used': 0,
                        'total': 0,
                        'internals': [],
                        'model_name': model_name
                    }

                total_gb = round(usage.total / (1024 ** 3), 2)
                used_percent = round(usage.percent, 1)

                partition_info = DiskPartitionInfo(
                    device=part.device,
                    mount_point=part.mountpoint,
                    used_percent=used_percent,
                    total_gb=total_gb
                )

                if not any(p.device == part.device for p in disks[phys]['internals']):
                    disks[phys]['internals'].append(partition_info)

                disks[phys]['used'] = max(disks[phys]['used'], usage.used)
                disks[phys]['total'] = max(disks[phys]['total'], usage.total)
            except:
                continue

        result = []
        for phys, info in disks.items():
            total_gb = round(info['total'] / (1024 ** 3), 2)
            used_percent = round((info['used'] / info['total'] * 100) if info['total'] > 0 else 0, 1)

            result.append(DiskInfo(
                device=f"/dev/{phys}",
                model_name=info['model_name'],
                temperature_c=0.0,
                used_percent=used_percent,
                total_gb=total_gb,
                internals=info['internals']
            ))

        return result

    def _get_physical_disks_linux(self) -> list[DiskInfo]:
        """Получение физических дисков на Linux"""
        import json
        import os

        disks = []

        try:
            result = subprocess.run(
                ['lsblk', '-b', '-o', 'NAME,TYPE,SIZE,MOUNTPOINT,PKNAME,FSTYPE,MODEL', '--json'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return self._fallback_linux_disks()

            data = json.loads(result.stdout)
            block_devices = data.get('blockdevices', [])

            physical_disks = [d for d in block_devices if d.get('type') == 'disk']

            for disk in physical_disks:
                disk_name = disk['name']
                total_bytes = int(disk.get('size', 0))
                model_name = disk.get('model', '').strip() or disk_name

                partitions = self._find_partitions(disk, block_devices)

                mount_points = []
                total_used = 0

                for part in partitions:
                    mountpoint = part.get('mountpoint')
                    if mountpoint:
                        try:
                            usage = psutil.disk_usage(mountpoint)
                            mount_points.append(mountpoint)
                            total_used += usage.used
                        except (PermissionError, FileNotFoundError):
                            pass

                total_gb = round(total_bytes / (1024 ** 3), 2)
                used_percent = round((total_used / total_bytes * 100) if total_bytes > 0 else 0, 1)

                temperature = self._get_disk_temperature_linux(disk_name)

                internals = []
                for part in partitions:
                    mountpoint = part.get('mountpoint')
                    if mountpoint:
                        try:
                            usage = psutil.disk_usage(mountpoint)
                            internals.append(DiskPartitionInfo(
                                device=f"/dev/{part['name']}",
                                mount_point=mountpoint,
                                used_percent=usage.percent,
                                total_gb=round(usage.total / (1024 ** 3), 2)
                            ))
                        except:
                            pass

                disks.append(DiskInfo(
                    device=f"/dev/{disk_name}",
                    model_name=model_name,
                    temperature_c=temperature,
                    used_percent=used_percent,
                    total_gb=total_gb,
                    internals=internals
                ))

        except Exception as e:
            print(f"Error getting physical disks: {e}")
            return self._fallback_linux_disks()

        return disks

    def _find_partitions(self, disk: dict, all_devices: list) -> list:
        """Рекурсивный поиск всех разделов диска"""
        partitions = []
        disk_name = disk['name']

        for device in all_devices:
            if device.get('pkname') == disk_name:
                partitions.append(device)
                partitions.extend(self._find_partitions(device, all_devices))

        return partitions

    def _get_disk_temperature_linux(self, disk_name: str) -> float:
        """Получение температуры диска на Linux"""
        import re

        try:
            result = subprocess.run(
                ['smartctl', '-a', f'/dev/{disk_name}'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Temperature' in line or 'temperature' in line:
                        match = re.search(r'(\d+)', line)
                        if match:
                            return float(match.group(1))
        except Exception:
            pass

        return 0.0

    def _get_disk_model_linux(self, disk_name: str) -> str:
        """Получение модели диска на Linux из sysfs"""
        import os
        try:
            model_path = f"/sys/block/{disk_name}/device/model"
            if os.path.exists(model_path):
                with open(model_path, 'r') as f:
                    return f.read().strip()
        except:
            pass
        return disk_name

    def _fallback_linux_disks(self) -> list[DiskInfo]:
        """Резервный метод получения дисков"""
        disks = []
        seen_devices = set()

        for part in psutil.disk_partitions():
            device = part.device
            base_device = ''.join([c for c in device if not c.isdigit()]).rstrip('/')

            if base_device in seen_devices:
                continue

            try:
                usage = psutil.disk_usage(part.mountpoint)
                temp = self._get_disk_temperature_linux(base_device.replace('/dev/', ''))

                # Получаем модель диска из sysfs
                model_name = self._get_disk_model_linux(base_device.replace('/dev/', ''))

                disks.append(DiskInfo(
                    device=base_device,
                    model_name=model_name,
                    temperature_c=temp,
                    used_percent=usage.percent,
                    total_gb=round(usage.total / (1024 ** 3), 2),
                    internals=[DiskPartitionInfo(
                        device=device,
                        mount_point=part.mountpoint,
                        used_percent=usage.percent,
                        total_gb=round(usage.total / (1024 ** 3), 2)
                    )]
                ))
                seen_devices.add(base_device)
            except (PermissionError, FileNotFoundError):
                continue

        return disks

    def _get_physical_disks_windows(self) -> list[DiskInfo]:
        """Получение физических дисков на Windows"""
        import re

        disks = []

        try:
            cmd = [
                "powershell", "-Command",
                "Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, Size, MediaType | ConvertTo-Csv -NoTypeInformation"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            lines = result.stdout.strip().split('\n')[1:]

            for line in lines:
                if not line.strip():
                    continue

                parts = [p.strip('"') for p in line.split(',')]
                if len(parts) >= 3:
                    device_id = parts[0]
                    name = parts[1]
                    size_bytes = int(parts[2]) if parts[2].isdigit() else 0

                    partitions_cmd = [
                        "powershell", "-Command",
                        f"Get-Disk -Number {device_id} | Get-Partition | Get-Volume | Select-Object DriveLetter, SizeRemaining, Size | ConvertTo-Csv -NoTypeInformation"
                    ]

                    try:
                        part_result = subprocess.run(partitions_cmd, capture_output=True, text=True, timeout=5)
                        part_lines = part_result.stdout.strip().split('\n')[1:]

                        total_used = 0
                        total_size = 0
                        mount_points = []
                        internals = []

                        for part_line in part_lines:
                            if not part_line.strip():
                                continue
                            part_parts = [p.strip('"') for p in part_line.split(',')]
                            if len(part_parts) >= 3:
                                drive_letter = part_parts[0]
                                size_remaining = int(part_parts[1]) if part_parts[1].isdigit() else 0
                                size = int(part_parts[2]) if part_parts[2].isdigit() else 0

                                if drive_letter and drive_letter != '':
                                    mount_point = f"{drive_letter}:"
                                    mount_points.append(mount_point)
                                    used = size - size_remaining
                                    total_used += used
                                    total_size += size

                                    internals.append(DiskPartitionInfo(
                                        device=f"{drive_letter}:",
                                        mount_point=mount_point,
                                        used_percent=round((used / size * 100) if size > 0 else 0, 1),
                                        total_gb=round(size / (1024 ** 3), 2)
                                    ))

                        total_gb = round(size_bytes / (1024 ** 3), 2)
                        used_percent = round((total_used / total_size * 100) if total_size > 0 else 0, 1)

                        temperature = 0.0

                        disks.append(DiskInfo(
                            device=f"PhysicalDrive{device_id}",
                            model_name=name,
                            temperature_c=temperature,
                            used_percent=used_percent,
                            total_gb=total_gb,
                            internals=internals
                        ))
                    except Exception:
                        continue

        except Exception as e:
            print(f"Error getting Windows physical disks: {e}")

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
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"],
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
            if entry.startswith("card") and "-card" not in entry and amd_idx < len(gpus) and gpus[
                amd_idx].vendor == "AMD":
                dev_path = os.path.join(drm_path, entry, "device")
                try:
                    mem_used = int(open(os.path.join(dev_path, "mem_info_vram_used")).read().strip())
                    mem_total = int(open(os.path.join(dev_path, "mem_info_vram_total")).read().strip())
                    gpus[amd_idx].memory_used_mb = round(mem_used / (1024 ** 2), 2)
                    gpus[amd_idx].memory_total_mb = round(mem_total / (1024 ** 2), 2)

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
                if entry.startswith("card") and "-card" not in entry and intel_idx < len(gpus) and gpus[
                    intel_idx].vendor == "Intel":
                    dev_path = os.path.join(drm_path, entry, "device")
                    try:
                        cur = int(open(os.path.join(dev_path, "gt_cur_freq_mhz")).read().strip())
                        max_ = int(open(os.path.join(dev_path, "gt_max_freq_mhz")).read().strip())
                        if max_ > 0:
                            gpus[intel_idx].load_percent = round((cur / max_) * 100, 2)

                        vram = os.path.join(dev_path, "mem_info_vram_total")
                        if os.path.exists(vram):
                            total = int(open(vram).read().strip())
                            gpus[intel_idx].memory_total_mb = round(total / (1024 ** 2), 2)

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