# Chronos Context 🚀

**Веб-сервис для подготовки, хранения и выдачи сжатого контекста Python-проектов под LLM-кодинг.**

## 📌 О проекте

Chronos помогает экономить токены при работе с большими кодовыми базами в LLM (ChatGPT, Claude, Cursor и др.), генерируя сжатые скелеты проектов вместо полной отправки исходного кода.

### Ключевые возможности
- 🗜️ **Сжатие контекста**: Генерация структурного скелета проекта (классы, функции, импорты) вместо полного кода
- 💰 **Экономия токенов**: Типичная экономия 85-95% токенов по сравнению с полной отправкой файлов
- 🔄 **Инкрементальное обновление**: Кэширование результатов и обновление только изменённых файлов
- 🌐 **Web UI**: Визуальный контроль структуры проектов, история, настройки
- 🔌 **API-first**: REST API для интеграции с внешними инструментами и IDE

## 🏗️ Архитектура

| Слой | Роль | Технологии |
|------|------|------------|
| **Backend** | REST API, парсинг кода → скелет, подсчёт токенов, кэш, бизнес-логика | FastAPI, SQLModel/SQLAlchemy, tiktoken, ast |
| **Storage** | Хранение путей проектов, сжатых структур, метрик, истории запросов | SQLite (MVP) → PostgreSQL (scale) + файловый кэш JSON |
| **Frontend** | Управление проектами, просмотр/редактирование структуры, копирование контекста | HTML/JS (Vanilla/HTMX) |
| **Core Engine** | Изолированный модуль сжатия: parser → compressor → tokenizer | Чистый Python, без фреймворков |

### Поток данных

1. Пользователь через фронт добавляет путь к проекту
2. FastAPI запускает асинхронный парсинг → генерирует скелет + метрики токенов
3. Результат сохраняется в БД + файловый кэш
4. Фронт отображает структуру, процент экономии, кнопку **Copy Context**
5. При повторном запросе отдаётся кэш, при изменении файлов → инкрементальное обновление

## 🚀 Быстрый старт

### Требования
- Python 3.9+
- pip

### Установка

```bash
# Клонирование репозитория
git clone https://github.com/ankorsoft/Chronos.git
cd Chronos

# Создание виртуального окружения
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Установка зависимостей
pip install -r requirements.txt

# Применение миграций БД
alembic upgrade head

# Запуск сервера
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Сервер запустится на `http://localhost:8000`

### Docker

```bash
# Сборка и запуск
docker build -t chronos .
docker run -p 8000:8000 chronos

# Или одной командой
docker run -p 8000:8000 python:3.13-slim sh -c "pip install -r requirements.txt && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

### API Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/` | Главная страница с Web UI |
| `POST` | `/api/v1/projects/` | Добавить новый проект |
| `GET` | `/api/v1/projects/` | Список всех проектов |
| `GET` | `/api/v1/projects/{project_id}` | Детали проекта |
| `POST` | `/api/v1/projects/{project_id}/analyze` | Запустить анализ проекта |
| `GET` | `/api/v1/projects/{project_id}/context` | Получить сжатый контекст |
| `POST` | `/api/v1/projects/{project_id}/snapshot` | Создать снимок проекта |
| `GET` | `/api/v1/projects/{project_id}/history` | История снимков |
| `GET` | `/api/v1/projects/{project_id}/export` | Экспорт в ZIP |
| `DELETE` | `/api/v1/projects/{project_id}` | Удалить проект |

### Пример использования API

```bash
# Добавить проект
curl -X POST "http://localhost:8000/api/v1/projects/" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project", "path": "D:\\GIT_HOME\\my-project"}'

# Запустить анализ
curl -X POST "http://localhost:8000/api/v1/projects/1/analyze"

# Получить контекст
curl "http://localhost:8000/api/v1/projects/1/context"
```

## 📊 Эффективность

| Метрика | Значение |
|---------|----------|
| Средняя экономия токенов | **85-95%** |
| Скорость анализа (10k строк) | ~2-5 сек |
| Поддерживаемые языки | Python (MVP), roadmap: JS/TS, Go, Rust |

## 🛠️ Структура проекта

```
Chronos/
├── app/                    # Веб-приложение
│   ├── main.py             # FastAPI приложение (точка входа)
│   ├── models.py           # SQLModel модели БД
│   ├── database.py         # Настройка подключения к БД
│   ├── schemas.py          # Pydantic схемы валидации
│   ├── api/                # API слой
│   │   ├── router.py       # APIRouter v1
│   │   └── views.py        # Обработчики эндпоинтов
│   └── static/             # Статика + Web UI
│       └── index.html      # Главная страница
├── core/                   # Core engine (бизнес-логика)
│   ├── engine.py           # Движок сжатия контекста
│   └── cache.py            # Файловый кэш
├── migrations/             # Alembic миграции
│   ├── env.py
│   └── versions/
│       └── 3faacbccf5bb_initial_schema.py
├── doc/                    # Документация
│   └── DEVELOPMENT_PLAN.md
├── alembic.ini             # Конфигурация Alembic
├── requirements.txt        # Зависимости
├── Dockerfile              # Docker образ
├── .env.example            # Шаблон переменных окружения
├── .gitignore
└── README.md
```

## 📋 Управление базой данных

Все изменения БД делаются через Alembic миграции:

```bash
# Создать новую миграцию (после changes в models.py)
alembic revision --autogenerate -m "description"

# Применить миграции
alebmic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1

# Показать текущую версию
alembic current

# Пошаговая история миграций
alembic history --range base:head
```

## 🔮 Roadmap

- [ ] Поддержка дополнительных языков (JavaScript/TypeScript, Go, Rust)
- [ ] Интеграция с GitHub/GitLab для анализа удалённых репозиториев
- [ ] Плагины для VS Code, JetBrains IDE
- [ ] Расширенная аналитика и метрики проектов
- [ ] PostgreSQL поддержка для production
- [ ] WebSocket для real-time обновления статуса анализа
- [ ] React/Vue frontend

## 🤝 Вклад

Pull Request приветствуются! Для крупных изменений сначала откройте Issue для обсуждения.

## 📄 Лицензия

MIT License

---

**Автор**: Ankorsoft  
**Репозиторий**: https://github.com/ankorsoft/Chronos