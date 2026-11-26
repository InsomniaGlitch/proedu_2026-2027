import hashlib
import html
import json
import os
import secrets
import shutil
import tempfile
import uuid
from pathlib import Path
from zipfile import BadZipFile

import httpx
import psycopg2
from psycopg2 import errors
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str


class ReviewRequest(BaseModel):
    decision: str
    comment: str = ""


def extract_langflow_response(payload: dict) -> str:
    for flow_output in payload.get("outputs", []):
        if not isinstance(flow_output, dict):
            continue
        for component_output in flow_output.get("outputs", []):
            if not isinstance(component_output, dict):
                continue

            results = component_output.get("results")
            if isinstance(results, dict):
                message = results.get("message")
                if isinstance(message, dict) and message.get("text"):
                    return str(message["text"])
                if isinstance(message, str) and message.strip():
                    return message

            for item in component_output.get("messages", []):
                if not isinstance(item, dict):
                    continue
                message = item.get("message")
                if isinstance(message, dict) and message.get("text"):
                    return str(message["text"])
                if isinstance(message, str) and message.strip():
                    return message

            artifacts = component_output.get("artifacts")
            if isinstance(artifacts, dict):
                message = artifacts.get("message")
                if isinstance(message, str) and message.strip():
                    return message

    for key in ("text", "response", "output", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value

    raise ValueError("Langflow response did not contain a chat message")


async def get_ai_response(text: str, user_id: int, session_id: str) -> str:
    base_url = os.getenv("LANGFLOW_BASE_URL", "http://localhost:7860").rstrip("/")
    flow_id = os.getenv("LANGFLOW_FLOW_ID", "").strip()
    api_key = os.getenv("LANGFLOW_API_KEY", "").strip()
    try:
        timeout = float(os.getenv("LANGFLOW_TIMEOUT_SECONDS", "30"))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Некорректный таймаут Langflow") from exc

    if not flow_id or not api_key or timeout <= 0:
        raise HTTPException(
            status_code=503,
            detail="Интеграция Langflow не настроена",
        )

    payload = {
        "input_request": {
            "input_type": "chat",
            "input_value": text,
            "output_type": "chat",
            "session_id": session_id,
            "user_id": str(user_id),
        }
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/api/v1/run/{flow_id}",
                params={"stream": "false"},
                headers={
                    "x-api-key": api_key,
                },
                json=payload,
            )
            response.raise_for_status()
            return extract_langflow_response(response.json())
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=503, detail="Время ожидания Langflow истекло") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Langflow вернул ошибку") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Не удалось связаться с Langflow") from exc
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=502, detail="Некорректный ответ Langflow") from exc


async def get_reviewer_response(text: str, user_id: int) -> dict:
    base_url = os.getenv("LANGFLOW_BASE_URL", "http://localhost:7860").rstrip("/")
    flow_id = os.getenv("LANGFLOW_REVIEWER_FLOW_ID", "").strip()
    api_key = os.getenv("LANGFLOW_API_KEY", "").strip()
    try:
        timeout = float(os.getenv("LANGFLOW_TIMEOUT_SECONDS", "30"))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Некорректный таймаут Langflow") from exc

    if not flow_id or not api_key or timeout <= 0:
        raise HTTPException(status_code=503, detail="Reviewer Langflow не настроен")

    run_id = str(uuid.uuid4())
    payload = {
        "action": "submit_and_review",
        "telegram_id": user_id,
        "run_id": run_id,
        "text": text,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/api/v1/run/{flow_id}",
                params={"stream": "false"},
                headers={"x-api-key": api_key},
                json={
                    "input_value": json.dumps(payload, ensure_ascii=False),
                    "input_type": "chat",
                    "output_type": "chat",
                    "session_id": run_id,
                },
            )
            response.raise_for_status()
            response_text = extract_langflow_response(response.json())
            result = json.loads(response_text)
            if not isinstance(result, dict):
                raise ValueError("Reviewer response is not an object")
            return result
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=503, detail="Время ожидания Reviewer истекло") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Reviewer Langflow вернул ошибку") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Не удалось связаться с Reviewer Langflow") from exc
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=502, detail="Некорректный ответ Reviewer Langflow") from exc


def extract_reviewer_results(payload: dict) -> dict:
    for flow_output in payload.get("outputs", []):
        if not isinstance(flow_output, dict):
            continue
        for component_output in flow_output.get("outputs", []):
            if not isinstance(component_output, dict):
                continue

            results = component_output.get("results")
            if isinstance(results, dict):
                return results

    raise ValueError("Reviewer Langflow response did not contain results")


sessions = {}


def get_db_connection():
    settings = {
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_PORT": os.getenv("DB_PORT"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD"),
    }
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise psycopg2.OperationalError(
            "Missing required database settings: " + ", ".join(missing)
        )

    return psycopg2.connect(
        host=settings["DB_HOST"],
        port=settings["DB_PORT"],
        dbname=settings["DB_NAME"],
        user=settings["DB_USER"],
        password=settings["DB_PASSWORD"],
    )


def authenticate_user(username: str, password: str):
    password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash, role FROM users WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        user_id, stored_hash, role = row
        if stored_hash is None or not secrets.compare_digest(str(stored_hash), password_hash):
            return None
        return {"id": user_id, "role": role}
    finally:
        conn.close()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.post("/api/login")
def login(payload: LoginRequest):
    try:
        user = authenticate_user(payload.username, payload.password)
    except psycopg2.OperationalError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Не удалось подключиться к PostgreSQL"},
        )
    if user is None:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Неверный логин или пароль"},
        )

    token = str(uuid.uuid4())
    sessions[token] = {
        "user_id": user["id"],
        "username": payload.username,
        "role": user["role"],
    }
    response = JSONResponse(content={"status": "ok", "role": user["role"]})
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@app.post("/api/register")
def register(payload: RegisterRequest):
    username = payload.username.strip()
    if len(username) < 3:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Логин должен содержать минимум 3 символа"},
        )
    if len(payload.password) < 6:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Пароль должен содержать минимум 6 символов"},
        )

    password_hash = hashlib.sha256(payload.password.encode("utf-8")).hexdigest()
    try:
        conn = get_db_connection()
    except psycopg2.OperationalError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "Регистрация сейчас недоступна: не удалось подключиться к PostgreSQL.",
            },
        )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, 'student')
                RETURNING id
                """,
                (username, password_hash),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
    except errors.UniqueViolation:
        conn.rollback()
        return JSONResponse(
            status_code=409,
            content={"status": "error", "message": "Пользователь с таким логином уже существует"},
        )
    finally:
        conn.close()

    token = str(uuid.uuid4())
    sessions[token] = {"user_id": user_id, "username": username, "role": "student"}
    response = JSONResponse(
        content={"status": "ok", "role": "student", "redirect": "/dashboard"}
    )
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@app.get("/dashboard-placeholder", response_class=HTMLResponse)
def dashboard_placeholder(request: Request):
    session = get_session(request)
    if session is None:
        return RedirectResponse(url="/login", status_code=302)
    username = html.escape(session["username"])
    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Личный кабинет</title>
          <link rel="stylesheet" href="/static/style.css">
        </head>
        <body>
          <main class="login-page">
            <section class="card">
              <h1>Добро пожаловать, {username}!</h1>
              <p class="subtitle">Раздел личного кабинета временно находится в разработке.</p>
              <a class="btn btn-primary" href="/login" onclick="event.preventDefault(); fetch('/api/logout').then(() => location.href='/login')">Выйти</a>
            </section>
          </main>
        </body>
        </html>
        """
    )


def get_session(request: Request):
    token = request.cookies.get("session_token")
    return sessions.get(token) if token else None


def parse_submission_file(file_value: str):
    try:
        submission_file = json.loads(file_value)
    except (TypeError, json.JSONDecodeError):
        return {"filename": str(file_value), "content": ""}

    if not isinstance(submission_file, dict):
        return {"filename": str(file_value), "content": ""}

    filename = submission_file.get("filename")
    content = submission_file.get("content")
    if not isinstance(filename, str) or not isinstance(content, str):
        return {"filename": str(file_value), "content": ""}
    return {"filename": filename, "content": content}


@app.get("/dashboard", response_class=HTMLResponse)
def student_dashboard(request: Request):
    session = get_session(request)
    if session is None:
        return RedirectResponse(url="/login", status_code=302)
    if session["role"] != "student":
        return RedirectResponse(url="/teacher/dashboard", status_code=302)
    return templates.TemplateResponse(
        request, "student_dashboard.html", {"username": session["username"]}
    )


@app.get("/submissions", response_class=HTMLResponse)
def submissions_page(request: Request):
    session = get_session(request)
    if session is None:
        return RedirectResponse(url="/login", status_code=302)
    if session["role"] != "student":
        return RedirectResponse(url="/teacher/dashboard", status_code=302)
    return templates.TemplateResponse(
        request,
        "submissions.html",
        {
            "username": session["username"],
            "submissions": get_student_submissions(session["user_id"]),
        },
    )


def get_student_submissions(user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, u.username, s.file, s.status, s.created_at,
                       feedback.text
                FROM submissions AS s
                JOIN users AS u ON u.id = s.student_id
                LEFT JOIN LATERAL (
                    SELECT f.text
                    FROM grades AS g
                    JOIN feedbacks AS f ON f.id = g.feedback_id
                    WHERE g.submission_id = s.id
                    ORDER BY g.created_at DESC
                    LIMIT 1
                ) AS feedback ON TRUE
                WHERE u.id = %s
                ORDER BY s.created_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
        return [
            {
                "id": submission_id,
                "username": username,
                "filename": parse_submission_file(file_value)["filename"],
                "status": status,
                "date": created_at.strftime("%d.%m.%Y %H:%M"),
                "feedback": feedback_text,
            }
            for submission_id, username, file_value, status, created_at, feedback_text in rows
        ]
    finally:
        conn.close()


@app.get("/api/submissions")
def list_submissions(request: Request):
    session = get_session(request)
    if session is None:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Войдите, чтобы просмотреть работы"},
        )
    if session["role"] != "student":
        return JSONResponse(
            status_code=403,
            content={"status": "error", "message": "Работы доступны только студентам"},
        )
    return JSONResponse(
        content={
            "status": "ok",
            "submissions": get_student_submissions(session["user_id"]),
        }
    )


@app.post("/api/submissions")
async def create_submission(request: Request, file: UploadFile = File(...)):
    session = get_session(request)
    if session is None:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Войдите, чтобы загрузить работу"},
        )
    if session["role"] != "student":
        return JSONResponse(
            status_code=403,
            content={"status": "error", "message": "Загружать работы могут только студенты"},
        )

    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".docx"}:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Поддерживаются только файлы PDF и DOCX"},
        )

    with tempfile.TemporaryDirectory(prefix="student-submission-") as temp_dir:
        uploaded_file = Path(temp_dir) / f"submission{extension}"
        with uploaded_file.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)

        if uploaded_file.stat().st_size == 0:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Файл пуст"},
            )

        try:
            if extension == ".pdf":
                extracted_text = "\n".join(
                    page.extract_text() or "" for page in PdfReader(uploaded_file).pages
                )
            else:
                document = Document(uploaded_file)
                document_text = [paragraph.text for paragraph in document.paragraphs]
                document_text.extend(
                    cell.text
                    for table in document.tables
                    for row in table.rows
                    for cell in row.cells
                )
                extracted_text = "\n".join(document_text)
            stored_file = json.dumps(
                {
                    "filename": filename,
                    "content": extracted_text.replace("\x00", ""),
                },
                ensure_ascii=False,
            )
        except (PdfReadError, ValueError, OSError, EOFError, PackageNotFoundError, BadZipFile):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Не удалось прочитать файл"},
            )

    try:
        conn = get_db_connection()
    except psycopg2.OperationalError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Не удалось подключиться к PostgreSQL"},
        )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO submissions (student_id, file, status, created_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (session["user_id"], stored_file, "На проверке"),
            )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse(content={"status": "ok"})


@app.get("/teacher/dashboard", response_class=HTMLResponse)
def teacher_dashboard(request: Request):
    session = get_session(request)
    if session is None:
        return RedirectResponse(url="/login", status_code=302)
    if session["role"] != "teacher":
        return RedirectResponse(url="/dashboard", status_code=302)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'На проверке'),
                    COUNT(*) FILTER (WHERE status = 'На доработке'),
                    COUNT(*) FILTER (WHERE status = 'Проверено')
                FROM submissions
                """
            )
            on_review, need_revision, reviewed = cur.fetchone()
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "teacher_dashboard.html",
        {
            "username": session["username"],
            "on_review": on_review,
            "need_revision": need_revision,
            "reviewed": reviewed,
        },
    )


def feature_placeholder(request: Request, role: str, title: str):
    session = get_session(request)
    if session is None:
        return RedirectResponse(url="/login", status_code=302)
    if session["role"] != role:
        dashboard_url = "/teacher/dashboard" if session["role"] == "teacher" else "/dashboard"
        return RedirectResponse(url=dashboard_url, status_code=302)

    dashboard_url = "/teacher/dashboard" if role == "teacher" else "/dashboard"
    return templates.TemplateResponse(
        request,
        "feature_placeholder.html",
        {
            "title": title,
            "username": session["username"],
            "dashboard_url": dashboard_url,
        },
    )


def get_or_create_chat_session(user_id: int) -> int:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM chat_sessions
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row is not None:
                return row[0]

            cur.execute(
                """
                INSERT INTO chat_sessions (user_id, created_at)
                VALUES (%s, CURRENT_TIMESTAMP)
                RETURNING id
                """,
                (user_id,),
            )
            chat_session_id = cur.fetchone()[0]
        conn.commit()
        return chat_session_id
    finally:
        conn.close()


def get_chat_history(chat_session_id: int) -> list[dict[str, str]]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sender, text
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (chat_session_id,),
            )
            return [
                {"sender": sender, "text": text}
                for sender, text in cur.fetchall()
            ]
    finally:
        conn.close()


def save_chat_message(chat_session_id: int, sender: str, text: str) -> None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (session_id, sender, text, created_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (chat_session_id, sender, text),
            )
        conn.commit()
    finally:
        conn.close()


@app.get("/chat", response_class=HTMLResponse)
def student_chat_page(request: Request):
    session = get_session(request)
    if session is None:
        return RedirectResponse(url="/login", status_code=302)
    if session["role"] != "student":
        return RedirectResponse(url="/teacher/dashboard", status_code=302)

    try:
        chat_session_id = get_or_create_chat_session(session["user_id"])
        history = get_chat_history(chat_session_id)
    except psycopg2.Error:
        return templates.TemplateResponse(
            request,
            "chat.html",
            {
                "username": session["username"],
                "history": [],
                "chat_error": "Не удалось загрузить историю чата",
            },
            status_code=503,
        )

    return templates.TemplateResponse(
        request,
        "chat.html",
        {"username": session["username"], "history": history},
    )


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request):
    session = get_session(request)
    if session is None:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Войдите, чтобы пользоваться чатом"},
        )
    if session["role"] != "student":
        return JSONResponse(
            status_code=403,
            content={"status": "error", "message": "Чат доступен только студентам"},
        )

    message = payload.message.strip()
    if not message:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Введите сообщение"},
        )

    try:
        chat_session_id = get_or_create_chat_session(session["user_id"])
        langflow_session_id = f"chat-{chat_session_id}"
        save_chat_message(chat_session_id, "user", message)
    except psycopg2.OperationalError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Не удалось сохранить сообщение в PostgreSQL"},
        )

    bot_reply = await get_ai_response(message, session["user_id"], langflow_session_id)

    try:
        save_chat_message(chat_session_id, "ai", bot_reply)
    except psycopg2.OperationalError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Ответ получен, но не удалось сохранить его в PostgreSQL"},
        )

    return JSONResponse(content={"response": bot_reply})


@app.get("/teacher/queue", response_class=HTMLResponse)
def teacher_queue_page(request: Request):
    session = get_session(request)
    if session is None:
        return RedirectResponse(url="/login", status_code=302)
    if session["role"] != "teacher":
        return RedirectResponse(url="/dashboard", status_code=302)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, u.username, s.created_at, s.status
                FROM submissions AS s
                JOIN users AS u ON u.id = s.student_id
                WHERE u.role = 'student'
                  AND s.status = 'На проверке'
                ORDER BY s.created_at
                """
            )
            rows = cur.fetchall()
        works = [
            {
                "id": work_id,
                "student": student,
                "date": created_at.strftime("%d.%m.%Y %H:%M"),
                "status": status,
            }
            for work_id, student, created_at, status in rows
        ]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request,
        "teacher_queue.html",
        {"username": session["username"], "works": works},
    )


@app.get("/teacher/review/{work_id}", response_class=HTMLResponse)
def teacher_review_page(work_id: int, request: Request):
    session = get_session(request)
    if session is None:
        return RedirectResponse(url="/login", status_code=302)
    if session["role"] != "teacher":
        return RedirectResponse(url="/dashboard", status_code=302)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.username, s.file, s.status
                FROM submissions AS s
                JOIN users AS u ON u.id = s.student_id
                WHERE s.id = %s
                """,
                (work_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Работа не найдена")

    student, file_value, status = row
    submission_file = parse_submission_file(file_value)
    return templates.TemplateResponse(
        request,
        "teacher_review.html",
        {
            "username": session["username"],
            "work_id": work_id,
            "student": student,
            "submission": submission_file,
            "status": status,
        },
    )


@app.post("/api/submissions/{submission_id}/review")
def review_submission(
    submission_id: int, payload: ReviewRequest, request: Request
):
    session = get_session(request)
    if session is None:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Войдите, чтобы проверять работы"},
        )
    if session["role"] != "teacher":
        return JSONResponse(
            status_code=403,
            content={"status": "error", "message": "Проверять работы могут только преподаватели"},
        )

    decisions = {
        "approved": ("Проверено", "Допустить"),
        "revision": ("На доработке", "На доработку"),
    }
    if payload.decision not in decisions:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Некорректное решение"},
        )

    status, decision_label = decisions[payload.decision]
    feedback_text = f"Решение: {decision_label}"
    comment = payload.comment.strip()
    if comment:
        feedback_text += f"\n\nКомментарий преподавателя:\n{comment}"

    try:
        conn = get_db_connection()
    except psycopg2.OperationalError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Не удалось подключиться к PostgreSQL"},
        )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT student_id, status FROM submissions WHERE id = %s FOR UPDATE",
                (submission_id,),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Работа не найдена"},
                )
            student_id, current_status = row
            if current_status != "На проверке":
                conn.rollback()
                return JSONResponse(
                    status_code=409,
                    content={"status": "error", "message": "Эта работа уже проверена"},
                )

            cur.execute(
                "INSERT INTO feedbacks (text) VALUES (%s) RETURNING id",
                (feedback_text,),
            )
            feedback_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO grades (
                    student_id, submission_id, feedback_id, final_score,
                    graded_by, created_at
                )
                VALUES (%s, %s, %s, NULL, %s, CURRENT_TIMESTAMP)
                """,
                (student_id, submission_id, feedback_id, session["user_id"]),
            )
            cur.execute(
                "UPDATE submissions SET status = %s WHERE id = %s",
                (status, submission_id),
            )
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(content={"status": "ok", "submission_status": status})


@app.get("/teacher/students", response_class=HTMLResponse)
def teacher_students_page(request: Request):
    session = get_session(request)
    if session is None:
        return RedirectResponse(url="/login", status_code=302)
    if session["role"] != "teacher":
        return RedirectResponse(url="/dashboard", status_code=302)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.username, u.role, COUNT(s.id)
                FROM users AS u
                LEFT JOIN submissions AS s ON s.student_id = u.id
                WHERE u.role = 'student'
                GROUP BY u.id, u.username, u.role
                ORDER BY u.username
                """
            )
            students = [
                {
                    "username": username,
                    "role": role,
                    "submissions_count": submissions_count,
                }
                for username, role, submissions_count in cur.fetchall()
            ]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request,
        "teacher_students.html",
        {"username": session["username"], "students": students},
    )


@app.get("/api/logout")
def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        sessions.pop(token, None)

    response = JSONResponse(content={"status": "ok"})
    response.delete_cookie("session_token")
    return response


def ensure_reviewer_schema() -> None:
    conn = get_db_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE grades ALTER COLUMN final_score DROP NOT NULL")
            cur.execute("ALTER TABLE grades ALTER COLUMN graded_by DROP NOT NULL")
            cur.execute("ALTER TYPE status ADD VALUE IF NOT EXISTS 'На проверке'")
            cur.execute("ALTER TYPE status ADD VALUE IF NOT EXISTS 'На доработке'")
            cur.execute("ALTER TYPE status ADD VALUE IF NOT EXISTS 'Проверено'")
    finally:
        conn.close()


@app.post("/api/submissions")
async def create_submission(request: Request, file: UploadFile = File(...)):
    session = get_session(request)
    if session is None:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Войдите, чтобы загрузить работу"},
        )
    if session["role"] != "student":
        return JSONResponse(
            status_code=403,
            content={"status": "error", "message": "Загружать работы могут только студенты"},
        )

    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".docx"}:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Поддерживаются только файлы PDF и DOCX"},
        )

    with tempfile.TemporaryDirectory(prefix="student-submission-") as temp_dir:
        uploaded_file = Path(temp_dir) / f"submission{extension}"
        with uploaded_file.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)

        if uploaded_file.stat().st_size == 0:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Файл пуст"},
            )

        try:
            if extension == ".pdf":
                extracted_text = "\n".join(
                    page.extract_text() or "" for page in PdfReader(uploaded_file).pages
                )
            else:
                document = Document(uploaded_file)
                document_text = [paragraph.text for paragraph in document.paragraphs]
                document_text.extend(
                    cell.text
                    for table in document.tables
                    for row in table.rows
                    for cell in row.cells
                )
                extracted_text = "\n".join(document_text)
            stored_file = json.dumps(
                {
                    "filename": filename,
                    "content": extracted_text.replace("\x00", ""),
                },
                ensure_ascii=False,
            )
        except (PdfReadError, ValueError, OSError, EOFError, PackageNotFoundError, BadZipFile):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Не удалось прочитать файл"},
            )

    try:
        ensure_reviewer_schema()
        conn = get_db_connection()
    except psycopg2.OperationalError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Не удалось подключиться к PostgreSQL"},
        )

    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET telegram_id = %s WHERE id = %s",
                (session["user_id"], session["user_id"]),
            )
        conn.commit()
    except psycopg2.Error:
        conn.rollback()
        conn.close()
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Не удалось привязать пользователя к Reviewer"},
        )
    finally:
        conn.close()

    reviewer_result = await get_reviewer_response(
        extracted_text.replace("\x00", ""),
        session["user_id"],
    )

    if reviewer_result.get("processing_status") == "error":
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": "Reviewer не смог проверить работу",
                "error_code": reviewer_result.get("error_code", "unknown"),
            },
        )

    submission_id = reviewer_result.get("submission_id")
    if type(submission_id) is not int or submission_id <= 0:
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": "Reviewer не вернул идентификатор работы"},
        )

    nested_result = reviewer_result.get("result")
    if isinstance(nested_result, dict):
        feedback_text = nested_result.get("feedback_text")
    else:
        feedback_text = reviewer_result.get("feedback_text")
    if not isinstance(feedback_text, str) or not feedback_text.strip():
        feedback_text = "Предварительная проверка Reviewer завершена. Решение принимает преподаватель."

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE submissions
                SET file = %s, status = %s
                WHERE id = %s AND student_id = %s
                """,
                (stored_file, "На проверке", submission_id, session["user_id"]),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return JSONResponse(
                    status_code=502,
                    content={"status": "error", "message": "Не удалось связать проверку с загрузкой"},
                )

            cur.execute(
                """
                INSERT INTO feedbacks (text)
                VALUES (%s)
                ON CONFLICT (text) DO UPDATE SET text = EXCLUDED.text
                RETURNING id
                """,
                (feedback_text,),
            )
            feedback_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO grades (
                    student_id, submission_id, feedback_id, final_score,
                    graded_by, created_at
                )
                VALUES (%s, %s, %s, NULL, NULL, CURRENT_TIMESTAMP)
                """,
                (session["user_id"], submission_id, feedback_id),
            )
        conn.commit()
    except psycopg2.Error:
        conn.rollback()
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Не удалось сохранить результат Reviewer в PostgreSQL"},
        )
    finally:
        conn.close()

    return JSONResponse(
        content={
            "status": "ok",
            "submission_id": submission_id,
            "processing_status": "completed",
        }
    )


submission_routes = [
    route
    for route in app.router.routes
    if getattr(route, "path", None) == "/api/submissions"
    and "POST" in getattr(route, "methods", set())
]
if len(submission_routes) > 1:
    for duplicate_route in submission_routes[:-1]:
        app.router.routes.remove(duplicate_route)