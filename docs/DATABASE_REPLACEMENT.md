# Замена тестовой БД на `sustainability_course_db`

Пошаговая инструкция: как перевести Tutor со старой тестовой базы на обновлённую базу из ветки `database`
(файл [`database_state/sustainability_course_db.dump`](https://github.com/InsomniaGlitch/proedu_2026-2027/blob/database/database_state/sustainability_course_db.dump)).

> [!IMPORTANT]
> Инструкция **не удаляет** старую базу: новая создаётся рядом, Tutor переключается через `.env`. Откат — в [разделе 9](#9-откат).

## Содержание

1. [Что изменилось и зачем](#1-что-изменилось-и-зачем)
2. [Что внутри дампа](#2-что-внутри-дампа)
3. [Получите дамп](#3-получите-дамп)
4. [Поднимите базу и восстановите дамп](#4-поднимите-базу-и-восстановите-дамп)
5. [Создайте пользователя только на чтение и обновите `.env`](#5-создайте-пользователя-только-на-чтение-и-обновите-env)
6. [Обновите Flow и проверьте компоненты](#6-обновите-flow-и-проверьте-компоненты)
7. [Перезапустите и проверьте](#7-перезапустите-и-проверьте)
8. [Если что-то не работает](#8-если-что-то-не-работает)
9. [Откат](#9-откат)

---

## 1. Что изменилось и зачем

Раньше Tutor читал только `public.document_chunks` и показывал студенту «Документ №N», потому что названий документов в тестовой базе не было.
В новой базе есть таблица `public.documents` с именами файлов (`filename`), поэтому:

| Файл                                          | Что изменено                                                                                                                                                                       |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `custom_components/postgres_course_search.py` | SQL делает `LEFT JOIN public.documents` и берёт `filename`. В заголовок каждого фрагмента добавлено `document_title=…`. Понятная ошибка, если в базе нет нужных таблиц или колонок. |
| `custom_components/sources_formatter.py`      | Читает `document_title` из заголовков и выводит в «Источниках» название документа вместо «Документ №N». Если названия нет — запасной вариант «Документ №N».                         |
| `flow/tutor-flow.json`                        | Код обоих компонентов внутри Flow обновлён (он хранится в JSON отдельно от `.py`-файлов). В системном промпте RAG-агента уточнено правило про названия документов.                   |
| `tutor-local.sh`                              | Проверка БД при `start` теперь читает обе таблицы и выводит число документов и фрагментов.                                                                                         |

Формат заголовка фрагмента — контракт между двумя компонентами:

```
[1; document_id=5; chunk_id=100; cosine_distance=0.2149; document_title=1.3. Вызовы антропоцена]
```

Ответ студента теперь заканчивается так:

```
Источники:
- 1.3. Вызовы антропоцена
- 1.2. Осознание глобальных проблем
```

Название берётся из базы, а не от модели: форматтер по-прежнему принимает только пары `document_id:chunk_id`, которые реально были в найденном контексте.

---

## 2. Что внутри дампа

Дамп создан `pg_dump` **18.6** в custom-формате (`-Fc`), база называется `sustainability_course_db`.

**Таблицы, которые использует Tutor:**

| Таблица                  | Поля                                                                                |
| ------------------------ | ----------------------------------------------------------------------------------- |
| `public.documents`       | `id`, `text`, `filename varchar(260)`                                               |
| `public.document_chunks` | `id`, `document_id → documents.id`, `content`, `category`, `embedding vector(1024)` |

Остальные таблицы (`users`, `chat_sessions`, `messages`, `submissions`, `reviews`, `grades`, …) принадлежат другим веткам и в дампе **пустые**. Tutor к ним доступа не получает.

**Данные** (проверено разбором дампа): 15 документов, 493 фрагмента, у всех фрагментов есть вектор размерности 1024 (модель `BAAI/bge-m3` — совместима с `bge-m3:latest` в Ollama).

| `documents.id` | `filename` (как хранится)                                     | Фрагментов | Как увидит студент                                      |
| :------------: | ------------------------------------------------------------- | :--------: | ------------------------------------------------------- |
| 1              | `0.1. O курсе.txt`                                            | 14         | 0.1. O курсе                                            |
| 2              | `0.2. Введение.txt`                                           | 11         | 0.2. Введение                                           |
| 3              | `1.1. Экологическая устойчивость и экологические кризисы.txt` | 31         | 1.1. Экологическая устойчивость и экологические кризисы |
| 4              | `1.2. Осознание глобальных проблем.txt`                       | 23         | 1.2. Осознание глобальных проблем                       |
| 5              | `1.3. Вызовы антропоцена.txt`                                 | 76         | 1.3. Вызовы антропоцена                                 |
| 6              | `2.1. Социальные системы.txt`                                 | 32         | 2.1. Социальные системы                                 |
| 7              | `2.2. Стратегическое планирование.txt`                        | 56         | 2.2. Стратегическое планирование                        |
| 8              | `3.1. Алгоритм решения задач управления.txt`                  | 61         | 3.1. Алгоритм решения задач управления                  |
| 9              | `3.2. Концепция Run — Change — Disrupt Model.txt`             | 13         | 3.2. Концепция Run — Change — Disrupt Model             |
| 10             | `4.1. Стратегии устойчивого развития.txt`                     | 52         | 4.1. Стратегии устойчивого развития                     |
| 11             | `4.2. Проекты устойчивого развития.txt`                       | 24         | 4.2. Проекты устойчивого развития                       |
| 12             | `4.3. Отчетность об устойчивом развитии.txt`                  | 60         | 4.3. Отчетность об устойчивом развитии                  |
| 13             | `Приложение 1.txt`                                            | 3          | Приложение 1                                            |
| 14             | `Приложение 2.txt`                                            | 18         | Приложение 2                                            |
| 15             | `Приложение 3.txt`                                            | 19         | Приложение 3                                            |

> [!NOTE]
> В `documents.id = 1` в имени файла латинская «O» (`0.1. O курсе`). Это данные в базе, а не ошибка Tutor. Исправить можно командой `UPDATE documents SET filename = '0.1. О курсе.txt' WHERE id = 1;` (владелец базы).

Расширение `.txt` при показе скрывается. Если у документа пустое имя, студент увидит «Документ №N».

---

## 3. Получите дамп

Дамп лежит в ветке `database`. Не коммитьте его в ветку `tutor` (в `.gitignore` добавлено `*.dump`).

Самый надёжный способ, одинаковый для Linux, macOS и Windows (`curl.exe`), — скачать файл напрямую:

```bash
curl -L -o sustainability_course_db.dump \
  https://github.com/InsomniaGlitch/proedu_2026-2027/raw/database/database_state/sustainability_course_db.dump
```

Размер ≈ 2,9 МБ. Не используйте `git show … > файл` в PowerShell: перенаправление портит бинарные файлы.

Быстрая проверка, что файл целый (первые 5 байт — `PGDMP`):

```bash
head -c 5 sustainability_course_db.dump; echo
```

---

## 4. Поднимите базу и восстановите дамп

> [!WARNING]
> **Нужен `pg_restore` версии 17 или новее.** Дамп сделан в PostgreSQL 18, и `pg_restore` 15/16 отвечает
> `pg_restore: error: unsupported version (1.16) in file header`. Кроме того, на сервере должно быть расширение **pgvector**.
> Поэтому самый простой путь — отдельный контейнер `pgvector/pgvector:pg18`: в нём есть и то и другое.

### Вариант A (рекомендуемый): отдельный контейнер

1. Запустите контейнер (пароль администратора придумайте свой; он нужен только для восстановления):

```bash
docker run -d --name tutor-course-db \
  -e POSTGRES_PASSWORD='ПАРОЛЬ_АДМИНИСТРАТОРА' \
  -v tutor-course-db-data:/var/lib/postgresql \
  -p 127.0.0.1:5433:5432 \
  pgvector/pgvector:pg18
```

Порт `5433` на хосте нужен только для ваших ручных проверок; Langflow подключается по имени контейнера внутри Docker-сети.

2. Создайте базу и восстановите дамп **одной транзакцией** (при любой ошибке ничего не останется наполовину):

```bash
docker exec tutor-course-db createdb -U postgres sustainability_course_db
docker cp sustainability_course_db.dump tutor-course-db:/tmp/sustainability_course_db.dump
docker exec tutor-course-db pg_restore -U postgres -d sustainability_course_db \
  --no-owner --no-privileges --single-transaction --exit-on-error \
  /tmp/sustainability_course_db.dump
docker exec tutor-course-db rm /tmp/sustainability_course_db.dump
```

Если контейнер ещё запускается, подождите несколько секунд и повторите `createdb`.

3. Проверьте результат:

```bash
docker exec -i tutor-course-db psql -U postgres -d sustainability_course_db <<'SQL'
SELECT count(*) AS documents FROM public.documents;                                  -- 15
SELECT count(*) AS chunks    FROM public.document_chunks;                            -- 493
SELECT count(*) AS no_vector FROM public.document_chunks WHERE embedding IS NULL;    -- 0
SELECT vector_dims(embedding) AS dims, count(*) FROM public.document_chunks GROUP BY 1; -- 1024 | 493
SELECT d.id, d.filename, count(c.id) AS chunks
FROM public.documents d LEFT JOIN public.document_chunks c ON c.document_id = d.id
GROUP BY d.id ORDER BY d.id;                                                         -- 15 строк, см. таблицу выше
SQL
```

### Вариант Б: уже есть свой PostgreSQL

Подходит, если на сервере установлен pgvector, а `pg_restore` у вас версии 17+ (можно запустить его из контейнера: `docker run --rm -v "$PWD:/d:ro" pgvector/pgvector:pg18 pg_restore …`).

```bash
createdb -h ХОСТ -U АДМИН sustainability_course_db
pg_restore -h ХОСТ -U АДМИН -d sustainability_course_db \
  --no-owner --no-privileges --single-transaction --exit-on-error \
  sustainability_course_db.dump
```

Дамп содержит `CREATE EXTENSION vector`; для него нужны права суперпользователя (или pgvector должен быть уже установлен в этой базе).

> [!CAUTION]
> Не восстанавливайте дамп поверх существующей рабочей базы и не запускайте `pg_restore --clean` в общей проектной БД без согласования с командой. Ваша задача — отдельная база для Tutor.

---

## 5. Создайте пользователя только на чтение и обновите `.env`

### 5.1. Пользователь только на чтение

Tutor должен видеть **только** `documents` и `document_chunks` (в остальных таблицах будут пользователи и хэши паролей).

```bash
docker exec -i tutor-course-db psql -U postgres -d sustainability_course_db <<'SQL'
CREATE ROLE tutor_ro LOGIN PASSWORD 'ПАРОЛЬ_TUTOR_RO';
GRANT CONNECT ON DATABASE sustainability_course_db TO tutor_ro;
GRANT USAGE ON SCHEMA public TO tutor_ro;
GRANT SELECT ON public.documents, public.document_chunks TO tutor_ro;
SQL
```

> [!NOTE]
> Права нужны на **обе** таблицы. Если выдать только `document_chunks` (как было раньше), поиск упадёт с `permission denied for table documents`.

### 5.2. Пароль в Base64

```bash
# Linux / macOS
printf '%s' 'ПАРОЛЬ_TUTOR_RO' | base64
```

```powershell
# Windows PowerShell
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('ПАРОЛЬ_TUTOR_RO'))
```

### 5.3. Правки в `.env`

Откройте `.env` (шаблон — `.env.example`) и замените блок БД. Формат — только `KEY=value`, без кавычек и пробелов вокруг `=`.

| Переменная              | Было (старая тестовая БД) | Стало (вариант A)                        |
| ----------------------- | ------------------------- | ---------------------------------------- |
| `TUTOR_DB_CONTAINER`    | имя старого контейнера    | `tutor-course-db`                        |
| `TUTOR_DB_HOST`         | адрес старой БД           | `tutor-course-db`                        |
| `TUTOR_DB_PORT`         | `5432`                    | `5432` (внутри Docker-сети, **не** 5433) |
| `TUTOR_DB_NAME`         | имя старой базы           | `sustainability_course_db`               |
| `TUTOR_DB_USER`         | старый пользователь       | `tutor_ro`                               |
| `TUTOR_DB_PASSWORD_B64` | старый пароль             | Base64 из шага 5.2                       |

Запишите старые значения (или закомментируйте строки) — они понадобятся для [отката](#9-откат).

Для варианта Б (свой сервер): `TUTOR_DB_CONTAINER` оставьте пустым или укажите контейнер сервера, `TUTOR_DB_HOST` — адрес, доступный **из контейнера Langflow** (например, `host.docker.internal`).

Остальные настройки (`OLLAMA_BASE_URL`, `OLLAMA_EMBEDDING_MODEL=bge-m3:latest`) не меняются.

---

## 6. Обновите Flow и проверьте компоненты

Код компонентов хранится **в двух местах**: в `custom_components/*.py` и внутри самого Flow. Langflow выполняет код из Flow, поэтому одной замены `.py`-файлов недостаточно — без обновления Flow студент по-прежнему увидит «Документ №N».

В `flow/tutor-flow.json` код уже обновлён. Выберите один из способов.

### Способ 1 (рекомендуемый): заново импортировать Flow

1. В Langflow (http://127.0.0.1:7860) импортируйте `flow/tutor-flow.json`.
2. Заново настройте модели (Router, Agent ×3, Language Model) и прокси: ключи в JSON пустые.
3. Проверьте в узле **PostgreSQL Course Search**: `Embedding Model` = `bge-m3:latest` (Ollama), `Top K` и `Maximum Cosine Distance` (см. [ниже](#порог-cosine-distance)).
4. Скопируйте новый ID потока из адреса `.../flow/<ID>` в `TUTOR_FLOW_ID` в `.env` — **после каждого импорта ID меняется**.
5. Старый Flow можно удалить, когда убедитесь, что новый работает.

### Способ 2: обновить код в существующем Flow (ID не меняется)

Для **каждого** из двух узлов:

1. Откройте узел → кнопка **Code** (`</>`).
2. Полностью замените код содержимым соответствующего файла:
   - `PostgreSQL Course Search` → `custom_components/postgres_course_search.py`
   - `Sources Formatter` → `custom_components/sources_formatter.py`
3. Нажмите **Check & Save**. Входы и выходы узлов не менялись, соединения сохранятся.
4. В системном промпте RAG-агента (узел `Agent`, к которому подключён поиск) в правиле 10 добавьте предложение: «Название документа можно упоминать в ответе только в том виде, как оно указано в заголовке фрагмента (document_title).»

### Проверка, что в Flow именно новый код

В узле **Sources Formatter** в коде должна быть функция `collect_headers`, а в **PostgreSQL Course Search** — `LEFT JOIN {DOCUMENTS_TABLE}`. Если их нет — Flow всё ещё со старым кодом.

### Порог cosine distance

Значения порога по умолчанию (`1.0` в Flow, `0.5` в коде) подбирались для тестовой базы и **не откалиброваны** для новой. Чтобы подобрать порог, посмотрите расстояния для типичных вопросов напрямую в БД:

```bash
EMB=$(curl -s http://localhost:11434/api/embeddings \
  -d '{"model":"bge-m3:latest","prompt":"что такое антропоцен"}' \
  | python3 -c "import sys,json;print('['+','.join(map(str,json.load(sys.stdin)['embedding']))+']')")

docker exec -i tutor-course-db psql -U postgres -d sustainability_course_db -c "
SELECT c.id AS chunk_id, d.filename, round((c.embedding <=> '$EMB'::vector)::numeric, 4) AS distance
FROM public.document_chunks c JOIN public.documents d ON d.id = c.document_id
ORDER BY c.embedding <=> '$EMB'::vector LIMIT 10;"
```

Проверьте несколько вопросов по курсу и несколько посторонних (например, про рецепты) и выберите порог между ними.

---

## 7. Перезапустите и проверьте

```bash
./tutor-local.sh start
```

(Windows/вручную: `docker compose -f docker-compose.yml -f docker-compose.tutor.yml up -d --build`, а контейнер БД подключите к сети Langflow сами.)

Каталог `custom_components` монтируется в контейнер, но Langflow читает компоненты при запуске — перезапуск обязателен.

**Ожидаемый вывод скрипта** (в конце):

```
PostgreSQL доступен: database=sustainability_course_db, user=tutor_ro, documents=15, document_chunks=493
```

**Проверка в Playground / чате** (маршрут `RAG`):

| Вопрос                                        | Ожидание                                                                                        |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `Что такое антропоцен и какие у него вызовы?` | Ответ по материалам; блок «Источники» с **названиями**, например `- 1.3. Вызовы антропоцена`    |
| `Привет!`                                     | Короткий ответ без поиска и без источников                                                      |
| `Расскажи рецепт борща`                       | «В найденных материалах не обнаружено достаточно релевантной информации…» (если порог подобран) |

Чек-лист:

- [ ] В «Источниках» нет строк «Документ №N».
- [ ] Названия совпадают с `documents.filename` (без `.txt`).
- [ ] В деталях выполнения узла поиска в заголовках фрагментов есть `document_title=…`.
- [ ] Статус `Sources Formatter` — `VALID_SOURCE_IDS`.

Эти же вопросы можно задать в веб-чате (`npm run dev`, http://localhost:3000/tutor). Не забудьте обновить `TUTOR_FLOW_ID`, если импортировали Flow заново.

---

## 8. Если что-то не работает

| Симптом                                                               | Причина и решение                                                                                                                  |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `pg_restore: error: unsupported version (1.16) in file header`        | `pg_restore` старше 17. Используйте контейнер `pgvector/pgvector:pg18` ([вариант A](#вариант-a-рекомендуемый-отдельный-контейнер)). |
| `extension "vector" is not available`                                 | На сервере нет pgvector. Используйте образ `pgvector/pgvector`.                                                                    |
| `database … already exists` / `relation … already exists` при restore | Восстанавливать нужно в **пустую** базу. Создайте новую (`createdb`) или удалите неудавшуюся: `dropdb`.                            |
| `permission denied for table documents`                               | Пользователю не выдан `SELECT` на `documents` (шаг 5.1).                                                                           |
| «Схема базы не подходит компоненту…» в логах Langflow                 | Подключена не та база: нет `public.documents` или колонки `filename`. Проверьте `TUTOR_DB_NAME`.                                   |
| В источниках по-прежнему «Документ №N»                                | В Flow остался старый код компонентов ([раздел 6](#6-обновите-flow-и-проверьте-компоненты)) либо у документа пустой `filename`.    |
| `Embedding dimension is …; expected 1024`                             | Выбрана неподходящая Embedding Model. Нужна `bge-m3:latest`.                                                                       |
| «Не удалось проверить источники этого ответа»                         | Модель нарушила формат `USED_SOURCES` (не связано с БД). См. README → «Источники».                                                 |
| `./tutor-local.sh start` падает на проверке PostgreSQL                | Контейнер БД не в сети Langflow или неверный `TUTOR_DB_HOST`. Для варианта A хост = имя контейнера, порт = `5432`.                 |
| Фронтенд пишет «Сценарий Tutor не найден»                             | После повторного импорта Flow изменился ID — обновите `TUTOR_FLOW_ID` и перезапустите `npm run dev`.                               |

Логи Langflow: `docker compose -f docker-compose.yml -f docker-compose.tutor.yml logs -f langflow`.

---

## 9. Откат

Старая база не тронута. Чтобы вернуться:

1. В `.env` верните старые значения `TUTOR_DB_*`.
2. Верните прежние версии компонентов и Flow из Git. Новый поиск требует таблицу `documents`, поэтому со старой базой он работать не будет:

   ```bash
   git checkout <коммит_до_обновления> -- custom_components flow tutor-local.sh
   ```

   Затем заново импортируйте `flow/tutor-flow.json` (или вставьте старый код в узлы) и обновите `TUTOR_FLOW_ID`.
3. Перезапустите Langflow: `./tutor-local.sh start`.

Удалить новую базу целиком (данные в контейнере будут потеряны):

```bash
docker rm -f tutor-course-db
docker volume rm tutor-course-db-data
```
