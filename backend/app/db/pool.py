from psycopg_pool import ConnectionPool

from app.core.config import get_settings

settings = get_settings()

pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=5,
    open=False,
)


def open_pool() -> None:
    if pool.closed:
        pool.open(wait=True)


def close_pool() -> None:
    if not pool.closed:
        pool.close()
