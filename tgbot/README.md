# TelegramBot-CSV-INSERTER

Позволяет наполнять базу данных с помощью Telegram-бота.

## Установка

1. Установите Python 3.14+.

2. Склонируйте репозиторий

    ```bash
    mkdir tgbot_csv_inserter
    cd tgbot_csv_inserter
    git clone --no-checkout --depth 1 https://github.com/InsomniaGlitch/proedu_2026-2027/ .
    git sparse-checkout init
    git sparse-checkout set "tgbot_csv_inserter/*"
    git checkout database
    ```

## Быстрый старт

1. Перейдите к [@BotFather](https://telegram.me/botfather) в Telegram, чтобы получить `BOT_TOKEN` вашего бота и ваш `USER_ID`. Внесите эти данные в файл `config.json`.
2. Установите систему управления базами данных, например [PostgreSQL](https://www.postgresql.org/download/). Заполните все поля, относящиеся к базе данных, в файле `config.json`.
3. Установите параметр `access_list_type`:

    - -1 — режим черного списка;
    - 0 — проверка доступа отключена;
    - 1 — режим белого списка.

4. Если для `access_list_type` установлено значение 0, этот шаг можно пропустить. В противном случае заполните `access_list` идентификаторами пользователей (user ID).

    - В режиме черного списка пользователи, чьи ID указаны в `access_list`, не смогут использовать основные команды (`/structure`, `/table`, `/csv`).
    - В режиме белого списка доступ будет только у пользователей, чьи ID есть в списке; остальные будут игнорироваться. Если выбран режим белого списка, но `access_list` остался пустым, доступ будет только у владельца бота.

5. После выполнения предыдущих шагов откройте терминал в директории, содержащей файл `bot.py`. Установите зависимости:

    ```bash
    pip install -r requirements.txt
    ```

6. Запустите его командой:

    ```bash
    python bot.py
    ```

### Функции

- `/start`, `/help` – подсказка с командами
- `/pw` – ввод пароля, если есть
- `/structure` – вывод струтуры БД
- `/table` – вывод первых нескольких строк таблицы
- `/csv` – отправка CSV файла в указанную таблицу
