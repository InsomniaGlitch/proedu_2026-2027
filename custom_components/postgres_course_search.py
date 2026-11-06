import base64
import logging
import os
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
TABLE = "public.document_chunks"


def required_setting(name: str) -> str:
    """Read a required setting from the container environment."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment setting {name} is missing.")
    return value


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


def extract_text(value) -> str:
    """Extract plain text from a Langflow input."""
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""

    if hasattr(value, "text"):
        value = value.text
    elif hasattr(value, "data") and isinstance(value.data, dict):
        data = value.data
        value = (
            data.get("text")
            or data.get("content")
            or data.get("message")
            or str(data)
        )
    elif isinstance(value, dict):
        value = (
            value.get("text")
            or value.get("content")
            or value.get("message")
            or str(value)
        )

    return str(value or "").strip()


def database_password() -> str:
    """Decode the locally configured database password."""
    encoded = required_setting("TUTOR_DB_PASSWORD_B64")

    try:
        return base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError(
            "TUTOR_DB_PASSWORD_B64 must contain valid UTF-8 Base64 data."
        ) from exc


class PostgresCourseSearch(Component):
    display_name = "PostgreSQL Course Search"
    description = (
        "Search PostgreSQL chunks and route results by cosine distance."
    )
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
                "Select an embedding model compatible with the vectors "
                "stored in PostgreSQL. For the current database, use "
                "bge-m3:latest."
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
            raise ValueError(
                "Maximum Cosine Distance must be between 0 and 2."
            )

        top_k = max(1, min(int(self.top_k or 6), 10))

        total_started = time.perf_counter()
        embedding_started = time.perf_counter()

        embedding_model = get_embeddings(
            model=self.model,
            user_id=self.user_id,
            ollama_base_url=required_setting("OLLAMA_BASE_URL"),
        )
        embedding = embedding_model.embed_query(query)

        if len(embedding) != VECTOR_DIMENSION:
            raise ValueError(
                f"Embedding dimension is {len(embedding)}; "
                f"expected {VECTOR_DIMENSION}."
            )

        embedding_ms = (time.perf_counter() - embedding_started) * 1000

        vector = "[" + ",".join(
            format(float(value), ".9g") for value in embedding
        ) + "]"

        sql = f"""
            SELECT
                id,
                document_id,
                content,
                embedding <=> %s::vector AS distance
            FROM {TABLE}
            WHERE embedding IS NOT NULL
              AND content IS NOT NULL
              AND btrim(content) <> ''
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """

        db_started = time.perf_counter()

        with psycopg.connect(
            host=required_setting("TUTOR_DB_HOST"),
            port=int_setting("TUTOR_DB_PORT", 5432),
            dbname=required_setting("TUTOR_DB_NAME"),
            user=required_setting("TUTOR_DB_USER"),
            password=database_password(),
            connect_timeout=int_setting(
                "TUTOR_DB_CONNECT_TIMEOUT_SECONDS", 10
            ),
            options=(
                "-c statement_timeout="
                f"{int_setting('TUTOR_DB_STATEMENT_TIMEOUT_MS', 30000)}"
            ),
            application_name="TutorRAG",
        ) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            rows = conn.execute(sql, (vector, vector, top_k)).fetchall()

        db_ms = (time.perf_counter() - db_started) * 1000
        total_ms = (time.perf_counter() - total_started) * 1000

        accepted = []

        for rank, (chunk_id, document_id, content, distance) in enumerate(
            rows, 1
        ):
            if distance is None:
                continue

            distance = float(distance)

            if distance <= threshold:
                accepted.append(
                    f"[{rank}; document_id={document_id}; "
                    f"chunk_id={chunk_id}; "
                    f"cosine_distance={distance:.4f}]\n"
                    f"{content}"
                )

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
