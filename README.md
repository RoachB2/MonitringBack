# Tuwunel Monitor: Функциональная документация

## 🔐 Аутентификация
- **Механизм:** JWT (Bearer Token)
- **Эндпоинт:** `POST /api/v1/token`
- **Вход:** `username`, `password` (form-data)
- **Выход:** `access_token`, `token_type`
- **Роли:**
  - `admin` → чтение + управление процессами
  - `user` → только чтение
> [!TIP] Использование
> Добавляйте заголовок ко всем запросам: `Authorization: Bearer <токен>`
> Срок жизни токена: 30 минут.

## 📊 Мониторинг системы
- **Эндпоинт:** `GET /api/v1/dashboard`
- **Возвращает:** Актуальные метрики в JSON
- **Поля ответа:** 

| Поле                                | Описание                        | Тип        |
| ----------------------------------- | ------------------------------- | ---------- |
| `cpu.load_percent`                  | Загрузка процессора             | float (%)  |
| `cpu.core_count`                    | Кол-во ядер                     | int        |
| `cpu.frequency_mhz`                 | Текущая частота                 | float      |
| `ram.load_percent`                  | Загрузка ОЗУ                    | float (%)  |
| `ram.used_gb`/ `ram.total_gb`       | Объём памяти                    | float (ГБ) |
| `disks[]`                           | Список дисков                   | array      |
| `disks[].device` / `mount_point`    | Устройство и точка монтирования | string     |
| `disks[].used_percent` / `total_gb` | Заполненность и объём           | float      |



## Мониторинг GPU
- **Эндпоинт:** `GET /api/v1/dashboard` (массив `gpus`)
- **Базовые данные** (всегда доступны): `name`, `vendor`
- **Метрики** (зависят от ОС/драйверов): `load_percent`, `memory_used_mb`, `memory_total_mb`, `temperature_c`, `metrics_available`
- **Поддержка:**

| Вендор     | Windows | Linux             | Метрики                                    |
| ---------- | ------- | ----------------- | ------------------------------------------ |
| **NVIDIA** | ✅       | ✅                 | Загрузка, VRAM, температура (`nvidia-smi`) |
| **AMD**    | 🔸Имя   | ✅ (root/rocm-smi) | VRAM, частота, темп (Linux)                |
| **Intel**  | 🔸 Имя  | ✅ (sysfs)         | Частота, память (Linux)                    |
|            |         |                   |                                            |

> [!WARNING] `metrics_available: false`
> Система видит видеокарту, но не может снять метрики (нет прав или утилит). Значения сброшены в `0`.

##  Управление процессами
### 1. Список процессов
- **Endpoint:** `GET /api/v1/processes`
- **Фильтры:** `?name=...` (по имени), `?user=...` (по владельцу)
- **Логика:** Регистронезависимый поиск, сортировка по `cpu_percent` (↓)
- **Поля:** `pid`, `name`, `cpu_percent`, `memory_percent`, `user`

### 2. Завершение процесса
- **Endpoint:** `POST /api/v1/process/{pid}/kill`
- **Доступ:** Только `admin`
- **Защита:** Блокировка `pid <= 100` (системные процессы)
- **Ответы:**
  - `200` → `{"status": "success"}`
  - `404` → Процесс не найден/уже завершён
  - `403` → Нет прав или `AccessDenied` от ОС
  - `400` → Попытка убить системный процесс

##  Примеры запросов
### Получить токен

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/token" \
  -d "username=admin&password=ВАШ_ПАРОЛЬ"
```
### Запросить Dashboard
```bash
curl -H "Authorization: Bearer ВАШ_ТОКЕН" \
  "http://127.0.0.1:8000/api/v1/dashboard"
```

### Убить процесс
```bash
curl -X POST -H "Authorization: Bearer ВАШ_ТОКЕН" \
  "http://127.0.0.1:8000/api/v1/process/1234/kill"
```
