# Tutor — фронтенд

Веб-интерфейс чата с ИИ-помощником (Tutor) на Next.js. Работает с реальным Langflow-потоком `flow/tutor-flow.json`.

```
Браузер  →  Next.js (/tutor)  →  POST /api/tutor/chat  →  Langflow (/api/v1/run/<flow_id>)  →  RAG / модель
            ^ UI, markdown        ^ серверный прокси: ключ API остаётся на сервере
```

## Быстрый старт

Нужно: Node.js 20+, Docker, запущенные Ollama и языковая модель (gpt2giga) — см. `README.md` ветки.

```bash
# 1. Настройки (один файл на всё)
cp .env.example .env
#   заполните LANGFLOW_SUPERUSER_PASSWORD и TUTOR_DB_* / OLLAMA_* (см. README),
#   LANGFLOW_API_KEY и TUTOR_FLOW_ID заполните на шаге 3

# 2. Запуск Langflow
chmod +x tutor-local.sh
./tutor-local.sh start                 # Windows: docker compose -f docker-compose.yml -f docker-compose.tutor.yml up -d --build
#   Langflow: http://127.0.0.1:7860 (логин langflow / пароль из LANGFLOW_SUPERUSER_PASSWORD)

# 3. В интерфейсе Langflow:
#    а) импортируйте flow/tutor-flow.json и проверьте модели/прокси (как в README)
#    б) скопируйте ID потока из адресной строки  .../flow/<ID>   -> TUTOR_FLOW_ID
#    в) Settings → Langflow API Keys → Create   -> LANGFLOW_API_KEY
#    (после правки .env перезапускать Langflow не нужно — только фронтенд)

# 4. Фронтенд
npm install
npm run dev                            # http://localhost:3000  -> редирект на /tutor
```

Для production: `npm run build && npm start`.

## Проверка

1. Откройте `http://localhost:3000/tutor`. Индикатор справа вверху должен показывать **«Tutor онлайн»**.
   - «Нет связи» — Langflow не запущен или неверный `LANGFLOW_URL`.
   - «Требуется настройка» — не заполнен `TUTOR_FLOW_ID`.
2. Три проверки из README (Playground), только теперь через интерфейс:
   - `Привет!` → короткий ответ (маршрут `NO_RAG`);
   - `Реши за меня задание и дай готовый ответ для сдачи.` → вежливый отказ (`RESTRICTED`);
   - `Объясни условие задачи, что такое ESG.` → ответ по материалам (`COURSE_RAG`).
3. Быстрая проверка API без UI:
   ```bash
   curl http://localhost:3000/api/tutor/status
   curl -X POST http://localhost:3000/api/tutor/chat -H 'Content-Type: application/json' \
        -d '{"message":"Привет!","sessionId":"test-session-0001"}'
   ```
4. Для отладки поставьте `TUTOR_DEBUG=1` — в уведомлениях об ошибках появятся «Технические детали».

## Что умеет интерфейс

- Несколько чатов: создание, переключение, переименование, удаление (с подтверждением).
- Каждый чат — отдельный `session_id` в Langflow, т.е. отдельная память диалога.
- История хранится в браузере (localStorage), отдельно для каждого пользователя.
- Markdown в ответах: заголовки, списки, таблицы, ссылки, код с кнопкой «Копировать».
- Остановка запроса, повтор при ошибке, подсказки при пустом чате, счётчик символов (лимит 4000).
- Понятные ошибки: нет связи, неверный ключ, не найден flow, таймаут, ошибка модели и т.д.
- Адаптивность (мобильный drawer со списком чатов), доступность (aria, фокус, клавиатура: Enter — отправить, Shift+Enter — перенос).

## Структура кода

```
src/app/tutor/page.tsx              страница /tutor (заголовок + <TutorChat />)
src/app/api/tutor/chat/route.ts     прокси к Langflow
src/app/api/tutor/status/route.ts   проверка Langflow и настроек
src/components/tutor/               UI-компоненты (TutorChat — главный)
src/components/tutor/Avatars.tsx    иконки бота и пользователя — менять здесь
src/lib/tutor/server/               конфиг и клиент Langflow (только сервер)
src/lib/tutor/client/               API-клиент, хранилище чатов, хук статуса
src/lib/tutor/errors.ts             тексты ошибок для пользователя
src/lib/tutor/constants.ts          приветствие, подсказки, лимиты
```

## Интеграция с остальными страницами

1. **Layout.** `<TutorChat />` занимает 100% высоты и ширины родителя и не задаёт фон страницы. Положите его в общий layout (сайдбар, фон, шапка) — заголовок «Чат с ИИ-помощником (Tutor)» находится в `src/app/tutor/page.tsx`, его можно заменить на общий.
2. **Пользователь.** Передайте реального пользователя: `<TutorChat user={{ id: String(user.id) }} />`. По `id` разделяются истории чатов и `session_id` в Langflow. Без `user` используется анонимный id браузера.
3. **Защита API.** Роуты `/api/tutor/*` сейчас открыты. После появления авторизации добавьте в `route.ts` проверку сессии и берите `userId` оттуда, а не из тела запроса.
4. **Формат запроса.** Для потока из ветки `main` (guarded-flow, JSON-вход) поставьте `TUTOR_INPUT_MODE=json`.
5. **Хранение истории на сервере.** Весь доступ к хранилищу — `src/lib/tutor/client/storage.ts` (`loadChats` / `saveChats`); замените реализацию на вызовы бэкенда.
6. **Конфликты стилей.** Используется Tailwind CSS 4 (`@import "tailwindcss"`), свои классы начинаются с `tutor-` (см. `globals.css`).

## Частые проблемы

| Симптом                           | Причина / решение                                                                                                                                     |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| «Нет связи»                       | `./tutor-local.sh start` не запущен; Langflow слушает только `127.0.0.1:7860` — фронтенд должен быть на той же машине, иначе поменяйте `LANGFLOW_URL` |
| «Нет доступа к сервису Tutor»     | неверный/пустой `LANGFLOW_API_KEY`                                                                                                                    |
| «Сценарий Tutor не найден»        | неверный `TUTOR_FLOW_ID` (после повторного импорта flow ID меняется)                                                                                  |
| «Tutor не смог обработать запрос» | смотрите `docker compose logs -f langflow`: чаще всего недоступны gpt2giga, Ollama или БД                                                             |
| Ответ не приходит долго           | первый запрос к модели медленный; лимит — `TUTOR_REQUEST_TIMEOUT_MS`                                                                                  |
| Правка `.env` не применилась      | перезапустите `npm run dev` / `npm start`                                                                                                             |
