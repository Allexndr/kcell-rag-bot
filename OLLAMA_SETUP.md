# Настройка Ollama (Локальная LLM)

## Преимущества
✅ **Бесплатно** - никаких лимитов API  
✅ **Приватно** - данные не уходят в облако  
✅ **Быстро** - работает локально  
✅ **Надежно** - не зависит от интернета  

## Установка (macOS)

### 1. Установить Ollama
```bash
brew install ollama
```

### 2. Запустить сервер Ollama
```bash
ollama serve
```

### 3. Скачать модель (в новом терминале)

**Для слабого компьютера (2-4GB RAM):**
```bash
ollama pull gemma:2b
```

**Для среднего (8GB+ RAM):**
```bash
ollama pull phi3:mini
```

**Для мощного (16GB+ RAM):**
```bash
ollama pull llama3:8b
```

**Русскоязычная модель (рекомендуется):**
```bash
ollama pull saiga
```

## Использование в боте

### Вариант 1: Замена Gemini на Ollama

Отредактировать `main.py`:
```python
# Было:
from rag_engine import RAGEngine

# Стало:
from rag_engine_local import RAGEngineLocal as RAGEngine
```

### Вариант 2: Гибридный режим

```python
# main.py
try:
    from rag_engine import RAGEngine  # Gemini
except:
    from rag_engine_local import RAGEngineLocal as RAGEngine  # Fallback
```

## Тестирование

```bash
# Запустить тест
python3 rag_engine_local.py

# Или через main.py (если заменили import)
python3 main.py
```

## Рекомендуемые модели

| Модель | Размер | RAM | Качество для русского | Скорость |
|--------|--------|-----|---------------------|----------|
| gemma:2b | 1.4GB | 4GB | ⭐⭐⭐ | ⚡⚡⚡ |
| phi3:mini | 2.3GB | 8GB | ⭐⭐⭐⭐ | ⚡⚡ |
| llama3:8b | 4.7GB | 16GB | ⭐⭐⭐⭐⭐ | ⚡ |
| saiga | 4.1GB | 16GB | ⭐⭐⭐⭐⭐ | ⚡ |

## Проблемы и решения

**Ошибка: "connection refused"**
→ Забыли запустить `ollama serve`

**Слишком медленно**
→ Выберите модель поменьше (gemma:2b)

**Плохое качество ответов**
→ Попробуйте модель побольше (llama3:8b или saiga)
