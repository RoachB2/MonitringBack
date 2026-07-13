<div align="center">

# Tuwunel Monitor

**Единая точка управления self-hosted инфраструктурой — мониторинг сервера и управление сервисами с телефона за 5 минут.**

<img src="img/appDashboard.png" width="300" alt="Tuwunel Dashboard">

</div>

---

## 🎯 Описание проекта

### Для чего этот проект?

Tuwunel Monitor решает главную проблему self-hosted энтузиастов: **сложность управления распределённой инфраструктурой**. Вместо десятков отдельных интерфейсов, у вас есть единая панель для мониторинга системных ресурсов и управления сервисами через мобильное приложение.

### Сценарии использования

#### 🏠 Homelab энтузиасты
- Мониторинг домашнего сервера/Raspberry Pi в реальном времени
- Управление Docker контейнерами (Nextcloud, Jellyfin, Home Assistant) с телефона
- Быстрая диагностика проблем (перезапуск зависших сервисов, анализ нагрузки)

#### 💼 Small Business Owners  
- Альтернатива облачным подпискам (Google Workspace, Slack, Zoom)
- Полный контроль над корпоративными данными
- Cost reduction на $500-2000/месяц при переходе с облаков

#### 👨‍💻 IT Консультанты
- Управление инфраструктурой клиентов через единый интерфейс
- Быстрое развёртывание стандартных стеков
- Remote monitoring и troubleshooting

#### 🎓 Образовательные учреждения
- Локальные LMS и медиа-библиотеки без зависимости от облаков
- Обучение студентов основам системного администрирования
- Privacy-first подход к образовательным данным

### Текущее состояние проекта

#### ✅ Готово (Core MVP)
- **Системный мониторинг**: CPU, RAM, диски (физические + разделы), GPU (NVIDIA/AMD/Intel), сеть, процессы
- **Безопасная аутентификация**: JWT tokens, ролевая система, автоматическая генерация паролей
- **RESTful API**: полная документация через Swagger/OpenAPI
- **Mobile-ready архитектура**: оптимизирован для работы с мобильного клиента

#### 🏗 В активной разработке
- Управление Docker контейнерами (старт/стоп/рестарт/логи)
- Docker-compose возможность быстрого конфигурирования контейнеров
- Install скрипт для автоматической установки на любом сервере
- Интеграция с Proxmox VE через WebView компонент

#### 📅 Планы на будущее
- Marketplace готовых стеков (Privacy Stack, Media Stack, Office Stack)
- Multi-user поддержка с granular permissions  
- Система уведомлений (Telegram, email, push)
- Автоматические бэкапы и disaster recovery
- Kubernetes поддержка

---

## 📖 Документация API

Этот раздел предназначен для разработчиков, которые хотят создать **сторонний клиент** для Tuwunel Monitor платформы.

### Базовая информация
- **Базовый URL**: `/api/v1`
- **Формат ответов**: JSON
- **Аутентификация**: Bearer Token (JWT)
- **Content-Type**: `application/json`

### Интерактивная документация
Полная OpenAPI спецификация доступна по адресам:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/doc`

### Аутентификация

Все endpoints кроме `/api/v1/token` требуют авторизации.

**1. Получение токена:**
```bash
curl -X POST "http://localhost:8000/api/v1/token" \
  -d "username=admin&password=your_password"
```

**Ответ:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**2. Использование токена:**
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  "http://localhost:8000/api/v1/dashboard"
```

### Основные endpoints

#### Аутентификация

- `POST /api/v1/token` — получение access/refresh токенов
- `POST /api/v1/refresh` — обновление access токена
- `POST /api/v1/logout` — выход из системы

#### Управление аккаунтами

- `POST /api/v1/create_user` — создание нового пользователя
- `POST /api/v1/change_password` — изменение текущего пароля пользователя
- `POST /api/v1/change_username` — изменение текущего имени пользователя
-  `POST /api/v1/del_user` — удаления пользователя
#### Системный мониторинг

- `GET /api/v1/dashboard` — полная информация о системе
- `GET /api/v1/dashboard/cpu` — только CPU метрики  
- `GET /api/v1/dashboard/ram` — только RAM метрики
- `GET /api/v1/dashboard/disks` — информация о дисках
- `GET /api/v1/dashboard/gpu` — GPU метрики
- `GET /api/v1/dashboard/network` — сетевые интерфейсы и статистика

#### Управление процессами
- `GET /api/v1/processes` — список процессов (с фильтрацией по имени/пользователю)
- `POST /api/v1/process/{pid}/kill` — завершение процесса (требует admin прав)

#### Healthcheck
- `GET /api/v1/healthcheck` — проверка работоспособности сервера и базы данных

### Схемы данных

Все ответы соответствуют Pydantic моделям из `app/schemas/metrics.py`. Основные структуры:

- **DashboardResponse** — полный dashboard
- **CpuInfo**, **RamInfo**, **DiskInfo**, **GpuInfo**, **NetworkInterfaceInfo** — отдельные компоненты
- **ProcessInfo** — информация о процессах

---

## ⚙️ Настройка рабочего окружения

### Требования
- **Python**: 3.10 или выше
- **Системные зависимости**: 
  - Linux: `smartctl` (для SMART мониторинга дисков)
  - GPU monitoring: `nvidia-smi`, `rocm-smi` (опционально)

### Установка зависимостей

**1. Клонирование репозитория:**
```bash
git clone https://github.com/your-username/tuwunel-monitor.git
cd tuwunel-monitor
```

**2. Создание виртуального окружения (рекомендуется):**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/MacOS
# или
venv\Scripts\activate     # Windows
```

**3. Установка Python зависимостей:**

Точные версии пакетов указаны в `requirements.txt`:

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
psutil==5.9.6
pydantic==2.5.0
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
python-multipart==0.0.6
bcrypt==4.0.1
aiosqlite==0.19.0
sqlalchemy==2.0.23
```

Установка:
```bash
pip install -r requirements.txt
```

### Запуск сервера

**Режим разработки (с авто-перезагрузкой):**
```bash
python app/run.py
```

**Продакшен режим:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Сервер будет доступен по адресу: `http://localhost:8000`

### Первая настройка

При первом запуске автоматически создаётся пользователь:
- **Логин**: `admin`
- **Пароль**: генерируется случайно и выводится в консоль

Пример вывода:
```
========================================
Login: admin
Password: xK9@mP2$vL8!qR5&sT7
========================================
```

Далее рекомендуется сменить пароль по умолчаню
### Конфигурация

Конфигурация осуществляется через файл `.env` в корне проекта:

```env
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

Если файл `.env` не существует, используются значения по умолчанию (для разработки).
