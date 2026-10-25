"""Проверка подключения к GigaChat API.

Берёт ключ авторизации из файла .env рядом со скриптом, получает access token,
показывает доступные модели и задаёт один тестовый вопрос.
Сам ключ скрипт никуда не выводит.
"""

import os
import sys
import uuid
from pathlib import Path

import requests
import urllib3

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
API_URL = "https://gigachat.devices.sberbank.ru/api/v1"


def load_env(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ssl_verify():
    # GigaChat использует сертификат НУЦ Минцифры, которого нет в системе по умолчанию.
    ca_bundle = os.environ.get("GIGACHAT_CA_BUNDLE")
    if ca_bundle:
        return ca_bundle
    if os.environ.get("GIGACHAT_INSECURE") == "1":
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return False
    return True


def get_token(auth_key, scope, verify):
    response = requests.post(
        OAUTH_URL,
        headers={
            "Authorization": f"Basic {auth_key}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        data={"scope": scope},
        timeout=30,
        verify=verify,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def main():
    load_env(Path(__file__).with_name(".env"))
    auth_key = os.environ.get("GIGACHAT_AUTH_KEY", "")
    scope = os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    if not auth_key or auth_key == "вставь_сюда":
        sys.exit("Нет ключа: впиши GIGACHAT_AUTH_KEY в файл .env рядом со скриптом.")

    verify = ssl_verify()
    try:
        token = get_token(auth_key, scope, verify)
    except requests.exceptions.SSLError:
        sys.exit(
            "Ошибка SSL: нужен корневой сертификат НУЦ Минцифры.\n"
            "Для быстрой проверки добавь в .env строку GIGACHAT_INSECURE=1 и запусти снова."
        )
    except requests.HTTPError as exc:
        sys.exit(f"Не удалось получить токен: HTTP {exc.response.status_code}. "
                 "Проверь ключ авторизации и scope.")
    print("Токен получен.")

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    models = requests.get(f"{API_URL}/models", headers=headers, timeout=30, verify=verify)
    models.raise_for_status()
    names = [m["id"] for m in models.json().get("data", [])]
    print("Доступные модели:", ", ".join(names) or "(список пуст)")

    model = os.environ.get("GIGACHAT_MODEL", "GigaChat")
    reply = requests.post(
        f"{API_URL}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Одним предложением: что такое устойчивое развитие?"}],
            "temperature": 0.1,
        },
        timeout=60,
        verify=verify,
    )
    reply.raise_for_status()
    body = reply.json()
    print(f"\nОтвет {model}:", body["choices"][0]["message"]["content"])
    print("Токены:", body.get("usage"))
    print("\nПодключение работает.")


if __name__ == "__main__":
    main()
