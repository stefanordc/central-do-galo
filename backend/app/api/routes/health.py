import logging

from fastapi import APIRouter, HTTPException

from app.db.pool import pool

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger("central_galo.health")


@router.get("")
def health() -> dict:
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                value = cur.fetchone()[0]

        return {
            "status": "ok",
            "database": value == 1,
        }
    except RuntimeError as exc:
        logger.error("[health] configuração do banco inválida: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[health] banco indisponível: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Banco indisponível. Verifique conexão e credenciais DB_*.",
        ) from exc
