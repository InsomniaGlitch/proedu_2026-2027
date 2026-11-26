import base64
import logging
import os
import re
import time

import psycopg
from langflow.custom import Component
from langflow.io import FloatInput, IntInput, MessageTextInput, Output
from langflow.schema import Message
from lfx.io import ModelInput
from lfx.base.models.unified_models import (
    get_embedding_model_options,
    get_embeddings,
    handle_model_input_update,
)

logger = logging.getLogger(__name__)

VECTOR_DIMENSION = 1024

# Схема базы sustainability_course_db (ветка database):
#   documents(id, text, filename)
#   document_chunks(id, document_id -> documents.id, content, category, embedding)
CHUNKS_TABLE = "public.document_chunks"
DOCUMENTS_TABLE = "public.documents"

# Расширения файлов, которые не нужно показывать студенту в названии.
FILE_EXTENSION_RE = re.compile(
    r"\.(?:txt|md|pdf|docx?|html?|rtf)$",
    re.IGNORECASE,
)
MAX_TITLE_LENGTH = 200

# --- Режим эмбеддингов -------------------------------------------------------
# 'api'    — OpenAI-совместимый /embeddings по ключу (gpt2giga, OpenAI, vLLM).
# 'ollama' — локальная Ollama.
EMBEDDINGS_PROVIDER_API = "api"
EMBEDDINGS_PROVIDER_OLLAMA = "ollama"
OLLAMA_PROVIDER_NAME = "Ollama"


def required_setting(name: str) -> str:
    """Read a required setting from the container environment."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment setting {name} is missing.")
    return value


def env_setting(name: str) -> str:
    """Stripped environment value, or an empty string if it is not set."""
    return os.getenv(name, "").strip()


def env_int_setting(name: str, default: int | None = None) -> int | None:
    """Integer from the environment; an empty value returns the default."""
    value = env_setting(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def int_setting(name: str, default: int, minimum: int = 1) -> int:
    """Read and validate an integer environment setting."""
    value = os.getenv(name, str(default))
    try:
        result = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if result < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}.")
    return result


def embeddings_provider() -> str:
    """
    Embedding mode: 'api' or 'ollama'.

    An explicit TUTOR_EMBEDDINGS_PROVIDER wins. If it is empty, the mode is
    inferred from TUTOR_EMBEDDINGS_BASE_URL: set -> 'api', otherwise 'ollama'
    (backward compatibility with older .env files).
    """
    value = env_setting("TUTOR_EMBEDDINGS_PROVIDER").lower()
    if not value:
        value = (
            EMBEDDINGS_PROVIDER_API
            if env_setting("TUTOR_EMBEDDINGS_BASE_URL")
            else EMBEDDINGS_PROVIDER_OLLAMA
        )
    if value not in (EMBEDDINGS_PROVIDER_API, EMBEDDINGS_PROVIDER_OLLAMA):
        raise RuntimeError("TUTOR_EMBEDDINGS_PROVIDER must be 'ollama' or 'api'.")
    return value


def selected_embedding_model(model) -> dict:
    """
    Final embedding-model selection.

    Priority: .env variables > the selection made in the Flow node.
    In 'api' mode TUTOR_EMBEDDINGS_MODEL is mandatory, so the configuration
    lives in .env and not in the Flow JSON.
    """
    if isinstance(model, list):
        if not model:
            raise RuntimeError("Embedding model is not selected in the node.")
        selection = dict(model[0])
    elif isinstance(model, dict):
        selection = dict(model)
    else:
        raise RuntimeError("Cannot read the embedding model selection.")

    provider_override = env_setting("TUTOR_EMBEDDINGS_PROVIDER_NAME")
    name_override = env_setting("TUTOR_EMBEDDINGS_MODEL")

    if embeddings_provider() == EMBEDDINGS_PROVIDER_API:
        if not name_override:
            raise RuntimeError(
                "TUTOR_EMBEDDINGS_PROVIDER=api, but TUTOR_EMBEDDINGS_MODEL "
                "is not set. Set it in .env to the embedding model of your "
                "OpenAI-compatible /embeddings endpoint "
                "(e.g. EmbeddingsGigaR for gpt2giga)."
            )
        selection["name"] = name_override
        selection["provider"] = provider_override or "OpenAI"
    else:
        if name_override:
            selection["name"] = name_override
        if provider_override:
            selection["provider"] = provider_override
        if selection.get("provider") != OLLAMA_PROVIDER_NAME:
            raise RuntimeError(
                "TUTOR_EMBEDDINGS_PROVIDER=ollama, but the selected provider "
                "is not Ollama. Pick an Ollama embedding model in the node "
                "or set TUTOR_EMBEDDINGS_PROVIDER_NAME."
            )

    if not selection.get("name") or not selection.get("provider"):
        raise RuntimeError("The embedding model selection is incomplete.")
    return selection


def build_embedding_model(model, user_id):
    """
    Create the embedding model for the search query.

    Overrides are passed only in the mode they belong to: api_key and
    api_base are for the OpenAI-compatible server, ollama_base_url is for
    Ollama. Empty variables are not passed, so Langflow Global Variables
    and the container environment still apply.
    """
    selection = selected_embedding_model(model)

    if embeddings_provider() == EMBEDDINGS_PROVIDER_OLLAMA:
        ollama_base_url = env_setting("OLLAMA_BASE_URL")
        if not ollama_base_url:
            raise RuntimeError(
                "Embeddings are configured for Ollama, but OLLAMA_BASE_URL "
                "is not set. Set it in .env, or switch to the API mode: "
                "TUTOR_EMBEDDINGS_PROVIDER=api with "
                "TUTOR_EMBEDDINGS_BASE_URL and TUTOR_EMBEDDINGS_MODEL."
            )
        return get_embeddings(
            model=[selection],
            user_id=user_id,
            ollama_base_url=ollama_base_url,
        )

    api_base = env_setting("TUTOR_EMBEDDINGS_BASE_URL")
    if not api_base:
        raise RuntimeError(
            "TUTOR_EMBEDDINGS_PROVIDER=api, but TUTOR_EMBEDDINGS_BASE_URL "
            "is not set. Set it in .env to the base URL of the "
            "OpenAI-compatible server without /embeddings."
        )

    overrides: dict = {"api_base": api_base}

    api_key = env_setting("TUTOR_EMBEDDINGS_API_KEY")
    if api_key:
        overrides["api_key"] = api_key

    dimensions = env_int_setting("TUTOR_EMBEDDINGS_DIMENSIONS")
    if dimensions is not None:
        if dimensions < 1:
            raise RuntimeError(
                "TUTOR_EMBEDDINGS_DIMENSIONS must be a positive integer."
            )
        overrides["dimensions"] = dimensions

    return get_embeddings(
        model=[selection],
        user_id=user_id,
        **overrides,
    )


def database_password() -> str:
    """Decode the locally configured database password."""
    encoded = required_setting("TUTOR_DB_PASSWORD_B64")
    try:
        return base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError(
            "TUTOR_DB_PASSWORD_B64 must contain valid UTF-8 Base64 data."
        ) from exc


def extract_text(value) -> str:
    """Extract plain text from a Langflow input."""
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    if hasattr(value, "text"):
        value = value.text
    elif hasattr(value, "data") and isinstance(value.data, dict):
        data = value.data
        value = (
            data.get("text") or data.get("content") or data.get("message") or str(data)
        )
    elif isinstance(value, dict):
        value = (
            value.get("text")
            or value.get("content")
            or value.get("message")
            or str(value)
        )
    return str(value or "").strip()


def document_title(filename) -> str:
    """
    Build a display title from documents.filename.
    The result goes into a one-line chunk header that is parsed by
    sources_formatter.py, so control characters and square brackets
    are removed. An empty string means "title unknown".
    """
    if filename is None:
        return ""
    title = str(filename)
    title = re.sub(r"[\x00-\x1f\x7f]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    title = FILE_EXTENSION_RE.sub("", title).strip()
    title = title.replace("[", "(").replace("]", ")")
    if len(title) > MAX_TITLE_LENGTH:
        title = title[: MAX_TITLE_LENGTH - 1].rstrip() + "…"
    return title


def chunk_header(rank, document_id, chunk_id, distance, title) -> str:
    """
    Header of one chunk passed to the agent.
    This format is a contract with sources_formatter.py (HEADER_RE):
    change both files together. document_title is optional there.
    """
    header = (
        f"[{rank}; document_id={document_id}; "
        f"chunk_id={chunk_id}; "
        f"cosine_distance={distance:.4f}"
    )
    if title:
        header += f"; document_title={title}"
    return header + "]"


class PostgresCourseSearch(Component):
    display_name = "PostgreSQL Course Search"
    description = "Search PostgreSQL chunks and route results by cosine distance."
    icon = "Database"
    name = "PostgresCourseSearch"

    def update_build_config(self, build_config, field_value, field_name=None):
        """Populate the standard Langflow embedding-model selector."""
        return handle_model_input_update(
            self,
            dict(build_config),
            field_value,
            field_name,
            cache_key_prefix="embedding_model_options",
            get_options_func=get_embedding_model_options,
        )

    inputs = [
        ModelInput(
            name="model",
            display_name="Embedding Model",
            info=(
                "Default embedding model for the search query. The provider "
                "and model from .env (TUTOR_EMBEDDINGS_PROVIDER, "
                "TUTOR_EMBEDDINGS_MODEL, TUTOR_EMBEDDINGS_PROVIDER_NAME) take "
                "priority over this selection. The resulting vector must be "
                "1024-dimensional to match PostgreSQL."
            ),
            model_type="embedding",
            required=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Standalone search query for the course materials.",
            required=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            value=10,
            info="Maximum number of nearest chunks to inspect, from 1 to 10.",
        ),
        FloatInput(
            name="max_distance",
            display_name="Maximum Cosine Distance",
            info=(
                "Maximum accepted cosine distance. This preliminary "
                "threshold must be calibrated for the course corpus."
            ),
            value=0.5,
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="sufficient_context",
            display_name="Sufficient Context",
            method="build_sufficient_context",
            types=["Message"],
            selected="Message",
            group_outputs=True,
        ),
        Output(
            name="insufficient_context",
            display_name="No Sufficient Context",
            method="build_insufficient_context",
            types=["Message"],
            selected="Message",
            group_outputs=True,
        ),
    ]

    def _search(self):
        """Retrieve chunks and filter them by cosine distance."""
        query = extract_text(self.query)
        if not query:
            raise ValueError("The search query is empty.")

        threshold = float(self.max_distance)
        if not 0.0 <= threshold <= 2.0:
            raise ValueError("Maximum Cosine Distance must be between 0 and 2.")

        top_k = max(1, min(int(self.top_k or 6), 10))

        total_started = time.perf_counter()

        embedding_started = time.perf_counter()
        embedding_model = build_embedding_model(self.model, self.user_id)
        embedding = embedding_model.embed_query(query)
        if len(embedding) != VECTOR_DIMENSION:
            raise ValueError(
                f"Embedding dimension is {len(embedding)}; expected {VECTOR_DIMENSION}."
            )
        embedding_ms = (time.perf_counter() - embedding_started) * 1000

        vector = (
            "[" + ",".join(format(float(value), ".9g") for value in embedding) + "]"
        )

        # LEFT JOIN: чанк не должен пропадать, даже если для него нет
        # записи в documents. documents.text (весь документ) не выбираем.
        sql = f"""
            SELECT
                c.id,
                c.document_id,
                d.filename,
                c.content,
                c.embedding <=> %s::vector AS distance
            FROM {CHUNKS_TABLE} AS c
            LEFT JOIN {DOCUMENTS_TABLE} AS d
                ON d.id = c.document_id
            WHERE c.embedding IS NOT NULL
              AND c.content IS NOT NULL
              AND btrim(c.content) <> ''
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """

        db_started = time.perf_counter()
        with psycopg.connect(
            host=required_setting("TUTOR_DB_HOST"),
            port=int_setting("TUTOR_DB_PORT", 5432),
            dbname=required_setting("TUTOR_DB_NAME"),
            user=required_setting("TUTOR_DB_USER"),
            password=database_password(),
            connect_timeout=int_setting("TUTOR_DB_CONNECT_TIMEOUT_SECONDS", 10),
            options=(
                "-c statement_timeout="
                f"{int_setting('TUTOR_DB_STATEMENT_TIMEOUT_MS', 30000)}"
            ),
            application_name="TutorRAG",
        ) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            try:
                rows = conn.execute(sql, (vector, vector, top_k)).fetchall()
            except (
                psycopg.errors.UndefinedTable,
                psycopg.errors.UndefinedColumn,
            ) as exc:
                raise RuntimeError(
                    "Схема базы не подходит компоненту: ожидаются таблицы "
                    f"{CHUNKS_TABLE}(id, document_id, content, embedding) и "
                    f"{DOCUMENTS_TABLE}(id, filename). "
                    "См. docs/DATABASE_REPLACEMENT.md. "
                    f"Ошибка PostgreSQL: {exc}"
                ) from exc
        db_ms = (time.perf_counter() - db_started) * 1000
        total_ms = (time.perf_counter() - total_started) * 1000

        accepted = []
        for rank, (
            chunk_id,
            document_id,
            filename,
            content,
            distance,
        ) in enumerate(rows, 1):
            if distance is None:
                continue
            distance = float(distance)
            if distance <= threshold:
                header = chunk_header(
                    rank,
                    document_id,
                    chunk_id,
                    distance,
                    document_title(filename),
                )
                accepted.append(f"{header}\n{content}")

        logger.info(
            "Tutor RAG timings: embedding_ms=%.1f db_ms=%.1f "
            "total_ms=%.1f rows=%d accepted=%d",
            embedding_ms,
            db_ms,
            total_ms,
            len(rows),
            len(accepted),
        )

        if accepted:
            return "CONTEXT_FOUND", "\n\n---\n\n".join(accepted)
        if rows:
            return "CONTEXT_INSUFFICIENT", ""
        return "CONTEXT_NOT_FOUND", ""

    def _route(self):
        """Run the search and exclude the unselected branch."""
        # Reuse the result if Langflow evaluates both output methods
        # on the same component instance.
        if not hasattr(self, "_course_search_result"):
            self._course_search_result = self._search()
        status, context = self._course_search_result
        self.status = status

        selected = (
            "sufficient_context"
            if status == "CONTEXT_FOUND"
            else "insufficient_context"
        )
        excluded = [
            name
            for name in ("sufficient_context", "insufficient_context")
            if name != selected
        ]
        for name in excluded:
            self.stop(name)
        self.graph.exclude_branches_conditionally(
            self._id,
            output_names=excluded,
        )
        return selected, context

    def build_sufficient_context(self) -> Message:
        selected, context = self._route()
        if selected != "sufficient_context":
            return Message(text="")
        return Message(text=context)

    def build_insufficient_context(self) -> Message:
        selected, _ = self._route()
        if selected != "insufficient_context":
            return Message(text="")
        return Message(
            text=(
                "В найденных материалах не обнаружено достаточно релевантной "
                "информации для ответа. Пришлите формулировку задания или "
                "уточните, о какой теме курса вы спрашиваете."
            )
        )
