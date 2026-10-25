import os
import json
import signal, sys
from time import sleep
from telebot import TeleBot
from helpers import *
from query import *

print("Initializing...")

abs_path_cur_folder = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(abs_path_cur_folder, 'config.json')

try:
    with open(config_path, 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    raise FileNotFoundError("Ensure that a non-empty 'config.json' file is located in the same folder as the 'bot.py' file.")

ATTEMPTS = 5
VISITORS = config['visited_users']
VERIFIED_USERS = []

API_TOKEN, USER_ID, PW, ACCESS_TYPE, ACCESS_LIST = validate_config(config_path, config)

ENGINE = setup_engine(
    dbms=config['DBMS'],
    db_host=config['DATABASE_HOST'],
    db_port=config['DATABASE_PORT'],
    db_name=config['DB_NAME'],
    db_login=config['DB_LOGIN'],
    db_password=config['DB_PASSWORD'],
    driver=config['DRIVER']
)

db_structure = inspect_database(ENGINE)

try:
    bot = TeleBot(API_TOKEN)
except ValueError:
    raise ValueError("BOT_TOKEN value is invalid.")

if ACCESS_TYPE != 0:
    buffer_list = []

is_running = True
def shutdown(signum, frame):
    global is_running
    print("Shutting down...")

    bot.stop_polling()
    is_running = False

    ENGINE.dispose()

    sys.exit(0)
signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

def is_allowed(message):
    "Return True if the user is verified and is not in the banned_list"
    if ACCESS_TYPE == 0:
        return True
    else:
        user_id = message.from_user.id
        return (user_id in VERIFIED_USERS) and (user_id not in buffer_list)

@bot.message_handler(commands=['table'], func=is_allowed)
def ask_table_limit(message):
    update(message, config, config_path, ACCESS_TYPE, VISITORS, ACCESS_LIST)

    sent_msg = bot.send_message(message.chat.id, "Set table name")
    bot.register_next_step_handler(sent_msg, ask_table, is_insert=False)

@bot.message_handler(commands=['csv'], func=is_allowed)
def ask_csv(message):
    update(message, config, config_path, ACCESS_TYPE, VISITORS, ACCESS_LIST)

    sent_msg = bot.send_message(message.chat.id, "Sent table name")
    bot.register_next_step_handler(sent_msg, ask_table, is_insert=True)

@bot.message_handler(commands=['structure'], func=is_allowed)
@cooldown(bot, 10)
def send_db_structure(message):
    update(message, config, config_path, ACCESS_TYPE, VISITORS, ACCESS_LIST)
    bot.send_message(message.chat.id, str(db_structure))

@bot.message_handler(func=is_allowed)
def prompt_verified(message):
    update(message, config, config_path, ACCESS_TYPE, VISITORS, ACCESS_LIST)

    chat_id = message.chat.id
    bot.send_message(chat_id, "/structure to see current database structure. /table to see head of the table")
    bot.send_message(
        chat_id, 
        "ATTENTION! The structure of the CSV file must exactly match the structure of the database table. " \
        "If you are unsure, use the /structure or /table command.")
    bot.send_message(chat_id, "If you are ready – send /csv")

@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    update(message, config, config_path, ACCESS_TYPE, VISITORS, ACCESS_LIST)
    bot.send_message(message.chat.id, "Hi. If you don't know how to use me, you don't need to use me. /pw")

@bot.message_handler(commands=['pw'])
@cooldown(bot, 30)
def get_password(message):
    update(message, config, config_path, ACCESS_TYPE, VISITORS, ACCESS_LIST)

    chat_id = message.chat.id
    if PW:
        sent_instigation = bot.send_message(chat_id, "Try")
    else:
        sent_instigation = bot.send_message(chat_id, "You lucky (type anything)")
    bot.register_next_step_handler(sent_instigation, check_password, attempt=1)

@bot.message_handler(func=lambda message: True)
def prompt_commands(message):
    update(message, config, config_path, ACCESS_TYPE, VISITORS, ACCESS_LIST)

    user_id = message.from_user.id
    chat_id = message.chat.id

    if ACCESS_TYPE == -1:
        if user_id not in buffer_list:
            if in_blacklist(user_id, ACCESS_LIST):
                buffer_list.append(user_id)
                bot.send_message(chat_id, "This is a private party")
            bot.send_message(chat_id, "/start")
        else:
            bot.send_message(chat_id, "This is a private party")

    else:
        bot.send_message(chat_id, "/start")


def check_password(message, attempt):
    chat_id = message.chat.id
    if sent_msg := type_check(bot, message, 'text'):
        bot.register_next_step_handler(sent_msg, check_password, attempt=1)
        return

    user_id = message.from_user.id
    if not PW:
        if user_id not in VERIFIED_USERS:
            VERIFIED_USERS.append(user_id)
        bot.reply_to(message, f"{message.text}? What do you mean, Master?")
        return
    
    password = message.text

    if password == '/cancel':
        bot.send_message(chat_id, "Cancelled")
        return
    
    if password == PW:
        sent_msg = bot.send_message(chat_id, "Welcome, Master")
        if user_id not in VERIFIED_USERS:
            VERIFIED_USERS.append(user_id)
        return

    if attempt >= ATTEMPTS:
        bot.send_message(chat_id, "Too many attempts. Try again later")
    else:
        next_attempt = attempt + 1
        sent_msg = bot.send_message(chat_id, "Wrong. Try again or /cancel")

        bot.register_next_step_handler(sent_msg, check_password, attempt=next_attempt)
        return

def ask_table(message, is_insert):
    chat_id = message.chat.id
    if sent_msg := type_check(bot, message, 'text'):
        bot.register_next_step_handler(sent_msg, ask_table, is_insert=is_insert)
        return

    table = message.text

    if table == '/cancel':
        bot.send_message(chat_id, "Cancelled")
        return

    if table not in db_structure:
        sent_msg = bot.send_message(chat_id, f"There is no table '{table}'. Try again or /cancel")
        bot.register_next_step_handler(sent_msg, ask_table, is_insert=is_insert)
        return
    
    if not is_insert:
        sent_msg = bot.send_message(chat_id, "Set number of rows (1-5) or /skip")
        bot.register_next_step_handler(sent_msg, ask_limit, table=table)
    else:
        sent_msg = bot.send_message(chat_id, "Send CSV document")
        bot.register_next_step_handler(sent_msg, get_csv, table=table)

def ask_limit(message, table):
    chat_id = message.chat.id
    if sent_msg := type_check(bot, message, 'text'):
        bot.register_next_step_handler(sent_msg, ask_limit, table)

    limit = message.text

    if limit == '/skip':
        limit = 3
        bot.send_message(chat_id, "Number of rows is set to 3")

    try:
        limit = int(limit)
    except Exception:
        err_warn = f"Can't convert {message.text} to integer"
        print(err_warn)
        sent_msg = bot.send_message(chat_id, f"{err_warn}. Try again or /skip")
        bot.register_next_step_handler(sent_msg, ask_limit, table=table)
        return

    if not (1 <= limit <= 5):
        sent_msg = bot.send_message(chat_id, "Rows amount must be >= 1 and <= 5). Try again or /skip")
        bot.register_next_step_handler(sent_msg, ask_limit, table=table)
        return

    head = list_head(ENGINE, db_structure, table, limit)
    result = make_table(head, table)

    bot.send_message(chat_id, result)

def get_csv(message, table):
    chat_id = message.chat.id

    if message.text and message.text == '/cancel':
        bot.send_message(chat_id, 'Cancelled')
        return

    contype = message.content_type
    if contype != 'document':
        sent_msg = bot.send_message(chat_id, f"Send document, not {contype}, or /cancel")
        bot.register_next_step_handler(sent_msg, get_csv, table=table)
        return

    if not is_csv(message):
        sent_msg = bot.send_message(chat_id, "Send CSV or /cancel")
        bot.register_next_step_handler(sent_msg, get_csv, table=table)
        return

    file_name = message.document.file_name
    file_info = bot.get_file(message.document.file_id)

    sent_msg = bot.send_message(chat_id, f"Received: {file_name}. Send delimiter in one message without quotes (default=','). /skip if delimiter is defauit")
    bot.register_next_step_handler(sent_msg, get_delimiter, file_name=file_name, file_info=file_info, table=table)

def get_delimiter(message, file_name, file_info, table):
    chat_id = message.chat.id

    if message.content_type != 'text':
        sent_msg = bot.send_message(chat_id, "Send text or /cancel")
        bot.register_next_step_handler(sent_msg, get_delimiter, file_name=file_name, table=table)
        return

    delimiter = message.text

    if delimiter == '/skip':
        delimiter = ','
        bot.send_message(chat_id, 'Set to default')

    if delimiter == '/cancel':
        bot.send_message(chat_id, 'Cancelled')
        return

    downloaded_bytes = bot.download_file(file_info.file_path)

    try:
        insert_csv(downloaded_bytes, delimiter, table, ENGINE)
    except Exception as e:
        exception = f"Failed on insertion: {e}"
        bot.send_message(chat_id, f"{exception[:250]}..")
        print(exception)
        return

    print("Waiting for file insertion...")
    sleep(3)
    bot.send_message(chat_id, f"Insertion of {file_name} is completed")

print("Starting bot...")
bot.infinity_polling()
