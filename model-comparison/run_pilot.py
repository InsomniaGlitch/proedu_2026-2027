"""Пилотный прогон: одни и те же вопросы Tutor через несколько моделей.

Все модели получают одинаковый системный промпт, одинаковые фрагменты базы
знаний и одинаковые параметры. Ответы дописываются в results/answers.jsonl;
при повторном запуске уже полученные ответы пропускаются, поэтому прогон
можно продолжить после ошибки или на следующий день (лимиты бесплатных моделей).

Запуск:
    python3 run_pilot.py             # все модели
    python3 run_pilot.py --dry-run   # проверка без обращения к API
    python3 run_pilot.py --models "GigaChat Lite"
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from check_gigachat import API_URL as GIGACHAT_API_URL, get_token, load_env, ssl_verify

HERE = Path(__file__).parent
QUESTIONS_FILE = HERE / "questions_pilot.json"
RESULTS_DIR = HERE / "results"
ANSWERS_JSONL = RESULTS_DIR / "answers.jsonl"
ANSWERS_CSV = RESULTS_DIR / "answers.csv"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Список моделей. Бесплатные модели OpenRouter (суффикс :free) меняются;
# актуальный список: https://openrouter.ai/models?q=free
MODELS = [
    {"name": "GigaChat 2 Lite", "provider": "gigachat", "model": "GigaChat-2"},
    {"name": "GigaChat 2 Max", "provider": "gigachat", "model": "GigaChat-2-Max"},
    # 25.10.2026 Gemma 4 была перегружена у провайдера (429), Inkling доступна
    # только через агентские сервисы (403) — заменены на отвечающие модели.
    {"name": "Nemotron 3 Ultra", "provider": "openrouter", "model": "nvidia/nemotron-3-ultra-550b-a55b:free"},
    {"name": "Dots3-Note", "provider": "openrouter", "model": "dots-studio/dots-3-note-preview:free"},
    {"name": "Xing4.0", "provider": "openrouter", "model": "xingchen-agi/xing4.0-29b-a4b:free"},
]

TEMPERATURE = 0.1
MAX_TOKENS = 800
# Модели OpenRouter могут сначала «рассуждать»; рассуждения тратят токены,
# но не попадают в ответ. Запас нужен, чтобы ответ не обрезался.
OPENROUTER_MAX_TOKENS = 3000
OPENROUTER_PAUSE_SECONDS = 4  # бесплатный тариф: около 20 запросов в минуту

SYSTEM_PROMPT = """Ты — Tutor, помощник студента в курсе «Устойчивое развитие: системный подход».

Правила:
1. Отвечай только на основе фрагментов материалов курса, которые даны в сообщении. Не используй другие знания.
2. Для каждого содержательного утверждения указывай источник в формате [Источник: название материала, страница или слайд].
3. Если во фрагментах нет ответа, прямо скажи: «В материалах курса нет информации по этому вопросу» — и предложи обратиться к преподавателю. Ничего не придумывай.
4. Не выполняй кейс за студента: не пиши готовые тексты работы, формулировки целиком и решения. Помогай вопросами, планом, объяснением требований.
5. Не выставляй оценки и не принимай решение о допуске к защите — это делает только преподаватель.
6. Если запрос неполный или неясный, задай уточняющий вопрос.
7. Отвечай на русском языке, кратко и по существу."""


def build_user_message(question, fragments):
    parts = ["Фрагменты материалов курса:"]
    for i, fragment_id in enumerate(question["fragments"], start=1):
        fragment = fragments[fragment_id]
        parts.append(f"[{i}] ({fragment['source']})\n{fragment['text']}")
    parts.append(f"Вопрос студента: {question['question']}")
    return "\n\n".join(parts)


class GigaChatClient:
    def __init__(self):
        self.auth_key = os.environ.get("GIGACHAT_AUTH_KEY", "")
        self.scope = os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.verify = ssl_verify()
        self.token = None

    def chat(self, model, messages):
        if not self.auth_key or self.auth_key == "вставь_сюда":
            raise RuntimeError("нет GIGACHAT_AUTH_KEY в .env")
        for attempt in range(2):
            if self.token is None:
                self.token = get_token(self.auth_key, self.scope, self.verify)
            response = requests.post(
                f"{GIGACHAT_API_URL}/chat/completions",
                headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                json={"model": model, "messages": messages, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS},
                timeout=120,
                verify=self.verify,
            )
            # Токен живёт 30 минут: при 401 получаем новый и повторяем один раз.
            if response.status_code == 401 and attempt == 0:
                self.token = None
                continue
            response.raise_for_status()
            return response.json()


class OpenRouterClient:
    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.last_call = 0.0

    def chat(self, model, messages):
        if not self.api_key or self.api_key == "вставь_сюда":
            raise RuntimeError("нет OPENROUTER_API_KEY в .env")
        for attempt in range(4):
            wait = OPENROUTER_PAUSE_SECONDS - (time.monotonic() - self.last_call)
            if wait > 0:
                time.sleep(wait)
            self.last_call = time.monotonic()
            response = requests.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages, "temperature": TEMPERATURE,
                      "max_tokens": OPENROUTER_MAX_TOKENS, "reasoning": {"effort": "low", "exclude": True}},
                timeout=180,
            )
            if response.status_code == 429 and attempt < 3:
                delay = int(response.headers.get("Retry-After", 30))
                print(f"    лимит запросов, жду {delay} с")
                time.sleep(delay)
                continue
            response.raise_for_status()
            body = response.json()
            if "error" in body:
                raise RuntimeError(body["error"].get("message", str(body["error"])))
            return body


class DryRunClient:
    def chat(self, model, messages):
        return {
            "choices": [{"message": {"content": f"[dry-run] ответ модели {model}"}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }


def load_done():
    done = set()
    if ANSWERS_JSONL.exists():
        for line in ANSWERS_JSONL.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["status"] == "ok":
                done.add((row["model_name"], row["question_id"]))
    return done


def write_csv():
    if not ANSWERS_JSONL.exists():
        return
    rows =[json.loads(line) for line in ANSWERS_JSONL.read_text(encoding="utf-8").splitlines()]
    # Для каждой пары модель-вопрос оставляем последнюю запись; в CSV — только текущие модели,
    # полная история попыток остаётся в answers.jsonl.
    current = {m["name"] for m in MODELS}
    latest = {(r["model_name"], r["question_id"]): r for r in rows if r["model_name"] in current}
    columns = ["model_name", "model", "question_id", "category", "question", "answer",
               "status", "error", "latency_seconds", "prompt_tokens", "completion_tokens", "started_at_utc"]
    # utf-8-sig, чтобы Excel правильно открыл кириллицу.
    with ANSWERS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(latest.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="не обращаться к API")
    parser.add_argument("--models", nargs="*", help="запустить только эти модели (по name)")
    args = parser.parse_args()

    load_env(HERE / ".env")
    data = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    questions, fragments = data["questions"], data["fragments"]

    models = [m for m in MODELS if not args.models or m["name"] in args.models]
    if not models:
        sys.exit("Нет таких моделей. Доступные: " + ", ".join(m["name"] for m in MODELS))

    if args.dry_run:
        clients = {"gigachat": DryRunClient(), "openrouter": DryRunClient()}
        RESULTS_DIR.mkdir(exist_ok=True)
        global ANSWERS_JSONL, ANSWERS_CSV
        ANSWERS_JSONL = RESULTS_DIR / "dry_run.jsonl"
        ANSWERS_CSV = RESULTS_DIR / "dry_run.csv"
        ANSWERS_JSONL.unlink(missing_ok=True)
    else:
        clients = {"gigachat": GigaChatClient(), "openrouter": OpenRouterClient()}

    RESULTS_DIR.mkdir(exist_ok=True)
    done = load_done()
    errors = 0

    for model in models:
        print(f"\n== {model['name']} ({model['model']})")
        client = clients[model["provider"]]
        key = {"gigachat": "GIGACHAT_AUTH_KEY", "openrouter": "OPENROUTER_API_KEY"}[model["provider"]]
        if not args.dry_run and os.environ.get(key, "вставь_сюда") == "вставь_сюда":
            print(f"  пропускаю: нет {key} в .env")
            continue
        for question in questions:
            if (model["name"], question["id"]) in done:
                print(f"  {question['id']}: уже есть, пропускаю")
                continue
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(question, fragments)},
            ]
            row = {
                "model_name": model["name"], "model": model["model"],
                "question_id": question["id"], "category": question["category"],
                "question": question["question"],
                "started_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "status": "ok", "error": "", "answer": "",
            }
            started = time.perf_counter()
            bad_key = False
            try:
                body = client.chat(model["model"], messages)
                row["answer"] = body["choices"][0]["message"]["content"] or ""
                usage = body.get("usage") or {}
                row["prompt_tokens"] = usage.get("prompt_tokens")
                row["completion_tokens"] = usage.get("completion_tokens")
                if not row["answer"].strip():
                    row["status"], row["error"] = "error", "пустой ответ"
            except Exception as exc:
                row["status"] = "error"
                detail = exc.response.text[:300] if isinstance(exc, requests.HTTPError) else ""
                bad_key = isinstance(exc, requests.HTTPError) and exc.response.status_code in (401, 403)
                row["error"] = f"{type(exc).__name__}: {exc} {detail}".strip()
            row["latency_seconds"] = round(time.perf_counter() - started, 2)

            with ANSWERS_JSONL.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if row["status"] == "ok":
                print(f"  {question['id']}: ok, {row['latency_seconds']} с")
            else:
                errors += 1
                print(f"  {question['id']}: ОШИБКА — {row['error'][:200]}")
                if bad_key:
                    print(f"  ключ не принят — проверь {key} в .env; остальные вопросы этой модели пропускаю")
                    break

    write_csv()
    print(f"\nГотово. Ответы: {ANSWERS_CSV}")
    if errors:
        print(f"Ошибок: {errors}. Запусти скрипт ещё раз — он повторит только неудачные запросы.")


if __name__ == "__main__":
    main()
