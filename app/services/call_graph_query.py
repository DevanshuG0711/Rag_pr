import os

import psycopg2


def get_call_graph_for_file(file_name: str) -> dict[str, list[str]]:
    if not file_name:
        return {}

    dsn = os.getenv("POSTGRES_DSN") or ""
    if not dsn:
        return {}

    graph: dict[str, list[str]] = {}

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT function_name, called_functions
                FROM call_graph
                WHERE file_name = %s
                """,
                (file_name,),
            )
            rows = cur.fetchall()

    for function_name, called_functions in rows:
        graph[str(function_name)] = [str(name) for name in (called_functions or [])]

    return graph
