from fastapi import APIRouter, HTTPException

from app.db.pool import pool

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict:
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                value = cur.fetchone()[0]
        return {"status": "ok", "database": value == 1}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Banco indisponível") from exc
