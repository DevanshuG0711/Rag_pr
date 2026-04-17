import logging
import os

import psycopg2

logger = logging.getLogger(__name__)

_table_initialized = False


def _postgres_dsn() -> str:
    dsn = os.getenv("POSTGRES_DSN")
    return dsn or ""


def _ensure_table(conn) -> None:
    global _table_initialized

    if _table_initialized:
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS call_graph (
                id BIGSERIAL PRIMARY KEY,
                function_name TEXT NOT NULL,
                file_name TEXT NOT NULL,
                called_functions TEXT[] NOT NULL DEFAULT '{}',
                UNIQUE (file_name, function_name)
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_call_graph_function_name
            ON call_graph (function_name)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_call_graph_file_name
            ON call_graph (file_name)
            """
        )

    conn.commit()
    _table_initialized = True


def upsert_call_graph(file_name: str, call_graph: dict[str, list[str]]) -> int:
    if not file_name or not call_graph:
        return 0

    dsn = _postgres_dsn()
    if not dsn:
        logger.info("Postgres not configured, skipping call graph storage")
        return 0

    rows = 0
    try:
        with psycopg2.connect(dsn) as conn:

            _ensure_table(conn)

            with conn.cursor() as cur:
                for function_name, called_functions in call_graph.items():
                    normalized_called = [str(name) for name in (called_functions or [])]

                    cur.execute(
                        """
                        INSERT INTO call_graph (function_name, file_name, called_functions)
                        VALUES (%s, %s, %s::text[])
                        ON CONFLICT (file_name, function_name)
                        DO UPDATE SET called_functions = EXCLUDED.called_functions
                        """,
                        (function_name, file_name, normalized_called),
                    )
                    rows += 1

            conn.commit()
            logger.debug("Call graph stored")
    except Exception as e:
        logger.exception("Failed to upsert call graph")
        raise

    return rows
