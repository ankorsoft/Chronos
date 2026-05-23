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
| **Frontend** | Управление проектами, просмотр/редактирование структуры, копирование контекста | HTML/JS (Vanilla/HTMX) → React/Vue (roadmap) |
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

# Установка зависимостей
pip install -r requirements.txt

# Запуск сервера
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Сервер запустится на `http://localhost:8000`

### API Endpoints

- `GET /` - Главная страница с Web UI
- `POST /api/projects/` - Добавить новый проект
- `GET /api/projects/` - Список всех проектов
- `GET /api/projects/{project_id}` - Детали проекта со сжатым контекстом
- `POST /api/projects/{project_id}/analyze` - Запустить анализ проекта
- `GET /api/projects/{project_id}/context` - Получить сжатый контекст
- `DELETE /api/projects/{project_id}` - Удалить проект

### Пример использования API

```bash
# Добавить проект
curl -X POST "http://localhost:8000/api/projects/" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project", "path": "/path/to/project"}'

# Запустить анализ
curl -X POST "http://localhost:8000/api/projects/1/analyze"

# Получить контекст
curl "http://localhost:8000/api/projects/1/context"
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
├── app/
│   ├── main.py        # FastAPI приложение и роуты
│   ├── models.py      # SQLModel модели данных
│   └── database.py    # Конфигурация БД
├── core/
│   └── engine.py      # Ядро сжатия контекста (parser, compressor, tokenizer)
├── static/            # Статические файлы (CSS, JS)
├── templates/         # HTML шаблоны
├── tests/             # Тесты
├── requirements.txt   # Зависимости Python
├── .gitignore
└── README.md
```

## 🔮 Roadmap

- [ ] Поддержка дополнительных языков (JavaScript/TypeScript, Go, Rust)
- [ ] Интеграция с GitHub/GitLab для анализа удалённых репозиториев
- [ ] Плагины для VS Code, JetBrains IDE
- [ ] Расширенная аналитика и метрики проектов
- [ ] Docker-контейнеризация
- [ ] PostgreSQL поддержка для production
- [ ] WebSocket для real-time обновления статуса анализа

## 🤝 Вклад

Pull Request приветствуются! Для крупных изменений сначала откройте Issue для обсуждения.

## 📄 Лицензия

MIT License

---

**Автор**: Ankorsoft  
**Репозиторий**: https://github.com/ankorsoft/Chronos