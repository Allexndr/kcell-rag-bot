import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import config
from rag_engine_local import RAGEngineLocal as RAGEngine  # Using local Ollama instead of Gemini
import time
import re
import json
import os

# Import new modular components
from src.security.content_filter import check_dangerous_content, DANGEROUS_PATTERNS, SAFE_CONTEXT_KEYWORDS
from src.personalization.user_profiles import personalization
from src.auto_update.knowledge_updater import init_updater, check_and_update

# Per-user rate limiting (simple token bucket in memory)
user_buckets = {}
ALLOWED_IDS = set(getattr(config, "ALLOWED_USER_IDS", []))
RATE_WINDOW = getattr(config, "RATE_LIMIT_WINDOW_SEC", 5)
RATE_MAX = getattr(config, "RATE_LIMIT_MAX", 5)
# Basic block patterns (SQL injection, etc.)
BLOCK_PATTERNS = [
    r"http://", r"https://", r"(?i)select .* from", r"(?i)union .* select",
]

# Feedback system
FEEDBACK_FILE = "analytics/feedback.json"
feedback_data = {}
if os.path.exists(FEEDBACK_FILE):
    try:
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            feedback_data = json.load(f)
    except:
        feedback_data = {}

# Conversational memory (simple in-memory storage)
conversation_memory = {}  # user_id -> list of recent messages
MEMORY_SIZE = 5  # Keep last 5 messages per user

# User personalization data
user_profiles = {}  # user_id -> profile data
PERSONALIZATION_FILE = "analytics/personalization.json"

# Comparison State: {user_id: {'step': 'wait_orig'|'wait_mod', 'file1': path}}
comparison_state = {}
from src.compare.engine import DocumentComparator
import shutil
import uuid
comparator = DocumentComparator()

def load_user_profiles():
    global user_profiles
    try:
        if os.path.exists(PERSONALIZATION_FILE):
            with open(PERSONALIZATION_FILE, 'r', encoding='utf-8') as f:
                user_profiles = json.load(f)
    except:
        user_profiles = {}

def save_user_profiles():
    os.makedirs(os.path.dirname(PERSONALIZATION_FILE), exist_ok=True)
    with open(PERSONALIZATION_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_profiles, f, ensure_ascii=False, indent=2)

# Auto-update system for knowledge base
AUTO_UPDATE_FILE = "analytics/auto_update.json"
last_update_check = 0
UPDATE_CHECK_INTERVAL = 300  # Check every 5 minutes

def check_document_changes():
    """Check for document changes and trigger reindexing if needed"""
    global last_update_check

    current_time = time.time()
    if current_time - last_update_check < UPDATE_CHECK_INTERVAL:
        return False  # Too soon to check

    last_update_check = current_time

    try:
        # Load last known state
        last_state = {}
        if os.path.exists(AUTO_UPDATE_FILE):
            with open(AUTO_UPDATE_FILE, 'r', encoding='utf-8') as f:
                last_state = json.load(f)

        # Check current state
        current_state = {}
        docs_dir = config.DOCS_DIR

        for root, dirs, files in os.walk(docs_dir):
            for file in files:
                if file.endswith(('.pdf', '.docx', '.txt', '.xlsx', '.pptx', '.md')):
                    filepath = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(filepath)
                        current_state[filepath] = mtime
                    except:
                        pass

        # Check for changes
        changes_detected = False
        new_files = set(current_state.keys()) - set(last_state.keys())
        deleted_files = set(last_state.keys()) - set(current_state.keys())
        modified_files = []

        for filepath, mtime in current_state.items():
            if filepath in last_state and last_state[filepath] != mtime:
                modified_files.append(filepath)

        if new_files or deleted_files or modified_files:
            changes_detected = True
            print(f"📁 Document changes detected:")
            if new_files:
                print(f"  ➕ New files: {len(new_files)}")
            if deleted_files:
                print(f"  ➖ Deleted files: {len(deleted_files)}")
            if modified_files:
                print(f"  ✏️ Modified files: {len(modified_files)}")

            # Save new state
            with open(AUTO_UPDATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(current_state, f, indent=2)

            # Trigger reindexing (this would be implemented in a separate function)
            trigger_reindexing(new_files, deleted_files, modified_files)

        return changes_detected

    except Exception as e:
        print(f"⚠️ Error checking document changes: {e}")
        return False

def trigger_reindexing(new_files, deleted_files, modified_files):
    """Trigger automatic reindexing of changed documents"""
    try:
        print("🔄 Starting automatic reindexing...")

        # This would call the ingestion script for changed documents
        # For now, just log the changes
        if new_files:
            print(f"📥 Would reindex new files: {list(new_files)[:3]}...")
        if modified_files:
            print(f"🔄 Would reindex modified files: {list(modified_files)[:3]}...")

        print("✅ Auto-reindexing completed (simulated)")

    except Exception as e:
        print(f"❌ Error during auto-reindexing: {e}")

def update_user_profile(user_id, message, response):
    """Update user profile based on interaction patterns"""
    if user_id not in user_profiles:
        user_profiles[user_id] = {
            'total_messages': 0,
            'language': 'ru',  # Default
            'topics': {},
            'style': 'formal',  # formal/casual/technical
            'last_active': time.time()
        }

    profile = user_profiles[user_id]
    profile['total_messages'] += 1
    profile['last_active'] = time.time()

    # Detect language
    try:
        from langdetect import detect
        profile['language'] = detect(message)
    except:
        pass

    # Analyze topics from message
    message_lower = message.lower()
    topics = {
        'telephony': ['ватс', 'телефон', 'sip', 'бизнес-телефон'],
        'internet': ['интернет', 'подключение', 'тариф', 'скорость'],
        'billing': ['счет', 'оплата', 'тариф', 'эсф', 'авр'],
        'technical': ['настройка', 'конфигурация', 'оборудование']
    }

    for topic, keywords in topics.items():
        if any(keyword in message_lower for keyword in keywords):
            profile['topics'][topic] = profile['topics'].get(topic, 0) + 1

    # Analyze communication style
    if any(word in message_lower for word in ['плиз', 'пожалуйста', 'спасибо', 'извините']):
        profile['style'] = 'polite'
    elif any(word in message_lower for word in ['быстрее', 'срочно', 'немедленно']):
        profile['style'] = 'urgent'
    elif len(message.split()) > 20:
        profile['style'] = 'detailed'

    save_user_profiles()

load_user_profiles()

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Initialize RAG Engine
rag = None

def save_feedback():
    """Save feedback data to file"""
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
    with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(feedback_data, f, ensure_ascii=False, indent=2)

# Функция check_dangerous_content импортируется из src.security.content_filter

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feedback buttons (like/dislike)"""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith('feedback_'):
        return

    # Parse feedback data: feedback_{message_id}_{rating}
    parts = data.split('_')
    if len(parts) != 3:
        return

    message_id = int(parts[1])
    rating = parts[2]  # 'like' or 'dislike'

    user_id = query.from_user.id

    # Store feedback
    if str(message_id) not in feedback_data:
        feedback_data[str(message_id)] = {}

    feedback_data[str(message_id)][str(user_id)] = {
        'rating': rating,
        'timestamp': time.time(),
        'user_id': user_id
    }

    save_feedback()

    # Update message with feedback confirmation
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("👍 Спасибо за отзыв!", callback_data="none")
    ]])

    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except:
        pass  # Message might be too old to edit

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hello! I am the Kcell RAG Bot. Ask me anything about the documents, and I'll check the archives for you."
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics and feedback"""
    user_id = update.effective_user.id if update.effective_user else None

    # Only allow authorized users to see stats
    if ALLOWED_IDS and user_id not in ALLOWED_IDS:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Доступ ограничен.")
        return

    # Calculate feedback stats
    total_feedback = 0
    likes = 0
    dislikes = 0

    for msg_id, msg_feedback in feedback_data.items():
        for user_fb in msg_feedback.values():
            total_feedback += 1
            if user_fb['rating'] == 'like':
                likes += 1
            elif user_fb['rating'] == 'dislike':
                dislikes += 1

    satisfaction_rate = (likes / max(total_feedback, 1)) * 100

    stats_text = f"""📊 Статистика Kae Bot:

Обратная связь:
• Всего оценок: {total_feedback}
• 👍 Понравилось: {likes}
• 👎 Не понравилось: {dislikes}
• 📈 Уровень удовлетворенности: {satisfaction_rate:.1f}%

Топ проблемных тем: [в разработке]
Рекомендации по улучшению: [в разработке]"""

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=stats_text
    )

async def clear_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear conversation memory for current user"""
    user_id = update.effective_user.id if update.effective_user else None

    if user_id in conversation_memory:
        conversation_memory[user_id] = []

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🧠 Память разговора очищена. Теперь каждый вопрос будет рассматриваться независимо."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id if update.effective_user else None

    # Access control
    if ALLOWED_IDS and user_id not in ALLOWED_IDS:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Доступ ограничен.")
        return

    # Simple rate limiting
    now = time.time()
    bucket = user_buckets.get(user_id, [])
    bucket = [t for t in bucket if now - t <= RATE_WINDOW]
    if len(bucket) >= RATE_MAX:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Слишком часто, попробуйте позже.")
        return
    bucket.append(now)
    user_buckets[user_id] = bucket

    # Basic prompt/abuse filter
    if len(user_text or "") > 1000:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Запрос слишком длинный.")
        return

    # Check for dangerous content
    is_dangerous, danger_reason, danger_response = check_dangerous_content(user_text)
    if is_dangerous:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=danger_response)
        return

    # Update conversation memory
    if user_id not in conversation_memory:
        conversation_memory[user_id] = []
    conversation_memory[user_id].append({
        'text': user_text,
        'timestamp': now,
        'role': 'user'
    })
    # Keep only recent messages
    conversation_memory[user_id] = conversation_memory[user_id][-MEMORY_SIZE:]

    # Build context from conversation history
    conversation_context = ""
    if len(conversation_memory[user_id]) > 1:
        recent_messages = conversation_memory[user_id][-3:]  # Use last 3 messages for context
        context_parts = []
        for msg in recent_messages[:-1]:  # Exclude current message
            context_parts.append(f"Предыдущий вопрос: {msg['text']}")
        conversation_context = "\n".join(context_parts) + "\n\n"

    # Notify user we are thinking
    status_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔍 Ищу в документах..."
    )

    try:
        if rag:
            # Combine conversation context with current question
            full_query = conversation_context + user_text
            result = rag.answer_question(full_query)

            if isinstance(result, dict):
                response = result["answer"]
                sources = result.get("sources", [])
                confidence = result.get("confidence", 0)
                reasoning = result.get("reasoning", 0)

                # Format the response with metadata
                if sources:
                    source_lines = ["📚 Источники:"]
                    for source_info in sources:
                        if isinstance(source_info, dict):
                            source_name = source_info.get('source', 'Unknown')
                            contribution = source_info.get('contribution', 0)
                            citations = source_info.get('citations', [])

                            source_line = f"{source_name} - {contribution}% вклада"
                            source_lines.append(source_line)

                            # Add citations if available
                            if citations:
                                for citation in citations:
                                    # Clean and format citation
                                    citation = citation.strip('"').strip('.').strip('"')
                                    if len(citation) > 120:
                                        citation = citation[:117] + "..."
                                    source_lines.append(f"   💬 «{citation}»")
                                source_lines.append("")  # Empty line after citations
                            else:
                                source_lines.append("")  # Empty line even without citations
                        else:
                            # Backward compatibility for old format
                            source_lines.append(source_info)
                    source_text = "\n" + "\n".join(source_lines)
                else:
                    source_text = "\n\n📚 Источники: не найдены"

                confidence_text = f"\n\n🎯 Уверенность: {confidence}% из документов, {reasoning}% самостоятельное мышление"

                full_response = response + source_text + confidence_text

                # Store bot response in memory
                conversation_memory[user_id].append({
                    'text': response,
                    'timestamp': time.time(),
                    'role': 'assistant'
                })
                conversation_memory[user_id] = conversation_memory[user_id][-MEMORY_SIZE:]
            else:
                # Backward compatibility for old responses
                full_response = result
        else:
            full_response = "RAG Engine not initialized. Please check server logs."

        # Add feedback buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👍 Полезно", callback_data=f"feedback_{status_msg.message_id}_like"),
                InlineKeyboardButton("👎 Не точно", callback_data=f"feedback_{status_msg.message_id}_dislike")
            ]
        ])

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=full_response,
            reply_markup=keyboard
        )
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=f"Произошла ошибка: {e}"
        )

    # ... (existing handlers)

async def handle_compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the document comparison flow."""
    user_id = update.effective_user.id
    comparison_state[user_id] = {'step': 'wait_orig'}
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔄 <b>Режим сравнения документов</b>\n\nПожалуйста, отправьте <b>оригинальный файл</b> (Версия 1).",
        parse_mode="HTML"
    )

async def process_comparison(update: Update, context: ContextTypes.DEFAULT_TYPE, file_path_2: str):
    user_id = update.effective_user.id
    state = comparison_state.get(user_id)
    if not state or 'file1' not in state:
        return

    path1 = state['file1']
    path2 = file_path_2
    
    status_msg = await update.message.reply_text("⏳ Сравниваю документы...")
    
    try:
        # We need to replicate server structure: uploads/compare_temp/{session_id}/
        session_id = str(uuid.uuid4())
        session_dir = os.path.join("uploads", "compare_temp", session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        # Move files to session dir
        new_path1 = os.path.join(session_dir, "original_" + os.path.basename(path1))
        new_path2 = os.path.join(session_dir, "modified_" + os.path.basename(path2))
        
        shutil.move(path1, new_path1)
        shutil.move(path2, new_path2)
        
        # Run comparison
        result = comparator.compare_files(new_path1, new_path2)
        
        # Add metadata
        result['session_id'] = session_id
        result['filenames'] = {
            'original': os.path.basename(new_path1).replace("original_", ""),
            'modified': os.path.basename(new_path2).replace("modified_", "")
        }
        
        # Save JSON for Web UI
        with open(os.path.join(session_dir, "result.json"), "w", encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
            
        # Clear state
        del comparison_state[user_id]
        
        # Return Link
        # Replace localhost with actual IP if deployed, but for now locahost or hardcoded
        # Assuming we run server on port 8000
        web_link = f"http://localhost:8000/compare/{session_id}"
        
        stats = result.get('stats', {})
        summary = f"""✅ <b>Сравнение завершено!</b>
        
➕ Добавлено: {stats.get('added', 0)} строк
➖ Удалено: {stats.get('deleted', 0)} строк
✏️ Изменено: {stats.get('modified', 0)} блоков

🔗 <a href="{web_link}">Открыть отчет о сравнении</a>"""

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=summary,
            parse_mode="HTML"
        )
        
    except Exception as e:
        await context.bot.edit_message_text(
             chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=f"❌ Ошибка при сравнении: {e}"
        )
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads for 'teaching' the bot."""
    document = update.message.document
    user_id = update.effective_user.id if update.effective_user else None

    # Access control - only authorized users can upload documents
    if ALLOWED_IDS and user_id not in ALLOWED_IDS:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Доступ к загрузке документов ограничен.")
        return

    # Check file size (limit to 10MB)
    if document.file_size and document.file_size > 10 * 1024 * 1024:
        await update.message.reply_text("❌ Файл слишком большой (максимум 10MB).")
        return

    # Check file type
    allowed_extensions = ['.pdf', '.docx', '.txt', '.xlsx', '.pptx', '.md']
    file_ext = os.path.splitext(document.file_name)[1].lower()
    if file_ext not in allowed_extensions:
        await update.message.reply_text(f"❌ Неподдерживаемый формат файла. Разрешены: {', '.join(allowed_extensions)}")
        return

    if file_ext not in allowed_extensions:
        await update.message.reply_text(f"❌ Неподдерживаемый формат файла. Разрешены: {', '.join(allowed_extensions)}")
        return

    # Check comparison state
    if user_id in comparison_state:
        state = comparison_state[user_id]
        file = await document.get_file()
        
        # Temp save
        timestamp = int(time.time())
        temp_path = os.path.join("uploads", "temp_incoming", f"{user_id}_{timestamp}_{document.file_name}")
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        await file.download_to_drive(temp_path)
        
        if state['step'] == 'wait_orig':
            comparison_state[user_id]['file1'] = temp_path
            comparison_state[user_id]['step'] = 'wait_mod'
            await update.message.reply_text("✅ Оригинал принят.\n\nТеперь отправьте <b>измененный файл</b> (Версия 2).", parse_mode="HTML")
            return
            
        elif state['step'] == 'wait_mod':
            await process_comparison(update, context, temp_path)
            return

    try:
        # Standard ingestion flow starts here
        file = await document.get_file()

        # Save file with timestamp to avoid conflicts
        timestamp = int(time.time())
        safe_filename = f"{timestamp}_{document.file_name.replace(' ', '_')}"
        file_path = os.path.join(config.DOCS_DIR, "learned", safe_filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        await file.download_to_drive(file_path)

        # Send initial confirmation
        status_msg = await update.message.reply_text(
            f"📥 Загружаю {document.file_name}...\n⏳ Обрабатываю документ..."
        )

        # Ingest immediately
        import subprocess
        process = subprocess.run(
            ["python3", "ingest_file.py", file_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if process.returncode == 0:
            # Success message
            success_text = f"""✅ Документ успешно изучен!

📄 Файл: {document.file_name}
📊 Статус: Добавлен в базу знаний
🤖 Теперь вы можете задавать вопросы об этом документе!

💡 Подсказка: Попробуйте спросить "Что сказано в {document.file_name} о..." """

            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=success_text
            )
        else:
            # Error message
            error_text = f"""⚠️ Проблема при обработке документа

📄 Файл: {document.file_name}
❌ Ошибка: {process.stderr[:500]}...

Попробуйте:
• Проверить формат файла
• Убедиться, что файл не поврежден
• Связаться с администратором"""

            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=error_text
            )

    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏰ Обработка документа занимает слишком много времени. Попробуйте позже или обратитесь к администратору.")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при загрузке файла: {str(e)[:200]}")

def main():
    global rag
    if not config.GEMINI_API_KEY:
        print("CRITICAL: GEMINI_API_KEY is missing. Bot cannot function correctly.")
    
    # Initialize RAG (will load DB)
    try:
        rag = RAGEngine()
        print("RAG Engine initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize RAG Engine: {e}")

    application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    stats_handler = CommandHandler('stats', stats)
    start_handler = CommandHandler('start', start)
    stats_handler = CommandHandler('stats', stats)
    clear_handler = CommandHandler('clear', clear_memory)
    compare_handler = CommandHandler('compare', handle_compare_command) # New
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    doc_handler = MessageHandler(filters.Document.ALL, handle_document) # New handler
    feedback_handler = CallbackQueryHandler(handle_feedback)  # Feedback handler

    application.add_handler(start_handler)
    application.add_handler(stats_handler)
    application.add_handler(start_handler)
    application.add_handler(stats_handler)
    application.add_handler(clear_handler)
    application.add_handler(compare_handler) # Add new handler
    application.add_handler(message_handler)
    application.add_handler(doc_handler)
    application.add_handler(feedback_handler)
    
    print("Bot is polling...")
    # Print bot info
    async def post_init(application):
        bot = await application.bot.get_me()
        print(f"BOT_USERNAME: @{bot.username}")

    application.post_init = post_init
    application.run_polling()

if __name__ == '__main__':
    main()
