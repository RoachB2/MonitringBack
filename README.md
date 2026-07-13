# Tuwunel Monitor

**Единая точка управления self-hosted инфраструктурой — мониторинг сервера и управление сервисами с телефона за 5 минут.**

![Tuwunel Dashboard](https://github.com/your-username/tuwunel-monitor/raw/main/screenshots/dashboard.png)

## 🎯 Миссия

Tuwununel Monitor решает главную проблему self-hosted энтузиастов: **сложность управления распределённой инфраструктурой**. Вместо десятков отдельных интерфейсов, у вас есть единая панель для:

- 📊 **Мониторинга** системных ресурсов (CPU, RAM, GPU, диски, сеть)
- 🐳 **Управления** Docker контейнерами  
- ☁️ **Интеграции** с Proxmox VE (в разработке)
- 📱 **Контроля** всего этого с мобильного устройства

Запустите полную рабочую среду на любом сервере/VDS/Raspberry Pi одной командой и управляйте ею с кармана.

## 🛠 Технологический стек

### Backend
- **FastAPI** — современный async web framework
- **Python 3.10+** — основной язык разработки  
- **psutil** — системный мониторинг (CPU, RAM, диски, GPU, сеть, процессы)
- **Docker SDK** — управление контейнерами
- **SQLAlchemy + aiosqlite** — асинхронная работа с базой данных
- **JWT** — безопасная аутентификация с refresh токенами
- **Pydantic** — валидация данных и сериализация

### Frontend (отдельный репозиторий)
- **Qt6 + QML** — кроссплатформенное мобильное приложение
- **Material Design** — современный и интуитивный интерфейс

### Деплоймент
- **Docker** — основной способ развёртывания
- **Systemd** — нативный запуск на Linux
- **Install script** — автоматическая установка одной командой

## 🚀 Текущее состояние

### ✅ Готово (MVP Core)
- Полноценный системный мониторинг:
  - CPU (загрузка, частота, температура)
  - RAM (использование, доступно)
  - Диски (физические диски + разделы, SMART температура)
  - GPU (NVIDIA, AMD, Intel с метриками использования)
  - Процессы (список, фильтрация, завершение)
  - Сеть (интерфейсы, IP адреса, статистика трафика)
- Безопасная аутентификация:
  - JWT Bearer tokens с автоматической генерацией пароля
  - Ролевая система (admin/user)
  - Refresh tokens для долгосрочных сессий
- RESTful API с документацией
- Mobile-first архитектура

### 🏗 В активной разработке
- Управление Docker контейнерами (старт/стоп/логи)
- Install скрипт для быстрого развёртывания
- Интеграция с Proxmox VE через WebView
- Marketplace готовых стеков (Nextcloud, Jellyfin, Home Assistant)

### 📅 Планы на будущее
- Multi-user поддержка с granular permissions
- Система уведомлений (Telegram, email)
- Автоматические бэкапы и восстановление
- Kubernetes поддержка
- Расширенный marketplace с community шаблонами
- Hosted SaaS версия для non-technical пользователей

## 📖 Документация API

Полная документация API доступна по адресу:

**`http://localhost:8000/docs`** (Swagger UI)  
**`http://localhost:8000/redoc`** (ReDoc)

Основные endpoints:

- **Аутентификация**: `POST /api/v1/token`
- **Dashboard**: `GET /api/v1/dashboard` 
- **Процессы**: `GET /api/v1/processes`, `POST /api/v1/process/{pid}/kill`
- **Системные метрики**: `/api/v1/dashboard/cpu`, `/ram`, `/disks`, `/gpu`, `/network`

## 🚦 Быстрый старт

### Локальная разработка
```bash
# Клонировать репозиторий
git clone https://github.com/your-username/tuwunel-monitor.git
cd tuwunel-monitor

# Установить зависимости
pip install -r requirements.txt

# Запустить сервер
python app/run.py

# Сервер будет доступен на http://127.0.0.1:8000
