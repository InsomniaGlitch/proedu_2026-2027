from os import PathLike
from telebot import TeleBot
from telebot.types import Message
import json
from time import time
from functools import wraps

def _needs_reset(parameter: str = '', recommended_option: str = '') -> bool:
    """
    Starts infinite loop prompting for reset.
    Reseting option, `parameter`, and `recommended_option` can be specified. 

    Returns `True` if the user's response is positive. 

    Raises `ValueError` if `recommended_option` is invalid.
    """
    if parameter: parameter += ' '
    if not recommended_option:
        options = 'y/n'
    elif recommended_option == 'y':
        options = 'Y/n'
    elif recommended_option == 'n':
        options = 'y/N'
    else:
        raise ValueError("recommended_option takes only 'y' as Yes and 'n' as No. Default = 'y/n'.")
    
    while True:
        needs_parameter = input(f"Do you want to reset {parameter}now ({options}): ").strip().lower()
        if needs_parameter in ('y', 'n'): break

    return True if needs_parameter == 'y' else False

def _fill_space(text: str, max_len: int) -> str:
    "Returns centered string with spaces on either side"
    return text.center(max_len + 2)

def _update_lists(message: Message, 
                 config: dict[str, str | int | bool | list], 
                 config_path: PathLike, 
                 visitors: list[int], access_list: list[int], current_list: list[int] = None) -> None:
    "Flushes provided lists into config."
    user_id = message.from_user.id

    if user_id not in visitors:
        visitors.append(user_id)
    config['visited_users'] = visitors
    visitors.clear()

    if current_list is not None:
        access_list.extend(current_list)
        config['access_list'] = list(set(access_list))
        current_list.clear()
    
    with open(config_path, 'w') as f:
        json.dump(config, f)

def in_blacklist(user_id: int, access_list: list[int]) -> bool:
    "Returns True if user_id is in the specified access_list"
    if not user_id:
        raise ValueError("user_id argument is empty.")
    if not access_list:
        raise ValueError("access_list argument is empty.")

    return user_id in access_list

def validate_config(absolute_path: PathLike, config: dict[str, str | int | bool | list]) -> tuple[str, int, str, int, list]: 
    """
    Validates several config values and, if any of them are invalid, prompts the user to make 
    corrections. Returns tuple[TOKEN, USER_ID, PASSWORD, ACCESS_TYPE, ACCESS_LIST]
    """
    API_TOKEN: str = config['BOT_TOKEN']
    if not API_TOKEN:
        raise ValueError("BOT_TOKEN is empty. See 'README.md' before starting.")
    USER_ID: int = config['BOT_USER_ID']
    if not USER_ID:
        raise ValueError("BOT_USER_ID is empty. See 'README.md' for instructions.")

    pwcheck: bool = config['PASSWORD_CHECK']
    if not isinstance(pwcheck, bool):
        print('PASSWORD_CHECK value is invalid.')
        if _needs_reset():
            print("If PASSWORD_CHECK is True you will be asked to set the password.")
            while True:
                needs_pwcheck = input("Enable password check (y/n): ").strip().lower()
                if needs_pwcheck == 'y':
                    pwcheck = True
                    break
                if needs_pwcheck == 'n':
                    pwcheck = False
                    break
        else:
            pwcheck = False
            print("Password check is disabled.")

    PW: str = config['BOT_PASSWORD']
    if pwcheck:
        if len(PW.strip()) <= 4:
            print("Provided password is too simple!")
            if _needs_reset(recommended_option='y'):
                while True:
                    PW = input("Password: ")
                    if len(PW.strip()) > 4: break

                    print("New password is too simple.")
            else:
                config['PASSWORD_CHECK'] = False
                print("This reminder will not appear again.")

    
    access_list_type: int = config['access_list_type']
    if access_list_type not in (-1, 0, 1):
        print("access_list_type value seems to be incorrect.")
        if _needs_reset(recommended_option='y'):
            print("-1 stands for blacklist, 1 for whitelist. 0 disables any access lists.")
            while True:
                new_alt = int(input("New access list type: ").strip())
                if new_alt not in (-1, 0, 1): break
        else:
            new_alt = 0
            print("Access list is disabled.")
    else:
        new_alt = access_list_type

    access_list: list[list[int]] = config['access_list']
    new_list = []
    if new_alt == 0:
        if access_list:
            print("Access list is not empty, but it is disabled!")
    else:
        for user_id in access_list:
            try:
                new_list.apppend(int(user_id))
            except:
                raise TypeError(f"User's id must be an integer, but {type(user_id), user_id} was provided.")
    
    config['PASSWORD_CHECK'] = pwcheck
    config['BOT_PASSWORD'] = PW
    config['access_list_type'] = new_alt

    with open(absolute_path, 'w') as f:
        json.dump(config, f)

    return API_TOKEN, USER_ID, PW, new_alt, new_list


def type_check(bot: TeleBot, message: Message, msg_type: str) -> Message | bool:
    "Returns Message object if message type is unsuitable, otherwise False"
    sent_msg = False
    if message.content_type != msg_type:
        sent_msg = bot.send_message(message.chat.id, f"Send {msg_type}")
    return sent_msg

def make_table(content: list[list], name: str) -> str:
    "Returns table as a string"
    if name:
        print(name.upper())
    
    columns = []
    c = len(content[0])

    for i in range(c):
        cols = []
        for row in content:
            cols.append(str(row[i]))
        columns.append(cols)
    
    lens = [len(max(col, key=len)) for col in columns]
    i = 0
    string_table = ""
    for row in content:
        for column in row:
            string_table += f"{_fill_space(str(column), lens[i % c])}|"
            i += 1
        string_table += "\n"

    return string_table

def is_csv(message: Message) -> bool:
    "Returns True if document in the message is a CSV file"
    if message.content_type == 'document':
        return message.document.file_name.lower().endswith('.csv')
    return False

def is_sub_in(sub: str, array: list[str]) -> bool:
    "Returns True if a substring  is present in any of the arrays's strings"
    return any(sub in string for string in array)

def update(message: Message, 
           config: dict[str, str | int | bool | list], 
           config_path: PathLike, access_type: int,
           visitors: list[int], access_list: list[int], current_list: list[int] = None) -> None:
    "Calls _update_lists depending on access_type"
    if access_type == 0:
        _update_lists(message, config, config_path, visitors, access_list)
    else:
        _update_lists(message, config, config_path, visitors, access_list, current_list)

def cooldown(bot: TeleBot, seconds: int) -> function:
    "Decorator. Adds cooldown for a command (although works with any passed message). Must go after @bot decorator."
    user_cooldowns = {}

    def decorator(func):
        @wraps(func)
        def wrapper(message, *args, **kwargs):
            user_id = message.from_user.id
            chat_id = message.chat.id
            current_time = time()

            if user_id in user_cooldowns:
                time_passed = current_time - user_cooldowns[user_id]
                if time_passed < seconds:
                    time_left = int(seconds - time_passed)
                    bot.send_message(chat_id, f"Wait {time_left} seconds.")
                    return

            user_cooldowns[user_id] = current_time
            return func(message, *args, **kwargs)
        return wrapper
    return decorator