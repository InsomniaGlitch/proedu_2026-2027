#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
TUTOR_COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.tutor.yml"

# Единый файл настроек: .env (общий для Docker Compose, этого скрипта и фронтенда).
# Для обратной совместимости поддерживается старый .env.tutor.
ENV_FILE="${SCRIPT_DIR}/.env"
if [[ ! -f "$ENV_FILE" && -f "${SCRIPT_DIR}/.env.tutor" ]]; then
    ENV_FILE="${SCRIPT_DIR}/.env.tutor"
fi

fail() {
    printf 'E: %s\n' "$*" >&2
    exit 1
}

read_env() {
    local key="$1"
    awk -F= -v key="$key" '
        $1 == key {
            sub(/^[^=]*=/, "")
            sub(/\r$/, "")
            gsub(/^[ \t]+|[ \t]+$/, "")
            print
            exit
        }
    ' "$ENV_FILE"
}

# Значение задано и не является заглушкой YOUR_...
env_is_set() {
    local value
    value="$(read_env "$1")"
    [[ -n "$value" && "$value" != YOUR_* ]]
}

[[ -f "$COMPOSE_FILE" ]] || fail "Не найден $COMPOSE_FILE"
[[ -f "$TUTOR_COMPOSE_FILE" ]] || fail "Не найден $TUTOR_COMPOSE_FILE"
[[ -f "$ENV_FILE" ]] || fail "Не найден файл настроек .env. Выполните: cp .env.example .env"
[[ -f "${SCRIPT_DIR}/custom_components/postgres_course_search.py" ]] ||
    fail "Не найден компонент PostgreSQL Course Search."
[[ -f "${SCRIPT_DIR}/custom_components/sources_formatter.py" ]] ||
    fail "Не найден компонент Sources Formatter."

chmod 600 "$ENV_FILE"

PROJECT="$(read_env TUTOR_COMPOSE_PROJECT)"
PROJECT="${PROJECT:-$(basename "$SCRIPT_DIR" | tr '[:upper:]' '[:lower:]')}"
[[ "$PROJECT" =~ ^[a-z0-9][a-z0-9_-]*$ ]] ||
    fail "Некорректное имя Docker Compose проекта: $PROJECT"

DB_CONTAINER="$(read_env TUTOR_DB_CONTAINER)"
DB_HOST="$(read_env TUTOR_DB_HOST)"
OLLAMA_SERVICE="$(read_env TUTOR_OLLAMA_SERVICE)"
STOP_DB="$(read_env TUTOR_STOP_DB_ON_STOP)"
STOP_OLLAMA="$(read_env TUTOR_STOP_OLLAMA_SERVICE_ON_STOP)"
COMPOSE_NETWORK="$(read_env TUTOR_COMPOSE_NETWORK)"
STOP_DB="${STOP_DB:-0}"
STOP_OLLAMA="${STOP_OLLAMA:-0}"
COMPOSE_NETWORK="${COMPOSE_NETWORK:-${PROJECT}_default}"

# --- Режим эмбеддингов --------------------------------------------------
# Логика совпадает с embeddings_provider() в postgres_course_search.py:
# явное TUTOR_EMBEDDINGS_PROVIDER важнее; иначе 'api', если задан
# TUTOR_EMBEDDINGS_BASE_URL, иначе 'ollama' (обратная совместимость).
# В режиме api сервер и модель эмбеддингов можно задавать прямо в узле
# Langflow, поэтому в .env они необязательны.
EMBEDDINGS_PROVIDER="$(read_env TUTOR_EMBEDDINGS_PROVIDER | tr '[:upper:]' '[:lower:]')"
if [[ -z "$EMBEDDINGS_PROVIDER" ]]; then
    if [[ -n "$(read_env TUTOR_EMBEDDINGS_BASE_URL)" ]]; then
        EMBEDDINGS_PROVIDER="api"
    else
        EMBEDDINGS_PROVIDER="ollama"
    fi
fi

EMBEDDINGS_HINT=""
case "$EMBEDDINGS_PROVIDER" in
    api)
        # Сервер и модель вводятся в Langflow; в .env ничего обязательного нет.
        EMBEDDINGS_REQUIRED=()
        ;;
    ollama)
        EMBEDDINGS_REQUIRED=(OLLAMA_BASE_URL OLLAMA_EMBEDDING_MODEL)
        EMBEDDINGS_HINT=" Чтобы задавать сервер и модель эмбеддингов в Langflow, укажите TUTOR_EMBEDDINGS_PROVIDER=api."
        ;;
    *)
        fail "В файле настроек ($(basename "$ENV_FILE")) задан неизвестный TUTOR_EMBEDDINGS_PROVIDER: '$EMBEDDINGS_PROVIDER' (ожидается ollama или api)."
        ;;
esac

for key in TUTOR_DB_HOST TUTOR_DB_NAME TUTOR_DB_USER \
           TUTOR_DB_PASSWORD_B64 \
           ${EMBEDDINGS_REQUIRED[@]+"${EMBEDDINGS_REQUIRED[@]}"}; do
    value="$(read_env "$key")"
    [[ -n "$value" && "$value" != YOUR_* ]] ||
        fail "В файле настроек ($(basename "$ENV_FILE")) не задан $key (или стоит заглушка YOUR_...).${EMBEDDINGS_HINT}"
done

if [[ "$DB_CONTAINER" == YOUR_* ]]; then
    fail "Замени TUTOR_DB_CONTAINER в .env на имя своего PostgreSQL-контейнера."
fi

DOCKER=()

as_root() {
    if [[ "$EUID" -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        return 127
    fi
}

select_docker() {
    command -v docker >/dev/null 2>&1 || fail "Команда docker не найдена."

    if docker info >/dev/null 2>&1; then
        DOCKER=(docker)
        return
    fi

    if command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
        DOCKER=(sudo docker)
        return
    fi

    # Если Docker daemon не запущен, пробуем запустить его в поддерживаемом init.
    if command -v rc-service >/dev/null 2>&1; then
        as_root rc-service docker start >/dev/null 2>&1 || true
    elif command -v systemctl >/dev/null 2>&1; then
        as_root systemctl start docker >/dev/null 2>&1 || true
    fi

    for ((attempt = 1; attempt <= 30; attempt++)); do
        if docker info >/dev/null 2>&1; then
            DOCKER=(docker)
            return
        fi
        if command -v sudo >/dev/null 2>&1 &&
           sudo docker info >/dev/null 2>&1; then
            DOCKER=(sudo docker)
            return
        fi
        sleep 1
    done

    fail "Docker daemon недоступен. Запусти Docker и повтори команду."
}

docker_run() {
    "${DOCKER[@]}" "$@"
}

compose() {
    docker_run compose \
        -p "$PROJECT" \
        --project-directory "$SCRIPT_DIR" \
        -f "$COMPOSE_FILE" \
        -f "$TUTOR_COMPOSE_FILE" \
        "$@"
}

start_ollama_service_if_configured() {
    [[ -n "$OLLAMA_SERVICE" ]] || return 0

    if command -v rc-service >/dev/null 2>&1; then
        as_root rc-service "$OLLAMA_SERVICE" start
    elif command -v systemctl >/dev/null 2>&1; then
        as_root systemctl start "$OLLAMA_SERVICE"
    else
        printf 'W: сервис Ollama автоматически не запущен; проверю доступность из Langflow.\n' >&2
    fi
}

container_networks() {
    docker_run inspect \
        --format '{{range $name, $config := .NetworkSettings.Networks}}{{println $name}}{{end}}' \
        "$1"
}

first_container_network() {
    container_networks "$1" | awk 'NF { print; exit }'
}

container_has_network() {
    local networks
    networks="$(container_networks "$1")"
    grep -Fxq -- "$2" <<<"$networks"
}

ollama_probe() {
    docker_run exec -i "$1" python - <<'PY'
import json
import os
import sys
from urllib.request import urlopen

base = os.environ["OLLAMA_BASE_URL"].rstrip("/")
expected = os.environ["OLLAMA_EMBEDDING_MODEL"]

try:
    with urlopen(base + "/api/tags", timeout=5) as response:
        models = json.loads(response.read().decode("utf-8")).get("models", [])
except Exception as exc:
    print(f"Ollama API недоступна по {base}: {type(exc).__name__}: {exc}", file=sys.stderr)
    raise SystemExit(1)

names = [item.get("name", "") for item in models]
base_name = expected.split(":", 1)[0]
match = next(
    (name for name in names if name == expected or name.split(":", 1)[0] == base_name),
    None,
)
if not match:
    print(
        f"Модель {expected} не найдена в Ollama. "
        f"Установи её на хосте командой: ollama pull {base_name}",
        file=sys.stderr,
    )
    raise SystemExit(1)

print(f"Ollama доступна; модель найдена: {match}")
PY
}

check_ollama() {
    local container_id="$1"
    local output=""
    local attempt

    for ((attempt = 1; attempt <= 30; attempt++)); do
        if output="$(ollama_probe "$container_id" 2>&1)"; then
            printf '%s\n' "$output"
            return 0
        fi
        sleep 1
    done

    printf 'E: Не удалось проверить Ollama из Langflow:\n%s\n' "$output" >&2
    return 1
}

embeddings_probe() {
    docker_run exec -i "$1" python - <<'PY'
import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Размерность колонки document_chunks.embedding (vector(1024)).
EXPECTED_DIMENSION = 1024


def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        print(f"В контейнере Langflow не задана переменная {name}.", file=sys.stderr)
        raise SystemExit(1)
    return value


base = required("TUTOR_EMBEDDINGS_BASE_URL").rstrip("/")
model = required("TUTOR_EMBEDDINGS_MODEL")
key = os.getenv("TUTOR_EMBEDDINGS_API_KEY", "").strip()
dimensions_raw = os.getenv("TUTOR_EMBEDDINGS_DIMENSIONS", "").strip()

# Повторяем запрос компонента: тот же model, тот же dimensions (если задан).
payload = {"model": model, "input": "проверка Tutor"}
if dimensions_raw:
    try:
        payload["dimensions"] = int(dimensions_raw)
    except ValueError:
        print("TUTOR_EMBEDDINGS_DIMENSIONS должен быть целым числом.", file=sys.stderr)
        raise SystemExit(1)

headers = {"Content-Type": "application/json"}
if key:
    # Правило lfx: ПРОПИСНОЕ_ИМЯ -> переменная окружения, иначе -> литеральный ключ.
    token = os.environ.get(key, key) if key.replace("_", "").isupper() else key
    headers["Authorization"] = f"Bearer {token}"

request = Request(
    base + "/embeddings",
    data=json.dumps(payload).encode("utf-8"),
    headers=headers,
)
try:
    with urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
except HTTPError as exc:
    body = exc.read(300).decode("utf-8", "replace")
    print(
        f"Сервер эмбеддингов {base}/embeddings ответил HTTP {exc.code}: {body}",
        file=sys.stderr,
    )
    raise SystemExit(1)
except Exception as exc:
    print(
        f"Эмбеддинги недоступны по {base}/embeddings: "
        f"{type(exc).__name__}: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(1)

rows = data.get("data") or []
if not rows:
    print("Сервер эмбеддингов вернул пустой ответ.", file=sys.stderr)
    raise SystemExit(1)

dimension = len(rows[0].get("embedding") or [])
if dimension != EXPECTED_DIMENSION:
    print(
        f"Размерность эмбеддинга {dimension}, а база ожидает {EXPECTED_DIMENSION}. "
        f"Проверь TUTOR_EMBEDDINGS_MODEL / TUTOR_EMBEDDINGS_DIMENSIONS.",
        file=sys.stderr,
    )
    raise SystemExit(1)

print(f"Эмбеддинги доступны: model={model}, dimension={dimension}")
PY
}

check_embeddings_api() {
    local container_id="$1"
    local output=""
    local attempt

    # Сервер и модель могут быть заданы только в узле Langflow — их лаунчер
    # не видит. Проверяем, только если оба значения указаны в .env.
    if ! env_is_set TUTOR_EMBEDDINGS_BASE_URL || ! env_is_set TUTOR_EMBEDDINGS_MODEL; then
        printf 'I: Сервер и модель эмбеддингов не заданы в .env: их нужно указать в узле Langflow. Проверка из лаунчера пропущена.\n'
        return 0
    fi

    for ((attempt = 1; attempt <= 5; attempt++)); do
        if output="$(embeddings_probe "$container_id" 2>&1)"; then
            printf '%s\n' "$output"
            return 0
        fi
        sleep 1
    done

    printf 'E: Не удалось проверить API эмбеддингов из Langflow:\n%s\n' "$output" >&2
    return 1
}

check_embeddings() {
    local container_id="$1"
    if [[ "$EMBEDDINGS_PROVIDER" == "ollama" ]]; then
        check_ollama "$container_id"
    else
        check_embeddings_api "$container_id"
    fi
}

database_probe() {
    docker_run exec -i "$1" python - <<'PY'
import base64
import os
import sys

import psycopg

try:
    password = base64.b64decode(
        os.environ["TUTOR_DB_PASSWORD_B64"],
        validate=True,
    ).decode("utf-8")
    with psycopg.connect(
        host=os.environ["TUTOR_DB_HOST"],
        port=int(os.getenv("TUTOR_DB_PORT", "5432")),
        dbname=os.environ["TUTOR_DB_NAME"],
        user=os.environ["TUTOR_DB_USER"],
        password=password,
        connect_timeout=int(os.getenv("TUTOR_DB_CONNECT_TIMEOUT_SECONDS", "10")),
        application_name="TutorRAGLauncher",
    ) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute(
            "SELECT current_database(), current_user"
        ).fetchone()
        # Те же таблицы и поля, что использует компонент поиска:
        # чанки + названия документов (documents.filename).
        conn.execute(
            "SELECT c.id, c.document_id, d.filename "
            "FROM public.document_chunks AS c "
            "LEFT JOIN public.documents AS d ON d.id = c.document_id "
            "LIMIT 1"
        ).fetchone()
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM public.documents), "
            "(SELECT count(*) FROM public.document_chunks)"
        ).fetchone()
    print(
        f"PostgreSQL доступен: database={row[0]}, user={row[1]}, "
        f"documents={counts[0]}, document_chunks={counts[1]}"
    )
except Exception as exc:
    print(f"Проверка PostgreSQL не прошла: {type(exc).__name__}: {exc}", file=sys.stderr)
    raise SystemExit(1)
PY
}

check_database() {
    local container_id="$1"
    local output=""
    local attempt

    for ((attempt = 1; attempt <= 30; attempt++)); do
        if output="$(database_probe "$container_id" 2>&1)"; then
            printf '%s\n' "$output"
            return 0
        fi
        sleep 1
    done

    printf 'E: Langflow не смог подключиться к PostgreSQL:\n%s\n' "$output" >&2
    return 1
}

is_true() {
    case "$1" in
        1|true|TRUE|yes|YES|on|ON) return 0 ;;
        *) return 1 ;;
    esac
}

case "${1:-}" in
    start)
        select_docker

        printf 'I: Режим эмбеддингов: %s\n' "$EMBEDDINGS_PROVIDER"
        if [[ "$EMBEDDINGS_PROVIDER" == "ollama" ]]; then
            start_ollama_service_if_configured
        fi

        if [[ -n "$DB_CONTAINER" ]]; then
            docker_run container inspect "$DB_CONTAINER" >/dev/null 2>&1 ||
                fail "Не найден контейнер БД $DB_CONTAINER. Дамп скрипт не восстанавливает."

            if [[ "$(docker_run inspect --format '{{.State.Running}}' "$DB_CONTAINER")" != "true" ]]; then
                docker_run start "$DB_CONTAINER" >/dev/null
            fi
        fi

        compose up -d --build

        LANGFLOW_ID="$(compose ps -q langflow 2>/dev/null || true)"
        LANGFLOW_ID="${LANGFLOW_ID%%$'\n'*}"
        [[ -n "$LANGFLOW_ID" ]] || fail "Compose не вернул контейнер сервиса langflow."

        NETWORK="$(first_container_network "$LANGFLOW_ID")"
        [[ -n "$NETWORK" ]] || fail "Не удалось определить Docker-сеть Langflow."

        if [[ -n "$DB_CONTAINER" ]]; then
            if container_has_network "$DB_CONTAINER" "$NETWORK"; then
                printf 'I: БД уже подключена к сети %s\n' "$NETWORK"
            else
                docker_run network connect "$NETWORK" "$DB_CONTAINER"
                printf 'I: БД подключена к сети %s\n' "$NETWORK"
            fi
        fi

        check_embeddings "$LANGFLOW_ID"
        check_database "$LANGFLOW_ID"

        printf 'I: Tutor запущен: http://127.0.0.1:7860\n'
        ;;

    stop)
        select_docker

        if [[ -n "$DB_CONTAINER" ]] &&
           docker_run container inspect "$DB_CONTAINER" >/dev/null 2>&1; then
            NETWORK="$COMPOSE_NETWORK"
            LANGFLOW_ID="$(compose ps -a -q langflow 2>/dev/null || true)"
            LANGFLOW_ID="${LANGFLOW_ID%%$'\n'*}"

            if [[ -n "$LANGFLOW_ID" ]]; then
                ACTUAL_NETWORK="$(first_container_network "$LANGFLOW_ID" 2>/dev/null || true)"
                NETWORK="${ACTUAL_NETWORK:-$NETWORK}"
            fi

            if container_has_network "$DB_CONTAINER" "$NETWORK"; then
                docker_run network disconnect --force "$NETWORK" "$DB_CONTAINER"
            fi
        fi

        # Без -v: Docker volumes и данные Langflow сохраняются.
        compose down

        if is_true "$STOP_DB" && [[ -n "$DB_CONTAINER" ]] &&
           docker_run container inspect "$DB_CONTAINER" >/dev/null 2>&1 &&
           [[ "$(docker_run inspect --format '{{.State.Running}}' "$DB_CONTAINER")" == "true" ]]; then
            docker_run stop "$DB_CONTAINER" >/dev/null
        fi

        if is_true "$STOP_OLLAMA" && [[ -n "$OLLAMA_SERVICE" ]]; then
            if command -v rc-service >/dev/null 2>&1; then
                as_root rc-service "$OLLAMA_SERVICE" stop
            elif command -v systemctl >/dev/null 2>&1; then
                as_root systemctl stop "$OLLAMA_SERVICE"
            fi
        fi

        if [[ "$EMBEDDINGS_PROVIDER" == "ollama" ]]; then
            printf 'I: Tutor остановлен. Docker, Ollama и БД не удалены.\n'
        else
            printf 'I: Tutor остановлен. Docker и БД не удалены.\n'
        fi
        ;;

    *)
        printf 'Использование: %s {start|stop}\n' "$0" >&2
        exit 2
        ;;
esac
