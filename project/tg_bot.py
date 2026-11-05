import os
import io
import json
import uuid
import hashlib
import threading
import requests
import telebot
import psycopg2
import PyPDF2
import docx
from psycopg2.extras import DictCursor
from telebot import types
from dotenv import load_dotenv

load_dotenv()

TG_TOKEN = os.getenv("TG_TOKEN")
LANGFLOW_URL = os.getenv("LANGFLOW_URL")
API_KEY = os.getenv("LANGFLOW_API_KEY")
TUTOR_FLOW_ID = os.getenv("TUTOR_FLOW_ID")
REVIEWER_FLOW_ID = os.getenv("REVIEWER_FLOW_ID")

bot = telebot.TeleBot(TG_TOKEN)


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


# --- РАБОТА С БД (Только для авторизации) ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def check_user_exists(telegram_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (str(telegram_id),))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result is not None
    except:
        return False


def register_user(telegram_id, username, password):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (telegram_id, username, password_hash, role) VALUES (%s, %s, %s, 'student')",
            (str(telegram_id), username, hash_password(password))
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print("Ошибка регистрации:", e)
        return False


def verify_login(telegram_id, password):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute("SELECT password_hash FROM users WHERE telegram_id = %s", (str(telegram_id),))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result and result['password_hash'] == hash_password(password)
    except:
        return False


def get_user_role(telegram_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute("SELECT role FROM users WHERE telegram_id = %s", (str(telegram_id),))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['role'] if result else 'student'
    except:
        return 'student'


# --- РАБОТА С LANGFLOW ---
def send_to_langflow(flow_id, payload_dict, expect_json=False):
    url = f"{LANGFLOW_URL}/api/v1/run/{flow_id}"
    payload = {
        "input_value": json.dumps(payload_dict, ensure_ascii=False),
        "input_type": "chat",
        "output_type": "chat",
        "session_id": payload_dict.get("run_id", str(uuid.uuid4())),
    }
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=300)  # Ждем до 5 минут
        response.raise_for_status()
        body = response.json()
        # Извлекаем текст ответа
        text_response = body["outputs"][0]["outputs"][0]["results"]["message"]["text"]
        if expect_json:
            return json.loads(text_response)
        return {"text": text_response}
    except Exception as e:
        print(f"Ошибка Langflow: {e}")
        return None


# --- СЦЕНАРИЙ РЕГИСТРАЦИИ ---
@bot.message_handler(commands=['start'])
def start_message(message):
    tg_id = message.from_user.id
    if check_user_exists(tg_id):
        msg = bot.send_message(message.chat.id, "С возвращением! Введите пароль:")
        bot.register_next_step_handler(msg, process_login)
    else:
        msg = bot.send_message(message.chat.id, "Привет! Придумайте пароль для регистрации:")
        bot.register_next_step_handler(msg, process_registration)


def process_registration(message):
    password = message.text.strip()
    tg_id = message.from_user.id
    username = message.from_user.username or "User"
    if register_user(tg_id, username, password):
        bot.send_message(message.chat.id, "✅ Регистрация успешна! Вы Студент.")
    else:
        bot.send_message(message.chat.id, "❌ Ошибка БД при регистрации.")


def process_login(message):
    if verify_login(message.from_user.id, message.text.strip()):
        bot.send_message(message.chat.id, "✅ Вход выполнен!")
    else:
        bot.send_message(message.chat.id, "❌ Неверный пароль.")


# --- ОТПРАВКА ФАЙЛА И ПРОВЕРКА (Reviewer) ---
@bot.message_handler(content_types=['document'])
def handle_document(message):
    tg_id = message.from_user.id
    bot.reply_to(message, "⏳ Извлекаю текст из файла...")

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text = ""
        if message.document.mime_type == 'application/pdf':
            reader = PyPDF2.PdfReader(io.BytesIO(downloaded_file))
            for page in reader.pages: text += page.extract_text() or ""
        elif message.document.mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            doc = docx.Document(io.BytesIO(downloaded_file))
            for para in doc.paragraphs: text += para.text + "\n"

        if not text.strip():
            return bot.reply_to(message, "Не удалось извлечь текст.")

        # Запускаем фоновый процесс проверки
        threading.Thread(target=run_review_process, args=(message.chat.id, tg_id, text)).start()

    except Exception as e:
        bot.reply_to(message, f"Ошибка при чтении файла: {e}")


def run_review_process(chat_id, tg_id, text):
    run_id = str(uuid.uuid4())

    # 1. Отправляем работу на сохранение (submit)
    bot.send_message(chat_id, "💾 Сохраняю работу в базу данных...")
    submit_payload = {
        "action": "submit",
        "telegram_id": tg_id,
        "run_id": run_id,
        "text": text
    }
    submit_res = send_to_langflow(REVIEWER_FLOW_ID, submit_payload, expect_json=True)

    if not submit_res or submit_res.get("processing_status") == "error":
        return bot.send_message(chat_id, f"❌ Ошибка при сохранении: {submit_res.get('error_code', 'Unknown')}")

    # 2. Запускаем проверку (review)
    bot.send_message(chat_id, "🧠 Reviewer проверяет вашу работу (это займет пару минут)...")
    review_payload = {
        "action": "review",
        "telegram_id": tg_id,
        "run_id": run_id
    }
    review_res = send_to_langflow(REVIEWER_FLOW_ID, review_payload, expect_json=True)

    if not review_res or review_res.get("processing_status") == "error":
        return bot.send_message(chat_id, f"❌ Ошибка проверки: {review_res.get('error_code', 'Unknown')}")

    # 3. Выводим результат
    result = review_res.get("result", {})
    feedback = result.get("feedback_text", "Нет текста замечаний.")

    bot.send_message(chat_id, f"✅ **Проверка завершена!**\n\n{feedback}")


# --- ОБЫЧНЫЕ ТЕКСТОВЫЕ СООБЩЕНИЯ (Tutor) ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if not check_user_exists(message.from_user.id):
        return bot.reply_to(message, "Сначала пройдите регистрацию /start")

    tg_id = message.from_user.id
    bot.send_chat_action(message.chat.id, 'typing')

    # Отправляем вопрос в Tutor (guarded-flow)
    tutor_payload = {
        "action": "ask",
        "telegram_id": tg_id,
        "run_id": str(uuid.uuid4()),
        "text": message.text
    }
    res = send_to_langflow(TUTOR_FLOW_ID, tutor_payload)

    if res and "text" in res:
        bot.reply_to(message, res["text"])
    elif res:
        bot.reply_to(message, str(res))  # Если формат другой
    else:
        bot.reply_to(message, "❌ Ошибка связи с Langflow.")


print("🤖 Бот запущен!")
bot.polling(none_stop=True)