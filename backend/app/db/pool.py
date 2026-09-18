from __future__ import annotations

from typing import Any

from psycopg_pool import ConnectionPool

from app.core.config import get_settings

settings = get_settings()
_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool

    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=5,
            open=False,
        )

    return _pool


class LazyConnectionPool:
    @property
    def closed(self) -> bool:
        if _pool is None:
            return True
        return _pool.closed

    def open(self, *args: Any, **kwargs: Any) -> None:
        _get_pool().open(*args, **kwargs)

    def close(self, *args: Any, **kwargs: Any) -> None:
        global _pool

        if _pool is None:
            return

        _pool.close(*args, **kwargs)
        _pool = None

    def connection(self, *args: Any, **kwargs: Any):
        return _get_pool().connection(*args, **kwargs)


pool = LazyConnectionPool()


def open_pool() -> None:
    if pool.closed:
        pool.open(wait=True)


def close_pool() -> None:
    if not pool.closed:
        pool.close()
