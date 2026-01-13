# 🤝 Вклад в проект Kcell RAG Bot

Спасибо за интерес к проекту! Мы приветствуем вклад от сообщества. Пожалуйста, прочитайте эти рекомендации перед внесением изменений.

## 📋 Правила внесения вклада

### Как внести вклад

1. **Fork** репозиторий
2. Создайте **feature branch** (`git checkout -b feature/amazing-feature`)
3. Зафиксируйте изменения (`git commit -m 'Add amazing feature'`)
4. **Push** в ветку (`git push origin feature/amazing-feature`)
5. Создайте **Pull Request**

### Типы вкладов

#### 🐛 Исправления ошибок (Bug Fixes)
- Создавайте issue с описанием проблемы
- Указывайте шаги для воспроизведения
- Предлагайте решение

#### ✨ Новые функции (Features)
- Обсудите идею в Discussions или Issues
- Следуйте архитектуре проекта
- Добавляйте тесты

#### 📚 Документация (Documentation)
- Исправления опечаток
- Улучшения clarity
- Новые примеры использования

#### 🧪 Тесты (Tests)
- Добавление новых тестов
- Улучшение покрытия
- Рефакторинг существующих тестов

## 🛠️ Разработка

### Настройка окружения

```bash
# Клонирование репозитория
git clone https://github.com/Allexndr/kcellbot.git
cd kcellbot

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Установка Ollama (если еще не установлено)
# см. OLLAMA_SETUP.md

# Копирование конфигурации
cp .env.example .env
# Отредактируйте .env файл
```

### Структура проекта

```
kcellbot/
├── src/                    # Модули
│   ├── core/              # Основные компоненты
│   ├── security/          # Безопасность
│   ├── personalization/   # Персонализация
│   └── auto_update/       # Авто-обновление
├── tests/                 # Тесты
├── tools/                 # Инструменты
├── analytics/             # Аналитика
├── docs/                  # Документация
└── main.py               # Точка входа
```

### Стиль кода

- **Python**: PEP 8
- **Комментарии**: на русском языке для корпоративного кода
- **Docstrings**: используйте Google стиль
- **Именование**: snake_case для функций, PascalCase для классов

### Пример кода

```python
def process_user_query(query: str) -> str:
    """
    Обрабатывает запрос пользователя.

    Args:
        query: Текстовый запрос пользователя

    Returns:
        str: Ответ системы
    """
    # Ваш код здесь
    pass
```

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
python3 -m pytest tests/

# С покрытием
python3 -m pytest --cov=src tests/

# Конкретный тест
python3 -m pytest tests/test_rag_direct.py -v
```

### Написание тестов

```python
import pytest
from src.core.rag_engine import RAGEngine

class TestRAGEngine:
    def test_query_expansion(self):
        engine = RAGEngine()
        result = engine.expand_query("ВАТС")
        assert "виртуальная атс" in result
```

## 📝 Коммиты

Используйте понятные сообщения коммитов:

```
feat: add user personalization system
fix: resolve memory leak in rag engine
docs: update installation guide
test: add comprehensive test suite
refactor: improve code modularity
```

## 🔒 Безопасность

- Не коммитите API ключи
- Используйте `.env` для конфиденциальных данных
- Следуйте принципам безопасного кодирования

## 📞 Контакты

- **Issues**: [GitHub Issues](https://github.com/Allexndr/kcellbot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Allexndr/kcellbot/discussions)
- **Email**: dev@kcell.kz

## 🙏 Благодарности

Спасибо всем контрибьюторам за улучшение проекта! 🎉
